#!/usr/bin/env bash
# Restart the backend on :8765 only when no AI job is running (dev helper). Open windows reconnect by themselves.
cd "$(dirname "$0")/../backend"
LOG="${1:-/tmp/scaffold-server.log}"
for i in $(seq 1 600); do
  R=$(curl -s -m 3 http://127.0.0.1:8765/api/jobs 2>/dev/null)
  if [ -z "$R" ] || echo "$R" | grep -q '"running":\[\]'; then break; fi
  [ "$i" = 1 ] && echo "waiting for running jobs to finish: $R"
  sleep 2
done
pkill -f "uvicorn app.main:app"
# also free the port from anything else still holding it (e.g. an orphaned reload worker)
for pid in $(lsof -tiTCP:8765 -sTCP:LISTEN 2>/dev/null); do kill "$pid" 2>/dev/null; done
for i in $(seq 1 20); do lsof -tiTCP:8765 -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 0.25; done
nohup .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --timeout-graceful-shutdown 2 > "$LOG" 2>&1 &
for i in $(seq 1 40); do curl -s -m 1 -o /dev/null http://127.0.0.1:8765/api/version && break; sleep 0.25; done
echo "server restarted"
