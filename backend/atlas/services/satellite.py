"""Open Sentinel-2 imagery: catalogue search and pixel-level index change detection.

Sentinel-2 bands are 10-20 m. That resolves mine pits, reservoirs, fields and large construction
sites. It cannot resolve vehicles or tank roofs, so the trackers refuse those claims explicitly.
"""

import base64
import io
import logging

import numpy as np
from PIL import Image

from atlas.core.errors import SourceUnavailable
from atlas.core.fetcher import get_fetcher

log = logging.getLogger("atlas.satellite")
CATALOGS = {"earthsearch": "https://earth-search.aws.element84.com/v1/search", "cdse": "https://stac.dataspace.copernicus.eu/v1/search"}
COLLECTIONS = {"sentinel-2": {"earthsearch": "sentinel-2-l2a", "cdse": "sentinel-2-l2a"}, "landsat": {"earthsearch": "landsat-c2-l2"}}
GSD = {"sentinel-2": 10, "landsat": 30}
MAX_AOI_DEGREES = 0.3
INDICES = {
    "ndvi": {"bands": ("nir", "red"), "name": "Vegetation (NDVI)", "meaning": "Higher means denser green vegetation"},
    "ndwi": {"bands": ("green", "nir"), "name": "Surface water (NDWI)", "meaning": "Above 0 usually indicates open water"},
    "bsi": {"bands": ("swir16", "nir"), "name": "Bare ground (NDBI-style)", "meaning": "Higher means more exposed soil or built surface"},
    "nbr": {"bands": ("nir", "swir22"), "name": "Burn ratio (NBR)", "meaning": "A large fall after a fire indicates burned vegetation"},
}
# Sentinel-2 scene classes kept as clear ground: vegetation, bare soil, water, unclassified.
CLEAR_SCL = (4, 5, 6, 7)
UNSUPPORTED = {
    "retail": "Parking-lot occupancy needs sub-metre imagery. Sentinel-2 at 10 m cannot see individual vehicles, so no estimate is made.",
    "oil": "Floating-roof tank inventory needs high-resolution shadow geometry. Sentinel-2 at 10 m cannot measure it, so no estimate is made.",
}


def scene_from_item(item: dict, mission: str) -> dict:
    p, assets = item["properties"], item.get("assets", {})
    return {"id": item["id"], "acquired_at": p.get("datetime"), "cloud_cover": p.get("eo:cloud_cover"), "platform": p.get("platform"),
            "constellation": p.get("constellation"), "mission": mission, "resolution_m": GSD[mission],
            "thumbnail": (assets.get("thumbnail") or assets.get("preview") or {}).get("href"), "bbox": item.get("bbox"),
            "assets": {k: assets[k]["href"] for k in ("red", "green", "nir", "swir16", "swir22", "scl") if k in assets}}


async def search(bbox: list[float], start: str, end: str, mission: str = "sentinel-2", max_cloud: float = 30, limit: int = 20, catalog: str = "earthsearch") -> dict:
    collection = COLLECTIONS.get(mission, {}).get(catalog)
    if not collection:
        raise ValueError(f"{mission} is not available from {catalog}")
    body = {"collections": [collection], "bbox": bbox, "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": limit,
            "query": {"eo:cloud_cover": {"lt": max_cloud}}, "sortby": [{"field": "properties.datetime", "direction": "desc"}]}
    if catalog == "cdse":
        del body["query"]
        body["filter"] = {"op": "<", "args": [{"property": "eo:cloud_cover"}, max_cloud]}
    got = await get_fetcher().get(catalog, CATALOGS[catalog], method="POST", json_body=body, ttl=3600,
                                  headers={"Content-Type": "application/json"})
    payload = got.json()
    return {"scenes": [scene_from_item(i, mission) for i in payload.get("features", [])], "matched": (payload.get("context") or {}).get("matched"),
            "_fetched": got.fetched_at, "_stale": got.stale}


def normalised_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    total = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(total > 0, (a - b) / total, np.nan)


def change_stats(before: np.ndarray, after: np.ndarray, threshold: float = 0.15) -> dict:
    """Pixel statistics over the area both acquisitions observed clearly."""
    valid = ~np.isnan(before) & ~np.isnan(after)
    n = int(valid.sum())
    if n == 0:
        return {"valid_fraction": 0.0, "confidence": "none"}
    delta = after[valid] - before[valid]
    frac = n / before.size
    noise = float(np.median(np.abs(delta - np.median(delta)))) * 1.4826
    return {"valid_fraction": round(frac, 3), "mean_before": round(float(np.nanmean(before[valid])), 4), "mean_after": round(float(np.nanmean(after[valid])), 4),
            "mean_change": round(float(delta.mean()), 4), "pct_increased": round(float((delta > threshold).mean() * 100), 2),
            "pct_decreased": round(float((delta < -threshold).mean() * 100), 2), "threshold": threshold, "noise_sigma": round(noise, 4),
            "confidence": "high" if frac >= 0.9 and noise < threshold / 2 else "medium" if frac >= 0.7 else "low"}


def change_png(before: np.ndarray, after: np.ndarray, threshold: float = 0.15) -> str:
    """Transparent overlay: blue where the index rose, orange where it fell."""
    delta = after - before
    h, w = delta.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[np.nan_to_num(delta) > threshold] = (56, 140, 245, 210)
    rgba[np.nan_to_num(delta) < -threshold] = (240, 130, 40, 210)
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _read_band(href: str, bbox: list[float], shape: tuple[int, int]) -> np.ndarray:
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    env = {"AWS_NO_SIGN_REQUEST": "YES", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif", "GDAL_HTTP_TIMEOUT": "30"}
    with rasterio.Env(**env), rasterio.open(href) as src:
        bounds = transform_bounds("EPSG:4326", src.crs, *bbox)
        window = from_bounds(*bounds, transform=src.transform)
        return src.read(1, window=window, out_shape=shape, resampling=Resampling.bilinear, boundless=True, fill_value=0).astype("float32")


def compute_index(scene: dict, bbox: list[float], index: str) -> np.ndarray:
    """Reads two bands and the scene classification, masking cloud, shadow and no-data pixels."""
    a_key, b_key = INDICES[index]["bands"]
    missing = [k for k in (a_key, b_key, "scl") if k not in scene["assets"]]
    if missing:
        raise SourceUnavailable("earthsearch", f"Scene {scene['id']} lacks {missing}")
    deg = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
    side = int(min(512, max(128, deg * 111_000 / 20)))
    shape = (side, side)
    try:
        a = _read_band(scene["assets"][a_key], bbox, shape)
        b = _read_band(scene["assets"][b_key], bbox, shape)
        scl = _read_band(scene["assets"]["scl"], bbox, shape).round()
    except Exception as exc:
        raise SourceUnavailable("earthsearch", f"Could not read imagery: {exc}") from exc
    value = normalised_difference(a, b)
    value[~np.isin(scl, CLEAR_SCL)] = np.nan
    return value


def bbox_guard(bbox: list[float]) -> None:
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid bounding box")
    if east - west > MAX_AOI_DEGREES or north - south > MAX_AOI_DEGREES:
        raise ValueError(f"Area too large: keep each side under {MAX_AOI_DEGREES} degrees")
