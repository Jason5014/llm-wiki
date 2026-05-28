"""
处理流水线 API — /api/process
"""
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.models import RunPipelineRequest
from src.pipeline import get_task, get_task_events, run_pipeline
from src.storage import load_kb_config

router = APIRouter()


def _check_kb(kb_id: str):
    if not load_kb_config(kb_id):
        raise HTTPException(status_code=404, detail=f"知识库 '{kb_id}' 不存在")


@router.post("/{kb_id}/run", summary="触发处理流水线", status_code=202)
async def trigger_pipeline(kb_id: str, req: RunPipelineRequest = RunPipelineRequest()):
    _check_kb(kb_id)
    task = await run_pipeline(kb_id, req)
    return {
        "task_id": task.task_id,
        "status": task.status,
        "message": task.message,
    }


@router.get("/{kb_id}/tasks/{task_id}", summary="查询任务状态")
def get_task_status(kb_id: str, task_id: str):
    task = get_task(task_id)
    if not task or task.kb_id != kb_id:
        raise HTTPException(status_code=404, detail=f"任务 '{task_id}' 不存在")
    return task


@router.get("/{kb_id}/tasks/{task_id}/stream", summary="SSE 实时进度推流")
async def stream_task(kb_id: str, task_id: str):
    task = get_task(task_id)
    if not task or task.kb_id != kb_id:
        raise HTTPException(status_code=404, detail=f"任务 '{task_id}' 不存在")

    async def event_generator():
        async for event in get_task_events(task_id):
            if event.get("heartbeat"):
                yield {"data": ": ping"}
            else:
                import json
                yield {"data": json.dumps(event, ensure_ascii=False)}

    return EventSourceResponse(event_generator())
