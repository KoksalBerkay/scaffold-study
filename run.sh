#!/usr/bin/env bash
# Start Scaffold.
#   ./run.sh          web version at http://127.0.0.1:8765 (open it in any browser)
#   ./run.sh --app    desktop app (native window)
#   add --no-build to skip rebuilding the frontend
set -e
cd "$(dirname "$0")"
APP=0; BUILD=1
for a in "$@"; do
  case "$a" in
    --app) APP=1 ;;
    --no-build) BUILD=0 ;;
  esac
done
if [ ! -d backend/.venv ]; then
  uv venv -p 3.12 backend/.venv
fi
uv pip install -q -p backend/.venv/bin/python -r backend/requirements.txt
if [ ! -d frontend/node_modules ]; then (cd frontend && npm install); fi
if [ "$BUILD" = 1 ] || [ ! -d frontend/dist ]; then (cd frontend && npx vite build >/dev/null); fi
[ -d demo-materials ] || backend/.venv/bin/python backend/make_demo_materials.py
cd backend
if [ "$APP" = 1 ]; then
  echo "Opening the Scaffold app…"
  exec .venv/bin/python desktop.py
fi
echo "Scaffold running at http://127.0.0.1:8765"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --timeout-graceful-shutdown 2
