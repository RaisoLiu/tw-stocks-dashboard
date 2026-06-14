"""Current 投信持股 (張) scraped from 富邦 e-broker (big5-encoded HTML).

This is the one fragile, best-effort source: it parses an HTML table from
``fubon-ebrokerdj.fbs.com.tw``. Any failure is swallowed per-stock so the run
degrades gracefully (trust % becomes null for that stock) instead of crashing.
"""

from __future__ import annotations

import logging
import re
import subprocess
from typing import Dict, List

log = logging.getLogger(__name__)

_URL = "https://fubon-ebrokerdj.fbs.com.tw/z/zc/zcl/zcl_{code}.djhtm"
_DATE_RE = re.compile(r"1\d{2}/\d{2}/\d{2}")          # ROC date e.g. 115/05/19
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
_CELL_RE = re.compile(r'<td[^>]*class="t3[nt]\d?"[^>]*>([^<]*)')


def fetch_current_trust(codes: List[str], timeout: int = 12) -> Dict[str, int]:
    """Return ``{code: 投信持股(張)}`` for the latest available row per stock.

    The table layout varies (9 or 11 columns), but 投信持股 is reliably the 5th
    cell from the end (``cells[-5]``).
    """
    result: Dict[str, int] = {}
    for code in codes:
        try:
            cmd = f'timeout 8 curl -s "{_URL.format(code=code)}" -H "User-Agent: Mozilla/5.0"'
            proc = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
            text = proc.stdout.decode("big5", errors="replace")
            for row in _ROW_RE.findall(text):
                cells = [c.strip() for c in _CELL_RE.findall(row) if c.strip()]
                if cells and _DATE_RE.match(cells[0]) and len(cells) >= 7:
                    try:
                        result[code] = int(cells[-5].replace(",", ""))
                    except ValueError:
                        pass
                    break
        except (subprocess.SubprocessError, OSError) as exc:
            log.debug("fubon fetch failed for %s: %s", code, exc)
    log.info("投信持股 (富邦): %d/%d 檔取得", len(result), len(codes))
    return result
