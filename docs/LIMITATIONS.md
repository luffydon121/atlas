# Known limitations

## Data

- **Yahoo Finance** powers prices through an undocumented public endpoint meant for personal use. It can change or block without notice, quotes are usually delayed 15 minutes or more, and data must not be redistributed. When it fails, ATLAS falls back to locally stored bars and labels them stale.
- **Stooq** was rejected: it now serves a browser check, and solving that would bypass a technical restriction.
- **FRED** did not respond to anonymous CSV requests during development, so it needs a free key. The FRED code path has never been run against the real service.
- **ATLAS_SEC_CONTACT and the full ticker list** were not exercised with a real contact. Form 4 parsing is tested on a sample document only.
- **Market cap** is only available where SEC share counts exist, so mainly US companies. ASX and other non-US names get prices and charts but no fundamentals.
- **Enterprise value** uses cash and equivalents only and excludes marketable securities, so it is overstated for cash-rich firms such as Apple.
- **XBRL tags** vary. Banks and insurers have sparser statements, and some ratios show a dash.
- **Earnings dates** are past 8-K filings plus a 91-day estimate. No free source of confirmed future dates was found.
- **Economic data-release dates** are missing because BLS blocks automated access to its schedule. The calendar shows central bank decisions and earnings estimates only.
- **The calendar** reads Federal Reserve and RBA web pages, so a layout change on those pages would empty it.
- **Live crypto tiles** poll one exchange every 5 seconds in USDT, not USD.
- **Backtests** default to dividend-adjusted closes. The screener universe is today's large caps, so it has survivorship bias.
- **Point-in-time data** exists only from your install date.
- **GDELT** was rate limited for much of development. Geopolitics may show only official US Federal Register items until it recovers.
- **Open-Meteo** is free for non-commercial use. Weather regions are single points with approximate weights, not crop maps.

## Satellite

- Sentinel-2 resolves 10 to 20 m. Retail parking and oil-tank trackers deliberately refuse to produce estimates.
- Landsat is catalogue-only, because its pixels are requester-pays.
- Copernicus Data Space is metadata search only.
- Confidence comes from clear-pixel share and noise. No detector has been evaluated against ground truth.
- Change between seasons can be natural. Compare the same season in different years.

## Shipping and aviation

- There is no live vessel tracking. PortWatch gives daily chokepoint estimates several days late. Its service is slow, so the first shipping load can take up to a minute.
- Port congestion, container port throughput and LNG-specific indicators are not implemented.
- OpenSky allows 400 anonymous credits a day and has no history without an account. Airport history is only what you have sampled.

## Assistant

- Tested against a simulated Ollama server only. No real local model has been run through it, because Ollama was not installed on the development Mac.
- It routes questions by keywords, so unusual phrasing can miss data. It says so rather than guessing.
- The hallucination guard checks figures, not meaning. A model can still misinterpret correct numbers.
- Document search is keyword based, and scanned PDFs need OCR first.

## App

- Designed for desktop. Narrow windows collapse the sidebar, but dense tables need horizontal scrolling.
- Customisation means reordering and hiding Today cards and resizing Workspace panels. There is no free-form widget grid.
- Prices are delayed quotes, so "live" movement outside crypto depends on the provider.
- There is no database migration tool yet.
- Price updates are polled, not streamed.
- The scheduler only runs while ATLAS is running.
