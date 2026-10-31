from datetime import timedelta

import httpx
import pytest
import respx

from atlas.core.envelope import utcnow
from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import Fetcher
from atlas.db import CacheEntry, SourceStatus, session_scope

URL = "https://example.test/data"


def make() -> Fetcher:
    return Fetcher(backoff_base=0, max_attempts=3)


@respx.mock
async def test_caches_until_expiry():
    route = respx.get(URL).respond(200, text="one")
    f = make()
    assert (await f.get("usgs", URL, ttl=60)).body == "one"
    second = await f.get("usgs", URL, ttl=60)
    assert second.cached and route.call_count == 1


@respx.mock
async def test_retries_transient_failure():
    route = respx.get(URL).mock(side_effect=[httpx.Response(503), httpx.Response(200, text="ok")])
    assert (await make().get("usgs", URL)).body == "ok"
    assert route.call_count == 2


@respx.mock
async def test_does_not_retry_permanent_failure():
    route = respx.get(URL).respond(403)
    with pytest.raises(SourceUnavailable):
        await make().get("usgs", URL)
    assert route.call_count == 1


@respx.mock
async def test_serves_stale_cache_when_source_fails():
    respx.get(URL).respond(200, text="saved")
    f = make()
    await f.get("usgs", URL, ttl=60)
    with session_scope() as db:
        for row in db.query(CacheEntry).all():
            row.expires_at = utcnow() - timedelta(seconds=1)
    respx.get(URL).respond(500)
    got = await f.get("usgs", URL, ttl=60)
    assert got.stale and got.body == "saved"
    with session_scope() as db:
        assert db.get(SourceStatus, "usgs").failure_count == 1


@respx.mock
async def test_invalid_body_is_never_cached():
    respx.get(URL).respond(200, text='{"error": 1}')
    f = make()
    with pytest.raises(SourceUnavailable):
        await f.get("usgs", URL, validate=lambda b: "error" not in b)
    with session_scope() as db:
        assert db.query(CacheEntry).count() == 0


@respx.mock
async def test_error_inside_a_200_is_retried():
    route = respx.get(URL).mock(side_effect=[httpx.Response(200, text='{"error": 1}'), httpx.Response(200, text="good")])
    assert (await make().get("usgs", URL, validate=lambda b: "error" not in b)).body == "good"
    assert route.call_count == 2


@respx.mock
async def test_reports_when_nothing_is_available():
    respx.get(URL).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(SourceUnavailable):
        await make().get("usgs", URL)


@respx.mock
async def test_background_refresh_answers_instantly_then_updates():
    import asyncio

    respx.get(URL).respond(200, text="old")
    f = make()
    await f.get("yahoo", URL, ttl=60)
    with session_scope() as db:
        for row in db.query(CacheEntry).all():
            row.expires_at = utcnow() - timedelta(seconds=1)
    respx.get(URL).respond(200, text="new")
    assert (await f.get("yahoo", URL, ttl=60)).body == "old"
    await asyncio.gather(*f._refreshing.values())
    assert (await f.get("yahoo", URL, ttl=60)).body == "new"


@respx.mock
async def test_binary_body_round_trips():
    import base64

    respx.get(URL).respond(200, content=b"\xd0\xcf\x11")
    assert base64.b64decode((await make().get("eia", URL, binary=True)).body) == b"\xd0\xcf\x11"


@respx.mock
async def test_busy_database_does_not_fail_a_fetch(monkeypatch):
    from sqlalchemy.exc import OperationalError

    from atlas.core import fetcher as module

    respx.get(URL).respond(200, text="ok")

    class Busy:
        def __enter__(self):
            raise OperationalError("write", {}, Exception("database is locked"))

        def __exit__(self, *_):
            return False

    real = module.session_scope
    calls = []

    def flaky():
        calls.append(1)
        return real() if len(calls) == 1 else Busy()

    monkeypatch.setattr(module, "session_scope", flaky)
    assert (await make().get("usgs", URL)).body == "ok"
