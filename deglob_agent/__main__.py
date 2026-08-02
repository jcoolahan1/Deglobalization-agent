"""CLI: python -m deglob_agent [--dry-run] [--output preview.html] [--config config.yaml]"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from .digest import render_html, render_text
from .emailer import send_email
from .fetchers import fetch_page_date, fetch_source
from .models import Item
from .scoring import Scorer
from .state import SeenState

log = logging.getLogger("deglob_agent")


def curate(config: dict, state: SeenState) -> list[Item]:
    settings = config["digest"]
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings["lookback_days"])
    # Scraped listing pages carry no dates, so relevant items get their date
    # looked up from the article page itself and are held to this looser
    # window (asset managers publish monthly/quarterly, not daily).
    scraped_cutoff = now - timedelta(days=settings.get("scraped_max_age_days", 45))
    lookup_budget = settings.get("date_lookup_limit", 12)
    scorer = Scorer(config["keyword_groups"])
    per_source_cap = (
        settings["first_run_max_per_source"] if state.first_run
        else settings["max_items_per_source"]
    )

    selected: list[Item] = []
    for source in config["sources"]:
        candidates = []
        for item in fetch_source(source):
            if state.is_seen(item.key):
                continue
            if item.published is not None and item.published < cutoff:
                # Old dated items are skipped but not marked seen, in case a
                # feed ever republishes something within the window later.
                continue
            scorer.score(item)
            state.mark(item.key, item.url, sent=False)
            if item.score >= settings["min_score"]:
                candidates.append(item)
        candidates.sort(key=lambda it: -it.score)

        kept: list[Item] = []
        lookups = 0
        for item in candidates:
            if len(kept) >= per_source_cap:
                break
            if item.published is None and lookups < lookup_budget:
                lookups += 1
                item.published = fetch_page_date(item.url)
                if item.published is not None and item.published < scraped_cutoff:
                    log.info("Dropping stale item (%s): %s",
                             item.published.date(), item.title)
                    continue
            kept.append(item)
        if len(candidates) > len(kept):
            log.info("%s: kept %d of %d relevant items", source["name"], len(kept), len(candidates))
        selected.extend(kept)

    selected.sort(key=lambda it: -it.score)
    return selected[: settings["max_items_total"]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly deglobalization digest")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true",
                        help="Do not send email and do not update seen-state")
    parser.add_argument("--no-email", action="store_true",
                        help="Update seen-state but skip sending (e.g. to seed state)")
    parser.add_argument("--output", metavar="FILE",
                        help="Also write the HTML digest to FILE")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = yaml.safe_load(Path(args.config).read_text())
    state = SeenState(config["state_file"])
    if state.first_run:
        log.info("First run: no seen-state file yet, capping undated sources")

    items = curate(config, state)
    log.info("Curated %d items for the digest", len(items))

    group_order = [g["label"] for g in
                   sorted(config["keyword_groups"], key=lambda g: -g["weight"])]
    html_body = render_html(items, group_order)
    text_body = render_text(items, group_order)

    if args.output:
        Path(args.output).write_text(html_body)
        log.info("Wrote HTML preview to %s", args.output)

    if args.dry_run:
        print(text_body)
        log.info("Dry run: email not sent, state not saved")
        return 0

    if items and not args.no_email:
        subject = (f"{config['digest']['subject_prefix']} — "
                   f"{datetime.now(timezone.utc):%b %d, %Y} ({len(items)} links)")
        send_email(subject, html_body, text_body)
        log.info("Email sent")
        for item in items:
            state.mark(item.key, item.url, sent=True)
    elif not items:
        log.info("No new relevant items; skipping email")
    else:
        log.info("--no-email: seen-state updated, email skipped")

    state.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
