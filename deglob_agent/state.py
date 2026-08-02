"""Persistent record of links already seen, so each digest only has new ones."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class SeenState:
    def __init__(self, path: str):
        self.path = Path(path)
        self.first_run = not self.path.exists()
        self._data: dict[str, dict] = {}
        if not self.first_run:
            self._data = json.loads(self.path.read_text())

    def is_seen(self, key: str) -> bool:
        return key in self._data

    def mark(self, key: str, url: str, sent: bool) -> None:
        if key not in self._data:
            self._data[key] = {
                "url": url,
                "first_seen": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sent": sent,
            }
        elif sent:
            self._data[key]["sent"] = True

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=1, sort_keys=True) + "\n")
