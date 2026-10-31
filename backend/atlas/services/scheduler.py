"""In-process background jobs. No external queue or cloud service required."""

import asyncio
import logging
import time

from atlas.api import market
from atlas.config import get_settings
from atlas.connectors import econ, news, world
from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import prune_cache
from atlas.core.reference import WEATHER_REGIONS
from atlas.services import alerts, briefing

log = logging.getLogger("atlas.scheduler")


async def _refresh_econ() -> None:
    for series in econ.CATALOG:
        try:
            await econ.load(series)
        except SourceUnavailable as exc:
            log.info("Skipped %s: %s", series.id, exc.reason)


async def _warm_weather() -> None:
    for commodity in WEATHER_REGIONS:
        await world.commodity_risk(commodity)


async def _warm_market() -> None:
    await market._overview_quotes()
    await briefing.today()


async def _warm_universe() -> None:
    await market._universe()


async def _warm_shipping() -> None:
    await world.chokepoints()


async def _prune() -> None:
    prune_cache()


async def run() -> None:
    settings = get_settings()
    jobs = [("market", _warm_market, 120), ("news", news.refresh, 900), ("universe", _warm_universe, 3600), ("alerts", alerts.evaluate_all, settings.alert_interval_seconds),
            ("econ", _refresh_econ, 6 * 3600), ("shipping", _warm_shipping, 12 * 3600), ("weather", _warm_weather, 86400), ("cache", _prune, 86400)]
    last = dict.fromkeys((name for name, _, _ in jobs), 0.0)
    await asyncio.sleep(1)
    while True:
        for name, job, every in jobs:
            if time.monotonic() - last[name] >= every:
                last[name] = time.monotonic()
                try:
                    await job()
                except Exception:
                    log.exception("Job %s failed", name)
        await asyncio.sleep(10)
