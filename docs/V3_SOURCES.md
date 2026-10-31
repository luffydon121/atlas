# Data sources and licences

Generated from `backend/atlas/core/registry.py`. These are plain summaries. The provider's own terms apply.

| Provider | Coverage | Licence | Redistribution | Limitations |
| --- | --- | --- | --- | --- |
| [Yahoo Finance chart endpoint](https://finance.yahoo.com) | Global equities, ETFs, indices, FX, futures, crypto | Unofficial public endpoint. Personal, non-commercial use; do not redistribute. | Personal use. Do not republish. | Undocumented and may change without notice. Quotes are typically delayed 15+ minutes. Excessive requests can be blocked. |
| [SEC EDGAR](https://www.sec.gov/edgar) | US-listed filers: XBRL financials, filings, Forms 3/4/5 | US Government public data | Public data. Attribute the source. | 10 requests/second maximum. Non-US issuers filing no XBRL are not covered. The full ticker list needs ATLAS_SEC_CONTACT. |
| [US Bureau of Labor Statistics](https://www.bls.gov/developers/) | US CPI, employment, wages | US Government public data | Public data. Attribute the source. | 25 queries a day and 10 years without a free key. |
| [US Treasury](https://home.treasury.gov) | Daily par yield curve | US Government public data | Public data. Attribute the source. | Business days only, published after the close. |
| [World Bank Open Data](https://data.worldbank.org) | 200+ economies, annual | CC BY 4.0 | Public data. Attribute the source. | Annual and often 1-2 years behind. |
| [Reserve Bank of Australia](https://www.rba.gov.au/statistics/tables/) | Australian cash rate, inflation, yields, labour tables | CC BY 4.0 (check table notes) | Public data. Attribute the source. | CSV table layouts can change. |
| [European Central Bank](https://data.ecb.europa.eu) | Euro-area rates, inflation, FX | ECB open data, attribution required | Public data. Attribute the source. | Euro-area focus. |
| [Eurostat](https://ec.europa.eu/eurostat) | EU and euro-area statistics, including HICP on the ECOICOP v2 basis | CC BY 4.0 | Public data. Attribute the source. | Replaced the ECB HICP series, which ends in December 2025. |
| [Australian Bureau of Statistics](https://www.abs.gov.au) | Australian labour force and other SDMX datasets | CC BY 4.0 | Public data. Attribute the source. | Dataflow versions change over time. |
| [OECD Data Explorer](https://data-explorer.oecd.org) | Composite leading indicators | CC BY 4.0 | Public data. Attribute the source. | Rate limited. Latest values are revised. |
| [US Energy Information Administration](https://www.eia.gov) | Weekly US crude oil stocks | US Government public data | Public data. Attribute the source. | US inventories only, published weekly. |
| [Federal Reserve and RBA calendars](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) | FOMC and RBA decision dates | Public web pages, used for dates only | Dates only. | Page layouts can change, which would empty the calendar. |
| [Bank for International Settlements](https://data.bis.org) | Central bank policy rates | BIS terms: free reuse with attribution | Public data. Attribute the source. | Daily series, published with a short lag. |
| [USAspending.gov](https://www.usaspending.gov) | US federal contract awards | US Government public data | Public data. Attribute the source. | US federal awards only. Award size is not revenue. |
| [FRED (St. Louis Fed)](https://fred.stlouisfed.org) | US and global macro series | Free key; each series keeps its publisher's terms | Public data. Attribute the source. | Off until ATLAS_FRED_API_KEY is set. |
| [Frankfurter (ECB reference rates)](https://frankfurter.dev) | 30+ currencies, daily | Open source; ECB data | Public data. Attribute the source. | Daily reference rates, not tradable quotes. |
| Publisher RSS feeds | Central banks, regulators, business media | Headline and link only; content stays with the publisher | Headlines and links only. | Headlines only, no full text. |
| [GDELT DOC 2.0](https://www.gdeltproject.org) | Global news monitoring | Free with citation | Free with citation. | One request per 5 seconds. Automated classification, not verified fact. |
| [Federal Register](https://www.federalregister.gov/developers) | OFAC sanctions and BIS export-control documents | US Government public data | Public data. Attribute the source. | US actions only. |
| [Open-Meteo](https://open-meteo.com) | Global forecast and ERA5-based archive | CC BY 4.0, free for non-commercial use | Non-commercial use with attribution. | 10,000 calls/day. Archive lags by several days. |
| [Open-Meteo ERA5 archive](https://open-meteo.com) | Daily reanalysis back to 1940 | CC BY 4.0, free for non-commercial use | Non-commercial use with attribution. | Long ranges count as many calls, so requests are spaced 7 seconds apart. Lags by several days. |
| [USGS Earthquake Hazards](https://earthquake.usgs.gov) | Global M4.5+ earthquakes | US Government public data | Public data. Attribute the source. | Past week only in this feed. |
| [NASA EONET](https://eonet.gsfc.nasa.gov) | Wildfires, storms, volcanoes, floods | NASA open data | Public data. Attribute the source. | Curated, with some lag. |
| [US National Weather Service](https://www.weather.gov) | US severe weather alerts | US Government public data | Public data. Attribute the source. | US only. |
| [NOAA National Hurricane Center](https://www.nhc.noaa.gov) | Active Atlantic and East Pacific tropical cyclones | US Government public data | Public data. Attribute the source. | Empty outside active storms. |
| [OpenSky Network](https://opensky-network.org) | ADS-B aircraft positions | Free for research and non-commercial use | Non-commercial research use. Ask OpenSky before public display. | 400 anonymous credits a day, no history without an account, receiver coverage varies. |
| [IMF PortWatch](https://portwatch.imf.org) | Daily transits at global chokepoints, derived from AIS | IMF open data, attribution required | Public data. Attribute the source. | Lags by several days. Estimates, not individual vessel tracks. Slow on the first query of a chokepoint. |
| [Earth Search (Element 84)](https://earth-search.aws.element84.com/v1) | Sentinel-2 L2A and Landsat catalogue; Sentinel-2 COGs on AWS | Sentinel data: Copernicus open licence | Public data. Attribute the source. | 10 m resolution at best: cannot detect individual vehicles. Landsat pixels are requester-pays. |
| [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu) | Sentinel catalogue (metadata) | Copernicus open licence | Public data. Attribute the source. | Pixel downloads need a free account and are not implemented. |
| [NASA GIBS](https://nasa-gibs.github.io/gibs-api-docs/) | Daily global MODIS/VIIRS map tiles | NASA open data | Public data. Attribute the source. | 250 m or coarser. Loaded directly by the map in your browser. |
| [Binance public market data](https://data-api.binance.vision) | Major pairs against USDT | Free public endpoint, market data only | Display of market data; check Binance terms before republishing. | USDT pairs, not USD. Prices are from one exchange. |
| [Alternative.me Fear and Greed](https://alternative.me/crypto/fear-and-greed-index/) | Daily crypto sentiment index | Free with attribution | Attribution required. | A composite opinion measure, updated daily. |
| [CoinGecko public API](https://www.coingecko.com) | Crypto prices, market cap, volume | Free tier, attribution required | Attribution required. Limits apply to the free plan. | Shared low rate limit. |
| [mempool.space](https://mempool.space) | Bitcoin network statistics | Public API, AGPL open-source project | Public data. Attribute the source. | Fair-use limits. |
| [DefiLlama](https://defillama.com) | DeFi TVL and stablecoin supply | Free public API | Free with attribution. | Self-reported adapters; methodology varies by protocol. |
| [PublicNode Ethereum RPC](https://ethereum-rpc.publicnode.com) | Ethereum chain head | Free public endpoint | Public data. Attribute the source. | Shared endpoint with no uptime guarantee. |
| [Wikimedia Pageviews](https://wikimedia.org/api/rest_v1/) | Daily article views | CC0 | Public data. Attribute the source. | A proxy for public attention, not Google Trends. |
| [Ollama (local)](https://ollama.com) | Local language models on this Mac | MIT; each model has its own licence | Runs locally. | Optional. ATLAS answers from evidence without it. |
