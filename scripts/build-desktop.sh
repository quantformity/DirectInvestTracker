#!/usr/bin/env bash
# Build the Qf Direct Invest Tracker desktop app (macOS DMG / Windows NSIS).
#
# Usage:
#   ./scripts/build-desktop.sh            # full rebuild (backend + frontend)
#   ./scripts/build-desktop.sh --frontend # skip PyInstaller, rebuild frontend only
#
# Prerequisites (first run only):
#   cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt pyinstaller
#   cd frontend && npm install

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

FRONTEND_ONLY=false
for arg in "$@"; do
  [[ "$arg" == "--frontend" ]] && FRONTEND_ONLY=true
done

echo "============================================================"
echo "  Qf Direct Invest Tracker — desktop build"
echo "============================================================"

# ── 1. Backend (PyInstaller) ─────────────────────────────────────
if [ "$FRONTEND_ONLY" = false ]; then
  echo ""
  echo ">>> [1/2] Building Python backend binary..."

  if [ ! -f "$BACKEND/.venv/bin/python" ] && [ ! -f "$BACKEND/.venv/Scripts/python.exe" ]; then
    echo "    ERROR: backend/.venv not found."
    echo "    Run once to set up:"
    echo "      cd backend"
    echo "      python -m venv .venv"
    echo "      .venv/bin/pip install -r requirements.txt pyinstaller"
    exit 1
  fi

  cd "$BACKEND"

  # Use the venv's pyinstaller
  PYINSTALLER=".venv/bin/pyinstaller"
  [ -f ".venv/Scripts/pyinstaller.exe" ] && PYINSTALLER=".venv/Scripts/pyinstaller.exe"

  rm -rf build dist
  "$PYINSTALLER" backend.spec

  echo "    Backend binary: dist/investments-backend/"
else
  echo ""
  echo ">>> [1/2] Skipping backend build (--frontend flag set)"
fi

# ── 1b. Ad-hoc sign the backend binary (macOS only) ─────────────
# Required on macOS Ventura/Sonoma: unsigned executables inside an app
# bundle are blocked even after xattr -cr unless they carry a signature.
if [[ "$(uname)" == "Darwin" ]]; then
  BIN="$BACKEND/dist/investments-backend/investments-backend"
  if [ -f "$BIN" ]; then
    echo ""
    echo ">>> [1b] Ad-hoc signing backend binary..."
    chmod +x "$BIN"
    codesign --force --deep --sign - "$BIN"
    echo "    Signed: $BIN"
  else
    echo "    WARNING: backend binary not found at $BIN — skipping sign step"
  fi
fi

# ── 2. Frontend (Electron + Vite) ───────────────────────────────
echo ""
echo ">>> [2/2] Building Electron app..."

cd "$FRONTEND"

if [ ! -d "node_modules" ]; then
  echo "    node_modules not found — running npm install..."
  npm install
fi

npm run electron:build

echo ""
echo "============================================================"
echo "  Build complete!"
echo ""
ls -lh "$FRONTEND/release/"*.dmg "$FRONTEND/release/"*.exe 2>/dev/null || \
  ls -lh "$FRONTEND/release/"
echo "============================================================"
