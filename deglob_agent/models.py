from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Item:
    """A single candidate link pulled from any source."""

    title: str
    url: str
    source: str
    source_category: str  # news | podcast | asset_manager
    summary: str = ""
    published: datetime | None = None

    # Filled in by scoring.
    score: int = 0
    matched_group: str | None = None
    matched_keywords: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Stable dedupe key: URL without scheme, query, or trailing slash."""
        url = self.url.split("?")[0].split("#")[0].rstrip("/")
        for prefix in ("https://", "http://", "www."):
            if url.startswith(prefix):
                url = url[len(prefix):]
        if url.startswith("www."):
            url = url[4:]
        return url.lower()
