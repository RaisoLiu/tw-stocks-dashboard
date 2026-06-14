"""Tests for the data contract (schema dataclasses) and rule-string derivation."""

from screener.config import ScreeningConfig
from screener.schema import ScanResult, StockRecord

# The exact field set + order the deployed web/data.json (and the UI) expect.
EXPECTED_STOCK_KEYS = [
    "code", "name", "close", "mktcap_b", "start_date", "streak", "rise_pct",
    "avg_wk", "dist20", "turnover_m", "trust_start", "trust_now",
    "margin_pct_turnover", "tier",
]
EXPECTED_ROOT_KEYS = [
    "date", "updated", "rules", "market_turnover_total",
    "market_turnover_total_b", "margin_date", "stocks",
]


def _sample_stock():
    return StockRecord(
        code="2344", name="華邦電", close=117.5, mktcap_b=529.0, start_date="05/08",
        streak=8, rise_pct=3.1, avg_wk=7.8, dist20=5.4, turnover_m=19631.0,
        trust_start=5.5, trust_now=7.2, margin_pct_turnover=86.15, tier=1,
    )


def test_stock_record_keys_and_order():
    assert list(_sample_stock().to_dict().keys()) == EXPECTED_STOCK_KEYS


def test_stock_record_optional_fields_default_none():
    s = StockRecord(
        code="1234", name="X", close=10.0, mktcap_b=0, start_date="01/01",
        streak=5, rise_pct=1.0, avg_wk=3.0, dist20=2.0, turnover_m=5000.0,
    )
    d = s.to_dict()
    assert d["trust_start"] is None
    assert d["trust_now"] is None
    assert d["margin_pct_turnover"] is None
    assert d["tier"] == 1


def test_scan_result_structure():
    result = ScanResult(
        date="20260519", updated="2026-05-20 04:37",
        rules=ScreeningConfig().rules_text(),
        market_turnover_total=1146995450622, market_turnover_total_b=11470.0,
        margin_date="20260519", stocks=[_sample_stock()],
    )
    d = result.to_dict()
    assert list(d.keys()) == EXPECTED_ROOT_KEYS
    assert isinstance(d["stocks"], list)
    assert d["stocks"][0]["code"] == "2344"
    assert d["market_turnover_total_b"] == 11470.0


def test_rules_text_default():
    assert ScreeningConfig().rules_text() == (
        "5EMA>20EMA>60EMA ≥5日 + 起漲週均>2% + 均額>2000M + 市值>100B"
    )


def test_rules_text_reflects_config_changes():
    cfg = ScreeningConfig(min_turnover=3e9, min_weekly_pct=2.5)
    text = cfg.rules_text()
    assert "均額>3000M" in text
    assert "起漲週均>2.5%" in text


def test_rules_text_includes_trust_filter_when_enabled():
    cfg = ScreeningConfig(min_trust_rise=0.1)
    assert "投信持股上升≥0.1%" in cfg.rules_text()
