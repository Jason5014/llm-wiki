# LLM 处理流水线设计

> 四个阶段将原始内容转化为结构化的 Wiki 知识图谱

---

## 一、流水线总览

```
Raw 原始文档
    │
    ▼ Stage 1: 数据清洗（可选）
清洗后的 Raw 文档
    │
    ▼ Stage 2: Source 摘要生成（LLM，per-document）
wiki/source/{doc_id}.md   ← 每篇文章生成一个摘要页
    │
    ▼ Stage 3: 实体/概念抽取（LLM，批量处理）
  ┌─┴─┐
  │   │
  ▼   ▼
wiki/entity/{Name}.md      wiki/concept/{name}.md
（如 Claude.md、OpenAI.md）  （如 agent.md、mcp.md）
  │   │
  └─┬─┘
    │
    ▼ Stage 4: 索引构建（自动，无 LLM）
wiki/index.md              db/fts.db + Milvus + graph.json
```

---

## 二、Stage 2 — Source 摘要生成

### 2.1 处理策略
- **逐文档处理**：每个 raw 文档独立调用一次 LLM
- **并发控制**：最多同时 3 个 LLM 调用（避免 API 限流）
- **跳过机制**：wiki/source 已存在则跳过（可强制重处理）
- **截断处理**：超过 12000 字符的内容截断后处理

### 2.2 Prompt 设计

```
系统角色：知识库构建助手，将原始网页/文章处理为结构化 Wiki 知识条目

输入：原始文章内容（纯文本）

输出格式：JSON
{
  "title": "文章原标题",
  "content_type": "tutorial|guide|news|opinion|comparison|case-study|other",
  "theme": "2-3句话描述核心主题和角度",
  "key_points": ["要点1", "要点2", ...],   // 4-8条，保留技术细节
  "tags": ["标签1", ...],                  // 5-10个
  "entities": ["Claude", "OpenAI", ...],   // 具体产品/公司/工具名
  "concepts": ["agent", "rag", ...]        // 技术概念/方法名
}

规则：
- entities：用英文标准名（Claude、MCP、LangChain）
- concepts：用小写英文或中文标准名（agent、rag、工具调用）
- key_points：保留数字、命令、专业术语
```

### 2.3 输出示例

```markdown
> 原始文档：15-hermes-features_a1b2c3d4

---
## 📋 基本信息
- **原标题**：15 个 Hermes 进阶功能
- **内容类型**：guide

## 🎯 核心主题
系统梳理了 Hermes Agent 的 15 项进阶功能，按基础设置、
中程控制、触达扩展、自定义能力四层分类，帮助用户充分
释放 Hermes 的能力。

## 📌 关键要点
- SOUL.md 永久定义 Agent 人格，跨会话生效
- memory.md + USER.md 支持 8 周内历史记忆召回
- /branch 开会话分支，/rollback 回滚文件系统
- Gateway 支持接入 Telegram、飞书等 17 个平台
- 支持自定义 skill 斜杠命令，永久跨平台可用

## 🏷️ 关键词标签
#[[Hermes]] #[[agent]] #[[Claude]] #[[memory]] #[[skill]]

## 🔗 相关实体
[[Hermes]]
[[Claude]]
[[Anthropic]]
[[Telegram]]

## 💡 关联概念
[[agent]]
[[memory]]
[[skill]]
[[工具调用]]
---
```

---

## 三、Stage 3 — 实体/概念抽取

### 3.1 处理策略
- **批量处理**：每批 20 个 source 页面，合并摘要后送给 LLM
- **跨文档识别**：同一批次内的实体/概念可以互相对照，确保命名一致
- **两轮去重**：
  - 批次内：LLM 自然去重
  - 跨批次：代码层按名称（case-insensitive）合并

### 3.2 批量抽取 Prompt

```
角色：知识库构建专家，从文章摘要集合中识别知识图谱元素

【实体（entity）】= 具体的事物：产品、公司、工具、框架、人物、项目
示例：Claude、OpenAI、MCP、LangChain、吴恩达

【概念（concept）】= 抽象的技术/方法/模式/理论
示例：agent、rag、工具调用、prompt engineering、工作流

输出：JSON
{
  "entities": [{
    "name": "标准名称",
    "category": "product|company|tool|person|project|other",
    "description": "一句话描述",
    "aliases": ["别名"],
    "related_entities": ["关联实体"],
    "related_concepts": ["关联概念"],
    "source_docs": ["文档ID"]
  }],
  "concepts": [{
    "name": "标准名称（小写英文或中文）",
    "category": "technology|method|pattern|theory|term|other",
    "description": "1-2句描述",
    "aliases": [],
    "related_concepts": [],
    "related_entities": [],
    "source_docs": []
  }]
}

规则：
- 只提取真正重要的、跨多篇文章出现的元素
- 过于通用的词（AI、技术等）单独出现时忽略
- 每个实体/概念仅出现一次
```

### 3.3 Wiki 页面生成 Prompt（Entity）

```
角色：知识库条目撰写专家

输入：
- 实体基本信息（name, category, description, aliases, related...）
- 相关文章的内容摘录（上下文，最多 3000 字）

输出：完整的 Markdown Wiki 页面
格式：见《02-数据模型.md》的 4.3 节

要求：
1. [[WikiLink]] 引用所有实体和概念
2. 基于上下文内容，保持事实准确
3. 百科全书风格，简洁专业
4. 中文撰写
```

---

## 四、Stage 4 — 索引构建

### 4.1 自动生成 index.md

扫描所有 entity/concept/source 页面，自动编译：
- 概念体系目录（按 category 分组）
- 实体对象目录（按 category 分组）
- 原始资料索引（按文档 ID 排序）
- 别名索引（从 YAML frontmatter 读取）
- 健康状态统计

### 4.2 构建 Milvus 向量索引

```
对每个 wiki 页面：
  1. 清洗 Markdown → 纯文本
  2. 长文档分块（按段落，最大 1000 字）
  3. 调用 DashScope text-embedding-v3 获取向量
  4. 批量写入 Milvus Collection

批量大小：25（DashScope API 单次最大）
向量维度：1024
距离度量：COSINE
```

### 4.3 构建 SQLite FTS5 索引

```sql
-- 对每个 wiki 页面执行：
INSERT OR REPLACE INTO wiki_fts(doc_id, page_type, title, content)
VALUES (?, ?, ?, ?);
```

### 4.4 构建关系图谱

从所有 entity/concept 页面提取 `[[WikiLink]]`，生成：
```json
{
  "nodes": [{"id": "entity:Claude", "label": "Claude", "type": "entity"}],
  "edges": [{"source": "entity:Claude", "target": "concept:agent", "type": "related"}]
}
```

---

## 五、流水线执行接口

### CLI 命令

```bash
# 完整流水线（从 raw 到索引）
llm-wiki process --kb ai-tech

# 单独执行某个阶段
llm-wiki process --kb ai-tech --stage source    # 只做 source 摘要
llm-wiki process --kb ai-tech --stage extract   # 只做实体/概念抽取
llm-wiki process --kb ai-tech --stage index     # 只重建索引

# 强制重新处理（忽略已处理的文件）
llm-wiki process --kb ai-tech --force
```

### API 触发（HTTP）

```
POST /api/process/{kb_id}/run         # 触发完整流水线
POST /api/process/{kb_id}/stage/{n}   # 触发指定阶段
GET  /api/process/{kb_id}/status      # 查询进度
GET  /api/process/{kb_id}/stream      # SSE 实时进度流
```

---

## 六、错误处理策略

| 错误类型 | 处理方式 |
|---------|---------|
| LLM API 超时 | Tenacity 自动重试，最多 3 次，指数退避 |
| LLM 返回非 JSON | 正则提取 JSON 片段；失败则跳过该文档并记录 |
| Milvus 连接失败 | 启动时检查，启动失败返回 503 |
| 文档过长 | 截断到 12000 字符后处理 |
| 实体名冲突 | 代码层 case-insensitive 合并，保留出现次数多的版本 |

---

## 七、性能估算

以 100 篇文章为例：

| 阶段 | 调用次数 | 预计耗时 |
|------|---------|---------|
| Source 摘要 | 100 次 LLM | ~15 分钟（并发 3） |
| 实体/概念抽取 | 5 批次（100/20）| ~5 分钟 |
| 页面生成 | ~50 次（实体+概念）| ~8 分钟 |
| 向量化 | 4 批次（150页/25）| ~2 分钟 |
| **总计** | | **~30 分钟** |
