"""Real-network checks. Run with `uv run pytest -m live`."""

import pytest

from atlas.connectors import econ, world, yahoo

pytestmark = pytest.mark.live


async def test_yahoo_returns_a_price():
    assert (await yahoo.quote_for("AAPL"))["price"] > 0


async def test_treasury_curve_is_recent():
    assert (await econ.load(econ.BY_ID["us.y10"]))[0][-1][1] > 0


async def test_chokepoints_are_current():
    row = await world.chokepoint({"id": "chokepoint1", "name": "Suez", "lat": 0, "lon": 0})
    assert row["available"] and row["latest_date"] > "2026-01-31"
