"""Incrementally enrich app listings with storefront price and up to 3 lowest-star written reviews.

A sample of publicly accessible reviews is sorted ascending by score. This is not
guaranteed to find the globally lowest-rated reviews.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

DOCS = Path(__file__).resolve().parent / "docs"
PATH = DOCS / "details.json"
APPS = DOCS / "apps.json"
MAX_APPS_PER_RUN = 30
USER_AGENT = {"User-Agent": "ExpenseAppMarketMonitor/1.0"}


def select_low_reviews(items):
    dedup = {}
    for item in items:
        text = str(item.get("text") or "").strip()
        try:
            rating = int(item.get("rating") or 0)
        except (TypeError, ValueError):
            continue
        if not text or not 1 <= rating <= 5:
            continue
        key = str(item.get("id") or (rating, text))
        dedup[key] = {"rating": rating, "text": text[:1200], "date": str(item.get("date") or "")[:10]}
    return sorted(dedup.values(), key=lambda v: (v["rating"], v["date"]))[:3]


def google_details(app_id):
    from google_play_scraper import app, reviews, Sort
    info = app(app_id, lang="en", country="us")
    # The package marks free apps and has a localized sale price string.
    price = "Free" if info.get("free") else (info.get("saleText") or
             info.get("priceText") or (str(info.get("price")) + " " + (info.get("currency") or "USD")))
    sampled = []
    for score in (1, 2, 3, 4, 5):
        if len(sampled) >= 3:
            break
        batch, _ = reviews(app_id, lang="en", country="us", sort=Sort.NEWEST,
                           count=30, filter_score_with=score)
        sampled.extend({"id": x.get("reviewId"), "rating": x.get("score"),
                        "text": x.get("content"), "date": x.get("at")}
                       for x in batch)
        time.sleep(0.25)
    return {"price": price or "Unknown", "price_value": (
        0.0 if info.get("free") else
        float(info["price"]) if isinstance(info.get("price"), (int, float)) else None
    ), "currency": info.get("currency") or "USD", "reviews": select_low_reviews(sampled)}


def apple_details(app_id):
    lookup = requests.get("https://itunes.apple.com/lookup",
                          params={"id": app_id, "country": "us"}, headers=USER_AGENT, timeout=25)
    lookup.raise_for_status()
    found = lookup.json().get("results") or []
    if not found:
        raise ValueError("Missing App Store lookup")
    info = found[0]
    price = info.get("formattedPrice") or (
        "Free" if info.get("price") == 0 else
        (str(info.get("price")) + " " + (info.get("currency") or "USD")))
    # Public Apple RSS is a limited sample, not an exhaustive review archive.
    sampled = []
    for page in (1, 2):
        url = f"https://itunes.apple.com/us/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
        try:
            response = requests.get(url, headers=USER_AGENT, timeout=25)
            if response.status_code in (404, 400):
                break
            response.raise_for_status()
            entries = response.json().get("feed", {}).get("entry", [])
        except (requests.RequestException, ValueError) as exc:
            print("App Store review feed unavailable:", app_id, type(exc).__name__)
            break
        if isinstance(entries, dict):
            entries = [entries]
        for e in entries:
            if "im:rating" not in e:
                continue
            sampled.append({
                "id": e.get("id", {}).get("label"),
                "rating": e.get("im:rating", {}).get("label"),
                "text": e.get("content", {}).get("label"),
                "date": e.get("updated", {}).get("label"),
            })
        time.sleep(0.3)
    return {"price": price or "Unknown", "price_value": (
        float(info["price"]) if isinstance(info.get("price"), (int, float)) else None
    ), "currency": info.get("currency") or "USD", "reviews": select_low_reviews(sampled)}


def run():
    app_lists = json.loads(APPS.read_text(encoding="utf-8"))
    existing = json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else {}
    items = [(platform, str(a["id"])) for platform in ("google_play", "app_store")
             for a in app_lists.get(platform, {}).get("apps", [])]
    current = {f"{p}:{i}" for p, i in items}
    # Drop apps no longer in the latest discovered list.
    existing = {key: value for key, value in existing.items() if key in current}
    # refresh oldest; prioritize those never processed
    items.sort(key=lambda pair: existing.get(f"{pair[0]}:{pair[1]}", {}).get("updated_at", ""))
    for platform, app_id in items[:MAX_APPS_PER_RUN]:
        key = f"{platform}:{app_id}"
        try:
            details = google_details(app_id) if platform == "google_play" else apple_details(app_id)
            existing[key] = {**details, "updated_at": datetime.now(timezone.utc).isoformat()}
            print(key, details["price"], len(details["reviews"]))
        except Exception as exc:
            print("Could not enrich", key, type(exc).__name__, str(exc)[:130])
        time.sleep(0.5)
    PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
