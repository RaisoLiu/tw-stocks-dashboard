"""Unit tests for the pure screening helpers (no network)."""

from datetime import datetime

import pytest

from screener.config import ScreeningConfig
from screener.screening import (
    assign_tier,
    dist_pct,
    screen_one,
    streak_len,
    to_naive,
    weekly_avg_pct,
)


# --------------------------------------------------------------------------- #
# streak_len                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("mask,expected", [
    ([], 0),
    ([True], 1),
    ([False], 0),
    ([True, True, True], 3),
    ([False, True, True], 2),     # only the trailing run counts
    ([True, True, False], 0),     # broken at the end
    ([True, False, True, True], 2),
])
def test_streak_len(mask, expected):
    assert streak_len(mask) == expected


# --------------------------------------------------------------------------- #
# weekly_avg_pct                                                               #
# --------------------------------------------------------------------------- #
def test_weekly_avg_pct_basic():
    # single +2% step -> mean daily 2% * 5 * 100 = 10.0
    assert weekly_avg_pct([100, 102]) == pytest.approx(10.0)


def test_weekly_avg_pct_constant_growth():
    # +1% per day -> 1% * 5 * 100 = 5.0
    prices = [100 * 1.01 ** i for i in range(6)]
    assert weekly_avg_pct(prices) == pytest.approx(5.0, abs=1e-6)


@pytest.mark.parametrize("prices", [[], [100]])
def test_weekly_avg_pct_too_short(prices):
    assert weekly_avg_pct(prices) is None


def test_weekly_avg_pct_handles_zero_baseline():
    # a zero price must not raise (it's skipped)
    assert weekly_avg_pct([0, 100, 110]) is not None


# --------------------------------------------------------------------------- #
# dist_pct                                                                     #
# --------------------------------------------------------------------------- #
def test_dist_pct():
    assert dist_pct(110, 100) == pytest.approx(10.0)
    assert dist_pct(95, 100) == pytest.approx(-5.0)


# --------------------------------------------------------------------------- #
# assign_tier (boundaries inclusive on the recent side, matching original)     #
# --------------------------------------------------------------------------- #
def _days_before(ref, n):
    from datetime import timedelta
    return ref - timedelta(days=n)


def test_assign_tier_boundaries():
    ref = datetime(2026, 5, 19)
    assert assign_tier(_days_before(ref, 10), ref) == 1
    assert assign_tier(_days_before(ref, 30), ref) == 1     # inclusive
    assert assign_tier(_days_before(ref, 31), ref) == 2
    assert assign_tier(_days_before(ref, 90), ref) == 2     # inclusive
    assert assign_tier(_days_before(ref, 91), ref) == 3


def test_assign_tier_custom_cutoffs():
    ref = datetime(2026, 5, 19)
    assert assign_tier(_days_before(ref, 5), ref, tier_days=(7, 14)) == 1
    assert assign_tier(_days_before(ref, 10), ref, tier_days=(7, 14)) == 2
    assert assign_tier(_days_before(ref, 20), ref, tier_days=(7, 14)) == 3


# --------------------------------------------------------------------------- #
# to_naive                                                                     #
# --------------------------------------------------------------------------- #
def test_to_naive_strips_tz():
    pd = pytest.importorskip("pandas")
    ts = pd.Timestamp("2026-05-19", tz="Asia/Taipei")
    out = to_naive(ts)
    assert out.tzinfo is None
    assert (out.year, out.month, out.day) == (2026, 5, 19)


# --------------------------------------------------------------------------- #
# screen_one (synthetic frame, still no network)                               #
# --------------------------------------------------------------------------- #
def _uptrend_df(rows=80, start=100.0, end=200.0, volume=2e7):
    pd = pytest.importorskip("pandas")
    idx = pd.date_range("2026-01-01", periods=rows, freq="D")
    close = [start + (end - start) * i / (rows - 1) for i in range(rows)]
    return pd.DataFrame({"Close": close, "Volume": [volume] * rows}, index=idx)


def test_screen_one_accepts_clean_uptrend():
    cfg = ScreeningConfig()
    df = _uptrend_df()
    rec = screen_one(df, "9999", "測試", shares=10**9, config=cfg)
    assert rec is not None
    assert rec["code"] == "9999"
    assert rec["streak"] >= cfg.min_align_days
    assert rec["avg_wk"] > cfg.min_weekly_pct
    assert rec["mktcap_b"] >= cfg.min_mktcap_b
    assert rec["trading_dates"]              # non-empty
    assert rec["close"] == pytest.approx(200.0)


def test_screen_one_rejects_low_turnover():
    cfg = ScreeningConfig()
    df = _uptrend_df(volume=1)  # turnover ~ 200 NTD, far below the floor
    assert screen_one(df, "9999", "測試", shares=10**9, config=cfg) is None


def test_screen_one_rejects_short_history():
    cfg = ScreeningConfig()
    df = _uptrend_df(rows=40)   # < min_history_rows
    assert screen_one(df, "9999", "測試", shares=10**9, config=cfg) is None


def test_screen_one_rejects_downtrend():
    cfg = ScreeningConfig()
    df = _uptrend_df(start=200.0, end=100.0)  # EMAs never align upward
    assert screen_one(df, "9999", "測試", shares=10**9, config=cfg) is None


def test_screen_one_rejects_low_price():
    cfg = ScreeningConfig()
    # close ends at 90 (≤ min_price 100); the higher volume keeps it above the
    # turnover floor so ONLY the price gate can reject it.
    df = _uptrend_df(start=50.0, end=90.0, volume=3e7)
    assert screen_one(df, "9999", "測試", shares=10**9, config=cfg) is None
