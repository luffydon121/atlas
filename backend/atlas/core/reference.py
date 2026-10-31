"""Curated static reference data. Locations and groupings only, never observations."""

INDICES = {
    "^GSPC": "S&P 500", "^IXIC": "Nasdaq Comp", "^DJI": "Dow Jones", "^RUT": "Russell 2000",
    "^AXJO": "ASX 200", "^FTSE": "FTSE 100", "^GDAXI": "DAX", "^FCHI": "CAC 40",
    "^STOXX50E": "Euro Stoxx 50", "^N225": "Nikkei 225", "^HSI": "Hang Seng", "000001.SS": "Shanghai Comp",
    "^KS11": "KOSPI", "^NSEI": "Nifty 50",
}
RATES_VOL = {"^VIX": "VIX", "^IRX": "US 3M", "^FVX": "US 5Y", "^TNX": "US 10Y", "^TYX": "US 30Y"}
FX = {
    "AUDUSD=X": "AUD/USD", "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY",
    "USDCNY=X": "USD/CNY", "DX-Y.NYB": "US Dollar Index",
}
COMMODITIES = {
    "CL=F": "WTI Crude", "BZ=F": "Brent Crude", "NG=F": "Natural Gas", "GC=F": "Gold", "SI=F": "Silver",
    "HG=F": "Copper", "ZW=F": "Wheat", "ZC=F": "Corn", "ZS=F": "Soybeans", "KC=F": "Coffee", "CC=F": "Cocoa",
}
CRYPTO = {"BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana"}
SECTORS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care", "XLY": "Cons. Discretionary",
    "XLP": "Cons. Staples", "XLE": "Energy", "XLI": "Industrials", "XLB": "Materials",
    "XLRE": "Real Estate", "XLU": "Utilities", "XLC": "Communication",
}

# ticker: (CIK, name, sector). Fallback used when no SEC contact is configured.
LARGE_CAPS: dict[str, tuple[int, str, str]] = {
    "AAPL": (320193, "Apple", "Technology"), "MSFT": (789019, "Microsoft", "Technology"),
    "NVDA": (1045810, "NVIDIA", "Technology"), "AVGO": (1730168, "Broadcom", "Technology"),
    "ORCL": (1341439, "Oracle", "Technology"), "CRM": (1108524, "Salesforce", "Technology"),
    "AMD": (2488, "AMD", "Technology"), "INTC": (50863, "Intel", "Technology"),
    "CSCO": (858877, "Cisco", "Technology"), "IBM": (51143, "IBM", "Technology"),
    "GOOGL": (1652044, "Alphabet", "Communication"), "META": (1326801, "Meta", "Communication"),
    "NFLX": (1065280, "Netflix", "Communication"), "DIS": (1744489, "Disney", "Communication"),
    "T": (732717, "AT&T", "Communication"), "VZ": (732712, "Verizon", "Communication"),
    "AMZN": (1018724, "Amazon", "Cons. Discretionary"), "TSLA": (1318605, "Tesla", "Cons. Discretionary"),
    "HD": (354950, "Home Depot", "Cons. Discretionary"), "MCD": (63908, "McDonald's", "Cons. Discretionary"),
    "NKE": (320187, "Nike", "Cons. Discretionary"), "SBUX": (829224, "Starbucks", "Cons. Discretionary"),
    "WMT": (104169, "Walmart", "Cons. Staples"), "COST": (909832, "Costco", "Cons. Staples"),
    "PG": (80424, "Procter & Gamble", "Cons. Staples"), "KO": (21344, "Coca-Cola", "Cons. Staples"),
    "PEP": (77476, "PepsiCo", "Cons. Staples"), "JPM": (19617, "JPMorgan Chase", "Financials"),
    "BAC": (70858, "Bank of America", "Financials"), "GS": (886982, "Goldman Sachs", "Financials"),
    "V": (1403161, "Visa", "Financials"), "MA": (1141391, "Mastercard", "Financials"),
    "BRK-B": (1067983, "Berkshire Hathaway", "Financials"), "UNH": (731766, "UnitedHealth", "Health Care"),
    "JNJ": (200406, "Johnson & Johnson", "Health Care"), "LLY": (59478, "Eli Lilly", "Health Care"),
    "PFE": (78003, "Pfizer", "Health Care"), "MRK": (310158, "Merck", "Health Care"),
    "ABBV": (1551152, "AbbVie", "Health Care"), "XOM": (34088, "ExxonMobil", "Energy"),
    "CVX": (93410, "Chevron", "Energy"), "CAT": (18230, "Caterpillar", "Industrials"),
    "BA": (12927, "Boeing", "Industrials"),
}

CHOKEPOINTS = [
    {"id": "chokepoint1", "name": "Suez Canal", "lat": 30.6, "lon": 32.3},
    {"id": "chokepoint2", "name": "Panama Canal", "lat": 9.1, "lon": -79.7},
    {"id": "chokepoint3", "name": "Bosporus Strait", "lat": 41.1, "lon": 29.05},
    {"id": "chokepoint4", "name": "Bab el-Mandeb Strait", "lat": 12.6, "lon": 43.3},
    {"id": "chokepoint5", "name": "Malacca Strait", "lat": 2.5, "lon": 101.4},
    {"id": "chokepoint6", "name": "Strait of Hormuz", "lat": 26.55, "lon": 56.25},
    {"id": "chokepoint7", "name": "Cape of Good Hope", "lat": -34.4, "lon": 18.5},
    {"id": "chokepoint8", "name": "Gibraltar Strait", "lat": 35.95, "lon": -5.6},
    {"id": "chokepoint11", "name": "Taiwan Strait", "lat": 24.5, "lon": 119.5},
]

PORTS = [
    ("Shanghai", 31.23, 121.8), ("Singapore", 1.26, 103.84), ("Ningbo-Zhoushan", 29.93, 121.85),
    ("Shenzhen", 22.5, 113.9), ("Busan", 35.1, 129.05), ("Rotterdam", 51.95, 4.05), ("Antwerp", 51.3, 4.3),
    ("Hamburg", 53.53, 9.95), ("Los Angeles", 33.73, -118.26), ("Long Beach", 33.75, -118.2),
    ("New York-New Jersey", 40.67, -74.05), ("Houston", 29.73, -95.0), ("Santos", -23.97, -46.3),
    ("Jebel Ali", 25.01, 55.06), ("Port Hedland", -20.31, 118.58), ("Melbourne", -37.83, 144.92),
    ("Sydney (Botany)", -33.97, 151.21), ("Durban", -29.87, 31.03), ("Mumbai (JNPT)", 18.95, 72.95),
    ("Yokohama", 35.45, 139.67),
]

# Port identifiers from the PortWatch ports database. Name lookups time out on the daily table.
PORT_DASHBOARD = [
    {"portid": "port1188", "portname": "Shanghai", "country": "China"}, {"portid": "port1201", "portname": "Singapore", "country": "Singapore"}, {"portid": "port824", "portname": "Ningbo", "country": "China"},
    {"portid": "port1065", "portname": "Busan", "country": "South Korea"}, {"portid": "port744", "portname": "Jebel Ali", "country": "United Arab Emirates"}, {"portid": "port1114", "portname": "Rotterdam", "country": "Netherlands"},
    {"portid": "port57", "portname": "Antwerp", "country": "Belgium"}, {"portid": "port446", "portname": "Hamburg", "country": "Germany"}, {"portid": "port664", "portname": "Los Angeles-Long Beach", "country": "United States"},
    {"portid": "port1160", "portname": "Santos", "country": "Brazil"}, {"portid": "port955", "portname": "Port Hedland", "country": "Australia"}, {"portid": "port729", "portname": "Melbourne", "country": "Australia"},
]

# Illustrative great-circle-style waypoints, not actual vessel tracks.
TRADE_ROUTES = [
    {"name": "Asia - Europe via Suez",
     "path": [[121.8, 31.2], [103.8, 1.3], [80, 6], [55, 13], [43.3, 12.6], [38, 21], [32.3, 30.6], [15, 36], [-5.5, 36], [-9, 43], [4, 52]]},
    {"name": "Asia - Europe via Cape",
     "path": [[103.8, 1.3], [80, -10], [40, -32], [18.5, -35], [0, -10], [-15, 15], [-9, 43], [4, 52]]},
    {"name": "Trans-Pacific", "path": [[121.8, 31.2], [145, 38], [180, 45]]},
    {"name": "Trans-Pacific (east)", "path": [[-180, 45], [-150, 42], [-118.3, 33.7]]},
    {"name": "Persian Gulf - Asia crude",
     "path": [[50, 27], [56.2, 26.5], [60, 22], [80, 6], [95, 6], [103.8, 1.3], [115, 12], [121.8, 31.2]]},
    {"name": "Australia - China iron ore", "path": [[118.6, -20.3], [116, -8.5], [120, 5], [122, 25], [121.8, 31.2]]},
    {"name": "US Gulf - Europe LNG", "path": [[-93.9, 29.7], [-80, 25], [-40, 40], [-9, 45], [4, 52]]},
]

AIRPORTS = [
    {"code": "SYD", "name": "Sydney", "lat": -33.946, "lon": 151.177},
    {"code": "MEL", "name": "Melbourne", "lat": -37.673, "lon": 144.843},
    {"code": "SIN", "name": "Singapore Changi", "lat": 1.359, "lon": 103.989},
    {"code": "HKG", "name": "Hong Kong", "lat": 22.308, "lon": 113.918},
    {"code": "NRT", "name": "Tokyo Narita", "lat": 35.772, "lon": 140.393},
    {"code": "DXB", "name": "Dubai", "lat": 25.253, "lon": 55.365},
    {"code": "LHR", "name": "London Heathrow", "lat": 51.47, "lon": -0.454},
    {"code": "FRA", "name": "Frankfurt", "lat": 50.033, "lon": 8.57},
    {"code": "JFK", "name": "New York JFK", "lat": 40.64, "lon": -73.779},
    {"code": "ATL", "name": "Atlanta", "lat": 33.637, "lon": -84.428},
    {"code": "LAX", "name": "Los Angeles", "lat": 33.943, "lon": -118.408},
    {"code": "ORD", "name": "Chicago O'Hare", "lat": 41.978, "lon": -87.905},
]

ENERGY_SITES = [
    {"name": "Ras Tanura (terminal)", "lat": 26.64, "lon": 50.16, "kind": "oil"},
    {"name": "Cushing, Oklahoma (storage hub)", "lat": 35.98, "lon": -96.76, "kind": "oil"},
    {"name": "Port Arthur (refining)", "lat": 29.88, "lon": -93.94, "kind": "oil"},
    {"name": "Baytown (refining)", "lat": 29.75, "lon": -95.0, "kind": "oil"},
    {"name": "Garyville (refining)", "lat": 30.06, "lon": -90.6, "kind": "oil"},
    {"name": "Louisiana Offshore Oil Port", "lat": 28.88, "lon": -90.03, "kind": "oil"},
    {"name": "Rotterdam (refining hub)", "lat": 51.9, "lon": 4.2, "kind": "oil"},
    {"name": "Ras Laffan (LNG)", "lat": 25.9, "lon": 51.55, "kind": "lng"},
    {"name": "Sabine Pass (LNG)", "lat": 29.74, "lon": -93.87, "kind": "lng"},
    {"name": "Gorgon (LNG)", "lat": -20.78, "lon": 115.44, "kind": "lng"},
    {"name": "North West Shelf (LNG)", "lat": -20.6, "lon": 116.78, "kind": "lng"},
    {"name": "Three Gorges (hydro)", "lat": 30.82, "lon": 111.0, "kind": "power"},
    {"name": "Hornsea (offshore wind)", "lat": 53.9, "lon": 1.9, "kind": "power"},
]

INDUSTRIAL_SITES = [
    {"name": "Mount Whaleback iron ore mine", "lat": -23.36, "lon": 119.67, "kind": "mine"},
    {"name": "Escondida copper mine", "lat": -24.27, "lon": -69.07, "kind": "mine"},
    {"name": "Olympic Dam", "lat": -30.44, "lon": 136.88, "kind": "mine"},
    {"name": "Giga Texas", "lat": 30.22, "lon": -97.62, "kind": "factory"},
    {"name": "TSMC Hsinchu", "lat": 24.78, "lon": 121.01, "kind": "factory"},
    {"name": "Baosteel Shanghai", "lat": 31.4, "lon": 121.45, "kind": "factory"},
]

# Fixed sites for each tracker. bbox is west, south, east, north.
SATELLITE_AOIS = [
    {"id": "whaleback", "name": "Mount Whaleback mine, Pilbara", "tracker": "mining", "index": "bsi",
     "bbox": [119.60, -23.40, 119.74, -23.32], "ticker": "BHP.AX"},
    {"id": "escondida", "name": "Escondida mine, Chile", "tracker": "mining", "index": "bsi",
     "bbox": [-69.14, -24.31, -69.02, -24.21], "ticker": "BHP"},
    {"id": "mato-grosso", "name": "Soy belt, Mato Grosso", "tracker": "agriculture", "index": "ndvi",
     "bbox": [-55.75, -13.05, -55.60, -12.92], "ticker": "ZS=F"},
    {"id": "iowa-corn", "name": "Corn belt, Iowa", "tracker": "agriculture", "index": "ndvi",
     "bbox": [-93.70, 41.95, -93.55, 42.08], "ticker": "ZC=F"},
    {"id": "minas-coffee", "name": "Coffee region, Minas Gerais", "tracker": "agriculture", "index": "ndvi",
     "bbox": [-45.50, -21.35, -45.38, -21.25], "ticker": "KC=F"},
    {"id": "lake-mead", "name": "Lake Mead reservoir", "tracker": "environment", "index": "ndwi",
     "bbox": [-114.80, 36.00, -114.64, 36.14], "ticker": None},
    {"id": "darling-basin", "name": "Menindee Lakes, NSW", "tracker": "environment", "index": "ndwi",
     "bbox": [142.30, -32.42, 142.46, -32.28], "ticker": None},
    {"id": "giga-texas", "name": "Giga Texas site", "tracker": "construction", "index": "bsi",
     "bbox": [-97.64, 30.20, -97.60, 30.24], "ticker": "TSLA"},
    {"id": "neom-line", "name": "NEOM, Saudi Arabia", "tracker": "construction", "index": "bsi",
     "bbox": [35.25, 27.95, 35.40, 28.08], "ticker": None},
    {"id": "hsinchu", "name": "Hsinchu Science Park", "tracker": "industrial", "index": "ndvi",
     "bbox": [120.98, 24.76, 121.04, 24.80], "ticker": "TSM"},
]

WEATHER_REGIONS = {
    "coffee": [("Minas Gerais, Brazil", -21.2, -45.0, 0.35), ("Dak Lak, Vietnam", 12.7, 108.2, 0.2),
               ("Huila, Colombia", 2.5, -75.5, 0.1)],
    "cocoa": [("Soubre, Cote d'Ivoire", 5.8, -6.6, 0.4), ("Ashanti, Ghana", 6.7, -1.6, 0.2)],
    "wheat": [("Kansas, USA", 38.5, -98.5, 0.2), ("Punjab, India", 30.9, 75.8, 0.25),
              ("Rostov, Russia", 47.2, 40.0, 0.2), ("Wheatbelt, WA", -31.6, 117.6, 0.1)],
    "corn": [("Iowa, USA", 42.0, -93.5, 0.35), ("Illinois, USA", 40.0, -89.2, 0.25),
             ("Heilongjiang, China", 46.8, 126.9, 0.15)],
    "soybeans": [("Mato Grosso, Brazil", -13.0, -55.7, 0.35), ("Iowa, USA", 42.0, -93.5, 0.2),
                 ("Cordoba, Argentina", -32.5, -63.0, 0.15)],
    "natural_gas": [("Chicago, USA", 41.9, -87.6, 0.35), ("New York, USA", 40.7, -74.0, 0.35),
                    ("Berlin, Germany", 52.5, 13.4, 0.3)],
}
# Main growing months for annual crops, from USDA crop calendars. Perennials and gas demand have none.
GROWING_MONTHS = {
    ("wheat", "Kansas, USA"): range(3, 7), ("wheat", "Punjab, India"): (11, 12, 1, 2, 3, 4), ("wheat", "Rostov, Russia"): range(4, 8), ("wheat", "Wheatbelt, WA"): range(5, 12),
    ("corn", "Iowa, USA"): range(5, 11), ("corn", "Illinois, USA"): range(4, 11), ("corn", "Heilongjiang, China"): range(5, 10),
    ("soybeans", "Mato Grosso, Brazil"): (10, 11, 12, 1, 2, 3), ("soybeans", "Iowa, USA"): range(5, 11), ("soybeans", "Cordoba, Argentina"): (11, 12, 1, 2, 3, 4),
}
COMMODITY_TICKERS = {"coffee": "KC=F", "cocoa": "CC=F", "wheat": "ZW=F", "corn": "ZC=F",
                     "soybeans": "ZS=F", "natural_gas": "NG=F"}
