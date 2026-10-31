"""Rules for the public demo. Everything is refused unless it is explicitly allowed."""

import time
from collections import defaultdict, deque

READ_ONLY = "This public demo is read-only. Saving, uploads and interactive calculations are disabled."
PRIVATE = "Personal workspace features are unavailable in the public demo."
TOO_MANY = "Too many requests. Please wait a moment."
LIMIT_PER_MINUTE = 120
ALLOWED = ("/api/health", "/api/search", "/api/market/", "/api/company", "/api/econ/", "/api/news", "/api/today", "/api/calendar", "/api/map/", "/api/weather/", "/api/hazards/", "/api/aviation/", "/api/shipping/", "/api/trade/",
           "/api/geo/", "/api/crypto/", "/api/alt/", "/api/sources", "/api/quality", "/api/impact/", "/api/graph", "/api/briefings/latest")
_hits: dict[str, deque] = defaultdict(deque)


def client_id(headers, fallback: str) -> str:
    forwarded = headers.get("cf-connecting-ip") or headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or fallback


def _allowed(path: str) -> bool:
    return any(path == p or path.startswith(p if p.endswith("/") else p + "/") for p in ALLOWED)


def limited(client: str, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    hits = _hits[client]
    while hits and hits[0] < now - 60:
        hits.popleft()
    if len(hits) >= LIMIT_PER_MINUTE:
        return True
    hits.append(now)
    if len(_hits) > 10_000:
        _hits.clear()
    return False


def check(method: str, path: str, client: str) -> tuple[int, str] | None:
    if not path.startswith("/api"):
        return None
    if method not in {"GET", "HEAD", "OPTIONS"}:
        return 403, READ_ONLY
    if not _allowed(path):
        return 403, PRIVATE
    if limited(client):
        return 429, TOO_MANY
    return None
