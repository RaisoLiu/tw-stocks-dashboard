"""Output: the ``data.json`` writer and the human-readable text report."""

from __future__ import annotations

import json
import logging
import os
from typing import List

from .schema import ScanResult, StockRecord

log = logging.getLogger(__name__)

_TIERS = [
    (1, "🟢", "剛起漲 (<1個月)"),
    (2, "🟡", "中段加速 (1~3個月)"),
    (3, "🔴", "長線主升 (>3個月)"),
]


def write_json(result: ScanResult, path: str) -> None:
    """Write the scan result to ``path`` as UTF-8 JSON (the GitHub-Pages feed)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, ensure_ascii=False)


def _fmt_table(stocks: List[StockRecord]) -> str:
    header = (
        f"{'代號':<6}{'名稱':<12}{'市值':>6}{'起漲':>5}{'持續':>4}"
        f"{'漲幅':>8}{'週均':>8}{'乖離':>7}{'均額':>8} {'投信%':>14}"
    )
    rows = [header]
    for s in stocks:
        mc_str = f"{s.mktcap_b:.0f}B" if s.mktcap_b else "—"
        if s.trust_start is not None and s.trust_now is not None:
            trust_str = f"{s.trust_start}→{s.trust_now}%"
        else:
            trust_str = "—"
        rows.append(
            f"{s.code:<6}{s.name:<12}{mc_str:>6}{s.start_date:>5}{s.streak:>4}"
            f"{s.rise_pct:>+7.1f}%{s.avg_wk:>+7.2f}%{s.dist20:>+6.1f}%"
            f"{s.turnover_m:>7,.0f}M {trust_str:>14}"
        )
    return "\n".join(rows)


def format_report(result: ScanResult) -> str:
    """Render the grouped, 3-tier text report (printed to stdout)."""
    lines = [
        f"📋 **台股篩選 — {result.date}**",
        f"規則：{result.rules}",
        f"共 {len(result.stocks)} 檔",
        "",
    ]
    for tier, dot, label in _TIERS:
        group = [s for s in result.stocks if s.tier == tier]
        if not group:
            continue
        lines.append(f"{dot} **{label}** — {len(group)} 檔")
        lines.append("```")
        lines.append(_fmt_table(group))
        lines.append("```")
    return "\n".join(lines)
