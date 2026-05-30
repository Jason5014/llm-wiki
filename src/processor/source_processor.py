"""
Stage 2: Source 摘要生成
将原始文档处理为结构化的 wiki/source 摘要页
"""
import asyncio
import logging
from datetime import datetime

from src.config import settings
from src.llm import chat_json, llm_executor
from src.models import SourcePage
from src.storage import (
    clean_markdown_for_embedding,
    list_raw_doc_ids,
    load_raw_document,
    save_wiki_page,
    source_page_exists,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Prompt 定义
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """你是知识库构建助手，将原始网页/文章处理为结构化 Wiki 知识条目。

你必须输出严格的 JSON 格式（不要输出任何其他文字）：
{
  "title": "文章原标题",
  "content_type": "tutorial|guide|news|opinion|comparison|case-study|other",
  "theme": "2-3句话描述核心主题和角度",
  "key_points": ["要点1", "要点2"],
  "tags": ["标签1", "标签2"],
  "entities": ["Claude", "OpenAI"],
  "concepts": ["agent", "rag"]
}

规则：
- entities：用英文标准名（Claude、MCP、LangChain），具体产品/公司/工具/框架
- concepts：用小写英文或中文标准名（agent、rag、工具调用），技术概念/方法/模式
- key_points：4-8条，保留技术细节、数字、命令名
- tags：5-10个关键词标签
- 过于通用的词（AI、技术、方法等）单独出现时不作为 entity/concept"""

USER_PROMPT_TEMPLATE = """请分析以下文章，生成结构化摘要：

---
{content}
---"""


# ─────────────────────────────────────────────
# Source 页面 Markdown 模板
# ─────────────────────────────────────────────

def render_source_page(doc_id: str, page: SourcePage) -> str:
    """将 SourcePage 渲染为 Markdown 格式"""
    lines = [
        f"> 原始文档：{doc_id}",
        "",
        "---",
        "## 📋 基本信息",
        f"- **原标题**：{page.title}",
        f"- **内容类型**：{page.content_type}",
    ]

    if page.url:
        lines.append(f"- **来源**：{page.url}")

    lines += [
        "",
        "## 🎯 核心主题",
        page.theme,
        "",
        "## 📌 关键要点",
    ]
    for point in page.key_points:
        lines.append(f"- {point}")

    lines += ["", "## 🏷️ 关键词标签"]
    if page.tags:
        tag_line = " ".join(f"#[[{t}]]" for t in page.tags)
        lines.append(tag_line)

    if page.entities:
        lines += ["", "## 🔗 相关实体"]
        for entity in page.entities:
            lines.append(f"[[{entity}]]")

    if page.concepts:
        lines += ["", "## 💡 关联概念"]
        for concept in page.concepts:
            lines.append(f"[[{concept}]]")

    lines += ["", "---"]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# 核心处理函数
# ─────────────────────────────────────────────

async def process_single_document(
    kb_id: str,
    doc_id: str,
    force: bool = False,
) -> SourcePage | None:
    """
    处理单个原始文档，生成 source 摘要页
    返回 None 表示跳过（已存在且未强制）
    """
    # 跳过检查
    if not force and source_page_exists(kb_id, doc_id):
        logger.debug(f"跳过（已存在）：{doc_id}")
        return None

    # 读取原始内容
    raw_content = load_raw_document(kb_id, doc_id)
    if not raw_content:
        logger.warning(f"原始文档不存在：{doc_id}")
        return None

    # 清洗 + 截断
    cleaned = clean_markdown_for_embedding(raw_content)
    if len(cleaned) > settings.max_content_chars:
        cleaned = cleaned[: settings.max_content_chars]
        logger.debug(f"文档截断到 {settings.max_content_chars} 字符：{doc_id}")

    # 调用 LLM（受并发限制）
    try:
        result = await llm_executor.run(
            chat_json([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(content=cleaned)},
            ])
        )
    except Exception as e:
        logger.error(f"LLM 调用失败（{doc_id}）：{e}")
        return None

    # 构建 SourcePage
    page = SourcePage(
        doc_id=doc_id,
        title=result.get("title", doc_id),
        content_type=result.get("content_type", "other"),
        theme=result.get("theme", ""),
        key_points=result.get("key_points", []),
        tags=result.get("tags", []),
        entities=result.get("entities", []),
        concepts=result.get("concepts", []),
        processed_at=datetime.now(),
    )
    page.raw_markdown = render_source_page(doc_id, page)

    # 保存
    await save_wiki_page(kb_id, "source", doc_id, page.raw_markdown)
    logger.info(f"✅ 处理完成：{doc_id}")
    return page


async def process_all_sources(
    kb_id: str,
    force: bool = False,
    doc_ids: list[str] | None = None,
    progress_callback=None,
    error_callback=None,
) -> list[SourcePage]:
    """
    批量处理所有原始文档（并发受限）
    progress_callback(completed, total, message) 用于进度上报
    error_callback(msg) 用于上报非致命错误
    """
    all_ids = doc_ids or list_raw_doc_ids(kb_id)
    total = len(all_ids)

    if not all_ids:
        msg = "没有找到待处理的原始文档"
        logger.warning(msg)
        if error_callback:
            await error_callback(msg)
        return []

    logger.info(f"开始处理 source 阶段，共 {total} 篇文档")

    results: list[SourcePage] = []
    completed = 0
    failed = 0

    # 使用信号量限制并发（最多 llm_max_concurrent 个同时运行）
    semaphore = asyncio.Semaphore(settings.llm_max_concurrent)

    async def _process_with_sem(doc_id: str):
        nonlocal completed, failed
        async with semaphore:
            page = await process_single_document(kb_id, doc_id, force=force)
            completed += 1
            if page:
                msg = f"✅ 处理完成：{doc_id}"
            elif page is None and not force and source_page_exists(kb_id, doc_id):
                msg = f"⏭️ 跳过（已存在）：{doc_id}"
            else:
                failed += 1
                msg = f"❌ 处理失败：{doc_id}"
                if error_callback:
                    await error_callback(msg)
            if progress_callback:
                await progress_callback(completed, total, msg)
            return page

    tasks = [_process_with_sem(doc_id) for doc_id in all_ids]
    pages = await asyncio.gather(*tasks, return_exceptions=True)

    for p in pages:
        if isinstance(p, SourcePage):
            results.append(p)
        elif isinstance(p, Exception):
            failed += 1
            err_msg = f"处理异常：{p}"
            logger.error(err_msg)
            if error_callback:
                await error_callback(err_msg)

    logger.info(f"source 阶段完成，成功 {len(results)}/{total}，失败 {failed}")

    if failed > 0 and not results:
        if error_callback:
            await error_callback(f"所有 {failed} 篇文档处理失败，请检查 LLM API 配置")

    return results
