#!/usr/bin/env bash
# LLM Wiki — 停止所有开发服务

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[stop] 停止 FastAPI..."
pkill -f "uvicorn api.main:app" 2>/dev/null && echo "  ✅ FastAPI 已停止" || echo "  — FastAPI 未运行"

echo "[stop] 停止 Vue 开发服务器..."
pkill -f "vite.*web" 2>/dev/null && echo "  ✅ Vue 已停止" || echo "  — Vue 未运行"

echo "[stop] 停止 Milvus..."
docker compose down 2>/dev/null && echo "  ✅ Milvus 已停止" || echo "  — Milvus 未运行"

echo ""
echo "✅ 所有服务已停止"
