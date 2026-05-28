# MCP 服务器设计

> 通过 MCP 协议对外暴露知识库能力，让 Claude 等 AI 工具可以直接调用

---

## 一、概述

LLM Wiki 提供标准 MCP 服务器，支持：
- 在 Claude Desktop / Claude Code 中直接查询知识库
- 在任何支持 MCP 的 AI 工具中使用
- 通过 stdio 或 HTTP 两种方式运行

---

## 二、MCP 工具定义

### 工具 1：search_knowledge

**功能**：在知识库中搜索并获取 AI 生成的回答

```json
{
  "name": "search_knowledge",
  "description": "在 LLM Wiki 知识库中搜索问题并获取智能回答，附带引用来源",
  "inputSchema": {
    "type": "object",
    "properties": {
      "kb_id": {
        "type": "string",
        "description": "知识库 ID，如 'ai-tech'"
      },
      "query": {
        "type": "string",
        "description": "要搜索的问题或关键词"
      },
      "top_k": {
        "type": "integer",
        "description": "返回的参考来源数量，默认 5",
        "default": 5
      }
    },
    "required": ["kb_id", "query"]
  }
}
```

**响应示例**：
```
回答：使用 [[Hermes]] 实现持久化记忆主要通过 memory.md 和 USER.md 两个文件...

参考来源：
- [concept/memory] 记忆层，支持 FTS5 + LLM 摘要索引（相关度: 92%）
- [source/15-hermes-features] 15个Hermes进阶功能（相关度: 87%）
```

---

### 工具 2：get_wiki_page

**功能**：获取特定 Wiki 页面的完整内容

```json
{
  "name": "get_wiki_page",
  "description": "获取知识库中某个实体或概念的完整 Wiki 页面内容",
  "inputSchema": {
    "type": "object",
    "properties": {
      "kb_id": {
        "type": "string",
        "description": "知识库 ID"
      },
      "page_type": {
        "type": "string",
        "enum": ["entity", "concept", "source"],
        "description": "页面类型"
      },
      "name": {
        "type": "string",
        "description": "页面名称，如 'Claude'、'agent'"
      }
    },
    "required": ["kb_id", "page_type", "name"]
  }
}
```

---

### 工具 3：list_knowledge_bases

**功能**：列出所有可用的知识库

```json
{
  "name": "list_knowledge_bases",
  "description": "列出所有可用的知识库及其基本信息",
  "inputSchema": {
    "type": "object",
    "properties": {}
  }
}
```

**响应示例**：
```
可用知识库：
1. ai-tech — AI技术知识库（96文档，25实体，25概念）
2. finance — 金融研究库（45文档，18实体，12概念）
```

---

### 工具 4：get_related_pages

**功能**：获取与某个实体/概念相关联的页面列表

```json
{
  "name": "get_related_pages",
  "description": "获取与指定实体或概念相关联的所有页面",
  "inputSchema": {
    "type": "object",
    "properties": {
      "kb_id": {"type": "string"},
      "name": {"type": "string", "description": "实体或概念名称"},
      "depth": {"type": "integer", "default": 1, "description": "关联深度，1=直接关联"}
    },
    "required": ["kb_id", "name"]
  }
}
```

---

## 三、MCP 服务器配置

### Claude Desktop 配置（`claude_desktop_config.json`）

```json
{
  "mcpServers": {
    "llm-wiki": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "/path/to/llm-wiki",
      "env": {
        "DASHSCOPE_API_KEY": "sk-xxx",
        "MILVUS_HOST": "localhost"
      }
    }
  }
}
```

### 运行方式

```bash
# stdio 模式（给 Claude Desktop 使用）
python -m src.mcp.server

# HTTP 模式（可选，给其他 MCP 客户端使用）
python -m src.mcp.server --transport http --port 3100
```
