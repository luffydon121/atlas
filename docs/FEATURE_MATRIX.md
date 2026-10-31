# Feature matrix

**Done** means built and exercised with real data or tests. **Partial** means useful but narrower than the brief. **No** means not built.

## Version 2.1 additions

| Feature | Status | Notes |
| --- | --- | --- |
| Layouts from 320 px phones to 2560 px monitors | Done | Automated checks at 8 sizes on 20 pages |
| Phone tab bar, touch-sized controls, layers sheet | Done | |
| Phone and tablet access over Wi-Fi with passcode | Done | Opt-in with `--lan` |
| Price page for shares outside the US | Done | No statements without SEC data |
| Watchlist star and quick price alert on charts | Done | |
| News filter, shortcut list, error and not-found pages, offline banner | Done | |
| Safari engine, iPhone and Android emulation tests | Done | Emulated, not real devices |

## Version 2 additions

| Feature | Status | Notes |
| --- | --- | --- |
| New interface, light and dark themes | Done | Reviewed at 1440 px in both themes |
| Today briefing with editable cards | Done | Written by fixed rules from retrieved numbers |
| Sparklines, batch quotes, faster loads | Done | |
| Spotlight-style search with recents and ask | Done | |
| Calendar | Partial | FOMC and RBA dates are official; earnings are estimates; no data-release dates |
| ABS unemployment, OECD leading indicators, EIA crude stocks | Done | |
| Live crypto tiles | Done | Binance USDT pairs, polled every 5 seconds |
| Dividend-adjusted backtests | Done | On by default, can be switched off |
| Satellite change alerts | Done | Tested through shared code; not run on a schedule against real scenes |
| Watchlist drag reorder, CSV export | Done | |
| Workspace layout | Done | The V1 dashboard, restyled |

## All milestones

| Milestone | Status |
| --- | --- |
| 1 Core terminal | Done, except equities outside US lack fundamentals |
| 2 Global intelligence | Mostly done; shipping and aviation are limited by free data |
| 3 Advanced research | Partial: assistant works, alternative data covers 5 of 23 listed signals |
| 4 Quantitative intelligence | Done for single assets and portfolios; satellite alerts missing |
| 5 Optimisation | Not started beyond basic caching |

| Area | Feature | Status | Notes |
| --- | --- | --- | --- |
| Markets | Stocks, ETFs, indices, FX, futures, crypto | Done | Delayed. Yahoo endpoint |
| Markets | Yields, volatility, sector performance | Done | |
| Markets | Breadth | Partial | 43 large caps only |
| Markets | Candlesticks, timeframes, SMA, Bollinger, RSI, MACD | Done | |
| Markets | Comparison, correlation, heatmap, screener | Done | Heatmap covers sectors; screener covers 43 large caps |
| Markets | Watchlists, trailing returns, price alerts | Done | |
| Markets | Custom dashboards | Partial | Resizable, selectable panels, one saved layout |
| Company | Statements, ratios, growth, FCF, multiples | Done | SEC XBRL |
| Company | Filings, dividend history, competitor comparison | Done | |
| Company | DCF, scenarios, sensitivity | Done | Marked as estimates |
| Company | Insider transactions | Partial | Links by default; parsing needs SEC contact and is untested live |
| Company | Earnings calendar | Partial | Past dates plus an estimate |
| Company | Institutional ownership | No | |
| Company | Industry research | No | SIC industry label only |
| Satellite | Sentinel-2 search, cloud and resolution metadata | Done | |
| Satellite | Change detection with confidence and overlay | Done | Pixel-level, run live on Mount Whaleback |
| Satellite | Mining, agriculture, construction, environment, industrial | Partial | 10 fixed areas; index change only |
| Satellite | Retail and oil trackers | Refused | Resolution cannot support them |
| Satellite | Landsat, Copernicus | Partial | Catalogue only |
| Satellite | Detection model evaluation | No | |
| Shipping | Chokepoint transits, tankers, containers, disruption flag | Done | 9 chokepoints |
| Shipping | Routes and ports on map | Done | Schematic reference data |
| Shipping | Vessel tracking, port congestion, LNG | No | |
| Aviation | Live aircraft in view, airport activity proxy | Done | Quota-limited |
| Aviation | Historical flights, airline research | No | |
| Weather | Forecasts, hazards, US alerts, tropical storms | Done | |
| Weather | Commodity risk for 6 markets | Done | Screens, not forecasts |
| Economy | US, Australia, euro area dashboards | Done | |
| Economy | Yield curve, recession indicators, World Bank global | Done | |
| Economy | FRED series | Partial | Needs key, untested live |
| Economy | IMF, economic data-release dates | No | IMF blocks automated requests |
| Geopolitics | Events, tiers, map | Done | Official and automated clearly separated |
| Crypto | Prices, volume, BTC and ETH network, DeFi, stablecoins | Done | |
| Crypto | Exchange flows, token unlocks | No | No reliable free source |
| Alternative | Attention, shipping, crop weather, land change, airports | Done | With method, uncertainty and validation notes |
| Alternative | Other 18 listed signals | No | Reasons listed on the page |
| Assistant | Retrieval, citations, missing-data reporting | Done | |
| Assistant | Hallucination guard, reports, local documents | Done | |
| Assistant | Ollama narration | Partial | Simulated server only |
| Assistant | Vector search | No | Keyword search today |
| Quant | Backtests, costs, walk-forward, Monte Carlo | Done | |
| Quant | Optimiser, factor proxies, metrics | Done | |
| Portfolio | Entries, CSV, P&L, FX, allocation, risk, benchmark | Done | |
| Portfolio | Paper trading | Done | Simulated fills at delayed prices |
| Alerts | Price, volume, filings, economic releases, weather, shipping, earthquakes | Done | Weather and shipping rules unit-tested through shared code only |
| Map | 14 toggle layers, NASA imagery, date playback | Done | Playback for imagery only |
| Interface | Dark terminal, palette, shortcuts, resizing, full-screen charts, assistant sidebar | Done | |
| Reliability | Rate limits, retries, cache, stale fallback, registry | Done | |
| Security | Local binding, host check, safe parsing, no telemetry | Done | |
