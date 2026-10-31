"""Weather, hazards, aviation, shipping, geopolitics, and alternative attention data."""

import asyncio
import math
import re
from datetime import UTC, date, datetime, timedelta

import numpy as np

from atlas.connectors.econ import remember
from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import get_fetcher
from atlas.core.reference import AIRPORTS, CHOKEPOINTS, COMMODITY_TICKERS, WEATHER_REGIONS

# -- Weather ---------------------------------------------------------------------------------------------

LATEST_RISK: dict[str, dict] = {}


async def forecast(lat: float, lon: float, days: int = 7) -> dict:
    got = await get_fetcher().get("openmeteo", "https://api.open-meteo.com/v1/forecast", params={
        "latitude": round(lat, 2), "longitude": round(lon, 2), "forecast_days": days, "timezone": "UTC",
        "current": "temperature_2m,precipitation,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,wind_speed_10m_max"}, ttl=3600)
    return {**got.json(), "_fetched": got.fetched_at, "_stale": got.stale}


def anomaly_stats(days: list[str], precip: list, temp: list, today: date, window: int = 30) -> dict:
    """Compares the latest window with the same calendar window in each earlier year."""
    series = {date.fromisoformat(d): (p, t) for d, p, t in zip(days, precip, temp, strict=True)}
    end = max((d for d, v in series.items() if v[0] is not None), default=today)

    def window_for(last: date):
        rows = [series.get(last - timedelta(days=i)) for i in range(window)]
        rows = [r for r in rows if r and r[0] is not None and r[1] is not None]
        return (sum(r[0] for r in rows), float(np.mean([r[1] for r in rows]))) if len(rows) >= window * 0.9 else None

    current = window_for(end)
    past = []
    for years in range(1, 11):
        try:
            anchor = end.replace(year=end.year - years)
        except ValueError:
            anchor = end.replace(year=end.year - years, day=28)
        value = window_for(anchor)
        if value:
            past.append(value)
    if not current or len(past) < 5:
        return {"available": False, "window_end": end.isoformat()}
    rains, temps = np.array([p[0] for p in past]), np.array([p[1] for p in past])
    rain_sd, temp_sd = max(float(rains.std(ddof=1)), 1.0), max(float(temps.std(ddof=1)), 0.2)
    return {"available": True, "window_end": end.isoformat(), "window_days": window, "baseline_years": len(past),
            "rain_mm": round(current[0], 1), "rain_normal_mm": round(float(rains.mean()), 1),
            "rain_pct_of_normal": round(current[0] / rains.mean() * 100, 1) if rains.mean() > 0 else None,
            "rain_z": round((current[0] - float(rains.mean())) / rain_sd, 2),
            "temp_c": round(current[1], 1), "temp_normal_c": round(float(temps.mean()), 1),
            "temp_z": round((current[1] - float(temps.mean())) / temp_sd, 2)}


def risk_label(stats: dict, forecast_flags: dict) -> dict:
    if not stats.get("available"):
        return {"level": "unknown", "drivers": ["Insufficient history for this window"]}
    drivers, score = [], 0.0
    if stats["rain_z"] <= -1.5:
        drivers.append(f"Dry: {stats['rain_pct_of_normal']}% of normal rain over {stats['window_days']} days")
        score += abs(stats["rain_z"])
    if stats["rain_z"] >= 2:
        drivers.append("Unusually wet: flood or waterlogging risk")
        score += stats["rain_z"] * 0.7
    if stats["temp_z"] >= 1.5:
        drivers.append(f"Hot: {stats['temp_c']} C vs {stats['temp_normal_c']} C normal")
        score += stats["temp_z"] * 0.7
    if forecast_flags["frost_days"]:
        drivers.append(f"Frost forecast on {forecast_flags['frost_days']} day(s)")
        score += 1.5
    if forecast_flags["heat_days"]:
        drivers.append(f"Extreme heat forecast on {forecast_flags['heat_days']} day(s)")
        score += 1.0
    level = "elevated" if score >= 3 else "watch" if score >= 1.5 else "normal"
    return {"level": level, "drivers": drivers or ["Near seasonal norms"], "score": round(score, 2)}


async def region_risk(commodity: str, region: tuple) -> dict:
    name, lat, lon, weight = region
    end = date.today() - timedelta(days=6)
    start = end.replace(year=end.year - 11)
    arch = await get_fetcher().get("openmeteo_archive", "https://archive-api.open-meteo.com/v1/archive", params={
        "latitude": lat, "longitude": lon, "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": "precipitation_sum,temperature_2m_mean", "timezone": "UTC"}, ttl=86400)
    daily = arch.json()["daily"]
    stats = anomaly_stats(daily["time"], daily["precipitation_sum"], daily["temperature_2m_mean"], end)
    fc = (await forecast(lat, lon))["daily"]
    mins, maxs = fc["temperature_2m_min"], fc["temperature_2m_max"]
    flags = {"frost_days": sum(1 for t in mins if t is not None and t <= 1) if commodity in {"coffee", "wheat", "soybeans", "corn"} else 0,
             "heat_days": sum(1 for t in maxs if t is not None and t >= 38) if commodity != "natural_gas" else 0}
    return {"region": name, "lat": lat, "lon": lon, "production_weight": weight, "stats": stats, "forecast": flags, "risk": risk_label(stats, flags)}


async def commodity_risk(commodity: str) -> dict:
    regions = await asyncio.gather(*(region_risk(commodity, r) for r in WEATHER_REGIONS[commodity]), return_exceptions=True)
    ok = [r for r in regions if isinstance(r, dict)]
    rank = {"elevated": 2, "watch": 1, "normal": 0, "unknown": 0}
    result = {"commodity": commodity, "ticker": COMMODITY_TICKERS[commodity], "regions": ok,
              "regions_unavailable": len(regions) - len(ok),
              "overall": max((r["risk"]["level"] for r in ok), key=lambda x: rank[x], default="unknown")}
    if ok:
        LATEST_RISK[commodity] = result
    return result


# -- Hazards ---------------------------------------------------------------------------------------------

async def earthquakes() -> list[dict]:
    got = await get_fetcher().get("usgs", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson", ttl=600)
    return [{"id": f["id"], "title": f["properties"]["title"], "mag": f["properties"]["mag"], "lon": f["geometry"]["coordinates"][0],
             "lat": f["geometry"]["coordinates"][1], "depth_km": f["geometry"]["coordinates"][2],
             "time": datetime.fromtimestamp(f["properties"]["time"] / 1000, UTC).replace(tzinfo=None).isoformat() + "Z",
             "url": f["properties"]["url"], "tsunami": bool(f["properties"].get("tsunami"))} for f in got.json()["features"]]


def parse_eonet(payload: dict) -> list[dict]:
    out = []
    for event in payload.get("events", []):
        geoms = [g for g in event.get("geometry", []) if g.get("type") == "Point"]
        if not geoms:
            continue
        last = geoms[-1]
        cats = event.get("categories") or [{}]
        out.append({"id": event["id"], "title": event["title"], "category": cats[0].get("title"), "lon": last["coordinates"][0],
                    "lat": last["coordinates"][1], "time": last.get("date"), "url": event.get("link")})
    return out


async def natural_events(days: int = 30) -> list[dict]:
    got = await get_fetcher().get("eonet", "https://eonet.gsfc.nasa.gov/api/v3/events",
                                  params={"status": "open", "days": days, "limit": 300}, ttl=1800)
    return parse_eonet(got.json())


async def nws_alerts() -> list[dict]:
    got = await get_fetcher().get("nws", "https://api.weather.gov/alerts/active", params={"severity": "Extreme,Severe", "status": "actual"},
                                  headers={"Accept": "application/geo+json"}, ttl=600)
    return [{"event": f["properties"]["event"], "area": f["properties"].get("areaDesc"), "severity": f["properties"].get("severity"),
             "effective": f["properties"].get("effective"), "headline": f["properties"].get("headline")} for f in got.json().get("features", [])][:100]


async def tropical_storms() -> list[dict]:
    got = await get_fetcher().get("nhc", "https://www.nhc.noaa.gov/CurrentStorms.json", ttl=1800)
    return [{"name": s.get("name"), "class": s.get("classification"), "intensity_kt": s.get("intensity"), "lat": s.get("latitudeNumeric"),
             "lon": s.get("longitudeNumeric"), "time": s.get("lastUpdate"), "url": (s.get("publicAdvisory") or {}).get("url")}
            for s in got.json().get("activeStorms", [])]


# -- Aviation --------------------------------------------------------------------------------------------

OPENSKY = "https://opensky-network.org/api/states/all"


def parse_states(payload: dict) -> list[dict]:
    out = []
    for s in payload.get("states") or []:
        if s[5] is None or s[6] is None:
            continue
        out.append({"icao24": s[0], "callsign": (s[1] or "").strip(), "country": s[2], "lon": s[5], "lat": s[6], "altitude_m": s[7],
                    "on_ground": s[8], "velocity_ms": s[9], "heading": s[10]})
    return out


async def aircraft(bbox: tuple[float, float, float, float]) -> dict:
    west, south, east, north = bbox
    got = await get_fetcher().get("opensky", OPENSKY, params={"lamin": south, "lomin": west, "lamax": north, "lomax": east}, ttl=120)
    payload = got.json()
    return {"states": parse_states(payload), "observed_at": payload.get("time"), "_fetched": got.fetched_at, "_stale": got.stale}


async def airport_activity(code: str) -> dict:
    airport = next((a for a in AIRPORTS if a["code"] == code), None)
    if airport is None:
        raise SourceUnavailable("opensky", f"Unknown airport {code}")
    d = 0.5
    box = (airport["lon"] - d, airport["lat"] - d, airport["lon"] + d, airport["lat"] + d)
    snapshot = await aircraft(box)
    states = snapshot["states"]
    ground = sum(1 for s in states if s["on_ground"])
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M")
    if not snapshot["_stale"]:
        remember(f"aviation.{code}.nearby", [(now, float(len(states)))], "opensky")
    return {**airport, "aircraft_nearby": len(states), "on_ground": ground, "airborne": len(states) - ground,
            "observed_at": snapshot["observed_at"], "_fetched": snapshot["_fetched"], "_stale": snapshot["_stale"]}


# -- Shipping --------------------------------------------------------------------------------------------

PORTWATCH = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query"


def summarise_chokepoint(rows: list[dict]) -> dict:
    rows = sorted(rows, key=lambda r: r["date"])
    totals = np.array([r["n_total"] for r in rows], dtype=float)
    if len(totals) < 40:
        return {"available": False}
    week = totals[-7:].mean()
    baseline = totals[-372:-7] if len(totals) > 60 else totals[:-7]
    sd = max(float(baseline.std(ddof=1)), 1.0)
    prior_week = [float(np.mean(baseline[i:i + 7])) for i in range(0, len(baseline) - 6, 7)]
    weekly_sd = max(float(np.std(prior_week, ddof=1)), 0.5) if len(prior_week) > 3 else sd
    z = (week - baseline.mean()) / weekly_sd
    return {"available": True, "latest_date": rows[-1]["date"], "transits_7d_avg": round(float(week), 1),
            "baseline_avg": round(float(baseline.mean()), 1), "pct_vs_baseline": round((week / baseline.mean() - 1) * 100, 1),
            "z": round(float(z), 2), "tanker_7d": round(float(np.mean([r["n_tanker"] for r in rows[-7:]])), 1),
            "container_7d": round(float(np.mean([r["n_container"] for r in rows[-7:]])), 1),
            # A long collapse raises the baseline's own spread, so a large fall also counts on its own.
            "disrupted": bool(z <= -2 or week / baseline.mean() <= 0.5), "history": [{"date": r["date"], "total": r["n_total"], "tanker": r["n_tanker"],
                                                     "container": r["n_container"]} for r in rows[-180:]]}


LATEST_CHOKEPOINTS: dict[str, dict] = {}


async def _chokepoint_rows(portid: str) -> tuple[list[dict], object]:
    """One chokepoint at a time. Wider queries time out on the service and return a 400 inside a 200."""
    got = await get_fetcher().get("portwatch", PORTWATCH, params={
        "where": f"portid='{portid}'", "outFields": "date,portid,n_total,n_tanker,n_container,n_cargo",
        "orderByFields": "date DESC", "resultRecordCount": 420, "f": "json"},
        ttl=12 * 3600, validate=lambda body: '"error"' not in body[:40])
    rows = []
    for feature in got.json().get("features", []):
        row = feature["attributes"]
        if isinstance(row["date"], int):
            row["date"] = datetime.fromtimestamp(row["date"] / 1000, UTC).date().isoformat()
        rows.append(row)
    return rows, got


async def chokepoint(cp: dict) -> dict:
    rows, got = await _chokepoint_rows(cp["id"])
    result = {**cp, **summarise_chokepoint(rows)}
    if result.get("available"):
        recent = sorted(rows, key=lambda r: r["date"])[-30:]
        remember(f"shipping.{cp['id']}.transits", [(r["date"], float(r["n_total"])) for r in recent], "portwatch")
    result = {**result, "_fetched": got.fetched_at, "_stale": got.stale}
    LATEST_CHOKEPOINTS[cp["id"]] = result
    return result


async def chokepoints() -> list[dict]:
    gate = asyncio.Semaphore(3)

    async def one(cp: dict) -> dict:
        async with gate:
            try:
                return await chokepoint(cp)
            except SourceUnavailable:
                return {**cp, "available": False}

    return list(await asyncio.gather(*(one(cp) for cp in CHOKEPOINTS)))


_chokepoint_task: asyncio.Task | None = None


async def chokepoints_ready(timeout: float = 20) -> list[dict]:
    """Answers within `timeout`. A cold start keeps loading in the background and fills in on the next call."""
    global _chokepoint_task
    if _chokepoint_task is None or _chokepoint_task.done():
        _chokepoint_task = asyncio.create_task(chokepoints())
    await asyncio.wait({_chokepoint_task}, timeout=timeout)
    return [LATEST_CHOKEPOINTS.get(cp["id"], {**cp, "available": False, "loading": not _chokepoint_task.done()}) for cp in CHOKEPOINTS]


# -- Geopolitics -----------------------------------------------------------------------------------------

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
THEMES = {
    "sanctions": ("sanction", "export control", "embargo", "tariff"),
    "conflict": ("strike", "conflict", "ceasefire", "invasion", "attack"),
    "supply_chain": ("supply chain", "port strike", "pipeline", "refinery", "outage"),
    "maritime": ("hormuz", "red sea", "suez", "taiwan strait", "panama canal", "shipping"),
    "politics": ("coup", "election", "state of emergency"),
}
QUERY = '("Strait of Hormuz" OR "Red Sea" OR "Suez Canal" OR "Taiwan Strait" OR "supply chain disruption" OR "export controls" OR "economic sanctions" OR "pipeline attack" OR "state of emergency")'


def classify_theme(title: str) -> str:
    low = title.lower()
    return next((theme for theme, words in THEMES.items() if any(w in low for w in words)), "other")


# Gazetteer for a best-effort map pin. A pin marks a place named in the headline, not a verified location.
PLACES = {
    "hormuz": (26.5, 56.2), "red sea": (20, 38.5), "suez": (30.6, 32.3), "bab el": (12.6, 43.3), "taiwan": (23.7, 121),
    "panama": (9.1, -79.7), "ukraine": (49, 32), "russia": (61, 90), "china": (35, 104), "iran": (32, 53), "israel": (31.5, 34.9),
    "gaza": (31.4, 34.4), "lebanon": (33.9, 35.8), "syria": (35, 38), "yemen": (15.5, 48), "north korea": (40, 127),
    "south korea": (36.5, 128), "japan": (36, 138), "india": (22, 79), "pakistan": (30, 70), "venezuela": (7, -66),
    "sudan": (15, 30), "nigeria": (9, 8), "turkey": (39, 35), "saudi": (24, 45), "germany": (51, 10), "france": (46.5, 2.5),
    "united kingdom": (54, -2), "australia": (-25, 134), "brazil": (-10, -55), "mexico": (23, -102), "canada": (56, -106),
    "washington": (38.9, -77), "european union": (50.8, 4.4), "eu ": (50.8, 4.4),
}


def locate(text: str) -> tuple[str, float, float] | None:
    low = f" {text.lower()} "
    for place, (lat, lon) in PLACES.items():
        if place in low:
            return place.strip().title(), lat, lon
    return None


async def gdelt_events() -> list[dict]:
    """One combined query. GDELT allows a request every 5 seconds, so nothing here fans out."""
    got = await get_fetcher().get("gdelt", GDELT, params={"query": f"{QUERY} sourcelang:english", "mode": "artlist", "maxrecords": 75,
                                                          "timespan": "3d", "format": "json", "sort": "datedesc"}, ttl=1800, attempts=1)
    if not got.body.lstrip().startswith("{"):
        raise SourceUnavailable("gdelt", got.body[:120])
    out = []
    for a in got.json().get("articles", []):
        place = locate(a.get("title", ""))
        out.append({"title": a.get("title"), "url": a.get("url"), "publisher": a.get("domain"), "theme": classify_theme(a.get("title", "")), "tier": "automated",
                    "time": a.get("seendate"), "place": place[0] if place else None, "lat": place[1] if place else None,
                    "lon": place[2] if place else None, "language": a.get("language")})
    return out


async def federal_register() -> list[dict]:
    agencies = {"foreign-assets-control-office": "sanctions", "industry-and-security-bureau": "export_controls"}
    out = []
    for agency, theme in agencies.items():
        got = await get_fetcher().get("federalregister", "https://www.federalregister.gov/api/v1/documents.json", params={
            "conditions[agencies][]": agency, "order": "newest", "per_page": 12,
            "fields[]": ["title", "html_url", "publication_date", "type", "abstract"]}, ttl=6 * 3600)
        for doc in got.json().get("results", []):
            place = locate(f"{doc.get('title', '')} {doc.get('abstract') or ''}")
            out.append({"title": doc["title"], "url": doc["html_url"], "publisher": "US Federal Register", "theme": theme, "tier": "official",
                        "time": doc["publication_date"], "place": place[0] if place else None, "lat": place[1] if place else None,
                        "lon": place[2] if place else None})
    return out


# -- Alternative attention -------------------------------------------------------------------------------

_TITLE = re.compile(r"^[\w ().,'&-]{1,80}$")


async def pageviews(article: str, days: int = 400) -> list[tuple[str, float]]:
    if not _TITLE.match(article):
        raise ValueError("Invalid article title")
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=days)
    title = article.replace(" ", "_").replace("/", "%2F")
    got = await get_fetcher().get("wikimedia", f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{title}/daily/{start:%Y%m%d}/{end:%Y%m%d}",
                                  headers={"User-Agent": "ATLAS/0.1 (open-source local terminal; https://www.mediawiki.org/wiki/Wikimedia_REST_API)"}, ttl=12 * 3600)
    return [(f"{i['timestamp'][:4]}-{i['timestamp'][4:6]}-{i['timestamp'][6:8]}", float(i["views"])) for i in got.json().get("items", [])]


def attention_stats(views: list[tuple[str, float]], returns: dict[str, float] | None = None) -> dict:
    values = np.array([v for _, v in views], dtype=float)
    if len(values) < 60:
        return {"available": False}
    log_v = np.log1p(values)
    base = log_v[-97:-7]
    z = (log_v[-7:].mean() - base.mean()) / max(float(base.std(ddof=1)), 0.05)
    result = {"available": True, "latest_date": views[-1][0], "views_7d_avg": round(float(values[-7:].mean())),
              "views_90d_avg": round(float(np.exp(base.mean()) - 1)), "z": round(float(z), 2)}
    if returns:
        pairs = [(math.log1p(v), abs(returns[d2])) for (d1, v), (d2, _) in zip(views, views[1:], strict=False) if d2 in returns]
        if len(pairs) >= 60:
            split = len(pairs) * 2 // 3
            a = np.array(pairs)
            result["validation"] = {"test": "corr(log views t, |return| t+1)", "in_sample": round(float(np.corrcoef(a[:split].T)[0, 1]), 3),
                                    "out_of_sample": round(float(np.corrcoef(a[split:].T)[0, 1]), 3), "n": len(pairs),
                                    "caveat": "Association with next-day volatility only; says nothing about direction."}
    return result
