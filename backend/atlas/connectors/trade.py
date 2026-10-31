"""Port activity and cross-country indicators from free official statistics."""

import asyncio
import csv
import io
import math
import re
from datetime import date, datetime, timedelta

import numpy as np

from atlas.connectors import econ
from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import get_fetcher
from atlas.core.reference import PORT_DASHBOARD

PORTS = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Ports_Data/FeatureServer/0/query"
BIS = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.{areas}"
OECD_CPI = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/{areas}.M.N.CPI.PA._T.N.GY"
OECD_JOBS = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0/{areas}..._Z.Y._T.Y_GE15..M"
BANKS = {"US": "United States", "AU": "Australia", "XM": "Euro area", "GB": "United Kingdom", "JP": "Japan", "CN": "China", "IN": "India"}
OECD_AREAS = {"USA": "United States", "AUS": "Australia", "EA20": "Euro area", "GBR": "United Kingdom", "JPN": "Japan", "CHN": "China", "IND": "India"}
LATEST_PORTS: dict[str, dict] = {}


def summarise_port(rows: list[dict]) -> dict:
    """A congestion proxy, not a queue measure: it compares recent port calls with the prior year."""
    rows = sorted(rows, key=lambda r: r["date"])
    calls = np.array([r["portcalls"] for r in rows], dtype=float)
    if len(calls) < 60:
        return {"available": False}
    week, base = calls[-7:].mean(), calls[-372:-7]
    return {"available": True, "latest_date": rows[-1]["date"], "calls_7d_avg": round(float(week), 1), "baseline_avg": round(float(base.mean()), 1), "pct_vs_baseline": round((week / base.mean() - 1) * 100, 1) if base.mean() else None,
            "container_7d": round(float(np.mean([r["portcalls_container"] for r in rows[-7:]])), 1), "tanker_7d": round(float(np.mean([r["portcalls_tanker"] for r in rows[-7:]])), 1),
            "import_7d": round(float(np.mean([r["import"] for r in rows[-7:]]))), "export_7d": round(float(np.mean([r["export"] for r in rows[-7:]]))),
            "history": [{"date": r["date"], "calls": r["portcalls"]} for r in rows[-120:]]}


async def port(spec: dict) -> dict:
    got = await get_fetcher().get("portwatch", PORTS, params={"where": f"portid='{spec['portid']}'", "outFields": "date,portname,portcalls,portcalls_container,portcalls_tanker,import,export", "orderByFields": "date DESC", "resultRecordCount": 420, "f": "json"},
                                  ttl=24 * 3600, validate=lambda body: '"error"' not in body[:40], timeout=70, attempts=4)
    rows = [f["attributes"] for f in got.json().get("features", [])]
    for row in rows:
        if isinstance(row["date"], int):
            row["date"] = datetime.fromtimestamp(row["date"] / 1000).date().isoformat()
    result = {**spec, **summarise_port(rows)}
    if result.get("available"):
        LATEST_PORTS[spec["portname"]] = result
    return result


async def refresh_ports() -> int:
    gate = asyncio.Semaphore(2)

    async def one(spec: dict) -> None:
        async with gate:
            try:
                await port(spec)
            except SourceUnavailable:
                pass

    await asyncio.gather(*(one(p) for p in PORT_DASHBOARD))
    return len(LATEST_PORTS)


def parse_bis(text: str) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        value = float(row["OBS_VALUE"]) if row.get("OBS_VALUE") else math.nan
        if math.isfinite(value):
            out.setdefault(row["REF_AREA"], []).append((row["TIME_PERIOD"], value))
    return {k: sorted(v) for k, v in out.items()}


def summarise_rate(rows: list[tuple[str, float]]) -> dict:
    latest = rows[-1]
    change = next(((rows[i][0], rows[i][1] - rows[i - 1][1]) for i in range(len(rows) - 1, 0, -1) if rows[i][1] != rows[i - 1][1]), None)
    return {"rate": latest[1], "as_of": latest[0], "last_change_date": change[0] if change else None, "last_change": round(change[1], 3) if change else None}


async def policy_rates() -> dict:
    start = (date.today() - timedelta(days=800)).isoformat()
    got = await get_fetcher().get("bis", BIS.format(areas="+".join(BANKS)), params={"startPeriod": start, "format": "csv"}, ttl=24 * 3600)
    parsed = parse_bis(got.body)
    rows = [{"code": k, "country": BANKS[k], **summarise_rate(parsed[k]), "history": [{"date": d, "value": v} for d, v in parsed[k][::14]]} for k in BANKS if k in parsed]
    return {"rows": rows, "_fetched": got.fetched_at, "_stale": got.stale}


def parse_oecd(text: str) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        if row.get("OBS_VALUE"):
            out.setdefault(row["REF_AREA"], []).append((row["TIME_PERIOD"], float(row["OBS_VALUE"])))
    return {k: sorted(v) for k, v in out.items()}


async def _oecd(url: str, areas: list[str]) -> dict:
    start = f"{date.today().year - 5}-01"
    got = await get_fetcher().get("oecd", url.format(areas="+".join(areas)), params={"startPeriod": start, "format": "csvfile"}, ttl=24 * 3600)
    parsed = parse_oecd(got.body)
    return {"rows": [{"code": k, "country": OECD_AREAS[k], "latest": parsed[k][-1][1], "period": parsed[k][-1][0], "previous": parsed[k][-2][1] if len(parsed[k]) > 1 else None, "history": [{"date": d, "value": v} for d, v in parsed[k]]} for k in areas if k in parsed],
            "missing": [OECD_AREAS[k] for k in areas if k not in parsed], "_fetched": got.fetched_at, "_stale": got.stale}


def out_of_date(period: str, today: date, months: int = 9) -> bool:
    year, month = int(period[:4]), int(period[5:7])
    return (today.year - year) * 12 + today.month - month > months


async def inflation() -> dict:
    """OECD stops at different dates by country, so old values are flagged rather than compared."""
    res = await _oecd(OECD_CPI, [k for k in OECD_AREAS if k != "EA20"])
    euro = econ.history("ea.hicp")
    if euro:
        res["rows"].insert(2, {"code": "EA20", "country": "Euro area", "latest": euro[-1][1], "period": euro[-1][0][:7], "previous": euro[-2][1] if len(euro) > 1 else None, "history": [{"date": d[:7], "value": v} for d, v in euro[-60:]], "source": "eurostat"})
    for row in res["rows"]:
        row["out_of_date"] = out_of_date(row["period"], date.today())
    return res


async def unemployment() -> dict:
    res = await _oecd(OECD_JOBS, [k for k in OECD_AREAS if k not in {"CHN", "IND"}])
    for row in res["rows"]:
        row["out_of_date"] = out_of_date(row["period"], date.today())
    return res


MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def parse_bea(page: str) -> list[dict]:
    year = re.search(r"Year (20\d\d)", page)
    if not year:
        return []
    out = []
    for month_day, title in re.findall(rf'release-date">((?:{MONTHS}) \d+)<.*?release-title[^>]*>\s*([^<]+?)\s*<', page, re.S):
        out.append({"date": datetime.strptime(f"{month_day} {year[1]}", "%B %d %Y").date().isoformat(), "title": title, "region": "US", "kind": "release", "confirmed": True, "url": "https://www.bea.gov/news/schedule"})
    return out


async def releases() -> list[dict]:
    got = await get_fetcher().get("calendars", "https://www.bea.gov/news/schedule", ttl=86400)
    return parse_bea(got.body)


async def procurement(company: str) -> dict:
    """US federal contract awards only. Award size is not revenue."""
    end = date.today()
    body = {"filters": {"recipient_search_text": [company], "award_type_codes": ["A", "B", "C", "D"], "time_period": [{"start_date": (end - timedelta(days=365)).isoformat(), "end_date": end.isoformat()}]},
            "fields": ["Recipient Name", "Award Amount", "Award ID", "Awarding Agency", "Description"], "limit": 10, "sort": "Award Amount", "order": "desc"}
    got = await get_fetcher().get("usaspending", "https://api.usaspending.gov/api/v2/search/spending_by_award/", method="POST", json_body=body, ttl=86400, headers={"Content-Type": "application/json"})
    return {"awards": [{"recipient": r.get("Recipient Name"), "amount": r.get("Award Amount"), "id": r.get("Award ID"), "agency": r.get("Awarding Agency"), "description": (r.get("Description") or "")[:160]} for r in got.json().get("results", [])], "_fetched": got.fetched_at, "_stale": got.stale}


_refresh_task: asyncio.Task | None = None


async def start_refresh() -> None:
    """Port queries are slow, so requests return at once and the data fills in behind them."""
    global _refresh_task
    if _refresh_task is None or _refresh_task.done():
        _refresh_task = asyncio.create_task(refresh_ports())
