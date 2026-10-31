"""The source registry: what each provider is, what it allows and how ATLAS treats it."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Source:
    id: str
    provider: str
    domain: str
    licence: str
    coverage: str
    refresh: str
    limitations: str
    freshness: str
    min_interval_s: float = 0.5
    url: str = ""
    quality: str = "official"
    requires: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


_SOURCES = [
    Source("yahoo", "Yahoo Finance chart endpoint", "markets",
           "Unofficial public endpoint. Personal, non-commercial use; do not redistribute.",
           "Global equities, ETFs, indices, FX, futures, crypto", "3 min cache",
           "Undocumented and may change without notice. Quotes are typically delayed 15+ minutes. "
           "Excessive requests can be blocked.",
           "delayed", 0.2, "https://finance.yahoo.com", "community"),
    Source("sec", "SEC EDGAR", "companies", "US Government public data",
           "US-listed filers: XBRL financials, filings, Forms 3/4/5", "24 h cache",
           "10 requests/second maximum. Non-US issuers filing no XBRL are not covered. "
           "The full ticker list needs ATLAS_SEC_CONTACT.",
           "historical", 0.15, "https://www.sec.gov/edgar"),
    Source("bls", "US Bureau of Labor Statistics", "economy", "US Government public data",
           "US CPI, employment, wages", "12 h cache",
           "25 queries a day and 10 years without a free key.", "historical", 1.0, "https://www.bls.gov/developers/"),
    Source("treasury", "US Treasury", "economy", "US Government public data",
           "Daily par yield curve", "6 h cache", "Business days only, published after the close.",
           "historical", 1.0, "https://home.treasury.gov"),
    Source("worldbank", "World Bank Open Data", "economy", "CC BY 4.0",
           "200+ economies, annual", "24 h cache", "Annual and often 1-2 years behind.",
           "historical", 0.3, "https://data.worldbank.org"),
    Source("rba", "Reserve Bank of Australia", "economy", "CC BY 4.0 (check table notes)",
           "Australian cash rate, inflation, yields, labour tables", "12 h cache",
           "CSV table layouts can change.", "historical", 1.0, "https://www.rba.gov.au/statistics/tables/"),
    Source("ecb", "European Central Bank", "economy", "ECB open data, attribution required",
           "Euro-area rates, inflation, FX", "12 h cache", "Euro-area focus.",
           "historical", 0.5, "https://data.ecb.europa.eu"),
    Source("eurostat", "Eurostat", "economy", "CC BY 4.0",
           "EU and euro-area statistics, including HICP on the ECOICOP v2 basis", "12 h cache",
           "Replaced the ECB HICP series, which ends in December 2025.", "historical", 0.5, "https://ec.europa.eu/eurostat"),
    Source("abs", "Australian Bureau of Statistics", "economy", "CC BY 4.0",
           "Australian labour force and other SDMX datasets", "12 h cache", "Dataflow versions change over time.", "historical", 1.0, "https://www.abs.gov.au"),
    Source("oecd", "OECD Data Explorer", "economy", "CC BY 4.0", "Composite leading indicators", "24 h cache", "Rate limited. Latest values are revised.", "historical", 2.0, "https://data-explorer.oecd.org"),
    Source("eia", "US Energy Information Administration", "economy", "US Government public data", "Weekly US crude oil stocks", "12 h cache", "US inventories only, published weekly.", "historical", 1.0, "https://www.eia.gov"),
    Source("calendars", "Federal Reserve and RBA calendars", "economy", "Public web pages, used for dates only", "FOMC and RBA decision dates", "24 h cache", "Page layouts can change, which would empty the calendar.", "reference", 1.0, "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"),
    Source("bis", "Bank for International Settlements", "economy", "BIS terms: free reuse with attribution", "Central bank policy rates", "24 h cache", "Daily series, published with a short lag.", "historical", 1.0, "https://data.bis.org"),
    Source("usaspending", "USAspending.gov", "altdata", "US Government public data", "US federal contract awards", "24 h cache", "US federal awards only. Award size is not revenue.", "historical", 1.0, "https://www.usaspending.gov"),
    Source("fred", "FRED (St. Louis Fed)", "economy", "Free key; each series keeps its publisher's terms",
           "US and global macro series", "12 h cache", "Off until ATLAS_FRED_API_KEY is set.",
           "historical", 0.6, "https://fred.stlouisfed.org", requires="ATLAS_FRED_API_KEY"),
    Source("frankfurter", "Frankfurter (ECB reference rates)", "markets", "Open source; ECB data",
           "30+ currencies, daily", "6 h cache", "Daily reference rates, not tradable quotes.",
           "historical", 0.3, "https://frankfurter.dev"),
    Source("rss", "Publisher RSS feeds", "news", "Headline and link only; content stays with the publisher",
           "Central banks, regulators, business media", "15 min cache", "Headlines only, no full text.",
           "live", 0.5, quality="mixed"),
    Source("gdelt", "GDELT DOC 2.0", "geopolitics", "Free with citation",
           "Global news monitoring", "30 min cache",
           "One request per 5 seconds. Automated classification, not verified fact.",
           "live", 6.0, "https://www.gdeltproject.org", "automated"),
    Source("federalregister", "Federal Register", "geopolitics", "US Government public data",
           "OFAC sanctions and BIS export-control documents", "6 h cache",
           "US actions only.", "live", 0.5, "https://www.federalregister.gov/developers"),
    Source("openmeteo", "Open-Meteo", "weather", "CC BY 4.0, free for non-commercial use",
           "Global forecast and ERA5-based archive", "1-24 h cache",
           "10,000 calls/day. Archive lags by several days.", "live", 0.25, "https://open-meteo.com"),
    Source("openmeteo_archive", "Open-Meteo ERA5 archive", "weather", "CC BY 4.0, free for non-commercial use",
           "Daily reanalysis back to 1940", "24 h cache",
           "Long ranges count as many calls, so requests are spaced 7 seconds apart. Lags by several days.",
           "historical", 7.0, "https://open-meteo.com"),
    Source("usgs", "USGS Earthquake Hazards", "hazards", "US Government public data",
           "Global M4.5+ earthquakes", "10 min cache", "Past week only in this feed.",
           "live", 1.0, "https://earthquake.usgs.gov"),
    Source("eonet", "NASA EONET", "hazards", "NASA open data",
           "Wildfires, storms, volcanoes, floods", "30 min cache", "Curated, with some lag.",
           "live", 1.0, "https://eonet.gsfc.nasa.gov"),
    Source("nws", "US National Weather Service", "hazards", "US Government public data",
           "US severe weather alerts", "10 min cache", "US only.", "live", 1.0, "https://www.weather.gov"),
    Source("nhc", "NOAA National Hurricane Center", "hazards", "US Government public data",
           "Active Atlantic and East Pacific tropical cyclones", "30 min cache",
           "Empty outside active storms.", "live", 1.0, "https://www.nhc.noaa.gov"),
    Source("opensky", "OpenSky Network", "aviation", "Free for research and non-commercial use",
           "ADS-B aircraft positions", "1 min cache",
           "400 anonymous credits a day, no history without an account, receiver coverage varies.",
           "live", 11.0, "https://opensky-network.org", "community"),
    Source("portwatch", "IMF PortWatch", "shipping", "IMF open data, attribution required",
           "Daily transits at global chokepoints, derived from AIS", "12 h cache",
           "Lags by several days. Estimates, not individual vessel tracks. Slow on the first query of a chokepoint.",
           "historical", 1.0, "https://portwatch.imf.org"),
    Source("earthsearch", "Earth Search (Element 84)", "satellite", "Sentinel data: Copernicus open licence",
           "Sentinel-2 L2A and Landsat catalogue; Sentinel-2 COGs on AWS", "1 h cache",
           "10 m resolution at best: cannot detect individual vehicles. Landsat pixels are requester-pays.",
           "historical", 0.5, "https://earth-search.aws.element84.com/v1"),
    Source("cdse", "Copernicus Data Space Ecosystem", "satellite", "Copernicus open licence",
           "Sentinel catalogue (metadata)", "1 h cache",
           "Pixel downloads need a free account and are not implemented.",
           "historical", 0.5, "https://dataspace.copernicus.eu"),
    Source("gibs", "NASA GIBS", "satellite", "NASA open data",
           "Daily global MODIS/VIIRS map tiles", "Browser tile cache",
           "250 m or coarser. Loaded directly by the map in your browser.",
           "historical", 0.0, "https://nasa-gibs.github.io/gibs-api-docs/"),
    Source("binance", "Binance public market data", "crypto", "Free public endpoint, market data only", "Major pairs against USDT", "5 s cache",
           "USDT pairs, not USD. Prices are from one exchange.", "live", 0.5, "https://data-api.binance.vision"),
    Source("feargreed", "Alternative.me Fear and Greed", "crypto", "Free with attribution", "Daily crypto sentiment index", "1 h cache", "A composite opinion measure, updated daily.", "historical", 1.0, "https://alternative.me/crypto/fear-and-greed-index/", "community"),
    Source("coingecko", "CoinGecko public API", "crypto", "Free tier, attribution required",
           "Crypto prices, market cap, volume", "3 min cache", "Shared low rate limit.",
           "delayed", 2.5, "https://www.coingecko.com", "community"),
    Source("mempool", "mempool.space", "crypto", "Public API, AGPL open-source project",
           "Bitcoin network statistics", "5 min cache", "Fair-use limits.", "live", 1.0,
           "https://mempool.space", "community"),
    Source("defillama", "DefiLlama", "crypto", "Free public API",
           "DeFi TVL and stablecoin supply", "1 h cache", "Self-reported adapters; methodology varies by protocol.",
           "delayed", 1.0, "https://defillama.com", "community"),
    Source("ethrpc", "PublicNode Ethereum RPC", "crypto", "Free public endpoint",
           "Ethereum chain head", "1 min cache", "Shared endpoint with no uptime guarantee.",
           "live", 1.0, "https://ethereum-rpc.publicnode.com", "community"),
    Source("wikimedia", "Wikimedia Pageviews", "altdata", "CC0",
           "Daily article views", "12 h cache", "A proxy for public attention, not Google Trends.",
           "historical", 0.5, "https://wikimedia.org/api/rest_v1/", "official"),
    Source("ollama", "Ollama (local)", "ai", "MIT; each model has its own licence",
           "Local language models on this Mac", "On demand", "Optional. ATLAS answers from evidence without it.",
           "live", 0.0, "https://ollama.com", "local"),
]

REGISTRY: dict[str, Source] = {s.id: s for s in _SOURCES}

# Plain summaries for this app's use. The provider's own terms are what apply.
_PERSONAL = "Personal use. Do not republish."
_PUBLIC = "Public data. Attribute the source."
_NONCOMMERCIAL = "Non-commercial use with attribution."
REDISTRIBUTION = {
    "yahoo": _PERSONAL, "coingecko": "Attribution required. Limits apply to the free plan.", "binance": "Display of market data; check Binance terms before republishing.",
    "openmeteo": _NONCOMMERCIAL, "openmeteo_archive": _NONCOMMERCIAL, "opensky": "Non-commercial research use. Ask OpenSky before public display.", "rss": "Headlines and links only.",
    "gdelt": "Free with citation.", "calendars": "Dates only.", "defillama": "Free with attribution.", "feargreed": "Attribution required.", "ollama": "Runs locally.",
}
_REFRESH = {"yahoo": 180, "binance": 30, "rss": 900, "gdelt": 1800, "openmeteo": 3600, "openmeteo_archive": 86400, "usgs": 600, "eonet": 1800, "nws": 600, "nhc": 1800, "opensky": 300, "portwatch": 43200, "coingecko": 180, "mempool": 300,
            "ethrpc": 300, "defillama": 3600, "sec": 86400, "bls": 43200, "treasury": 21600, "worldbank": 86400, "rba": 43200, "ecb": 43200, "eurostat": 43200, "abs": 43200, "oecd": 86400, "eia": 43200, "federalregister": 21600, "calendars": 86400,
            "frankfurter": 21600, "bis": 86400, "usaspending": 86400, "wikimedia": 43200, "feargreed": 3600, "earthsearch": 3600, "cdse": 3600}
_TIERS = ["low", "medium", "high"]
_BASE = {"official": 2, "local": 2, "community": 1, "mixed": 1, "automated": 0}


def redistribution(source_id: str) -> str:
    return REDISTRIBUTION.get(source_id, _PUBLIC)


def expected_seconds(source_id: str) -> int | None:
    return _REFRESH.get(source_id)


def reliability(spec: Source, success_rate: float | None) -> str:
    """Tier from the kind of source, lowered one step if under 90% of recent fetches succeed."""
    level = _BASE.get(spec.quality, 1)
    if success_rate is not None and success_rate < 0.9:
        level = max(level - 1, 0)
    return _TIERS[level]
