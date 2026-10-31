from fastapi import APIRouter, HTTPException, Query

from atlas.core import exposure
from atlas.core.envelope import Freshness, envelope
from atlas.core.memo import memo
from atlas.services import impact

router = APIRouter(prefix="/api", tags=["impact"])


@router.get("/impact/events")
async def events(days: int = Query(30, ge=1, le=365), category: str | None = Query(None, max_length=40), verification: str | None = Query(None, pattern="^(official|derived|unverified)$")):
    status = await impact.refresh()
    rows = impact.feed(days, category, verification)
    return envelope({"events": rows, "categories": impact.CATEGORIES, "unavailable": status["failed"]}, source=["usgs", "nhc", "eonet", "federalregister", "gdelt", "portwatch", "openmeteo"], freshness=Freshness.DELAYED,
                    note="Official comes straight from a government source. Derived is calculated by ATLAS from official or public data. Unverified is machine-collected news.")


@router.get("/impact/events/{event_id}")
async def event(event_id: int):
    found = await impact.detail(event_id)
    if found is None:
        raise HTTPException(404, "Event not found")
    return envelope(found, source=[found["source"]], freshness=Freshness.DELAYED, as_of=found["observed_at"], note=impact.HYPOTHESIS)


@memo(3600)
async def _reactions(rule_ids: tuple[str, ...]) -> dict:
    rules = [exposure.RULES_BY_ID[r] for r in rule_ids]
    info = impact.describe(rules)
    return await impact.reactions(info["assets"], [a["date"] for a in info["analogues"]])


@router.get("/impact/reactions")
async def reactions(rules: str = Query(min_length=1, max_length=200)):
    ids = tuple(sorted({r for r in rules.split(",") if r in exposure.RULES_BY_ID}))
    if not ids:
        raise HTTPException(404, "Unknown rule")
    result = await _reactions(ids)
    return envelope(result, source="yahoo", freshness=Freshness.HISTORICAL, note=result["note"])


@router.get("/impact/scenario")
def scenario(zone: str | None = Query(None, max_length=30), crop: str | None = Query(None, max_length=30), chokepoint: str | None = Query(None, max_length=30)):
    if zone and zone not in exposure.ZONES:
        raise HTTPException(404, "Unknown zone")
    return envelope(impact.scenario(zone, crop, chokepoint), source="atlas", freshness=Freshness.REFERENCE, note="A what-if view built from documented exposure rules. No live event is implied.")


@router.get("/graph")
def graph(q: str = Query("", max_length=60)):
    return envelope(impact.graph(q), source="atlas", freshness=Freshness.REFERENCE, note="Hand-written links from public documents. A link means possible exposure, not a measured relationship.")


