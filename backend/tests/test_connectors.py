import pytest

from atlas.connectors import econ, news, sec, world, yahoo


def chart(stamps, closes, granularity="1d"):
    n = len(stamps)
    return {"chart": {"error": None, "result": [{"meta": {"symbol": "BHP.AX", "dataGranularity": granularity, "currency": "AUD"}, "timestamp": stamps,
                                                 "indicators": {"quote": [{"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1] * n}]}}]}}


def test_parse_chart_merges_duplicate_last_session():
    # Regression: daily data repeats the last session stamped at the final trade.
    got = yahoo.parse_chart(chart([1793228400, 1793314800, 1793337658], [57.52, 57.56, 57.56]))
    assert [b["close"] for b in got["bars"]] == [57.52, 57.56]


def test_parse_chart_keeps_intraday_bars():
    assert len(yahoo.parse_chart(chart([0, 300, 600], [1.0, 2.0, 3.0], "5m"))["bars"]) == 3


def test_parse_chart_skips_null_closes():
    assert len(yahoo.parse_chart(chart([0, 100_000], [1.0, None]))["bars"]) == 1


def test_parse_chart_raises_for_unknown_symbol():
    with pytest.raises(ValueError):
        yahoo.parse_chart({"chart": {"result": None, "error": {"description": "No data found"}}})


FACTS = {"facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [
        {"start": "2023-01-01", "end": "2023-12-31", "val": 90, "form": "10-K", "fp": "FY", "filed": "2024-02-01"},
        {"start": "2023-01-01", "end": "2023-12-31", "val": 100, "form": "10-K", "fp": "FY", "filed": "2025-02-01"},
        {"start": "2024-01-01", "end": "2024-12-31", "val": 120, "form": "10-K", "fp": "FY", "filed": "2025-02-01"},
        {"start": "2024-10-01", "end": "2024-12-31", "val": 35, "form": "10-K", "fp": "FY", "filed": "2025-02-01"}]}},
    "NetIncomeLoss": {"units": {"USD": [{"start": "2024-01-01", "end": "2024-12-31", "val": 12, "form": "10-K", "fp": "FY", "filed": "2025-02-01"}]}},
    "Assets": {"units": {"USD": [{"end": "2024-12-31", "val": 500, "form": "10-K", "fp": "FY", "filed": "2025-02-01"}]}},
    "StockholdersEquity": {"units": {"USD": [{"end": "2024-12-31", "val": 200, "form": "10-K", "fp": "FY", "filed": "2025-02-01"}]}},
    "LongTermDebtNoncurrent": {"units": {"USD": [{"end": "2024-12-31", "val": 50, "form": "10-K", "fp": "FY", "filed": "2025-02-01"}]}},
    "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [{"start": "2024-01-01", "end": "2024-12-31", "val": 30, "form": "10-K", "fp": "FY", "filed": "2025-02-01"}]}},
    "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [{"start": "2024-01-01", "end": "2024-12-31", "val": 10, "form": "10-K", "fp": "FY", "filed": "2025-02-01"}]}},
}}}


def test_statements_use_latest_filing_and_ignore_quarter_stub():
    rows = sec.build_statements(FACTS)
    assert [(r["period_end"], r["revenue"]) for r in rows] == [("2023-12-31", 100), ("2024-12-31", 120)]


def test_ratios():
    r = sec.ratios(sec.build_statements(FACTS))[-1]
    assert r["revenue_growth"] == pytest.approx(0.2)
    assert r["net_margin"] == pytest.approx(0.1)
    assert r["free_cash_flow"] == 20
    assert r["debt_to_equity"] == pytest.approx(0.25)


FORM4 = """<ownershipDocument><reportingOwner><reportingOwnerId><rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>
<reportingOwnerRelationship><officerTitle>CFO</officerTitle></reportingOwnerRelationship></reportingOwner>
<nonDerivativeTable><nonDerivativeTransaction><transactionDate><value>2026-01-02</value></transactionDate>
<transactionCoding><transactionCode>S</transactionCode></transactionCoding><transactionAmounts><transactionShares><value>100</value></transactionShares>
<transactionPricePerShare><value>12.5</value></transactionPricePerShare><transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts>
</nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>"""


def test_parse_form4():
    assert sec.parse_form4(FORM4) == [{"owner": "Doe Jane", "title": "CFO", "date": "2026-01-02", "code": "S", "acquired_disposed": "D", "shares": 100.0, "price": 12.5}]


def test_form4_rejects_entity_expansion():
    bomb = '<!DOCTYPE x [<!ENTITY a "aaaa">]><ownershipDocument>&a;</ownershipDocument>'
    with pytest.raises(Exception, match="Entities|forbidden|Forbidden"):
        sec.parse_form4(bomb)


def test_earnings_estimate_is_flagged():
    sub = {"cik": "1", "filings": {"recent": {"form": ["8-K"], "accessionNumber": ["1-2-3"], "primaryDocument": ["a.htm"], "filingDate": ["2020-01-30"], "reportDate": [""], "primaryDocDescription": [""], "items": ["2.02,9.01"]}}}
    got = sec.earnings_dates(sub)
    assert got["next_is_estimate"] and got["next_estimate"] == "2020-04-30" and got["estimate_passed"]


def test_parse_rba_accepts_both_date_formats():
    text = "﻿Title,CPI\nSeries ID,GCPIAGYP\n31/03/2026,3.1\n30-Jun-2026,3.2\nbad,row\n"
    assert econ.parse_rba(text, "GCPIAGYP") == [("2026-03-31", 3.1), ("2026-06-30", 3.2)]


def test_parse_eurostat():
    payload = {"dimension": {"time": {"category": {"index": {"2026-08": 0, "2026-09": 1}}}}, "value": {"0": 3.2, "1": 3.8}}
    assert econ.parse_eurostat(payload) == [("2026-08-01", 3.2), ("2026-09-01", 3.8)]


def test_parse_bls_skips_annual_and_missing():
    payload = {"Results": {"series": [{"seriesID": "X", "data": [{"year": "2026", "period": "M02", "value": "2"}, {"year": "2026", "period": "M01", "value": "1"}, {"year": "2026", "period": "M13", "value": "9"}, {"year": "2025", "period": "M10", "value": "-"}]}]}}
    assert econ.parse_bls(payload, "X") == [("2026-01-01", 1.0), ("2026-02-01", 2.0)]


def test_parse_treasury():
    assert econ.parse_treasury('Date,"10 Yr"\n10/30/2026,4.94\n', "10 Yr") == [("2026-10-30", 4.94)]


def test_yoy():
    assert econ.yoy([("2025-01-01", 100.0), ("2026-01-01", 103.0)]) == [("2026-01-01", 3.0)]


def test_revisions_are_kept_for_point_in_time_reads():
    from datetime import timedelta

    from atlas.core.envelope import utcnow

    econ.remember("s", [("2026-01-01", 1.0)], "bls")
    before_revision = utcnow() + timedelta(milliseconds=1)
    import time

    time.sleep(0.01)
    econ.remember("s", [("2026-01-01", 1.5)], "bls")
    assert econ.history("s") == [("2026-01-01", 1.5)]
    assert econ.history("s", as_of=before_revision) == [("2026-01-01", 1.0)]
    assert econ.remember("s", [("2026-01-01", 1.5)], "bls") == 0


def test_rss_atom_and_rdf_are_parsed_and_scripts_refused():
    rss = '<rss><channel><item><title>A &lt;b&gt;x&lt;/b&gt;</title><link>https://a.test/1</link><pubDate>Fri, 30 Oct 2026 10:00:00 GMT</pubDate></item><item><title>Bad</title><link>javascript:alert(1)</link></item></channel></rss>'
    assert [(i["title"], i["url"]) for i in news.parse_feed(rss)] == [("A x", "https://a.test/1")]
    atom = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>B</title><link href="https://a.test/2"/><updated>2026-10-30T10:00:00Z</updated></entry></feed>'
    assert news.parse_feed(atom)[0]["url"] == "https://a.test/2"


def test_anomaly_stats_flags_dry_window():
    from datetime import date, timedelta

    days, rain, temp = [], [], []
    for i in range(12 * 365 + 3):
        d = date(2014, 1, 1) + timedelta(days=i)
        days.append(d.isoformat())
        rain.append(0.0 if d.year == 2025 and d.month == 12 else 3.0 + (d.year % 3) * 0.3)
        temp.append(20.0 + (d.year % 3) * 0.2)
    stats = world.anomaly_stats(days, rain, temp, date(2025, 12, 31))
    assert stats["available"] and stats["rain_mm"] == 0 and stats["rain_z"] < -1.5
    assert world.risk_label(stats, {"frost_days": 0, "heat_days": 0})["level"] != "normal"


def test_chokepoint_flags_collapse():
    rows = [{"date": f"2026-{m:02d}-{d:02d}", "n_total": 50 + (d % 3), "n_tanker": 10, "n_container": 10} for m in range(1, 9) for d in range(1, 29)]
    rows += [{"date": f"2026-09-{d:02d}", "n_total": 5, "n_tanker": 1, "n_container": 1} for d in range(1, 8)]
    got = world.summarise_chokepoint(rows)
    assert got["disrupted"] and got["pct_vs_baseline"] < -80


def test_locate_is_best_effort():
    assert world.locate("Tanker seized near Strait of Hormuz")[0] == "Hormuz"
    assert world.locate("Quarterly results improve") is None


async def test_cold_chokepoint_load_answers_on_time(monkeypatch):
    import asyncio

    async def slow():
        await asyncio.sleep(5)

    monkeypatch.setattr(world, "chokepoints", slow)
    rows = await asyncio.wait_for(world.chokepoints_ready(timeout=0.01), 1)
    assert rows and all(r["loading"] and not r["available"] for r in rows)


FOMC_HTML = """<h4><a>2026 FOMC Meetings</a></h4><div class="fomc-meeting__month col"><strong>January</strong></div><div class="fomc-meeting__date col">27-28</div>
<div class="fomc-meeting__month col"><strong>Apr/May</strong></div><div class="fomc-meeting__date col">28-1*</div>"""


def test_fomc_dates_use_the_decision_day():
    from atlas.connectors import calendar

    assert [e["date"] for e in calendar.parse_fomc(FOMC_HTML)] == ["2026-01-28", "2026-05-01"]


def test_rba_dates():
    from atlas.connectors import calendar

    page = '''<caption>Board meeting schedules 2026</caption><tr><th scope="row">November</th> <td>2&ndash;3 November</td> <td>19 November</td></tr>
    <tr><th colspan="3">October</th></tr><tr><th scope="row">December</th><td>7&ndash;8 December</td><td></td></tr>
    <caption>Board meeting schedules 2027</caption><tr><th scope="row">February</th><td></td><td>24 February</td></tr>'''
    assert [e["date"] for e in calendar.parse_rba(page)] == ["2026-11-03", "2026-12-08"]


def test_upcoming_is_sorted_and_windowed():
    from datetime import date

    from atlas.connectors import calendar

    rows = [{"date": "2026-12-01"}, {"date": "2026-11-05"}, {"date": "2020-01-01"}, {"date": "2030-01-01"}]
    assert [r["date"] for r in calendar.upcoming(rows, date(2026, 11, 1))] == ["2026-11-05", "2026-12-01"]


def spark_payload():
    return {"spark": {"result": [{"symbol": "AAPL", "response": [{"meta": {"regularMarketPrice": 110.0, "chartPreviousClose": 100.0, "instrumentType": "EQUITY", "currency": "USD", "regularMarketTime": 1000},
                                                                  "indicators": {"quote": [{"close": [100.0, None, 110.0]}]}}]}]}}


def test_spark_gives_change_and_drops_gaps():
    q = yahoo.parse_spark(spark_payload())["AAPL"]
    assert q["change_pct"] == pytest.approx(10) and q["spark"] == [100.0, 110.0] and q["freshness"] == "delayed"


def test_thin_keeps_last_value():
    out = yahoo.thin(list(map(float, range(1000))), 40)
    assert len(out) == 40 and out[-1] == 999


def test_parse_chart_carries_adjusted_close():
    payload = chart([0, 100_000], [10.0, 11.0])
    payload["chart"]["result"][0]["indicators"]["adjclose"] = [{"adjclose": [9.5, 11.0]}]
    assert yahoo.parse_chart(payload)["bars"][0]["adjclose"] == 9.5


def test_sdmx_csv():
    assert econ.parse_sdmx_csv("TIME_PERIOD,OBS_VALUE\n2026-01,4.1\n2025-12,\n") == [("2026-01-01", 4.1)]


def test_shares_sum_classes_and_fall_back():
    multi = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [{"end": "2026-06-30", "val": 10}, {"end": "2026-06-30", "val": 5}, {"end": "2025-06-30", "val": 99}]}}}}}
    assert sec.shares_outstanding(multi) == {"value": 15, "as_of": "2026-06-30"}
    gaap = {"facts": {"us-gaap": {"WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [{"end": "2026-06-30", "val": 7}]}}}}}
    assert sec.shares_outstanding(gaap)["value"] == 7
    assert sec.shares_outstanding({"facts": {}}) is None
