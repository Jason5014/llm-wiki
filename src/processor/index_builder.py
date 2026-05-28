"""
Stage 4: 索引构建
生成 index.md + Milvus 向量索引 + SQLite FTS5 + 图谱 JSON
"""
import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from src.storage import (
    concept_dir,
    entity_dir,
    extract_wikilinks,
    index_path,
    list_wiki_pages,
    load_wiki_page,
    save_graph,
    source_dir,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# index.md 生成
# ─────────────────────────────────────────────

def build_index_md(kb_id: str) -> str:
    """扫描所有 wiki 页面，生成 index.md"""
    today = datetime.now().strftime("%Y-%m-%d")

    source_pages = list_wiki_pages(kb_id, "source")
    entity_pages = list_wiki_pages(kb_id, "entity")
    concept_pages = list_wiki_pages(kb_id, "concept")

    # 按 category 分组
    entity_by_cat: dict[str, list] = defaultdict(list)
    for p in entity_pages:
        cat = _get_frontmatter_field(kb_id, "entity", p.name, "category") or "other"
        entity_by_cat[cat].append(p)

    concept_by_cat: dict[str, list] = defaultdict(list)
    for p in concept_pages:
        cat = _get_frontmatter_field(kb_id, "concept", p.name, "category") or "other"
        concept_by_cat[cat].append(p)

    # 收集别名
    aliases = _collect_aliases(kb_id, entity_pages, concept_pages)

    lines = [
        "---",
        f"type: index",
        f"version: 1.0.0",
        f"last-updated: {today}",
        f"source-count: {len(source_pages)}",
        f"entity-count: {len(entity_pages)}",
        f"concept-count: {len(concept_pages)}",
        "---",
        "",
        "# 全局知识库索引",
        "",
        "## 一、概念体系目录（concepts）",
        "",
    ]

    # 概念目录
    cat_labels = {
        "technology": "核心技术",
        "method": "方法论",
        "pattern": "设计模式",
        "theory": "理论基础",
        "term": "术语",
        "other": "其他",
    }
    for cat, label in cat_labels.items():
        pages = concept_by_cat.get(cat, [])
        if pages:
            lines.append(f"### {label}")
            for p in sorted(pages, key=lambda x: x.name):
                lines.append(f"- [[concept/{p.name}]] — {p.description or p.name}")
            lines.append("")

    lines += ["", "## 二、实体对象目录（entities）", ""]

    # 实体目录
    ent_cat_labels = {
        "product": "AI 模型与产品",
        "company": "公司与组织",
        "tool": "工具与框架",
        "person": "人物",
        "project": "项目与平台",
        "other": "其他",
    }
    for cat, label in ent_cat_labels.items():
        pages = entity_by_cat.get(cat, [])
        if pages:
            lines.append(f"### {label}")
            for p in sorted(pages, key=lambda x: x.name):
                lines.append(f"- [[entity/{p.name}]] — {p.description or p.name}")
            lines.append("")

    lines += ["", "## 三、原始资料索引（sources）", ""]
    for p in sorted(source_pages, key=lambda x: x.name):
        lines.append(f"- [[source/{p.name}]] — {p.description or p.name}")

    # 别名索引
    if aliases:
        lines += ["", "## 四、别名索引", "", "| 别名 | 指向 |", "|------|------|"]
        for alias, target in sorted(aliases.items()):
            lines.append(f"| {alias} | {target} |")

    # 健康状态
    lines += [
        "",
        "## 五、健康状态",
        "",
        f"- 原始文档：{len(source_pages)} 篇",
        f"- Source 页面：{len(source_pages)} 个",
        f"- Entity 页面：{len(entity_pages)} 个",
        f"- Concept 页面：{len(concept_pages)} 个",
        f"- 上次更新：{today}",
        "",
    ]

    content = "\n".join(lines)

    # 保存
    path = index_path(kb_id)
    path.write_text(content, encoding="utf-8")
    logger.info(f"index.md 已生成（{len(entity_pages)} 实体，{len(concept_pages)} 概念）")
    return content


def _get_frontmatter_field(kb_id: str, page_type: str, name: str, field: str) -> str | None:
    """从 Wiki 页面的 frontmatter 提取指定字段"""
    content = load_wiki_page(kb_id, page_type, name)
    if not content:
        return None
    m = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None
    fm = m.group(1)
    fm_match = re.search(rf"^{field}:\s*(.+)", fm, re.MULTILINE)
    return fm_match.group(1).strip() if fm_match else None


def _collect_aliases(kb_id: str, entity_pages, concept_pages) -> dict[str, str]:
    """从所有页面的 frontmatter 中收集别名"""
    aliases: dict[str, str] = {}

    for p in entity_pages:
        content = load_wiki_page(kb_id, "entity", p.name)
        if content:
            _extract_aliases_from_frontmatter(content, f"[[entity/{p.name}]]", aliases)

    for p in concept_pages:
        content = load_wiki_page(kb_id, "concept", p.name)
        if content:
            _extract_aliases_from_frontmatter(content, f"[[concept/{p.name}]]", aliases)

    return aliases


def _extract_aliases_from_frontmatter(content: str, target: str, store: dict) -> None:
    """从 frontmatter 的 aliases 字段提取别名"""
    m = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return
    fm = m.group(1)
    # aliases: ["别名1", "别名2"] 或 aliases: [别名1]
    am = re.search(r"aliases:\s*\[([^\]]*)\]", fm)
    if not am:
        return
    raw = am.group(1)
    # 提取引号内的内容或裸词
    found = re.findall(r'"([^"]+)"|\'([^\']+)\'|(\S+)', raw)
    for groups in found:
        alias = next(g for g in groups if g)
        alias = alias.strip(",").strip()
        if alias:
            store[alias] = target


# ─────────────────────────────────────────────
# 图谱 JSON 构建
# ─────────────────────────────────────────────

async def build_graph_json(kb_id: str) -> dict[str, Any]:
    """
    从所有 entity/concept 页面提取 [[WikiLink]]，生成图谱数据
    """
    nodes: dict[str, dict] = {}
    edge_set: set[tuple] = set()

    entity_pages = list_wiki_pages(kb_id, "entity")
    concept_pages = list_wiki_pages(kb_id, "concept")

    # 先注册所有节点
    for p in entity_pages:
        node_id = f"entity:{p.name}"
        nodes[node_id] = {
            "id": node_id,
            "label": p.name,
            "type": "entity",
            "category": _get_frontmatter_field(kb_id, "entity", p.name, "category") or "other",
            "description": p.description,
        }

    for p in concept_pages:
        node_id = f"concept:{p.name}"
        nodes[node_id] = {
            "id": node_id,
            "label": p.name,
            "type": "concept",
            "category": _get_frontmatter_field(kb_id, "concept", p.name, "category") or "other",
            "description": p.description,
        }

    # 提取边（WikiLink 引用关系）
    edges_list: list[dict] = []
    all_names = (
        {p.name.lower(): f"entity:{p.name}" for p in entity_pages}
        | {p.name.lower(): f"concept:{p.name}" for p in concept_pages}
    )

    def _process_page(page_type: str, name: str):
        content = load_wiki_page(kb_id, page_type, name)
        if not content:
            return
        source_id = f"{page_type}:{name}"
        links = extract_wikilinks(content)
        for link in links:
            # 去掉可能的路径前缀
            link_name = link.split("/")[-1]
            target_id = all_names.get(link_name.lower())
            if target_id and target_id != source_id:
                edge_key = (source_id, target_id)
                if edge_key not in edge_set:
                    edge_set.add(edge_key)
                    edges_list.append({
                        "source": source_id,
                        "target": target_id,
                        "type": "related",
                        "weight": 1.0,
                    })

    for p in entity_pages:
        _process_page("entity", p.name)
    for p in concept_pages:
        _process_page("concept", p.name)

    graph_data = {
        "nodes": list(nodes.values()),
        "edges": edges_list,
    }

    await save_graph(kb_id, graph_data)
    logger.info(f"图谱构建完成：{len(nodes)} 节点，{len(edges_list)} 边")
    return graph_data
