# Architecture

How the screener is put together, and *why* the screening logic works the way
it does. For the output format see [SCHEMA.md](SCHEMA.md); for the rules in
plain language see the [README](README.md).

## Pipeline

```
python -m screener
        │
        ▼
  screener/__main__.run()
        │
        ├─ sources.twse.fetch_market()    → trade_date, names, codes, market turnover (MI_INDEX)
        ├─ sources.twse.fetch_shares()    → 發行股數 per code           (MI_QFIIS, walks back ≤7d)
        ├─ sources.prices.download()      → 6-month daily OHLCV         (yfinance, bulk)
        ├─ screening.screen_universe()    → matches (EMA/turnover/streak/weekly/mktcap filters)
        ├─ trust.compute_trust()          → trust_start / trust_now %   (T86 cache + 富邦)
        ├─ sources.twse.fetch_margin()    → 融資今日餘額 per code        (MI_MARGN, walks back ≤7d)
        │
        ├─ build StockRecord[] + ScanResult  (schema.py)   ← the data contract
        ├─ export.write_json()            → web/data.json
        └─ export.format_report()         → text report on stdout
```

Deployment is **not** part of the screener. `run()` only writes the local
`web/data.json`; the GitHub Actions workflow commits it and Pages serves it.
This is a deliberate split — *compute* and *publish* are separate concerns
(and it removes the old in-script GitHub-token push).

## Modules

| Module | Responsibility |
|---|---|
| `config.py` | `ScreeningConfig` — every threshold + `rules_text()` (the single rule definition) |
| `schema.py` | `StockRecord` / `ScanResult` dataclasses — the `data.json` contract |
| `screening.py` | pure helpers (`streak_len`, `weekly_avg_pct`, `dist_pct`, `assign_tier`) + `screen_one`/`screen_universe` |
| `trust.py` | 投信持股 % at 起漲日 vs now, from T86 net-buys + current 富邦 holding |
| `cache.py` | `T86Cache` — per-date JSON cache for 三大法人 data |
| `export.py` | `write_json` + the grouped text report |
| `sources/twse.py` | TWSE JSON endpoints (market, shares, T86, margin) |
| `sources/prices.py` | yfinance bulk download |
| `sources/fubon.py` | current 投信持股 scraper (big5 HTML) |
| `__main__.py` | CLI + orchestration (`run()`) |

The pure helpers in `screening.py` carry the testable logic and need no network;
`tests/` covers them plus a synthetic `screen_one` happy/reject path.

## Why the screening rules

* **EMA alignment (`5EMA > 20EMA > 60EMA`).** Short-, medium-, and long-term
  exponential moving averages stacked in that order is a classic confirmation
  that price is trending up across time-frames. Requiring it for
  `min_align_days` (5) trailing days filters out one-day noise. `streak` counts
  how long the alignment has held; the first day of the streak is 起漲日.
* **Weekly-avg return > 2%.** `mean(daily % change over the streak) × 5`. Keeps
  only trends with real momentum, not slow grinds.
* **Turnover floor (30-day avg > 2,000M).** Liquidity gate — avoids thin stocks
  you can’t actually trade.
* **Market-cap floor (> 100B).** Size gate. Stocks with unknown share count
  (`mktcap_b == 0`) are *kept* rather than dropped (matches the original).
* **Tiers (30 / 90 days).** Group by how fresh the trend is so 剛起漲 vs
  長線主升 are visually separated.

All thresholds live in `config.py`; the human rule string is derived from them,
so they can’t drift apart.

## 投信 (trust) holding calculation

`trust_now` comes from 富邦’s current 投信持股 (張 → ×1000 shares), divided by
發行股數. `trust_start` works backwards: subtract the cumulative T86 投信
net-buys over the streak from the current holding, giving the holding as it was
on 起漲日. The intent is to show whether 投信 accumulated *into* the move.

T86 is fetched one trading day at a time and **cached** to `data/t86/` (the TWSE
endpoint is throttled with `t86_sleep`, default 3.5s). The cache is what makes
daily runs cheap; it’s git-ignored and persisted across CI runs via
`actions/cache`.

## 融資/均額 (margin / turnover)

`margin_pct_turnover` = 融資今日餘額 (NTD) ÷ 30-day average turnover. A value
over 100% means the outstanding margin position exceeds a typical day’s trading
value — the dashboard flags that in red as a crowding/risk signal. See
[SCHEMA.md](SCHEMA.md) for the exact formula.

## Data-source notes & fragility

* **TWSE `rwd` JSON** is public but undocumented; field *positions* matter
  (e.g. T86 投信淨買 is column 10, MI_MARGN 融資今日餘額 is the first `今日餘額`).
  `twse.py` resolves columns by header name where possible and falls back to the
  observed index.
* **yfinance** is the price backbone; a total failure here is fatal (the run
  exits non-zero rather than publishing an empty list). `auto_adjust=False`
  keeps `close` as the raw 收盤價.
* **富邦 scraping** is the most brittle source (big5-encoded HTML parsed by
  regex). Failures are swallowed per-stock, so 投信 fields just become `null`.

## Error handling

Each data source isolates its own failures so one flaky source degrades a field
(→ `null`) instead of crashing the run. The top-level `main()` wraps everything
and exits non-zero on a fatal error, so CI turns red and the published
`data.json` is left untouched.
