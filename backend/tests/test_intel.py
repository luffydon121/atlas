import asyncio

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from atlas.connectors import holdings, trade
from atlas.main import app
from atlas.services import eventstudy, quant, reports, satellite_monitor


def client():
    return TestClient(app, base_url="http://localhost")


XML = """<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip><value>1000</value><shrsOrPrnAmt><sshPrnamt>10</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip><value>500</value><shrsOrPrnAmt><sshPrnamt>5</sshPrnamt></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>CHEVRON</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>166764100</cusip><value>2000</value><shrsOrPrnAmt><sshPrnamt>20</sshPrnamt></shrsOrPrnAmt><putCall>Put</putCall></infoTable>
</informationTable>"""


def test_13f_rows_combine_same_security_and_keep_puts_separate():
    rows = holdings.parse_table(XML)
    assert rows[0]["put_call"] == "Put"
    assert next(r for r in rows if r["cusip"] == "037833100")["shares"] == 15


def test_13f_changes_use_shares_not_value():
    a = [{"cusip": "a", "put_call": None, "shares": 10, "value": 100, "issuer": "A"}, {"cusip": "b", "put_call": None, "shares": 5, "value": 50, "issuer": "B"}, {"cusip": "c", "put_call": None, "shares": 1, "value": 1, "issuer": "C"}]
    b = [{"cusip": "a", "put_call": None, "shares": 10, "value": 200, "issuer": "A"}, {"cusip": "b", "put_call": None, "shares": 8, "value": 80, "issuer": "B"}, {"cusip": "d", "put_call": None, "shares": 2, "value": 2, "issuer": "D"}]
    c = holdings.changes(a, b)
    assert [r["cusip"] for r in c["increased"]] == ["b"] and c["increased"][0]["change"] == 3
    assert [r["cusip"] for r in c["added"]] == ["d"] and [r["cusip"] for r in c["removed"]] == ["c"]
    assert c["reduced"] == []


def test_13f_list_comes_from_submissions():
    sub = {"cik": "0001067983", "filings": {"recent": {"form": ["4", "13F-HR"], "filingDate": ["2026-08-01", "2026-08-14"], "reportDate": ["", "2026-06-30"], "accessionNumber": ["1", "0000950123-26-000001"]}}}
    assert holdings.filings(sub)[0]["period"] == "2026-06-30"


async def test_13f_table_needs_a_declared_contact():
    from atlas.core.errors import SourceNotConfigured

    with pytest.raises(SourceNotConfigured):
        await holdings.table(1067983, "0000950123-26-000001")


def test_port_proxy_summary():
    rows = [{"date": (pd.Timestamp("2026-01-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%d"), "portcalls": 100 if i < 93 else 50, "portcalls_container": 10, "portcalls_tanker": 5, "import": 1, "export": 2} for i in range(100)]
    s = trade.summarise_port(rows)
    assert s["calls_7d_avg"] == 50 and s["pct_vs_baseline"] == -50


def test_bis_summary_finds_last_change():
    assert trade.summarise_rate([("2026-01-01", 4.0), ("2026-02-01", 3.75), ("2026-03-01", 3.75)]) == {"rate": 3.75, "as_of": "2026-03-01", "last_change_date": "2026-02-01", "last_change": -0.25}


def test_bea_schedule_parser():
    page = 'Year 2026 <div class="release-date">November 4</div> <small>8:30 AM</small> </td><td>x</td><td class="release-title views-field" headers="y">U.S. International Trade in Goods and Services, September 2026 </td>'
    assert trade.parse_bea(page)[0]["date"] == "2026-11-04"


def test_polygon_mask_and_bbox():
    poly = [[0.0, 0.0], [0.1, 0.0], [0.0, 0.1]]
    assert satellite_monitor.bbox_of(poly) == [0.0, 0.0, 0.1, 0.1]
    mask = satellite_monitor.polygon_mask(poly, [0, 0, 0.1, 0.1], (100, 100))
    assert 0.4 < mask.mean() < 0.6 and mask[99, 1] and not mask[1, 99]


def test_masked_values_outside_shape_are_empty():
    out = satellite_monitor.masked(np.ones((10, 10), dtype="float32"), [[0.0, 0.0], [0.1, 0.0], [0.0, 0.1]], [0, 0, 0.1, 0.1])
    assert np.isnan(out).any() and np.nanmean(out) == 1


def test_same_season_picks_clearest_scene_a_year_earlier():
    scenes = [{"id": "near", "acquired_at": "2025-10-20T00:00:00Z", "cloud_cover": 8.0}, {"id": "clear", "acquired_at": "2025-10-25T00:00:00Z", "cloud_cover": 1.0}, {"id": "summer", "acquired_at": "2025-07-01T00:00:00Z", "cloud_cover": 0.0}]
    assert satellite_monitor.same_season("2026-10-22T00:00:00Z", scenes)["id"] == "clear"
    assert satellite_monitor.same_season("2026-01-22T00:00:00Z", scenes) is None


@pytest.mark.parametrize("poly", [[[0, 0], [1, 1]], [[0, 0], [5, 0], [0, 5]], [[200, 0], [201, 0], [200, 1]]])
def test_bad_polygons_are_refused(poly):
    with pytest.raises(ValueError):
        satellite_monitor.check_polygon(poly)


def test_area_crud():
    c = client()
    body = {"name": "Pit", "tracker": "mine", "polygon": [[119.6, -23.4], [119.7, -23.4], [119.7, -23.3]]}
    made = c.post("/api/satellite/areas", json=body)
    assert made.status_code == 201 and made.json()["index"] == "bsi"
    assert c.post("/api/satellite/areas", json={**body, "tracker": "cars"}).status_code == 422
    assert "Pit" in c.get("/api/satellite/areas").text
    assert "No observations yet" in c.get(f"/api/satellite/areas/{made.json()['id']}/report").text
    assert c.delete(f"/api/satellite/areas/{made.json()['id']}").status_code == 204


def test_sentinel_trackers_exclude_vehicle_counting():
    assert not {"retail", "vehicles", "oil_tanks"} & set(satellite_monitor.TRACKERS)


def walk(n=2000, seed=1, start="2008-01-01"):
    rng = np.random.default_rng(seed)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n))), index=pd.bdate_range(start, periods=n))


def test_stress_reports_missing_history_instead_of_guessing():
    rows = quant.stress_test({"OLD": walk(), "NEW": walk(start="2021-01-01", n=800)}, {"OLD": 0.5, "NEW": 0.5})
    gfc = rows[0]
    assert gfc["missing"] == ["NEW"] and gfc["weight_covered"] == 0.5 and gfc["portfolio"] == pytest.approx(gfc["moves"]["OLD"])


def test_regimes_label_current_state():
    out = quant.vol_regimes(walk())
    assert out["current"] in {"calm", "normal", "stressed"} and sum(r["days"] for r in out["regimes"].values()) > 1900


def test_rolling_correlation_of_identical_series_is_one():
    px = walk()
    assert quant.rolling_correlation(px, px)[-1]["value"] == pytest.approx(1)


def test_compare_gives_p_values_for_correction():
    rows = quant.compare_strategies(walk())
    assert {r["strategy"] for r in rows} == set(quant.STRATEGIES)
    assert len(eventstudy.benjamini_hochberg([r["p_value"] for r in rows])) == 4


def test_multi_asset_book_averages_legs():
    out = quant.multi_asset({"A": walk(seed=1), "B": walk(seed=2)}, "buy_hold", 0)
    assert out["assets"] == ["A", "B"] and "sharpe" in out["metrics"]


async def test_briefing_states_gaps_and_escapes_html(monkeypatch):
    from atlas.connectors import yahoo
    from atlas.core.errors import SourceUnavailable

    async def down(_s):
        raise SourceUnavailable("yahoo", "down")

    monkeypatch.setattr(yahoo, "quotes", down)
    made = await reports.generate("daily")
    assert "Market prices" in made["markdown"] and "Period covered" in made["markdown"]
    page = reports.to_html("# T\n- <script>alert(1)</script>", "T")
    assert "<script>" not in page and "&lt;script&gt;" in page


async def test_asset_briefing_lists_documented_exposure(monkeypatch):
    from atlas.connectors import yahoo
    from atlas.core.errors import SourceUnavailable

    async def down(*_a, **_k):
        raise SourceUnavailable("yahoo", "down")

    monkeypatch.setattr(yahoo, "quote_for", down)
    made = await reports.generate("asset", "XOM")
    assert "US Gulf energy" in made["markdown"] and "Price for XOM" in made["markdown"]


@pytest.mark.parametrize(("kind", "subject"), [("asset", "bad symbol!"), ("country", "Narnia"), ("commodity", "unobtainium")])
def test_briefing_rejects_unknown_subjects(kind, subject):
    with pytest.raises(ValueError):
        asyncio.run(reports.build(kind, subject))


def test_briefing_export_routes():
    c = client()
    assert c.post("/api/briefings", json={"kind": "country", "subject": "Australia"}).status_code == 201
    row = c.get("/api/briefings").json()[0]
    assert c.get(f"/api/briefings/{row['id']}/export?format=html").headers["content-type"].startswith("text/html")
    assert c.get("/api/briefings/999").status_code == 404


def test_bis_skips_missing_values():
    text = "REF_AREA,TIME_PERIOD,OBS_VALUE\nGB,2026-01-01,4.0\nGB,2026-01-02,NaN\nGB,2026-01-03,3.75\nGB,2026-01-04,\n"
    assert trade.parse_bis(text)["GB"] == [("2026-01-01", 4.0), ("2026-01-03", 3.75)]


def test_old_country_figures_are_flagged():
    from datetime import date

    assert trade.out_of_date("2021-06", date(2026, 11, 1))
    assert not trade.out_of_date("2026-08", date(2026, 11, 1))


def test_alt_register_is_complete_and_honest():
    from atlas.api.world import ALT_SIGNALS

    assert len(ALT_SIGNALS) == 20
    fields = {"method", "history", "source", "frequency", "limitations", "confidence", "validation", "assets"}
    assert all(fields <= set(s) for s in ALT_SIGNALS)
    assert next(s for s in ALT_SIGNALS if s["id"] == "google_trends")["status"] == "blocked"


@pytest.mark.parametrize("layer", ["zones", "monitoring"])
def test_new_map_layers(layer):
    assert client().get(f"/api/map/layer/{layer}").json()["data"]["type"] == "FeatureCollection"


async def test_hybrid_search_falls_back_to_keywords_without_a_model():
    from atlas.services import documents

    documents.ingest("a.md", b"Copper smelter output rose in Chile during the quarter.")
    assert (await documents.hybrid_search("copper chile"))[0]["filename"] == "a.md"


async def test_hybrid_search_ranks_vector_match_and_cleans_up(monkeypatch):
    import respx
    from httpx import Response

    from atlas.config import get_settings
    from atlas.db import DocVector, session_scope
    from atlas.services import documents

    monkeypatch.setattr(get_settings(), "ollama_embed_model", "fake")
    doc = documents.ingest("b.md", b"Mining output and bauxite shipments were steady this period.")
    with respx.mock:
        respx.post("http://127.0.0.1:11434/api/embed").mock(side_effect=lambda r: Response(200, json={"embeddings": [[1.0, 0.0]]}))
        assert await documents.index_vectors(doc["id"]) == 1
        rows = await documents.hybrid_search("aluminium ore")
    assert rows[0]["filename"] == "b.md"
    documents.delete(doc["id"])
    with session_scope() as db:
        assert db.query(DocVector).count() == 0


async def test_assistant_uses_exposures_and_events():
    from atlas.services import assistant, impact

    impact.save(impact.from_chokepoints([{"id": "chokepoint6", "name": "Strait of Hormuz", "disrupted": True, "pct_vs_baseline": -89.0, "latest_date": "2026-10-25", "lat": 26.5, "lon": 56.2, "transits_7d_avg": 3.3, "baseline_avg": 28.8, "z": -0.9}]))
    r = assistant.Retrieval()
    themes = assistant._themes("which events might affect crude oil supply")
    assert "hormuz" in {t.id for t in themes} or themes
    r.evidence.extend(assistant._exposure_ev(themes))
    assert any("not a forecast" in " ".join(e.facts) for e in r.evidence)
    assert "Hormuz" in " ".join(assistant._events_ev().facts)


async def test_memo_drops_oldest_entries():
    from atlas.core.memo import memo

    @memo(60, maxsize=2)
    async def double(x):
        calls.append(x)
        return x * 2

    calls = []
    for x in (1, 2, 3):
        await double(x)
    await double(3)
    assert calls == [1, 2, 3]
    await double(1)
    assert calls == [1, 2, 3, 1]


async def test_slow_feed_does_not_hold_up_the_event_page(monkeypatch):
    from atlas.connectors import calendar, world
    from atlas.services import impact

    async def fast(*_a, **_k):
        return []

    async def slow(*_a, **_k):
        await asyncio.sleep(5)

    for name in ("earthquakes", "tropical_storms", "natural_events", "federal_register"):
        monkeypatch.setattr(world, name, fast)
    monkeypatch.setattr(world, "gdelt_events", slow)

    async def banks():
        return [], []

    monkeypatch.setattr(calendar, "central_banks", banks)
    monkeypatch.setattr(impact, "FEED_BUDGET", 0.05)
    assert (await impact.collect())["failed"] == ["GDELT"]
