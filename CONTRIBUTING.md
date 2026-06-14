# Contributing / Development

A small, single-maintainer project. This is the practical guide to running it,
changing it, and deploying it.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # runtime deps + pytest
```

## Run locally

```bash
python -m screener              # full scan → writes web/data.json + prints report
python -m screener --no-write   # dry run (print only)
python -m screener --quiet      # suppress progress logs (errors only)
```

First run is slow: with an empty `data/t86/` cache the screener fetches the
三大法人 history one day at a time (throttled, ~3.5s/day). Subsequent runs reuse
the cache and are fast.

Preview the dashboard against the generated data:

```bash
python -m http.server -d web 8000   # open http://localhost:8000/
```

## Tests

```bash
pytest
```

Tests are network-free (they cover the pure screening helpers, a synthetic
`screen_one` path, and the schema/rules contract). Keep new business logic in
pure functions in `screening.py` so it stays testable.

## Common changes

* **Tune a threshold / rule** — edit one value in
  [`screener/config.py`](screener/config.py). The rule string in the UI and the
  text report update automatically (`rules_text()`). The deployed predecessor
  used `min_turnover=3e9` and `min_trust_rise=0.1`; both are one-line changes here.
* **Add a field to `data.json`** — add it to `StockRecord`/`ScanResult` in
  `screener/schema.py`, populate it in `__main__.run()`, document it in
  [SCHEMA.md](SCHEMA.md), and add it to `REQUIRED_FIELDS` (or treat as optional)
  in `web/index.html`. Update all three together — see SCHEMA.md’s versioning note.
* **Add/replace a data source** — add a module under `screener/sources/`,
  isolate its failures (return empty/partial; don’t raise unless it’s essential
  like prices), and wire it into `run()`.

## Deploy

[`/.github/workflows/daily-scan.yml`](.github/workflows/daily-scan.yml) runs on a
weekday cron (and manual *Run workflow*), executes `python -m screener`, and
commits `web/data.json` with the built-in `GITHUB_TOKEN` (`permissions:
contents: write`). No manual credentials — the old `/tmp/git-creds.txt` token
hack is gone.

One-time GitHub Pages setup: **Settings → Pages → Deploy from a branch →
`<default branch>` / `root`**. Dashboard URL: `https://<user>.github.io/<repo>/web/`.

The publish step keeps the **last-good** `data.json` if a scan returns zero
stocks, and only commits when the file actually changed.

### Running fetches from CI

GitHub-hosted runners are US-based; the TWSE / 富邦 endpoints occasionally
rate-limit or geo-block them. Mitigations already in place: the workflow caches
`data/t86/`, supports manual dispatch, and never overwrites a good `data.json`
with an empty result. If the endpoints become unreachable from GitHub’s
runners, switch the job to a **self-hosted runner in Taiwan** (only the
`runs-on:` line changes). `yfinance` (Yahoo) is unaffected.

## Gotchas

* `data/t86/*.json` is git-ignored — it’s a regenerable cache, not source.
* `web/data.json` **is** committed — GitHub Pages serves it statically.
* The 富邦 scraper is the most fragile piece; if 投信 columns shift, check the
  `cells[-5]` index in `screener/sources/fubon.py`.
