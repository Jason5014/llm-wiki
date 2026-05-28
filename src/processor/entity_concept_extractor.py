"""
Stage 3a: 实体/概念批量抽取
从 source 页面中提取跨文章的实体和概念
"""
import logging
from collections import defaultdict

from src.config import settings
from src.llm import chat_json, llm_executor
from src.models import ConceptData, EntityData
from src.storage import list_wiki_pages, load_wiki_page

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """你是知识库构建专家，从文章摘要集合中识别知识图谱元素。

【实体（entity）】= 具体的事物：产品、公司、工具、框架、人物、项目
示例：Claude、OpenAI、MCP、LangChain、吴恩达、Cursor

【概念（concept）】= 抽象的技术/方法/模式/理论
示例：agent、rag、工具调用、prompt engineering、工作流、向量数据库

输出严格的 JSON 格式：
{
  "entities": [
    {
      "name": "标准名称（英文 PascalCase）",
      "category": "product|company|tool|person|project|other",
      "description": "一句话描述",
      "aliases": ["别名列表"],
      "related_entities": ["关联实体名"],
      "related_concepts": ["关联概念名"],
      "source_docs": ["文档ID列表"]
    }
  ],
  "concepts": [
    {
      "name": "标准名称（小写英文或中文）",
      "category": "technology|method|pattern|theory|term|other",
      "description": "1-2句描述",
      "aliases": ["别名，如中英文互译"],
      "related_concepts": ["关联概念"],
      "related_entities": ["关联实体"],
      "source_docs": ["文档ID列表"]
    }
  ]
}

规则：
- 只提取真正重要的、反复出现的知识点
- 过于通用的词（AI、技术、系统等）单独出现时忽略
- 每个实体/概念只出现一次（做好去重）
- source_docs 填入来源文档的 doc_id（从摘要头部的"原始文档：XXX"获取）"""

USER_PROMPT_TEMPLATE = """请从以下 {count} 篇文章摘要中，提取所有重要的实体和概念：

{summaries}"""


# ─────────────────────────────────────────────
# 批量抽取
# ─────────────────────────────────────────────

async def extract_entities_concepts(
    kb_id: str,
    doc_ids: list[str] | None = None,
    progress_callback=None,
) -> tuple[list[EntityData], list[ConceptData]]:
    """
    批量抽取所有实体和概念
    Returns: (entities, concepts)
    """
    # 获取所有 source 页面
    if doc_ids:
        all_source_ids = doc_ids
    else:
        pages = list_wiki_pages(kb_id, "source")
        all_source_ids = [p.name for p in pages]

    if not all_source_ids:
        logger.warning("没有可用的 source 页面")
        return [], []

    total = len(all_source_ids)
    batch_size = settings.extraction_batch_size
    batches = [
        all_source_ids[i : i + batch_size]
        for i in range(0, total, batch_size)
    ]

    logger.info(f"开始实体/概念抽取，共 {total} 篇，{len(batches)} 批")

    all_entities: dict[str, EntityData] = {}
    all_concepts: dict[str, ConceptData] = {}
    completed_batches = 0

    for batch_idx, batch in enumerate(batches):
        logger.info(f"处理批次 {batch_idx + 1}/{len(batches)}")

        # 读取这一批的 source 页面内容
        summaries = _build_batch_summaries(kb_id, batch)
        if not summaries:
            continue

        try:
            result = await llm_executor.run(
                chat_json([
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": USER_PROMPT_TEMPLATE.format(
                            count=len(batch),
                            summaries=summaries,
                        ),
                    },
                ])
            )
        except Exception as e:
            logger.error(f"批次 {batch_idx + 1} LLM 调用失败：{e}")
            continue

        # 合并实体
        for e_data in result.get("entities", []):
            _merge_entity(all_entities, EntityData(**e_data))

        # 合并概念
        for c_data in result.get("concepts", []):
            _merge_concept(all_concepts, ConceptData(**c_data))

        completed_batches += 1
        if progress_callback:
            await progress_callback(
                completed_batches,
                len(batches),
                f"批次 {batch_idx + 1}/{len(batches)} 完成，已识别 {len(all_entities)} 实体 {len(all_concepts)} 概念",
            )

    entities = list(all_entities.values())
    concepts = list(all_concepts.values())
    logger.info(f"抽取完成：{len(entities)} 实体，{len(concepts)} 概念")
    return entities, concepts


def _build_batch_summaries(kb_id: str, doc_ids: list[str]) -> str:
    """将一批 source 页面拼接成输入文本"""
    parts = []
    for doc_id in doc_ids:
        content = load_wiki_page(kb_id, "source", doc_id)
        if content:
            parts.append(f"=== 文章 {doc_id} ===\n{content}\n")
    return "\n".join(parts)


def _merge_entity(store: dict[str, EntityData], new: EntityData) -> None:
    """跨批次合并实体（按名称 case-insensitive）"""
    key = new.name.lower()
    if key in store:
        existing = store[key]
        # 合并别名
        existing.aliases = list(set(existing.aliases + new.aliases))
        # 合并关联
        existing.related_entities = list(set(existing.related_entities + new.related_entities))
        existing.related_concepts = list(set(existing.related_concepts + new.related_concepts))
        # 合并来源
        existing.source_docs = list(set(existing.source_docs + new.source_docs))
        # 如果新版本描述更详细，替换
        if len(new.description) > len(existing.description):
            existing.description = new.description
    else:
        store[key] = new


def _merge_concept(store: dict[str, ConceptData], new: ConceptData) -> None:
    """跨批次合并概念"""
    key = new.name.lower()
    if key in store:
        existing = store[key]
        existing.aliases = list(set(existing.aliases + new.aliases))
        existing.related_concepts = list(set(existing.related_concepts + new.related_concepts))
        existing.related_entities = list(set(existing.related_entities + new.related_entities))
        existing.source_docs = list(set(existing.source_docs + new.source_docs))
        if len(new.description) > len(existing.description):
            existing.description = new.description
    else:
        store[key] = new
