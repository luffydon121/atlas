"""Prices from Yahoo's public chart endpoint. Stored locally so history survives outages."""

import asyncio
from datetime import UTC, datetime
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from atlas.core.envelope import Freshness, envelope, iso
from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import get_fetcher
from atlas.db import Bar, session_scope

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/"
SPARK = "https://query1.finance.yahoo.com/v7/finance/spark"
SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; ATLAS local terminal)"}
INTERVALS = {"1m", "5m", "15m", "1h", "1d", "1wk", "1mo"}
RANGES = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}
_POOL = asyncio.Semaphore(4)
SPARK_LIMIT = 20


def _ttl(interval: str) -> int:
    return 120 if interval in {"1m", "5m", "15m", "1h"} else 900


def parse_chart(payload: dict) -> dict:
    chart = payload.get("chart") or {}
    if chart.get("error") or not chart.get("result"):
        raise ValueError((chart.get("error") or {}).get("description") or "symbol not found")
    result = chart["result"][0]
    meta = result["meta"]
    stamps = result.get("timestamp") or []
    q = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = ((result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")) or []
    bars = []
    daily = meta.get("dataGranularity") in {"1d", "5d", "1wk", "1mo", "3mo"}
    for i, ts in enumerate(stamps):
        close = q["close"][i] if q.get("close") else None
        if close is None:
            continue
        bar = {"time": ts, "open": q["open"][i], "high": q["high"][i], "low": q["low"][i],
               "close": close, "volume": (q.get("volume") or [None] * len(stamps))[i]}
        if i < len(adjusted) and adjusted[i] is not None:
            bar["adjclose"] = adjusted[i]
        # Daily data often ends with a second bar stamped at the last trade for the same session.
        if daily and bars and ts - bars[-1]["time"] < 72_000:
            bars[-1] = {**bars[-1], **{k: v for k, v in bar.items() if k != "time" and v is not None}}
            continue
        bars.append(bar)
    events = result.get("events") or {}
    dividends = sorted(({"time": v["date"], "amount": v["amount"]} for v in (events.get("dividends") or {}).values()),
                       key=lambda d: d["time"])
    splits = sorted(({"time": v["date"], "ratio": f"{v['numerator']:g}:{v['denominator']:g}"}
                     for v in (events.get("splits") or {}).values()), key=lambda d: d["time"])
    return {"meta": {"symbol": meta.get("symbol"), "name": meta.get("longName") or meta.get("shortName"),
                     "currency": meta.get("currency"), "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
                     "type": meta.get("instrumentType"), "timezone": meta.get("exchangeTimezoneName"),
                     "price": meta.get("regularMarketPrice"), "market_time": meta.get("regularMarketTime"),
                     "day_high": meta.get("regularMarketDayHigh"), "day_low": meta.get("regularMarketDayLow"),
                     "volume": meta.get("regularMarketVolume"), "high_52w": meta.get("fiftyTwoWeekHigh"),
                     "low_52w": meta.get("fiftyTwoWeekLow"), "prev_close": meta.get("chartPreviousClose")},
            "bars": bars, "dividends": dividends, "splits": splits}


def _store(symbol: str, interval: str, bars: list[dict]) -> None:
    if not bars or interval not in {"1d", "1wk", "1mo"}:
        return
    rows = [{"symbol": symbol, "interval": interval, "ts": b["time"], "open": b["open"], "high": b["high"],
             "low": b["low"], "close": b["close"], "volume": b["volume"], "source": "yahoo"} for b in bars]
    with session_scope() as db:
        for start in range(0, len(rows), 400):
            stmt = insert(Bar).values(rows[start:start + 400])
            db.execute(stmt.on_conflict_do_update(
                index_elements=["symbol", "interval", "ts"],
                set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "volume")}))


def stored_bars(symbol: str, interval: str) -> list[dict]:
    with session_scope() as db:
        rows = db.scalars(select(Bar).where(Bar.symbol == symbol, Bar.interval == interval).order_by(Bar.ts)).all()
    return [{"time": r.ts, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume}
            for r in rows]


async def chart(symbol: str, range_: str = "1y", interval: str = "1d", ttl: int | None = None) -> dict:
    """Returns the parsed chart, adding `_fetched`. Falls back to locally stored bars."""
    params = {"range": range_, "interval": interval, "events": "div,split", "includePrePost": "false"}
    url = CHART + quote(symbol, safe="")
    try:
        async with _POOL:
            got = await get_fetcher().get("yahoo", url, params=params, headers=HEADERS, ttl=ttl or _ttl(interval))
        parsed = parse_chart(got.json())
    except (SourceUnavailable, ValueError) as exc:
        bars = stored_bars(symbol, interval)
        if not bars:
            raise SourceUnavailable("yahoo", f"{symbol}: {exc}") from exc
        return {"meta": {"symbol": symbol, "price": bars[-1]["close"], "market_time": bars[-1]["time"]},
                "bars": bars, "dividends": [], "splits": [], "_fetched": None, "_stale": True}
    _store(symbol, interval, parsed["bars"])
    parsed["_fetched"] = got.fetched_at
    parsed["_stale"] = got.stale
    return parsed


def _classify(symbol_type: str | None) -> Freshness:
    return Freshness.LIVE if symbol_type == "CRYPTOCURRENCY" else Freshness.DELAYED


async def quote_for(symbol: str) -> dict:
    parsed = await chart(symbol, "5d", "1d", ttl=180)
    meta, bars = parsed["meta"], parsed["bars"]
    price = meta.get("price") or (bars[-1]["close"] if bars else None)
    prev = None
    if len(bars) >= 2:
        # A bar is stamped at its session open, which can be the previous UTC day for Asia-Pacific markets.
        same_session = meta.get("market_time", bars[-1]["time"]) - bars[-1]["time"] < 86_400
        prev = bars[-2]["close"] if same_session else bars[-1]["close"]
    change = price - prev if price is not None and prev else None
    return {"symbol": symbol, "name": meta.get("name"), "currency": meta.get("currency"),
            "exchange": meta.get("exchange"), "type": meta.get("type"), "price": price, "prev_close": prev,
            "change": change, "change_pct": change / prev * 100 if change is not None else None,
            "volume": meta.get("volume") or (bars[-1]["volume"] if bars else None),
            "high_52w": meta.get("high_52w"), "low_52w": meta.get("low_52w"),
            "as_of": iso(datetime.fromtimestamp(meta["market_time"], UTC).replace(tzinfo=None)) if meta.get("market_time") else None,
            "freshness": (Freshness.HISTORICAL if parsed.get("_stale") else _classify(meta.get("type"))).value,
            "stale": bool(parsed.get("_stale"))}


def thin(values: list[float], points: int = 40) -> list[float]:
    """Reduces a series for a sparkline, always keeping the final value."""
    if len(values) <= points:
        return values
    step = (len(values) - 1) / (points - 1)
    return [values[round(i * step)] for i in range(points)]


def parse_spark(payload: dict) -> dict[str, dict]:
    out = {}
    for item in (payload.get("spark") or {}).get("result") or []:
        if not item.get("response"):
            continue
        res = item["response"][0]
        meta = res.get("meta") or {}
        closes = [c for c in ((res.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [] if c is not None]
        price, prev = meta.get("regularMarketPrice"), meta.get("chartPreviousClose")
        if price is None:
            continue
        change = price - prev if prev else None
        moment = meta.get("regularMarketTime")
        out[item["symbol"]] = {"symbol": item["symbol"], "name": meta.get("longName") or meta.get("shortName"), "currency": meta.get("currency"), "exchange": meta.get("fullExchangeName"),
                               "type": meta.get("instrumentType"), "price": price, "prev_close": prev, "change": change, "change_pct": change / prev * 100 if change is not None else None,
                               "volume": meta.get("regularMarketVolume"), "high_52w": meta.get("fiftyTwoWeekHigh"), "low_52w": meta.get("fiftyTwoWeekLow"),
                               "as_of": iso(datetime.fromtimestamp(moment, UTC).replace(tzinfo=None)) if moment else None, "freshness": _classify(meta.get("instrumentType")).value, "stale": False,
                               "spark": [round(c, 4) for c in thin(closes)]}
    return out


async def _spark_chunk(symbols: list[str], ttl: int) -> dict[str, dict]:
    try:
        got = await get_fetcher().get("yahoo", SPARK, params={"symbols": ",".join(symbols), "range": "1d", "interval": "15m"}, headers=HEADERS, ttl=ttl)
        rows = parse_spark(got.json())
    except (SourceUnavailable, ValueError):
        return {}
    return {s: {**q, "stale": got.stale} for s, q in rows.items()}


async def quotes(symbols: list[str], ttl: int = 60) -> dict:
    """One request per 20 symbols, with a per-symbol fallback for anything the batch omits."""
    ordered = sorted(set(symbols))
    chunks = await asyncio.gather(*(_spark_chunk(ordered[i:i + SPARK_LIMIT], ttl) for i in range(0, len(ordered), SPARK_LIMIT)))
    found = {k: v for chunk in chunks for k, v in chunk.items()}
    missing = [s for s in symbols if s not in found]
    fallback = await asyncio.gather(*(quote_for(s) for s in missing[:SPARK_LIMIT]), return_exceptions=True)
    for symbol, result in zip(missing, fallback, strict=False):
        if not isinstance(result, Exception):
            found[symbol] = {**result, "spark": []}
    return {"quotes": [found[s] for s in symbols if s in found], "unavailable": [s for s in symbols if s not in found]}


async def search(q: str) -> list[dict]:
    got = await get_fetcher().get("yahoo", SEARCH, params={"q": q, "quotesCount": 12, "newsCount": 0}, headers=HEADERS, ttl=3600)
    return [{"symbol": r["symbol"], "name": r.get("longname") or r.get("shortname") or r["symbol"],
             "exchange": r.get("exchDisp") or r.get("exchange"), "type": r.get("quoteType"), "sector": r.get("sector")}
            for r in got.json().get("quotes", []) if r.get("symbol")]


def chart_envelope(parsed: dict, note: str | None = None) -> dict:
    stale = bool(parsed.get("_stale"))
    payload = {k: v for k, v in parsed.items() if not k.startswith("_")}
    return envelope(payload, source="yahoo", freshness=Freshness.HISTORICAL if stale else _classify(parsed["meta"].get("type")),
                    fetched_at=parsed.get("_fetched"), stale=stale,
                    note=note or ("Source unreachable: showing bars stored locally." if stale else None))
