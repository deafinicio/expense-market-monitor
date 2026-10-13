# Трекер трекерів витрат / Expense Tracker Tracker

Public, open-source daily discovery tracker for personal expense-tracking apps in **Google Play** and **Apple App Store**.

**Dashboard:** https://deafinicio.github.io/expense-market-monitor/ (available once GitHub Pages is enabled).

## What it measures
This is the count of *distinct apps found through a fixed set of search queries and matching a transparent keyword heuristic*, NOT the total number of relevant apps in each store. Rankings, region, search API limits and incomplete descriptions influence counts. A decline is not proof that apps disappeared.

- Country: US; Google Play language: English.
- Eight search queries are deduplicated by app ID per store.
- Only fully successful batches produce chart points; failed scans appear in the status log.
- Historic estimates based on release dates and latest discovered application lists are published as JSON and CSV.
- Data collection runs daily with GitHub Actions (approximate schedule, not exact) and can be triggered manually.
- Data are committed to the repository, so no server or database hosting is required.

## Enable public website
1. In this GitHub repository open **Settings → Pages**.
2. Under **Build and deployment**, select **GitHub Actions** as the source.
3. Open **Actions → Daily market scan → Run workflow** for the initial collection.
4. After a successful workflow, open the dashboard link above.

The scheduled workflow runs every day at 01:10 UTC (Kyiv time 03:10 in winter, 04:10 in summer). Scheduled workflows may be delayed or skipped by GitHub. Check Actions logs.

## Developer setup
```bash
python -m pip install -r requirements.txt
python collect.py
python -m unittest discover -s tests -v
```

The scan stores data under `docs/`. This folder is public. To add queries change `QUERIES` in `collect.py`, then document the methodology break. Historical data are not backfilled.

## Data definitions
- `docs/history.json`: daily successes, unsuccessful attempts and configuration hash.
- `docs/apps.json`: most recently identified applications, grouped by store.
- `docs/history.csv`: the dated counts for download.
- `docs/index.html`: static dashboard; `docs/.nojekyll`: GitHub Pages compatibility.

The Google Play source uses the unofficial `google-play-scraper` Python package, which may be blocked or break as the store changes. Apple data use Apple's public search endpoint, not a complete catalog API. Respect the stores' usage policies and do not treat any results as an audited market total.

MIT-licensed application code. Store names and metadata belong to their respective owners.

## Retrospective 2026 estimate

The chart combines reconstructed values for **2026-01-01 through the day before the first actual successful daily observation**, then actual daily search snapshots. Estimated values count currently discoverable relevant apps whose recorded first release date is on or before each day. Removed apps and historical availability cannot be recovered with this method; these early points are not historical store counts. A Google Play lookup limit of 70 IDs per job enables progressive enrichment across successive runs, while Apple IDs are looked up in batches.

The pipeline publishes `docs/historical_estimate.json` and `docs/release_dates.json` alongside the daily observations.
