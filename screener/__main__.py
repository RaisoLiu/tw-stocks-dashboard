"""CLI entry point: ``python -m screener``.

Orchestrates: fetch market → fetch shares → download prices → screen →
compute 投信% → compute 融資/均額 → build the typed :class:`ScanResult` →
write ``web/data.json`` and print the text report.

Deployment is intentionally NOT done here. The screener only writes the local
``data.json``; publishing to GitHub Pages is the CI workflow's job (see
``.github/workflows/daily-scan.yml``). This removes the old ``/tmp`` token hack.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime

from .cache import T86Cache
from .config import ScreeningConfig
from .export import format_report, write_json
from .schema import ScanResult, StockRecord
from . import screening
from . import trust as trust_mod
from .sources import fubon, prices, twse

log = logging.getLogger("screener")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DATA_PATH = os.path.join(_REPO_ROOT, "web", "data.json")
T86_CACHE_DIR = os.path.join(_REPO_ROOT, "data", "t86")


def _margin_pct_turnover(balance_zhang, close, turnover_m):
    """融資餘額 / 均額 (%).

    ``balance_zhang`` is 融資今日餘額 in 張 (1,000 shares); ``turnover_m`` is the
    average turnover in millions NTD. Verified to reproduce the deployed values
    exactly (see SCHEMA.md).
    """
    if balance_zhang is None or not turnover_m:
        return None
    return round(balance_zhang * 1000 * close / (turnover_m * 1e6) * 100, 2)


def run(config: ScreeningConfig | None = None, write: bool = True):
    """Run a full scan. Returns ``(ScanResult, report_text)``."""
    config = config or ScreeningConfig()

    log.info("⏳ 下載市場資料...")
    trade_date, namemap, codes, market_turnover_total = twse.fetch_market()

    log.info("⏳ 下載發行股數...")
    shares_map, _ = twse.fetch_shares(trade_date)

    log.info("⏳ 下載價格資料 (yfinance)...")
    price_data = prices.download(codes, period=config.history)

    log.info("⏳ 篩選中...")
    records = screening.screen_universe(price_data, codes, namemap, shares_map, config)

    log.info("⏳ 計算投信持股比率...")
    trust_start, trust_now = trust_mod.compute_trust(
        records, shares_map, T86Cache(T86_CACHE_DIR),
        twse.fetch_t86, fubon.fetch_current_trust, config.t86_sleep,
    )

    log.info("⏳ 下載融資資料...")
    margin_balance, margin_date = twse.fetch_margin(trade_date)

    try:
        ref_date = datetime.strptime(str(trade_date), "%Y%m%d")
    except (ValueError, TypeError):
        ref_date = datetime.now()

    records.sort(key=lambda r: r["streak"])
    stocks = []
    for r in records:
        code = r["code"]
        rise = trust_now.get(code, 0) - trust_start.get(code, 0) if code in trust_now else None
        if config.min_trust_rise is not None and (rise is None or rise < config.min_trust_rise):
            continue
        stocks.append(StockRecord(
            code=code,
            name=r["name"],
            close=r["close"],
            mktcap_b=r["mktcap_b"],
            start_date=r["start_date"],
            streak=r["streak"],
            rise_pct=r["rise_pct"],
            avg_wk=r["avg_wk"],
            dist20=r["dist20"],
            turnover_m=r["turnover_m"],
            trust_start=trust_start.get(code),
            trust_now=trust_now.get(code),
            margin_pct_turnover=_margin_pct_turnover(margin_balance.get(code), r["close"], r["turnover_m"]),
            tier=screening.assign_tier(screening.to_naive(r["start_date_dt"]), ref_date, config.tier_days),
        ))

    result = ScanResult(
        date=str(trade_date),
        updated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        rules=config.rules_text(),
        market_turnover_total=market_turnover_total,
        market_turnover_total_b=round(market_turnover_total / 1e8, 1),
        margin_date=margin_date,
        stocks=stocks,
    )

    report = format_report(result)
    if write:
        write_json(result, WEB_DATA_PATH)
        log.info("✅ 已寫入 %s (%d 檔)", WEB_DATA_PATH, len(stocks))
    return result, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m screener", description="台股篩選每日掃描")
    parser.add_argument("--no-write", action="store_true", help="不要寫入 web/data.json（僅印出報告）")
    parser.add_argument("--quiet", action="store_true", help="只印錯誤（隱藏進度訊息）")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.ERROR if args.quiet else logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )

    try:
        _, report = run(write=not args.no_write)
    except Exception as exc:  # noqa: BLE001 — top-level guard; exit non-zero for CI
        log.error("❌ 掃描失敗: %s", exc, exc_info=True)
        return 1

    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
