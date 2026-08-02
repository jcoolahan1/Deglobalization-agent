"""Keyword-based relevance scoring against the deglobalization taxonomy."""

from __future__ import annotations

import re

from .models import Item


class Scorer:
    def __init__(self, keyword_groups: list[dict]):
        # Sort so higher-weight groups decide the item's section label.
        self.groups = []
        for group in sorted(keyword_groups, key=lambda g: -g["weight"]):
            pattern = re.compile(
                r"\b(?:" + "|".join(re.escape(k) for k in group["keywords"]) + r")\b",
                re.IGNORECASE,
            )
            self.groups.append((group["label"], group["weight"], pattern))

    def score(self, item: Item) -> Item:
        title = item.title or ""
        summary = item.summary or ""
        score = 0
        matched_group = None
        matched_keywords: list[str] = []

        for label, weight, pattern in self.groups:
            title_hits = {m.lower() for m in pattern.findall(title)}
            summary_hits = {m.lower() for m in pattern.findall(summary)}
            if not title_hits and not summary_hits:
                continue
            # Title hits count double; each distinct keyword counts once.
            score += weight * (2 * len(title_hits) + len(summary_hits - title_hits))
            if matched_group is None:
                matched_group = label
            matched_keywords.extend(sorted(title_hits | summary_hits))

        item.score = score
        item.matched_group = matched_group
        item.matched_keywords = matched_keywords
        return item
