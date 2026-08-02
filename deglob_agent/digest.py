"""Render the curated item list as an HTML email body."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from itertools import groupby

from .models import Item

_STYLE = """
  body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a2e;
         max-width: 720px; margin: 0 auto; padding: 24px 16px; }
  h1 { font-size: 22px; border-bottom: 3px solid #14213d; padding-bottom: 8px; }
  h2 { font-size: 17px; color: #14213d; margin-top: 28px;
       border-bottom: 1px solid #d5d5e0; padding-bottom: 4px; }
  .item { margin: 14px 0; }
  .item a { color: #0b3d91; font-size: 15px; font-weight: bold; text-decoration: none; }
  .meta { font-size: 12px; color: #6b6b7b; margin-top: 2px; }
  .summary { font-size: 13px; color: #3a3a4a; margin-top: 4px; }
  .tag { background: #eef1f8; border-radius: 3px; padding: 1px 6px;
         font-size: 11px; color: #444; }
  .footer { margin-top: 32px; font-size: 11px; color: #9a9aa8;
            border-top: 1px solid #d5d5e0; padding-top: 8px; }
"""


def render_html(items: list[Item], group_order: list[str]) -> str:
    """Items grouped by matched keyword group, ordered by taxonomy weight."""
    now = datetime.now(timezone.utc)
    order = {label: i for i, label in enumerate(group_order)}
    items = sorted(items, key=lambda it: (order.get(it.matched_group, 99), -it.score))

    sections = []
    for label, group_items in groupby(items, key=lambda it: it.matched_group):
        rows = []
        for it in group_items:
            date = it.published.strftime("%b %d, %Y") if it.published else "undated"
            keywords = ", ".join(it.matched_keywords[:6])
            summary = ""
            if it.summary:
                text = it.summary[:280] + ("…" if len(it.summary) > 280 else "")
                summary = f'<div class="summary">{html.escape(text)}</div>'
            rows.append(
                f'<div class="item">'
                f'<a href="{html.escape(it.url, quote=True)}">{html.escape(it.title)}</a>'
                f'<div class="meta">{html.escape(it.source)} &middot; {date} &middot; '
                f'<span class="tag">{html.escape(keywords)}</span></div>'
                f"{summary}</div>"
            )
        sections.append(f"<h2>{html.escape(label or 'Other')}</h2>\n" + "\n".join(rows))

    body = "\n".join(sections) if sections else "<p>No new relevant links this week.</p>"
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{_STYLE}</style></head>
<body>
  <h1>Deglobalization Weekly &mdash; {now.strftime("%B %d, %Y")}</h1>
  <p style="font-size:13px;color:#555;">Curated links on deglobalization and its
  investment implications: trade policy, energy, semiconductors, critical
  materials, precious metals, and the US dollar. {len(items)} new items this week.</p>
  {body}
  <div class="footer">Generated automatically by the deglobalization digest agent.
  Sources: WSJ, Odd Lots, The Compound, Eye on the Market, JPMAM, MFS,
  Columbia Threadneedle, Baillie Gifford.</div>
</body>
</html>"""


def render_text(items: list[Item], group_order: list[str]) -> str:
    """Plain-text alternative part."""
    order = {label: i for i, label in enumerate(group_order)}
    items = sorted(items, key=lambda it: (order.get(it.matched_group, 99), -it.score))
    lines = [f"Deglobalization Weekly — {datetime.now(timezone.utc):%B %d, %Y}", ""]
    for label, group_items in groupby(items, key=lambda it: it.matched_group):
        lines += [label or "Other", "-" * len(label or "Other")]
        for it in group_items:
            date = it.published.strftime("%Y-%m-%d") if it.published else "undated"
            lines.append(f"* {it.title} ({it.source}, {date})")
            lines.append(f"  {it.url}")
        lines.append("")
    return "\n".join(lines)
