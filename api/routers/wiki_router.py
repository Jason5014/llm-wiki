"""
Wiki 内容 API — /api/wiki
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from src.models import WikiPageListResponse
from src.storage import (
    index_path,
    list_wiki_pages,
    load_kb_config,
    load_wiki_page,
    load_graph,
)

router = APIRouter()


def _check_kb(kb_id: str):
    if not load_kb_config(kb_id):
        raise HTTPException(status_code=404, detail=f"知识库 '{kb_id}' 不存在")


@router.get("/{kb_id}/page/{page_type}/{name}", summary="获取 Wiki 页面内容", response_class=PlainTextResponse)
def get_wiki_page(kb_id: str, page_type: str, name: str):
    _check_kb(kb_id)
    if page_type not in ("source", "entity", "concept"):
        raise HTTPException(status_code=400, detail=f"无效的页面类型：{page_type}")

    content = load_wiki_page(kb_id, page_type, name)
    if not content:
        raise HTTPException(status_code=404, detail=f"页面 '{page_type}/{name}' 不存在")
    return content


@router.get("/{kb_id}/index", summary="获取 index.md", response_class=PlainTextResponse)
def get_index(kb_id: str):
    _check_kb(kb_id)
    idx_path = index_path(kb_id)
    if not idx_path.exists():
        raise HTTPException(status_code=404, detail="index.md 还未生成，请先运行流水线")
    return idx_path.read_text(encoding="utf-8")


@router.get("/{kb_id}/pages", summary="列出所有 Wiki 页面")
def list_pages(
    kb_id: str,
    type: str = Query("entity", description="entity | concept | source"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> WikiPageListResponse:
    _check_kb(kb_id)
    if type not in ("source", "entity", "concept"):
        raise HTTPException(status_code=400, detail=f"无效的页面类型：{type}")

    all_pages = list_wiki_pages(kb_id, type)
    total = len(all_pages)
    start = (page - 1) * page_size
    end = start + page_size
    return WikiPageListResponse(items=all_pages[start:end], total=total)


@router.get("/{kb_id}/graph", summary="获取知识图谱数据")
def get_graph(kb_id: str):
    _check_kb(kb_id)
    graph = load_graph(kb_id)
    if not graph:
        raise HTTPException(status_code=404, detail="图谱数据还未生成，请先运行流水线")
    return graph
