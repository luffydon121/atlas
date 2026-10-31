"""Official economic series. Each value is appended to `observations`, preserving revisions."""

import base64
import csv
import io
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime

import xlrd
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert

from atlas.config import get_settings
from atlas.core.envelope import utcnow
from atlas.core.errors import SourceNotConfigured
from atlas.core.fetcher import Fetched, get_fetcher
from atlas.db import Observation, session_scope

Row = tuple[str, float]


@dataclass(frozen=True)
class Series:
    id: str
    name: str
    region: str
    group: str
    unit: str
    source: str
    code: str
    transform: str | None = None  # "yoy" converts an index into a 12-month % change


CATALOG: list[Series] = [
    Series("us.cpi", "CPI inflation", "US", "Inflation", "% y/y", "bls", "CUUR0000SA0", "yoy"),
    Series("us.core_cpi", "Core CPI inflation", "US", "Inflation", "% y/y", "bls", "CUUR0000SA0L1E", "yoy"),
    Series("us.unemployment", "Unemployment rate", "US", "Labour", "%", "bls", "LNS14000000"),
    Series("us.payrolls", "Nonfarm payrolls", "US", "Labour", "thousands", "bls", "CES0000000001"),
    Series("us.manufacturing_jobs", "Manufacturing employment", "US", "Activity", "thousands", "bls", "CES3000000001"),
    Series("us.y3m", "3-month Treasury", "US", "Rates", "%", "treasury", "3 Mo"),
    Series("us.y2", "2-year Treasury", "US", "Rates", "%", "treasury", "2 Yr"),
    Series("us.y10", "10-year Treasury", "US", "Rates", "%", "treasury", "10 Yr"),
    Series("us.y30", "30-year Treasury", "US", "Rates", "%", "treasury", "30 Yr"),
    Series("au.cash_rate", "Cash rate target", "Australia", "Rates", "%", "rba", "f1-data|FIRMMCRTD"),
    Series("au.cpi", "CPI inflation", "Australia", "Inflation", "% y/y", "rba", "g1-data|GCPIAGYP"),
    Series("au.y10", "10-year government bond", "Australia", "Rates", "%", "rba", "f2-data|FCMYGBAG10D"),
    Series("au.y3", "3-year government bond", "Australia", "Rates", "%", "rba", "f2-data|FCMYGBAG3D"),
    Series("au.unemployment", "Unemployment rate", "Australia", "Labour", "%", "abs", "LF,1.0.0/M13.3.1599.20.AUS.M"),
    Series("au.cli", "OECD leading indicator", "Australia", "Activity", "index", "oecd", "AUS"),
    Series("us.cli", "OECD leading indicator", "US", "Activity", "index", "oecd", "USA"),
    Series("us.crude_stocks", "Commercial crude stocks", "US", "Energy", "thousand bbl", "eia", "WCESTUS1"),
    Series("ea.deposit_rate", "ECB deposit rate", "Euro area", "Rates", "%", "ecb", "FM/D.U2.EUR.4F.KR.DFR.LEV"),
    Series("ea.hicp", "HICP inflation", "Euro area", "Inflation", "% y/y", "eurostat", "prc_hicp_minr"),
    Series("us.gdp", "Real GDP", "US", "Activity", "$bn (2017)", "fred", "GDPC1"),
    Series("us.indpro", "Industrial production", "US", "Activity", "index", "fred", "INDPRO"),
    Series("us.retail", "Retail sales", "US", "Consumer", "$m", "fred", "RSAFS"),
    Series("us.housing_starts", "Housing starts", "US", "Housing", "thousands", "fred", "HOUST"),
]
BY_ID = {s.id: s for s in CATALOG}

WB_INDICATORS = {
    "gdp_growth": ("NY.GDP.MKTP.KD.ZG", "GDP growth", "% y/y"),
    "inflation": ("FP.CPI.TOTL.ZG", "Inflation", "% y/y"),
    "unemployment": ("SL.UEM.TOTL.ZS", "Unemployment", "%"),
    "debt_gdp": ("GC.DOD.TOTL.GD.ZS", "Government debt", "% GDP"),
    "current_account": ("BN.CAB.XOKA.GD.ZS", "Current account", "% GDP"),
    "reserves": ("FI.RES.TOTL.CD", "FX reserves", "US$"),
    "trade_balance": ("NE.RSB.GNFS.ZS", "Trade balance", "% GDP"),
}
WB_COUNTRIES = {"AU": "Australia", "US": "United States", "CN": "China", "JP": "Japan", "DE": "Germany",
                "GB": "United Kingdom", "IN": "India", "BR": "Brazil", "ID": "Indonesia", "KR": "South Korea"}


def parse_bls(payload: dict, code: str) -> list[Row]:
    for series in payload.get("Results", {}).get("series", []):
        if series.get("seriesID") == code:
            rows = [(f"{d['year']}-{d['period'][1:]}-01", float(d["value"])) for d in series.get("data", [])
                    if d.get("period", "").startswith("M") and d["period"] != "M13" and d.get("value") not in ("-", "")]
            return sorted(rows)
    return []


def parse_treasury(text: str, column: str) -> list[Row]:
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        if row.get(column):
            rows.append((datetime.strptime(row["Date"], "%m/%d/%Y").date().isoformat(), float(row[column])))
    return sorted(rows)


def parse_rba(text: str, code: str) -> list[Row]:
    reader = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    header = next((r for r in reader if r and r[0].strip() == "Series ID"), None)
    if header is None or code not in header:
        return []
    col = header.index(code)
    rows = []
    for r in reader[reader.index(header) + 1:]:
        if len(r) <= col or not r[0] or not r[col].strip():
            continue
        try:
            rows.append((_rba_date(r[0].strip()), float(r[col])))
        except ValueError:
            continue
    return sorted(rows)


def _rba_date(raw: str) -> str:
    """RBA tables mix 31-Mar-2026 and 31/03/2026."""
    for fmt in ("%d-%b-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(raw)


def parse_eurostat(payload: dict) -> list[Row]:
    index = payload["dimension"]["time"]["category"]["index"]
    values = payload.get("value", {})
    return sorted((f"{period}-01", float(values[str(pos)])) for period, pos in index.items() if str(pos) in values)


def parse_ecb(text: str) -> list[Row]:
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        period, value = row.get("TIME_PERIOD"), row.get("OBS_VALUE")
        if period and value:
            rows.append((period if len(period) > 7 else f"{period}-01", float(value)))
    return sorted(rows)


def yoy(rows: list[Row]) -> list[Row]:
    lookup = dict(rows)
    out = []
    for period, value in rows:
        y, rest = period.split("-", 1)
        base = lookup.get(f"{int(y) - 1}-{rest}")
        if base:
            out.append((period, round((value / base - 1) * 100, 3)))
    return out


async def _bls(s: Series) -> tuple[list[Row], Fetched]:
    settings = get_settings()
    end = date.today().year
    body = {"seriesid": [x.code for x in CATALOG if x.source == "bls"], "startyear": str(end - 9), "endyear": str(end)}
    if settings.bls_api_key:
        body["registrationkey"] = settings.bls_api_key
    got = await get_fetcher().get("bls", "https://api.bls.gov/publicAPI/v2/timeseries/data/", method="POST",
                                  json_body=body, ttl=12 * 3600)
    return parse_bls(got.json(), s.code), got


async def _treasury(s: Series) -> tuple[list[Row], Fetched]:
    rows: list[Row] = []
    year = date.today().year
    got = None
    for y in range(year - 4, year + 1):
        got = await get_fetcher().get(
            "treasury",
            f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all",
            params={"type": "daily_treasury_yield_curve", "field_tdr_date_value": y, "_format": "csv"},
            ttl=6 * 3600 if y == year else 30 * 86400)
        rows += parse_treasury(got.body, s.code)
    return sorted(rows), got


async def _rba(s: Series) -> tuple[list[Row], Fetched]:
    table, code = s.code.split("|")
    got = await get_fetcher().get("rba", f"https://www.rba.gov.au/statistics/tables/csv/{table}.csv", ttl=12 * 3600)
    return parse_rba(got.body, code), got


async def _ecb(s: Series) -> tuple[list[Row], Fetched]:
    flow, key = s.code.split("/", 1)
    got = await get_fetcher().get("ecb", f"https://data-api.ecb.europa.eu/service/data/{flow}/{key}",
                                  params={"format": "csvdata", "startPeriod": "2015-01-01"}, ttl=12 * 3600)
    return parse_ecb(got.body), got


async def _eurostat(s: Series) -> tuple[list[Row], Fetched]:
    got = await get_fetcher().get("eurostat", f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{s.code}",
                                  params={"format": "JSON", "geo": "EA", "coicop18": "TOTAL", "unit": "RCH_A", "sinceTimePeriod": "2016-01"}, ttl=12 * 3600)
    return parse_eurostat(got.json()), got


def parse_sdmx_csv(text: str, column: str = "OBS_VALUE") -> list[Row]:
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        period, value = row.get("TIME_PERIOD"), row.get(column)
        if period and value:
            rows.append((period if len(period) > 7 else f"{period}-01", float(value)))
    return sorted(rows)


async def _abs(s: Series) -> tuple[list[Row], Fetched]:
    flow, key = s.code.split("/", 1)
    got = await get_fetcher().get("abs", f"https://data.api.abs.gov.au/rest/data/ABS,{flow}/{key}", params={"startPeriod": "2016-01", "format": "csv"}, ttl=12 * 3600)
    return parse_sdmx_csv(got.body), got


async def _oecd(s: Series) -> tuple[list[Row], Fetched]:
    got = await get_fetcher().get("oecd", f"https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,4.1/{s.code}.M.LI...AA...H",
                                  params={"startPeriod": "2016-01", "format": "csvfile"}, ttl=24 * 3600)
    return parse_sdmx_csv(got.body), got


def parse_eia(raw: bytes) -> list[Row]:
    book = xlrd.open_workbook(file_contents=raw)
    sheet = book.sheet_by_name("Data 1")
    rows = []
    for i in range(3, sheet.nrows):
        when, value = sheet.cell(i, 0), sheet.cell(i, 1)
        if when.ctype == xlrd.XL_CELL_DATE and value.ctype == xlrd.XL_CELL_NUMBER:
            rows.append((xlrd.xldate_as_datetime(when.value, book.datemode).date().isoformat(), float(value.value)))
    return sorted(rows)[-520:]


async def _eia(s: Series) -> tuple[list[Row], Fetched]:
    got = await get_fetcher().get("eia", f"https://www.eia.gov/dnav/pet/hist_xls/{s.code}w.xls", ttl=12 * 3600, binary=True)
    return parse_eia(base64.b64decode(got.body)), got


async def _fred(s: Series) -> tuple[list[Row], Fetched]:
    key = get_settings().fred_api_key
    if not key:
        raise SourceNotConfigured("fred", "Add a free ATLAS_FRED_API_KEY to enable this series.")
    got = await get_fetcher().get("fred", "https://api.stlouisfed.org/fred/series/observations",
                                  params={"series_id": s.code, "api_key": key, "file_type": "json",
                                          "observation_start": "2010-01-01"}, ttl=12 * 3600)
    return [(o["date"], float(o["value"])) for o in got.json().get("observations", []) if o["value"] != "."], got


_READERS: dict[str, Callable[[Series], Awaitable[tuple[list[Row], Fetched]]]] = {
    "bls": _bls, "treasury": _treasury, "rba": _rba, "ecb": _ecb, "eurostat": _eurostat, "abs": _abs, "oecd": _oecd, "eia": _eia, "fred": _fred}


def remember(series_id: str, rows: list[Row], source: str) -> int:
    """Appends unseen (period, value) pairs. A revision is a new row, so vintages are preserved."""
    if not rows:
        return 0
    now = utcnow()
    values = [{"series_id": series_id, "period": p, "value": v, "source": source, "first_seen": now} for p, v in rows]
    added = 0
    with session_scope() as db:
        for start in range(0, len(values), 400):
            added += db.execute(insert(Observation).values(values[start:start + 400]).on_conflict_do_nothing()).rowcount
    return added


def history(series_id: str, as_of: datetime | None = None) -> list[Row]:
    """Latest known value per period, or the value known at `as_of` for point-in-time research."""
    stmt = select(Observation.period, Observation.value, func.max(Observation.first_seen)).where(Observation.series_id == series_id)
    if as_of:
        stmt = stmt.where(Observation.first_seen <= as_of)
    stmt = stmt.group_by(Observation.period).order_by(Observation.period)
    with session_scope() as db:
        return [(p, v) for p, v, _ in db.execute(stmt).all()]


async def load(series: Series) -> tuple[list[Row], datetime | None, bool]:
    rows, got = await _READERS[series.source](series)
    if series.transform == "yoy":
        rows = yoy(rows)
    remember(series.id, rows, series.source)
    return rows, got.fetched_at, got.stale


async def world_bank(indicator: str, countries: list[str], years: int = 25) -> Fetched:
    code = WB_INDICATORS[indicator][0]
    return await get_fetcher().get("worldbank", f"https://api.worldbank.org/v2/country/{';'.join(countries)}/indicator/{code}",
                                   params={"format": "json", "per_page": 2000, "mrv": years}, ttl=86400)


def parse_world_bank(payload: list) -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = {}
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        return out
    for row in payload[1]:
        if row.get("value") is not None:
            out.setdefault(row["countryiso3code"] or row["country"]["id"], []).append((row["date"], row["value"]))
    return {k: sorted(v) for k, v in out.items()}


async def yield_curve() -> dict:
    year = date.today().year
    got = await get_fetcher().get(
        "treasury", f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all",
        params={"type": "daily_treasury_yield_curve", "field_tdr_date_value": year, "_format": "csv"}, ttl=6 * 3600)
    rows = list(csv.DictReader(io.StringIO(got.body)))
    if not rows:
        return {"curves": [], "fetched_at": got.fetched_at, "stale": got.stale}
    tenors = [c for c in rows[0] if c != "Date"]
    picks = [(0, "Latest"), (min(21, len(rows) - 1), "1 month ago"), (min(126, len(rows) - 1), "6 months ago")]
    curves = [{"label": label, "date": datetime.strptime(rows[i]["Date"], "%m/%d/%Y").date().isoformat(),
               "points": [{"tenor": t, "value": float(rows[i][t]) if rows[i].get(t) else None} for t in tenors]}
              for i, label in picks]
    return {"curves": curves, "fetched_at": got.fetched_at, "stale": got.stale}
