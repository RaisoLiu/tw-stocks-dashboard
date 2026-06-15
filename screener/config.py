"""Central configuration — every screening threshold lives here.

This is the single source of truth for the screening rules. The human-readable
rule string shown in the web UI and the text report is *derived* from these
values via :meth:`ScreeningConfig.rules_text`, so a rule change means editing
one number here — not four hand-typed strings that silently drift apart (which
is exactly what happened in the original ``daily_scan.py``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreeningConfig:
    # --- EMA alignment: ema_spans[0] > ema_spans[1] > ema_spans[2] (e.g. 5>20>60) ---
    ema_spans: tuple[int, int, int] = (5, 20, 60)
    min_align_days: int = 5  # alignment must hold for at least this many trailing days

    # --- Momentum: average weekly return must exceed this (percent) ---
    min_weekly_pct: float = 3.0

    # --- Liquidity: N-day average turnover floor (NTD) ---
    turnover_window: int = 30
    min_turnover: float = 2e9  # 2,000M NTD

    # --- Size: market-cap floor (billions NTD = close * issued_shares / 1e9) ---
    # Stocks with unknown share count (mktcap_b == 0) are kept, matching the
    # original behaviour.
    min_mktcap_b: float = 100.0

    # --- Price: latest close must be greater than this (NTD) ---
    min_price: float = 100.0

    # --- Price history pulled from yfinance (needs >= ~60 rows for EMA60) ---
    history: str = "6mo"
    min_history_rows: int = 65

    # --- 投信 (investment-trust) holding: throttle between T86 date fetches ---
    t86_sleep: float = 3.5

    # --- Tier boundaries by 起漲日 (days since the up-trend started) ---
    #   <= tier_days[0] -> tier 1 (剛起漲),
    #   <= tier_days[1] -> tier 2 (中段加速),
    #   else            -> tier 3 (長線主升)
    tier_days: tuple[int, int] = (30, 90)

    # --- Require 投信 holding to have risen by >= this much (percentage points) ---
    # Enabled at 0.1 (matches the last deployed site): keep only names 投信 is
    # accumulating into, 起漲日 → now. Set to None to disable the filter.
    min_trust_rise: float | None = 0.1

    def rules_text(self) -> str:
        """Human-readable rule string — the ONE place it is defined."""
        e5, e20, e60 = self.ema_spans
        parts = [
            f"{e5}EMA>{e20}EMA>{e60}EMA ≥{self.min_align_days}日",
            f"起漲週均>{self.min_weekly_pct:g}%",
            f"均額>{self.min_turnover / 1e6:.0f}M",
            f"市值>{self.min_mktcap_b:.0f}B",
            f"股價>{self.min_price:g}",
        ]
        if self.min_trust_rise is not None:
            parts.append(f"投信持股上升≥{self.min_trust_rise:g}%")
        return " + ".join(parts)
