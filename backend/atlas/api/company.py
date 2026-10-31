import asyncio

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from atlas.api.deps import Symbol, SymbolList, split_symbols
from atlas.connectors import sec, yahoo
from atlas.core.envelope import Freshness, envelope
from atlas.core.errors import SourceUnavailable
from atlas.core.memo import memo
from atlas.services import valuation

router = APIRouter(prefix="/api/company", tags=["company"])


def _small(sub: dict) -> dict:
    """The submissions file is large. Only what the pages read is kept in memory."""
    return {k: v for k, v in sub.items() if k != "filings"} | {"filings": {"recent": sub.get("filings", {}).get("recent", {})}}


@memo(900, maxsize=12)
async def _load(ticker: str) -> dict:
    info = await sec.resolve(ticker)
    facts_got, sub_got = await asyncio.gather(sec.company_facts(info["cik"]), sec.submissions(info["cik"]))
    facts, sub = facts_got.json(), sub_got.json()
    annual = sec.build_statements(facts)
    return {"info": info, "shares": sec.shares_outstanding(facts), "sub": _small(sub), "annual": annual, "ratios": sec.ratios(annual), "fetched": facts_got.fetched_at, "stale": facts_got.stale}


def _multiples(price: float | None, shares: dict | None, annual: list[dict], ratios: list[dict]) -> dict:
    if not price or not shares or not annual:
        return {}
    last, ratio = annual[-1], ratios[-1]
    cap = price * shares["value"]
    debt, cash = ratio.get("total_debt"), last.get("cash")
    ev = cap + debt - cash if debt is not None and cash is not None else None
    ebitda = last["operating_income"] + (last.get("depreciation") or 0) if last.get("operating_income") is not None else None
    fcf, rev, ni, eq = ratio.get("free_cash_flow"), last.get("revenue"), last.get("net_income"), last.get("equity")

    def safe(a, b):
        return a / b if a is not None and b and b > 0 else None

    return {"market_cap": cap, "enterprise_value": ev, "pe": safe(cap, ni), "ps": safe(cap, rev), "pb": safe(cap, eq), "ev_ebitda": safe(ev, ebitda), "ev_sales": safe(ev, rev),
            "fcf_yield": safe(fcf, cap), "dividend_yield": safe(abs(last["dividends_paid"]), cap) if last.get("dividends_paid") else None}


@router.get("/{ticker}")
async def overview(ticker: Symbol):
    ticker = ticker.upper()
    data = await _load(ticker)
    sub = data["sub"]
    try:
        quote = await yahoo.quote_for(ticker)
    except SourceUnavailable:
        quote = None
    shares = data["shares"]
    parsed = None
    try:
        parsed = await yahoo.chart(ticker, "10y", "1mo")
    except SourceUnavailable:
        pass
    return envelope({
        "ticker": ticker, "name": sub.get("name"), "cik": data["info"]["cik"], "sic": sub.get("sic"), "industry": sub.get("sicDescription"),
        "exchanges": sub.get("exchanges"), "fiscal_year_end": sub.get("fiscalYearEnd"), "state": sub.get("stateOfIncorporation"), "website": sub.get("website"),
        "quote": quote, "shares": shares, "multiples": _multiples(quote and quote["price"], shares, data["annual"], data["ratios"]),
        "annual": data["annual"], "ratios": data["ratios"], "dividends": (parsed or {}).get("dividends", [])[-24:], "splits": (parsed or {}).get("splits", []),
        "earnings": sec.earnings_dates(sub),
    }, source=["sec", "yahoo"], freshness=Freshness.HISTORICAL, fetched_at=data["fetched"], stale=data["stale"],
        note="Statements are as reported in XBRL. Multiples use delayed price and latest annual figures. Cash is cash and equivalents only, excluding marketable securities, so EV can be overstated.")


@router.get("/{ticker}/statements")
async def statements(ticker: Symbol, period: str = Query("annual", pattern="^(annual|quarterly)$")):
    info = await sec.resolve(ticker)
    got = await sec.company_facts(info["cik"])
    rows = sec.build_statements(got.json(), period, 12)
    return envelope(rows, source="sec", freshness=Freshness.HISTORICAL, fetched_at=got.fetched_at, stale=got.stale,
                    note="Fourth quarters are not filed separately, so they are absent from quarterly view." if period == "quarterly" else None)


@router.get("/{ticker}/filings")
async def filings(ticker: Symbol, form: str | None = Query(None, max_length=12)):
    info = await sec.resolve(ticker)
    got = await sec.submissions(info["cik"])
    return envelope(sec.recent_filings(got.json(), {form} if form else None, 60), source="sec", freshness=Freshness.HISTORICAL, fetched_at=got.fetched_at, stale=got.stale)


@router.get("/{ticker}/insiders")
async def insiders(ticker: Symbol):
    info = await sec.resolve(ticker)
    got = await sec.submissions(info["cik"])
    rows = await sec.insider_transactions(got.json())
    note = "Parsed from Form 4. Code P is open-market purchase, S sale, A grant, M option exercise, F tax withholding."
    if not rows:
        note = "SEC requires a declared contact to read Form 4 documents. Set ATLAS_SEC_CONTACT to parse transactions; filing links are shown meanwhile."
    return envelope({"transactions": rows, "filings": sec.insider_filings(got.json())}, source="sec", freshness=Freshness.HISTORICAL, fetched_at=got.fetched_at, note=note)


@router.get("")
async def compare(tickers: SymbolList):
    names = split_symbols(tickers)
    results = await asyncio.gather(*(_load(t) for t in names), return_exceptions=True)
    quotes = await asyncio.gather(*(yahoo.quote_for(t) for t in names), return_exceptions=True)
    rows = []
    for name, res, q in zip(names, results, quotes, strict=True):
        if isinstance(res, Exception) or not res["annual"]:
            rows.append({"ticker": name, "available": False})
            continue
        last, ratio = res["annual"][-1], res["ratios"][-1]
        price = None if isinstance(q, Exception) else q["price"]
        rows.append({"ticker": name, "available": True, "name": res["sub"].get("name"), "period_end": last["period_end"], "revenue": last.get("revenue"), "net_income": last.get("net_income"),
                     **{k: ratio.get(k) for k in ("revenue_growth", "net_margin", "operating_margin", "gross_margin", "roe", "debt_to_equity", "free_cash_flow")},
                     **_multiples(price, res["shares"], res["annual"], res["ratios"])})
    return envelope(rows, source=["sec", "yahoo"], freshness=Freshness.HISTORICAL)


class DcfBody(BaseModel):
    ticker: str | None = Field(None, pattern=r"^[A-Za-z0-9.^=\-]{1,20}$")
    base_fcf: float | None = None
    growth: float = Field(0.08, ge=-0.5, le=1)
    terminal_growth: float = Field(0.025, ge=-0.02, le=0.06)
    discount_rate: float = Field(0.09, gt=0, le=0.5)
    years: int = Field(10, ge=1, le=30)
    net_debt: float | None = None
    shares: float | None = None


@router.post("/dcf/run")
async def run_dcf(body: DcfBody):
    base, net_debt, shares, price, assumed = body.base_fcf, body.net_debt, body.shares, None, []
    if body.ticker:
        data = await _load(body.ticker.upper())
        last, ratio = data["annual"][-1], data["ratios"][-1]
        share_row = data["shares"]
        if base is None:
            base = ratio.get("free_cash_flow")
            assumed.append(f"Base free cash flow from fiscal {last['period_end']} filing")
        if net_debt is None:
            net_debt = (ratio.get("total_debt") or 0) - (last.get("cash") or 0)
            assumed.append("Net debt = reported debt minus cash and equivalents")
        if shares is None and share_row:
            shares = share_row["value"]
            assumed.append(f"Shares outstanding as of {share_row['as_of']}")
        try:
            price = (await yahoo.quote_for(body.ticker.upper()))["price"]
        except SourceUnavailable:
            pass
    if base is None or shares is None:
        raise HTTPException(422, "Provide a ticker with SEC data, or base_fcf and shares.")
    p = valuation.DcfInput(base_fcf=base, growth=body.growth, terminal_growth=body.terminal_growth, discount_rate=body.discount_rate, years=body.years, net_debt=net_debt or 0, shares=shares)
    try:
        result = valuation.dcf(p)
        output = {**result, "inputs": p.__dict__, "scenarios": valuation.scenarios(p), "sensitivity": valuation.sensitivity(p), "assumptions": assumed, "market_price": price,
                  "upside": result["per_share"] / price - 1 if price else None}
    except valuation.ValuationError as exc:
        raise HTTPException(422, str(exc)) from exc
    return envelope(output, source=["sec", "yahoo"] if body.ticker else ["user input"], freshness=Freshness.ESTIMATED, note="A DCF output is an estimate that depends entirely on these assumptions.")
