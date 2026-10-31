# Architecture

```
Browser (127.0.0.1:3000)
  Next.js + React + TypeScript + Tailwind
  Lightweight Charts, Apache ECharts, MapLibre GL, SWR
        |  /api/* rewritten to the backend
FastAPI (127.0.0.1:8000)
  api/         HTTP routes, input validation, provenance envelope
  services/    analytics, valuation, quant, portfolio, satellite, alerts, assistant, documents, scheduler
  connectors/  one module per provider family
  core/        Fetcher, source registry, reference data, errors
        |
SQLite (data/atlas.db, WAL mode)     Public data providers
```

## Decisions

| Choice | Why |
| --- | --- |
| SQLite only | Enough for one user on a laptop, with no server to run. DuckDB, Parquet and PostgreSQL were left out because nothing needs them yet |
| In-process scheduler | No queue or cloud service required |
| Python 3.12 | Reliable wheels for rasterio and scipy on Apple Silicon |
| `create_all` instead of migrations | The schema is young. Add Alembic before the first change that must preserve user data |
| Retrieval before narration | The model can only rephrase evidence, so it cannot introduce unchecked figures |
| FTS5 for documents | Fast local search with no embedding model. Vector search can be added once Ollama is standard |

## Data flow

Every network call goes through `core/fetcher.py`, which provides per-provider pacing, retries with exponential backoff that honour `Retry-After`, a SQLite cache, request coalescing, response validation, health recording and stale-cache fallback.

Every data response is wrapped by `core/envelope.py` with `source`, `freshness` (live, delayed, historical, estimated, reference, unavailable), `as_of`, `fetched_at`, `stale` and `note`. The UI shows these on each panel.

## Speed

- Quotes use Yahoo's batch endpoint: one request per 20 symbols, with intraday sparklines included.
- Slowly changing sources answer from the last copy at once and refresh in the background (`BACKGROUND_REFRESH` in `core/fetcher.py`).
- `core/memo.py` keeps computed responses in memory, and the scheduler warms the market data every 2 minutes.
- JSON is encoded with orjson and compressed with gzip.
- The browser restores recent responses after hydration, so a reload paints from memory, then revalidates. Restoring before hydration would mismatch the server HTML.
- ECharts is tree-shaken. Pages keep previous data while the next request runs, and menu hover preloads the next page's data.

## Interface

`app/globals.css` holds the design tokens for both themes. The theme is applied by an inline script before first paint. `Shell` must not read the theme during render: it sits above the prerendered page, and a mismatch there forces React to rebuild the boundary, which once left a duplicate headline in dark mode. A browser test guards this.

## Storage

| Table | Holds |
| --- | --- |
| `cache_entries`, `source_status` | HTTP cache and provider health |
| `bars` | Daily, weekly and monthly prices, used as a fallback during outages |
| `observations` | Append-only series values. A revision is a new row, so `econ.history(id, as_of)` reads what was known at a past time |
| `news_items` | Deduplicated headlines |
| `watchlists`, `watchlist_items`, `layouts` | Workspace |
| `portfolios`, `transactions` | Local financial records, including paper accounts |
| `alerts`, `notifications` | Alert rules and the notification centre |
| `documents`, `doc_chunks` | Uploaded files and FTS5 index |
| `satellite_measurements` | Stored index means per area |

## Research integrity

- `quant.simulate` shifts signals by one bar, so a bar cannot trade on itself. A test proves strategies give the same past signals with or without future prices.
- `quant.walk_forward` selects parameters on a trailing window and scores only the following unseen window.
- Observations record when ATLAS first saw each value, which gives point-in-time reads from the day you install. Earlier history is not point-in-time.

## Security

- By default both servers bind to 127.0.0.1. `--lan` exposes only the web app, behind the passcode check in `frontend/proxy.ts`. The API always stays on 127.0.0.1. `TrustedHostMiddleware` rejects foreign Host headers, which blocks DNS rebinding. CORS allows only the local frontend.
- Secrets come from `.env`, which is git-ignored, and are never returned by the API.
- XML is parsed with defusedxml. Uploads have a size limit, a type allow-list and sanitised names.
- Retrieved text is treated as data: map popups use text nodes, feed links must be http or https, and the model gets no tools. Instruction-like phrases in evidence are flagged, which reduces but does not eliminate prompt-injection risk.
- ATLAS sends no telemetry, and Next.js telemetry is disabled in all scripts.

## Adding a connector

1. Add a `Source` to `core/registry.py` with its licence and limits.
2. Fetch through `get_fetcher().get(source_id, url, ttl=...)`.
3. Keep parsing in a pure function and unit test it.
4. Return data through `envelope(...)` with an honest freshness.
