"""Build estimated 2026 history from current discovered apps' release dates.

Runs incrementally. Historical points precede the first observed daily snapshot;
observed history is never overwritten or fabricated.
"""
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

DOCS = Path(__file__).resolve().parent / "docs"
CACHE = DOCS / "release_dates.json"
HISTORY = DOCS / "history.json"
APPS = DOCS / "apps.json"
BACKFILL = DOCS / "historical_estimate.json"
START = date(2026, 1, 1)


def get_json(path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def iso_date(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return parsed.isoformat()
    except ValueError:
        pass
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def fetch_apple(ids):
    out = {}
    for pos in range(0, len(ids), 80):
        subset = ids[pos:pos+80]
        r = requests.get("https://itunes.apple.com/lookup",
                         params={"id": ",".join(subset), "country": "us"},
                         timeout=40, headers={"User-Agent": "ExpenseAppMarketMonitor/1.0"})
        r.raise_for_status()
        payload = r.json()
        for item in payload.get("results", []):
            if item.get("trackId"):
                out[str(item["trackId"])] = iso_date(item.get("releaseDate"))
        time.sleep(0.4)
    return out


def fetch_google(app_id):
    from google_play_scraper import app
    info = app(app_id, lang="en", country="us")
    return iso_date(info.get("released"))


def build(history, inventory, first_dates):
    output = []
    today = datetime.now(timezone.utc).date()
    for platform in ("google_play", "app_store"):
        observed = sorted(x["day"] for x in history.get("history", [])
                          if x["platform"] == platform and x.get("day"))
        # Only reconstruct dates BEFORE the first daily measurement.
        end = min(date.fromisoformat(observed[0])-timedelta(days=1), today) if observed else today
        if end < START:
            continue
        ids = [str(x["id"]) for x in inventory.get(platform, {}).get("apps", [])]
        dates = [date.fromisoformat(first_dates[platform][i]) for i in ids
                 if first_dates.get(platform, {}).get(i) and
                 iso_date(first_dates[platform][i])]
        cursor = START
        while cursor <= end:
            output.append({"day": cursor.isoformat(), "platform": platform,
                           "count": sum(d <= cursor for d in dates)})
            cursor += timedelta(days=1)
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "method": "current_discovered_apps_with_first_release_date",
            "history": output,
            "coverage": {p: {"total_current_apps": len(inventory.get(p, {}).get("apps", [])),
                             "known_release_dates": sum(1 for a in inventory.get(p, {}).get("apps", [])
                                 if first_dates.get(p, {}).get(str(a["id"])))}
                         for p in ("google_play", "app_store")}}


def run():
    inventory = get_json(APPS, {})
    history = get_json(HISTORY, {"history": []})
    cache = get_json(CACHE, {"google_play": {}, "app_store": {}})
    for platform in ("google_play", "app_store"):
        cache.setdefault(platform, {})
    for platform in ("app_store", "google_play"):
        ids = [str(x["id"]) for x in inventory.get(platform, {}).get("apps", [])]
        pending = [i for i in ids if i not in cache[platform]]
        if platform == "app_store" and pending:
            try:
                result = fetch_apple(pending)
                for app_id in pending:
                    cache[platform][app_id] = result.get(app_id)
            except Exception as exc:
                print("Apple release-date lookup failed:", exc)
        if platform == "google_play":
            # Cap traffic per execution; run again daily to enrich remaining IDs.
            for app_id in pending[:70]:
                try:
                    cache[platform][app_id] = fetch_google(app_id)
                except Exception as exc:
                    print("Google release-date lookup failed for", app_id, type(exc).__name__)
                    # A failed request is NOT cached and will be retried.
                time.sleep(0.6)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    result = build(history, inventory, cache)
    BACKFILL.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Estimate data points:", len(result["history"]), "coverage:", result["coverage"])


if __name__ == "__main__":
    run()
