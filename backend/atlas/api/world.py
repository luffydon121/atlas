import asyncio
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import Symbol
from atlas.config import get_settings
from atlas.connectors import calendar, crypto, econ, news, trade, world, yahoo
from atlas.core import exposure
from atlas.core import reference as ref
from atlas.core.envelope import Freshness, envelope
from atlas.core.errors import SourceUnavailable
from atlas.db import MonitoringArea, SatelliteMeasurement, session_scope
from atlas.services import analytics, briefing, impact, satellite, satellite_monitor

router = APIRouter(prefix="/api", tags=["world"])


def point(lon, lat, **props) -> dict:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}


def collection(features: list) -> dict:
    return {"type": "FeatureCollection", "features": features}


LAYERS = [
    {"id": "hazards_quakes", "label": "Earthquakes", "group": "Natural disasters", "source": "usgs", "freshness": "live"},
    {"id": "hazards_events", "label": "Wildfires, storms, volcanoes", "group": "Natural disasters", "source": "eonet", "freshness": "live"},
    {"id": "hazards_storms", "label": "Tropical cyclones", "group": "Weather", "source": "nhc", "freshness": "live"},
    {"id": "agriculture", "label": "Crop-region weather screen", "group": "Agriculture", "source": "openmeteo", "freshness": "estimated"},
    {"id": "geopolitics", "label": "Geopolitical events", "group": "Geopolitics", "source": "federalregister,gdelt", "freshness": "live"},
    {"id": "chokepoints", "label": "Chokepoint transits", "group": "Shipping", "source": "portwatch", "freshness": "historical"},
    {"id": "ports", "label": "Major ports", "group": "Shipping", "source": "reference", "freshness": "reference"},
    {"id": "routes", "label": "Trade routes (schematic)", "group": "Shipping", "source": "reference", "freshness": "reference"},
    {"id": "aircraft", "label": "Aircraft in view", "group": "Aviation", "source": "opensky", "freshness": "live"},
    {"id": "airports", "label": "Major airports", "group": "Aviation", "source": "reference", "freshness": "reference"},
    {"id": "energy", "label": "Energy infrastructure", "group": "Energy", "source": "reference", "freshness": "reference"},
    {"id": "industrial", "label": "Mines and industrial sites", "group": "Industry", "source": "reference", "freshness": "reference"},
    {"id": "satellite_aois", "label": "Satellite watch areas", "group": "Satellite", "source": "reference", "freshness": "reference"},
    {"id": "economy", "label": "GDP growth by economy", "group": "Economy", "source": "worldbank", "freshness": "historical"},
    {"id": "impact", "label": "Impact Engine events", "group": "Intelligence", "source": "atlas", "freshness": "delayed"},
    {"id": "zones", "label": "Exposure regions", "group": "Intelligence", "source": "reference", "freshness": "reference"},
    {"id": "monitoring", "label": "Your monitoring areas", "group": "Satellite", "source": "reference", "freshness": "reference"},
]
CAPITALS = {"AU": (-35.3, 149.1), "US": (38.9, -77.0), "CN": (39.9, 116.4), "JP": (35.7, 139.7), "DE": (52.5, 13.4), "GB": (51.5, -0.1), "IN": (28.6, 77.2),
            "BR": (-15.8, -47.9), "ID": (-6.2, 106.8), "KR": (37.6, 127.0)}
ISO3 = {"AUS": "AU", "USA": "US", "CHN": "CN", "JPN": "JP", "DEU": "DE", "GBR": "GB", "IND": "IN", "BRA": "BR", "IDN": "ID", "KOR": "KR"}


_warmup: asyncio.Task | None = None


def _warmup_running() -> bool:
    return _warmup is not None and not _warmup.done()


def _start_warmup() -> None:
    global _warmup

    async def run() -> None:
        for commodity in ref.WEATHER_REGIONS:
            if commodity not in world.LATEST_RISK:
                await world.commodity_risk(commodity)

    _warmup = asyncio.create_task(run())


@router.get("/map/layers")
def layers():
    return envelope(LAYERS, source="atlas", freshness=Freshness.REFERENCE)


async def _events() -> tuple[list[dict], list[str]]:
    results = await asyncio.gather(world.federal_register(), world.gdelt_events(), return_exceptions=True)
    rows = [e for r in results if not isinstance(r, Exception) for e in r]
    labels = ["Federal Register", "GDELT"]
    return rows, [n for n, r in zip(labels, results, strict=True) if isinstance(r, Exception)]


@router.get("/map/layer/{layer}")
async def layer(layer: str, west: float = Query(-180, ge=-180, le=180), south: float = Query(-85, ge=-90, le=90), east: float = Query(180, ge=-180, le=180), north: float = Query(85, ge=-90, le=90)):
    match layer:
        case "hazards_quakes":
            rows = await world.earthquakes()
            return envelope(collection([point(q["lon"], q["lat"], **{k: v for k, v in q.items() if k not in ("lat", "lon")}) for q in rows]), source="usgs", freshness=Freshness.DELAYED)
        case "hazards_events":
            rows = await world.natural_events()
            return envelope(collection([point(e["lon"], e["lat"], **{k: v for k, v in e.items() if k not in ("lat", "lon")}) for e in rows]), source="eonet", freshness=Freshness.DELAYED)
        case "hazards_storms":
            rows = await world.tropical_storms()
            return envelope(collection([point(s["lon"], s["lat"], **{k: v for k, v in s.items() if k not in ("lat", "lon")}) for s in rows if s["lon"] is not None]), source="nhc", freshness=Freshness.DELAYED, note=None if rows else "No active storms in the NHC basins.")
        case "agriculture":
            feats = [point(r["lon"], r["lat"], name=r["region"], commodity=c["commodity"], level=r["risk"]["level"], drivers="; ".join(r["risk"]["drivers"]))
                     for c in world.LATEST_RISK.values() for r in c["regions"]]
            warming = len(world.LATEST_RISK) < len(ref.WEATHER_REGIONS)
            if warming and not _warmup_running():
                _start_warmup()
            return envelope(collection(feats), source="openmeteo", freshness=Freshness.ESTIMATED,
                            note=("Loading climate baselines in the background (about 2 minutes on first run). " if warming else "") + "Weather anomaly screen. Not a production or price forecast.")
        case "geopolitics":
            rows, failed = await _events()
            feats = [point(e["lon"], e["lat"], **{k: v for k, v in e.items() if k not in ("lat", "lon")}) for e in rows if e.get("lat") is not None]
            return envelope(collection(feats), source=["federalregister", "gdelt"], freshness=Freshness.DELAYED, note=(f"Unavailable: {', '.join(failed)}. " if failed else "") + "Pins mark places named in a headline.")
        case "chokepoints":
            rows = await world.chokepoints_ready()
            return envelope(collection([point(c["lon"], c["lat"], **{k: v for k, v in c.items() if k not in ("lat", "lon", "history") and not k.startswith("_")}) for c in rows]), source="portwatch", freshness=Freshness.HISTORICAL)
        case "ports":
            return envelope(collection([point(lon, lat, name=n) for n, lat, lon in ref.PORTS]), source="reference", freshness=Freshness.REFERENCE)
        case "routes":
            feats = [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": r["path"]}, "properties": {"name": r["name"]}} for r in ref.TRADE_ROUTES]
            return envelope(collection(feats), source="reference", freshness=Freshness.REFERENCE, note="Schematic corridors, not vessel tracks.")
        case "aircraft":
            if east - west > 40 or north - south > 40:
                return envelope(collection([]), source="opensky", freshness=Freshness.UNAVAILABLE, note="Zoom in to a region to load aircraft. This protects the free daily quota.")
            res = await world.aircraft((west, south, east, north))
            return envelope(collection([point(s["lon"], s["lat"], callsign=s["callsign"], country=s["country"], altitude_m=s["altitude_m"], velocity_ms=s["velocity_ms"], heading=s["heading"], on_ground=s["on_ground"]) for s in res["states"]]),
                            source="opensky", freshness=Freshness.HISTORICAL if res["_stale"] else Freshness.LIVE, fetched_at=res["_fetched"], stale=res["_stale"])
        case "airports":
            return envelope(collection([point(a["lon"], a["lat"], name=a["name"], code=a["code"]) for a in ref.AIRPORTS]), source="reference", freshness=Freshness.REFERENCE)
        case "energy" | "industrial":
            rows = ref.ENERGY_SITES if layer == "energy" else ref.INDUSTRIAL_SITES
            return envelope(collection([point(s["lon"], s["lat"], name=s["name"], kind=s["kind"]) for s in rows]), source="reference", freshness=Freshness.REFERENCE)
        case "satellite_aois":
            return envelope(collection([point((a["bbox"][0] + a["bbox"][2]) / 2, (a["bbox"][1] + a["bbox"][3]) / 2, id=a["id"], name=a["name"], tracker=a["tracker"]) for a in ref.SATELLITE_AOIS]), source="reference", freshness=Freshness.REFERENCE)
        case "impact":
            await impact.refresh()
            rows = [e for e in impact.feed(30) if e["lat"] is not None]
            return envelope(collection([point(e["lon"], e["lat"], id=e["id"], title=e["title"], severity=e["severity"], verification=e["verification"], category=e["category_label"], time=e["observed_at"], exposed=e["exposed"]) for e in rows]), source="atlas", freshness=Freshness.DELAYED)
        case "zones":
            feats = [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[w, s_], [e_, s_], [e_, n], [w, n], [w, s_]]]}, "properties": {"name": z["name"], "id": k}} for k, z in exposure.ZONES.items() for w, s_, e_, n in [z["bbox"]]]
            return envelope(collection(feats), source="reference", freshness=Freshness.REFERENCE, note="Rough boxes used to match events to documented exposures.")
        case "monitoring":
            if get_settings().public_read_only:
                return envelope(collection([]), source="reference", freshness=Freshness.REFERENCE)
            with session_scope() as db:
                areas = [satellite_monitor.to_dict(a) for a in db.scalars(select(MonitoringArea))]
            feats = [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[*a["polygon"], a["polygon"][0]]]}, "properties": {"name": a["name"], "tracker": a["tracker_label"]}} for a in areas]
            return envelope(collection(feats), source="reference", freshness=Freshness.REFERENCE)
        case "economy":
            parsed = econ.parse_world_bank((await econ.world_bank("gdp_growth", list(econ.WB_COUNTRIES), 3)).json())
            feats = []
            for iso, rows in parsed.items():
                cc = ISO3.get(iso, iso)
                if cc in CAPITALS:
                    feats.append(point(CAPITALS[cc][1], CAPITALS[cc][0], name=econ.WB_COUNTRIES[cc], value=round(rows[-1][1], 2), year=rows[-1][0]))
            return envelope(collection(feats), source="worldbank", freshness=Freshness.HISTORICAL)
    raise HTTPException(404, "Unknown layer")


@router.get("/weather/commodity/{commodity}")
async def weather_commodity(commodity: str):
    if commodity not in ref.WEATHER_REGIONS:
        raise HTTPException(404, "Unknown commodity")
    return envelope(await world.commodity_risk(commodity), source="openmeteo", freshness=Freshness.ESTIMATED, note="Rain and temperature anomaly against the prior 10 years. A proxy for crop stress, not a yield or price forecast.")


@router.get("/weather/commodities")
def weather_commodities():
    return envelope({c: {"ticker": ref.COMMODITY_TICKERS[c], "regions": [r[0] for r in rows]} for c, rows in ref.WEATHER_REGIONS.items()}, source="reference", freshness=Freshness.REFERENCE)


@router.get("/weather/forecast")
async def weather_forecast(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    res = await world.forecast(lat, lon)
    return envelope({k: v for k, v in res.items() if not k.startswith("_")}, source="openmeteo", freshness=Freshness.LIVE, fetched_at=res["_fetched"], stale=res["_stale"])


@router.get("/hazards/us-alerts")
async def us_alerts():
    return envelope(await world.nws_alerts(), source="nws", freshness=Freshness.DELAYED)


@router.get("/aviation/airports")
async def airports():
    return envelope(ref.AIRPORTS, source="reference", freshness=Freshness.REFERENCE)


@router.get("/aviation/airport/{code}")
async def airport(code: str):
    if code.upper() not in {a["code"] for a in ref.AIRPORTS}:
        raise HTTPException(404, "Unknown airport")
    res = await world.airport_activity(code.upper())
    history = [{"time": p, "value": v} for p, v in econ.history(f"aviation.{code.upper()}.nearby")][-96:]
    return envelope({**{k: v for k, v in res.items() if not k.startswith("_")}, "history": history}, source="opensky", freshness=Freshness.HISTORICAL if res["_stale"] else Freshness.LIVE, fetched_at=res["_fetched"], stale=res["_stale"],
                    note="Counts aircraft with ADS-B reports within about 55 km. A proxy for activity, not official movements. History grows as you sample.")


@router.get("/shipping/chokepoints")
async def shipping():
    rows = await world.chokepoints_ready()
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    loading = sum(1 for r in rows if r.get("loading"))
    stale = any(r.get("_stale") for r in rows)
    latest = max((r["latest_date"] for r in clean if r.get("latest_date")), default=None)
    return envelope(clean, source="portwatch", freshness=Freshness.HISTORICAL, as_of=latest, stale=stale,
                    note=(f"Still loading {loading} chokepoints from a slow service. " if loading else "") + "Daily AIS-derived estimates from IMF PortWatch, with a lag of several days. Live vessel tracking is not available for free at global scale.")


@router.get("/geo/events")
async def geo_events():
    rows, failed = await _events()
    tiers = {"official": 0, "automated": 1}
    rows.sort(key=lambda e: (tiers.get(e["tier"], 2), str(e.get("time"))), reverse=False)
    return envelope({"events": rows, "unavailable": failed}, source=["federalregister", "gdelt"], freshness=Freshness.DELAYED,
                    note="Official = published by a government source. Automated = machine-collected news, unverified.")


@router.get("/today")
async def today_view():
    return envelope(await briefing.today(), source=["yahoo", "rss", "portwatch", "openmeteo"], freshness=Freshness.DELAYED, note="Written from retrieved numbers by fixed rules, not by a language model.")


@router.get("/calendar")
async def calendar_view():
    from sqlalchemy import select as sql_select

    from atlas.db import Watchlist
    from atlas.db import session_scope as scope

    banks, failed = await calendar.central_banks()
    with scope() as db:
        symbols = [i.symbol for w in db.scalars(sql_select(Watchlist)) for i in w.items]
    tickers = [s for s in dict.fromkeys(symbols) if s in ref.LARGE_CAPS]
    rows = calendar.upcoming(banks + await calendar.earnings(tickers[:20]), date.today())
    return envelope({"events": rows, "unavailable": failed}, source=["calendars", "sec"], freshness=Freshness.REFERENCE, note="Central bank dates are official. Earnings dates are estimates: last results plus 91 days.")


@router.get("/news")
async def news_feed(tier: str | None = Query(None, pattern="^(official|media)$"), q: str | None = Query(None, max_length=60), limit: int = Query(60, ge=1, le=200)):
    refreshed = await news.refresh()
    rows = news.latest(limit, tier, q)
    return envelope(rows, source="rss", freshness=Freshness.DELAYED, note=f"Feeds unavailable: {', '.join(refreshed['failed'])}" if refreshed["failed"] else None)


# -- Crypto -----------------------------------------------------------------------------------------------

@router.get("/crypto/markets")
async def crypto_markets():
    res = await crypto.markets()
    return envelope(res["coins"], source="coingecko", freshness=Freshness.DELAYED, fetched_at=res["_fetched"], stale=res["_stale"], note="Data from CoinGecko.")


@router.get("/crypto/live")
async def crypto_live():
    res = await crypto.live_tickers()
    return envelope(res["rows"], source="binance", freshness=Freshness.HISTORICAL if res["_stale"] else Freshness.LIVE, fetched_at=res["_fetched"], stale=res["_stale"], note="Binance prices against USDT.")


@router.get("/crypto/networks")
async def crypto_networks():
    btc, eth = await asyncio.gather(crypto.bitcoin_network(), crypto.ethereum_network(), return_exceptions=True)
    return envelope({"bitcoin": None if isinstance(btc, Exception) else {k: v for k, v in btc.items() if not k.startswith("_")}, "ethereum": None if isinstance(eth, Exception) else eth}, source=["mempool", "ethrpc"], freshness=Freshness.DELAYED)


@router.get("/crypto/defi")
async def crypto_defi():
    res = await crypto.defi()
    return envelope({k: v for k, v in res.items() if not k.startswith("_")}, source="defillama", freshness=Freshness.DELAYED, fetched_at=res["_fetched"], stale=res["_stale"],
                    note="Exchange flows and token unlock schedules have no reliable free source and are not shown.")


# -- Alternative data -------------------------------------------------------------------------------------

def _sig(id, name, status, method, history, source, frequency, limitations, confidence, validation, assets):  # noqa: A002
    return {"id": id, "name": name, "status": status, "method": method, "history": history, "source": source, "frequency": frequency, "limitations": limitations, "confidence": confidence, "validation": validation, "assets": assets}


ALT_SIGNALS = [
    _sig("attention", "Wikipedia attention", "live", "Daily human pageviews. z-score of the 7-day mean of log views against the prior 90 days.", "About 400 days per query, stored as you use it", "Wikimedia", "Daily", "Spikes follow news as often as they lead it. English Wikipedia only.", "medium", "Per-ticker correlation with next-day absolute return, in and out of sample.", "Any company with an article"),
    _sig("google_trends", "Google Trends", "blocked", "None", "None", "None", "None", "Google offers no official free API, and scraping would breach its terms. Wikipedia attention is the lawful substitute.", "none", "None", "None"),
    _sig("hiring", "Corporate hiring trends", "blocked", "None", "None", "None", "None", "No lawful free global source was found. Job sites prohibit scraping.", "none", "None", "None"),
    _sig("job_ads", "Public job advertisements", "blocked", "None", "None", "None", "None", "Same as hiring trends.", "none", "None", "None"),
    _sig("product_prices", "Retail product prices", "blocked", "None", "None", "None", "None", "Needs per-retailer collection that respects each site's terms.", "none", "None", "None"),
    _sig("availability", "Online product availability", "blocked", "None", "None", "None", "None", "Same as retail prices.", "none", "None", "None"),
    _sig("permits", "Construction permits", "planned", "Official national series could be connected.", "None yet", "ABS and US Census publish these", "Monthly", "Not connected yet.", "none", "None", "Homebuilders, materials"),
    _sig("procurement", "Public procurement spending", "live", "Largest US federal contract awards to a named recipient in the past year.", "Past 12 months", "USAspending.gov", "Daily", "US federal only. Award ceiling is not revenue.", "medium", "None. Descriptive only.", "US contractors"),
    _sig("patents", "Patent applications", "blocked", "None", "None", "USPTO", "None", "The USPTO API needs a registered key, which ATLAS does not have.", "none", "None", "Technology companies"),
    _sig("crop_weather", "Agricultural weather risk", "live", "30-day rain and temperature anomaly against the prior 10 years, plus frost and heat days in growing season.", "About 11 years", "Open-Meteo", "Daily", "Point samples, not crop maps. Weights are approximate.", "medium", "No yield validation yet.", "Grains, coffee, cocoa"),
    _sig("mining", "Mining activity", "live", "Sentinel-2 bare-ground index change at mine sites, same season against a year earlier.", "Grows with each observation", "Sentinel-2", "About 5 days", "10 to 20 m pixels. Shows surface change, not output.", "low", "No ground-truth validation.", "Miners"),
    _sig("shipping", "Shipping disruptions", "live", "PortWatch transit estimates against a one-year baseline.", "400 days", "IMF PortWatch", "Daily, several days late", "AIS-derived estimates.", "medium", "Published by the IMF. Not validated by ATLAS.", "Tankers, carriers, energy"),
    _sig("airports", "Airport activity", "partial", "ADS-B aircraft near an airport, sampled when requested.", "Only what you have sampled", "OpenSky", "On demand", "Receiver coverage varies. Snapshots only.", "low", "None. History must accumulate.", "Airlines"),
    _sig("tourism", "Tourism indicators", "planned", "Official arrivals data could be connected.", "None yet", "ABS and national statistics", "Monthly", "Not connected yet.", "none", "None", "Airlines, hotels"),
    _sig("energy_output", "Energy production indicators", "partial", "EIA weekly crude stocks are connected. Production series are not yet.", "10 years of stocks", "EIA", "Weekly", "US only.", "high", "Official statistics.", "Oil, gas"),
    _sig("inventories", "Public commodity inventories", "live", "EIA commercial crude stocks and their weekly change.", "10 years", "EIA", "Weekly", "US crude only.", "high", "Official statistics.", "WTI crude, refiners"),
    _sig("renewables", "Renewable infrastructure", "partial", "Satellite tracker for large solar farm land clearing, in user-drawn areas.", "Grows with each observation", "Sentinel-2", "About 5 days", "Shows land change, not capacity.", "low", "No ground-truth validation.", "Solar developers"),
    _sig("websites", "Corporate website changes", "planned", "A robots-aware monitor for pages you choose.", "None yet", "None yet", "None", "Not built.", "none", "None", "Any company"),
    _sig("real_estate", "Public real estate indicators", "partial", "RBA and FRED housing series, where configured.", "Varies", "FRED", "Monthly", "Needs a free FRED key.", "medium", "Official statistics.", "Homebuilders, banks"),
    _sig("supply_chain", "Global supply-chain activity", "live", "Port calls and chokepoint transits against a year earlier.", "400 days", "IMF PortWatch", "Daily, several days late", "A proxy. Rising calls can mean demand or diversion.", "medium", "None by ATLAS.", "Carriers, retailers, exporters"),
]


@router.get("/alt/signals")
def alt_signals():
    return envelope(ALT_SIGNALS, source="atlas", freshness=Freshness.REFERENCE)




@router.get("/alt/inventories")
async def inventories():
    rows, fetched, stale = await econ.load(econ.BY_ID["us.crude_stocks"])
    recent = rows[-104:]
    changes = [{"date": d, "value": v, "change": v - recent[i - 1][1] if i else None} for i, (d, v) in enumerate(recent)]
    return envelope(changes, source="eia", freshness=Freshness.HISTORICAL, fetched_at=fetched, stale=stale, as_of=rows[-1][0] if rows else None)


@router.get("/alt/procurement")
async def procurement(company: str = Query(min_length=2, max_length=60)):
    res = await trade.procurement(company)
    return envelope(res["awards"], source="usaspending", freshness=Freshness.HISTORICAL, fetched_at=res["_fetched"], stale=res["_stale"], note="US federal awards only. Award amounts are ceilings, not revenue.")


@router.get("/alt/attention/{symbol}")
async def attention(symbol: Symbol, article: str = Query(min_length=1, max_length=80)):
    try:
        views = await world.pageviews(article)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    returns = None
    try:
        s = analytics.closes((await yahoo.chart(symbol.upper(), "2y", "1d"))["bars"]).pct_change(fill_method=None).dropna()
        returns = {d.strftime("%Y-%m-%d"): float(v) for d, v in s.items()}
    except SourceUnavailable:
        pass
    econ.remember(f"attention.{article}", views[-30:], "wikimedia")
    return envelope({"article": article, "stats": world.attention_stats(views, returns), "history": [{"date": d, "value": v} for d, v in views[-180:]]}, source=["wikimedia", "yahoo"], freshness=Freshness.HISTORICAL)


# -- Satellite --------------------------------------------------------------------------------------------

@router.get("/satellite/aois")
def satellite_aois():
    return envelope({"aois": ref.SATELLITE_AOIS, "indices": satellite.INDICES, "unsupported": satellite.UNSUPPORTED, "resolution_note": "Sentinel-2 bands are 10-20 m. Individual vehicles and tank roofs are not resolvable."},
                    source="reference", freshness=Freshness.REFERENCE)


@router.get("/satellite/scenes")
async def scenes(west: float, south: float, east: float, north: float, start: date | None = None, end: date | None = None, mission: str = Query("sentinel-2", pattern="^(sentinel-2|landsat)$"),
                 max_cloud: float = Query(30, ge=0, le=100), catalog: str = Query("earthsearch", pattern="^(earthsearch|cdse)$"), limit: int = Query(20, ge=1, le=100)):
    bbox = [west, south, east, north]
    end = end or date.today()
    start = start or end - timedelta(days=120)
    try:
        res = await satellite.search(bbox, start.isoformat(), end.isoformat(), mission, max_cloud, limit, catalog)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return envelope({"scenes": res["scenes"], "matched": res["matched"]}, source=catalog, freshness=Freshness.HISTORICAL, fetched_at=res["_fetched"], stale=res["_stale"],
                    note="Landsat pixels are requester-pays on AWS, so Landsat is catalogue-only here." if mission == "landsat" else None)


class ChangeRequest(BaseModel):
    bbox: list[float] = Field(min_length=4, max_length=4)
    before_id: str = Field(max_length=120)
    after_id: str = Field(max_length=120)
    index: str = Field("ndvi", pattern="^(ndvi|ndwi|bsi)$")
    threshold: float = Field(0.15, gt=0, le=1)
    aoi: str | None = Field(None, max_length=80)


async def _scene(scene_id: str) -> dict:
    from atlas.core.fetcher import get_fetcher

    got = await get_fetcher().get("earthsearch", f"https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/{scene_id}", ttl=7 * 86400)
    return satellite.scene_from_item(got.json(), "sentinel-2")


@router.post("/satellite/change")
async def change(req: ChangeRequest):
    try:
        satellite.bbox_guard(req.bbox)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    a, b = await asyncio.gather(_scene(req.before_id), _scene(req.after_id))
    before, after = await asyncio.gather(asyncio.to_thread(satellite.compute_index, a, req.bbox, req.index), asyncio.to_thread(satellite.compute_index, b, req.bbox, req.index))
    stats = satellite.change_stats(before, after, req.threshold)
    if req.aoi and stats["valid_fraction"] > 0:
        with session_scope() as db:
            for scene, arr in ((a, before), (b, after)):
                db.add(SatelliteMeasurement(aoi=req.aoi, index_name=req.index, scene_id=scene["id"], acquired_at=scene["acquired_at"], mean=float(satellite.np.nanmean(arr)), valid_fraction=float((~satellite.np.isnan(arr)).mean())))
    return envelope({"stats": stats, "before": {k: a[k] for k in ("id", "acquired_at", "cloud_cover", "resolution_m", "thumbnail")}, "after": {k: b[k] for k in ("id", "acquired_at", "cloud_cover", "resolution_m", "thumbnail")},
                     "overlay": satellite.change_png(before, after, req.threshold) if stats["valid_fraction"] > 0 else None, "bbox": req.bbox, "index": req.index, "index_meaning": satellite.INDICES[req.index]["meaning"]},
                    source="earthsearch", freshness=Freshness.ESTIMATED, as_of=b["acquired_at"], note="Blue pixels rose and orange pixels fell by more than the threshold. Season, sun angle and residual cloud can also cause change.")


@router.get("/satellite/history/{aoi}")
def satellite_history(aoi: str):
    with session_scope() as db:
        rows = db.scalars(select(SatelliteMeasurement).where(SatelliteMeasurement.aoi == aoi).order_by(SatelliteMeasurement.acquired_at)).all()
    return envelope([{"acquired_at": r.acquired_at, "index": r.index_name, "mean": r.mean, "valid_fraction": r.valid_fraction, "scene_id": r.scene_id} for r in rows], source="earthsearch", freshness=Freshness.HISTORICAL)
