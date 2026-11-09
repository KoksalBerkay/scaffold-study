#!/usr/bin/env bash
# Start Scaffold.
#   ./run.sh          web version at http://127.0.0.1:8765 (open it in any browser)
#   ./run.sh --app    desktop app (native window)
#   add --no-build to skip rebuilding the frontend
#   add --demo to open the demo semester (its own workspace-demo/ folder, separate from your data)
set -e
cd "$(dirname "$0")"
APP=0; BUILD=1
for a in "$@"; do
  case "$a" in
    --app) APP=1 ;;
    --no-build) BUILD=0 ;;
    --demo) export SCAFFOLD_WORKSPACE="$PWD/workspace-demo" ;;
  esac
done
if [ ! -d backend/.venv ]; then
  uv venv -p 3.12 backend/.venv
fi
uv pip install -q -p backend/.venv/bin/python -r backend/requirements.txt
if [ ! -d frontend/node_modules ]; then (cd frontend && npm install); fi
if [ "$BUILD" = 1 ] || [ ! -d frontend/dist ]; then scripts/build-frontend.sh; fi
[ -d demo-materials ] || backend/.venv/bin/python backend/make_demo_materials.py
cd backend
if [ "$APP" = 1 ]; then
  echo "Opening the Scaffold app…"
  # A copy of the interpreter named "Scaffold" makes macOS show "Scaffold" in the Dock instead of "python3.12".
  # (A symlink is not enough: macOS uses the real file name. The venv's pyvenv.cfg keeps the copy working.)
  REAL_PY="$(.venv/bin/python -c 'import os,sys; print(os.path.realpath(sys.executable))')"
  if [ ! -x .venv/bin/Scaffold ] || [ -L .venv/bin/Scaffold ] || ! cmp -s "$REAL_PY" .venv/bin/Scaffold; then
    rm -f .venv/bin/Scaffold && cp "$REAL_PY" .venv/bin/Scaffold && chmod +x .venv/bin/Scaffold
  fi
  # the interpreter finds its shared library relative to itself (@executable_path/../lib)
  for lib in "$(dirname "$REAL_PY")"/../lib/libpython*.dylib; do
    [ -e "$lib" ] && [ ! -e ".venv/lib/$(basename "$lib")" ] && ln -s "$lib" ".venv/lib/$(basename "$lib")"
  done
  exec .venv/bin/Scaffold desktop.py
fi
echo "Scaffold running at http://127.0.0.1:8765"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --timeout-graceful-shutdown 2
