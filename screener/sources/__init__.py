"""External data sources for the screener.

Each module wraps one provider so a failure is isolated to that source:

* :mod:`screener.sources.twse`   — TWSE open-data JSON (names, market turnover,
  issued shares, T86 三大法人, 融資 margin).
* :mod:`screener.sources.prices` — yfinance bulk OHLCV download.
* :mod:`screener.sources.fubon`  — current 投信持股 scraped from 富邦 (big5 HTML).
"""
