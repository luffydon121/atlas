"""Saved monitoring areas: scene discovery, index history and same-season comparison."""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta

import numpy as np
from sqlalchemy import select

from atlas.core.envelope import iso, utcnow
from atlas.db import MonitoringArea, Notification, SatelliteMeasurement, session_scope
from atlas.services import satellite

log = logging.getLogger("atlas.monitor")
TRACKERS = {"mine": ("Mine expansion", "bsi"), "construction": ("Large construction", "bsi"), "agriculture": ("Agriculture", "ndvi"), "deforestation": ("Deforestation", "ndvi"), "wildfire": ("Wildfire damage", "nbr"),
            "reservoir": ("Reservoir level", "ndwi"), "industrial": ("Industrial land", "bsi"), "coast": ("Coastal change", "ndwi"), "solar": ("Solar farm construction", "bsi")}
MAX_VERTICES = 200
BASELINE_WINDOW_DAYS = 30


def bbox_of(polygon: list[list[float]]) -> list[float]:
    lons, lats = [p[0] for p in polygon], [p[1] for p in polygon]
    return [min(lons), min(lats), max(lons), max(lats)]


def check_polygon(polygon: list[list[float]]) -> None:
    if not 3 <= len(polygon) <= MAX_VERTICES:
        raise ValueError(f"Draw between 3 and {MAX_VERTICES} points")
    if any(len(p) != 2 or not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90) for p in polygon):
        raise ValueError("Points must be longitude and latitude")
    satellite.bbox_guard(bbox_of(polygon))


def polygon_mask(polygon: list[list[float]], bbox: list[float], shape: tuple[int, int]) -> np.ndarray:
    """True inside the drawn shape. Works in image space, so a bbox-aligned square covers every pixel."""
    from rasterio.features import rasterize
    from rasterio.transform import from_bounds

    ring = [*polygon, polygon[0]]
    transform = from_bounds(*bbox, shape[1], shape[0])
    return rasterize([({"type": "Polygon", "coordinates": [ring]}, 1)], out_shape=shape, transform=transform, fill=0, default_value=1, dtype="uint8").astype(bool)


def masked(values: np.ndarray, polygon: list[list[float]], bbox: list[float]) -> np.ndarray:
    out = values.copy()
    out[~polygon_mask(polygon, bbox, values.shape)] = np.nan
    return out


def same_season(acquired: str, scenes: list[dict], window: int = BASELINE_WINDOW_DAYS) -> dict | None:
    """The clearest scene from about a year earlier, so seasonal greening is not read as change."""
    target = datetime.fromisoformat(acquired[:10]) - timedelta(days=365)
    near = [s for s in scenes if abs((datetime.fromisoformat(s["acquired_at"][:10]) - target).days) <= window]
    return min(near, key=lambda s: s["cloud_cover"] if s["cloud_cover"] is not None else 100, default=None)


def to_dict(a: MonitoringArea) -> dict:
    return {"id": a.id, "name": a.name, "tracker": a.tracker, "tracker_label": TRACKERS.get(a.tracker, (a.tracker,))[0], "index": a.index_name, "polygon": json.loads(a.polygon), "frequency_days": a.frequency_days, "max_cloud": a.max_cloud, "alert_pct": a.alert_pct,
            "enabled": a.enabled, "last_scene": a.last_scene, "last_checked": iso(a.last_checked), "last_error": a.last_error}


async def check_area(area_id: int) -> dict:
    with session_scope() as db:
        a = db.get(MonitoringArea, area_id)
        spec = to_dict(a)
    polygon, index = spec["polygon"], spec["index"]
    bbox = bbox_of(polygon)
    today = date.today()
    recent = (await satellite.search(bbox, (today - timedelta(days=60)).isoformat(), today.isoformat(), max_cloud=spec["max_cloud"], limit=10))["scenes"]
    result: dict = {"new_scene": False}
    if recent and recent[0]["id"] != spec["last_scene"]:
        latest = recent[0]
        year_ago = datetime.fromisoformat(latest["acquired_at"][:10]) - timedelta(days=365)
        older = (await satellite.search(bbox, (year_ago - timedelta(days=BASELINE_WINDOW_DAYS)).date().isoformat(), (year_ago + timedelta(days=BASELINE_WINDOW_DAYS)).date().isoformat(), max_cloud=spec["max_cloud"], limit=20))["scenes"]
        after = masked(await asyncio.to_thread(satellite.compute_index, latest, bbox, index), polygon, bbox)
        inside = polygon_mask(polygon, bbox, after.shape).sum()
        clear = float((~np.isnan(after)).sum() / max(inside, 1))
        with session_scope() as db:
            db.add(SatelliteMeasurement(aoi=f"area:{area_id}", index_name=index, scene_id=latest["id"], acquired_at=latest["acquired_at"], mean=float(np.nanmean(after)) if clear else 0.0, valid_fraction=clear))
        result = {"new_scene": True, "scene": latest["id"], "clear_fraction": round(clear, 3)}
        base = same_season(latest["acquired_at"], older)
        if base and clear >= 0.5:
            before = masked(await asyncio.to_thread(satellite.compute_index, base, bbox, index), polygon, bbox)
            stats = satellite.change_stats(before, after)
            changed = stats.get("pct_increased", 0) + stats.get("pct_decreased", 0)
            result.update({"baseline_scene": base["id"], "stats": stats, "changed_pct": changed})
            if spec["alert_pct"] is not None and changed >= spec["alert_pct"] and stats["confidence"] in {"high", "medium"}:
                with session_scope() as db:
                    db.add(Notification(title=f"{spec['name']}: {changed:.1f}% of pixels changed", body=f"{base['acquired_at'][:10]} to {latest['acquired_at'][:10]}, same season. Confidence {stats['confidence']}.", severity="info"))
    with session_scope() as db:
        a = db.get(MonitoringArea, area_id)
        a.last_checked, a.last_error = utcnow(), None
        if result.get("scene"):
            a.last_scene = result["scene"]
    return result


async def run_due() -> int:
    now = utcnow()
    with session_scope() as db:
        due = [a.id for a in db.scalars(select(MonitoringArea).where(MonitoringArea.enabled)) if a.last_checked is None or now - a.last_checked >= timedelta(days=a.frequency_days)]
    for area_id in due:
        try:
            await check_area(area_id)
        except Exception as exc:
            log.warning("Area %s failed: %s", area_id, exc)
            with session_scope() as db:
                a = db.get(MonitoringArea, area_id)
                a.last_checked, a.last_error = now, str(exc)[:400]
    return len(due)


def history(area_id: int) -> list[dict]:
    with session_scope() as db:
        rows = db.scalars(select(SatelliteMeasurement).where(SatelliteMeasurement.aoi == f"area:{area_id}").order_by(SatelliteMeasurement.acquired_at)).all()
    return [{"acquired_at": r.acquired_at, "index": r.index_name, "mean": r.mean, "clear_fraction": r.valid_fraction, "scene_id": r.scene_id} for r in rows]


def report(area_id: int) -> str:
    with session_scope() as db:
        a = to_dict(db.get(MonitoringArea, area_id))
    rows = history(area_id)
    lines = [f"# {a['name']}", "", f"Tracker: {a['tracker_label']}. Index: {a['index']}. Checked every {a['frequency_days']} days.", "", "Sentinel-2 pixels are 10 to 20 m. Change can also come from season, sun angle or residual cloud.", "", "| Acquired | Mean | Clear share | Scene |", "| --- | --- | --- | --- |"]
    lines += [f"| {r['acquired_at'][:10]} | {r['mean']:.3f} | {r['clear_fraction'] * 100:.0f}% | {r['scene_id']} |" for r in rows]
    return "\n".join(lines) + ("\n" if rows else "\nNo observations yet.\n")
