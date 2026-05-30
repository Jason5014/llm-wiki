"""
图片下载器 — 从 Markdown 中提取图片 URL，下载到本地，替换为本地路径

用法：
    new_content = await download_images(kb_id, markdown_content)
"""
import asyncio
import hashlib
import re
from pathlib import Path

import httpx

from src.storage import assets_dir

# 匹配 Markdown 图片语法 ![alt](url)
_IMG_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

# 允许的图片类型
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"}

# 单张图片最大 20MB
_MAX_SIZE = 20 * 1024 * 1024


def _guess_ext(url: str, content_type: str) -> str:
    """从 URL 或 Content-Type 推断文件扩展名"""
    path = url.split("?")[0].split("#")[0]
    for ext in _ALLOWED_EXTENSIONS:
        if path.lower().endswith(ext):
            return ext
    ct_map = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
        "image/webp": ".webp", "image/svg+xml": ".svg",
        "image/bmp": ".bmp", "image/x-icon": ".ico",
    }
    for ct, ext in ct_map.items():
        if ct in content_type.lower():
            return ext
    return ".jpg"


def _make_filename(url: str) -> str:
    """由 URL 生成唯一文件名"""
    return hashlib.md5(url.encode()).hexdigest()[:12]


async def _download_one(client: httpx.AsyncClient, url: str, asset_dir: Path) -> dict:
    """下载单张图片"""
    entry = {"url": url, "local_path": "", "status": "ok", "error": ""}
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            entry["status"] = "error"
            entry["error"] = f"HTTP {resp.status_code}"
            return entry

        data = resp.content
        if len(data) > _MAX_SIZE:
            entry["status"] = "skipped"
            entry["error"] = f"too large ({len(data)} bytes)"
            return entry

        ct = resp.headers.get("Content-Type", "")
        ext = _guess_ext(url, ct)
        filename = _make_filename(url) + ext
        local_path = asset_dir / filename

        local_path.write_bytes(data)
        rel_path = f"/api/assets/{asset_dir.parent.name}/{filename}"
        entry["local_path"] = rel_path

    except Exception as e:
        entry["status"] = "error"
        entry["error"] = str(e)

    return entry


async def download_images(kb_id: str, content: str) -> tuple[str, list[dict]]:
    """
    下载 Markdown 中的所有图片到本地。

    Returns:
        (new_content, download_report)
    """
    matches = list(_IMG_PATTERN.finditer(content))
    if not matches:
        return content, []

    unique_urls = list(set(m.group(2) for m in matches))

    # 过滤掉已经是本地路径和 data: URI 的
    to_download = [u for u in unique_urls if not u.startswith(("/", "./", "assets/", "data:"))]
    if not to_download:
        return content, []

    asset_dir = assets_dir(kb_id)
    asset_dir.mkdir(parents=True, exist_ok=True)

    # 并发下载
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "Mozilla/5.0"}) as client:
        tasks = [_download_one(client, url, asset_dir) for url in to_download]
        results = await asyncio.gather(*tasks)

    url_to_local = {r["url"]: r["local_path"] for r in results if r["local_path"]}

    # 替换 Markdown 中的图片 URL
    def _replace(match: re.Match) -> str:
        alt = match.group(1)
        url = match.group(2)
        local = url_to_local.get(url)
        if local:
            return f"![{alt}]({local})"
        return match.group(0)

    new_content = _IMG_PATTERN.sub(_replace, content)
    return new_content, results
