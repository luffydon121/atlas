"""Impact Engine: real events, documented exposures, measured history. Nothing here predicts."""

import asyncio
import json
import logging
import math
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from atlas.connectors import calendar, econ, world, yahoo
from atlas.core import exposure
from atlas.core import reference as ref
from atlas.core.envelope import iso, utcnow
from atlas.core.memo import memo
from atlas.db import IntelEvent, session_scope
from atlas.services import eventstudy

log = logging.getLogger("atlas.impact")
SEVERITY = ["info", "watch", "elevated", "severe"]
CATEGORIES = {"extreme_weather": "Extreme weather", "natural_disaster": "Natural disaster", "wildfire": "Wildfire", "shipping": "Shipping", "agriculture": "Crop risk", "central_bank": "Central bank", "inflation": "Inflation",
              "regulatory": "Regulation", "geopolitical": "Geopolitics", "energy": "Energy", "industrial": "Industry", "earnings": "Earnings"}
NEAR_KM = 400
OBSERVED = "Observed price moves since the event. They may have other causes."
HYPOTHESIS = "Exposures are hypotheses from documented geography and business lines, not forecasts."


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def sites() -> list[dict]:
    out = [{"name": s["name"], "lat": s["lat"], "lon": s["lon"], "kind": s["kind"]} for s in ref.ENERGY_SITES + ref.INDUSTRIAL_SITES]
    out += [{"name": n, "lat": lat, "lon": lon, "kind": "port"} for n, lat, lon in ref.PORTS]
    out += [{"name": c["name"], "lat": c["lat"], "lon": c["lon"], "kind": "chokepoint"} for c in ref.CHOKEPOINTS]
    return out


def nearby(lat: float | None, lon: float | None, radius: float = NEAR_KM, limit: int = 8) -> list[dict]:
    if lat is None or lon is None:
        return []
    rows = sorted(({**s, "km": round(km(lat, lon, s["lat"], s["lon"]))} for s in sites()), key=lambda s: s["km"])
    return [s for s in rows if s["km"] <= radius][:limit]


def _time(raw: str | int | None) -> datetime:
    if isinstance(raw, str):
        text = raw.strip().replace("Z", "+00:00")
        for parser in (datetime.fromisoformat, lambda v: datetime.strptime(v[:15], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)):
            try:
                parsed = parser(text)
                return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed
            except ValueError:
                continue
    return utcnow()


def quake_severity(mag: float) -> str:
    return "severe" if mag >= 7.5 else "elevated" if mag >= 6.8 else "watch"


def storm_severity(knots: float | None) -> str:
    """Saffir-Simpson: 64 knots is a hurricane, 96 knots is major."""
    return "watch" if knots is None or knots < 64 else "severe" if knots >= 96 else "elevated"


def chokepoint_severity(pct: float) -> str:
    return "severe" if pct <= -50 else "elevated" if pct <= -10 else "watch"


def event(key: str, category: str, title: str, severity: str, verification: str, source: str, observed: datetime, lat=None, lon=None, region=None, url=None, **payload) -> dict:
    return {"key": key[:200], "category": category, "title": title, "severity": severity, "verification": verification, "source": source, "observed_at": observed, "lat": lat, "lon": lon, "region": region, "url": url, "payload": payload}


def from_quakes(rows: list[dict]) -> list[dict]:
    return [event(f"usgs:{q['id']}", "natural_disaster", q["title"], quake_severity(q["mag"]), "official", "usgs", _time(q["time"]), q["lat"], q["lon"], url=q["url"], magnitude=q["mag"], depth_km=q["depth_km"], tsunami=q["tsunami"])
            for q in rows if q.get("mag") and q["mag"] >= 6]


def from_storms(rows: list[dict]) -> list[dict]:
    out = []
    for s in rows:
        if s.get("lat") is None or s.get("lon") is None:
            continue
        out.append(event(f"nhc:{s['name']}", "extreme_weather", f"{s.get('class') or 'Tropical system'} {s['name']}", storm_severity(s.get("intensity_kt")), "official", "nhc", _time(s.get("time")), s["lat"], s["lon"], url=s.get("url"), intensity_kt=s.get("intensity_kt")))
    return out


def from_natural(rows: list[dict]) -> list[dict]:
    """NASA lists thousands of small fires, so only events near tracked infrastructure enter the feed."""
    out = []
    for e in rows:
        planned = "prescribed" in e["title"].lower() or " rx " in f" {e['title'].lower()} "
        if planned or not nearby(e["lat"], e["lon"], 150, 1):
            continue
        # Fires get their own category: being in a region does not put its oil platforms at risk.
        category = "wildfire" if e.get("category") == "Wildfires" else "natural_disaster"
        out.append(event(f"eonet:{e['id']}", category, e["title"], "watch", "official", "eonet", _time(e.get("time")), e["lat"], e["lon"], url=e.get("url"), eonet_category=e.get("category")))
    return out


def from_chokepoints(rows: list[dict]) -> list[dict]:
    out = []
    for c in rows:
        if c.get("disrupted"):
            out.append(event(f"portwatch:{c['id']}:{c['latest_date'][:7]}", "shipping", f"{c['name']} transits {c['pct_vs_baseline']:+.0f}% against a year ago", chokepoint_severity(c["pct_vs_baseline"]), "derived", "portwatch", _time(c["latest_date"]),
                             c["lat"], c["lon"], url="https://portwatch.imf.org", chokepoint=c["id"], transits_7d=c["transits_7d_avg"], baseline=c["baseline_avg"], z=c["z"]))
    return out


def from_weather(risks: dict[str, dict]) -> list[dict]:
    out = []
    for name, risk in risks.items():
        hot = [r for r in risk["regions"] if r.get("in_season", True) and r["risk"]["level"] in {"elevated", "watch"}]
        for r in hot:
            out.append(event(f"weather:{name}:{r['region']}:{r['stats'].get('window_end', '')[:7]}", "agriculture", f"{name.replace('_', ' ').title()}: {'; '.join(r['risk']['drivers'])}", "elevated" if r["risk"]["level"] == "elevated" else "watch", "derived", "openmeteo",
                             _time(r["stats"].get("window_end")), r["lat"], r["lon"], region=r["region"], crop=name))
    return out


def from_inflation() -> list[dict]:
    out = []
    for sid, region in (("us.cpi", "US"), ("au.cpi", "Australia"), ("ea.hicp", "Euro area")):
        rows = econ.history(sid)
        if len(rows) >= 2 and abs(rows[-1][1] - rows[-2][1]) >= 0.3:
            change = rows[-1][1] - rows[-2][1]
            out.append(event(f"inflation:{sid}:{rows[-1][0]}", "inflation", f"{region} inflation {rows[-1][1]:.1f}%, {change:+.1f} points on the prior print", "watch", "derived", "bls" if region == "US" else "rba" if region == "Australia" else "eurostat", _time(rows[-1][0]), region=region, latest=rows[-1][1], previous=rows[-2][1]))
    return out


def from_calendar(rows: list[dict], today: date) -> list[dict]:
    return [event(f"calendar:{e['date']}:{e['title']}", "central_bank", f"{e['title']} scheduled", "info", "official", "calendars", _time(e["date"]), region=e["region"], url=e["url"]) for e in calendar.upcoming(rows, today, 10)]


def from_register(rows: list[dict]) -> list[dict]:
    return [event(f"fr:{e['url']}", "regulatory", e["title"], "info", "official", "federalregister", _time(e["time"]), e.get("lat"), e.get("lon"), region=e.get("place"), url=e["url"], theme=e["theme"]) for e in rows[:12]]


def from_news(rows: list[dict]) -> list[dict]:
    return [event(f"gdelt:{e['url']}", "geopolitical", e["title"], "info", "unverified", "gdelt", _time(e.get("time")), e.get("lat"), e.get("lon"), region=e.get("place"), url=e["url"], publisher=e.get("publisher")) for e in rows[:10] if e.get("lat") is not None]


def save(rows: list[dict]) -> int:
    added = 0
    now = utcnow()
    with session_scope() as db:
        for row in rows:
            found = db.scalar(select(IntelEvent).where(IntelEvent.key == row["key"]))
            data = {**row, "payload": json.dumps(row["payload"], default=str)}
            if found:
                found.last_seen, found.severity, found.title, found.payload = now, row["severity"], row["title"], data["payload"]
            else:
                db.add(IntelEvent(**data, first_seen=now, last_seen=now))
                added += 1
    return added


async def collect() -> dict:
    """One failed feed never stops the others. Failures are reported, not hidden."""
    feeds = {"USGS": world.earthquakes(), "NOAA hurricanes": world.tropical_storms(), "NASA EONET": world.natural_events(), "Calendars": calendar.central_banks(), "Federal Register": world.federal_register(), "GDELT": world.gdelt_events()}
    results = await asyncio.gather(*feeds.values(), return_exceptions=True)
    got = dict(zip(feeds, results, strict=True))
    failed = [k for k, v in got.items() if isinstance(v, Exception)]
    ok = lambda k: [] if isinstance(got[k], Exception) else got[k]  # noqa: E731
    rows = from_quakes(ok("USGS")) + from_storms(ok("NOAA hurricanes")) + from_natural(ok("NASA EONET")) + from_register(ok("Federal Register")) + from_news(ok("GDELT"))
    if not isinstance(got["Calendars"], Exception):
        rows += from_calendar(got["Calendars"][0], date.today())
    rows += from_chokepoints(list(world.LATEST_CHOKEPOINTS.values())) + from_weather(world.LATEST_RISK) + from_inflation()
    return {"added": save(rows), "seen": len(rows), "failed": failed}


@memo(300)
async def refresh() -> dict:
    return await collect()


def to_dict(e: IntelEvent) -> dict:
    return {"id": e.id, "category": e.category, "category_label": CATEGORIES.get(e.category, e.category), "title": e.title, "severity": e.severity, "verification": e.verification, "region": e.region, "lat": e.lat, "lon": e.lon, "source": e.source, "url": e.url,
            "observed_at": iso(e.observed_at), "first_seen": iso(e.first_seen), "last_seen": iso(e.last_seen), "payload": json.loads(e.payload or "{}")}


def rules_for(e: dict) -> list[exposure.Rule]:
    p = e["payload"]
    return exposure.matching_rules(e["category"], e["lat"], e["lon"], p.get("chokepoint"), p.get("crop"), e["title"], e["region"])


def feed(days: int = 30, category: str | None = None, verification: str | None = None, limit: int = 100) -> list[dict]:
    stmt = select(IntelEvent).where(IntelEvent.last_seen >= utcnow() - timedelta(days=days))
    if category:
        stmt = stmt.where(IntelEvent.category == category)
    if verification:
        stmt = stmt.where(IntelEvent.verification == verification)
    with session_scope() as db:
        rows = [to_dict(e) for e in db.scalars(stmt.order_by(IntelEvent.observed_at.desc()).limit(500))]
    for row in rows:
        row["rules"] = [r.id for r in rules_for(row)]
        row["exposed"] = bool(row["rules"])
    rows.sort(key=lambda r: (SEVERITY.index(r["severity"]), r["exposed"], r["observed_at"]), reverse=True)
    return rows[:limit]


def describe(rules: list[exposure.Rule]) -> dict:
    assets, seen = [], set()
    for r in rules:
        for symbol, role in r.commodities:
            if symbol not in seen:
                seen.add(symbol)
                assets.append({"symbol": symbol, "role": role, "kind": "commodity", "rule": r.name})
        for symbol, role in r.companies:
            if symbol not in seen:
                seen.add(symbol)
                assets.append({"symbol": symbol, "role": role, "kind": "equity", "rule": r.name})
    return {"rules": [{"id": r.id, "name": r.name, "mechanism": r.mechanism, "uncertainty": r.uncertainty, "basis": r.basis} for r in rules], "industries": sorted({i for r in rules for i in r.industries}), "assets": assets,
            "analogues": exposure.analogues([r.id for r in rules]), "statement": HYPOTHESIS}


async def since(symbols: list[str], observed: datetime) -> list[dict]:
    """Real percentage moves since the event, for recent events only."""
    if (utcnow() - observed).days > 45:
        return []
    async def one(symbol: str):
        s = await yahoo.daily_history(symbol, (observed - timedelta(days=10)).date().isoformat())
        at = s.index.searchsorted(observed)
        base = s.iloc[max(at - 1, 0)]
        return {"symbol": symbol, "from": s.index[max(at - 1, 0)].strftime("%Y-%m-%d"), "to": s.index[-1].strftime("%Y-%m-%d"), "change": float(s.iloc[-1] / base - 1)}

    results = await asyncio.gather(*(one(s) for s in symbols[:10]), return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


async def detail(event_id: int) -> dict | None:
    with session_scope() as db:
        row = db.get(IntelEvent, event_id)
        if row is None:
            return None
        e = to_dict(row)
        observed = row.observed_at
    info = describe(rules_for(e))
    evidence = [{"label": e["title"], "source": e["source"], "time": e["observed_at"], "url": e["url"], "kind": "event"}] + [{"label": r["basis"], "source": "Reference note", "time": None, "url": None, "kind": "exposure basis"} for r in info["rules"] if r["basis"]]
    return {**e, **info, "nearby": nearby(e["lat"], e["lon"]), "observed_moves": await since([a["symbol"] for a in info["assets"]], observed), "observed_note": OBSERVED, "evidence": evidence}


@memo(3600)
async def _asset_study(symbol: str, dates: tuple[str, ...], kind: str, before: int, after: int) -> dict:
    series = await yahoo.daily_history(symbol)
    bench = await yahoo.daily_history("SPY") if kind == "equity" else None
    return eventstudy.study(series, list(dates), bench, before, after)


async def reactions(assets: list[dict], dates: list[str], before: int = 1, after: int = 10) -> dict:
    """Measures past windows for each asset, then corrects for testing many assets at once."""
    chosen = assets[:10]
    results = await asyncio.gather(*(_asset_study(a["symbol"], tuple(dates), a["kind"], before, after) for a in chosen), return_exceptions=True)
    rows, missing = [], []
    for a, r in zip(chosen, results, strict=True):
        if isinstance(r, Exception):
            missing.append(a["symbol"])
        else:
            rows.append({**a, **r})
    passed = eventstudy.benjamini_hochberg([r["p_value"] for r in rows])
    for row, ok in zip(rows, passed, strict=True):
        row["survives_correction"] = ok
    return {"rows": rows, "unavailable": missing, "window": [-before, after], "dates": dates,
            "note": "Past reactions around dated events, relative to a pre-event market model for shares and raw for commodities. Small samples. Other news may explain the moves, and this is not a forecast."}


def scenario(zone: str | None = None, crop: str | None = None, chokepoint: str | None = None) -> dict:
    """A what-if view. It uses no live event, and the page must say so."""
    categories = sorted({c for r in exposure.RULES for c in r.categories})
    rules: list[exposure.Rule] = []
    for c in categories:
        if zone:
            west, south, east, north = exposure.ZONES[zone]["bbox"]
            rules += exposure.matching_rules(c, (south + north) / 2, (west + east) / 2)
        if chokepoint:
            rules += exposure.matching_rules(c, chokepoint=chokepoint)
        if crop:
            rules += exposure.matching_rules(c, crop=crop)
    unique = list({r.id: r for r in rules}.values())
    return {"scenario": True, "statement": "This is a hypothetical scenario, not a live event.", **{k: v for k, v in describe(unique).items() if k != "statement"}, "zones": {k: v["name"] for k, v in exposure.ZONES.items()}}


def graph(query: str = "") -> dict:
    """Links between places, rules, commodities, industries and companies, all from documented rules."""
    nodes: dict[str, dict] = {}
    edges = []

    def node(key: str, label: str, kind: str) -> str:
        nodes.setdefault(key, {"id": key, "label": label, "kind": kind})
        return key

    for r in exposure.RULES:
        hub = node(f"theme:{r.id}", r.name, "theme")
        for z in r.zones:
            edges.append({"from": node(f"zone:{z}", exposure.ZONES[z]["name"], "region"), "to": hub, "label": "located in"})
        for c in r.chokepoints:
            edges.append({"from": node(f"choke:{c}", next(x["name"] for x in ref.CHOKEPOINTS if x["id"] == c), "chokepoint"), "to": hub, "label": "route"})
        for i in r.industries:
            edges.append({"from": hub, "to": node(f"industry:{i}", i, "industry"), "label": "affects"})
        for s, role in r.commodities:
            edges.append({"from": hub, "to": node(f"asset:{s}", f"{role} ({s})", "commodity"), "label": "commodity"})
        for s, role in r.companies:
            edges.append({"from": hub, "to": node(f"asset:{s}", s, "company"), "label": role})
    if not query:
        return {"nodes": list(nodes.values()), "edges": edges}
    q = query.lower()
    hits = {k for k, n in nodes.items() if q in n["label"].lower()}
    kept = [e for e in edges if e["from"] in hits or e["to"] in hits]
    ids = hits | {e["from"] for e in kept} | {e["to"] for e in kept}
    return {"nodes": [nodes[k] for k in ids], "edges": kept}


