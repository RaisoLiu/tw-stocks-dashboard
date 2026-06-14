"""On-disk cache for T86 (三大法人) daily net-buy data.

Each trading day is cached as ``data/t86/YYYYMMDD.json`` so the 3.5s-throttled
TWSE fetch only ever runs once per date. The directory is git-ignored (the
files are regenerable) and persisted across CI runs via ``actions/cache``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)


class T86Cache:
    def __init__(self, cache_dir: str):
        self.dir = cache_dir

    def _path(self, date_str: str) -> str:
        return os.path.join(self.dir, f"{date_str}.json")

    def get(self, date_str: str) -> Optional[dict]:
        """Return cached data for a date, or ``None`` if not cached."""
        path = self._path(date_str)
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("ignoring corrupt T86 cache %s: %s", path, exc)
            return None

    def put(self, date_str: str, data: dict) -> None:
        """Persist data for a date (skips empty payloads)."""
        if not data:
            return
        os.makedirs(self.dir, exist_ok=True)
        with open(self._path(date_str), "w", encoding="utf-8") as fh:
            json.dump(data, fh)
