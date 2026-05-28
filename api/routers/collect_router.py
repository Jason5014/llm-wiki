"""
数据采集 API — /api/collect
"""
import io
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from src.models import BatchSubmitRequest, RawDocument, SubmitDocRequest
from src.storage import (
    generate_doc_id,
    list_raw_doc_ids,
    load_kb_config,
    load_raw_document,
    raw_dir,
    save_raw_document,
)

router = APIRouter()


def _check_kb(kb_id: str):
    if not load_kb_config(kb_id):
        raise HTTPException(status_code=404, detail=f"知识库 '{kb_id}' 不存在")


@router.post("/{kb_id}/raw", summary="提交单篇原始内容", status_code=201)
async def submit_raw(kb_id: str, req: SubmitDocRequest):
    _check_kb(kb_id)
    doc = RawDocument(
        title=req.title,
        url=req.url,
        content=req.content,
        metadata=req.metadata,
        crawled_at=datetime.now(),
    )
    doc_id = await save_raw_document(kb_id, doc)
    return {"doc_id": doc_id, "saved": True}


@router.post("/{kb_id}/batch", summary="批量提交原始内容", status_code=201)
async def batch_submit(kb_id: str, req: BatchSubmitRequest):
    _check_kb(kb_id)
    saved = []
    for item in req.documents:
        doc = RawDocument(
            title=item.title,
            url=item.url,
            content=item.content,
            metadata=item.metadata,
            crawled_at=datetime.now(),
        )
        doc_id = await save_raw_document(kb_id, doc)
        saved.append(doc_id)
    return {"saved": len(saved), "doc_ids": saved}


@router.post("/{kb_id}/upload", summary="上传本地文件", status_code=201)
async def upload_file(kb_id: str, file: UploadFile = File(...)):
    _check_kb(kb_id)

    filename = file.filename or "untitled"
    content_bytes = await file.read()

    # 提取内容
    content = _extract_file_content(filename, content_bytes)
    title = _filename_to_title(filename)

    doc = RawDocument(
        title=title,
        url=f"file://{filename}",
        content=content,
        metadata={"source": "upload", "filename": filename},
        crawled_at=datetime.now(),
    )
    doc_id = await save_raw_document(kb_id, doc)
    return {"doc_id": doc_id, "saved": True, "title": title}


def _extract_file_content(filename: str, data: bytes) -> str:
    """根据文件类型提取文本内容"""
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext in ("md", "txt"):
        return data.decode("utf-8", errors="ignore")

    elif ext == "html":
        try:
            import trafilatura
            text = trafilatura.extract(data.decode("utf-8", errors="ignore"))
            return text or data.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode("utf-8", errors="ignore")

    elif ext == "pdf":
        try:
            import pdfminer.high_level
            return pdfminer.high_level.extract_text(io.BytesIO(data))
        except Exception:
            return f"[PDF 文件，内容提取失败：{filename}]"

    return data.decode("utf-8", errors="ignore")


def _filename_to_title(filename: str) -> str:
    """从文件名提取标题"""
    name = filename.rsplit(".", 1)[0] if "." in filename else filename
    return name.replace("-", " ").replace("_", " ").strip()


@router.get("/{kb_id}/raw", summary="查看原始文档列表")
def list_raw_docs(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    _check_kb(kb_id)
    all_ids = list_raw_doc_ids(kb_id)
    total = len(all_ids)
    start = (page - 1) * page_size
    end = start + page_size
    page_ids = all_ids[start:end]

    items = []
    for doc_id in page_ids:
        items.append({
            "doc_id": doc_id,
            "has_source": (
                (load_kb_config(kb_id) is not None)
                and bool(load_raw_document(kb_id, doc_id))
            ),
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.delete("/{kb_id}/raw/{doc_id}", summary="删除原始文档", status_code=204)
def delete_raw_doc(kb_id: str, doc_id: str):
    _check_kb(kb_id)
    path = raw_dir(kb_id) / f"{doc_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"文档 '{doc_id}' 不存在")
    path.unlink()
