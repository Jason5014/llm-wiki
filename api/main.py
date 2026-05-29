"""
FastAPI 应用入口
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import collect_router, crawl_router, kb_router, process_router, search_router, wiki_router
from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="LLM Wiki API",
    description="AI 驱动的 Wiki 知识图谱系统",
    version="0.1.0",
)

# CORS（开发模式允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(kb_router.router, prefix="/api/kb", tags=["知识库管理"])
app.include_router(collect_router.router, prefix="/api/collect", tags=["数据采集"])
app.include_router(crawl_router.router, prefix="/api/crawl", tags=["采集任务队列"])
app.include_router(process_router.router, prefix="/api/process", tags=["处理流水线"])
app.include_router(wiki_router.router, prefix="/api/wiki", tags=["Wiki 内容"])
app.include_router(search_router.router, prefix="/api/search", tags=["搜索问答"])


@app.get("/health", tags=["系统"])
def health_check():
    return {"status": "ok", "service": "llm-wiki"}


@app.on_event("startup")
async def startup():
    """应用启动时初始化"""
    import logging
    from src import crawl_queue
    logger = logging.getLogger(__name__)
    logger.info(f"LLM Wiki 启动，知识库目录：{settings.kb_base_dir}")
    settings.kb_base_dir.mkdir(parents=True, exist_ok=True)
    crawl_queue.init_db()   # 建立 crawl_tasks 表（幂等）
