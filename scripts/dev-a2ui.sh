#!/usr/bin/env bash
# Start the A2UI dev environment:
#   - A2UI Backend  (uvicorn, port 10201)
#   - A2UI Frontend (Vite + Electron, port 5174)

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── A2UI Backend ──────────────────────────────────────────────────────────────
echo "Starting A2UI backend on :10201..."
cd "$ROOT/a2ui-backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 10201 &
BACKEND_PID=$!

# ── A2UI Frontend + Electron ──────────────────────────────────────────────────
echo "Starting A2UI frontend + Electron..."
cd "$ROOT/a2ui-frontend"
npm run electron:dev &
FRONTEND_PID=$!

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo "Shutting down A2UI dev environment..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
}
trap cleanup INT TERM

echo ""
echo "A2UI dev environment running."
echo "  Backend:  http://localhost:10201"
echo "  Frontend: http://localhost:5174"
echo "Press Ctrl+C to stop."
wait
