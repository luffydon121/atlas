"""What runs in the background, and how often. Nothing here needs an external service."""

import asyncio
import logging

from atlas.api import market
from atlas.config import get_settings
from atlas.connectors import econ, news, world
from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import prune_cache
from atlas.core.reference import WEATHER_REGIONS
from atlas.services import alerts, briefing, jobs, maintenance

log = logging.getLogger("atlas.scheduler")


async def _refresh_econ() -> None:
    for series in econ.CATALOG:
        try:
            await econ.load(series)
        except SourceUnavailable as exc:
            log.info("Skipped %s: %s", series.id, exc.reason)


async def _market() -> None:
    await market._overview_quotes()
    await briefing.today()


async def _universe() -> None:
    await market._universe()


async def _weather() -> None:
    for commodity in WEATHER_REGIONS:
        await world.commodity_risk(commodity)


async def _shipping() -> None:
    await world.chokepoints()


async def _housekeeping() -> None:
    prune_cache()
    jobs.prune_history()


def job_list() -> list[jobs.Job]:
    settings = get_settings()
    return [
        jobs.Job("market", _market, 120, 60, 0, "yahoo", "Market quotes and Today"),
        jobs.Job("news", news.refresh, 900, 90, 1, "rss", "News feeds"),
        jobs.Job("alerts", alerts.evaluate_all, settings.alert_interval_seconds, 240, 0, None, "Alert rules"),
        jobs.Job("universe", _universe, 3600, 180, 1, "yahoo", "Screener universe"),
        jobs.Job("economy", _refresh_econ, 6 * 3600, 300, 1, None, "Economic series"),
        jobs.Job("shipping", _shipping, 12 * 3600, 240, 1, "portwatch", "Chokepoint transits"),
        jobs.Job("weather", _weather, 86400, 300, 1, "openmeteo_archive", "Crop-region weather"),
        jobs.Job("backup", maintenance.scheduled_backup, 86400, 120, 1, None, "Database backup"),
        jobs.Job("housekeeping", _housekeeping, 86400, 60, 0, None, "Expire caches and job history"),
    ]


def build() -> jobs.Runner:
    runner = jobs.Runner(job_list())
    jobs.set_runner(runner)
    return runner


async def stop(runner: jobs.Runner) -> None:
    await asyncio.shield(runner.stop())
