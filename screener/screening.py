"""Screening logic.

The small, network-free helpers (:func:`streak_len`, :func:`weekly_avg_pct`,
:func:`dist_pct`, :func:`assign_tier`) are pure and unit-tested. The pandas-based
:func:`screen_one` / :func:`screen_universe` wrap them around a price DataFrame.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Pure helpers (no network, no pandas required) — covered by tests/            #
# --------------------------------------------------------------------------- #
def streak_len(mask: Iterable[bool]) -> int:
    """Number of consecutive truthy values at the END of ``mask``."""
    n = 0
    for v in reversed(list(mask)):
        if v:
            n += 1
        else:
            break
    return n


def weekly_avg_pct(prices: Iterable[float], days_per_week: int = 5) -> Optional[float]:
    """Average weekly return (%) = mean daily pct-change * days_per_week * 100."""
    prices = [p for p in prices]
    if len(prices) < 2:
        return None
    rets = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices)) if prices[i - 1]]
    if not rets:
        return None
    return sum(rets) / len(rets) * days_per_week * 100


def dist_pct(value: float, baseline: float) -> float:
    """Percentage distance of ``value`` above ``baseline``."""
    return (value / baseline - 1) * 100


def assign_tier(start_date: datetime, ref_date: datetime, tier_days=(30, 90)) -> int:
    """1 if 起漲日 within tier_days[0], 2 if within tier_days[1], else 3."""
    if start_date >= ref_date - timedelta(days=tier_days[0]):
        return 1
    if start_date >= ref_date - timedelta(days=tier_days[1]):
        return 2
    return 3


def to_naive(dt) -> datetime:
    """Coerce a pandas Timestamp / aware datetime to a naive datetime."""
    if hasattr(dt, "to_pydatetime"):
        dt = dt.to_pydatetime()
    if getattr(dt, "tzinfo", None) is not None:
        dt = dt.replace(tzinfo=None)
    return dt


# --------------------------------------------------------------------------- #
# pandas-based screening                                                       #
# --------------------------------------------------------------------------- #
def alignment_mask(close, spans):
    """Boolean Series: EMA(spans[0]) > EMA(spans[1]) > EMA(spans[2])."""
    e_fast = close.ewm(span=spans[0], adjust=False).mean()
    e_mid = close.ewm(span=spans[1], adjust=False).mean()
    e_slow = close.ewm(span=spans[2], adjust=False).mean()
    return (e_fast > e_mid) & (e_mid > e_slow)


def screen_one(df, code, name, shares, config) -> Optional[dict]:
    """Apply the screening rules to one stock's price history.

    ``df`` must have ``Close`` and ``Volume`` columns (a daily OHLCV frame).
    Returns an intermediate dict (incl. ``start_date_dt`` and ``trading_dates``
    for the trust calc) or ``None`` if the stock fails any rule.
    """
    if len(df) < config.min_history_rows:
        return None

    close_ser = df["Close"]

    # Liquidity filter
    avg_turnover = float((close_ser * df["Volume"]).tail(config.turnover_window).mean())
    if avg_turnover < config.min_turnover:
        return None

    # EMA alignment must hold over the last `min_align_days`
    mask = alignment_mask(close_ser, config.ema_spans)
    if not mask.iloc[-config.min_align_days:].all():
        return None
    streak = streak_len(mask.values)

    close = float(close_ser.iloc[-1])
    if close <= config.min_price:
        return None
    e_mid = float(close_ser.ewm(span=config.ema_spans[1], adjust=False).mean().iloc[-1])
    dist20 = round(dist_pct(close, e_mid), 1)

    start_idx = max(len(df) - streak, 0)
    avg_wk = weekly_avg_pct(close_ser.iloc[start_idx:].tolist())
    if avg_wk is None or avg_wk <= config.min_weekly_pct:
        return None

    start_price = float(close_ser.iloc[max(start_idx - 1, 0)])
    start_dt = df.index[start_idx]
    rise_pct = round(dist_pct(close, start_price), 1)
    turnover_m = round(avg_turnover / 1e6, 0)
    trading_dates = [d.strftime("%Y%m%d") for d in df.index[start_idx:]]

    mktcap_b = round(close * shares / 1e9, 0) if shares else 0
    if 0 < mktcap_b < config.min_mktcap_b:
        return None

    return {
        "code": code,
        "name": name,
        "close": close,
        "mktcap_b": mktcap_b,
        "start_date": start_dt.strftime("%m/%d"),
        "start_date_dt": start_dt,
        "streak": streak,
        "rise_pct": rise_pct,
        "avg_wk": round(avg_wk, 2),
        "dist20": dist20,
        "turnover_m": turnover_m,
        "trading_dates": trading_dates,
    }


def screen_universe(price_data, codes, namemap, shares_map, config) -> List[dict]:
    """Screen every code against a yfinance bulk-download frame."""
    import pandas as pd

    results: List[dict] = []
    is_multi = isinstance(price_data.columns, pd.MultiIndex)
    if not is_multi:
        log.warning("price data is not multi-indexed (got %d codes); nothing to screen", len(codes))
        return results

    for code in codes:
        ticker = f"{code}.TW"
        try:
            df = price_data.xs(ticker, level=1, axis=1).dropna(subset=["Close"])
        except KeyError:
            continue
        try:
            rec = screen_one(df, code, namemap.get(code, "?"), shares_map.get(code, 0), config)
        except Exception as exc:  # one bad ticker must not kill the whole run
            log.debug("screen %s failed: %s", code, exc)
            continue
        if rec is not None:
            results.append(rec)
    return results
