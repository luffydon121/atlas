import pytest
import respx
from fastapi.testclient import TestClient

from atlas.main import app
from atlas.services import alerts

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/"
SPARK = "https://query1.finance.yahoo.com/v7/finance/spark"


def chart(price=100.0):
    return {"chart": {"error": None, "result": [{"meta": {"symbol": "AAPL", "currency": "USD", "regularMarketPrice": price, "regularMarketTime": 1000000, "instrumentType": "EQUITY", "dataGranularity": "1d"},
                                                 "timestamp": [1, 900000], "indicators": {"quote": [{"open": [90, 95], "high": [91, 96], "low": [89, 94], "close": [90.0, 95.0], "volume": [10, 20]}]}}]}}


@pytest.fixture
def client():
    return TestClient(app, base_url="http://localhost")


def test_health_and_seed_watchlist(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/watchlists").json()[0]["name"] == "Core"


def test_foreign_host_header_is_rejected():
    assert TestClient(app, base_url="http://evil.example").get("/api/health").status_code == 400


def test_watchlist_crud(client):
    wid = client.post("/api/watchlists", json={"name": "Mine"}).json()["id"]
    assert client.post("/api/watchlists", json={"name": "Mine"}).status_code == 409
    assert client.post(f"/api/watchlists/{wid}/items", json={"symbol": "cba.ax"}).json()["symbols"] == ["CBA.AX"]
    assert client.post(f"/api/watchlists/{wid}/items", json={"symbol": "bad symbol!"}).status_code == 422
    client.delete(f"/api/watchlists/{wid}/items/CBA.AX")
    assert next(w for w in client.get("/api/watchlists").json() if w["id"] == wid)["symbols"] == []


@respx.mock
def test_quote_carries_provenance(client):
    respx.get(url__startswith=SPARK).respond(200, json={"spark": {"result": [{"symbol": "AAPL", "response": [{"meta": {"regularMarketPrice": 100.0, "chartPreviousClose": 90.0, "instrumentType": "EQUITY"}, "indicators": {"quote": [{"close": [90.0, 100.0]}]}}]}]}})
    body = client.get("/api/market/quotes?symbols=AAPL").json()
    q = body["data"]["quotes"][0]
    assert q["change_pct"] == pytest.approx((100 - 90) / 90 * 100)
    assert q["freshness"] == "delayed" and body["meta"]["source"] == ["yahoo"]


@respx.mock
def test_outage_returns_503_never_invented_data(client):
    respx.get(url__startswith=YAHOO).respond(500)
    res = client.get("/api/market/bars/ZZZZ")
    assert res.status_code == 503 and res.json()["freshness"] == "unavailable"


@respx.mock
def test_outage_falls_back_to_stored_bars_labelled_historical(client):
    respx.get(url__startswith=YAHOO).respond(200, json=chart())
    client.get("/api/market/bars/AAPL?range=1y&interval=1d")
    respx.get(url__startswith=YAHOO).respond(500)
    res = client.get("/api/market/bars/AAPL?range=5y&interval=1d").json()
    assert res["meta"]["stale"] and res["meta"]["freshness"] == "historical" and res["data"]["bars"]


def test_fred_reports_missing_key(client):
    body = client.get("/api/econ/series/us.gdp")
    assert body.status_code == 424 and "ATLAS_FRED_API_KEY" in body.json()["detail"]


def test_real_portfolio_refuses_paper_orders(client):
    pid = client.post("/api/portfolios", json={"name": "Real"}).json()["id"]
    assert client.post(f"/api/portfolios/{pid}/paper-order", json={"symbol": "AAPL", "side": "buy", "quantity": 1}).status_code == 422


@respx.mock
def test_paper_order_flow(client):
    respx.get(url__startswith=YAHOO).respond(200, json=chart())
    pid = client.post("/api/portfolios", json={"name": "Paper", "kind": "paper", "starting_cash": 1000, "base_currency": "USD"}).json()["id"]
    fill = client.post(f"/api/portfolios/{pid}/paper-order", json={"symbol": "AAPL", "side": "buy", "quantity": 1, "slippage_bps": 10}).json()
    assert fill["fill_price"] == pytest.approx(100.1)
    assert client.post(f"/api/portfolios/{pid}/paper-order", json={"symbol": "AAPL", "side": "buy", "quantity": 100}).status_code == 422
    assert client.post(f"/api/portfolios/{pid}/paper-order", json={"symbol": "AAPL", "side": "sell", "quantity": 5}).status_code == 422


def test_transaction_cannot_oversell(client):
    pid = client.post("/api/portfolios", json={"name": "L"}).json()["id"]
    res = client.post(f"/api/portfolios/{pid}/transactions", json={"ts": "2026-01-01T00:00:00", "symbol": "A", "side": "sell", "quantity": 1, "price": 1})
    assert res.status_code == 422


@respx.mock
async def test_price_alert_fires_once_per_crossing(client):
    aid = client.post("/api/alerts", json={"kind": "price_above", "target": "AAPL", "threshold": 99, "cooldown_minutes": 0}).json()["id"]
    respx.get(url__startswith=YAHOO).respond(200, json=chart(100))
    assert await alerts.evaluate_one(aid)
    assert not await alerts.evaluate_one(aid)
    assert client.get("/api/notifications").json()["unread"] == 1


def test_alert_needs_threshold(client):
    assert client.post("/api/alerts", json={"kind": "price_above", "target": "AAPL"}).status_code == 422


def test_settings_never_expose_secrets(client, monkeypatch):
    from atlas.config import get_settings

    monkeypatch.setattr(get_settings(), "fred_api_key", "super-secret")
    assert "super-secret" not in client.get("/api/settings").text


def test_layout_round_trip(client):
    client.put("/api/layouts/main", json={"symbol": "AAPL"})
    assert client.get("/api/layouts/main").json()["spec"] == {"symbol": "AAPL"}


def test_reference_layers_are_labelled(client):
    body = client.get("/api/map/layer/routes").json()
    assert body["meta"]["freshness"] == "reference" and "not vessel tracks" in body["meta"]["note"]


def test_upload_rejects_bad_type(client):
    assert client.post("/api/documents", files={"file": ("x.exe", b"MZ")}).status_code == 422


OLLAMA = "http://127.0.0.1:11434"


def _ollama(text: str):
    respx.get(f"{OLLAMA}/api/tags").respond(200, json={"models": [{"name": "fake:1"}]})
    respx.post(f"{OLLAMA}/api/chat").respond(200, json={"message": {"content": text}})
    respx.get(url__startswith=YAHOO).respond(200, json=chart(100))


@respx.mock
def test_assistant_keeps_a_grounded_model_answer(client):
    _ollama("WTI last traded at 100.00 [1].")
    body = client.post("/api/ai/ask", json={"question": "What is oil doing?"}).json()
    assert body["mode"] == "ollama" and body["warning"] is None and body["citations"]


@respx.mock
def test_assistant_discards_a_hallucinated_figure(client):
    _ollama("WTI will hit 487.25 next week [1].")
    body = client.post("/api/ai/ask", json={"question": "What is oil doing?"}).json()
    assert body["mode"] == "evidence" and "487.25" in body["warning"] and "487.25" not in body["answer"]


@respx.mock
def test_assistant_without_model_shows_evidence_and_admits_gaps(client):
    respx.get(f"{OLLAMA}/api/tags").mock(side_effect=__import__("httpx").ConnectError("off"))
    respx.get(url__startswith=YAHOO).respond(500)
    body = client.post("/api/ai/ask", json={"question": "What is oil doing?"}).json()
    assert body["mode"] == "evidence" and body["missing"] and "will not guess" in body["answer"]
