"""
搜索问答 API — /api/search
"""
from fastapi import APIRouter, HTTPException

from src.models import SearchRequest, SearchResponse
from src.retriever.retriever import search
from src.storage import load_kb_config

router = APIRouter()


def _check_kb(kb_id: str):
    if not load_kb_config(kb_id):
        raise HTTPException(status_code=404, detail=f"知识库 '{kb_id}' 不存在")


@router.post("/{kb_id}/query", summary="搜索并生成 AI 回答")
async def query(kb_id: str, req: SearchRequest) -> SearchResponse:
    _check_kb(kb_id)
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")

    return await search(
        kb_id=kb_id,
        query=req.query,
        top_k=req.top_k,
        generate_answer_flag=req.generate_answer,
    )


@router.post("/{kb_id}/retrieve", summary="纯检索（不生成答案）")
async def retrieve(kb_id: str, req: SearchRequest) -> SearchResponse:
    _check_kb(kb_id)
    req.generate_answer = False
    return await search(
        kb_id=kb_id,
        query=req.query,
        top_k=req.top_k,
        generate_answer_flag=False,
    )
