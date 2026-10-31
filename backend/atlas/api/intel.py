import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.connectors import calendar, holdings, sec, trade, world
from atlas.core import reference as ref
from atlas.core.envelope import Freshness, envelope
from atlas.core.errors import SourceNotConfigured
from atlas.db import MonitoringArea, get_db
from atlas.services import reports, satellite, satellite_monitor

router = APIRouter(prefix="/api", tags=["intelligence"])


# -- Trade ------------------------------------------------------------------------------------------------

@router.get("/trade/ports")
async def ports():
    missing = [p for p in ref.PORT_DASHBOARD if p["portname"] not in trade.LATEST_PORTS]
    if missing:
        await trade.start_refresh()
    rows = [{**p, **trade.LATEST_PORTS.get(p["portname"], {"available": False, "loading": True})} for p in ref.PORT_DASHBOARD]
    return envelope(rows, source="portwatch", freshness=Freshness.HISTORICAL, note=("Port data loads slowly on a first run and fills in by itself. " if missing else "") + "Port calls are satellite AIS estimates. A rise or fall is a proxy, not a measure of queues or live vessels.")


@router.get("/trade/routes")
async def routes():
    rows = await world.chokepoints_ready(15)
    energy = [{k: c.get(k) for k in ("name", "tanker_7d", "container_7d", "pct_vs_baseline", "disrupted", "latest_date")} for c in rows if c.get("available")]
    return envelope({"chokepoints": energy, "routes": [r["name"] for r in ref.TRADE_ROUTES]}, source="portwatch", freshness=Freshness.HISTORICAL)


# -- Economics --------------------------------------------------------------------------------------------

def _strip(res: dict) -> dict:
    return {k: v for k, v in res.items() if not k.startswith("_")}


@router.get("/econ/central-banks")
async def central_banks():
    res = await trade.policy_rates()
    return envelope(res["rows"], source="bis", freshness=Freshness.HISTORICAL, fetched_at=res["_fetched"], stale=res["_stale"], note="Policy rates from the BIS. ATLAS has no free consensus forecast, so it shows what changed, not surprises.")


@router.get("/econ/compare/{measure}")
async def compare(measure: str):
    readers = {"inflation": trade.inflation, "unemployment": trade.unemployment}
    if measure not in readers:
        raise HTTPException(404, "Unknown measure")
    res = await readers[measure]()
    note = f"OECD data. Not available here: {', '.join(res['missing'])}." if res["missing"] else "OECD data."
    return envelope(_strip(res), source="oecd", freshness=Freshness.HISTORICAL, fetched_at=res["_fetched"], stale=res["_stale"], note=note)


@router.get("/econ/releases")
async def releases():
    rows = await trade.releases()
    return envelope(calendar_upcoming(rows), source="calendars", freshness=Freshness.REFERENCE, note="Official BEA release dates. No consensus forecasts are shown, because no free official source exists.")


def calendar_upcoming(rows: list[dict]) -> list[dict]:
    from datetime import date

    return calendar.upcoming(rows, date.today(), 90)


# -- Institutional holdings -------------------------------------------------------------------------------

@router.get("/holdings/filers")
async def filers():
    return envelope([{"cik": c, "name": n} for c, n in holdings.FILERS.items()], source="sec", freshness=Freshness.REFERENCE)


@router.get("/holdings/{cik}")
async def holdings_view(cik: int):
    if cik not in holdings.FILERS:
        raise HTTPException(404, "Choose a listed filer")
    got = await sec.submissions(cik)
    sub = got.json()
    rows = holdings.filings(sub)
    latest = previous = None
    blocked = None
    if rows:
        try:
            latest = await holdings.table(cik, rows[0]["accession"])
            if len(rows) > 1:
                previous = await holdings.table(cik, rows[1]["accession"])
        except SourceNotConfigured as exc:
            blocked = exc.reason
    return envelope({"name": holdings.FILERS[cik], "filings": rows, "positions": (latest or [])[:50], "changes": holdings.changes(previous, latest) if latest and previous else None, "blocked": blocked}, source="sec", freshness=Freshness.HISTORICAL, fetched_at=got.fetched_at, stale=got.stale,
                    note="13F filings arrive up to 45 days after quarter end, list long US positions only, and may omit confidential positions.")


# -- Satellite monitoring ---------------------------------------------------------------------------------

class AreaIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    tracker: str = "agriculture"
    index: str | None = Field(None, pattern="^(ndvi|ndwi|bsi|nbr)$")
    polygon: list[list[float]] = Field(min_length=3, max_length=200)
    frequency_days: int = Field(7, ge=1, le=90)
    max_cloud: float = Field(15, ge=0, le=100)
    alert_pct: float | None = Field(None, gt=0, le=100)


@router.get("/satellite/areas")
def areas(db: Session = Depends(get_db)):
    return {"areas": [satellite_monitor.to_dict(a) for a in db.scalars(select(MonitoringArea).order_by(MonitoringArea.id))], "trackers": {k: {"label": v[0], "index": v[1]} for k, v in satellite_monitor.TRACKERS.items()}, "indices": {k: v["name"] for k, v in satellite.INDICES.items()}}


@router.post("/satellite/areas", status_code=201)
def create_area(body: AreaIn, db: Session = Depends(get_db)):
    if body.tracker not in satellite_monitor.TRACKERS:
        raise HTTPException(422, "Unknown tracker")
    try:
        satellite_monitor.check_polygon(body.polygon)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    area = MonitoringArea(name=body.name, tracker=body.tracker, index_name=body.index or satellite_monitor.TRACKERS[body.tracker][1], polygon=json.dumps(body.polygon), frequency_days=body.frequency_days, max_cloud=body.max_cloud, alert_pct=body.alert_pct)
    db.add(area)
    db.flush()
    return satellite_monitor.to_dict(area)


@router.delete("/satellite/areas/{area_id}", status_code=204)
def delete_area(area_id: int, db: Session = Depends(get_db)):
    area = db.get(MonitoringArea, area_id)
    if not area:
        raise HTTPException(404, "Not found")
    db.delete(area)


@router.post("/satellite/areas/{area_id}/check")
async def check_area(area_id: int, db: Session = Depends(get_db)):
    if not db.get(MonitoringArea, area_id):
        raise HTTPException(404, "Not found")
    return await satellite_monitor.check_area(area_id)


@router.get("/satellite/areas/{area_id}/history")
def area_history(area_id: int):
    return satellite_monitor.history(area_id)


@router.get("/satellite/areas/{area_id}/report", response_class=PlainTextResponse)
def area_report(area_id: int, db: Session = Depends(get_db)):
    if not db.get(MonitoringArea, area_id):
        raise HTTPException(404, "Not found")
    return PlainTextResponse(satellite_monitor.report(area_id), media_type="text/markdown")


# -- Briefings --------------------------------------------------------------------------------------------

class BriefingIn(BaseModel):
    kind: str = Field("daily", pattern="^(daily|weekly|asset|country|commodity)$")
    subject: str | None = Field(None, max_length=60)


@router.post("/briefings", status_code=201)
async def create_briefing(body: BriefingIn):
    try:
        return await reports.generate(body.kind, body.subject)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/briefings")
def list_briefings():
    return reports.recent()


@router.get("/briefings/latest")
async def latest_briefing():
    found = reports.latest() or await reports.generate("daily", save=not reports.read_only())
    return envelope(found, source="atlas", freshness=Freshness.DELAYED, note="Written from retrieved data by fixed rules. Unavailable feeds are listed in the briefing.")


@router.get("/briefings/{briefing_id}")
def get_briefing(briefing_id: int):
    found = reports.get(briefing_id)
    if not found:
        raise HTTPException(404, "Not found")
    return found


@router.get("/briefings/{briefing_id}/export")
def export_briefing(briefing_id: int, format: str = Query("md", pattern="^(md|html)$")):
    found = reports.get(briefing_id)
    if not found:
        raise HTTPException(404, "Not found")
    if format == "html":
        return HTMLResponse(reports.to_html(found["markdown"], found["title"]))
    return PlainTextResponse(found["markdown"], media_type="text/markdown")


