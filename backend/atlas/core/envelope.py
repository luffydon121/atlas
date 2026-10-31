"""Every API response carries provenance so the UI can never blur live and historical data."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


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
    return {
        "data": data,
        "meta": {
            "source": source if isinstance(source, list) else [source],
            "freshness": freshness.value,
            "as_of": as_of,
            "fetched_at": iso(fetched_at or utcnow()),
            "stale": stale,
            "note": note,
        },
    }
