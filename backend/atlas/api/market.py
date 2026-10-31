import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.api.deps import Symbol, SymbolList, split_symbols
from atlas.connectors import yahoo
from atlas.core import reference as ref
from atlas.core.envelope import Freshness, envelope
from atlas.core.errors import SourceUnavailable
from atlas.core.memo import memo
from atlas.db import Watchlist, WatchlistItem, get_db
from atlas.services import analytics

router = APIRouter(prefix="/api", tags=["market"])
GROUPS = {"indices": ref.INDICES, "rates": ref.RATES_VOL, "fx": ref.FX, "commodities": ref.COMMODITIES, "crypto": ref.CRYPTO, "sectors": ref.SECTORS}


def _named(result: dict, names: dict[str, str]) -> list[dict]:
    return [{**q, "label": names.get(q["symbol"], q.get("name") or q["symbol"])} for q in result["quotes"]]


@router.get("/search")
async def search(q: str = Query(min_length=1, max_length=60)):
    q_low = q.lower()
    local = [{"symbol": t, "name": n, "exchange": "US", "type": "EQUITY", "sector": s} for t, (_, n, s) in ref.LARGE_CAPS.items()
             if q_low in n.lower() or t.lower().startswith(q_low)]
    groups = [(ref.INDICES, "INDEX"), (ref.COMMODITIES, "FUTURE"), (ref.FX, "CURRENCY"), (ref.CRYPTO, "CRYPTOCURRENCY"), (ref.SECTORS, "ETF")]
    local += [{"symbol": s, "name": n, "exchange": "", "type": t, "sector": None} for g, t in groups for s, n in g.items()
              if q_low in n.lower() or q_low in s.lower()]
    note = None
    try:
        remote = await yahoo.search(q)
    except SourceUnavailable as exc:
        remote, note = [], f"Global search unavailable ({exc.reason}); showing the built-in list."
    seen, rows = set(), []
    for row in local + remote:
        if row["symbol"] not in seen:
            seen.add(row["symbol"])
            rows.append(row)
    return envelope(rows[:15], source=["yahoo"], freshness=Freshness.REFERENCE, note=note)


@memo(30)
async def _overview_quotes() -> dict:
    return await yahoo.quotes([s for g in GROUPS.values() for s in g])


async def _overview(groups: dict) -> dict:
    result = await _overview_quotes()
    by_symbol = {q["symbol"]: q for q in result["quotes"]}
    data = {k: _named({"quotes": [by_symbol[s] for s in g if s in by_symbol]}, g) for k, g in groups.items()}
    missing = result["unavailable"]
    return envelope(data, source="yahoo", freshness=Freshness.DELAYED, note=f"Unavailable: {', '.join(missing)}" if missing else "Delayed by the provider, typically 15+ minutes.")


@router.get("/market/overview")
async def overview():
    groups = GROUPS
    return await _overview(groups)


@router.get("/market/quotes")
async def quotes(symbols: SymbolList):
    result = await yahoo.quotes(split_symbols(symbols))
    return envelope(result, source="yahoo", freshness=Freshness.DELAYED)


@router.get("/market/bars/{symbol}")
async def bars(symbol: Symbol, range: str = Query("1y"), interval: str = Query("1d")):
    if range not in yahoo.RANGES or interval not in yahoo.INTERVALS:
        raise HTTPException(422, "Unsupported range or interval")
    parsed = await yahoo.chart(symbol.upper(), range, interval)
    s = analytics.closes(parsed["bars"]) if interval in {"1d", "1wk", "1mo"} else None
    out = yahoo.chart_envelope(parsed)
    if s is not None and len(s):
        out["data"]["returns"] = analytics.trailing_returns(s) if interval == "1d" else None
        out["data"]["vol_30d"] = analytics.realised_vol(s) if interval == "1d" else None
    return out


@router.get("/market/indicators/{symbol}")
async def indicators(symbol: Symbol, range: str = "2y", interval: str = "1d"):
    if range not in yahoo.RANGES or interval not in {"1d", "1wk", "1mo"}:
        raise HTTPException(422, "Indicators need daily, weekly or monthly bars")
    parsed = await yahoo.chart(symbol.upper(), range, interval)
    stamps = {b["time"]: b for b in parsed["bars"]}
    times = list(stamps)
    import pandas as pd

    s = pd.Series([stamps[t]["close"] for t in times], index=times, dtype=float)

    def line(series):
        return [{"time": int(t), "value": float(v)} for t, v in series.dropna().items()]

    m, b = analytics.macd(s), analytics.bollinger(s)
    data = {"sma20": line(analytics.sma(s, 20)), "sma50": line(analytics.sma(s, 50)), "sma200": line(analytics.sma(s, 200)), "ema20": line(analytics.ema(s, 20)),
            "rsi14": line(analytics.rsi(s)), "macd": line(m["macd"]), "macd_signal": line(m["signal"]), "macd_hist": line(m["hist"]),
            "bb_upper": line(b["upper"]), "bb_lower": line(b["lower"])}
    return envelope(data, source="yahoo", freshness=Freshness.ESTIMATED, fetched_at=parsed.get("_fetched"), note="Calculated locally from provider bars.")


@router.get("/market/compare")
async def compare(symbols: SymbolList, range: str = "1y"):
    if range not in yahoo.RANGES:
        raise HTTPException(422, "Unsupported range")
    names = split_symbols(symbols)
    parsed = await asyncio.gather(*(yahoo.chart(s, range, "1d") for s in names), return_exceptions=True)
    frames = {n: analytics.closes(p["bars"]) for n, p in zip(names, parsed, strict=True) if not isinstance(p, Exception) and p["bars"]}
    if len(frames) < 1:
        raise SourceUnavailable("yahoo", "No price history for the requested symbols")
    start = max(s.index[0] for s in frames.values())
    series = []
    for name, s in frames.items():
        s = s[s.index >= start]
        series.append({"symbol": name, "points": [{"date": d.strftime("%Y-%m-%d"), "value": float(v / s.iloc[0] * 100)} for d, v in s.items()], "return": float(s.iloc[-1] / s.iloc[0] - 1), "vol_30d": analytics.realised_vol(s)})
    corr = analytics.correlation(frames).round(3)
    return envelope({"series": series, "correlation": {"symbols": list(corr.columns), "matrix": [[None if v != v else v for v in row] for row in corr.values.tolist()]},
                     "unavailable": [n for n in names if n not in frames]},
                    source="yahoo", freshness=Freshness.HISTORICAL, note="Indexed to 100 at the first common date. Correlation uses daily returns.")


@memo(300)
async def _universe() -> tuple[list[dict], list[str]]:
    symbols = list(ref.LARGE_CAPS)
    parsed = await asyncio.gather(*(yahoo.chart(s, "2y", "1d") for s in symbols), return_exceptions=True)
    rows, missing = [], []
    for symbol, p in zip(symbols, parsed, strict=True):
        row = None if isinstance(p, Exception) else analytics.screen_row(symbol, ref.LARGE_CAPS[symbol][1], ref.LARGE_CAPS[symbol][2], p["bars"])
        (rows.append(row) if row else missing.append(symbol))
    return rows, missing


@router.get("/market/screener")
async def screener():
    rows, missing = await _universe()
    return envelope({"rows": rows, "breadth": analytics.breadth(rows), "unavailable": missing}, source="yahoo", freshness=Freshness.DELAYED,
                    note="Universe is a fixed list of today's US large caps, so it has survivorship bias. Market breadth is for this list only.")


@router.get("/watchlists")
def list_watchlists(db: Session = Depends(get_db)):
    return [{"id": w.id, "name": w.name, "symbols": [i.symbol for i in w.items]} for w in db.scalars(select(Watchlist).order_by(Watchlist.id))]


class WatchlistIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ItemIn(BaseModel):
    symbol: str = Field(pattern=r"^[A-Za-z0-9.^=\-]{1,20}$")


@router.post("/watchlists", status_code=201)
def create_watchlist(body: WatchlistIn, db: Session = Depends(get_db)):
    if db.scalar(select(Watchlist).where(Watchlist.name == body.name)):
        raise HTTPException(409, "A watchlist with that name exists")
    w = Watchlist(name=body.name)
    db.add(w)
    db.flush()
    return {"id": w.id, "name": w.name, "symbols": []}


@router.delete("/watchlists/{wid}", status_code=204)
def delete_watchlist(wid: int, db: Session = Depends(get_db)):
    w = db.get(Watchlist, wid)
    if not w:
        raise HTTPException(404, "Not found")
    db.delete(w)


@router.post("/watchlists/{wid}/items", status_code=201)
def add_item(wid: int, body: ItemIn, db: Session = Depends(get_db)):
    w = db.get(Watchlist, wid)
    if not w:
        raise HTTPException(404, "Not found")
    symbol = body.symbol.upper()
    if symbol not in [i.symbol for i in w.items]:
        w.items.append(WatchlistItem(symbol=symbol, position=len(w.items)))
    return {"symbols": [i.symbol for i in w.items]}


class OrderIn(BaseModel):
    symbols: list[str] = Field(max_length=200)


@router.put("/watchlists/{wid}/order")
def reorder(wid: int, body: OrderIn, db: Session = Depends(get_db)):
    w = db.get(Watchlist, wid)
    if not w:
        raise HTTPException(404, "Not found")
    rank = {s: i for i, s in enumerate(body.symbols)}
    for item in w.items:
        item.position = rank.get(item.symbol, len(rank))
    return {"ok": True}


@router.delete("/watchlists/{wid}/items/{symbol}", status_code=204)
def remove_item(wid: int, symbol: Symbol, db: Session = Depends(get_db)):
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.watchlist_id == wid, WatchlistItem.symbol == symbol.upper()))
    if item:
        db.delete(item)
