"""
文件存储操作模块 — 管理知识库的目录结构和文件读写
"""
import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from src.config import settings
from src.models import KBConfig, KBStats, RawDocument, WikiPageSummary


# ─────────────────────────────────────────────
# 路径管理
# ─────────────────────────────────────────────

def kb_dir(kb_id: str) -> Path:
    """知识库根目录"""
    return settings.kb_base_dir / kb_id


def raw_dir(kb_id: str) -> Path:
    return kb_dir(kb_id) / "raw"


def wiki_dir(kb_id: str) -> Path:
    return kb_dir(kb_id) / "wiki"


def source_dir(kb_id: str) -> Path:
    return wiki_dir(kb_id) / "source"


def entity_dir(kb_id: str) -> Path:
    return wiki_dir(kb_id) / "entity"


def concept_dir(kb_id: str) -> Path:
    return wiki_dir(kb_id) / "concept"


def db_dir(kb_id: str) -> Path:
    return kb_dir(kb_id) / "db"


def config_path(kb_id: str) -> Path:
    return kb_dir(kb_id) / "config.json"


def index_path(kb_id: str) -> Path:
    return wiki_dir(kb_id) / "index.md"


def graph_path(kb_id: str) -> Path:
    return db_dir(kb_id) / "graph.json"


def fts_db_path(kb_id: str) -> Path:
    return db_dir(kb_id) / "fts.db"


# ─────────────────────────────────────────────
# 知识库创建 & 加载
# ─────────────────────────────────────────────

def init_kb_dirs(kb_id: str) -> None:
    """初始化知识库目录结构"""
    for d in [
        raw_dir(kb_id),
        source_dir(kb_id),
        entity_dir(kb_id),
        concept_dir(kb_id),
        db_dir(kb_id),
    ]:
        d.mkdir(parents=True, exist_ok=True)


def save_kb_config(config: KBConfig) -> None:
    """保存知识库配置"""
    cfg_path = config_path(config.kb_id)
    cfg_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def load_kb_config(kb_id: str) -> KBConfig | None:
    """加载知识库配置，不存在返回 None"""
    cfg_path = config_path(kb_id)
    if not cfg_path.exists():
        return None
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return KBConfig(**data)


def list_kb_ids() -> list[str]:
    """列出所有知识库 ID"""
    base = settings.kb_base_dir
    if not base.exists():
        return []
    return [
        d.name
        for d in base.iterdir()
        if d.is_dir() and (d / "config.json").exists()
    ]


def get_kb_stats(kb_id: str) -> KBStats:
    """统计知识库当前状态"""
    stats = KBStats(kb_id=kb_id)

    r_dir = raw_dir(kb_id)
    if r_dir.exists():
        stats.raw_count = len(list(r_dir.glob("*.md")))

    s_dir = source_dir(kb_id)
    if s_dir.exists():
        stats.source_count = len(list(s_dir.glob("*.md")))

    e_dir = entity_dir(kb_id)
    if e_dir.exists():
        stats.entity_count = len(list(e_dir.glob("*.md")))

    c_dir = concept_dir(kb_id)
    if c_dir.exists():
        stats.concept_count = len(list(c_dir.glob("*.md")))

    stats.indexed = fts_db_path(kb_id).exists()

    return stats


# ─────────────────────────────────────────────
# Doc ID 生成
# ─────────────────────────────────────────────

def generate_doc_id(title: str, url: str = "") -> str:
    """
    由标题和 URL 生成唯一 doc_id
    格式：{slug}_{8位hash}
    """
    slug = _title_to_slug(title)
    source = (url or title).encode("utf-8")
    hash_suffix = hashlib.md5(source).hexdigest()[:8]
    return f"{slug}_{hash_suffix}"


def _title_to_slug(title: str) -> str:
    """将标题转换为 URL-safe slug"""
    # 移除特殊字符，保留字母数字和中文
    text = unicodedata.normalize("NFKD", title)
    # 替换中文和特殊字符中间的空白
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-").lower()
    # 限制长度
    if len(text) > 40:
        text = text[:40].rstrip("-")
    return text or "doc"


# ─────────────────────────────────────────────
# Raw 文档存储
# ─────────────────────────────────────────────

async def save_raw_document(kb_id: str, doc: RawDocument) -> str:
    """保存原始文档，返回 doc_id"""
    if not doc.doc_id:
        doc.doc_id = generate_doc_id(doc.title, doc.url)

    raw_path = raw_dir(kb_id) / f"{doc.doc_id}.md"
    content = _render_raw_markdown(doc)

    async with aiofiles.open(raw_path, "w", encoding="utf-8") as f:
        await f.write(content)

    return doc.doc_id


def _render_raw_markdown(doc: RawDocument) -> str:
    """将 RawDocument 渲染为 Markdown 格式"""
    lines = [f"# {doc.title}", "", f"> 抓取时间：{doc.crawled_at.strftime('%Y/%m/%d %H:%M:%S')}", "", "---", ""]

    if doc.url:
        lines += ["## 🔗 来源链接", "", doc.url, ""]

    lines += ["## 📝 正文", "", doc.content, ""]

    if doc.metadata:
        lines += ["## 📊 元数据", ""]
        lines += ["| 指标 | 数值 |", "|------|------|"]
        for k, v in doc.metadata.items():
            lines.append(f"| {k} | {v} |")
        lines.append("")

    return "\n".join(lines)


def load_raw_document(kb_id: str, doc_id: str) -> str | None:
    """读取原始文档内容"""
    path = raw_dir(kb_id) / f"{doc_id}.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def list_raw_doc_ids(kb_id: str) -> list[str]:
    """列出所有原始文档 ID"""
    r_dir = raw_dir(kb_id)
    if not r_dir.exists():
        return []
    return [p.stem for p in sorted(r_dir.glob("*.md"))]


# ─────────────────────────────────────────────
# Wiki 页面存储
# ─────────────────────────────────────────────

async def save_wiki_page(kb_id: str, page_type: str, name: str, content: str) -> None:
    """保存 Wiki 页面"""
    if page_type == "source":
        path = source_dir(kb_id) / f"{name}.md"
    elif page_type == "entity":
        path = entity_dir(kb_id) / f"{name}.md"
    elif page_type == "concept":
        path = concept_dir(kb_id) / f"{name}.md"
    else:
        raise ValueError(f"Unknown page_type: {page_type}")

    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)


def load_wiki_page(kb_id: str, page_type: str, name: str) -> str | None:
    """读取 Wiki 页面内容"""
    if page_type == "source":
        path = source_dir(kb_id) / f"{name}.md"
    elif page_type == "entity":
        path = entity_dir(kb_id) / f"{name}.md"
    elif page_type == "concept":
        path = concept_dir(kb_id) / f"{name}.md"
    else:
        return None

    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def list_wiki_pages(kb_id: str, page_type: str) -> list[WikiPageSummary]:
    """列出指定类型的所有 Wiki 页面摘要"""
    if page_type == "source":
        target_dir = source_dir(kb_id)
    elif page_type == "entity":
        target_dir = entity_dir(kb_id)
    elif page_type == "concept":
        target_dir = concept_dir(kb_id)
    else:
        return []

    if not target_dir.exists():
        return []

    results = []
    for path in sorted(target_dir.glob("*.md")):
        name = path.stem
        description, updated = _extract_page_meta(path.read_text(encoding="utf-8"))
        results.append(WikiPageSummary(
            name=name,
            type=page_type,
            description=description,
            updated=updated,
        ))
    return results


def _extract_page_meta(content: str) -> tuple[str, str]:
    """从页面内容提取描述和更新时间"""
    description = ""
    updated = ""

    # 从 frontmatter 提取 updated
    fm_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        m = re.search(r"updated:\s*(.+)", fm)
        if m:
            updated = m.group(1).strip()

    # 提取 > 描述行（标题后的第一个引用块）
    desc_match = re.search(r"^# .+\n+> (.+)", content, re.MULTILINE)
    if desc_match:
        description = desc_match.group(1).strip()

    return description, updated


def source_page_exists(kb_id: str, doc_id: str) -> bool:
    return (source_dir(kb_id) / f"{doc_id}.md").exists()


def entity_page_exists(kb_id: str, name: str) -> bool:
    return (entity_dir(kb_id) / f"{name}.md").exists()


def concept_page_exists(kb_id: str, name: str) -> bool:
    return (concept_dir(kb_id) / f"{name}.md").exists()


# ─────────────────────────────────────────────
# 抽取结果持久化（Stage 3a 原始输出）
# ─────────────────────────────────────────────

def extraction_path(kb_id: str) -> Path:
    """抽取结果 JSON 路径"""
    return wiki_dir(kb_id) / "extraction.json"


async def save_extraction(kb_id: str, entities: list, concepts: list) -> None:
    """保存实体/概念抽取结果（Stage 3a 原始输出）"""
    data = {
        "entities": [e if isinstance(e, dict) else e.model_dump() for e in entities],
        "concepts": [c if isinstance(c, dict) else c.model_dump() for c in concepts],
        "updated_at": datetime.now().isoformat(),
    }
    path = extraction_path(kb_id)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))


def load_extraction(kb_id: str) -> dict | None:
    """加载实体/概念抽取结果"""
    path = extraction_path(kb_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────
# 图谱数据存储
# ─────────────────────────────────────────────

async def save_graph(kb_id: str, graph_data: dict[str, Any]) -> None:
    """保存图谱 JSON"""
    path = graph_path(kb_id)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(graph_data, ensure_ascii=False, indent=2))


def load_graph(kb_id: str) -> dict[str, Any] | None:
    """加载图谱数据"""
    path = graph_path(kb_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def extract_wikilinks(content: str) -> list[str]:
    """从 Markdown 内容中提取所有 [[WikiLink]]"""
    pattern = r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]"
    return re.findall(pattern, content)


def clean_markdown_for_embedding(content: str) -> str:
    """清除 Markdown 语法，只保留文本内容（用于向量化）"""
    # 移除 frontmatter
    text = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
    # 移除代码块
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # 移除行内代码
    text = re.sub(r"`[^`]+`", "", text)
    # 移除图片
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    # 将 [[WikiLink|显示文本]] → 显示文本
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    # 将 [[WikiLink]] → WikiLink
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # 移除普通链接
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # 移除 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 移除 Markdown 标题符号
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 移除加粗/斜体
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    # 压缩空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
