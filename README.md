# LLM Wiki

> 基于 LLM 的结构化知识库系统 — 让 AI 像人类浏览维基百科一样推理知识

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.4+-brightgreen.svg)](https://vuejs.org)
[![Electron](https://img.shields.io/badge/Electron-31+-9cf.svg)](https://electronjs.org)
[![Milvus](https://img.shields.io/badge/Milvus-2.4+-blue.svg)](https://milvus.io)

---

## 项目背景

传统 RAG 知识库把文档切成固定大小的 Chunk，既丢失了上下文和逻辑结构，检索时也只能做模糊的向量匹配。

**LLM Wiki** 参考 Andrej Karpathy 提出的 LLM Wiki 理念，把原始内容通过 LLM **编译**成结构化的 Wiki 页面网络，再通过向量检索 + 全文检索 + 图谱导航的混合方式，让 AI 能在知识图谱中进行**导航式推理**，而不是简单的 Top-K 召回。

```
原始文档 ──LLM编译──► entity 页面 ◄──[[WikiLink]]──► concept 页面
                    ↕                              ↕
              source 摘要页面              混合检索引擎
                    ↕                              ↕
              Milvus 向量索引 ◄─── 搜索问答 ───► SQLite FTS5
```

---

## 功能特性

| 模块 | 功能 |
|------|------|
| **知识处理** | LLM 四阶段流水线：清洗 → 摘要 → 实体/概念抽取 → 索引构建 |
| **知识图谱** | `source / entity / concept` 三层 Wiki 页面，`[[WikiLink]]` 双向链接 |
| **混合检索** | 直接匹配 + Milvus 向量检索 + SQLite FTS5 全文，RRF 融合排序 |
| **数据采集** | Electron 桌面应用，内嵌浏览器支持登录采集（小红书/知乎等） |
| **Web 界面** | Wiki 浏览器、知识图谱可视化、AI 搜索问答、流水线管理 |
| **MCP 工具** | 4 个标准化工具接口，供外部 AI Agent 调用知识库 |
| **CLI** | 命令行工具，支持本地文档导入和搜索 |

---

## 技术栈

| 层次 | 技术 |
|------|------|
| LLM & Embedding | Qwen（通义千问）via DashScope — `qwen-plus` / `text-embedding-v3` |
| 向量数据库 | Milvus Standalone（Docker），IVF_FLAT + COSINE，1024维 |
| 全文检索 | SQLite FTS5，unicode61 分词 |
| 后端框架 | Python 3.11 + FastAPI + SSE（实时进度） |
| Web 前端 | Vue 3 + Vite + Element Plus + ECharts（知识图谱） |
| 桌面采集 | Electron 31 + electron-vite，支持 macOS / Windows |
| MCP 服务 | Python MCP SDK，stdio 传输 |
| 包管理 | uv（Python）+ npm（Node） |

---

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 20+
- Docker（运行 Milvus）
- [uv](https://astral.sh/uv)（Python 包管理）
- 阿里云 [DashScope API Key](https://dashscope.console.aliyun.com/)

### 1. 安装依赖

```bash
# 克隆项目
git clone git@github.com:Jason5014/llm-wiki.git
cd llm-wiki

# 安装所有依赖（Python + Web + Electron）
make setup
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填写必要配置：

```dotenv
DASHSCOPE_API_KEY=sk-xxx     # 阿里云 DashScope API Key（必填）
LLM_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v3
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

### 3. 启动开发环境

```bash
# 一键启动全部服务（推荐）
./scripts/dev.sh

# 或手动分步启动
make milvus    # 启动向量数据库（Docker）
make api       # 启动 FastAPI 后端（:8000）
make web       # 启动 Vue 前端（:5173）
make collector # 启动 Electron 采集器（可选）
```

| 服务 | 地址 |
|------|------|
| FastAPI 后端 | http://localhost:8000 |
| API 文档（Swagger） | http://localhost:8000/docs |
| Vue 前端 | http://localhost:5173 |
| Milvus 健康检查 | http://localhost:9091/healthz |

```bash
# 停止所有服务
./scripts/stop.sh
```

---

## 使用方式

### Web 界面

打开 http://localhost:5173，通过可视化界面完成：

1. **创建知识库** → 首页点击"新建知识库"
2. **导入文档** → 流水线页面上传 `.md / .txt / .pdf / .html` 文件
3. **运行流水线** → 点击"开始处理"，SSE 实时查看处理进度
4. **浏览 Wiki** → 左侧目录树点击任意 entity/concept 页面
5. **搜索问答** → 顶部搜索框，支持自然语言提问
6. **知识图谱** → 图谱页面查看实体关系的力导向图

### Electron 采集器

用于采集需要登录的网站（小红书、知乎等）：

1. 在**浏览器视图**中登录目标网站（Cookie 自动持久化）
2. 浏览到目标页面，点击**"保存当前页"**
3. 预览提取内容后确认，文档自动提交到知识库
4. 也可在**批量队列**视图中一次性提交多个 URL

### CLI

```bash
# 创建知识库
uv run llm-wiki create my-kb --name "AI 技术知识库"

# 导入文档
uv run llm-wiki collect my-kb --file ./article.md
uv run llm-wiki collect my-kb --dir ./docs/

# 运行处理流水线（全部阶段）
uv run llm-wiki process my-kb

# 运行指定阶段（source / extract / index）
uv run llm-wiki process my-kb --stage source

# 搜索
uv run llm-wiki search my-kb "什么是 RAG？"

# 列出所有知识库
uv run llm-wiki list
```

### MCP 服务

将 LLM Wiki 作为工具接口接入 AI Agent：

```bash
# 启动 MCP 服务器（stdio 模式）
make mcp
```

**可用工具：**

| 工具 | 说明 |
|------|------|
| `search_knowledge` | 混合检索 + LLM 生成答案 |
| `get_wiki_page` | 获取指定 entity/concept 页面内容 |
| `list_knowledge_bases` | 列出所有可用知识库 |
| `get_related_pages` | 获取页面的 WikiLink 关联页面 |

---

## 项目结构

```
llm-wiki/
├── api/                        # FastAPI 后端
│   ├── main.py                 # 应用入口，CORS，路由注册
│   └── routers/
│       ├── kb_router.py        # 知识库管理（CRUD）
│       ├── collect_router.py   # 文档收集（提交/上传/批量）
│       ├── process_router.py   # 流水线触发 + SSE 进度推送
│       ├── wiki_router.py      # Wiki 页面读取 + 图谱数据
│       └── search_router.py    # 搜索问答接口
│
├── src/                        # 核心业务逻辑
│   ├── config.py               # 全局配置（pydantic-settings）
│   ├── models.py               # 数据模型（Pydantic v2）
│   ├── storage.py              # 文件存储抽象层
│   ├── llm.py                  # LLM + Embedding 封装（DashScope）
│   ├── pipeline.py             # 异步流水线调度 + SSE 任务管理
│   ├── processor/
│   │   ├── source_processor.py         # Stage 2：文档摘要生成
│   │   ├── entity_concept_extractor.py # Stage 3a：实体/概念批量抽取
│   │   ├── page_builder.py             # Stage 3b：Wiki 页面生成
│   │   └── index_builder.py            # Stage 4：索引 + 图谱构建
│   ├── indexer/
│   │   └── indexer.py          # Milvus 向量索引 + SQLite FTS5
│   ├── retriever/
│   │   └── retriever.py        # 三路检索 + RRF 融合 + LLM 答案生成
│   └── mcp/
│       └── server.py           # MCP 服务器
│
├── collector/                  # Electron 桌面采集应用
│   └── src/
│       ├── main/               # 主进程（BrowserWindow、IPC、会话管理）
│       ├── preload/            # 预加载脚本（contextBridge）
│       └── renderer/src/views/
│           ├── BrowserView.vue   # 内嵌浏览器 + 一键保存
│           ├── QueueView.vue     # 批量 URL 队列采集
│           ├── ImportView.vue    # 本地文件拖拽导入
│           └── SettingsView.vue  # 设置 + Cookie 管理
│
├── web/                        # Vue 3 Web 前端
│   └── src/views/
│       ├── HomeView.vue          # 知识库管理
│       ├── WikiView.vue          # Wiki 页面浏览（支持 WikiLink）
│       ├── SearchView.vue        # 搜索问答
│       ├── GraphView.vue         # ECharts 知识图谱
│       └── PipelineView.vue      # 流水线管理 + 实时日志
│
├── cli.py                      # typer CLI
├── docker-compose.yml          # Milvus Standalone 部署
├── pyproject.toml              # Python 依赖（uv 管理）
├── Makefile                    # 开发命令集中管理
├── scripts/
│   ├── dev.sh                  # 一键启动开发环境
│   └── stop.sh                 # 停止所有服务
├── .env.example                # 环境变量模板
└── docs/                       # 设计文档（架构 / 流水线 / API 等）
```

---

## 知识库存储结构

每个知识库的数据以 Markdown 文件存储，与 Obsidian 格式兼容：

```
knowledge_bases/
└── {kb_id}/
    ├── config.json               # 知识库配置
    ├── raw/                      # 原始采集内容（Markdown）
    ├── wiki/
    │   ├── source/               # 每篇文档的结构化摘要页面
    │   ├── entity/               # 实体页面（公司、产品、人物等）
    │   ├── concept/              # 概念页面（技术、方法、理论等）
    │   └── index.md              # 全局索引 + 别名表
    └── db/
        ├── fts.db                # SQLite FTS5 全文检索索引
        └── graph.json            # 实体关系图（节点 + 边）
```

> Milvus 向量数据存储在 Docker volume 中，独立于文件目录。

---

## 检索架构

搜索请求同时走三条路径，通过 **RRF（Reciprocal Rank Fusion）** 融合排序：

```
查询
  ├── 直接匹配（精确/部分名称）   → score: 1.0 / 0.8
  ├── Milvus 向量检索（语义相似）  → COSINE 距离
  └── SQLite FTS5（关键词全文）    → BM25-like 评分
           ↓
      RRF 融合（k=60）
           ↓
      Top-N 候选页面
           ↓
      Qwen LLM 生成最终答案（引用 WikiLink）
```

---

## 开发命令

```bash
make help            # 查看所有可用命令

# 环境
make setup           # 安装所有依赖
make check           # 检查各服务运行状态

# 开发
make milvus          # 启动 Milvus
make api             # 启动后端（热重载）
make web             # 启动前端（热重载）
make collector       # 启动 Electron

# 构建
make build-web       # 构建 Vue 前端
make package-mac     # 打包 Electron（macOS .dmg）
make package-win     # 打包 Electron（Windows .exe）

# 清理
make clean           # 清除构建产物
make clean-wiki KB_ID=my-kb   # 清除指定知识库的 Wiki 输出
make clean-index KB_ID=my-kb  # 清除指定知识库的向量索引
```

---

## 文档

| 文档 | 内容 |
|------|------|
| [00-项目总览](./docs/00-项目总览.md) | 项目目标、模块总览、快速启动 |
| [01-技术选型](./docs/01-技术选型.md) | 技术栈选型决策与理由 |
| [02-数据模型](./docs/02-数据模型.md) | Pydantic 数据结构定义 |
| [03-数据采集层](./docs/03-数据采集层.md) | Electron 采集应用设计 |
| [04-LLM处理流水线](./docs/04-LLM处理流水线.md) | 四阶段处理流程 + Prompt 设计 |
| [05-知识图谱存储](./docs/05-知识图谱存储.md) | Wiki 文件格式规范 |
| [06-检索引擎](./docs/06-检索引擎.md) | 混合检索策略设计 |
| [07-API接口](./docs/07-API接口.md) | FastAPI 接口文档 |
| [08-前端UI](./docs/08-前端UI.md) | Vue3 页面设计 |
| [09-MCP服务](./docs/09-MCP服务.md) | MCP 工具接口定义 |
| [10-部署方案](./docs/10-部署方案.md) | Docker 部署 + 环境配置 |
