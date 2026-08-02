# Deglobalization Weekly Digest Agent

Emails a curated, weekly list of links on **deglobalization and its investment
implications** — trade policy, energy security, semiconductors, critical
materials, precious metals, and the US dollar — pulled from:

| Source | How it's pulled |
| --- | --- |
| Wall Street Journal (Markets, World, Business, Tech, Opinion) | public RSS feeds |
| Odd Lots (Bloomberg) | podcast RSS |
| The Compound and Friends + Animal Spirits (Ritholtz) | podcast RSS |
| Eye on the Market podcast (Michael Cembalest) | podcast RSS |
| JPM Eye on the Market / Private Bank insights | article page scrape |
| J.P. Morgan Asset Management (On the Minds of Investors) | JSON API |
| MFS Investments insights | article page scrape |
| Columbia Threadneedle insights | article page scrape |
| Baillie Gifford insights | article page scrape |

## How it works

Every run, the agent:

1. **Fetches** all candidate links from the sources in `config.yaml`.
2. **Scores** each item against a weighted keyword taxonomy (deglobalization
   and trade-policy terms weigh most; theme terms like energy, semis, critical
   minerals, gold, and the dollar weigh next; broad geopolitics terms least).
   Title matches count double. Items below `min_score` are dropped.
3. **Dedupes** against `state/seen.json`, so a link is only ever emailed once.
   Dated items must also fall within the `lookback_days` window.
4. **Emails** an HTML digest, grouped by theme and ranked by relevance, capped
   at `max_items_per_source` / `max_items_total` so it stays readable.
5. **Persists** the seen-state (the GitHub Actions workflow commits it back to
   the repo, so history is visible in git).

A GitHub Actions workflow ([`.github/workflows/weekly-digest.yml`](.github/workflows/weekly-digest.yml))
runs this every **Monday at 12:00 UTC** and also supports manual runs
(including a dry-run option) from the Actions tab.

## Setup

1. **Add repository secrets** (Settings → Secrets and variables → Actions):

   | Secret | Value |
   | --- | --- |
   | `SMTP_HOST` | e.g. `smtp.gmail.com` |
   | `SMTP_PORT` | `587` (STARTTLS) or `465` (implicit TLS) |
   | `SMTP_USERNAME` | SMTP login (for Gmail, your address) |
   | `SMTP_PASSWORD` | password — for Gmail use an [App Password](https://myaccount.google.com/apppasswords) |
   | `DIGEST_FROM` | From address (optional; defaults to `SMTP_USERNAME`) |
   | `DIGEST_TO` | your email; comma-separate for multiple recipients |

   For an internal relay without auth, leave `SMTP_USERNAME`/`SMTP_PASSWORD`
   unset and set the env var `SMTP_STARTTLS=false` if the relay lacks TLS.

2. **Trigger a first run** from the Actions tab ("Weekly deglobalization
   digest" → Run workflow). The first run has no seen-state yet, so undated
   scraped sources are capped harder (`first_run_max_per_source`) to keep the
   first email from being flooded with archives. Subsequent weekly runs only
   contain links that are new since the last run.

That's it — Mondays you'll get the digest automatically.

## Running locally

```bash
pip install -r requirements.txt

# Preview without sending or recording state:
python -m deglob_agent --dry-run --output preview.html

# Seed the seen-state without sending an email:
python -m deglob_agent --no-email

# Full run (requires the SMTP_* / DIGEST_* environment variables):
python -m deglob_agent
```

## Customizing

Everything lives in [`config.yaml`](config.yaml):

- **Add a source**: for anything with an RSS feed, add a `type: rss` entry.
  For an asset manager's insights page, add `type: html_links` with a
  `link_pattern` regex whose first capture group is the article URL (view the
  page source to find the pattern). One broken source never fails the run —
  it is logged and skipped.
- **Tune the curation**: edit `keyword_groups` (keywords, weights, section
  labels) and the `digest` thresholds (`min_score`, caps, `lookback_days`).
  Raise `min_score` for a tighter list, lower it for a broader one.
- **Change the schedule**: edit the `cron` line in the workflow (times are UTC).

## Notes

- WSJ links may require your WSJ subscription login to read in full; the
  digest links to the articles, it does not republish content.
- Scraped asset-manager pages expose no publish dates, so those items are
  marked "undated" and included the first time they appear.
- Podcast links point at the public episode pages from each show's own feed.
