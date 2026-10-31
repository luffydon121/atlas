# V3 limitations

These add to `LIMITATIONS.md`.

## Needs your decision

- **Yahoo data on the public demo.** Yahoo's data is for personal use. `chluffy.net` shows it publicly, so that use may breach Yahoo's terms. OpenSky and Open-Meteo also limit commercial or public use. The Data Quality Center lists this per source. Consider removing those feeds from the demo or getting permission.
- **SEC contact.** Position-level 13F data, the full ticker list and Form 4 parsing need `ATLAS_SEC_CONTACT`. Without it, Holdings shows filing history only.

## Impact Engine

- Exposure rules are hand-written, cover 19 themes and are not exhaustive. An unmatched event shows no exposure.
- Rule text summarises public knowledge. It has not been reviewed by a specialist.
- Analogue lists are short, often 3 to 6 events, so most reactions do not survive correction. That is an honest result.
- Events are dated by the reading, not by when a condition began.
- Event records stay in the feed for 30 days after they were last seen, even if a later rule would exclude them.
- No live NWS alerts are linked yet, because they carry no coordinates.

## Economics

- There are no consensus forecasts, so no true surprise indicators. Inflation events compare with the previous print.
- Release dates cover the US BEA only. BLS blocks automated access.
- OECD data ends early for some countries, and Japan's inflation series is out of date. Those rows are flagged.
- IMF data refused automated access.

## Satellite

- High-resolution import and object detection are not built. They need a validated model with a compatible licence.
- Reports are Markdown tables. Before and after images are not embedded.
- Polygons must be under about 30 km a side.
- Confidence comes from clear pixels and noise, not ground truth.

## Shipping

- Port data is estimates from a slow service. It can take minutes on a first run, and it sometimes refuses queries.
- There is no AIS integration and no live vessel tracking.
- Port call changes are a proxy and do not measure queues.

## Assistant

- Ollama was not installed during development, so model answers and embeddings have only run against simulated servers.
- It routes by keywords and rules, so unusual questions may retrieve little.
- Keyword rules can match broadly. Evidence is shown, so you can judge relevance.

## Security

- The rate limit trusts `cf-connecting-ip`, then `x-forwarded-for`. Without Cloudflare in front, a client could change that header.
- It is per process and resets on restart.

## Not verified

- Docker was not installed, so the `Dockerfile` itself has not been built here. Its steps were rehearsed by hand.
- In that rehearsal the demo used about 350 MB when idle and up to about 520 MB under heavy use on macOS. Linux may differ, and a 512 MB plan could restart under load.
- `--lan` mode has not been tested over a real network.
- Tests use emulated phones, not physical devices. Firefox could not start in the test environment.
