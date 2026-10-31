"""The one gateway to the network: rate limits, retries, caching, health and stale fallback."""

import asyncio
import base64
import email.utils
import hashlib
import json
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError

from atlas.core.envelope import utcnow
from atlas.core.errors import SourceUnavailable
from atlas.core.registry import REGISTRY
from atlas.db import CacheEntry, SourceStatus, session_scope

log = logging.getLogger("atlas.fetcher")

DEFAULT_UA = "ATLAS-local-terminal/0.1"
RETRYABLE = {429, 500, 502, 503, 504}
# These sources answer from the last copy at once and update in the background.
BACKGROUND_REFRESH = {"yahoo", "rss", "coingecko", "mempool", "defillama", "worldbank", "rba", "ecb", "eurostat", "bls", "treasury", "abs", "oecd", "eia", "portwatch"}


@dataclass
class Fetched:
    body: str
    fetched_at: datetime
    stale: bool = False
    cached: bool = False

    def json(self) -> Any:
        return json.loads(self.body)


class _Pacer:
    """Spaces requests to one provider by at least `interval` seconds."""

    def __init__(self, interval: float):
        self.interval = interval
        self.lock = asyncio.Lock()
        self.last = 0.0

    async def wait(self) -> None:
        async with self.lock:
            delay = self.last + self.interval - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self.last = time.monotonic()


def _record(source_id: str, ok: bool, error: str | None = None) -> None:
    """Health records are best effort. A busy database must never fail a data request."""
    now = utcnow()
    try:
        with session_scope() as db:
            row = db.get(SourceStatus, source_id)
            if row is None:
                row = SourceStatus(source_id=source_id, success_count=0, failure_count=0)
                db.add(row)
            row.last_attempt = now
            if ok:
                row.last_success, row.last_error = now, None
                row.success_count += 1
            else:
                row.last_error = (error or "unknown error")[:500]
                row.failure_count += 1
    except OperationalError as exc:
        log.warning("Could not record health for %s: %s", source_id, exc)


def _store(key: str, source_id: str, body: str, ttl: int) -> datetime:
    """A busy database means the next reader refetches, which is better than failing this one."""
    now = utcnow()
    try:
        with session_scope() as db:
            db.merge(CacheEntry(key=key, source_id=source_id, body=body, fetched_at=now, expires_at=now + timedelta(seconds=ttl)))
    except OperationalError as exc:
        log.warning("Could not cache %s: %s", source_id, exc)
    return now


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    if value.isdigit():
        return float(value)
    parsed = email.utils.parsedate_to_datetime(value)
    return max(0.0, parsed.timestamp() - time.time()) if parsed else None


class Fetcher:
    def __init__(self, client: httpx.AsyncClient | None = None, backoff_base: float = 0.8, max_attempts: int = 3):
        self.client = client or httpx.AsyncClient(timeout=25, follow_redirects=True, http2=False, limits=httpx.Limits(max_keepalive_connections=20))
        self.backoff_base = backoff_base
        self.max_attempts = max_attempts
        self._pacers: dict[str, _Pacer] = {}
        self._keylocks: dict[str, asyncio.Lock] = {}
        self._refreshing: dict[str, asyncio.Task] = {}

    def _pacer(self, source_id: str) -> _Pacer:
        if source_id not in self._pacers:
            spec = REGISTRY.get(source_id)
            self._pacers[source_id] = _Pacer(spec.min_interval_s if spec else 0.5)
        return self._pacers[source_id]

    @staticmethod
    def _key(method: str, url: str, params: dict | None, body: Any) -> str:
        raw = json.dumps([method, url, sorted((params or {}).items()), body], default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(
        self,
        source_id: str,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        ttl: int = 3600,
        method: str = "GET",
        json_body: Any = None,
        attempts: int | None = None,
        validate: Callable[[str], bool] | None = None,
        binary: bool = False,
        timeout: float | None = None,
    ) -> Fetched:
        key = self._key(method, url, params, json_body)
        lock = self._keylocks.setdefault(key, asyncio.Lock())
        async with lock:
            with session_scope() as db:
                entry = db.get(CacheEntry, key)
                cached = (entry.body, entry.fetched_at, entry.expires_at) if entry else None
            now = utcnow()
            if cached and cached[2] > now:
                return Fetched(cached[0], cached[1], cached=True)
            if cached and source_id in BACKGROUND_REFRESH and now - cached[2] < timedelta(seconds=ttl * 5):
                # Answer now with the last copy, then update it for the next reader.
                if key not in self._refreshing:
                    self._refreshing[key] = asyncio.create_task(self._refresh(key, source_id, ttl, method, url, params, headers, json_body, attempts, validate, binary, timeout))
                return Fetched(cached[0], cached[1], cached=True)
            try:
                body = await self._request(source_id, method, url, params, headers, json_body, attempts or self.max_attempts, validate, binary, timeout)
            except SourceUnavailable as exc:
                _record(source_id, False, exc.reason)
                if cached:
                    log.warning("%s failed, serving stale cache: %s", source_id, exc.reason)
                    return Fetched(cached[0], cached[1], stale=True, cached=True)
                raise
            now = _store(key, source_id, body, ttl)
            _record(source_id, True)
            return Fetched(body, now)

    async def _refresh(self, key, source_id, ttl, method, url, params, headers, json_body, attempts, validate, binary, timeout=None) -> None:
        try:
            body = await self._request(source_id, method, url, params, headers, json_body, attempts or self.max_attempts, validate, binary, timeout)
        except SourceUnavailable as exc:
            _record(source_id, False, exc.reason)
        else:
            _store(key, source_id, body, ttl)
            _record(source_id, True)
        finally:
            self._refreshing.pop(key, None)

    async def _request(self, source_id, method, url, params, headers, json_body, attempts, validate=None, binary=False, timeout=None) -> str:
        merged = {"User-Agent": DEFAULT_UA, **(headers or {})}
        reason = "no attempt made"
        for attempt in range(attempts):
            await self._pacer(source_id).wait()
            wait = self.backoff_base * 2**attempt + random.uniform(0, 0.3)
            try:
                response = await self.client.request(method, url, params=params, headers=merged, json=json_body, timeout=timeout or httpx.USE_CLIENT_DEFAULT)
            except httpx.HTTPError as exc:
                reason = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code < 400:
                    # Some services report errors inside a 200. Those are retried and never cached.
                    if binary:
                        return base64.b64encode(response.content).decode()
                    if validate is None or validate(response.text):
                        return response.text
                    reason = f"Invalid response: {response.text[:160]}"
                else:
                    reason = f"HTTP {response.status_code}"
                    if response.status_code not in RETRYABLE:
                        break
                    wait = max(wait, min(_retry_after(response) or 0, 30))
            if attempt + 1 < attempts:
                await asyncio.sleep(wait)
        raise SourceUnavailable(source_id, reason)

    async def close(self) -> None:
        await self.client.aclose()


_fetcher: Fetcher | None = None


def get_fetcher() -> Fetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = Fetcher()
    return _fetcher


def set_fetcher(fetcher: Fetcher | None) -> None:
    global _fetcher
    _fetcher = fetcher


def prune_cache(max_age_days: int = 14) -> int:
    with session_scope() as db:
        cutoff = utcnow() - timedelta(days=max_age_days)
        return db.execute(delete(CacheEntry).where(CacheEntry.expires_at < cutoff)).rowcount
