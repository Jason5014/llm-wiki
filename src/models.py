"""
数据模型定义 — 系统中所有核心数据结构
"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# 枚举类型
# ─────────────────────────────────────────────

class KBStatus(str, Enum):
    creating = "creating"
    ready = "ready"
    processing = "processing"
    error = "error"


class ContentType(str, Enum):
    tutorial = "tutorial"
    guide = "guide"
    news = "news"
    opinion = "opinion"
    comparison = "comparison"
    case_study = "case-study"
    other = "other"


class EntityCategory(str, Enum):
    product = "product"
    company = "company"
    tool = "tool"
    person = "person"
    project = "project"
    other = "other"


class ConceptCategory(str, Enum):
    technology = "technology"
    method = "method"
    pattern = "pattern"
    theory = "theory"
    term = "term"
    other = "other"


class PageType(str, Enum):
    source = "source"
    entity = "entity"
    concept = "concept"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    error = "error"


class PipelineStage(str, Enum):
    all = "all"
    source = "source"
    extract = "extract"
    pages = "pages"
    index = "index"


# ─────────────────────────────────────────────
# 知识库模型
# ─────────────────────────────────────────────

class KBConfig(BaseModel):
    kb_id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    name: str
    description: str = ""
    domain: str = ""
    language: str = "zh"
    crawl_targets: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: KBStatus = KBStatus.ready


class KBStats(BaseModel):
    kb_id: str
    raw_count: int = 0
    source_count: int = 0
    entity_count: int = 0
    concept_count: int = 0
    indexed: bool = False
    last_processed: datetime | None = None


class KBDetail(BaseModel):
    """API 响应：KB 完整信息（含统计）"""
    kb_id: str
    name: str
    description: str
    domain: str
    language: str
    status: KBStatus
    created_at: datetime
    updated_at: datetime
    stats: KBStats


# ─────────────────────────────────────────────
# 文档流转模型
# ─────────────────────────────────────────────

class RawDocument(BaseModel):
    doc_id: str = ""          # 由系统生成，提交时可为空
    title: str
    url: str = ""
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    crawled_at: datetime = Field(default_factory=datetime.now)
    char_count: int = 0

    def model_post_init(self, __context: Any) -> None:
        if not self.char_count:
            self.char_count = len(self.content)


class SourcePage(BaseModel):
    doc_id: str
    title: str
    content_type: str = ContentType.other
    url: str = ""
    theme: str = ""
    key_points: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    raw_markdown: str = ""
    processed_at: datetime = Field(default_factory=datetime.now)


class EntityData(BaseModel):
    name: str
    category: str = EntityCategory.other
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    source_docs: list[str] = Field(default_factory=list)


class ConceptData(BaseModel):
    name: str
    category: str = ConceptCategory.other
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    source_docs: list[str] = Field(default_factory=list)


class WikiPage(BaseModel):
    name: str
    page_type: PageType
    category: str = ""
    content: str = ""
    aliases: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ─────────────────────────────────────────────
# 检索模型
# ─────────────────────────────────────────────

class SearchResult(BaseModel):
    page_type: str
    name: str
    score: float
    snippet: str = ""
    url: str = ""
    path: str = ""


class SearchResponse(BaseModel):
    query: str
    answer: str = ""
    sources: list[SearchResult] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    search_time_ms: float = 0.0


# ─────────────────────────────────────────────
# 任务模型
# ─────────────────────────────────────────────

class TaskState(BaseModel):
    task_id: str
    kb_id: str
    stage: str = PipelineStage.all
    status: TaskStatus = TaskStatus.pending
    total: int = 0
    completed: int = 0
    progress: float = 0.0
    errors: list[str] = Field(default_factory=list)
    message: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def update_progress(self, completed: int, total: int, message: str = "") -> None:
        self.completed = completed
        self.total = total
        self.progress = round(completed / total * 100, 1) if total > 0 else 0.0
        self.updated_at = datetime.now()
        if message:
            self.message = message


# ─────────────────────────────────────────────
# API 请求/响应模型
# ─────────────────────────────────────────────

class CreateKBRequest(BaseModel):
    kb_id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
    name: str
    description: str = ""
    domain: str = ""
    language: str = "zh"
    crawl_targets: list[str] = Field(default_factory=list)


class SubmitDocRequest(BaseModel):
    title: str
    url: str = ""
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchSubmitRequest(BaseModel):
    documents: list[SubmitDocRequest]


class RunPipelineRequest(BaseModel):
    stage: PipelineStage = PipelineStage.all
    force: bool = False
    doc_ids: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    generate_answer: bool = True


class WikiPageSummary(BaseModel):
    name: str
    type: str
    description: str = ""
    updated: str = ""


class WikiPageListResponse(BaseModel):
    items: list[WikiPageSummary]
    total: int
