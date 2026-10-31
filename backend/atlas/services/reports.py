"""Intelligence briefings. Every line comes from retrieved data, and gaps are stated."""

import asyncio
import html
import re
from datetime import timedelta

from sqlalchemy import select

from atlas.config import get_settings
from atlas.connectors import econ, news, world, yahoo
from atlas.core import exposure
from atlas.core import reference as ref
from atlas.core.envelope import iso, utcnow
from atlas.core.errors import SourceUnavailable
from atlas.db import Briefing, session_scope
from atlas.services import impact

COUNTRIES = {"US": "US", "Australia": "Australia", "Euro area": "Euro area"}
COMMODITY_NAMES = {v.lower(): k for k, v in ref.COMMODITIES.items()} | {"oil": "CL=F", "crude": "CL=F", "gas": "NG=F"}
LEAD = {"^GSPC": "S&P 500", "^AXJO": "ASX 200", "^FTSE": "FTSE 100", "^N225": "Nikkei 225", "CL=F": "WTI crude", "GC=F": "Gold", "BTC-USD": "Bitcoin", "^VIX": "VIX"}


def read_only() -> bool:
    return get_settings().public_read_only


def line(label: str, q: dict) -> str:
    change = "n/a" if q.get("change_pct") is None else f"{q['change_pct']:+.2f}%"
    return f"- {label}: {q['price']:,.2f}, {change} ({q['freshness']}, as of {q.get('as_of') or 'unknown'})"


async def _markets(unavailable: list[str]) -> list[str]:
    try:
        result = await yahoo.quotes(list(LEAD))
    except SourceUnavailable:
        unavailable.append("Market prices")
        return ["No market data was available."]
    unavailable += [f"Price for {s}" for s in result["unavailable"]]
    return [line(LEAD[q["symbol"]], q) for q in result["quotes"]]


def _economy(regions: list[str], since) -> list[str]:
    out = []
    for s in econ.CATALOG:
        if s.region in regions and s.source != "fred":
            rows = econ.history(s.id)
            if len(rows) >= 2:
                out.append(f"- {s.region} {s.name}: {rows[-1][1]:g} {s.unit} for {rows[-1][0]} (previous {rows[-2][1]:g}, source {s.source})")
    return out or ["No stored economic readings yet."]


def _events(days: int, keep=None) -> list[str]:
    rows = [e for e in impact.feed(days) if e["severity"] != "info" and (keep is None or keep(e))][:10]
    return [f"- [{e['verification']}] {e['title']} ({e['observed_at'][:10]}, {e['source']})" for e in rows] or ["No notable events in the connected feeds."]


def _shipping() -> list[str]:
    rows = [c for c in world.LATEST_CHOKEPOINTS.values() if c.get("available")]
    return [f"- {c['name']}: {c['transits_7d_avg']} transits a day, {c['pct_vs_baseline']:+.1f}% against the year, to {c['latest_date']}" for c in sorted(rows, key=lambda c: c["pct_vs_baseline"])[:5]] or ["Chokepoint data has not loaded yet."]


def _crops() -> list[str]:
    rows = [f"- {k.replace('_', ' ').title()}: {v['overall']}" for k, v in world.LATEST_RISK.items()]
    return rows or ["Crop weather baselines have not loaded yet."]


def _headlines(q: str | None = None) -> list[str]:
    rows = news.latest(6, None, q)
    return [f"- {r['publisher']}: {r['title']}" for r in rows] or ["No matching headlines stored."]


async def _symbol_section(symbol: str, label: str, unavailable: list[str]) -> list[str]:
    try:
        q = await yahoo.quote_for(symbol)
        s = await yahoo.daily_history(symbol, str((utcnow() - timedelta(days=45)).date()))
    except SourceUnavailable:
        unavailable.append(f"Price for {symbol}")
        return ["No price data was available."]
    month = (s.iloc[-1] / s.iloc[0] - 1) * 100 if len(s) > 1 else None
    return [line(label, q), f"- Change since {s.index[0]:%Y-%m-%d}: {month:+.2f}%" if month is not None else "- No recent history."]


def _themes(symbol: str) -> list[str]:
    hits = [r for r in exposure.RULES if symbol in {s for s, _ in r.commodities + r.companies}]
    return [f"- {r.name}: {r.mechanism} Uncertainty: {r.uncertainty}" for r in hits] or ["No documented exposure themes."]


async def build(kind: str, subject: str | None) -> tuple[str, list[str]]:
    now = utcnow()
    days = 7 if kind == "weekly" else 1
    gaps: list[str] = []
    if kind in {"daily", "weekly"}:
        title = f"{'Weekly' if kind == 'weekly' else 'Daily'} intelligence briefing"
        sections = [("Financial markets", await _markets(gaps)), ("Economic indicators", _economy(list(COUNTRIES), now)), ("Global events", _events(max(days, 3))), ("Shipping", _shipping()), ("Commodity supply risks", _crops()), ("Headlines", _headlines())]
    elif kind == "asset":
        symbol = (subject or "").upper()
        if not re.fullmatch(r"[A-Z0-9.^=\-]{1,20}", symbol):
            raise ValueError("Enter a symbol")
        title = f"Asset briefing: {symbol}"
        sections = [("Price", await _symbol_section(symbol, symbol, gaps)), ("Documented exposures", _themes(symbol)), ("Headlines", _headlines(symbol))]
    elif kind == "country":
        if subject not in COUNTRIES:
            raise ValueError(f"Choose one of: {', '.join(COUNTRIES)}")
        title = f"Country briefing: {subject}"
        sections = [("Economic indicators", _economy([subject], now)), ("Global events", _events(7, lambda e: e["region"] == subject)), ("Headlines", _headlines(subject))]
    else:
        name = (subject or "").lower()
        symbol = COMMODITY_NAMES.get(name)
        if not symbol:
            raise ValueError("Choose a commodity, such as oil, gold or coffee")
        title = f"Commodity briefing: {subject}"
        rules = {r.id for r in exposure.RULES if symbol in {s for s, _ in r.commodities}}
        sections = [("Price", await _symbol_section(symbol, subject, gaps)), ("Documented exposures", _themes(symbol)), ("Related events", _events(14, lambda e: bool(set(e["rules"]) & rules))), ("Headlines", _headlines(name))]
    start = now - timedelta(days=days)
    body = [f"# {title}", "", f"Period covered: {start:%Y-%m-%d %H:%M} to {now:%Y-%m-%d %H:%M} UTC.", "", "Written from retrieved data by fixed rules. Not investment advice.", ""]
    for heading, rows in sections:
        body += [f"## {heading}", *rows, ""]
    body += ["## Unavailable feeds", *([f"- {g}" for g in gaps] or ["- None at the time of writing."]), ""]
    return "\n".join(body), gaps


def _row(b: Briefing) -> dict:
    return {"id": b.id, "kind": b.kind, "subject": b.subject, "title": b.markdown.splitlines()[0].lstrip("# "), "created_at": iso(b.created_at), "period_start": iso(b.period_start), "period_end": iso(b.period_end), "markdown": b.markdown}


async def generate(kind: str = "daily", subject: str | None = None, save: bool = True) -> dict:
    await asyncio.sleep(0)
    text, _gaps = await build(kind, subject)
    now = utcnow()
    item = Briefing(kind=kind, subject=subject, period_start=now - timedelta(days=7 if kind == "weekly" else 1), period_end=now, markdown=text, created_at=now)
    if not save:
        return _row(item) | {"id": None}
    with session_scope() as db:
        db.add(item)
        db.flush()
        return _row(item)


def recent(limit: int = 30) -> list[dict]:
    with session_scope() as db:
        return [{k: v for k, v in _row(b).items() if k != "markdown"} for b in db.scalars(select(Briefing).order_by(Briefing.created_at.desc()).limit(limit))]


def get(briefing_id: int) -> dict | None:
    with session_scope() as db:
        b = db.get(Briefing, briefing_id)
        return _row(b) if b else None


def latest() -> dict | None:
    with session_scope() as db:
        b = db.scalar(select(Briefing).where(Briefing.kind == "daily", Briefing.created_at >= utcnow() - timedelta(hours=24)).order_by(Briefing.created_at.desc()).limit(1))
        return _row(b) if b else None


def to_html(markdown: str, title: str) -> str:
    """All retrieved text is escaped, so a feed can never inject markup into an export."""
    out, in_list = [], False
    for raw in markdown.splitlines():
        text = html.escape(raw)
        if text.startswith("- ") and not in_list:
            out.append("<ul>")
            in_list = True
        if not text.startswith("- ") and in_list:
            out.append("</ul>")
            in_list = False
        if text.startswith("# "):
            out.append(f"<h1>{text[2:]}</h1>")
        elif text.startswith("## "):
            out.append(f"<h2>{text[3:]}</h2>")
        elif text.startswith("- "):
            out.append(f"<li>{text[2:]}</li>")
        elif text:
            out.append(f"<p>{text}</p>")
    if in_list:
        out.append("</ul>")
    style = "body{font:15px/1.5 -apple-system,sans-serif;max-width:720px;margin:40px auto;padding:0 20px;color:#1d1d1f}h1{font-size:30px}h2{font-size:19px;margin-top:28px}"
    return f"<!doctype html><html lang='en'><meta charset='utf-8'><title>{html.escape(title)}</title><style>{style}</style><body>{''.join(out)}</body></html>"
