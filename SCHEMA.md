# `web/data.json` — Data Contract

`web/data.json` is the **only** interface between the Python screener (producer)
and the web dashboard (consumer). This document is the source of truth for its
shape; it mirrors [`screener/schema.py`](screener/schema.py) (producer) and the
`REQUIRED_FIELDS` / rendering in [`web/index.html`](web/index.html) (consumer).

> **Why this file exists.** In the original project the producer and the
> deployed UI drifted apart: the committed script emitted 11 stock fields, but
> the live dashboard read 14 — `close`, `margin_pct_turnover`,
> `market_turnover_total_b`, and `margin_date` were consumed but never produced,
> so the UI silently showed “—”. The screener now builds a typed
> `StockRecord` / `ScanResult`, the UI validates against the field list on load,
> and this document keeps both honest.

## Root object

| Field | Type | Null? | Unit / format | Meaning |
|---|---|---|---|---|
| `date` | string | no | `YYYYMMDD` | TWSE trade date |
| `updated` | string | no | `YYYY-MM-DD HH:MM` | when the scan ran |
| `rules` | string | no | — | human rule string, **derived** from `ScreeningConfig.rules_text()` |
| `market_turnover_total` | integer | no | NTD | whole-market turnover (Σ 成交金額) |
| `market_turnover_total_b` | number | no | 億 (1e8 NTD) | `= market_turnover_total / 1e8` |
| `margin_date` | string | yes | `YYYYMMDD` | date of the 融資 (MI_MARGN) data; `null` if unavailable |
| `stocks` | array | no | — | list of stock records (below), sorted by `streak` ascending |

## Stock record (each item of `stocks[]`)

Field order below matches the JSON output exactly.

| Field | Type | Null? | Unit | Meaning |
|---|---|---|---|---|
| `code` | string | no | — | TWSE 4-digit code, e.g. `"2344"` |
| `name` | string | no | — | Chinese name, e.g. `"華邦電"` |
| `close` | number | no | NTD | latest close (raw 收盤價) |
| `mktcap_b` | number | no | 十億 (1e9 NTD) | market cap; `0` when issued shares unknown |
| `start_date` | string | no | `MM/DD` | 起漲日 (first day of the current alignment streak) |
| `streak` | integer | no | days | consecutive days of `5EMA>20EMA>60EMA` |
| `rise_pct` | number | no | % | price change from 起漲日 to now |
| `avg_wk` | number | no | % | average weekly return over the streak |
| `dist20` | number | no | % | 乖離 — distance of close above EMA20 |
| `turnover_m` | number | no | 百萬 (1e6 NTD) | 30-day average daily turnover |
| `trust_start` | number | **yes** | % | 投信持股 % at 起漲日 |
| `trust_now` | number | **yes** | % | 投信持股 % now |
| `margin_pct_turnover` | number | **yes** | % | 融資餘額 ÷ 均額 |
| `tier` | integer | no | 1/2/3 | 1 = 剛起漲 (<1mo), 2 = 中段加速 (1–3mo), 3 = 長線主升 (>3mo) |

Nullable fields become `null` when their (more fragile) source fails — the UI
renders `—` and keeps working. Required fields are asserted by
`validateSchema()` in the dashboard, which logs a console warning on any
missing/null required field.

## Derived-field formulas (verified)

These reproduce the previously-deployed values **exactly** (verified against the
live TWSE endpoints for 2026-05-19):

* **`market_turnover_total`** = Σ of the `成交金額` column over every row of the
  TWSE `MI_INDEX` 每日收盤行情 table.
  `market_turnover_total_b = round(market_turnover_total / 1e8, 1)`.
  _Example: `1,146,995,450,622 → 11470.0`._

* **`margin_pct_turnover`** = `融資今日餘額(張) × 1000 × close / (turnover_m × 1e6) × 100`,
  where `融資今日餘額` is the first `今日餘額` column of TWSE `MI_MARGN`.
  _Example: 2344 — `143,937 × 1000 × 117.5 / (19,631 × 1e6) × 100 = 86.15`._

* **`trust_now`** = `current 投信持股(張, 富邦) × 1000 / 發行股數 × 100`.
  **`trust_start`** = `(current 投信股數 − Σ T86 投信淨買 over the streak) / 發行股數 × 100`.

## Versioning

When you add or change a field: update `screener/schema.py`, this table, and
`REQUIRED_FIELDS` in `web/index.html` together — they are one contract in three
places, and the UI’s load-time validation will flag any divergence.
