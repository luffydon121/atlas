"""Headlines from public RSS feeds. Feed text is untrusted: parsed safely and stored as data."""

import asyncio
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from defusedxml import ElementTree
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from atlas.core.envelope import utcnow
from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import get_fetcher
from atlas.db import NewsItem, session_scope

# tier: official = primary source publication, media = independent journalism
FEEDS = [
    ("Federal Reserve", "official", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("Reserve Bank of Australia", "official", "https://www.rba.gov.au/rss/rss-cb-media-releases.xml"),
    ("European Central Bank", "official", "https://www.ecb.europa.eu/rss/press.html"),
    ("US SEC", "official", "https://www.sec.gov/news/pressreleases.rss"),
    ("BBC Business", "media", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("The Guardian Business", "media", "https://www.theguardian.com/business/rss"),
    ("Al Jazeera", "media", "https://www.aljazeera.com/xml/rss/all.xml"),
]
_TAG = re.compile(r"<[^>]+>")


def _date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed


def parse_feed(xml_text: str) -> list[dict]:
    root = ElementTree.fromstring(xml_text.lstrip("﻿ \n"))
    ns = {"a": "http://www.w3.org/2005/Atom", "rss": "http://purl.org/rss/1.0/", "dc": "http://purl.org/dc/elements/1.1/"}
    items = []
    for node in root.iter("item"):
        items.append({"title": node.findtext("title"), "url": node.findtext("link"), "summary": node.findtext("description"),
                      "published": node.findtext("pubDate") or node.findtext("dc:date", namespaces=ns)})
    for node in root.findall("rss:item", ns):
        items.append({"title": node.findtext("rss:title", namespaces=ns), "url": node.findtext("rss:link", namespaces=ns),
                      "summary": node.findtext("rss:description", namespaces=ns), "published": node.findtext("dc:date", namespaces=ns)})
    for node in root.findall("a:entry", ns):
        link = node.find("a:link", ns)
        items.append({"title": node.findtext("a:title", namespaces=ns), "url": link.get("href") if link is not None else None,
                      "summary": node.findtext("a:summary", namespaces=ns), "published": node.findtext("a:updated", namespaces=ns)})
    cleaned = []
    for item in items:
        if not item["title"] or not (item["url"] or "").startswith(("http://", "https://")):
            continue
        summary = _TAG.sub("", item["summary"] or "").strip()[:400] or None
        cleaned.append({"title": _TAG.sub("", item["title"]).strip(), "url": item["url"].strip(), "summary": summary,
                        "published_at": _date(item["published"])})
    return cleaned


async def _pull(publisher: str, tier: str, url: str) -> int:
    got = await get_fetcher().get("rss", url, ttl=900)
    rows = [{**i, "publisher": publisher, "tier": tier, "first_seen": utcnow()} for i in parse_feed(got.body)]
    if not rows:
        return 0
    with session_scope() as db:
        db.execute(insert(NewsItem).values(rows).on_conflict_do_nothing(index_elements=["url"]))
    return len(rows)


async def refresh() -> dict:
    results = await asyncio.gather(*(_pull(p, t, u) for p, t, u in FEEDS), return_exceptions=True)
    failed = [p for (p, _, _), r in zip(FEEDS, results, strict=True) if isinstance(r, SourceUnavailable | ElementTree.ParseError)]
    return {"failed": failed}


def latest(limit: int = 60, tier: str | None = None, q: str | None = None) -> list[dict]:
    stmt = select(NewsItem).order_by(NewsItem.published_at.desc().nullslast()).limit(limit)
    if tier:
        stmt = stmt.where(NewsItem.tier == tier)
    if q:
        stmt = stmt.where(NewsItem.title.icontains(q) | NewsItem.summary.icontains(q))
    with session_scope() as db:
        rows = db.scalars(stmt).all()
    return [{"title": r.title, "url": r.url, "summary": r.summary, "publisher": r.publisher, "tier": r.tier,
             "published_at": r.published_at.isoformat() + "Z" if r.published_at else None} for r in rows]
