"""Rules for the public site. Anyone can read and calculate; saving needs the passcode."""

import hashlib
import hmac
import time
from collections import defaultdict, deque

READ_ONLY = "Saving needs the site passcode."
PRIVATE = "This needs the site passcode."
TOO_MANY = "Too many requests. Please wait a moment."
LIMIT_PER_MINUTE = 120
CALCULATORS = ("/api/quant/", "/api/company/dcf/run", "/api/ai/ask", "/api/satellite/change")
_hits: dict[str, deque] = defaultdict(deque)


def owner(cookie: str | None, passcode: str) -> bool:
    """True for the site owner, who unlocked with the passcode. Same token as frontend/lib/access.ts."""
    if not passcode or not cookie:
        return False
    return hmac.compare_digest(cookie, hashlib.sha256(f"atlas:{passcode}".encode()).hexdigest())


def client_id(headers, fallback: str) -> str:
    forwarded = headers.get("cf-connecting-ip") or headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or fallback


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
    if method in {"GET", "HEAD", "OPTIONS"}:
        if path == "/api/settings" or path.startswith("/api/system/"):
            return 403, PRIVATE
    elif not path.startswith(CALCULATORS):
        return 403, READ_ONLY
    if limited(client):
        return 429, TOO_MANY
    return None
