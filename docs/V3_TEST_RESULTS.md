# V3 test results

Run on 1 November 2026, on an Apple Silicon Mac, on the `v3-development` branch.

| Check | Result |
| --- | --- |
| Backend tests (`uv run pytest`) | 184 passed |
| Live network tests (`uv run pytest -m live`) | 3 passed. One run failed once on a PortWatch timeout, then passed. Treat as flaky |
| Ruff | Clean |
| TypeScript | Clean |
| ESLint | No errors |
| Production build | Compiled |
| Browser tests on a clean production build | 132 passed |
| Demo build browser tests | 18 passed |
| `pip-audit` and `npm audit --omit=dev` | No known vulnerabilities |
| Migration on a copy of real data | Row counts identical in 12 tables, 0.31 seconds, schema matches models |

## What the browser tests cover

Chrome and the Safari engine at desktop size, iPhone and Android emulation, 25 pages at 8 screen sizes from 320 to 2560 pixels, the V3 workflows, and axe accessibility checks with colour contrast on 7 pages.

## Run by hand

The public demo was run in read-only mode with an empty database. Private paths, all write methods and path tricks returned 403 or redirected to a 403. The rate limit began at request 121. Demo pages loaded with no page errors.

Live checks confirmed event detection, 6 hurricane analogues across 9 assets, BIS rates, BEA dates, 13F history and a real Sentinel-2 monitoring check.

## Needs external services

`tests/test_live.py` calls Yahoo, the US Treasury and IMF PortWatch.

## Not run

- Docker image build, because Docker is not installed. Its steps were followed by hand from a clean clone, in read-only mode with an empty database.
- `--lan` over a real network.
- Real Ollama models.
- 13F positions and Form 4 parsing on real filings, which need an SEC contact.
- Firefox, which could not start in the test environment.
- Physical phones and tablets.
