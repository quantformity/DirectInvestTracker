#!/usr/bin/env bash
# Start the full dev environment:
#   - FastAPI backend (uvicorn, port 8000)
#   - Vite frontend + Electron

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── Backend ──────────────────────────────────────────────────────────────────
echo "Starting backend..."
cd "$ROOT/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# ── Frontend + Electron ───────────────────────────────────────────────────────
echo "Starting frontend + Electron..."
cd "$ROOT/frontend"
npm run electron:dev &
FRONTEND_PID=$!

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
}
trap cleanup INT TERM

echo ""
echo "Dev environment running. Press Ctrl+C to stop."
wait
