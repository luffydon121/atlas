import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from atlas.connectors import econ
from atlas.core.envelope import Freshness, envelope
from atlas.core.errors import SourceUnavailable

router = APIRouter(prefix="/api/econ", tags=["economy"])


def _info(s: econ.Series) -> dict:
    return {"id": s.id, "name": s.name, "region": s.region, "group": s.group, "unit": s.unit, "source": s.source}


@router.get("/catalog")
def catalog():
    return envelope([_info(s) for s in econ.CATALOG], source="atlas", freshness=Freshness.REFERENCE)


@router.get("/dashboard")
async def dashboard(region: str = Query("US", max_length=20)):
    picks = [s for s in econ.CATALOG if s.region == region]
    if not picks:
        raise HTTPException(404, "Unknown region")
    results = await asyncio.gather(*(econ.load(s) for s in picks), return_exceptions=True)
    rows, missing = [], []
    for s, res in zip(picks, results, strict=True):
        if isinstance(res, Exception) or not res[0]:
            missing.append({**_info(s), "reason": getattr(res, "reason", "No data returned")})
            continue
        history = res[0][-60:]
        rows.append({**_info(s), "latest": history[-1][1], "period": history[-1][0], "previous": history[-2][1] if len(history) > 1 else None, "stale": res[2],
                     "history": [{"date": p, "value": v} for p, v in history]})
    return envelope({"indicators": rows, "unavailable": missing}, source=sorted({s.source for s in picks}), freshness=Freshness.HISTORICAL)


@router.get("/series/{series_id}")
async def series(series_id: str, as_of: datetime | None = None):
    s = econ.BY_ID.get(series_id)
    if not s:
        raise HTTPException(404, "Unknown series")
    if as_of:
        rows = econ.history(series_id, as_of)
        return envelope({**_info(s), "rows": [{"date": p, "value": v} for p, v in rows]}, source=s.source, freshness=Freshness.HISTORICAL, note=f"Values as first stored locally on or before {as_of:%Y-%m-%d}.")
    rows, fetched, stale = await econ.load(s)
    return envelope({**_info(s), "rows": [{"date": p, "value": v} for p, v in rows]}, source=s.source, freshness=Freshness.HISTORICAL, fetched_at=fetched, stale=stale, as_of=rows[-1][0] if rows else None)


@router.get("/yield-curve")
async def yield_curve():
    data = await econ.yield_curve()
    return envelope(data["curves"], source="treasury", freshness=Freshness.HISTORICAL, fetched_at=data["fetched_at"], stale=data["stale"], as_of=data["curves"][0]["date"] if data["curves"] else None)


@router.get("/recession")
async def recession():
    y10, y2, y3m = await asyncio.gather(econ.load(econ.BY_ID["us.y10"]), econ.load(econ.BY_ID["us.y2"]), econ.load(econ.BY_ID["us.y3m"]))
    a, b, c = dict(y10[0]), dict(y2[0]), dict(y3m[0])
    rows = [{"date": d, "s10y2y": round(a[d] - b[d], 3), "s10y3m": round(a[d] - c[d], 3)} for d in sorted(a) if d in b and d in c]
    unemployment = None
    try:
        rate = (await econ.load(econ.BY_ID["us.unemployment"]))[0]
        trail = [v for _, v in rate[-15:]]
        if len(trail) >= 15:
            three = sum(trail[-3:]) / 3
            low = min(sum(trail[i:i + 3]) / 3 for i in range(len(trail) - 2))
            unemployment = {"sahm_gap": round(three - low, 2), "triggered": three - low >= 0.5, "period": rate[-1][0]}
    except SourceUnavailable:
        pass
    return envelope({"spreads": rows[-500:], "latest": rows[-1] if rows else None, "sahm": unemployment}, source=["treasury", "bls"], freshness=Freshness.ESTIMATED,
                    note="Calculated indicators with historical association to recessions. Not forecasts. Sahm gap uses a 13-month window here.")


@router.get("/global")
async def global_indicator(indicator: str = "gdp_growth"):
    if indicator not in econ.WB_INDICATORS:
        raise HTTPException(404, "Unknown indicator")
    got = await econ.world_bank(indicator, list(econ.WB_COUNTRIES))
    parsed = econ.parse_world_bank(got.json())
    code, name, unit = econ.WB_INDICATORS[indicator]
    countries = [{"code": k, "points": [{"year": y, "value": v} for y, v in rows]} for k, rows in parsed.items()]
    return envelope({"indicator": indicator, "name": name, "unit": unit, "series_code": code, "countries": countries, "choices": {k: v[1] for k, v in econ.WB_INDICATORS.items()}},
                    source="worldbank", freshness=Freshness.HISTORICAL, fetched_at=got.fetched_at, stale=got.stale)
