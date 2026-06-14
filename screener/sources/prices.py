"""Price history via yfinance."""

from __future__ import annotations

import logging
from typing import List

log = logging.getLogger(__name__)


def download(codes: List[str], period: str = "6mo", interval: str = "1d"):
    """Bulk-download daily OHLCV for ``codes`` (TWSE ``.TW`` suffix added here).

    Returns the raw multi-indexed yfinance DataFrame. Raises if yfinance itself
    fails — price data is the screener's backbone, so a total failure here is
    fatal (the run should exit non-zero rather than publish an empty list).
    """
    import yfinance as yf

    tickers = " ".join(f"{c}.TW" for c in codes)
    log.info("yfinance 下載 %d 檔 (%s)...", len(codes), period)
    # auto_adjust=False keeps `Close` as the raw closing price (TWSE 收盤價),
    # matching what the dashboard displays and the TWSE turnover figures.
    return yf.download(
        tickers, period=period, interval=interval,
        progress=False, threads=True, auto_adjust=False,
    )
