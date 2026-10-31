from fastapi.testclient import TestClient

from atlas.config import get_settings
from atlas.main import app


def test_public_mode_blocks_writes_and_personal_records():
    settings = get_settings()
    old = settings.public_read_only
    settings.public_read_only = True
    try:
        client = TestClient(app)
        for verb, path in [("post", "/api/portfolios"), ("delete", "/api/documents/1"), ("put", "/api/layouts/home"), ("post", "/api/quant/backtest")]:
            assert getattr(client, verb)(path).status_code == 403
        for path in ["/api/portfolios", "/api/documents", "/api/alerts", "/api/ai/report/AAPL"]:
            assert client.get(path).status_code == 403
        assert client.get("/openapi.json").status_code == 200
    finally:
        settings.public_read_only = old


def test_public_mode_refuses_unlisted_paths_and_settings():
    settings = get_settings()
    settings.public_read_only = True
    try:
        client = TestClient(app)
        for path in ["/api/settings", "/api/system/jobs", "/api/system/storage", "/api//portfolios", "/api/PORTFOLIOS", "/api/new-private-thing"]:
            assert client.get(path).status_code == 403, path
        assert client.get("/api/health").status_code == 200
    finally:
        settings.public_read_only = False


def test_public_mode_rate_limits_each_client():
    from atlas.services import public_mode

    public_mode._hits.clear()
    assert not any(public_mode.limited("a", 0.0) for _ in range(public_mode.LIMIT_PER_MINUTE))
    assert public_mode.limited("a", 1.0)
    assert not public_mode.limited("b", 1.0)
    assert not public_mode.limited("a", 61.0)
