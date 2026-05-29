"""
采集任务队列 — SQLite 持久化

该模块管理全局爬取任务队列。任务可由外部（API/脚本）提交，
Electron Collector 周期性拉取并处理。

数据库位置：{kb_base_dir}/crawl_tasks.db
"""
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from src.config import settings

# ─────────────────────────────────────────────────────
# 数据库路径
# ─────────────────────────────────────────────────────

def _db_path() -> Path:
    path = settings.kb_base_dir / "crawl_tasks.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ─────────────────────────────────────────────────────
# 初始化 / 建表
# ─────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS crawl_tasks (
    id          TEXT    PRIMARY KEY,
    kb_id       TEXT    NOT NULL,
    url         TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'pending',
    priority    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT,
    error       TEXT,
    doc_id      TEXT
);
CREATE INDEX IF NOT EXISTS idx_status_kb ON crawl_tasks(status, kb_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_url_kb ON crawl_tasks(url, kb_id);
"""


def init_db() -> None:
    """建表（幂等）。应在应用启动时调用。"""
    with sqlite3.connect(_db_path()) as conn:
        conn.executescript(_DDL)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────
# 任务状态类型
# ─────────────────────────────────────────────────────

TaskStatus = Literal["pending", "running", "done", "failed"]


# ─────────────────────────────────────────────────────
# CRUD 操作
# ─────────────────────────────────────────────────────

def add_task(kb_id: str, url: str, priority: int = 0) -> Optional[str]:
    """
    添加任务。若 (url, kb_id) 已存在且状态非 failed，则忽略（去重）。
    返回 task_id，若重复返回 None。
    """
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    with _conn() as conn:
        try:
            conn.execute(
                """
                INSERT INTO crawl_tasks (id, kb_id, url, status, priority, created_at)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (task_id, kb_id, url, priority, now),
            )
            return task_id
        except sqlite3.IntegrityError:
            # (url, kb_id) 已存在 — 只允许 failed 任务重试
            existing = conn.execute(
                "SELECT id, status FROM crawl_tasks WHERE url=? AND kb_id=?",
                (url, kb_id),
            ).fetchone()
            if existing and existing["status"] == "failed":
                # 重置为 pending
                conn.execute(
                    "UPDATE crawl_tasks SET status='pending', error=NULL, updated_at=? WHERE id=?",
                    (now, existing["id"]),
                )
                return existing["id"]
            return None  # 已存在且非 failed，忽略


def add_tasks_bulk(kb_id: str, urls: list[str], priority: int = 0) -> dict:
    """批量添加任务，返回 {added: n, skipped: n}"""
    added, skipped = 0, 0
    for url in urls:
        result = add_task(kb_id, url, priority)
        if result:
            added += 1
        else:
            skipped += 1
    return {"added": added, "skipped": skipped}


def get_tasks(
    kb_id: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """查询任务列表，支持按 kb_id 和 status 过滤"""
    where, params = [], []
    if kb_id:
        where.append("kb_id = ?")
        params.append(kb_id)
    if status:
        where.append("status = ?")
        params.append(status)

    sql = "SELECT * FROM crawl_tasks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY priority DESC, created_at ASC LIMIT ? OFFSET ?"
    params += [limit, offset]

    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def count_tasks(kb_id: Optional[str] = None, status: Optional[TaskStatus] = None) -> int:
    where, params = [], []
    if kb_id:
        where.append("kb_id = ?")
        params.append(kb_id)
    if status:
        where.append("status = ?")
        params.append(status)
    sql = "SELECT COUNT(*) FROM crawl_tasks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with _conn() as conn:
        return conn.execute(sql, params).fetchone()[0]


def update_task(
    task_id: str,
    status: TaskStatus,
    error: Optional[str] = None,
    doc_id: Optional[str] = None,
) -> bool:
    """更新任务状态。返回是否更新成功（任务是否存在）。"""
    now = datetime.now().isoformat()
    with _conn() as conn:
        cur = conn.execute(
            """
            UPDATE crawl_tasks
            SET status=?, error=?, doc_id=?, updated_at=?
            WHERE id=?
            """,
            (status, error, doc_id, now, task_id),
        )
        return cur.rowcount > 0


def delete_task(task_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM crawl_tasks WHERE id=?", (task_id,))
        return cur.rowcount > 0
