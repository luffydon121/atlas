"""Scheduled events. Central bank dates are official. Earnings dates are labelled estimates."""

import html
import re
from datetime import date

from atlas.connectors import sec
from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import get_fetcher

FOMC = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
RBA = "https://www.rba.gov.au/schedules-events/board-meeting-schedules.html"
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1)}
SHORT = {m[:3]: i for m, i in MONTHS.items()}


def _month(name: str) -> int | None:
    return MONTHS.get(name) or SHORT.get(name[:3])


def parse_fomc(html: str) -> list[dict]:
    """Each meeting is dated by its final day, when the decision is published."""
    out = []
    sections = re.split(r"(\d{4}) FOMC Meetings", html)
    for year_text, body in zip(sections[1::2], sections[2::2], strict=True):
        rows = re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>\s*([^<]+?)\s*<', body, re.S)
        for month_text, days in rows:
            parts = re.findall(r"\d+", days)
            names = month_text.strip().split("/")
            month = _month(names[-1].strip())
            if not parts or month is None:
                continue
            out.append({"date": date(int(year_text), month, int(parts[-1])).isoformat(), "title": "FOMC rate decision", "region": "US",
                        "kind": "central_bank", "confirmed": True, "url": FOMC})
    return out


def parse_rba(page: str) -> list[dict]:
    """Reads only the first data column. The second column is the Payments System Board, which does not set rates."""
    out = []
    sections = re.split(r"schedules\s+(20\d\d)", page)
    for year_text, body in zip(sections[1::2], sections[2::2], strict=True):
        for cell in re.findall(r'<th scope="row">[^<]*</th>\s*<td>(.*?)</td>', body, re.S):
            dates = re.findall(r"(\d{1,2}) (" + "|".join(MONTHS) + r")\b", html.unescape(cell))
            if dates:
                day, month = dates[-1]
                out.append({"date": date(int(year_text), MONTHS[month], int(day)).isoformat(), "title": "RBA rate decision", "region": "Australia", "kind": "central_bank", "confirmed": True, "url": RBA})
    return out


async def central_banks() -> tuple[list[dict], list[str]]:
    rows, failed = [], []
    for name, url, parser in (("Federal Reserve", FOMC, parse_fomc), ("RBA", RBA, parse_rba)):
        try:
            rows += parser((await get_fetcher().get("calendars", url, ttl=86400)).body)
        except SourceUnavailable:
            failed.append(name)
    return rows, failed


async def earnings(tickers: list[str]) -> list[dict]:
    out = []
    for ticker in tickers:
        try:
            info = await sec.resolve(ticker)
            dates = sec.earnings_dates((await sec.submissions(info["cik"])).json())
        except SourceUnavailable:
            continue
        if dates["next_estimate"]:
            out.append({"date": dates["next_estimate"], "title": f"{ticker} earnings", "region": "US", "kind": "earnings", "confirmed": False, "ticker": ticker,
                        "url": dates["past"][0]["url"] if dates["past"] else None})
    return out


def upcoming(rows: list[dict], today: date, days: int = 120) -> list[dict]:
    keep = [r for r in rows if 0 <= (date.fromisoformat(r["date"]) - today).days <= days]
    return sorted(keep, key=lambda r: r["date"])
