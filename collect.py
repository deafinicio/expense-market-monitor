"""Daily fixed-query discovery, not a census of the app stores."""
from __future__ import annotations
import csv
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
COUNTRY = "us"
LANG = "en"
QUERIES = (
    "expense tracker", "expense manager", "spending tracker",
    "budget planner", "personal finance tracker", "expense log",
    "track expenses", "money manager",
)
POSITIVE = (
    "expense", "spending", "budget", "money manager", "finance tracker",
    "financial tracker", "cost tracker", "personal finance",
)
NEGATIVE = ("employee reimbursement", "expense report approval", "receipt scanner only")
CONFIG = {"country": COUNTRY, "language": LANG, "queries": QUERIES,
          "positive": POSITIVE, "negative": NEGATIVE, "per_query": 100}
CONFIG_HASH = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()[:12]


def relevant(item):
    text = (item.get("name", "") + " " + item.get("description", "")).lower()
    return any(term in text for term in POSITIVE) and not any(term in text for term in NEGATIVE)


def google_search(query):
    from google_play_scraper import search
    results = search(query, lang=LANG, country=COUNTRY, n_hits=100)
    if not isinstance(results, list):
        raise RuntimeError("Unexpected Google Play response")
    return [
        {"id": str(x["appId"]), "name": x.get("title", ""),
         "description": x.get("description") or x.get("summary") or "",
         "url": "https://play.google.com/store/apps/details?id=" + x["appId"]}
        for x in results if x.get("appId")
    ]


def apple_search(query):
    response = requests.get(
        "https://itunes.apple.com/search",
        params={"term": query, "country": COUNTRY, "media": "software",
                "entity": "software", "limit": 200},
        timeout=30, headers={"User-Agent": "ExpenseAppMarketMonitor/1.0"},
    )
    response.raise_for_status()
    data = response.json()
    if "results" not in data:
        raise RuntimeError("Apple returned no results")
    return [
        {"id": str(x["trackId"]), "name": x.get("trackName", ""),
         "description": x.get("description", ""), "url": x.get("trackViewUrl", "")}
        for x in data["results"] if x.get("trackId") and x.get("kind", "software") == "software"
    ]


def read_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def run():
    DOCS.mkdir(exist_ok=True)
    history_path = DOCS / "history.json"
    apps_path = DOCS / "apps.json"
    history = read_json(history_path, {"history": [], "runs": []})
    app_lists = read_json(apps_path, {"google_play": {"day": None, "apps": []},
                                      "app_store": {"day": None, "apps": []}})
    day = datetime.now(timezone.utc).date().isoformat()
    errors_found = False
    for store, lookup in (("google_play", google_search), ("app_store", apple_search)):
        existing = next((r for r in history["history"]
                         if r["day"] == day and r["platform"] == store
                         and r.get("config_hash") == CONFIG_HASH), None)
        if existing:
            print(store, "already scanned today; preserving snapshot")
            continue
        found = {}
        errors = []
        for query in QUERIES:
            try:
                for item in lookup(query):
                    found[item["id"]] = item
            except Exception as exc:
                errors.append(f"{query}: {type(exc).__name__}: {str(exc)[:160]}")
            time.sleep(0.4)
        success = not errors
        matched = sorted((x for x in found.values() if relevant(x)),
                         key=lambda x: x["name"].lower())
        history["runs"] = [r for r in history["runs"]
                           if not (r["day"] == day and r["platform"] == store)]
        history["runs"].append({
            "day": day, "platform": store, "status": "ok" if success else "error",
            "queries_ok": len(QUERIES)-len(errors),
            "queries_total": len(QUERIES), "error": "; ".join(errors),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        })
        if success:
            history["history"] = [r for r in history["history"]
                                  if not (r["day"] == day and r["platform"] == store)]
            history["history"].append({
                "day": day, "platform": store, "count": len(matched),
                "discovered": len(found), "config_hash": CONFIG_HASH,
            })
            app_lists[store] = {"day": day, "apps": [
                {"id": x["id"], "name": x["name"], "url": x["url"]} for x in matched
            ]}
        else:
            errors_found = True
        print(f"{store}: status={'ok' if success else 'error'}, matches={len(matched)}, failures={len(errors)}")
    history["history"].sort(key=lambda r: (r["day"], r["platform"]))
    history["runs"].sort(key=lambda r: (r["day"], r["platform"]), reverse=True)
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    apps_path.write_text(json.dumps(app_lists, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (DOCS / "history.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("date", "store", "found_relevant", "discovered", "method_hash"))
        for row in history["history"]:
            writer.writerow((row["day"], row["platform"], row["count"],
                             row["discovered"], row["config_hash"]))
    return 1 if errors_found else 0


if __name__ == "__main__":
    raise SystemExit(run())
