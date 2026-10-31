import asyncio
import json
from datetime import date, datetime
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.api.deps import Symbol
from atlas.config import get_settings
from atlas.connectors import yahoo
from atlas.core import exposure
from atlas.core.envelope import Freshness, envelope, iso, utcnow
from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import get_fetcher
from atlas.core.registry import REGISTRY
from atlas.db import Alert, CacheEntry, Layout, Notification, Portfolio, SourceStatus, Transaction, get_db
from atlas.services import alerts as alert_service
from atlas.services import analytics, assistant, documents, eventstudy, quant
from atlas.services import portfolio as ledger

router = APIRouter(prefix="/api", tags=["research"])
SYMBOL_RE = r"^[A-Za-z0-9.^=\-]{1,20}$"
Symbol_Q = Annotated[str, Query(pattern=SYMBOL_RE)]


async def _prices(symbol: str, range_: str = "10y", total_return: bool = False) -> pd.Series:
    bars = (await yahoo.chart(symbol.upper(), range_, "1d"))["bars"]
    if total_return:
        bars = [{**b, "close": b.get("adjclose", b["close"])} for b in bars]
    s = analytics.closes(bars)
    if s.empty:
        raise SourceUnavailable("yahoo", f"No price history for {symbol}")
    return s


CAVEATS = {True: "Total return using dividend-adjusted closes, with next-bar execution. Past results do not predict future returns.",
           False: "Price return on split-adjusted closes, excluding dividends, with next-bar execution. Past results do not predict future returns."}


class BacktestIn(BaseModel):
    symbol: str = Field(pattern=SYMBOL_RE)
    strategy: str = "sma_cross"
    params: dict[str, float] = {}
    cost_bps: float = Field(10, ge=0, le=500)
    slippage_bps: float = Field(0, ge=0, le=500)
    walk_forward: bool = False
    total_return: bool = True


@router.get("/quant/strategies")
def strategies():
    return envelope({k: v[1] for k, v in quant.STRATEGIES.items()}, source="atlas", freshness=Freshness.REFERENCE)


@router.post("/quant/backtest")
async def backtest(body: BacktestIn):
    px = await _prices(body.symbol, total_return=body.total_return)
    params = {k: (int(v) if float(v).is_integer() else v) for k, v in body.params.items()}
    try:
        all_in = body.cost_bps + body.slippage_bps
        result = quant.backtest(px, body.strategy, params, all_in)
        result["walk_forward"] = quant.walk_forward(px, body.strategy, all_in) if body.walk_forward else None
    except (quant.ResearchError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return envelope(result, source="yahoo", freshness=Freshness.ESTIMATED, as_of=px.index[-1].strftime("%Y-%m-%d"), note=CAVEATS[body.total_return])


class StudyIn(BaseModel):
    symbol: str = Field(pattern=SYMBOL_RE)
    dates: list[date] = Field(min_length=1, max_length=60)
    before: int = Field(5, ge=0, le=60)
    after: int = Field(10, ge=1, le=120)
    benchmark: str | None = Field("SPY", pattern=SYMBOL_RE)


@router.post("/quant/eventstudy")
async def event_study(body: StudyIn):
    prices = await yahoo.daily_history(body.symbol.upper())
    bench = await yahoo.daily_history(body.benchmark.upper()) if body.benchmark else None
    try:
        result = eventstudy.study(prices, [d.isoformat() for d in body.dates], bench, body.before, body.after)
    except eventstudy.StudyError as exc:
        raise HTTPException(422, str(exc)) from exc
    return envelope(result, source="yahoo", freshness=Freshness.HISTORICAL, note="Measures what happened around these dates. It does not show that the events caused the moves.")


@router.get("/quant/analogues")
def analogue_sets():
    rows = exposure.analogues(list(exposure.RULES_BY_ID))
    return envelope({"events": rows, "sets": {r.id: r.name for r in exposure.RULES}}, source="atlas", freshness=Freshness.REFERENCE)


@router.get("/quant/rolling")
async def rolling(a: Symbol_Q, b: Symbol_Q, window: int = Query(63, ge=10, le=504)):
    left, right = await asyncio.gather(yahoo.daily_history(a.upper(), "2010-01-01"), yahoo.daily_history(b.upper(), "2010-01-01"))
    return envelope(quant.rolling_correlation(left, right, window), source="yahoo", freshness=Freshness.HISTORICAL)


@router.get("/quant/regimes/{symbol}")
async def regimes(symbol: Symbol):
    try:
        return envelope(quant.vol_regimes(await yahoo.daily_history(symbol.upper())), source="yahoo", freshness=Freshness.HISTORICAL, note="Labels describe the past. Next-month means are in-sample, not forecasts.")
    except quant.ResearchError as exc:
        raise HTTPException(422, str(exc)) from exc


class StressIn(BaseModel):
    weights: dict[str, float] = Field(min_length=1, max_length=30)


@router.post("/quant/stress")
async def stress(body: StressIn):
    total = sum(body.weights.values())
    if total <= 0:
        raise HTTPException(422, "Weights must add up to more than zero")
    names = list(body.weights)
    series = await asyncio.gather(*(yahoo.daily_history(s.upper()) for s in names))
    return envelope(quant.stress_test({s: v for s, v in zip(names, series, strict=True)}, {s: w / total for s, w in body.weights.items()}), source="yahoo", freshness=Freshness.HISTORICAL, note="Replays real past windows. Future stress can differ. Assets without history are left out and shown.")


class CompareIn(BaseModel):
    symbol: str = Field(pattern=SYMBOL_RE)
    cost_bps: float = Field(10, ge=0, le=500)


@router.post("/quant/compare")
async def compare(body: CompareIn):
    rows = quant.compare_strategies(await _prices(body.symbol, total_return=True), body.cost_bps)
    for row, ok in zip(rows, eventstudy.benjamini_hochberg([r["p_value"] for r in rows]), strict=True):
        row["survives_correction"] = ok
    return envelope(rows, source="yahoo", freshness=Freshness.ESTIMATED, note="Full-sample default settings, corrected for testing several strategies. Backtests do not guarantee future returns.")


class MultiIn(BaseModel):
    symbols: list[str] = Field(min_length=2, max_length=15)
    strategy: str = "momentum"
    cost_bps: float = Field(10, ge=0, le=500)


@router.post("/quant/multi")
async def multi(body: MultiIn):
    series = await asyncio.gather(*(_prices(s, total_return=True) for s in body.symbols))
    try:
        return envelope(quant.multi_asset({s.upper(): v for s, v in zip(body.symbols, series, strict=True)}, body.strategy, body.cost_bps), source="yahoo", freshness=Freshness.ESTIMATED, note="Equal-weight book, rebalanced daily. Costs apply per asset.")
    except quant.ResearchError as exc:
        raise HTTPException(422, str(exc)) from exc


class MonteCarloIn(BaseModel):
    symbol: str = Field(pattern=SYMBOL_RE)
    horizon: int = Field(252, ge=21, le=1260)
    paths: int = Field(2000, ge=100, le=10000)


@router.post("/quant/montecarlo")
async def montecarlo(body: MonteCarloIn):
    px = await _prices(body.symbol)
    return envelope(quant.monte_carlo(px.pct_change(fill_method=None), body.horizon, body.paths), source="yahoo", freshness=Freshness.ESTIMATED,
                    note="Block bootstrap of this asset's own history. Not a forecast. Cannot show regimes absent from the sample.")


class OptimiseIn(BaseModel):
    symbols: list[str] = Field(min_length=2, max_length=20)
    objective: str = "max_sharpe"
    max_weight: float = Field(1.0, gt=0, le=1)
    risk_free: float = Field(0.04, ge=0, le=0.2)


@router.post("/quant/optimise")
async def optimise(body: OptimiseIn):
    series = await asyncio.gather(*(_prices(s, "5y") for s in body.symbols))
    frame = pd.DataFrame({s.upper(): v for s, v in zip(body.symbols, series, strict=True)}).dropna()
    try:
        return envelope(quant.optimise(frame, body.objective, body.risk_free, body.max_weight), source="yahoo", freshness=Freshness.ESTIMATED, note="Weights are fitted to the past 5 years and are highly sensitive to the sample. Research only.")
    except quant.ResearchError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/quant/factors/{symbol}")
async def factors(symbol: Symbol):
    names = ["SPY", "IWM", "IWD", "IWF", "MTUM"]
    asset, *proxies = await asyncio.gather(_prices(symbol, "5y"), *(_prices(n, "5y") for n in names))
    r = pd.DataFrame(dict(zip(names, proxies, strict=True))).pct_change(fill_method=None)
    model = pd.DataFrame({"Market": r["SPY"], "Size": r["IWM"] - r["SPY"], "Value": r["IWD"] - r["IWF"], "Momentum": r["MTUM"] - r["SPY"]})
    return envelope(quant.factor_regression(asset.pct_change(fill_method=None), model), source="yahoo", freshness=Freshness.ESTIMATED, note="Long-only ETF spreads as rough factor proxies, not academic factors.")


# -- Portfolios --------------------------------------------------------------------------------------------

class PortfolioIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str = Field("real", pattern="^(real|paper)$")
    base_currency: str = Field("AUD", pattern="^[A-Z]{3}$")
    starting_cash: float = Field(0, ge=0)


class TransactionIn(BaseModel):
    ts: datetime
    symbol: str = Field(pattern=SYMBOL_RE)
    side: str = Field(pattern="^(buy|sell|dividend|deposit|withdraw)$")
    quantity: float = Field(gt=0)
    price: float = Field(ge=0)
    fee: float = Field(0, ge=0)
    currency: str = Field("USD", pattern="^[A-Z]{3}$")
    note: str | None = Field(None, max_length=500)


class PaperOrder(BaseModel):
    symbol: str = Field(pattern=SYMBOL_RE)
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)
    slippage_bps: float = Field(5, ge=0, le=200)
    fee: float = Field(0, ge=0)


async def _fx(currencies: set[str], base: str) -> dict[str, float]:
    rates = {base: 1.0}
    need = [c for c in currencies if c != base]
    if need:
        got = await get_fetcher().get("frankfurter", "https://api.frankfurter.dev/v1/latest", params={"base": base, "symbols": ",".join(need)}, ttl=6 * 3600)
        for code, rate in got.json().get("rates", {}).items():
            rates[code] = 1 / rate
    return rates


def _get_portfolio(db: Session, pid: int) -> Portfolio:
    p = db.get(Portfolio, pid)
    if not p:
        raise HTTPException(404, "Portfolio not found")
    return p


@router.get("/portfolios")
def portfolios(db: Session = Depends(get_db, scope="function")):
    return [{"id": p.id, "name": p.name, "kind": p.kind, "base_currency": p.base_currency, "starting_cash": p.starting_cash} for p in db.scalars(select(Portfolio).order_by(Portfolio.id))]


@router.post("/portfolios", status_code=201)
def create_portfolio(body: PortfolioIn, db: Session = Depends(get_db, scope="function")):
    if db.scalar(select(Portfolio).where(Portfolio.name == body.name)):
        raise HTTPException(409, "A portfolio with that name exists")
    p = Portfolio(**body.model_dump())
    db.add(p)
    db.flush()
    return {"id": p.id, "name": p.name}


@router.delete("/portfolios/{pid}", status_code=204)
def delete_portfolio(pid: int, db: Session = Depends(get_db, scope="function")):
    db.delete(_get_portfolio(db, pid))


def _check_ledger(existing: list, new: list) -> None:
    try:
        ledger.compute_positions([*existing, *new])
    except ledger.LedgerError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/portfolios/{pid}/transactions", status_code=201)
def add_transaction(pid: int, body: TransactionIn, db: Session = Depends(get_db, scope="function")):
    p = _get_portfolio(db, pid)
    tx = Transaction(portfolio_id=pid, **{**body.model_dump(), "symbol": body.symbol.upper(), "ts": body.ts.replace(tzinfo=None)})
    _check_ledger(p.transactions, [tx])
    db.add(tx)
    db.flush()
    return {"id": tx.id}


@router.delete("/portfolios/{pid}/transactions/{tid}", status_code=204)
def delete_transaction(pid: int, tid: int, db: Session = Depends(get_db, scope="function")):
    tx = db.get(Transaction, tid)
    if not tx or tx.portfolio_id != pid:
        raise HTTPException(404, "Not found")
    p = _get_portfolio(db, pid)
    _check_ledger([t for t in p.transactions if t.id != tid], [])
    db.delete(tx)


@router.post("/portfolios/{pid}/import", status_code=201)
async def import_csv(pid: int, file: UploadFile = File(...), db: Session = Depends(get_db, scope="function")):
    p = _get_portfolio(db, pid)
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV exceeds 5 MB")
    try:
        rows = ledger.parse_csv(raw.decode("utf-8"))
    except (ledger.LedgerError, UnicodeDecodeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    txs = [Transaction(portfolio_id=pid, **r) for r in rows]
    _check_ledger(p.transactions, txs)
    db.add_all(txs)
    return {"imported": len(txs)}


@router.post("/portfolios/{pid}/paper-order", status_code=201)
async def paper_order(pid: int, body: PaperOrder, db: Session = Depends(get_db, scope="function")):
    p = _get_portfolio(db, pid)
    if p.kind != "paper":
        raise HTTPException(422, "Paper orders need a paper portfolio. ATLAS never routes real orders.")
    q = await yahoo.quote_for(body.symbol.upper())
    sign = 1 if body.side == "buy" else -1
    price = q["price"] * (1 + sign * body.slippage_bps / 10_000)
    if body.side == "buy" and ledger.cash_balance(p.starting_cash, p.transactions) < price * body.quantity + body.fee:
        raise HTTPException(422, "Insufficient paper cash")
    tx = Transaction(portfolio_id=pid, ts=utcnow(), symbol=body.symbol.upper(), side=body.side, quantity=body.quantity, price=price, fee=body.fee, currency=q.get("currency") or "USD",
                     note=f"Simulated fill at delayed {q['price']:.4f} + {body.slippage_bps} bps")
    _check_ledger(p.transactions, [tx])
    db.add(tx)
    db.flush()
    return {"id": tx.id, "fill_price": price, "note": tx.note}


@router.get("/portfolios/{pid}")
async def portfolio_detail(pid: int, benchmark: str = "^GSPC", db: Session = Depends(get_db, scope="function")):
    p = _get_portfolio(db, pid)
    txs = list(p.transactions)
    book = ledger.compute_positions(txs)
    held = {s: v for s, v in book.items() if v["quantity"] > 1e-9}
    quotes = {q["symbol"]: q for q in (await yahoo.quotes(list(held)))["quotes"]} if held else {}
    fx_note, rates = None, {p.base_currency: 1.0}
    try:
        rates = await _fx({v["currency"] for v in book.values()} | {t.currency for t in txs}, p.base_currency)
    except SourceUnavailable as exc:
        fx_note = f"FX unavailable ({exc.reason}); foreign positions are not converted."
    positions, value, unreal = [], 0.0, 0.0
    for symbol, v in held.items():
        q = quotes.get(symbol)
        fx = rates.get(v["currency"])
        mv = q["price"] * v["quantity"] if q else None
        pnl = mv - v["cost"] if mv is not None else None
        if mv is not None and fx:
            value += mv * fx
            unreal += pnl * fx
        positions.append({"symbol": symbol, "quantity": v["quantity"], "avg_cost": v["avg_cost"], "currency": v["currency"], "price": q["price"] if q else None, "market_value": mv, "market_value_base": mv * fx if mv is not None and fx else None,
                          "unrealised": pnl, "unrealised_pct": pnl / v["cost"] if pnl is not None and v["cost"] else None, "day_change_pct": q.get("change_pct") if q else None, "income": v["income"], "realised": v["realised"], "freshness": q["freshness"] if q else "unavailable"})
    for row in positions:
        row["weight"] = row["market_value_base"] / value if row["market_value_base"] and value else None
    cash = ledger.cash_balance(p.starting_cash, txs) if p.kind == "paper" else None
    risk = await _risk(held, benchmark) if len(held) >= 1 else None
    realised = sum(v["realised"] * rates.get(v["currency"], 0) for v in book.values())
    income = sum(v["income"] * rates.get(v["currency"], 0) for v in book.values())
    return envelope({"id": p.id, "name": p.name, "kind": p.kind, "base_currency": p.base_currency, "positions": positions, "market_value": value, "cash": cash, "unrealised": unreal, "realised": realised, "income": income, "risk": risk,
                     "transactions": [{"id": t.id, "ts": t.ts.isoformat(), "symbol": t.symbol, "side": t.side, "quantity": t.quantity, "price": t.price, "fee": t.fee, "currency": t.currency, "note": t.note} for t in reversed(txs)]},
                    source=["yahoo", "frankfurter"], freshness=Freshness.DELAYED, note=fx_note)


async def _risk(held: dict, benchmark: str) -> dict | None:
    names = list(held)
    series = await asyncio.gather(*(_prices(s, "2y") for s in names), _prices(benchmark, "2y"), return_exceptions=True)
    frames = {n: s for n, s in zip(names, series[:-1], strict=True) if not isinstance(s, Exception)}
    bench = series[-1]
    if not frames or isinstance(bench, Exception):
        return None
    prices = pd.DataFrame(frames).ffill().dropna()
    if len(prices) < 60:
        return None
    # Constant-quantity history: what today's holdings would have done, not actual past performance.
    qty = pd.Series({n: held[n]["quantity"] for n in frames})
    nav = (prices * qty).sum(axis=1)
    r = nav.pct_change(fill_method=None).dropna()
    b = bench.pct_change(fill_method=None).reindex(r.index).dropna()
    common = r.index.intersection(b.index)
    beta = float(r[common].cov(b[common]) / b[common].var())
    corr = prices.pct_change(fill_method=None).corr().round(3) if len(frames) > 1 else None
    curve = (nav / nav.iloc[0]).iloc[::5]
    bcurve = bench.reindex(curve.index).ffill()
    return {"metrics": quant.metrics(r), "var_95_1d": float(r.quantile(0.05)), "beta": beta, "benchmark": benchmark,
            "curve": [{"date": d.strftime("%Y-%m-%d"), "portfolio": float(v), "benchmark": float(bcurve[d] / bcurve.iloc[0])} for d, v in curve.items()],
            "correlation": {"symbols": list(corr.columns), "matrix": corr.values.tolist()} if corr is not None else None}


# -- Alerts ------------------------------------------------------------------------------------------------

class AlertIn(BaseModel):
    kind: str
    target: str = Field(min_length=1, max_length=120)
    threshold: float | None = None
    label: str | None = Field(None, max_length=200)
    cooldown_minutes: int = Field(360, ge=0, le=100_000)

    @model_validator(mode="after")
    def check(self):
        if self.kind not in alert_service.KINDS:
            raise ValueError("Unknown alert kind")
        if self.kind in {"price_above", "price_below", "pct_move", "volume_spike", "chokepoint_drop", "earthquake", "satellite_change"} and self.threshold is None:
            raise ValueError("This alert needs a threshold")
        return self


def _alert(a: Alert) -> dict:
    return {"id": a.id, "kind": a.kind, "target": a.target, "threshold": a.threshold, "label": a.label, "enabled": a.enabled, "cooldown_minutes": a.cooldown_minutes, "last_fired": iso(a.last_fired), "last_checked": iso(a.last_checked), "last_error": a.last_error}


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db, scope="function")):
    return {"alerts": [_alert(a) for a in db.scalars(select(Alert).order_by(Alert.id))], "kinds": alert_service.KINDS}


@router.post("/alerts", status_code=201)
def create_alert(body: AlertIn, db: Session = Depends(get_db, scope="function")):
    a = Alert(**body.model_dump())
    db.add(a)
    db.flush()
    return _alert(a)


@router.delete("/alerts/{aid}", status_code=204)
def delete_alert(aid: int, db: Session = Depends(get_db, scope="function")):
    a = db.get(Alert, aid)
    if not a:
        raise HTTPException(404, "Not found")
    db.delete(a)


@router.post("/alerts/evaluate")
async def evaluate():
    return {"fired": await alert_service.evaluate_all()}


@router.get("/notifications")
def notifications(limit: int = 50, db: Session = Depends(get_db, scope="function")):
    rows = db.scalars(select(Notification).order_by(Notification.created_at.desc()).limit(min(limit, 200))).all()
    unread = db.scalar(select(func.count()).select_from(Notification).where(Notification.read.is_(False)))
    return {"unread": unread, "items": [{"id": n.id, "title": n.title, "body": n.body, "severity": n.severity, "created_at": iso(n.created_at), "read": n.read} for n in rows]}


@router.post("/notifications/read")
def mark_read(db: Session = Depends(get_db, scope="function")):
    for n in db.scalars(select(Notification).where(Notification.read.is_(False))):
        n.read = True
    return {"ok": True}


# -- AI and documents --------------------------------------------------------------------------------------

class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


@router.post("/ai/ask")
async def ask(body: AskIn):
    return await assistant.ask(body.question)


@router.get("/ai/status")
async def ai_status():
    return await assistant.ollama_status()


@router.get("/ai/report/{ticker}")
async def report(ticker: Symbol):
    return await assistant.company_report(ticker.upper())


@router.get("/documents")
def docs():
    return documents.list_documents()


@router.post("/documents", status_code=201)
async def upload(file: UploadFile = File(...)):
    limit = get_settings().max_upload_mb * 1024 * 1024
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(413, "File too large")
    try:
        result = await asyncio.to_thread(documents.ingest, file.filename or "upload.txt", raw)
        if not result.get("duplicate"):
            result["vectors"] = await documents.index_vectors(result["id"])
        return result
    except documents.DocumentError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/documents/{doc_id}", status_code=204)
def remove_document(doc_id: int):
    if not documents.delete(doc_id):
        raise HTTPException(404, "Not found")


# -- Workspace and system ----------------------------------------------------------------------------------

@router.get("/layouts/{name}")
def get_layout(name: str, db: Session = Depends(get_db, scope="function")):
    row = db.get(Layout, name[:80])
    return {"name": name, "spec": json.loads(row.spec) if row else None}


@router.put("/layouts/{name}")
def put_layout(name: str, spec: dict, db: Session = Depends(get_db, scope="function")):
    raw = json.dumps(spec)
    if len(raw) > 100_000:
        raise HTTPException(413, "Layout too large")
    db.merge(Layout(name=name[:80], spec=raw))
    return {"ok": True}


@router.get("/layouts")
def list_layouts(db: Session = Depends(get_db, scope="function")):
    return list(db.scalars(select(Layout.name).order_by(Layout.name)))


@router.get("/sources")
def sources(db: Session = Depends(get_db, scope="function")):
    status = {s.source_id: s for s in db.scalars(select(SourceStatus))}
    settings = get_settings()
    configured = {"fred": bool(settings.fred_api_key)}
    rows = []
    for spec in REGISTRY.values():
        st = status.get(spec.id)
        total = (st.success_count + st.failure_count) if st else 0
        state = "not_configured" if configured.get(spec.id) is False else "idle"
        if st and st.last_attempt:
            state = "ok" if st.last_error is None else "degraded" if st.last_success else "down"
        rows.append({**spec.to_dict(), "state": state, "last_success": iso(st.last_success) if st else None, "last_attempt": iso(st.last_attempt) if st else None, "last_error": st.last_error if st else None,
                     "success_rate": st.success_count / total if st and total else None})
    return envelope(rows, source="atlas", freshness=Freshness.LIVE)


@router.get("/settings")
async def settings_view():
    s = get_settings()
    return {"sec_contact_set": bool(s.sec_contact.strip()), "fred_key_set": bool(s.fred_api_key), "bls_key_set": bool(s.bls_api_key), "ollama": await assistant.ollama_status(), "scheduler_enabled": s.scheduler_enabled,
            "alert_interval_seconds": s.alert_interval_seconds, "macos_notifications": s.macos_notifications, "data_dir": str(s.resolved_data_dir), "bind": f"{s.host}:{s.port}"}


@router.get("/health")
def health(db: Session = Depends(get_db, scope="function")):
    return {"status": "ok", "cache_entries": db.scalar(select(func.count()).select_from(CacheEntry))}
