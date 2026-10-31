import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from atlas.core import exposure
from atlas.core.envelope import utcnow
from atlas.main import app
from atlas.services import eventstudy, impact


def client():
    return TestClient(app, base_url="http://localhost")


def hurricane(lat=27.0, lon=-90.0, knots=110):
    return impact.from_storms([{"name": "TEST", "class": "Hurricane", "intensity_kt": knots, "lat": lat, "lon": lon, "time": "2026-09-01T00:00:00Z", "url": "https://www.nhc.noaa.gov"}])[0]


def test_gulf_hurricane_finds_energy_exposure():
    e = hurricane()
    assert e["severity"] == "severe" and e["verification"] == "official"
    info = impact.describe(impact.rules_for(e))
    symbols = {a["symbol"] for a in info["assets"]}
    assert {"CL=F", "NG=F", "XOM", "VLO"} <= symbols
    assert "Refining" in info["industries"] and info["analogues"]
    assert "hypotheses" in info["statement"]
    assert any(s["kind"] == "oil" for s in impact.nearby(e["lat"], e["lon"]))


def test_storm_far_from_infrastructure_claims_no_exposure():
    assert impact.rules_for(hurricane(lat=15.0, lon=-40.0)) == []


@pytest.mark.parametrize(("knots", "level"), [(None, "watch"), (50, "watch"), (70, "elevated"), (100, "severe")])
def test_storm_severity_uses_wind_speed(knots, level):
    assert impact.storm_severity(knots) == level


def test_small_quakes_are_ignored_and_large_ones_use_magnitude():
    quake = {"id": "a", "title": "M 7.6", "mag": 7.6, "lat": 24.0, "lon": 121.5, "depth_km": 10, "time": "2026-01-01T00:00:00Z", "url": "https://usgs.gov", "tsunami": False}
    assert impact.from_quakes([{**quake, "mag": 4.9}]) == []
    e = impact.from_quakes([quake])[0]
    assert e["severity"] == "severe" and "malacca_taiwan" in [r.id for r in impact.rules_for(e)]


def test_chokepoint_disruption_links_to_rule():
    e = impact.from_chokepoints([{"id": "chokepoint6", "name": "Strait of Hormuz", "disrupted": True, "pct_vs_baseline": -89.0, "latest_date": "2026-10-25", "lat": 26.5, "lon": 56.2, "transits_7d_avg": 3.3, "baseline_avg": 28.8, "z": -0.9}])[0]
    assert e["verification"] == "derived" and e["severity"] == "severe"
    assert "hormuz" in [r.id for r in impact.rules_for(e)]


def test_unverified_news_stays_unverified():
    e = impact.from_news([{"title": "Report of attack", "url": "https://x.test", "lat": 26.0, "lon": 56.0, "place": "Hormuz", "time": "20261001T120000Z"}])[0]
    assert e["verification"] == "unverified" and e["severity"] == "info"


def test_events_persist_and_update_without_duplicates():
    impact.save([hurricane()])
    impact.save([hurricane(knots=70)])
    rows = impact.feed()
    assert len(rows) == 1 and rows[0]["severity"] == "elevated" and rows[0]["exposed"]


def test_event_api_contract_has_no_invented_probability(monkeypatch):
    async def done():
        return {"failed": ["GDELT"]}

    monkeypatch.setattr(impact, "refresh", done)

    async def none(_s, _o):
        return []

    monkeypatch.setattr(impact, "since", none)
    impact.save([hurricane()])
    c = client()
    body = c.get("/api/impact/events").json()
    assert body["data"]["unavailable"] == ["GDELT"]
    detail = c.get(f"/api/impact/events/{body['data']['events'][0]['id']}").json()["data"]
    assert detail["evidence"][0]["url"] and detail["rules"][0]["uncertainty"]
    assert "probability" not in str(detail).lower()
    assert c.get("/api/impact/events/999").status_code == 404


def test_scenario_is_labelled_hypothetical():
    body = client().get("/api/impact/scenario?zone=gulf_of_mexico").json()["data"]
    assert body["scenario"] and "hypothetical" in body["statement"] and body["assets"]
    assert client().get("/api/impact/scenario?zone=nowhere").status_code == 404


def test_graph_search_connects_company_to_themes():
    body = client().get("/api/graph?q=valero").json()["data"]
    assert body == {"nodes": [], "edges": []}
    body = client().get("/api/graph?q=VLO").json()["data"]
    assert {n["kind"] for n in body["nodes"]} >= {"company", "theme"}


def test_every_rule_has_mechanism_uncertainty_and_basis():
    for r in exposure.RULES:
        assert r.mechanism and r.uncertainty and r.basis, r.id


def test_history_dates_are_valid_and_linked_to_real_rules():
    for day, _title, rules, url in exposure.HISTORY:
        pd.Timestamp(day)
        assert url.startswith("https://")
        assert set(rules) <= set(exposure.RULES_BY_ID)


def walk(n=800, seed=1):
    rng = np.random.default_rng(seed)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n))), index=pd.bdate_range("2015-01-01", periods=n))


def test_event_study_finds_an_injected_jump():
    px = walk()
    day = px.index[500]
    px.iloc[500:] *= 1.10
    out = eventstudy.study(px, [day.strftime("%Y-%m-%d")], walk(seed=2), before=1, after=5)
    assert out["n"] == 1 and out["mean_car"] == pytest.approx(0.0953, abs=0.04)
    assert out["t_stat"] is None


def test_event_study_rolls_weekend_to_next_session():
    px = walk()
    out = eventstudy.study(px, ["2016-01-02"], before=1, after=3)
    assert out["events"][0]["date"] == "2016-01-04"


def test_event_study_skips_dates_without_history():
    out = eventstudy.study(walk(), ["1990-01-01", "2035-01-01"])
    assert out["n"] == 0 and out["mean_car"] is None and len(out["skipped"]) == 2


def test_estimation_window_excludes_the_event():
    px = walk()
    bench = walk(seed=2)
    a = eventstudy.study(px, ["2016-06-01"], bench)["events"][0]["beta"]
    changed = px.copy()
    changed.iloc[changed.index.searchsorted(pd.Timestamp("2016-06-01")):] *= 2
    assert eventstudy.study(changed, ["2016-06-01"], bench)["events"][0]["beta"] == pytest.approx(a)


def test_t_stat_needs_three_events():
    px = walk()
    days = [px.index[i].strftime("%Y-%m-%d") for i in (300, 500, 700)]
    assert eventstudy.study(px, days)["t_stat"] is not None
    assert eventstudy.study(px, days[:2])["t_stat"] is None


def test_benjamini_hochberg():
    assert eventstudy.benjamini_hochberg([0.001, 0.5, None, 0.04], q=0.1) == [True, False, False, True]
    assert eventstudy.benjamini_hochberg([0.9, 0.8]) == [False, False]


async def test_since_skips_old_events():
    from datetime import timedelta

    assert await impact.since(["AAPL"], utcnow() - timedelta(days=90)) == []




def test_public_demo_allows_impact_reads():
    from atlas.services import public_mode

    assert public_mode.check("GET", "/api/impact/scenario", "x") is None
    assert public_mode.check("POST", "/api/impact/events", "y")[0] == 403


def test_prescribed_burns_are_not_disasters():
    base = {"lat": 29.8, "lon": -94.0, "time": "2026-10-01T00:00:00Z", "url": "https://eonet.test", "category": "Wildfires"}
    assert impact.from_natural([{**base, "id": "a", "title": "Prescribed Fire Rx Polk 9275, Polk, Texas"}]) == []
    fire = impact.from_natural([{**base, "id": "b", "title": "Big Thicket Wildfire"}])[0]
    assert fire["category"] == "wildfire" and impact.rules_for(fire) == []


async def test_off_season_crops_raise_no_frost_alarm(monkeypatch):
    from datetime import date as real_date

    from atlas.connectors import world

    class Fake:
        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    days = [f"{y}-{m:02d}-{d:02d}" for y in range(2014, 2027) for m in range(1, 13) for d in range(1, 29)]

    class Fetch:
        async def get(self, *_a, **_k):
            return Fake({"daily": {"time": days, "precipitation_sum": [2.0] * len(days), "temperature_2m_mean": [5.0] * len(days)}})

    async def cold(_lat, _lon):
        return {"daily": {"temperature_2m_min": [-5.0] * 7, "temperature_2m_max": [0.0] * 7}}

    class November(real_date):
        @classmethod
        def today(cls):
            return real_date(2026, 11, 1)

    monkeypatch.setattr(world, "get_fetcher", lambda: Fetch())
    monkeypatch.setattr(world, "forecast", cold)
    monkeypatch.setattr(world, "date", November)
    row = await world.region_risk("corn", ("Iowa, USA", 42.0, -93.5, 0.3))
    assert not row["in_season"] and row["forecast"]["frost_days"] == 0 and row["risk"]["level"] == "normal"
    assert impact.from_weather({"corn": {"regions": [row]}}) == []
