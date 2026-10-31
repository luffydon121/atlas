# ATLAS V3 architecture

V3 extends V2.1 and keeps its layout. See `ARCHITECTURE.md` for the base design. This page covers what V3 adds.

```
Official and public feeds
        |  core/fetcher.py: pacing, retries, validation, cache, background refresh
connectors/            one module per provider family
        |
services/impact.py     normalises events ──> intel_events
core/exposure.py       documented rules: place -> theme -> commodity, industry, company
services/eventstudy.py measures past reactions, corrects for multiple tests
        |
api/                   every response carries source, freshness, licence, limitations
        |
frontend/              Impact Engine, Briefing, Holdings, Event Study Lab, Data Quality Center
```

## How the Impact Engine reasons

1. **Observe.** `collect()` reads each feed separately, so one failure never stops the others. Failed feeds are returned and shown.
2. **Classify.** Severity uses the source's own measure: Saffir-Simpson wind speed for storms, magnitude for earthquakes, percentage fall for chokepoints.
3. **Label.** `official` comes straight from a government source. `derived` is calculated by ATLAS from public data. `unverified` is machine-collected news.
4. **Link.** `exposure.matching_rules` matches category plus zone, chokepoint, crop, keyword or region. No match means no claimed exposure.
5. **Measure.** Analogues are dated past events. `eventstudy.study` fits a market model on a window before each event, with a gap, then measures abnormal returns. Commodities use raw returns.
6. **Correct.** Benjamini-Hochberg runs across all assets tested, and the page says so when nothing survives.

Rules are hypotheses. No part of this produces a probability or a forecast.

## Database

Alembic migrations live in `backend/atlas/migrations`. `core/migrate.py` runs at startup and:

- backs the database up before changing an existing one
- marks a V1 or V2 database as baseline instead of rebuilding it
- does nothing if the database is current

To restore, stop ATLAS and copy a file from `data/backups` over `data/atlas.db`.

## Background jobs

`services/jobs.py` runs jobs with bounded concurrency (3), per-job timeouts, retries with backoff and a rule that two jobs for one provider never overlap. Every run is stored in `job_runs`. After a crash, open runs are closed and each job resumes its own schedule. The list is in `services/scheduler.py`.

## Public demo

`services/public_mode.py` allows only listed read paths, so any new endpoint is private until someone adds it. It refuses all writes and limits each client to 120 requests a minute. Personal notifications are left out of Today in this mode.

## Deployment

Local use needs only `./scripts/install.sh` and `./scripts/start.sh`.

The public demo is built with the `Dockerfile`, which sets `ATLAS_PUBLIC_READ_ONLY=true`, `NEXT_PUBLIC_ATLAS_READ_ONLY=true` and turns background jobs off. Set `PORT` if your host needs it.

```bash
docker build -t atlas-demo .
```

```bash
docker run -p 10000:10000 atlas-demo
```

Nothing is deployed or pushed automatically. To publish this branch:

```bash
git push origin v3-development
```
