"""
数据采集 API — /api/collect
"""
import io
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from src.inspector.tier0 import tier0_inspect
from src.models import BatchSubmitRequest, RawDocument, SubmitDocRequest
from src.processor.image_downloader import download_images
from src.storage import (
    generate_doc_id,
    list_episodes,
    list_raw_doc_ids,
    load_all_qualities,
    load_kb_config,
    load_raw_document,
    raw_dir,
    save_episode,
    save_quality,
    save_raw_document,
)

router = APIRouter()


def _check_kb(kb_id: str):
    if not load_kb_config(kb_id):
        raise HTTPException(status_code=404, detail=f"知识库 '{kb_id}' 不存在")


@router.post("/{kb_id}/raw", summary="提交单篇原始内容", status_code=201)
async def submit_raw(kb_id: str, req: SubmitDocRequest):
    _check_kb(kb_id)

    # 下载图片到本地
    content, img_report = await download_images(kb_id, req.content)
    img_ok = sum(1 for r in img_report if r["status"] == "ok")

    # Tier0 机械质检
    quality = tier0_inspect({
        "title": req.title,
        "url": req.url,
        "content": content,
        "metadata": req.metadata,
    })

    metadata = {**req.metadata, "quality": quality}
    if img_report:
        metadata["img_downloaded"] = img_ok
        metadata["img_failed"] = sum(1 for r in img_report if r["status"] == "error")

    doc = RawDocument(
        title=req.title,
        url=req.url,
        content=content,
        metadata=metadata,
        crawled_at=datetime.now(),
    )
    doc_id = await save_raw_document(kb_id, doc)
    save_quality(kb_id, doc_id, quality)
    return {"doc_id": doc_id, "saved": True, "quality": quality, "images_downloaded": img_ok}


@router.post("/{kb_id}/batch", summary="批量提交原始内容", status_code=201)
async def batch_submit(kb_id: str, req: BatchSubmitRequest):
    _check_kb(kb_id)
    saved = []
    qualities = []
    for item in req.documents:
        # 下载图片到本地
        content, img_report = await download_images(kb_id, item.content)
        img_ok = sum(1 for r in img_report if r["status"] == "ok")

        # Tier0 机械质检
        quality = tier0_inspect({
            "title": item.title,
            "url": item.url,
            "content": content,
            "metadata": item.metadata,
        })

        metadata = {**item.metadata, "quality": quality}
        if img_report:
            metadata["img_downloaded"] = img_ok
            metadata["img_failed"] = sum(1 for r in img_report if r["status"] == "error")

        doc = RawDocument(
            title=item.title,
            url=item.url,
            content=content,
            metadata=metadata,
            crawled_at=datetime.now(),
        )
        doc_id = await save_raw_document(kb_id, doc)
        save_quality(kb_id, doc_id, quality)
        saved.append(doc_id)
        qualities.append({"doc_id": doc_id, "quality": quality})
    return {"saved": len(saved), "doc_ids": saved, "qualities": qualities}


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

    # 批量加载质检结果
    qualities = load_all_qualities(kb_id)

    items = []
    for doc_id in page_ids:
        content = load_raw_document(kb_id, doc_id)
        title, url, crawled_at = doc_id, "", ""
        if content:
            for line in content.split("\n"):
                if line.startswith("# ") and title == doc_id:
                    title = line[2:].strip()
                if line.startswith("> 抓取时间："):
                    crawled_at = line.replace("> 抓取时间：", "").strip()
            import re as _re
            _url_match = _re.search(r"^https?://\S+", content, _re.MULTILINE)
            if _url_match:
                url = _url_match.group(0)

        quality = qualities.get(doc_id)
        items.append({
            "doc_id": doc_id,
            "title": title,
            "url": url,
            "crawled_at": crawled_at,
            "char_count": len(content) if content else 0,
            "has_source": (load_kb_config(kb_id) is not None) and bool(content),
            "quality": quality,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{kb_id}/raw/{doc_id}", summary="查看原始文档内容")
def get_raw_doc(kb_id: str, doc_id: str):
    _check_kb(kb_id)
    content = load_raw_document(kb_id, doc_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f"文档 '{doc_id}' 不存在")
    return {"doc_id": doc_id, "content": content}


@router.delete("/{kb_id}/raw/{doc_id}", summary="删除原始文档", status_code=204)
def delete_raw_doc(kb_id: str, doc_id: str):
    _check_kb(kb_id)
    path = raw_dir(kb_id) / f"{doc_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"文档 '{doc_id}' 不存在")
    path.unlink()


# ─────────────────────────────────────────────
# Episode 接口（质检反馈环）
# ─────────────────────────────────────────────

@router.post("/{kb_id}/episode", summary="记录质检 episode", status_code=201)
async def record_episode(kb_id: str, episode: dict):
    """采集端 re-extract 后上报 episode，用于后续学习"""
    _check_kb(kb_id)
    ep_id = await save_episode(kb_id, episode)
    return {"episode_id": ep_id, "recorded": True}


@router.get("/{kb_id}/episodes", summary="查看质检 episodes")
def get_episodes(kb_id: str):
    """返回该知识库的所有质检 episode"""
    _check_kb(kb_id)
    eps = list_episodes(kb_id)
    return {"episodes": eps, "total": len(eps)}
