#!/usr/bin/env bash
# LLM Wiki — 一键启动开发环境
# 用法: ./scripts/dev.sh [--no-collector]
#
# 自动在多个 Terminal/iTerm2 窗口启动：
#   1. Milvus（Docker）
#   2. FastAPI 后端（:8000）
#   3. Vue 前端（:5173）
#   4. Electron 采集器（可选，默认启动）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# ── 参数 ─────────────────────────────────────
START_COLLECTOR=true
for arg in "$@"; do
  [[ "$arg" == "--no-collector" ]] && START_COLLECTOR=false
done

# ── 颜色输出 ──────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RESET='\033[0m'
log_info()  { echo -e "${BLUE}[dev]${RESET} $*"; }
log_ok()    { echo -e "${GREEN}[dev]${RESET} $*"; }
log_warn()  { echo -e "${YELLOW}[dev]${RESET} $*"; }
log_error() { echo -e "${RED}[dev]${RESET} $*"; }

# ── 前置检查 ──────────────────────────────────
cd "$ROOT"

if [ ! -f .env ]; then
  log_error ".env 文件不存在，请先执行："
  echo "  cp .env.example .env"
  echo "  然后填写 DASHSCOPE_API_KEY"
  exit 1
fi

if ! command -v uv &>/dev/null; then
  log_error "未找到 uv，请先安装：curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

if ! command -v docker &>/dev/null; then
  log_warn "未找到 docker，跳过 Milvus 启动"
  SKIP_MILVUS=true
fi

# ── 启动函数 ──────────────────────────────────

open_new_terminal() {
  local title="$1"
  local cmd="$2"
  local dir="${3:-$ROOT}"

  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS：使用 osascript 打开 Terminal 新标签
    osascript -e "
      tell application \"Terminal\"
        tell application \"System Events\" to keystroke \"t\" using command down
        delay 0.3
        do script \"cd '$dir' && echo '=== $title ===' && $cmd\" in front window
      end tell
    " 2>/dev/null || {
      # 回退：直接在后台执行并输出到文件
      mkdir -p "$ROOT/.logs"
      nohup bash -c "cd '$dir' && $cmd" > "$ROOT/.logs/${title//[^a-zA-Z0-9]/_}.log" 2>&1 &
      log_info "$title → 日志: .logs/${title//[^a-zA-Z0-9]/_}.log"
    }
  else
    # Linux/其他：后台运行 + 日志
    mkdir -p "$ROOT/.logs"
    nohup bash -c "cd '$dir' && $cmd" > "$ROOT/.logs/${title//[^a-zA-Z0-9]/_}.log" 2>&1 &
    log_info "$title → 日志: .logs/${title//[^a-zA-Z0-9]/_}.log"
  fi
}

# ── 1. 启动 Milvus ────────────────────────────
if [ -z "$SKIP_MILVUS" ]; then
  # 先检测是否已在运行，避免容器名冲突
  if curl -sf http://localhost:9091/healthz > /dev/null 2>&1; then
    log_ok "Milvus 已在运行，跳过启动 ✅"
  else
    log_info "启动 Milvus..."
    if ! docker compose up -d 2>&1; then
      log_warn "docker compose up 失败（可能容器名冲突），尝试重建..."
      docker compose down 2>/dev/null || true
      docker compose up -d
    fi

    log_info "等待 Milvus 就绪..."
    for i in $(seq 1 15); do
      sleep 2
      if curl -sf http://localhost:9091/healthz > /dev/null 2>&1; then
        log_ok "Milvus 就绪 ✅"
        break
      fi
      if [ $i -eq 15 ]; then
        log_warn "Milvus 启动超时，继续启动其他服务（可稍后重试）"
      fi
    done
  fi
fi

# ── 2. 启动 FastAPI ───────────────────────────
log_info "启动 FastAPI 后端..."
open_new_terminal "FastAPI :8000" \
  "uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000"

sleep 1

# ── 3. 启动 Vue 前端 ──────────────────────────
if [ -d "$ROOT/web/node_modules" ]; then
  log_info "启动 Vue 前端..."
  open_new_terminal "Vue :5173" "npm run dev" "$ROOT/web"
else
  log_warn "web/node_modules 不存在，跳过前端（请先执行: make setup-web）"
fi

# ── 4. 启动 Electron 采集器 ───────────────────
if $START_COLLECTOR; then
  if [ -d "$ROOT/collector/node_modules" ]; then
    log_info "启动 Electron 采集器..."
    open_new_terminal "Electron Collector" "npm run dev" "$ROOT/collector"
  else
    log_warn "collector/node_modules 不存在，跳过（请先执行: make setup-collector）"
  fi
fi

# ── 完成 ──────────────────────────────────────
echo ""
log_ok "开发环境启动完成 🚀"
echo ""
echo "  FastAPI 文档  → http://localhost:8000/docs"
echo "  Vue 前端      → http://localhost:5173"
echo "  Milvus 健康   → http://localhost:9091/healthz"
echo ""
echo "  停止所有服务：./scripts/stop.sh"
echo "  查看状态：    make check"
echo ""
