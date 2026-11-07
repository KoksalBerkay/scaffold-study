#!/usr/bin/env bash
# Start Scaffold: builds the frontend if needed and serves everything on http://127.0.0.1:8765
set -e
cd "$(dirname "$0")"
if [ ! -d backend/.venv ]; then
  uv venv -p 3.12 backend/.venv
  uv pip install -p backend/.venv/bin/python -r backend/requirements.txt
fi
if [ ! -d frontend/node_modules ]; then (cd frontend && npm install); fi
if [ "$1" != "--no-build" ]; then (cd frontend && npx vite build >/dev/null); fi
[ -d demo-materials ] || backend/.venv/bin/python backend/make_demo_materials.py
echo "Scaffold running at http://127.0.0.1:8765"
cd backend && exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --timeout-graceful-shutdown 2
