# API 接口文档

> FastAPI 后端所有接口定义

Base URL: `http://localhost:8000`

---

## 一、知识库管理 `/api/kb`

### 获取所有知识库
```
GET /api/kb/
```
响应：
```json
[
  {
    "kb_id": "ai-tech",
    "name": "AI技术知识库",
    "description": "...",
    "domain": "AI/Tech",
    "status": "ready",
    "stats": {
      "raw_count": 96,
      "source_count": 96,
      "entity_count": 25,
      "concept_count": 25,
      "indexed": true
    }
  }
]
```

### 创建知识库
```
POST /api/kb/
```
请求体：
```json
{
  "kb_id": "ai-tech",
  "name": "AI技术知识库",
  "description": "收录AI技术相关知识",
  "domain": "AI/Tech",
  "language": "zh",
  "crawl_targets": []
}
```

### 获取单个知识库
```
GET /api/kb/{kb_id}
```

### 删除知识库
```
DELETE /api/kb/{kb_id}
```

---

## 二、数据采集 `/api/collect`

### 提交单篇原始内容
```
POST /api/collect/{kb_id}/raw
```
请求体：
```json
{
  "title": "15 个 Hermes 进阶功能",
  "url": "https://www.xiaohongshu.com/...",
  "content": "正文内容...",
  "metadata": {
    "likes": 139,
    "collects": 268,
    "source": "xiaohongshu"
  }
}
```
响应：
```json
{
  "doc_id": "15-hermes-features_a1b2c3d4",
  "saved": true
}
```

### 批量提交原始内容
```
POST /api/collect/{kb_id}/batch
```
请求体：`{ "documents": [RawDocument, ...] }`

### 导入本地文件（文件上传）
```
POST /api/collect/{kb_id}/upload
Content-Type: multipart/form-data
file: [文件]
```
支持格式：`.md`、`.txt`、`.pdf`、`.html`

### 查看原始文档列表
```
GET /api/collect/{kb_id}/raw?page=1&page_size=20
```

---

## 三、处理流水线 `/api/process`

### 触发完整流水线
```
POST /api/process/{kb_id}/run
```
请求体（可选）：
```json
{
  "stage": "all",        // all | source | extract | pages | index
  "force": false,        // 是否强制重新处理
  "doc_ids": []          // 仅处理指定文档（空=全部）
}
```
响应：
```json
{
  "task_id": "task_abc123",
  "status": "running",
  "message": "流水线已启动"
}
```

### 查询任务状态
```
GET /api/process/{kb_id}/tasks/{task_id}
```
响应：
```json
{
  "task_id": "task_abc123",
  "kb_id": "ai-tech",
  "stage": "source",
  "status": "running",
  "total": 96,
  "completed": 43,
  "progress": 44.8,
  "errors": [],
  "message": "正在处理：hermes-memory-guide..."
}
```

### SSE 实时进度推送
```
GET /api/process/{kb_id}/tasks/{task_id}/stream
Accept: text/event-stream
```
推送格式：
```
data: {"completed": 44, "total": 96, "message": "处理中..."}

data: {"completed": 96, "total": 96, "status": "done", "message": "完成"}
```

---

## 四、Wiki 内容 `/api/wiki`

### 获取页面内容
```
GET /api/wiki/{kb_id}/page/{page_type}/{name}
```
- `page_type`: `source` | `entity` | `concept`
- 响应：Markdown 文本

### 获取 index.md
```
GET /api/wiki/{kb_id}/index
```

### 列出所有页面
```
GET /api/wiki/{kb_id}/pages?type=entity&page=1&page_size=50
```
响应：
```json
{
  "items": [
    {"name": "Claude", "type": "entity", "description": "..."},
    {"name": "OpenAI", "type": "entity", "description": "..."}
  ],
  "total": 25
}
```

### 获取关系图谱数据
```
GET /api/wiki/{kb_id}/graph
```
响应：`graph.json` 内容（nodes + edges）

---

## 五、搜索问答 `/api/search`

### 搜索查询
```
POST /api/search/{kb_id}/query
```
请求体：
```json
{
  "query": "怎么用 Hermes 实现持久化记忆？",
  "top_k": 5,
  "generate_answer": true
}
```
响应：
```json
{
  "query": "怎么用 Hermes 实现持久化记忆？",
  "answer": "使用 [[Hermes]] 的 memory.md 和 USER.md 文件...",
  "sources": [
    {
      "page_type": "concept",
      "name": "memory",
      "score": 0.92,
      "snippet": "记忆层，支持 FTS5 + LLM 摘要索引...",
      "path": "concept/memory"
    }
  ],
  "related_entities": ["Hermes", "Claude"],
  "related_concepts": ["memory", "agent"],
  "search_time_ms": 3240
}
```

### 纯检索（不生成答案）
```
POST /api/search/{kb_id}/retrieve
```
同上，但 `generate_answer: false`，响应更快

---

## 六、健康检查

```
GET /health
```
响应：`{"status": "ok", "service": "llm-wiki"}`

---

## 七、错误码规范

| HTTP 状态码 | 含义 |
|-----------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在（KB/页面不存在） |
| 409 | 冲突（KB 已存在） |
| 422 | 请求体格式错误 |
| 500 | 服务内部错误 |
| 503 | Milvus 不可用 |

错误响应格式：
```json
{
  "detail": "错误描述"
}
```
