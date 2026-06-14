"""台股篩選 (Taiwan-stock momentum screener).

A daily screener that finds stocks in a confirmed EMA up-trend and exports the
result to ``web/data.json`` for the static GitHub Pages dashboard.

Entry point: ``python -m screener`` (see ``screener.__main__``).
"""

from .config import ScreeningConfig
from .schema import StockRecord, ScanResult

__all__ = ["ScreeningConfig", "StockRecord", "ScanResult"]
