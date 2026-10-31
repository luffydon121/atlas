# V3 changelog

## Foundation

- Merged V2.1 onto the GitHub history, so phone layouts and the public demo now live together.
- Added Alembic migrations with automatic backups, and tested them on a copy of real data.
- Replaced the sequential loop with a job runner with timeouts, retries and stored history.
- Every response now carries licence and limitations.
- Nothing older than two minutes can be labelled live. Yahoo crypto, hazards and news are now labelled delayed.
- Changed the public demo from a block list to an allow list, and added rate limiting. `/api/settings` was previously open.
- Uploads now check PDF headers and refuse binary text files.

## New

- Impact Engine, with event feed, exposures, past reactions, scenarios and a relationship graph.
- Event Study Lab, with custom dates, volatility regimes, rolling correlation and stress tests.
- Intelligence Briefing: daily, weekly, asset, country and commodity, in Markdown, HTML and print.
- Data Quality Center, with source health, job status and storage.
- Institutional Holdings: Form 13F history, positions and quarter-on-quarter changes.
- Saved satellite areas with drawn polygons, scheduled checks, same-season comparison, alerts and reports.
- Port activity, central bank tracker, cross-country inflation and unemployment, BEA release dates.
- Alternative Data Studio with 20 documented signals, crude stocks and federal contract awards.
- Hybrid keyword and vector document search through Ollama.
- Map clustering, Impact layer, exposure regions, monitoring areas and saved views.
- Named Workspace layouts, strategy comparison with multiple-testing correction, slippage assumptions.

## Fixed

- Yahoo `range=max` returns monthly data, so event studies request explicit dates.
- Crop alerts now respect growing seasons, and prescribed burns no longer count as disasters.
- ECB inflation ended in December 2025. Euro area comparisons now use Eurostat.
- Out-of-date country figures are flagged and left out of charts.
- Muted text and status pills now meet WCAG AA contrast in both themes.
