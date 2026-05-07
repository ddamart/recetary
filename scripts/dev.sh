#!/usr/bin/env bash
# Bring up Recetary for local development.
# Starts FastAPI (port 8000) and Next.js (port 3000) as background jobs.
# Press Ctrl+C to stop both.
#
# Usage from the repo root:  bash scripts/dev.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Sanity checks
if [ ! -f .venv/Scripts/python.exe ] && [ ! -f .venv/bin/python ]; then
  echo "ERROR: Python venv missing. Run: python -m venv .venv && pip install -e backend[dev]" >&2
  exit 1
fi

# Detect venv python location (Windows Git Bash vs Linux/Mac)
if [ -f .venv/Scripts/python.exe ]; then
  PYTHON=".venv/Scripts/python.exe"
else
  PYTHON=".venv/bin/python"
fi

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend dependencies..."
  (cd frontend && npm install)
fi

if [ ! -f data/recetary.db ]; then
  echo "Database not found — initializing..."
  "$PYTHON" -m recetary init
fi

cleanup() {
  echo ""
  echo "Stopping servers..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT INT TERM

echo ""
echo "Starting backend  → http://localhost:8000  (docs at /docs)"
echo "Starting frontend → http://localhost:3000"
echo ""

"$PYTHON" -m uvicorn recetary.main:app --reload --app-dir backend --port 8000 &
BACKEND_PID=$!

(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo "Press Ctrl+C to stop both servers."
wait
