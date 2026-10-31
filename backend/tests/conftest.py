import asyncio

import pytest

from atlas import db
from atlas.connectors import world
from atlas.core.fetcher import set_fetcher
from atlas.core.memo import clear_memos


@pytest.fixture(autouse=True)
def no_real_shipping_calls(monkeypatch):
    """The background chokepoint task outlives a request, so tests must not leave one running."""

    async def empty():
        return []

    world.LATEST_CHOKEPOINTS.clear()
    monkeypatch.setattr(world, "_chokepoint_task", None)
    monkeypatch.setattr(world, "chokepoints", empty)
    yield
    task = world._chokepoint_task
    if isinstance(task, asyncio.Task):
        task.cancel()


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_SCHEDULER_ENABLED", "false")
    db.init_db(f"sqlite:///{tmp_path / 'test.db'}")
    set_fetcher(None)
    clear_memos()
    yield
    set_fetcher(None)
