# 台股篩選 · TW Stocks Momentum Screener

A daily Taiwan-stock momentum screener with a static, mobile-first dashboard.
Every trading day it finds stocks in a **confirmed EMA up-trend**, enriches them
with 投信 (investment-trust) holdings and 融資 (margin) data, and publishes the
result to a GitHub Pages page.

* **Screener** — a small Python package (`screener/`) that pulls public market
  data and writes `web/data.json`.
* **Dashboard** — a single self-contained `web/index.html` that renders
  `data.json` (no build step, no dependencies).
* **Deploy** — a scheduled GitHub Actions workflow runs the screener and commits
  the updated `data.json`; GitHub Pages serves it.

> Imported from `RaisoLiu/ai-tools-sharing-talk` (`tw-stocks/`) and restructured
> for maintainability. See [ARCHITECTURE.md](ARCHITECTURE.md) for the design and
> [SCHEMA.md](SCHEMA.md) for the `data.json` contract.

## The screening rule (plain language)

A stock is listed when **all** of these hold (defaults; all live in
[`screener/config.py`](screener/config.py)):

| Rule | Meaning | Default |
|---|---|---|
| `5EMA > 20EMA > 60EMA` for ≥ N days | short/medium/long moving averages stacked in up-trend order | ≥ 5 days |
| 起漲週均 > X% | average weekly return since the trend started | > 3% |
| 均額 > Y | 30-day average daily turnover (liquidity floor) | > 2,000M NTD |
| 市值 > Z | market capitalisation (size floor; 0/unknown is kept) | > 100B NTD |
| 股價 > P | latest close price floor | > 100 NTD |
| 投信持股上升 ≥ T | 投信 holding % rose from 起漲日 to now (accumulation) | ≥ 0.1pp |

Matches are bucketed into three tiers by how recently the trend started:

* 🟢 **剛起漲** — within the last month (`tier: 1`)
* 🟡 **中段加速** — 1–3 months ago (`tier: 2`)
* 🔴 **長線主升** — more than 3 months ago (`tier: 3`)

Each card also shows 投信持股 (起漲日 → now), 融資/均額, 乖離 (distance above
EMA20), and price/turnover. The exact rule string shown in the UI is **derived**
from the config — change a number in `config.py` and it updates everywhere.

## Data sources

| Source | Used for |
|---|---|
| TWSE `MI_INDEX` | stock names, codes, whole-market turnover |
| TWSE `MI_QFIIS` | 發行股數 (issued shares → market cap, holding %) |
| TWSE `T86` | 三大法人 daily net buys (投信 holding change) |
| TWSE `MI_MARGN` | 融資今日餘額 (margin balance → 融資/均額) |
| Yahoo Finance (`yfinance`) | 6-month daily OHLCV price history |
| 富邦 e-broker | current 投信持股 (張) |

## Quick start

```bash
pip install -r requirements.txt
python -m screener            # writes web/data.json, prints a text report
python -m screener --no-write # dry run: print only, don't touch data.json

# preview the dashboard locally
python -m http.server -d web 8000   # then open http://localhost:8000/
```

Run the tests with:

```bash
pip install -r requirements-dev.txt
pytest
```

## Deploy (GitHub Pages)

The [`daily-scan.yml`](.github/workflows/daily-scan.yml) workflow runs on a
weekday schedule (and on-demand via *Actions → Run workflow*). It runs the
screener and commits `web/data.json` using the built-in `GITHUB_TOKEN` — no
manual credentials.

One-time setup: **Settings → Pages → Build and deployment → Deploy from a
branch → `<default branch>` / `root`**. The dashboard is then served at:

```
https://<user>.github.io/<repo>/web/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for local development and deployment
details (including the note on running TWSE/富邦 fetches from CI).

## Project layout

```
screener/          Python screening engine (python -m screener)
  config.py        all thresholds + the single rule definition
  schema.py        the data.json contract (dataclasses)
  screening.py     pure screening logic (unit-tested)
  trust.py         投信% start→now
  sources/         one module per data provider (twse / prices / fubon)
  cache.py         T86 on-disk cache
  export.py        data.json writer + text report
web/               static dashboard (index.html) + generated data.json
data/t86/          T86 cache (git-ignored, CI-cached)
tests/             pytest suite (no network)
.github/workflows/ scheduled scan + publish
```
