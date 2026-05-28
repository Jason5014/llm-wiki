"""
索引构建器 — Milvus 向量索引 + SQLite FTS5 全文索引
"""
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    connections,
    utility,
)

from src.config import settings
from src.llm import embed_texts_batched
from src.storage import (
    clean_markdown_for_embedding,
    fts_db_path,
    list_wiki_pages,
    load_wiki_page,
)

logger = logging.getLogger(__name__)

MILVUS_URI = f"http://{settings.milvus_host}:{settings.milvus_port}"


# ─────────────────────────────────────────────
# Milvus 连接
# ─────────────────────────────────────────────

def get_milvus_client() -> MilvusClient:
    return MilvusClient(uri=MILVUS_URI)


def collection_name(kb_id: str) -> str:
    """将 kb_id 转换为合法的 Milvus collection 名称"""
    # Milvus collection 名只允许字母、数字、下划线
    return f"kb_{kb_id.replace('-', '_')}"


# ─────────────────────────────────────────────
# Milvus Collection 管理
# ─────────────────────────────────────────────

def ensure_collection(kb_id: str) -> None:
    """确保 Milvus Collection 存在，不存在则创建"""
    client = get_milvus_client()
    col_name = collection_name(kb_id)

    if client.has_collection(col_name):
        return

    client.create_collection(
        collection_name=col_name,
        schema=_build_schema(client, col_name),
        index_params=_build_index_params(client, col_name),
    )
    logger.info(f"Milvus Collection 已创建：{col_name}")


def _build_schema(client: MilvusClient, col_name: str):
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=settings.embedding_dim)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=256)
    schema.add_field("page_type", DataType.VARCHAR, max_length=32)
    schema.add_field("title", DataType.VARCHAR, max_length=512)
    schema.add_field("content", DataType.VARCHAR, max_length=4096)
    schema.add_field("chunk_idx", DataType.INT64)
    return schema


def _build_index_params(client: MilvusClient, col_name: str):
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="IVF_FLAT",
        metric_type="COSINE",
        params={"nlist": 128},
    )
    return index_params


def drop_collection(kb_id: str) -> None:
    """删除 Milvus Collection"""
    client = get_milvus_client()
    col_name = collection_name(kb_id)
    if client.has_collection(col_name):
        client.drop_collection(col_name)
        logger.info(f"Milvus Collection 已删除：{col_name}")


# ─────────────────────────────────────────────
# 向量索引构建
# ─────────────────────────────────────────────

def _chunk_text(text: str, max_chars: int = 1000) -> list[str]:
    """将长文本按段落分块"""
    paragraphs = re.split(r"\n{2,}", text)
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # 如果单个段落超过 max_chars，直接截断
            if len(para) > max_chars:
                chunks.append(para[:max_chars])
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks or [text[:max_chars]]


async def index_wiki_page(
    kb_id: str,
    page_type: str,
    name: str,
    client: MilvusClient | None = None,
) -> int:
    """
    向量化并索引单个 Wiki 页面
    Returns: 写入的向量数量
    """
    content = load_wiki_page(kb_id, page_type, name)
    if not content:
        return 0

    # 提取标题
    title_match = re.search(r"^# (.+)", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else name

    # 清洗 + 分块
    clean_text = clean_markdown_for_embedding(content)
    chunks = _chunk_text(clean_text)

    # 向量化
    vectors = await embed_texts_batched(chunks)

    if not client:
        client = get_milvus_client()

    col_name = collection_name(kb_id)
    data = []
    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        data.append({
            "vector": vector,
            "doc_id": name,
            "page_type": page_type,
            "title": title,
            "content": chunk[:4096],
            "chunk_idx": i,
        })

    if data:
        client.insert(collection_name=col_name, data=data)

    return len(data)


async def build_vector_index(kb_id: str, progress_callback=None) -> None:
    """
    构建全知识库的 Milvus 向量索引
    """
    ensure_collection(kb_id)
    client = get_milvus_client()
    col_name = collection_name(kb_id)

    # 清空已有数据
    client.delete(collection_name=col_name, filter="chunk_idx >= 0")

    all_pages: list[tuple[str, str]] = []
    for pt in ("source", "entity", "concept"):
        for p in list_wiki_pages(kb_id, pt):
            all_pages.append((pt, p.name))

    total = len(all_pages)
    completed = 0
    total_vectors = 0

    for page_type, name in all_pages:
        count = await index_wiki_page(kb_id, page_type, name, client)
        total_vectors += count
        completed += 1
        if progress_callback:
            await progress_callback(
                completed, total, f"向量化：{page_type}/{name} ({count} 块)"
            )

    logger.info(f"向量索引构建完成：{total_vectors} 个向量，{total} 个页面")


# ─────────────────────────────────────────────
# SQLite FTS5 索引
# ─────────────────────────────────────────────

def init_fts_db(kb_id: str) -> sqlite3.Connection:
    """初始化 FTS5 数据库"""
    db_path = fts_db_path(kb_id)
    conn = sqlite3.connect(str(db_path))

    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
            doc_id UNINDEXED,
            page_type UNINDEXED,
            title,
            content,
            tokenize = 'unicode61'
        );

        CREATE TABLE IF NOT EXISTS wiki_meta (
            doc_id     TEXT PRIMARY KEY,
            page_type  TEXT,
            title      TEXT,
            url        TEXT,
            updated    TEXT
        );
    """)
    conn.commit()
    return conn


def build_fts_index(kb_id: str) -> None:
    """构建 SQLite FTS5 全文检索索引"""
    conn = init_fts_db(kb_id)

    try:
        # 清空旧数据
        conn.execute("DELETE FROM wiki_fts")
        conn.execute("DELETE FROM wiki_meta")

        total = 0
        for page_type in ("source", "entity", "concept"):
            for page in list_wiki_pages(kb_id, page_type):
                content = load_wiki_page(kb_id, page_type, page.name)
                if not content:
                    continue

                # 提取 title 和 clean content
                title_match = re.search(r"^# (.+)", content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else page.name
                clean_text = clean_markdown_for_embedding(content)

                conn.execute(
                    "INSERT OR REPLACE INTO wiki_fts(doc_id, page_type, title, content) VALUES (?, ?, ?, ?)",
                    (page.name, page_type, title, clean_text),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO wiki_meta(doc_id, page_type, title, updated) VALUES (?, ?, ?, ?)",
                    (page.name, page_type, title, page.updated or ""),
                )
                total += 1

        conn.commit()
        logger.info(f"FTS5 索引构建完成：{total} 个页面")
    finally:
        conn.close()


def fts_search(kb_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    FTS5 全文检索
    Returns: list of {doc_id, page_type, title, snippet, rank}
    """
    db_path = fts_db_path(kb_id)
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        # 构建 FTS5 查询：多词用 OR 连接，转义特殊字符
        terms = _escape_fts5_query(query)

        results = conn.execute(
            """
            SELECT doc_id, page_type, title,
                   snippet(wiki_fts, 3, '<b>', '</b>', '...', 20) as snippet,
                   rank
            FROM wiki_fts
            WHERE wiki_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (terms, limit),
        ).fetchall()

        return [dict(r) for r in results]
    except sqlite3.OperationalError as e:
        logger.warning(f"FTS5 查询失败：{e}，query={query!r}")
        return []
    finally:
        conn.close()


def _escape_fts5_query(query: str) -> str:
    """将用户查询转为 FTS5 MATCH 语法"""
    # 移除 FTS5 特殊字符
    cleaned = re.sub(r'["\(\)\*\:\^]', " ", query)
    words = cleaned.split()
    if not words:
        return '""'
    # 单词用 OR 连接（提高召回），短语也尝试匹配
    if len(words) == 1:
        return words[0]
    return " OR ".join(words)
