# ATLAS

A local-first financial and global intelligence app. It runs on your Mac, costs nothing to run, and labels every number with where it came from and how fresh it is.

Version 2.1 fits phones, tablets and large monitors, and adds phone access over Wi-Fi. Version 2 added an all-new interface with light and dark themes, a daily Today briefing, faster data, a calendar and more sources.

ATLAS is a research tool. It is not investment advice and it never places real orders.

## Install on macOS

Needs Apple Silicon, Node.js 20 or newer, and about 2 GB of disk. The installer fetches [uv](https://docs.astral.sh/uv/) and Python 3.12 if you do not have them.

```bash
unzip atlas.zip && cd atlas
```

```bash
./scripts/install.sh
```

```bash
./scripts/start.sh
```

ATLAS opens at <http://127.0.0.1:3000>. Press Ctrl+C in the terminal to stop it. Everything is bound to this Mac only.

Market data loads in about a second, even on a first run. Shipping can take up to a minute the first time, and crop-weather baselines about 2 minutes, because those providers are slow or rate limited. Both fill in by themselves in the background.

## Use it on your phone or tablet

```bash
./scripts/start.sh --lan
```

ATLAS prints an address and a passcode. Connect the phone to the same Wi-Fi, open the address, and enter the passcode. In Safari, Share then Add to Home Screen gives it an app icon. The Mac must stay on and running ATLAS.

Without `--lan`, ATLAS stays private to your Mac. With it, anyone on your Wi-Fi can reach the passcode page, and traffic is not encrypted, so use it only on networks you trust. Set `ATLAS_PASSCODE` in `.env` to keep the same passcode between starts.

## Optional free setup

ATLAS works with no keys. Edit `.env` and restart to unlock more.

| Setting | Unlocks | Get it |
| --- | --- | --- |
| `ATLAS_SEC_CONTACT` | Every SEC filer (not only 43 large caps) and parsed Form 4 insider trades | Your own name and email. SEC asks automated clients to identify themselves |
| `ATLAS_FRED_API_KEY` | US GDP, retail sales, housing starts, industrial production | [Free key](https://fred.stlouisfed.org/docs/api/api_key.html) |
| `ATLAS_BLS_API_KEY` | Higher BLS daily allowance | [Free key](https://www.bls.gov/developers/) |
| `ATLAS_OLLAMA_MODEL` | Written assistant answers from a local model | Install [Ollama](https://ollama.com), then run `ollama pull llama3.2` |
| `ATLAS_MACOS_NOTIFICATIONS=true` | Alert banners in macOS | Nothing else needed |

Without Ollama the assistant still works. It shows the retrieved evidence with citations instead of writing prose.

## Using it

| Keys | Action |
| --- | --- |
| Cmd+K or `/` | Search tickers, companies and pages. Long questions go to the assistant |
| Cmd+J | Open the assistant |
| `?` | Show every shortcut |
| `g` then a letter | Jump to a page: d Today, m Markets, c Charts, r Companies, e Economy, w Map, q Quant, p Portfolio, a Alerts |

On Today, press Edit to drag, hide or restore cards. Drag watchlist rows to reorder them. Workspace is the dense layout with resizable panels. Tables with an Export button download as CSV. Switch themes from the top bar, or choose Automatic in Settings.

ASX symbols end in `.AX`, for example `BHP.AX`. Shares outside the US get a price page with chart, 52-week range and news; full statements cover SEC filers. On any chart, the star adds to your watchlist and Alert sets a price alert. Futures use Yahoo symbols such as `CL=F`.

Portfolio CSV columns are `date, symbol, side, quantity, price`, with optional `fee, currency, note`. Side is one of buy, sell, dividend, deposit, withdraw.

## Test

```bash
./scripts/test.sh
```

Browser tests need ATLAS running:

```bash
cd frontend && npx playwright install chromium && npx playwright test
```

Real-network checks:

```bash
cd backend && uv run pytest -m live
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Feature matrix](docs/FEATURE_MATRIX.md): what is built, partial and missing
- [Known limitations](docs/LIMITATIONS.md)
- [Roadmap](docs/ROADMAP.md)

Licences for every data source are on the Sources page. Your Mac uses the system San Francisco font; other systems fall back to Inter. Charts use TradingView Lightweight Charts (Apache 2.0, attribution shown on each chart). Maps use OpenFreeMap with OpenStreetMap data.
