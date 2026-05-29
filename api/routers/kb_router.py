"""
知识库管理 API — /api/kb
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.models import CreateKBRequest, KBConfig, KBDetail, KBStatus
from src.storage import (
    get_kb_stats,
    init_kb_dirs,
    list_kb_ids,
    load_kb_config,
    save_kb_config,
)

router = APIRouter()


def _kb_to_detail(config: KBConfig) -> KBDetail:
    stats = get_kb_stats(config.kb_id)
    return KBDetail(
        kb_id=config.kb_id,
        name=config.name,
        description=config.description,
        domain=config.domain,
        language=config.language,
        status=config.status,
        created_at=config.created_at,
        updated_at=config.updated_at,
        stats=stats,
    )


@router.get("/", summary="获取所有知识库")
def list_kbs() -> list[KBDetail]:
    result = []
    for kb_id in list_kb_ids():
        config = load_kb_config(kb_id)
        if config:
            result.append(_kb_to_detail(config))
    return result


@router.post("/", summary="创建知识库", status_code=201)
def create_kb(req: CreateKBRequest) -> KBDetail:
    # 未指定 kb_id 时自动生成：kb-{8位uuid}
    kb_id = req.kb_id or f"kb-{uuid.uuid4().hex[:8]}"

    # 检查是否已存在
    if load_kb_config(kb_id):
        raise HTTPException(status_code=409, detail=f"知识库 '{kb_id}' 已存在")

    config = KBConfig(
        kb_id=kb_id,
        name=req.name,
        description=req.description,
        domain=req.domain,
        language=req.language,
        crawl_targets=req.crawl_targets,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        status=KBStatus.ready,
    )
    init_kb_dirs(req.kb_id)
    save_kb_config(config)
    return _kb_to_detail(config)


@router.get("/{kb_id}", summary="获取单个知识库")
def get_kb(kb_id: str) -> KBDetail:
    config = load_kb_config(kb_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"知识库 '{kb_id}' 不存在")
    return _kb_to_detail(config)


@router.delete("/{kb_id}", summary="删除知识库", status_code=204)
def delete_kb(kb_id: str):
    config = load_kb_config(kb_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"知识库 '{kb_id}' 不存在")

    import shutil
    from src.storage import kb_dir
    from src.indexer.indexer import drop_collection

    # 删除文件目录
    shutil.rmtree(kb_dir(kb_id), ignore_errors=True)

    # 删除 Milvus collection（忽略错误）
    try:
        drop_collection(kb_id)
    except Exception:
        pass
