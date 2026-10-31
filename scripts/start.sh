#!/usr/bin/env bash
# Starts the API and the terminal on this Mac only. Press Ctrl+C to stop both.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH" NEXT_TELEMETRY_DISABLED=1

if [ ! -d frontend/.next ] || [ ! -d backend/.venv ]; then
  echo "Run ./scripts/install.sh first." >&2
  exit 1
fi

cleanup() { kill "${API_PID:-}" "${WEB_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

(cd backend && exec uv run python -m uvicorn atlas.main:app --host 127.0.0.1 --port 8000) &
API_PID=$!
API_READY=0
for _ in $(seq 1 40); do
  if curl -sf -o /dev/null http://127.0.0.1:8000/api/health; then
    API_READY=1
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    wait "$API_PID" || true
    echo "ATLAS API exited during startup. Check the error above." >&2
    exit 1
  fi
  sleep 1
done
if [ "$API_READY" -ne 1 ]; then
  echo "ATLAS API did not become ready at http://127.0.0.1:8000/api/health." >&2
  exit 1
fi
(cd frontend && exec npm run start) &
WEB_PID=$!

for _ in $(seq 1 40); do
  curl -sf -o /dev/null http://127.0.0.1:3000/api/health && break
  sleep 1
done
echo
echo "ATLAS is running at http://127.0.0.1:3000"
open http://127.0.0.1:3000 2>/dev/null || true
wait
