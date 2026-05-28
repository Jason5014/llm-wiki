"""
混合检索引擎 — Direct Lookup + 向量检索 + FTS5 + RRF 融合
"""
import logging
import time
from typing import Any

from src.indexer.indexer import collection_name, fts_search, get_milvus_client
from src.llm import chat_completion, embed_single
from src.models import SearchResponse, SearchResult
from src.storage import (
    extract_wikilinks,
    list_wiki_pages,
    load_wiki_page,
)

logger = logging.getLogger(__name__)

# RRF 参数
RRF_K = 60


# ─────────────────────────────────────────────
# 三路检索
# ─────────────────────────────────────────────

def direct_lookup(kb_id: str, query: str) -> list[SearchResult]:
    """
    直接查找：在 entity/concept 名称中做精确/包含匹配
    """
    results = []
    query_lower = query.lower()

    for page_type in ("entity", "concept"):
        pages = list_wiki_pages(kb_id, page_type)
        for page in pages:
            name_lower = page.name.lower()
            if name_lower == query_lower:
                score = 1.0
            elif name_lower in query_lower or query_lower in name_lower:
                score = 0.8
            else:
                continue

            results.append(SearchResult(
                page_type=page_type,
                name=page.name,
                score=score,
                snippet=page.description,
                path=f"{page_type}/{page.name}",
            ))

    return results


async def vector_search(kb_id: str, query: str, top_k: int = 10) -> list[SearchResult]:
    """
    向量语义检索
    """
    try:
        query_vector = await embed_single(query)
    except Exception as e:
        logger.error(f"查询向量化失败：{e}")
        return []

    try:
        client = get_milvus_client()
        col_name = collection_name(kb_id)

        if not client.has_collection(col_name):
            return []

        raw_results = client.search(
            collection_name=col_name,
            data=[query_vector],
            limit=top_k,
            output_fields=["doc_id", "page_type", "title", "content"],
            search_params={"metric_type": "COSINE", "params": {"nprobe": 10}},
        )
    except Exception as e:
        logger.error(f"Milvus 检索失败：{e}")
        return []

    results = []
    seen = set()  # 去重（同一页面多个 chunk）
    for hit in raw_results[0]:
        entity = hit.entity
        doc_id = entity.get("doc_id", "")
        page_type = entity.get("page_type", "")
        key = f"{page_type}:{doc_id}"

        if key in seen:
            continue
        seen.add(key)

        # COSINE distance → similarity
        score = 1.0 - hit.distance

        results.append(SearchResult(
            page_type=page_type,
            name=doc_id,
            score=score,
            snippet=entity.get("content", "")[:200],
            path=f"{page_type}/{doc_id}",
        ))

    return results


def fts_search_results(kb_id: str, query: str, top_k: int = 10) -> list[SearchResult]:
    """
    FTS5 全文检索
    """
    raw = fts_search(kb_id, query, limit=top_k)
    results = []
    for item in raw:
        results.append(SearchResult(
            page_type=item["page_type"],
            name=item["doc_id"],
            score=0.0,  # FTS rank 是负数，不直接使用
            snippet=_strip_html(item.get("snippet", "")),
            path=f"{item['page_type']}/{item['doc_id']}",
        ))
    return results


def _strip_html(text: str) -> str:
    """移除 FTS5 snippet 中的 HTML 标签"""
    import re
    return re.sub(r"<[^>]+>", "", text)


# ─────────────────────────────────────────────
# RRF 融合排序
# ─────────────────────────────────────────────

def rrf_merge(result_lists: list[list[SearchResult]], top_n: int = 5, k: int = RRF_K) -> list[SearchResult]:
    """
    Reciprocal Rank Fusion：
    score = Σ 1 / (k + rank_i)
    """
    rrf_scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}

    for result_list in result_lists:
        for rank, result in enumerate(result_list, start=1):
            key = f"{result.page_type}:{result.name}"
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            # 保留最高分数的结果对象（用于 snippet）
            if key not in result_map or result.score > result_map[key].score:
                result_map[key] = result

    # 按 RRF 分数排序
    top_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)[:top_n]

    merged = []
    for key in top_keys:
        result = result_map[key]
        result.score = round(rrf_scores[key], 4)
        merged.append(result)

    return merged


# ─────────────────────────────────────────────
# LLM 答案生成
# ─────────────────────────────────────────────

ANSWER_SYSTEM_PROMPT = """你是专业的知识库助手。基于检索到的知识片段，回答用户问题。

要求：
1. 直接回答，不要说"根据检索结果"等套话
2. 引用概念或实体时用 [[WikiLink]] 标注（如 [[Claude]]、[[agent]]）
3. 知识库中没有足够信息时，诚实说明
4. 简洁有条理，中文回答"""

ANSWER_USER_TEMPLATE = """用户问题：{query}

检索内容：
---
{context}
---

请回答用户的问题。"""


def _build_answer_context(kb_id: str, results: list[SearchResult]) -> str:
    """加载检索结果的完整页面内容作为 Context"""
    parts = []
    for result in results:
        content = load_wiki_page(kb_id, result.page_type, result.name)
        if content:
            # 截取前 800 字
            excerpt = content[:800]
            label = f"[{result.page_type.upper()}: {result.name}]"
            parts.append(f"{label}\n{excerpt}")
    return "\n\n---\n\n".join(parts) if parts else "（未找到相关内容）"


async def generate_answer(kb_id: str, query: str, results: list[SearchResult]) -> str:
    """调用 LLM 生成基于检索结果的答案"""
    if not results:
        return "抱歉，知识库中没有找到与您问题相关的内容。"

    context = _build_answer_context(kb_id, results)

    try:
        answer = await chat_completion(
            messages=[
                {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": ANSWER_USER_TEMPLATE.format(query=query, context=context),
                },
            ],
            temperature=0.3,
        )
        return answer
    except Exception as e:
        logger.error(f"答案生成失败：{e}")
        return "答案生成失败，请稍后重试。"


# ─────────────────────────────────────────────
# 主检索函数
# ─────────────────────────────────────────────

async def search(
    kb_id: str,
    query: str,
    top_k: int = 5,
    generate_answer_flag: bool = True,
) -> SearchResponse:
    """
    完整检索流程：三路检索 → RRF 融合 → LLM 答案
    """
    start = time.time()

    # 并发执行三路检索
    import asyncio

    direct_results = direct_lookup(kb_id, query)
    vector_task = asyncio.create_task(vector_search(kb_id, query, top_k=top_k * 2))
    fts_results = fts_search_results(kb_id, query, top_k=top_k * 2)
    vector_results = await vector_task

    # RRF 融合
    merged = rrf_merge(
        [direct_results, vector_results, fts_results],
        top_n=top_k,
    )

    # 填充缺失的 snippet
    for result in merged:
        if not result.snippet:
            content = load_wiki_page(kb_id, result.page_type, result.name)
            if content:
                # 提取描述行
                import re
                desc_match = re.search(r"^> (.+)", content, re.MULTILINE)
                result.snippet = desc_match.group(1) if desc_match else content[100:300]

    # 提取相关实体/概念
    related_entities = [r.name for r in merged if r.page_type == "entity"]
    related_concepts = [r.name for r in merged if r.page_type == "concept"]

    # LLM 生成答案
    answer = ""
    if generate_answer_flag:
        answer = await generate_answer(kb_id, query, merged)

    elapsed_ms = (time.time() - start) * 1000

    return SearchResponse(
        query=query,
        answer=answer,
        sources=merged,
        related_entities=related_entities,
        related_concepts=related_concepts,
        search_time_ms=round(elapsed_ms, 1),
    )
