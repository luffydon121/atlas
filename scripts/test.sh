#!/usr/bin/env bash
# Backend unit tests and lint, then frontend type check and lint.
# Browser tests need the app running: ./scripts/start.sh, then `cd frontend && npx playwright test`.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
(cd backend && uv run ruff check . && uv run python -m pytest -q)
(cd frontend && npx tsc --noEmit && npx eslint .)
