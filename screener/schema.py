"""The data contract between the Python producer and the JS consumer.

``web/data.json`` is the only interface the web UI sees. These dataclasses ARE
that contract: the field list here is mirrored in ``SCHEMA.md`` and consumed by
``web/index.html``. Because the producer builds a typed record (rather than an
ad-hoc dict), it can no longer silently omit a field the UI relies on — which is
how the original script drifted out of sync with the deployed dashboard.

Field order below is intentional: it matches the deployed ``data.json`` so a
regenerated file diffs cleanly against the live one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class StockRecord:
    code: str                 # TWSE 4-digit code, e.g. "2344"
    name: str                 # Chinese name, e.g. "華邦電"
    close: float              # latest close price (NTD)
    mktcap_b: float           # market cap in billions NTD (0 if shares unknown)
    start_date: str           # 起漲日, "MM/DD"
    streak: int               # consecutive days of EMA alignment
    rise_pct: float           # % change from start price to latest close
    avg_wk: float             # average weekly return (%) over the streak
    dist20: float             # % distance of close above EMA20 (乖離)
    turnover_m: float         # N-day average turnover in millions NTD
    trust_start: Optional[float] = None          # 投信 holding % at 起漲日
    trust_now: Optional[float] = None            # 投信 holding % now
    margin_pct_turnover: Optional[float] = None  # 融資餘額 / 均額 (%)
    tier: int = 1             # 1=剛起漲, 2=中段加速, 3=長線主升

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    date: str                          # trade date, "YYYYMMDD"
    updated: str                       # run timestamp, "YYYY-MM-DD HH:MM"
    rules: str                         # derived from ScreeningConfig.rules_text()
    market_turnover_total: int         # whole-market turnover (NTD)
    market_turnover_total_b: float     # = market_turnover_total / 1e8 (億)
    margin_date: Optional[str]         # date of the 融資 data, "YYYYMMDD" or None
    stocks: List[StockRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "updated": self.updated,
            "rules": self.rules,
            "market_turnover_total": self.market_turnover_total,
            "market_turnover_total_b": self.market_turnover_total_b,
            "margin_date": self.margin_date,
            "stocks": [s.to_dict() for s in self.stocks],
        }
