# LLM Wiki — 开发命令集中管理
# 用法: make <target>
# 列出所有命令: make help

.PHONY: help setup setup-python setup-web setup-collector \
        dev api web collector milvus milvus-stop milvus-status \
        build build-web package-mac package-win \
        clean clean-wiki clean-index \
        check lint

# ─────────────────────────────────────────────
# 默认：显示帮助
# ─────────────────────────────────────────────

help:
	@echo ""
	@echo "  LLM Wiki 开发命令"
	@echo ""
	@echo "  ── 环境初始化 ──────────────────────────────"
	@echo "  make setup           安装所有依赖（Python + Web + Collector）"
	@echo "  make setup-python    仅安装 Python 依赖（uv sync）"
	@echo "  make setup-web       仅安装 Web 前端依赖"
	@echo "  make setup-collector 仅安装 Electron 采集器依赖"
	@echo ""
	@echo "  ── 开发启动 ────────────────────────────────"
	@echo "  make milvus          启动 Milvus 向量数据库（Docker）"
	@echo "  make milvus-stop     停止 Milvus"
	@echo "  make milvus-status   查看 Milvus 健康状态"
	@echo "  make api             启动 FastAPI 后端（端口 8000，热重载）"
	@echo "  make web             启动 Vue 前端（端口 5173，热重载）"
	@echo "  make collector       启动 Electron 采集应用（开发模式）"
	@echo "  make mcp             启动 MCP 服务器（stdio 模式）"
	@echo ""
	@echo "  ── 构建 ────────────────────────────────────"
	@echo "  make build-web       构建 Vue 前端（输出到 web/dist）"
	@echo "  make package-mac     打包 Electron 应用（macOS .dmg）"
	@echo "  make package-win     打包 Electron 应用（Windows .exe）"
	@echo ""
	@echo "  ── 工具 ────────────────────────────────────"
	@echo "  make check           检查各服务连接状态"
	@echo "  make clean           清除构建产物和缓存"
	@echo "  make clean-wiki      清除指定知识库的 wiki 输出（KB_ID=xxx）"
	@echo "  make clean-index     清除指定知识库的向量索引（KB_ID=xxx）"
	@echo ""

# ─────────────────────────────────────────────
# 环境初始化
# ─────────────────────────────────────────────

setup: setup-python setup-web setup-collector
	@echo ""
	@echo "✅ 所有依赖安装完成"
	@echo ""
	@echo "下一步："
	@echo "  1. 复制配置文件：cp .env.example .env"
	@echo "  2. 编辑 .env 填写 DASHSCOPE_API_KEY"
	@echo "  3. 启动 Milvus：make milvus"
	@echo "  4. 启动后端：make api"
	@echo "  5. 启动前端：make web"

setup-python:
	@echo ">>> 安装 Python 依赖（uv sync）..."
	uv sync
	@echo ">>> 安装 Playwright 浏览器..."
	uv run playwright install chromium

setup-web:
	@echo ">>> 安装 Web 前端依赖..."
	cd web && npm install

setup-collector:
	@echo ">>> 安装 Electron 采集器依赖..."
	cd collector && npm install

# ─────────────────────────────────────────────
# Milvus（向量数据库）
# ─────────────────────────────────────────────

milvus:
	@if curl -sf http://localhost:9091/healthz > /dev/null 2>&1; then \
		echo "✅ Milvus 已在运行：http://localhost:9091/healthz"; \
	else \
		echo ">>> 清理残留容器..."; \
		for cname in milvus-standalone milvus-etcd milvus-minio; do \
			docker ps -a --format '{{.Names}}' | grep -qx "$$cname" && docker rm -f "$$cname" 2>/dev/null || true; \
		done; \
		echo ">>> 启动 Milvus..."; \
		docker compose up -d; \
		echo ">>> 等待 Milvus 就绪（最多 30s）..."; \
		for i in $$(seq 1 10); do \
			sleep 3; \
			if curl -sf http://localhost:9091/healthz > /dev/null 2>&1; then \
				echo "✅ Milvus 已启动：http://localhost:9091/healthz"; \
				break; \
			fi; \
			echo "  等待中... ($$i/10)"; \
		done; \
	fi

milvus-stop:
	docker compose down
	@echo "✅ Milvus 已停止"

milvus-status:
	@curl -sf http://localhost:9091/healthz && echo "✅ Milvus 运行正常" || echo "❌ Milvus 未响应"

# ─────────────────────────────────────────────
# 后端 API
# ─────────────────────────────────────────────

api:
	@if [ ! -f .env ]; then \
		echo "⚠️  未找到 .env 文件，请先执行: cp .env.example .env"; \
		exit 1; \
	fi
	@echo ">>> 启动 FastAPI 后端 → http://localhost:8000"
	@echo "    API 文档 → http://localhost:8000/docs"
	uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# ─────────────────────────────────────────────
# Web 前端
# ─────────────────────────────────────────────

web:
	@echo ">>> 启动 Vue 前端 → http://localhost:5173"
	cd web && npm run dev

# ─────────────────────────────────────────────
# Electron 采集器
# ─────────────────────────────────────────────

collector:
	@echo ">>> 启动 Electron 采集应用（开发模式）"
	cd collector && npm run dev

# ─────────────────────────────────────────────
# MCP 服务器
# ─────────────────────────────────────────────

mcp:
	@if [ ! -f .env ]; then \
		echo "⚠️  未找到 .env 文件"; exit 1; \
	fi
	@echo ">>> 启动 MCP 服务器（stdio 模式）"
	uv run python -m src.mcp.server

# ─────────────────────────────────────────────
# 构建 & 打包
# ─────────────────────────────────────────────

build-web:
	@echo ">>> 构建 Vue 前端..."
	cd web && npm run build
	@echo "✅ 构建完成，输出目录：web/dist"

package-mac:
	@echo ">>> 打包 Electron（macOS）..."
	cd collector && npm run package:mac
	@echo "✅ 安装包位于：collector/dist"

package-win:
	@echo ">>> 打包 Electron（Windows）..."
	cd collector && npm run package:win
	@echo "✅ 安装包位于：collector/dist"

# ─────────────────────────────────────────────
# 健康检查
# ─────────────────────────────────────────────

check:
	@echo ""
	@echo "=== 服务状态检查 ==="
	@echo ""
	@printf "Milvus (9091):  "; \
		curl -sf http://localhost:9091/healthz > /dev/null && echo "✅ 运行中" || echo "❌ 未启动"
	@printf "FastAPI (8000): "; \
		curl -sf http://localhost:8000/health > /dev/null && echo "✅ 运行中" || echo "❌ 未启动"
	@printf "Vue Dev (5173): "; \
		curl -sf http://localhost:5173 > /dev/null && echo "✅ 运行中" || echo "❌ 未启动"
	@echo ""
	@echo "=== 配置文件 ==="
	@test -f .env && echo "✅ .env 存在" || echo "⚠️  .env 缺失（请执行: cp .env.example .env）"
	@test -f web/node_modules/.package-lock.json && echo "✅ web 依赖已安装" || echo "⚠️  web 依赖未安装（make setup-web）"
	@test -f collector/node_modules/.package-lock.json && echo "✅ collector 依赖已安装" || echo "⚠️  collector 依赖未安装（make setup-collector）"
	@echo ""

# ─────────────────────────────────────────────
# 清理
# ─────────────────────────────────────────────

clean:
	rm -rf web/dist web/.vite
	rm -rf collector/out collector/dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ 清理完成"

# 清除指定知识库的 wiki 输出（保留 raw 原始文档）
# 用法: make clean-wiki KB_ID=ai-tech
clean-wiki:
	@if [ -z "$(KB_ID)" ]; then echo "用法: make clean-wiki KB_ID=ai-tech"; exit 1; fi
	rm -rf knowledge_bases/$(KB_ID)/wiki/*
	@echo "✅ 已清除 knowledge_bases/$(KB_ID)/wiki/"

# 清除指定知识库的向量索引（FTS + graph）
# 用法: make clean-index KB_ID=ai-tech
clean-index:
	@if [ -z "$(KB_ID)" ]; then echo "用法: make clean-index KB_ID=ai-tech"; exit 1; fi
	rm -f knowledge_bases/$(KB_ID)/db/fts.db
	rm -f knowledge_bases/$(KB_ID)/db/graph.json
	@echo "✅ 已清除 knowledge_bases/$(KB_ID)/db/ 中的索引文件"
