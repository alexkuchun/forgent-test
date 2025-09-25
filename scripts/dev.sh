#!/usr/bin/env bash
set -euo pipefail

RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; NC="\033[0m"

info()  { echo -e "${YELLOW}[dev]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC} $*"; }
fail()  { echo -e "${RED}[fail]${NC} $*"; }

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if command -v uv >/dev/null 2>&1; then
  UV_AVAILABLE=1
  info "uv detected; will use uv for Python env + run commands."
else
  UV_AVAILABLE=0
  info "uv not found; falling back to python -m venv and pip."
fi
 
start_api() {
  info "Starting API (FastAPI) ..."
  cd "$ROOT_DIR/services/api"
  if [ ! -d .venv ]; then
    info "Creating Python venv for API ..."
    if [ "$UV_AVAILABLE" -eq 1 ]; then
      uv venv .venv
    else
      python3 -m venv .venv
    fi
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  if [ "$UV_AVAILABLE" -eq 1 ]; then
    uv pip install -r requirements.txt >/dev/null
  else
    pip install -r requirements.txt >/dev/null
  fi
  UVICORN_PORT=${UVICORN_PORT:-8000}
  if [ "$UV_AVAILABLE" -eq 1 ]; then
    uv run uvicorn app.main:app --reload --port "$UVICORN_PORT"
  else
    uvicorn app.main:app --reload --port "$UVICORN_PORT"
  fi
}

start_worker() {
  info "Starting Worker (Dramatiq) ..."
  cd "$ROOT_DIR/services/worker"
  if [ ! -d .venv ]; then
    info "Creating Python venv for Worker ..."
    if [ "$UV_AVAILABLE" -eq 1 ]; then
      uv venv .venv
    else
      python3 -m venv .venv
    fi
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  if [ "$UV_AVAILABLE" -eq 1 ]; then
    uv pip install -r requirements.txt >/dev/null
  else
    pip install -r requirements.txt >/dev/null
  fi
  if [ -z "${REDIS_URL:-}" ]; then
    fail "REDIS_URL is not set. Export REDIS_URL (e.g., Upstash or local redis://localhost:6379/0)."
    exit 1
  fi
  if [ "$UV_AVAILABLE" -eq 1 ]; then
    uv run dramatiq worker.main --processes 1 --threads 1
  else
    dramatiq worker.main --processes 1 --threads 1
  fi
}

start_web() {
  info "Starting Web (Next.js) ..."
  cd "$ROOT_DIR/apps/web"
  npm install >/dev/null
  NEXT_PORT=${NEXT_PORT:-3000}
  npm run dev -- --port "$NEXT_PORT"
}

# Run all three in parallel and tear down cleanly on exit
start_api & API_PID=$!
start_worker & WORKER_PID=$!
start_web & WEB_PID=$!

trap 'info "Shutting down..."; kill $API_PID $WORKER_PID $WEB_PID 2>/dev/null || true' INT TERM EXIT

wait
