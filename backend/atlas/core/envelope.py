"""Every API response carries provenance so the UI can never blur live and historical data."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from atlas.core.registry import REGISTRY


class Freshness(StrEnum):
    LIVE = "live"
    DELAYED = "delayed"
    HISTORICAL = "historical"
    ESTIMATED = "estimated"
    REFERENCE = "reference"
    UNAVAILABLE = "unavailable"


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.replace(microsecond=0).isoformat() + "Z"


LIVE_WINDOW_SECONDS = 120


def envelope(
    data: Any,
    *,
    source: str | list[str],
    freshness: Freshness,
    as_of: str | None = None,
    fetched_at: datetime | None = None,
    stale: bool = False,
    note: str | None = None,
) -> dict[str, Any]:
    sources = source if isinstance(source, list) else [source]
    retrieved = fetched_at or utcnow()
    # Nothing older than the live window may be called live, whatever the caller passed.
    if freshness is Freshness.LIVE and (stale or (utcnow() - retrieved).total_seconds() > LIVE_WINDOW_SECONDS):
        freshness = Freshness.DELAYED
    specs = [REGISTRY[s] for s in sources if s in REGISTRY]
    return {
        "data": data,
        "meta": {
            "source": sources,
            "freshness": freshness.value,
            "as_of": as_of,
            "fetched_at": iso(retrieved),
            "stale": stale,
            "note": note,
            "licence": [f"{s.provider}: {s.licence}" for s in specs],
            "limitations": [s.limitations for s in specs],
        },
    }
