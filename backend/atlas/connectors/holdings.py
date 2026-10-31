"""SEC Form 13F holdings. Filings arrive up to 45 days after quarter end and show long US positions only."""

import re
from collections import defaultdict

from defusedxml import ElementTree

from atlas.config import get_settings
from atlas.connectors import sec
from atlas.core.errors import SourceNotConfigured
from atlas.core.fetcher import get_fetcher

FILERS = {1067983: "Berkshire Hathaway", 2012383: "BlackRock", 102909: "Vanguard", 93751: "State Street", 1350694: "Bridgewater Associates", 1037389: "Renaissance Technologies",
          1423053: "Citadel Advisors", 1029160: "Soros Fund Management", 1336528: "Pershing Square", 1649339: "Scion Asset Management", 1656456: "Appaloosa"}
INDEX = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/index.json"
_NS = re.compile(r"\{[^}]+\}")


def filings(sub: dict, limit: int = 12) -> list[dict]:
    recent = sub.get("filings", {}).get("recent", {})
    out = []
    for i, form in enumerate(recent.get("form", [])):
        if form in {"13F-HR", "13F-HR/A"}:
            out.append({"form": form, "filed": recent["filingDate"][i], "period": recent["reportDate"][i], "accession": recent["accessionNumber"][i],
                        "url": f"https://www.sec.gov/Archives/edgar/data/{int(sub['cik'])}/{recent['accessionNumber'][i].replace('-', '')}/"})
            if len(out) >= limit:
                break
    return out


def parse_table(xml_text: str) -> list[dict]:
    """Same-security rows are combined. Values are in US dollars for filings since 2023."""
    root = ElementTree.fromstring(xml_text)
    combined: dict[tuple, dict] = defaultdict(lambda: {"value": 0.0, "shares": 0.0})
    for row in root.iter():
        if _NS.sub("", row.tag) != "infoTable":
            continue
        cells = {_NS.sub("", c.tag): (c.text or "").strip() for c in row.iter()}
        key = (cells.get("cusip", ""), cells.get("putCall", "") or "")
        item = combined[key]
        item.update({"cusip": key[0], "issuer": cells.get("nameOfIssuer", ""), "title": cells.get("titleOfClass", ""), "put_call": key[1] or None})
        item["value"] += float(cells.get("value") or 0)
        item["shares"] += float(cells.get("sshPrnamt") or 0)
    return sorted(combined.values(), key=lambda r: r["value"], reverse=True)


def changes(previous: list[dict], current: list[dict]) -> dict:
    """Compares share counts, so a price move alone is never reported as buying or selling."""
    key = lambda r: (r["cusip"], r["put_call"])  # noqa: E731
    before, after = {key(r): r for r in previous}, {key(r): r for r in current}
    added = [after[k] for k in after.keys() - before.keys()]
    removed = [before[k] for k in before.keys() - after.keys()]
    increased, reduced = [], []
    for k in after.keys() & before.keys():
        delta = after[k]["shares"] - before[k]["shares"]
        if delta:
            row = {**after[k], "shares_before": before[k]["shares"], "change": delta, "change_pct": delta / before[k]["shares"] if before[k]["shares"] else None}
            (increased if delta > 0 else reduced).append(row)
    rank = lambda rows: sorted(rows, key=lambda r: r["value"], reverse=True)[:25]  # noqa: E731
    return {"added": rank(added), "removed": rank(removed), "increased": rank(increased), "reduced": rank(reduced)}


async def table(cik: int, accession: str) -> list[dict]:
    if not get_settings().sec_contact.strip():
        raise SourceNotConfigured("sec", "Reading holdings tables needs your SEC contact. Add ATLAS_SEC_CONTACT to .env.")
    folder = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
    headers = sec._headers()
    index = await get_fetcher().get("sec", INDEX.format(cik=cik, acc=accession.replace("-", "")), headers=headers, ttl=30 * 86400)
    names = [i["name"] for i in index.json()["directory"]["item"] if i["name"].lower().endswith(".xml") and "primary_doc" not in i["name"].lower()]
    if not names:
        return []
    got = await get_fetcher().get("sec", folder + names[0], headers=headers, ttl=365 * 86400)
    return parse_table(got.body)
