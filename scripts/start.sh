#!/usr/bin/env bash
# Starts ATLAS on this Mac only. Press Ctrl+C to stop.
# Add --lan to also reach it from phones and tablets on the same Wi-Fi, protected by a passcode.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH" NEXT_TELEMETRY_DISABLED=1

if [ ! -d frontend/.next ] || [ ! -d backend/.venv ]; then
  echo "Run ./scripts/install.sh first." >&2
  exit 1
fi

LAN=0
[ "${1:-}" = "--lan" ] && LAN=1

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
if [ "$LAN" -eq 1 ]; then
  # Only the web app is exposed. The API stays on this Mac and is reached through the web app.
  [ -f .env ] && PASSCODE_FROM_ENV=$(grep -E '^ATLAS_PASSCODE=' .env | cut -d= -f2- || true)
  export ATLAS_PASSCODE="${PASSCODE_FROM_ENV:-$(LC_ALL=C tr -dc 'a-z2-9' </dev/urandom | head -c 8)}"
  (cd frontend && exec npx next start -H 0.0.0.0 -p 3000) &
else
  (cd frontend && exec npm run start) &
fi
WEB_PID=$!

for _ in $(seq 1 40); do
  curl -s -o /dev/null http://127.0.0.1:3000/unlock && break
  sleep 1
done
echo
echo "ATLAS is running at http://127.0.0.1:3000"
if [ "$LAN" -eq 1 ]; then
  IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "this-mac-ip")
  echo "On a phone or tablet on the same Wi-Fi, open http://$IP:3000"
  echo "Passcode: $ATLAS_PASSCODE"
  echo "Traffic on your Wi-Fi is not encrypted. Use this on networks you trust."
fi
open http://127.0.0.1:3000 2>/dev/null || true
wait
