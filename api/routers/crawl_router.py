"""
采集任务队列 API — /api/crawl

Electron Collector 通过此接口提交和拉取任务，实现后台自动化采集。

典型用法：
  - Collector 启动后轮询 GET /api/crawl/tasks?status=pending&limit=10
  - 处理完成后 PATCH /api/crawl/tasks/{task_id} 更新状态
  - 外部脚本/CI 通过 POST /api/crawl/tasks 批量投递 URL
"""
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, HttpUrl

from src import crawl_queue
from src.storage import load_kb_config

router = APIRouter()


# ─────────────────────────────────────────────
# 请求 / 响应模型
# ─────────────────────────────────────────────

class AddTaskRequest(BaseModel):
    kb_id: str
    urls: List[str]          # 支持批量提交
    priority: int = 0        # 越大越优先


class UpdateTaskRequest(BaseModel):
    status: Literal["pending", "running", "done", "failed"]
    error: Optional[str] = None
    doc_id: Optional[str] = None  # 成功保存后的文档 ID


# ─────────────────────────────────────────────
# 路由
# ─────────────────────────────────────────────

@router.post("/tasks", summary="提交采集任务（支持批量）", status_code=201)
def add_tasks(req: AddTaskRequest):
    if not load_kb_config(req.kb_id):
        raise HTTPException(status_code=404, detail=f"知识库 '{req.kb_id}' 不存在")
    if not req.urls:
        raise HTTPException(status_code=422, detail="urls 不能为空")

    result = crawl_queue.add_tasks_bulk(req.kb_id, req.urls, req.priority)
    return result


@router.get("/tasks", summary="查询任务列表")
def list_tasks(
    kb_id: Optional[str] = Query(None, description="按知识库过滤"),
    status: Optional[str] = Query(None, description="pending | running | done | failed"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    tasks = crawl_queue.get_tasks(kb_id=kb_id, status=status, limit=limit, offset=offset)
    total = crawl_queue.count_tasks(kb_id=kb_id, status=status)
    return {"tasks": tasks, "total": total}


@router.patch("/tasks/{task_id}", summary="更新任务状态")
def update_task(task_id: str, req: UpdateTaskRequest):
    ok = crawl_queue.update_task(
        task_id=task_id,
        status=req.status,
        error=req.error,
        doc_id=req.doc_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"任务 '{task_id}' 不存在")
    return {"updated": True}


@router.delete("/tasks/{task_id}", summary="删除任务", status_code=204)
def delete_task(task_id: str):
    ok = crawl_queue.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"任务 '{task_id}' 不存在")


@router.get("/tasks/stats", summary="各状态任务统计")
def task_stats(kb_id: Optional[str] = Query(None)):
    statuses = ["pending", "running", "done", "failed"]
    return {
        s: crawl_queue.count_tasks(kb_id=kb_id, status=s)
        for s in statuses
    }
