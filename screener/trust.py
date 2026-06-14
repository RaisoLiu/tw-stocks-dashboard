"""投信 (investment-trust) holding %, 起漲日 → now.

Combines two sources:

* T86 (三大法人 daily net buys) accumulated over the streak — how many shares
  投信 net-bought from 起漲日 to now.
* Current 投信持股 (張) from 富邦 — the holding *now*.

Working backwards: ``start_holding = now_holding - cumulative_net_buys``. Both
are divided by issued shares to get a percentage.

The fetch functions are injected so this module stays free of network code and
is easy to test.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List, Tuple

from .cache import T86Cache

log = logging.getLogger(__name__)


def compute_trust(
    records: List[dict],
    shares_map: Dict[str, int],
    t86_cache: T86Cache,
    fetch_t86: Callable[[str], Dict[str, int]],
    fetch_current_trust: Callable[[List[str]], Dict[str, int]],
    t86_sleep: float = 3.5,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Return ``(trust_start_pct, trust_now_pct)`` keyed by stock code."""
    # 1. Load every needed trading date from cache; fetch the misses (throttled).
    needed_dates = sorted({d for r in records for d in r["trading_dates"]})
    t86_by_date: Dict[str, Dict[str, int]] = {}
    missing = []
    for d in needed_dates:
        cached = t86_cache.get(d)
        if cached is not None:
            t86_by_date[d] = cached
        else:
            missing.append(d)

    if missing:
        log.info("抓取 %d 個缺少的 T86 交易日...", len(missing))
        for i, d in enumerate(missing, 1):
            try:
                data = fetch_t86(d)
            except Exception as exc:  # noqa: BLE001 — one date failing is non-fatal
                log.warning("T86 %s 抓取失敗: %s", d, exc)
                data = {}
            t86_by_date[d] = data
            t86_cache.put(d, data)
            if i % 10 == 0:
                log.info("  ... T86 %d/%d", i, len(missing))
            time.sleep(t86_sleep)

    # 2. Current holding (張) from 富邦.
    codes = [r["code"] for r in records]
    current_k = fetch_current_trust(codes)

    # 3. Derive start % and now %.
    trust_start: Dict[str, float] = {}
    trust_now: Dict[str, float] = {}
    for r in records:
        code = r["code"]
        total_shares = shares_map.get(code, 0)
        if code not in current_k or total_shares == 0:
            continue
        now_shares = current_k[code] * 1000  # 張 → 股
        cum_net = sum(t86_by_date.get(d, {}).get(code, 0) for d in r["trading_dates"])
        start_shares = max(now_shares - cum_net, 0)
        trust_now[code] = round(now_shares / total_shares * 100, 1)
        trust_start[code] = round(start_shares / total_shares * 100, 1)
    return trust_start, trust_now
