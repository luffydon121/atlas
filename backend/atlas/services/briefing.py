"""Today: a plain-language summary built only from retrieved numbers."""

import asyncio
from datetime import date

from sqlalchemy import select

from atlas.connectors import calendar, crypto, econ, news, world, yahoo
from atlas.core import reference as ref
from atlas.core.errors import SourceUnavailable
from atlas.core.memo import memo
from atlas.db import Notification, Watchlist, session_scope


def _verb(change: float) -> str:
    return "rose" if change > 0 else "fell" if change < 0 else "was flat"


def phrase(label: str, q: dict | None) -> str | None:
    if not q or q.get("change_pct") is None:
        return None
    c = q["change_pct"]
    return f"{label} was flat" if abs(c) < 0.005 else f"{label} {_verb(c)} {abs(c):.2f}%"


def headline(quotes: dict[str, dict]) -> str:
    lead = [p for p in (phrase("The S&P 500", quotes.get("^GSPC")), phrase("the ASX 200", quotes.get("^AXJO"))) if p]
    rest = [p for p in (phrase("WTI crude", quotes.get("CL=F")), phrase("gold", quotes.get("GC=F")), phrase("Bitcoin", quotes.get("BTC-USD"))) if p]
    first = " and ".join(lead)
    sentences = [first[0].upper() + first[1:] + "." if first else ""]
    if rest:
        joined = ", ".join(rest[:-1]) + (" and " if len(rest) > 1 else "") + rest[-1]
        sentences.append(joined[0].upper() + joined[1:] + ".")
    return " ".join(s for s in sentences if s) or "Market data is unavailable right now."


def signals(quotes: dict[str, dict], watch: list[dict], curve: float | None, sentiment: dict | None) -> list[dict]:
    """Items that merit attention, each traceable to a number shown beside it."""
    out = []
    for c in world.LATEST_CHOKEPOINTS.values():
        if c.get("disrupted"):
            out.append({"severity": "serious", "area": "Shipping", "title": f"{c['name']} transits {c['pct_vs_baseline']:+.0f}%", "detail": f"{c['transits_7d_avg']} a day against a {c['baseline_avg']} baseline, to {c['latest_date']}", "href": "/transport"})
    for name, risk in world.LATEST_RISK.items():
        if risk["overall"] == "elevated":
            out.append({"severity": "warning", "area": "Weather", "title": f"{name.replace('_', ' ').title()} regions under stress", "detail": "Rain or temperature well outside the 10-year norm. Not a price forecast.", "href": "/weather"})
    vix = quotes.get("^VIX")
    if vix and vix.get("change_pct") is not None and abs(vix["change_pct"]) >= 8:
        out.append({"severity": "warning", "area": "Markets", "title": f"VIX {vix['change_pct']:+.1f}% to {vix['price']:.1f}", "detail": "A sharp move in implied volatility.", "href": "/chart?s=%5EVIX"})
    for q in watch:
        if q.get("change_pct") is not None and abs(q["change_pct"]) >= 3:
            out.append({"severity": "info", "area": "Watchlist", "title": f"{q['symbol']} {q['change_pct']:+.1f}%", "detail": f"Last {q['price']:,.2f} ({q['freshness']})", "href": f"/chart?s={q['symbol']}"})
    if curve is not None and curve < 0:
        out.append({"severity": "warning", "area": "Economy", "title": f"Yield curve inverted, 10Y-2Y {curve:.2f}", "detail": "Historically associated with slowdowns. Not a forecast.", "href": "/economy"})
    if sentiment and (sentiment["value"] <= 20 or sentiment["value"] >= 80):
        out.append({"severity": "info", "area": "Crypto", "title": f"Crypto sentiment: {sentiment['label']} ({sentiment['value']})", "detail": "Alternative.me Fear and Greed Index.", "href": "/crypto"})
    return out


@memo(45)
async def today() -> dict:
    watchlists: list[str] = []
    with session_scope() as db:
        for w in db.scalars(select(Watchlist).order_by(Watchlist.id)):
            watchlists += [i.symbol for i in w.items]
        alerts = [{"title": n.title, "body": n.body, "severity": n.severity} for n in db.scalars(select(Notification).order_by(Notification.created_at.desc()).limit(4))]
    watchlists = list(dict.fromkeys(watchlists))[:20]
    labels = ref.INDICES | ref.RATES_VOL | ref.COMMODITIES | ref.CRYPTO | ref.FX
    headline_set = ["^GSPC", "^IXIC", "^AXJO", "^N225", "^FTSE", "^VIX", "CL=F", "GC=F", "BTC-USD", "ETH-USD", "AUDUSD=X", "^TNX"]
    market, watch = await asyncio.gather(yahoo.quotes(headline_set), yahoo.quotes(watchlists) if watchlists else asyncio.sleep(0, {"quotes": []}))
    quotes = {q["symbol"]: {**q, "label": labels.get(q["symbol"], q["symbol"])} for q in market["quotes"]}
    curve, sentiment = None, None
    try:
        y10, y2 = econ.history("us.y10"), econ.history("us.y2")
        if y10 and y2:
            curve = round(y10[-1][1] - y2[-1][1], 2)
    except SourceUnavailable:
        pass
    try:
        sentiment = await crypto.fear_greed()
    except SourceUnavailable:
        pass
    events, _ = await calendar.central_banks()
    return {"date": date.today().isoformat(), "headline": headline(quotes), "markets": [quotes[s] for s in headline_set if s in quotes],
            "watchlist": sorted(watch["quotes"], key=lambda q: abs(q.get("change_pct") or 0), reverse=True)[:6],
            "signals": signals(quotes, watch["quotes"], curve, sentiment)[:8], "alerts": alerts, "news": news.latest(8), "events": calendar.upcoming(events, date.today())[:4], "sentiment": sentiment}
