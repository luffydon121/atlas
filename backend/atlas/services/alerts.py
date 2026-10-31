"""Alert engine. Evaluation reuses cached fetches, so alerts add little load on providers."""

import asyncio
import json
import logging
import subprocess
from datetime import date, timedelta

from sqlalchemy import select

from atlas.config import get_settings
from atlas.connectors import econ, sec, world, yahoo
from atlas.core.envelope import utcnow
from atlas.core.errors import SourceUnavailable
from atlas.core.reference import CHOKEPOINTS, SATELLITE_AOIS, WEATHER_REGIONS
from atlas.db import Alert, Notification, session_scope
from atlas.services import satellite

log = logging.getLogger("atlas.alerts")
KINDS = {
    "price_above": "Price rises above threshold", "price_below": "Price falls below threshold", "pct_move": "Daily move exceeds threshold %",
    "volume_spike": "Volume exceeds threshold x 20-day average", "new_filing": "New SEC filing", "series_change": "Economic series prints a new value",
    "chokepoint_drop": "Chokepoint transits fall below baseline by threshold %", "commodity_weather": "Commodity weather screen turns elevated",
    "earthquake": "Earthquake at or above magnitude threshold", "satellite_change": "Satellite area changes by threshold % of pixels",
}


class Outcome:
    def __init__(self, fired: bool, title: str = "", body: str = "", severity: str = "info", state: dict | None = None):
        self.fired, self.title, self.body, self.severity, self.state = fired, title, body, severity, state


async def _price(a: dict, state: dict) -> Outcome:
    q = await yahoo.quote_for(a["target"])
    price, th = q["price"], a["threshold"]
    if a["kind"] == "pct_move":
        chg = q.get("change_pct")
        return Outcome(chg is not None and abs(chg) >= th, f"{a['target']} moved {chg or 0:+.2f}%", f"Last {price:,.2f} ({q['freshness']})", "warning")
    hit = price >= th if a["kind"] == "price_above" else price <= th
    # Fire on the crossing, not on every check while the level stays breached.
    fired = hit and not state.get("hit")
    verb = "above" if a["kind"] == "price_above" else "below"
    return Outcome(fired, f"{a['target']} {verb} {th:,.2f}", f"Last {price:,.2f} ({q['freshness']})", "warning", {"hit": hit})


async def _volume(a: dict, _state: dict) -> Outcome:
    bars = (await yahoo.chart(a["target"], "3mo", "1d"))["bars"]
    vols = [b["volume"] for b in bars if b.get("volume")]
    if len(vols) < 21:
        return Outcome(False)
    ratio = vols[-1] / (sum(vols[-21:-1]) / 20)
    return Outcome(ratio >= a["threshold"], f"{a['target']} volume {ratio:.1f}x average", "Compared with the prior 20 sessions", "warning")


async def _filing(a: dict, state: dict) -> Outcome:
    info = await sec.resolve(a["target"])
    filings = sec.recent_filings((await sec.submissions(info["cik"])).json(), limit=1)
    if not filings:
        return Outcome(False)
    latest = filings[0]
    seen = state.get("accession")
    return Outcome(seen is not None and latest["accession"] != seen, f"{a['target']} filed {latest['form']}", f"Filed {latest['filed']}: {latest['url']}", "info", {"accession": latest["accession"]})


async def _series(a: dict, state: dict) -> Outcome:
    series = econ.BY_ID.get(a["target"])
    if series is None:
        raise SourceUnavailable("econ", f"Unknown series {a['target']}")
    rows = (await econ.load(series))[0]
    if not rows:
        return Outcome(False)
    period, value = rows[-1]
    seen = state.get("period")
    return Outcome(seen is not None and period != seen, f"{series.name} ({series.region}): {value:g} {series.unit}", f"Period {period}", "info", {"period": period})


async def _chokepoint(a: dict, _state: dict) -> Outcome:
    cps = [c for c in CHOKEPOINTS if a["target"] in ("any", c["id"])]
    hits = []
    for cp in cps:
        row = await world.chokepoint(cp)
        if row.get("available") and row["pct_vs_baseline"] <= -abs(a["threshold"]):
            hits.append(f"{row['name']} {row['pct_vs_baseline']:+.1f}%")
    return Outcome(bool(hits), "Chokepoint transits below baseline", "; ".join(hits), "warning")


async def _weather(a: dict, state: dict) -> Outcome:
    if a["target"] not in WEATHER_REGIONS:
        raise SourceUnavailable("openmeteo", f"Unknown commodity {a['target']}")
    r = await world.commodity_risk(a["target"])
    level = r["overall"]
    return Outcome(level == "elevated" and state.get("level") != "elevated", f"{a['target'].title()} weather screen elevated", "A weather anomaly does not imply a price move.", "warning", {"level": level})


async def _quake(a: dict, state: dict) -> Outcome:
    quakes = [q for q in await world.earthquakes() if q["mag"] and q["mag"] >= a["threshold"]]
    if not quakes:
        return Outcome(False)
    latest = max(quakes, key=lambda q: q["time"])
    seen = state.get("id")
    return Outcome(seen is not None and latest["id"] != seen, latest["title"], latest["time"], "warning", {"id": latest["id"]})


async def _satellite(a: dict, state: dict) -> Outcome:
    aoi = next((x for x in SATELLITE_AOIS if x["id"] == a["target"]), None)
    if aoi is None:
        raise SourceUnavailable("earthsearch", f"Unknown area {a['target']}")
    today = date.today()
    found = await satellite.search(aoi["bbox"], (today - timedelta(days=120)).isoformat(), today.isoformat(), max_cloud=10, limit=30)
    scenes = found["scenes"]
    if len(scenes) < 2 or scenes[0]["id"] == state.get("scene"):
        return Outcome(False)
    latest, earlier = scenes[0], next((s for s in scenes[1:] if s["acquired_at"][:7] != scenes[0]["acquired_at"][:7]), scenes[-1])
    after, before = await asyncio.gather(*(asyncio.to_thread(satellite.compute_index, s, aoi["bbox"], aoi["index"]) for s in (latest, earlier)))
    stats = satellite.change_stats(before, after)
    changed = stats.get("pct_increased", 0) + stats.get("pct_decreased", 0)
    fired = stats["confidence"] in {"high", "medium"} and changed >= a["threshold"]
    return Outcome(fired, f"{aoi['name']}: {changed:.1f}% of pixels changed", f"{earlier['acquired_at'][:10]} to {latest['acquired_at'][:10]}, confidence {stats['confidence']}. Season and light can also cause change.", "info", {"scene": latest["id"]})


HANDLERS = {"price_above": _price, "price_below": _price, "pct_move": _price, "volume_spike": _volume, "new_filing": _filing,
            "series_change": _series, "chokepoint_drop": _chokepoint, "commodity_weather": _weather, "earthquake": _quake, "satellite_change": _satellite}


def _macos_notify(title: str, body: str) -> None:
    def esc(s: str) -> str:
        return s.replace("\\", "").replace('"', "'")[:180]

    subprocess.run(["/usr/bin/osascript", "-e", f'display notification "{esc(body)}" with title "ATLAS" subtitle "{esc(title)}"'], check=False, timeout=5)  # noqa: S603


async def evaluate_one(alert_id: int) -> bool:
    with session_scope() as db:
        alert = db.get(Alert, alert_id)
        if alert is None or not alert.enabled:
            return False
        spec = {"kind": alert.kind, "target": alert.target, "threshold": alert.threshold}
        state = json.loads(alert.last_state or "{}")
        last_fired, cooldown = alert.last_fired, alert.cooldown_minutes
    try:
        outcome = await HANDLERS[spec["kind"]](spec, state)
        error = None
    except SourceUnavailable as exc:
        outcome, error = Outcome(False), exc.reason
    now = utcnow()
    cooling = last_fired is not None and now - last_fired < timedelta(minutes=cooldown)
    fire = outcome.fired and not cooling
    with session_scope() as db:
        alert = db.get(Alert, alert_id)
        alert.last_checked, alert.last_error = now, error
        if outcome.state is not None:
            alert.last_state = json.dumps({**state, **outcome.state})
        if fire:
            alert.last_fired = now
            db.add(Notification(alert_id=alert_id, title=outcome.title, body=outcome.body, severity=outcome.severity))
    if fire and get_settings().macos_notifications:
        await asyncio.to_thread(_macos_notify, outcome.title, outcome.body)
    return fire


async def evaluate_all() -> int:
    with session_scope() as db:
        ids = list(db.scalars(select(Alert.id).where(Alert.enabled)))
    return sum([await evaluate_one(i) for i in ids])
