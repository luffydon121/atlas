"""SEC EDGAR: company facts (XBRL), filings and insider forms."""

import re
from datetime import date, timedelta

from defusedxml import ElementTree

from atlas.config import get_settings
from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import get_fetcher
from atlas.core.reference import LARGE_CAPS

TICKERS = "https://www.sec.gov/files/company_tickers.json"
FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

# metric: (statement kind, ordered XBRL tags)
CONCEPTS: dict[str, tuple[str, list[str]]] = {
    "revenue": ("flow", ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                         "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
                         "RevenuesNetOfInterestExpense"]),
    "cost_of_revenue": ("flow", ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"]),
    "gross_profit": ("flow", ["GrossProfit"]),
    "rnd": ("flow", ["ResearchAndDevelopmentExpense"]),
    "operating_income": ("flow", ["OperatingIncomeLoss"]),
    "depreciation": ("flow", ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
                              "DepreciationAndAmortization"]),
    "net_income": ("flow", ["NetIncomeLoss", "ProfitLoss"]),
    "eps_diluted": ("flow", ["EarningsPerShareDiluted"]),
    "cfo": ("flow", ["NetCashProvidedByUsedInOperatingActivities",
                     "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]),
    "capex": ("flow", ["PaymentsToAcquirePropertyPlantAndEquipment",
                       "PaymentsToAcquireProductiveAssets"]),
    "dividends_paid": ("flow", ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"]),
    "buybacks": ("flow", ["PaymentsForRepurchaseOfCommonStock"]),
    "assets": ("stock", ["Assets"]),
    "current_assets": ("stock", ["AssetsCurrent"]),
    "cash": ("stock", ["CashAndCashEquivalentsAtCarryingValue",
                       "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]),
    "liabilities": ("stock", ["Liabilities"]),
    "current_liabilities": ("stock", ["LiabilitiesCurrent"]),
    "long_term_debt": ("stock", ["LongTermDebtNoncurrent", "LongTermDebt"]),
    "short_term_debt": ("stock", ["LongTermDebtCurrent", "ShortTermBorrowings", "CommercialPaper"]),
    "equity": ("stock", ["StockholdersEquity",
                         "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]),
}
FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "10-Q", "10-Q/A"}


def _headers() -> dict:
    contact = get_settings().sec_contact.strip()
    return {"User-Agent": f"ATLAS local research tool {contact}".strip()}


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def extract_series(facts: dict, tags: list[str], kind: str, period: str) -> dict[str, dict]:
    """Merges tags in priority order into {period_end: fact}, using the latest-filed value."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    merged: dict[str, dict] = {}
    span = (340, 390) if period == "annual" else (80, 100)
    for tag in tags:
        units = gaap.get(tag, {}).get("units", {})
        entries = units.get("USD") or units.get("USD/shares") or []
        best: dict[str, dict] = {}
        for e in entries:
            if e.get("form") not in FORMS or "end" not in e or "val" not in e:
                continue
            if period == "annual" and not e["form"].startswith(("10-K", "20-F", "40-F")):
                continue
            if kind == "flow":
                if "start" not in e or not span[0] <= _days(e["start"], e["end"]) <= span[1]:
                    continue
            elif period == "annual" and e.get("fp") != "FY":
                continue
            current = best.get(e["end"])
            if current is None or e.get("filed", "") >= current.get("filed", ""):
                best[e["end"]] = e
        for end, entry in best.items():
            merged.setdefault(end, {"value": entry["val"], "tag": tag, "filed": entry.get("filed"),
                                    "form": entry.get("form"), "accn": entry.get("accn")})
    return merged


def build_statements(facts: dict, period: str = "annual", limit: int = 10) -> list[dict]:
    columns: dict[str, dict] = {}
    for metric, (kind, tags) in CONCEPTS.items():
        for end, fact in extract_series(facts, tags, kind, period).items():
            columns.setdefault(end, {"period_end": end, "filed": fact["filed"], "form": fact["form"]})[metric] = fact["value"]
    rows = [c for _, c in sorted(columns.items()) if "revenue" in c or "net_income" in c or "assets" in c]
    # Keep one row per fiscal year end, dropping stock-only stubs with no income statement.
    rows = [r for r in rows if "net_income" in r or "revenue" in r]
    return rows[-limit:]


def ratios(rows: list[dict]) -> list[dict]:
    out, prev = [], None
    for r in rows:
        def div(a, b, row=r):
            x, y = row.get(a), row.get(b)
            return x / y if x is not None and y not in (None, 0) else None

        debt = None if r.get("long_term_debt") is None else r["long_term_debt"] + (r.get("short_term_debt") or 0)
        fcf = r["cfo"] - abs(r.get("capex") or 0) if r.get("cfo") is not None else None
        gross = r.get("gross_profit")
        if gross is None and r.get("revenue") is not None and r.get("cost_of_revenue") is not None:
            gross = r["revenue"] - r["cost_of_revenue"]
        row = {"period_end": r["period_end"], "free_cash_flow": fcf, "total_debt": debt,
               "gross_margin": gross / r["revenue"] if gross is not None and r.get("revenue") else None,
               "operating_margin": div("operating_income", "revenue"), "net_margin": div("net_income", "revenue"),
               "roe": div("net_income", "equity"), "roa": div("net_income", "assets"),
               "current_ratio": div("current_assets", "current_liabilities"),
               "debt_to_equity": debt / r["equity"] if debt is not None and r.get("equity") else None,
               "fcf_margin": fcf / r["revenue"] if fcf is not None and r.get("revenue") else None}
        for key, src in (("revenue_growth", "revenue"), ("net_income_growth", "net_income"), ("eps_growth", "eps_diluted")):
            a, b = r.get(src), (prev or {}).get(src)
            row[key] = (a - b) / abs(b) if a is not None and b else None
        out.append(row)
        prev = r
    return out


def shares_outstanding(facts: dict) -> dict | None:
    entries = facts.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    if entries:
        last = max(entries, key=lambda e: e.get("end", ""))
        # Multi-class issuers report one row per class at the same date.
        same_date = {e["val"] for e in entries if e.get("end") == last["end"]}
        return {"value": sum(same_date), "as_of": last["end"]}
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in ("CommonStockSharesOutstanding", "WeightedAverageNumberOfDilutedSharesOutstanding"):
        rows = gaap.get(tag, {}).get("units", {}).get("shares", [])
        if rows:
            last = max(rows, key=lambda e: e.get("end", ""))
            return {"value": last["val"], "as_of": last["end"]}
    return None


async def ticker_map() -> dict[str, dict]:
    if get_settings().sec_contact.strip():
        got = await get_fetcher().get("sec", TICKERS, headers=_headers(), ttl=7 * 86400)
        return {v["ticker"].upper(): {"cik": v["cik_str"], "name": v["title"]} for v in got.json().values()}
    return {t: {"cik": c, "name": n} for t, (c, n, _) in LARGE_CAPS.items()}


async def resolve(ticker: str) -> dict:
    ticker = ticker.upper()
    table = await ticker_map()
    match = table.get(ticker) or table.get(ticker.replace("-", ".")) or table.get(ticker.replace(".", "-"))
    if not match:
        hint = "" if get_settings().sec_contact.strip() else " Set ATLAS_SEC_CONTACT to look up every SEC filer."
        raise SourceUnavailable("sec", f"{ticker} is not in the available SEC ticker list.{hint}")
    return {"ticker": ticker, **match}


async def company_facts(cik: int):
    return await get_fetcher().get("sec", FACTS.format(cik=cik), headers=_headers(), ttl=86400)


async def submissions(cik: int):
    return await get_fetcher().get("sec", SUBMISSIONS.format(cik=cik), headers=_headers(), ttl=6 * 3600)


def recent_filings(sub: dict, forms: set[str] | None = None, limit: int = 40) -> list[dict]:
    recent = sub.get("filings", {}).get("recent", {})
    cik = int(sub["cik"])
    out = []
    for i, form in enumerate(recent.get("form", [])):
        if forms and form not in forms:
            continue
        acc = recent["accessionNumber"][i]
        doc = recent["primaryDocument"][i]
        out.append({"form": form, "filed": recent["filingDate"][i], "report_date": recent["reportDate"][i] or None,
                    "accession": acc, "description": recent["primaryDocDescription"][i], "items": recent.get("items", [""] * (i + 1))[i],
                    "url": ARCHIVE.format(cik=cik, acc=acc.replace("-", ""), doc=doc)})
        if len(out) >= limit:
            break
    return out


def earnings_dates(sub: dict) -> dict:
    """Past results come from 8-K Item 2.02. The next date is a +91 day estimate, never a confirmation."""
    filings = [f for f in recent_filings(sub, {"8-K"}, 300) if "2.02" in (f.get("items") or "")]
    past = [{"date": f["filed"], "url": f["url"]} for f in filings[:8]]
    estimate = None
    if past:
        estimate = (date.fromisoformat(past[0]["date"]) + timedelta(days=91)).isoformat()
    return {"past": past, "next_estimate": estimate, "next_is_estimate": True,
            "estimate_passed": bool(estimate and estimate < date.today().isoformat())}


def parse_form4(xml_text: str) -> list[dict]:
    root = ElementTree.fromstring(xml_text)
    owner = root.findtext(".//rptOwnerName") or "Unknown"
    title = root.findtext(".//officerTitle") or ("Director" if root.findtext(".//isDirector") in ("1", "true") else None)
    rows = []
    for tx in root.findall(".//nonDerivativeTransaction"):
        code = tx.findtext(".//transactionCode")
        shares = tx.findtext(".//transactionShares/value")
        price = tx.findtext(".//transactionPricePerShare/value")
        rows.append({"owner": owner, "title": title, "date": tx.findtext(".//transactionDate/value"), "code": code,
                     "acquired_disposed": tx.findtext(".//transactionAcquiredDisposedCode/value"),
                     "shares": float(shares) if shares else None, "price": float(price) if price else None})
    return rows


def insider_filings(sub: dict, limit: int = 20) -> list[dict]:
    return recent_filings(sub, {"3", "4", "5"}, limit)


async def insider_transactions(sub: dict, limit: int = 8) -> list[dict]:
    if not get_settings().sec_contact.strip():
        return []
    rows = []
    for filing in recent_filings(sub, {"4"}, limit):
        raw_url = re.sub(r"/xslF345X\d+/", "/", filing["url"])
        try:
            got = await get_fetcher().get("sec", raw_url, headers=_headers(), ttl=30 * 86400)
            parsed = parse_form4(got.body)
        except (SourceUnavailable, ElementTree.ParseError):
            continue
        rows.extend({**r, "filed": filing["filed"], "url": filing["url"]} for r in parsed)
    return rows
