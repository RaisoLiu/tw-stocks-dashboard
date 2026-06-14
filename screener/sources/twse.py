"""TWSE open-data JSON endpoints.

All endpoints are public ``https://www.twse.com.tw/rwd/...`` JSON APIs. Each
fetch isolates its own failure: callers get an empty/partial result and the run
degrades (a field becomes null) rather than crashing.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0"
_BASE = "https://www.twse.com.tw/rwd/zh"


def _fetch_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _walk_back(ref_date_str: str, days: int = 7):
    """Yield YYYYMMDD strings starting at ref_date, walking back ``days`` days."""
    try:
        ref = datetime.strptime(str(ref_date_str), "%Y%m%d")
    except (ValueError, TypeError):
        ref = datetime.now()
    for delta in range(days):
        yield (ref - timedelta(days=delta)).strftime("%Y%m%d")


def fetch_market() -> Tuple[str, Dict[str, str], List[str], int]:
    """MI_INDEX (每日收盤行情).

    Returns ``(trade_date, namemap, codes, market_turnover_total)`` where
    ``market_turnover_total`` is the summed 成交金額 across the whole market (NTD).
    """
    data = _fetch_json(f"{_BASE}/afterTrading/MI_INDEX?response=json&type=ALLBUT0999")
    namemap: Dict[str, str] = {}
    codes: List[str] = []
    market_turnover_total = 0

    for table in data.get("tables", []):
        if "每日收盤行情" not in table.get("title", ""):
            continue
        fields = table.get("fields", [])
        try:
            amount_idx = fields.index("成交金額")
        except ValueError:
            amount_idx = 4  # observed position; fall back defensively
        for row in table.get("data", []):
            code = row[0].strip()
            namemap[code] = row[1].strip()
            if len(code) == 4 and code.isdigit():
                codes.append(code)
            try:
                market_turnover_total += int(row[amount_idx].replace(",", ""))
            except (ValueError, IndexError):
                pass
        break

    trade_date = data.get("date", "?")
    log.info("市場資料: %s (%d 檔, 總成交額 %.0f 億)", trade_date, len(codes), market_turnover_total / 1e8)
    return trade_date, namemap, codes, market_turnover_total


def fetch_shares(trade_date: str) -> Tuple[Dict[str, int], Optional[str]]:
    """MI_QFIIS 發行股數. Returns ``({code: issued_shares}, source_date)``.

    Walks back up to 7 days from ``trade_date`` to find a day with data.
    """
    for d in _walk_back(trade_date):
        try:
            data = _fetch_json(f"{_BASE}/fund/MI_QFIIS?date={d}&selectType=ALLBUT0999&response=json")
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            log.debug("MI_QFIIS %s failed: %s", d, exc)
            continue
        if data.get("data"):
            shares: Dict[str, int] = {}
            for row in data["data"]:
                try:
                    shares[row[0].strip()] = int(row[3].replace(",", ""))
                except (ValueError, IndexError):
                    pass
            log.info("發行股數資料來源: %s (%d 檔)", d, len(shares))
            return shares, d
    log.warning("找不到發行股數資料")
    return {}, None


def fetch_t86(date_str: str) -> Dict[str, int]:
    """T86 三大法人買賣超. Returns ``{code: 投信買賣超股數}`` for one date."""
    data = _fetch_json(f"{_BASE}/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999")
    result: Dict[str, int] = {}
    for row in data.get("data", []):
        try:
            result[row[0].strip()] = int(row[10].replace(",", ""))  # 投信買賣超股數
        except (ValueError, IndexError):
            pass
    return result


def fetch_margin(trade_date: str) -> Tuple[Dict[str, int], Optional[str]]:
    """MI_MARGN 融資融券彙總. Returns ``({code: 融資今日餘額(張)}, source_date)``.

    The per-stock table lists 融資 first; ``今日餘額`` therefore appears at the
    融資 position (the first occurrence), which is exactly what we want.
    """
    for d in _walk_back(trade_date):
        try:
            data = _fetch_json(f"{_BASE}/marginTrading/MI_MARGN?date={d}&selectType=ALL&response=json")
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            log.debug("MI_MARGN %s failed: %s", d, exc)
            continue
        balances: Dict[str, int] = {}
        for table in data.get("tables", []):
            fields = table.get("fields", [])
            if "代號" not in fields or "今日餘額" not in fields:
                continue
            balance_idx = fields.index("今日餘額")  # first = 融資今日餘額
            for row in table.get("data", []):
                try:
                    balances[row[0].strip()] = int(row[balance_idx].replace(",", ""))
                except (ValueError, IndexError):
                    pass
            break
        if balances:
            log.info("融資資料來源: %s (%d 檔)", d, len(balances))
            return balances, d
    log.warning("找不到融資資料")
    return {}, None
