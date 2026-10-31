from fastapi.testclient import TestClient
from atlas.main import app
from atlas.config import get_settings

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
