#!/usr/bin/env bash
set -euo pipefail
cd /app
python -m uvicorn atlas.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!
node frontend/node_modules/next/dist/bin/next start frontend --hostname 0.0.0.0 --port "${PORT:-10000}" &
web_pid=$!
trap 'kill "$api_pid" "$web_pid" 2>/dev/null || true' EXIT INT TERM
wait -n "$api_pid" "$web_pid"
