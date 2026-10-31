# V3 feature matrix

**Complete** works and is tested. **Partial** works but is narrower than the brief. **Blocked** needs something outside ATLAS. **Not built** has not been started.

| Part | Feature | Status | Notes |
| --- | --- | --- | --- |
| 2 | Alembic migrations, backups, migration tests | Complete | Upgrade tested on a copy of real data |
| 2 | Indexed time series, storage monitoring | Complete | |
| 2 | Retention controls | Partial | Automatic for caches and job history only, by design. No user settings |
| 2 | DuckDB and Parquet | Not built | Optional, and not needed at 100 MB |
| 2 | Job runner, history, dashboard, recovery, shutdown | Complete | |
| 2 | Provenance, Data Quality Center | Complete | Reliability is a stated rule, not a measurement |
| 2 | Public demo audit | Complete | Allow list, rate limit, attack-tested locally |
| 3 | Event feed, severity, verification, map link | Complete | |
| 3 | Infrastructure, exposed assets, mechanisms, uncertainty | Complete | 19 hand-written themes |
| 3 | Historical comparisons, reaction charts, evidence | Complete | |
| 3 | Scenarios and relationship data | Complete | Hypothetical, clearly labelled |
| 3 | Earnings, industrial shutdown and energy incident events | Not built | No suitable structured free feed connected |
| 4 | Drawn polygons, saved areas, schedules, alerts, history | Complete | |
| 4 | Same-season comparison, overlays, reports | Partial | Reports are tables without images |
| 4 | Nine tracker types | Partial | Presets of index and purpose, not separate models |
| 4 | High-resolution import and detection | Not built | Needs a validated model |
| 5 | Chokepoint dashboards, disruption detection | Complete | 9 chokepoints |
| 5 | Port dashboards, congestion proxy | Complete | 12 ports |
| 5 | Commodity trade routes, energy exposure | Partial | Schematic routes and exposure rules |
| 5 | Optional AIS, export and import risk indicators | Not built | |
| 6 | Central banks, inflation, unemployment, yield curves | Complete | 7 economies where data exists |
| 6 | Release calendar | Partial | BEA only |
| 6 | Surprise indicators | Blocked | No free consensus forecasts |
| 6 | Housing and manufacturing by country | Partial | US and via free FRED key |
| 7 | 13F history | Complete | |
| 7 | 13F positions and changes | Blocked | Parser tested on samples. Needs your SEC contact |
| 7 | Relationship graph | Partial | Backend search only, with no visual page. Subsidiaries are not included |
| 7 | Patents | Blocked | USPTO needs a key |
| 7 | Procurement | Partial | US federal only |
| 7 | Transcripts, anomaly detection | Not built | |
| 8 | Alternative Data Lab, 20 documented indicators | Partial | 7 live, 4 partial, 3 planned, 6 blocked |
| 9 | Retrieval, citations, Impact Engine evidence | Complete | Rule-based routing |
| 9 | Ollama narration, embeddings, hybrid search | Partial | Tested on simulated servers only |
| 9 | Multi-document comparison | Not built | |
| 10 | Event studies, regimes, rolling correlation, stress tests | Complete | |
| 10 | Multi-asset backtest, strategy comparison, multiple-testing control | Partial | Multi-asset backend only, with no page yet |
| 10 | Slippage, walk-forward | Complete | |
| 11 | Clusters, impact layer, regions, areas, saved views | Complete | |
| 11 | Event timeline playback | Not built | Playback covers NASA imagery only |
| 11 | Viewport loading | Partial | Aircraft only |
| 12 | V3 pages, navigation, shortcuts, responsive layouts | Complete | |
| 12 | Saved layouts | Partial | Named symbol and panel choice, not panel positions |
| 13 | Daily, weekly, asset, country, commodity briefings | Complete | |
| 13 | Markdown and HTML | Complete | |
| 13 | PDF | Partial | Through the browser's print dialog |
| 15 | Backend, migration, security tests | Complete | See `V3_TEST_RESULTS.md` |
| 15 | End-to-end, responsive, accessibility tests | Complete | |
| 15 | Component tests | Not built | Browser tests cover these paths |
