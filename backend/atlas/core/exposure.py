"""Documented links between places, events, commodities and companies.

These are hypotheses about exposure, written by hand from public knowledge of where things are.
They say what could be affected and why. They never say what will happen.
"""

from dataclasses import asdict, dataclass, field

# west, south, east, north
ZONES: dict[str, dict] = {
    "gulf_of_mexico": {"name": "US Gulf Coast and Gulf of Mexico", "bbox": (-98.5, 18, -80, 31.5)},
    "persian_gulf": {"name": "Persian Gulf and Strait of Hormuz", "bbox": (47, 23, 60, 31)},
    "red_sea": {"name": "Red Sea and Suez", "bbox": (32, 11, 45, 32)},
    "panama": {"name": "Panama Canal region", "bbox": (-84, 7, -76, 11)},
    "taiwan": {"name": "Taiwan", "bbox": (118.5, 21.5, 123, 26)},
    "japan": {"name": "Japan", "bbox": (128, 30, 146, 46)},
    "pilbara": {"name": "Pilbara, Western Australia", "bbox": (114, -24.5, 122, -19.5)},
    "atacama": {"name": "Northern Chile copper belt", "bbox": (-71.5, -27, -67.5, -18)},
    "black_sea": {"name": "Black Sea grain region", "bbox": (28, 41, 42, 49)},
    "north_sea": {"name": "North Sea energy region", "bbox": (-4, 53, 9, 62)},
}


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    categories: tuple[str, ...]
    commodities: tuple[tuple[str, str], ...] = ()
    industries: tuple[str, ...] = ()
    companies: tuple[tuple[str, str], ...] = ()
    mechanism: str = ""
    uncertainty: str = ""
    zones: tuple[str, ...] = ()
    chokepoints: tuple[str, ...] = ()
    crop: str | None = None
    keywords: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    basis: str = ""
    benchmark: str = "SPY"
    tags: tuple[str, ...] = field(default=())

    def to_dict(self) -> dict:
        return asdict(self)


WEATHER = ("extreme_weather", "natural_disaster")
RULES = [
    Rule("gulf_energy", "US Gulf energy", WEATHER + ("energy",), (("CL=F", "WTI crude"), ("NG=F", "Natural gas"), ("RB=F", "Gasoline")), ("Offshore oil and gas", "Refining", "LNG export"),
         (("XOM", "Refining and Gulf production"), ("CVX", "Gulf production"), ("VLO", "Gulf Coast refining"), ("MPC", "Gulf Coast refining"), ("LNG", "LNG export terminals"), ("SLB", "Offshore services")),
         "Storms can shut offshore platforms, refineries and export terminals. Gasoline and refining margins have often reacted differently from crude, because closed refineries also reduce crude demand.",
         "The effect depends on the track, intensity and how long facilities stay closed. Forecast tracks change. Prices may already reflect forecasts.",
         zones=("gulf_of_mexico",), basis="The EIA describes the Gulf Coast as the largest US refining and offshore production region."),
    Rule("hormuz", "Strait of Hormuz", ("shipping", "geopolitical", "energy"), (("BZ=F", "Brent crude"), ("CL=F", "WTI crude"), ("NG=F", "Natural gas")), ("Crude shipping", "LNG shipping", "Airlines"),
         (("FRO", "Crude tankers"), ("STNG", "Product tankers"), ("XOM", "Global oil producer"), ("CVX", "Global oil producer"), ("DAL", "Jet fuel buyer")),
         "A large share of seaborne oil and Gulf LNG passes this strait. Fewer transits can tighten supply and raise tanker rates and insurance costs.",
         "Transit counts lag and may reflect routing, reporting or sanctions, not only physical disruption. Spare pipelines and strategic stocks can soften the effect.",
         zones=("persian_gulf",), chokepoints=("chokepoint6",), basis="IEA and EIA list Hormuz as the most important oil transit chokepoint."),
    Rule("red_sea", "Red Sea and Suez", ("shipping", "geopolitical"), (("BZ=F", "Brent crude"),), ("Container shipping", "Crude shipping", "Retail importers"),
         (("ZIM", "Container shipping"), ("MAERSK-B.CO", "Container shipping"), ("FRO", "Crude tankers")),
         "Diversions around the Cape lengthen voyages, which absorbs ship capacity. That has tended to lift freight rates, which helps carriers and costs importers.",
         "Carrier profits depend on contract rates and fleet supply. Fewer transits can be a reroute, not lost trade.",
         zones=("red_sea",), chokepoints=("chokepoint1", "chokepoint4"), basis="IMF PortWatch and UNCTAD report on Suez and Red Sea diversions."),
    Rule("panama", "Panama Canal", ("shipping", "extreme_weather"), (("ZC=F", "Corn"), ("ZS=F", "Soybeans")), ("Grain exports", "Container shipping", "LPG shipping"), (("ADM", "US grain exporter"), ("BG", "US grain exporter"), ("ZIM", "Container shipping")),
         "Low water can limit daily transits, which matters for US Gulf grain and energy cargoes bound for Asia.",
         "Cargoes can reroute at a cost, so the effect may show in freight rather than the commodity price.",
         zones=("panama",), chokepoints=("chokepoint2",), basis="The Panama Canal Authority publishes draft and transit limits."),
    Rule("malacca_taiwan", "Taiwan and Malacca", ("shipping", "geopolitical", "natural_disaster", "regulatory"), (), ("Semiconductors", "Electronics", "Asian energy imports"), (("TSM", "Leading chip foundry"), ("NVDA", "Depends on Taiwan foundry"), ("AMD", "Depends on Taiwan foundry"), ("ASML", "Equipment supplier"), ("EWT", "Taiwan equity ETF")),
         "Taiwan hosts much of the world's leading-edge chip manufacturing, and these straits carry a large share of Asian trade.",
         "Fabs are built to resist earthquakes and often recover quickly. Geopolitical headlines may not change physical flows.",
         zones=("taiwan",), chokepoints=("chokepoint5", "chokepoint11"), basis="TSMC filings and SIA reports describe this concentration."),
    Rule("black_sea", "Black Sea grain", ("geopolitical", "shipping", "agriculture"), (("ZW=F", "Wheat"), ("ZC=F", "Corn")), ("Grain exports", "Fertiliser"), (("ADM", "Grain trader"), ("BG", "Grain trader"), ("CF", "Fertiliser"), ("NTR", "Fertiliser")),
         "Russia and Ukraine are major wheat, corn and fertiliser exporters, so disruption here can reach global grain prices.",
         "Stocks and other exporters can offset losses, and prices often move before physical supply does.",
         zones=("black_sea",), chokepoints=("chokepoint3",), keywords=("russia", "ukraine"), basis="USDA WASDE reports show their share of world exports."),
    Rule("pilbara", "Pilbara iron ore", WEATHER + ("industrial",), (), ("Iron ore mining", "Bulk shipping", "Steelmaking"), (("BHP.AX", "Pilbara iron ore"), ("RIO.AX", "Pilbara iron ore"), ("FMG.AX", "Pilbara iron ore")),
         "Cyclones can close Port Hedland and Dampier and pause rail and mine operations, which can delay shipments.",
         "Producers plan for cyclone season, and lost tonnes are often recovered within the year.",
         zones=("pilbara",), basis="Company quarterly reports describe cyclone-related shipment effects."),
    Rule("chile_copper", "Chilean copper", WEATHER + ("industrial",), (("HG=F", "Copper"),), ("Copper mining",), (("FCX", "Copper producer"), ("SCCO", "Copper producer"), ("BHP", "Escondida operator")),
         "Northern Chile is the world's largest copper-producing region, so outages here can tighten concentrate supply.",
         "Earthquakes in this region are common and most mines restart quickly. Water and labour often matter more.",
         zones=("atacama",), basis="USGS Mineral Commodity Summaries rank Chile as the top copper producer."),
    Rule("north_sea", "North Sea energy", WEATHER + ("energy",), (("BZ=F", "Brent crude"), ("NG=F", "Natural gas")), ("Offshore oil and gas", "European power"), (("EQNR", "North Sea producer"), ("SHEL", "North Sea producer")),
         "Storms or outages can reduce North Sea supply to Europe.", "Most disruptions are short and local.", zones=("north_sea",), basis="UK NSTA and Norwegian Offshore Directorate publish production data."),
    Rule("japan", "Japan", ("natural_disaster",), (), ("Autos", "Electronics", "Nuclear power"), (("7203.T", "Toyota"), ("EWJ", "Japan equity ETF")), "Major earthquakes can halt plants and ports and disrupt supplier chains.", "Japan's infrastructure is unusually resilient. Most large quakes cause little market impact.", zones=("japan",), basis="Japanese Cabinet Office disaster reports."),
    Rule("coffee", "Coffee weather", ("agriculture",), (("KC=F", "Arabica coffee"),), ("Coffee roasting", "Food retail"), (("SBUX", "Coffee buyer"), ("NSRGY", "Coffee buyer")), "Frost or drought in Brazil and Vietnam can reduce crops.", "Point weather samples are not crop surveys. Crop stage and hedging matter.", crop="coffee", basis="USDA FAS and ICO report Brazil and Vietnam as the largest producers."),
    Rule("cocoa", "Cocoa weather", ("agriculture",), (("CC=F", "Cocoa"),), ("Confectionery",), (("HSY", "Cocoa buyer"), ("MDLZ", "Cocoa buyer")), "West African weather and disease can cut cocoa supply.", "Disease and tree age may matter as much as weather.", crop="cocoa", basis="ICCO reports Cote d'Ivoire and Ghana as the largest producers."),
    Rule("grains", "US and global grains", ("agriculture",), (("ZC=F", "Corn"), ("ZS=F", "Soybeans"), ("ZW=F", "Wheat")), ("Grain trading", "Farm equipment", "Fertiliser"), (("ADM", "Grain trader"), ("BG", "Grain trader"), ("DE", "Farm equipment")), "Weather stress in key regions can reduce yields.", "Timing against crop stage matters. Other regions may offset.", basis="USDA WASDE."),
    Rule("natgas_weather", "Gas heating demand", ("agriculture", "extreme_weather"), (("NG=F", "Natural gas"),), ("Gas utilities", "Power"), (("XLU", "US utilities ETF"),), "Cold in major cities raises heating demand.", "Storage levels matter as much as weather.", crop="natural_gas", basis="EIA weekly gas storage reports."),
    Rule("fed", "US monetary policy", ("central_bank",), (("GC=F", "Gold"),), ("Banks", "Housing", "Growth equities"), (("^GSPC", "S&P 500"), ("^TNX", "US 10-year yield"), ("XLF", "US financials ETF"), ("DX-Y.NYB", "US dollar index")), "Rate decisions and guidance reprice bonds, currencies and equities.", "Markets respond to the surprise against expectations, and ATLAS has no free consensus forecast.", regions=("US",), basis="Federal Reserve statements."),
    Rule("rba", "Australian monetary policy", ("central_bank",), (), ("Banks", "Housing"), (("^AXJO", "ASX 200"), ("AUDUSD=X", "Australian dollar"), ("CBA.AX", "Largest Australian bank")), "RBA decisions can move the Australian dollar, bank shares and bonds.", "Only the surprise matters, and ATLAS has no free consensus forecast.", regions=("Australia",), basis="RBA statements."),
    Rule("inflation", "Inflation prints", ("inflation",), (("GC=F", "Gold"),), ("Bonds", "Consumer staples"), (("^TNX", "US 10-year yield"), ("XLF", "US financials ETF")), "A higher or lower print than expected can shift rate expectations.", "This compares with the previous print, not with a consensus forecast, so it is not a true surprise measure.", basis="Official statistics agencies."),
    Rule("sanctions_energy", "Energy sanctions", ("regulatory", "geopolitical"), (("BZ=F", "Brent crude"),), ("Crude shipping", "Refining"), (("FRO", "Crude tankers"), ("XOM", "Global oil producer")), "Sanctions can reroute oil and raise shipping distance.", "Sanctioned barrels often still reach buyers at a discount.", keywords=("iran", "russia", "venezuela", "oil", "petroleum", "energy"), basis="OFAC sanctions notices."),
    Rule("chip_controls", "Chip export controls", ("regulatory",), (), ("Semiconductors",), (("NVDA", "China chip sales"), ("AMD", "China chip sales"), ("ASML", "Equipment exports"), ("AMAT", "Equipment exports"), ("LRCX", "Equipment exports")), "Export limits can reduce sales to affected buyers.", "Many notices are procedural. Read the rule before drawing conclusions.", keywords=("entity list", "semiconductor", "export control", "advanced computing"), basis="US Bureau of Industry and Security rules."),
]
RULES_BY_ID = {r.id: r for r in RULES}

# Dated public events, used only as analogues. Each links to a public description.
HISTORY = [
    ("2005-08-29", "Hurricane Katrina", ("gulf_energy",), "https://en.wikipedia.org/wiki/Hurricane_Katrina"),
    ("2005-09-24", "Hurricane Rita", ("gulf_energy",), "https://en.wikipedia.org/wiki/Hurricane_Rita"),
    ("2008-09-13", "Hurricane Ike", ("gulf_energy",), "https://en.wikipedia.org/wiki/Hurricane_Ike"),
    ("2017-08-25", "Hurricane Harvey", ("gulf_energy",), "https://en.wikipedia.org/wiki/Hurricane_Harvey"),
    ("2020-08-27", "Hurricane Laura", ("gulf_energy",), "https://en.wikipedia.org/wiki/Hurricane_Laura"),
    ("2021-08-29", "Hurricane Ida", ("gulf_energy",), "https://en.wikipedia.org/wiki/Hurricane_Ida"),
    ("2019-09-14", "Abqaiq oil facility attack", ("hormuz", "sanctions_energy"), "https://en.wikipedia.org/wiki/Abqaiq%E2%80%93Khurais_attack"),
    ("2019-06-13", "Gulf of Oman tanker attacks", ("hormuz",), "https://en.wikipedia.org/wiki/June_2019_Gulf_of_Oman_incident"),
    ("2020-01-03", "Soleimani strike", ("hormuz",), "https://en.wikipedia.org/wiki/Assassination_of_Qasem_Soleimani"),
    ("2021-03-23", "Ever Given blocks Suez", ("red_sea",), "https://en.wikipedia.org/wiki/2021_Suez_Canal_obstruction"),
    ("2023-12-15", "Red Sea attacks divert carriers", ("red_sea",), "https://en.wikipedia.org/wiki/Red_Sea_crisis"),
    ("2023-08-03", "Panama Canal drought limits", ("panama",), "https://en.wikipedia.org/wiki/Panama_Canal"),
    ("2022-08-02", "Pelosi visit and Taiwan drills", ("malacca_taiwan",), "https://en.wikipedia.org/wiki/2022_visit_by_Nancy_Pelosi_to_Taiwan"),
    ("2024-04-03", "Hualien earthquake", ("malacca_taiwan",), "https://en.wikipedia.org/wiki/2024_Hualien_earthquake"),
    ("2022-02-24", "Russia invades Ukraine", ("black_sea", "sanctions_energy"), "https://en.wikipedia.org/wiki/Russian_invasion_of_Ukraine"),
    ("2023-07-17", "Black Sea grain deal ends", ("black_sea",), "https://en.wikipedia.org/wiki/Black_Sea_Grain_Initiative"),
    ("2011-03-11", "Tohoku earthquake", ("japan",), "https://en.wikipedia.org/wiki/2011_T%C5%8Dhoku_earthquake_and_tsunami"),
    ("2024-01-01", "Noto earthquake", ("japan",), "https://en.wikipedia.org/wiki/2024_Noto_earthquake"),
    ("2021-07-20", "Brazil frost", ("coffee",), "https://en.wikipedia.org/wiki/Coffee_production_in_Brazil"),
    ("2010-02-27", "Chile earthquake", ("chile_copper",), "https://en.wikipedia.org/wiki/2010_Chile_earthquake"),
    ("2015-09-16", "Illapel earthquake", ("chile_copper",), "https://en.wikipedia.org/wiki/2015_Illapel_earthquake"),
    ("2022-10-07", "US chip export rules", ("chip_controls",), "https://en.wikipedia.org/wiki/United_States_New_Export_Controls_on_Advanced_Computing_and_Semiconductors_to_China"),
    ("2012-06-21", "US drought peak concerns", ("grains",), "https://en.wikipedia.org/wiki/2012_North_American_drought"),
]


def in_zone(zone: str, lat: float, lon: float) -> bool:
    west, south, east, north = ZONES[zone]["bbox"]
    return west <= lon <= east and south <= lat <= north


def matching_rules(category: str, lat: float | None = None, lon: float | None = None, chokepoint: str | None = None, crop: str | None = None, text: str = "", region: str | None = None) -> list[Rule]:
    low = text.lower()
    out = []
    for r in RULES:
        if category not in r.categories:
            continue
        zone = lat is not None and lon is not None and any(in_zone(z, lat, lon) for z in r.zones)
        choke = chokepoint is not None and chokepoint in r.chokepoints
        grown = crop is not None and (r.crop == crop or (r.id == "grains" and crop in {"corn", "soybeans", "wheat"}))
        word = any(k in low for k in r.keywords)
        place = region is not None and region in r.regions
        unconditional = category == "inflation"
        if zone or choke or grown or word or place or unconditional:
            out.append(r)
    return out


def analogues(rule_ids: list[str]) -> list[dict]:
    return [{"date": d, "title": t, "rules": list(rules), "url": u} for d, t, rules, u in HISTORY if set(rules) & set(rule_ids)]
