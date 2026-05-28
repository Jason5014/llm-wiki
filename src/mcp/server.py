"""
MCP 服务器 — 通过 MCP 协议对外暴露知识库能力
支持在 Claude Desktop / Claude Code 中直接查询知识库
"""
import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from src.storage import get_kb_stats, list_kb_ids, load_kb_config, load_wiki_page

app = Server("llm-wiki")


# ─────────────────────────────────────────────
# 工具定义
# ─────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_knowledge",
            description="在 LLM Wiki 知识库中搜索问题并获取智能回答，附带引用来源",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库 ID，如 'ai-tech'",
                    },
                    "query": {
                        "type": "string",
                        "description": "要搜索的问题或关键词",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回的参考来源数量，默认 5",
                        "default": 5,
                    },
                },
                "required": ["kb_id", "query"],
            },
        ),
        Tool(
            name="get_wiki_page",
            description="获取知识库中某个实体或概念的完整 Wiki 页面内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {"type": "string", "description": "知识库 ID"},
                    "page_type": {
                        "type": "string",
                        "enum": ["entity", "concept", "source"],
                        "description": "页面类型",
                    },
                    "name": {
                        "type": "string",
                        "description": "页面名称，如 'Claude'、'agent'",
                    },
                },
                "required": ["kb_id", "page_type", "name"],
            },
        ),
        Tool(
            name="list_knowledge_bases",
            description="列出所有可用的知识库及其基本信息",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_related_pages",
            description="获取与指定实体或概念相关联的所有页面",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {"type": "string"},
                    "name": {"type": "string", "description": "实体或概念名称"},
                    "depth": {
                        "type": "integer",
                        "default": 1,
                        "description": "关联深度，1=直接关联",
                    },
                },
                "required": ["kb_id", "name"],
            },
        ),
    ]


# ─────────────────────────────────────────────
# 工具实现
# ─────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "list_knowledge_bases":
        return await _list_knowledge_bases()

    elif name == "search_knowledge":
        return await _search_knowledge(
            kb_id=arguments["kb_id"],
            query=arguments["query"],
            top_k=arguments.get("top_k", 5),
        )

    elif name == "get_wiki_page":
        return await _get_wiki_page(
            kb_id=arguments["kb_id"],
            page_type=arguments["page_type"],
            name=arguments["name"],
        )

    elif name == "get_related_pages":
        return await _get_related_pages(
            kb_id=arguments["kb_id"],
            name=arguments["name"],
            depth=arguments.get("depth", 1),
        )

    return [TextContent(type="text", text=f"未知工具：{name}")]


async def _list_knowledge_bases() -> list[TextContent]:
    ids = list_kb_ids()
    if not ids:
        return [TextContent(type="text", text="暂无可用知识库")]

    lines = ["可用知识库："]
    for i, kb_id in enumerate(ids, 1):
        config = load_kb_config(kb_id)
        stats = get_kb_stats(kb_id)
        if config:
            lines.append(
                f"{i}. {kb_id} — {config.name}"
                f"（{stats.raw_count}文档，{stats.entity_count}实体，{stats.concept_count}概念）"
            )

    return [TextContent(type="text", text="\n".join(lines))]


async def _search_knowledge(kb_id: str, query: str, top_k: int) -> list[TextContent]:
    if not load_kb_config(kb_id):
        return [TextContent(type="text", text=f"知识库 '{kb_id}' 不存在")]

    from src.retriever.retriever import search
    result = await search(kb_id, query, top_k=top_k, generate_answer_flag=True)

    lines = []
    if result.answer:
        lines.append(f"回答：{result.answer}")
        lines.append("")

    if result.sources:
        lines.append("参考来源：")
        for src in result.sources:
            pct = int(src.score * 100)
            lines.append(f"- [{src.path}] {src.snippet[:100]}（相关度: {pct}%）")

    lines.append(f"\n搜索耗时：{result.search_time_ms:.0f}ms")
    return [TextContent(type="text", text="\n".join(lines))]


async def _get_wiki_page(kb_id: str, page_type: str, name: str) -> list[TextContent]:
    if not load_kb_config(kb_id):
        return [TextContent(type="text", text=f"知识库 '{kb_id}' 不存在")]

    content = load_wiki_page(kb_id, page_type, name)
    if not content:
        return [TextContent(type="text", text=f"页面 '{page_type}/{name}' 不存在")]

    return [TextContent(type="text", text=content)]


async def _get_related_pages(kb_id: str, name: str, depth: int) -> list[TextContent]:
    if not load_kb_config(kb_id):
        return [TextContent(type="text", text=f"知识库 '{kb_id}' 不存在")]

    from src.storage import extract_wikilinks, list_wiki_pages

    # 找到起始页面
    related: list[str] = []
    for page_type in ("entity", "concept"):
        content = load_wiki_page(kb_id, page_type, name)
        if content:
            links = extract_wikilinks(content)
            related.extend(links)
            break

    if not related:
        return [TextContent(type="text", text=f"未找到与 '{name}' 相关的页面")]

    lines = [f"与 '{name}' 相关的页面："]
    for link in related[:20]:
        lines.append(f"- {link}")

    return [TextContent(type="text", text="\n".join(lines))]


# ─────────────────────────────────────────────
# 服务器启动
# ─────────────────────────────────────────────

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="LLM Wiki MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=3100)
    args = parser.parse_args()

    if args.transport == "stdio":
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    else:
        # HTTP 模式（可选）
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route
        import uvicorn

        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await app.run(streams[0], streams[1], app.create_initialization_options())

        starlette_app = Starlette(routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages", app=sse.handle_post_message),
        ])
        uvicorn.run(starlette_app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    asyncio.run(main())
