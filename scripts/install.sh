#!/usr/bin/env bash
# Installs ATLAS on macOS (Apple Silicon). Safe to run more than once.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null; then
  echo "Installing uv, the Python package manager, from astral.sh"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
if ! command -v node >/dev/null; then
  echo "Node.js 20 or newer is required. Install it from https://nodejs.org, then run this script again." >&2
  exit 1
fi
[ -f .env ] || cp .env.example .env

echo "Installing the backend"
(cd backend && uv sync --python 3.12)
echo "Installing and building the frontend"
(cd frontend && npm ci --no-fund --no-audit && NEXT_TELEMETRY_DISABLED=1 npm run build)
echo
echo "Done. Start ATLAS with: ./scripts/start.sh"
