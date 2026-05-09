#!/usr/bin/env bash
# Bring up Recetary for local development.
# Starts FastAPI (port 8000) and Next.js (port 3000) as background jobs.
# Press Ctrl+C to stop both.
#
# Usage from the repo root:  bash scripts/dev.sh

set -uo pipefail

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

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: Node.js is not installed or not in PATH." >&2
  exit 1
fi

# On Windows, calling `npm` can route through a shell shim that depends on
# how `bash` resolves in PATH. Prefer npm.cmd when available.
if command -v npm.cmd >/dev/null 2>&1; then
  NPM="npm.cmd"
else
  NPM="npm"
fi

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend dependencies..."
  (cd frontend && "$NPM" install)
fi

if [ ! -f frontend/node_modules/next/dist/bin/next ]; then
  echo "ERROR: Next.js binary not found at frontend/node_modules/next/dist/bin/next" >&2
  echo "Run: (cd frontend && $NPM install)" >&2
  exit 1
fi

# Next.js auto-falls back to another port when 3000 is occupied, which can be
# confusing in this combined launcher. Fail fast with a clear message instead.
if node -e "const net=require('net');const s=net.connect({host:'127.0.0.1',port:3000},()=>process.exit(0));s.on('error',()=>process.exit(1));setTimeout(()=>process.exit(1),400);" >/dev/null 2>&1; then
  echo "ERROR: Port 3000 is already in use. Stop the existing frontend process and retry." >&2
  echo "Hint (Windows): taskkill /PID <pid> /F" >&2
  echo "Hint (Linux/macOS): kill <pid>" >&2
  exit 1
fi

if [ ! -f data/recetary.db ]; then
  echo "Database not found — initializing..."
  "$PYTHON" -m recetary init
fi

# Read IMAGE_BACKEND from .env (same file the Python backend reads)
IMAGE_BACKEND="imagen"
if [ -f .env ]; then
  _val=$(grep -E '^\s*IMAGE_BACKEND\s*=' .env | head -1 | sed "s/^[^=]*=//;s/^[ \"']*//;s/[ \"']*$//" | tr '[:upper:]' '[:lower:]')
  if [ -n "$_val" ]; then
    IMAGE_BACKEND="$_val"
  fi
fi

cleanup() {
  if [ "${CLEANUP_DONE:-0}" -eq 1 ]; then
    return
  fi
  CLEANUP_DONE=1
  echo ""
  echo "Stopping servers..."
  kill $BACKEND_PID $FRONTEND_PID ${FLUX_PID:-} 2>/dev/null || true
  wait $BACKEND_PID $FRONTEND_PID ${FLUX_PID:-} 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT INT TERM

echo ""
echo "Starting backend  → http://localhost:8000  (docs at /docs)"
echo "Starting frontend → http://localhost:3000"
if [ "$IMAGE_BACKEND" = "local" ]; then
  echo "Starting FLUX server → http://localhost:8500"
fi
echo ""

"$PYTHON" -m uvicorn recetary.main:app --reload --app-dir backend --port 8000 &
BACKEND_PID=$!

(cd frontend && node node_modules/next/dist/bin/next dev) &
FRONTEND_PID=$!

if [ "$IMAGE_BACKEND" = "local" ]; then
  "$PYTHON" backend/flux_server.py &
  FLUX_PID=$!
fi

echo "Press Ctrl+C to stop both servers."

# Keep all processes supervised and report which one exited first.
while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID"
    BACKEND_STATUS=$?
    echo "Backend process exited with status $BACKEND_STATUS." >&2
    exit "$BACKEND_STATUS"
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID"
    FRONTEND_STATUS=$?
    echo "Frontend process exited with status $FRONTEND_STATUS." >&2
    exit "$FRONTEND_STATUS"
  fi

  if [ -n "${FLUX_PID:-}" ] && ! kill -0 "$FLUX_PID" 2>/dev/null; then
    wait "$FLUX_PID"
    FLUX_STATUS=$?
    echo "FLUX server exited with status $FLUX_STATUS." >&2
    exit "$FLUX_STATUS"
  fi

  sleep 1
done
