"""Fetch candidate items from RSS feeds, HTML listing pages, and JSON APIs."""

from __future__ import annotations

import calendar
import html as html_lib
import json
import logging
import re
from datetime import datetime, timezone

import feedparser
import requests

from .models import Item

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
TIMEOUT = 30


def fetch_source(source: dict) -> list[Item]:
    """Dispatch on source type. Returns [] on any per-source failure so one
    broken site never kills the whole digest."""
    fetchers = {
        "rss": _fetch_rss,
        "html_links": _fetch_html_links,
        "jpmam_json": _fetch_jpmam_json,
    }
    fetcher = fetchers[source["type"]]
    try:
        items = fetcher(source)
        log.info("%-45s %3d items", source["name"], len(items))
        return items
    except Exception:
        log.exception("Source failed: %s", source["name"])
        return []


def _get(url: str) -> requests.Response:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp


def _strip_html(text: str) -> str:
    return html_lib.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _fetch_rss(source: dict) -> list[Item]:
    resp = _get(source["url"])
    feed = feedparser.parse(resp.content)
    items = []
    for entry in feed.entries:
        published = None
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            published = datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
        link = entry.get("link", "")
        title = _strip_html(entry.get("title", ""))
        if not link or not title:
            continue
        summary = _strip_html(entry.get("summary", ""))[:1500]
        items.append(
            Item(
                title=title,
                url=link,
                source=source["name"],
                source_category=source.get("category", "news"),
                summary=summary,
                published=published,
            )
        )
    return items


def _title_from_slug(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"\.(html?|aspx?)$", "", slug)
    slug = re.sub(r"-\d{6,}$", "", slug)  # trailing numeric ids
    slug = re.sub(r"^20\d\d[-_]q[1-4][-_]", "", slug)  # "2026-q2-" prefixes
    title = slug.replace("-", " ").replace("_", " ").strip()
    return title[:1].upper() + title[1:]


def _slug_is_stale(url: str, max_age_years: int = 1) -> bool:
    """Undated listing pages can expose their whole archive. If the URL slug
    itself carries a year (e.g. /2022-q4-...), skip clearly old articles."""
    years = [int(y) for y in re.findall(r"\b(20[0-4]\d)\b", url.rsplit("/", 2)[-2] + "/" + url.rsplit("/", 1)[-1])]
    if not years:
        return False
    return max(years) < datetime.now(timezone.utc).year - max_age_years


def _fetch_html_links(source: dict) -> list[Item]:
    """Extract article links from a listing page with a configured regex.

    The regex's first capture group must be the article URL. Anchor text is
    not always available in a regex-friendly way, so titles fall back to a
    cleaned-up URL slug, which is what scoring matches against.
    """
    page = _get(source["url"]).text
    base = source.get("base_url", "")
    min_depth = source.get("min_path_depth", 0)
    listing_url = source["url"].rstrip("/")

    seen: set[str] = set()
    items: list[Item] = []
    for match in re.finditer(source["link_pattern"], page):
        url = html_lib.unescape(match.group(1))
        if not url.startswith("http"):
            url = base + url
        if url.rstrip("/") == listing_url or url in seen:
            continue
        path = url.split("://", 1)[-1]
        if min_depth and len([p for p in path.split("/") if p]) < min_depth:
            continue
        if _slug_is_stale(url):
            continue
        seen.add(url)
        items.append(
            Item(
                title=_title_from_slug(url),
                url=url,
                source=source["name"],
                source_category=source.get("category", "asset_manager"),
            )
        )
    return items


def _fetch_jpmam_json(source: dict) -> list[Item]:
    """J.P. Morgan Asset Management AEM editorial-listing JSON endpoint."""
    data = _get(source["url"]).json()
    base = source.get("base_url", "https://am.jpmorgan.com")

    def find_article_list(obj):
        if isinstance(obj, list) and obj and isinstance(obj[0], dict) and "url" in obj[0]:
            return obj
        if isinstance(obj, dict):
            for value in obj.values():
                found = find_article_list(value)
                if found:
                    return found
        if isinstance(obj, list):
            for value in obj:
                found = find_article_list(value)
                if found:
                    return found
        return None

    articles = find_article_list(data.get("pages", data)) or []
    items = []
    for art in articles:
        url = art.get("url") or ""
        title = _strip_html(art.get("title") or art.get("headline") or "")
        if not url or not title:
            continue
        if not url.startswith("http"):
            url = base + url
        published = None
        for key in ("displayDate", "publishDate", "date"):
            raw = art.get(key)
            if raw:
                for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
                    try:
                        published = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        pass
            if published:
                break
        items.append(
            Item(
                title=title,
                url=url,
                source=source["name"],
                source_category=source.get("category", "asset_manager"),
                summary=_strip_html(art.get("description") or "")[:1500],
                published=published,
            )
        )
    return items
