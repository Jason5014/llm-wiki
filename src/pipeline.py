"""
流水线编排器 — 将四个 Stage 串联，支持任务状态跟踪和 SSE 推送
"""
import asyncio
import logging
import uuid
from datetime import datetime

from src.indexer.indexer import build_fts_index, build_vector_index
from src.models import ConceptData, EntityData, PipelineStage, RunPipelineRequest, TaskState, TaskStatus
from src.processor.entity_concept_extractor import extract_entities_concepts
from src.processor.index_builder import build_graph_json, build_index_md
from src.processor.page_builder import build_all_pages
from src.processor.source_processor import process_all_sources
from src.storage import load_extraction

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 任务管理（内存存储，进程重启后丢失）
# ─────────────────────────────────────────────

_tasks: dict[str, TaskState] = {}
_task_events: dict[str, asyncio.Queue] = {}  # task_id → SSE event queue


def create_task(kb_id: str, stage: str) -> TaskState:
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    task = TaskState(task_id=task_id, kb_id=kb_id, stage=stage)
    _tasks[task_id] = task
    _task_events[task_id] = asyncio.Queue()
    return task


def get_task(task_id: str) -> TaskState | None:
    return _tasks.get(task_id)


async def _push_event(task_id: str, data: dict) -> None:
    """向 SSE 队列推送事件"""
    q = _task_events.get(task_id)
    if q:
        await q.put(data)


async def get_task_events(task_id: str):
    """异步生成器，用于 SSE 推流"""
    q = _task_events.get(task_id)
    if not q:
        return

    while True:
        try:
            event = await asyncio.wait_for(q.get(), timeout=30.0)
            yield event
            if event.get("status") in ("done", "error"):
                break
        except asyncio.TimeoutError:
            # 发送心跳
            yield {"heartbeat": True}


# ─────────────────────────────────────────────
# 流水线执行
# ─────────────────────────────────────────────

async def run_pipeline(kb_id: str, req: RunPipelineRequest) -> TaskState:
    """
    启动流水线任务（后台异步执行）
    Returns: 任务状态对象
    """
    task = create_task(kb_id, req.stage)
    task.status = TaskStatus.running
    task.message = "流水线已启动"

    # 在后台运行，不阻塞 API 响应
    asyncio.create_task(_execute_pipeline(task, req))
    return task


async def _execute_pipeline(task: TaskState, req: RunPipelineRequest) -> None:
    """流水线主执行逻辑"""
    kb_id = task.kb_id

    async def progress(completed: int, total: int, message: str = "") -> None:
        task.update_progress(completed, total, message)
        await _push_event(task.task_id, {
            "completed": completed,
            "total": total,
            "progress": task.progress,
            "message": message,
        })

    async def on_error(message: str) -> None:
        """上报非致命错误到 SSE（前端显示为红色日志，但不中断流水线）"""
        task.errors.append(message)
        await _push_event(task.task_id, {
            "level": "warning",
            "message": f"⚠️ {message}",
        })

    try:
        stage = req.stage

        # Stage 2: Source 摘要
        if stage in (PipelineStage.all, PipelineStage.source):
            task.message = "阶段 2：生成 Source 摘要..."
            await _push_event(task.task_id, {"stage": "source", "message": task.message})
            source_pages = await process_all_sources(
                kb_id,
                force=req.force,
                doc_ids=req.doc_ids or None,
                progress_callback=progress,
                error_callback=on_error,
            )

            if not source_pages and stage == PipelineStage.source:
                await on_error("Source 摘要生成失败，无法继续后续阶段")
                task.status = TaskStatus.error
                task.message = "❌ Source 阶段失败"
                await _push_event(task.task_id, {"status": "error", "message": task.message})
                return

        # Stage 3a: 实体/概念抽取
        entities: list[EntityData] = []
        concepts: list[ConceptData] = []

        if stage in (PipelineStage.all, PipelineStage.extract):
            task.message = "阶段 3a：抽取实体和概念..."
            await _push_event(task.task_id, {"stage": "extract", "message": task.message})
            entities, concepts = await extract_entities_concepts(
                kb_id,
                progress_callback=progress,
                error_callback=on_error,
            )

            if not entities and not concepts:
                await on_error("实体/概念抽取结果为空，请检查 LLM API 配置或 source 页面内容")
            else:
                await _push_event(task.task_id, {
                    "message": f"✅ 抽取完成：{len(entities)} 个实体，{len(concepts)} 个概念",
                })

        # Stage 3b: 页面生成
        if stage in (PipelineStage.all, PipelineStage.pages):
            # 如果是独立运行 pages stage，从已保存的抽取结果加载
            if not entities and not concepts and stage == PipelineStage.pages:
                saved = load_extraction(kb_id)
                if saved:
                    entities = [EntityData(**e) for e in saved.get("entities", [])]
                    concepts = [ConceptData(**c) for c in saved.get("concepts", [])]
                    await _push_event(task.task_id, {
                        "message": f"📂 从已保存的抽取结果加载：{len(entities)} 实体，{len(concepts)} 概念",
                    })

            if entities or concepts:
                task.message = "阶段 3b：生成 Wiki 页面..."
                await _push_event(task.task_id, {"stage": "pages", "message": task.message})
                await build_all_pages(
                    kb_id,
                    entities,
                    concepts,
                    force=req.force,
                    progress_callback=progress,
                )
            else:
                await on_error("无可用的实体/概念数据，请先运行「仅实体/概念抽取」")

        # Stage 4: 索引构建
        if stage in (PipelineStage.all, PipelineStage.index):
            task.message = "阶段 4：构建索引..."
            await _push_event(task.task_id, {"stage": "index", "message": task.message})

            # 4.1 生成 index.md
            build_index_md(kb_id)

            # 4.2 构建向量索引
            await build_vector_index(kb_id, progress_callback=progress)

            # 4.3 构建 FTS5 索引
            build_fts_index(kb_id)

            # 4.4 构建图谱
            await build_graph_json(kb_id)

        # 完成
        task.status = TaskStatus.done
        task.message = "✅ 流水线全部完成"
        await _push_event(task.task_id, {
            "status": "done",
            "message": task.message,
            "completed": task.completed,
            "total": task.total,
        })
        logger.info(f"流水线完成：{kb_id}")

    except Exception as e:
        task.status = TaskStatus.error
        task.message = f"❌ 错误：{e}"
        task.errors.append(str(e))
        await _push_event(task.task_id, {
            "status": "error",
            "message": task.message,
        })
        logger.exception(f"流水线异常：{kb_id}")
