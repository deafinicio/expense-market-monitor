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
# Regional search coverage: separate query terms and storefront country per locale.
# This is a sampled international discovery strategy, NOT exhaustive worldwide coverage.
LOCALES = (
    ("en","us",("expense tracker","budget planner")),
    ("en","gb",("spending tracker","money manager")),
    ("uk","ua",("облік витрат","сімейний бюджет")),
    ("es","es",("control de gastos","presupuesto personal")),
    ("es","mx",("registro de gastos","control de gastos")),
    ("fr","fr",("suivi des dépenses","gestion budget")),
    ("de","de",("ausgaben tracker","haushaltsbuch")),
    ("pt","br",("controle de gastos","orçamento pessoal")),
    ("it","it",("gestione spese","bilancio familiare")),
    ("pl","pl",("kontrola wydatków","budżet domowy")),
    ("tr","tr",("harcama takibi","bütçe takip")),
    ("ja","jp",("家計簿","支出管理")),
    ("ko","kr",("가계부","지출 관리")),
    ("hi","in",("खर्च ट्रैकर","बजट प्लानर")),
    ("id","id",("catatan pengeluaran","pengatur anggaran")),
    ("ar","sa",("تتبع المصاريف","إدارة الميزانية")),
    ("zh","tw",("記帳","支出管理")),
)
POSITIVE = (
    "expense", "spending", "budget", "money manager", "finance tracker",
    "financial tracker", "cost tracker", "personal finance",
    "витрат", "бюджет", "фінанс", "gasto", "presupuesto", "finanzas",
    "dépense", "budget", "financ", "ausgaben", "haushalt", "spese",
    "orçamento", "despesa", "wydatk", "budżet", "harcama", "bütçe",
    "家計", "支出", "記帳", "가계부", "지출", "खर्च", "बजट",
    "pengeluaran", "anggaran", "مصاريف", "ميزانية",
)
NEGATIVE = ("employee reimbursement", "expense report approval", "receipt scanner only")
CONFIG = {"locales": LOCALES, "positive": POSITIVE, "negative": NEGATIVE, "per_query": 100}
CONFIG_HASH = hashlib.sha256(json.dumps(CONFIG, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def relevant(item):
    text = (item.get("name", "") + " " + item.get("description", "")).lower()
    return any(term in text for term in POSITIVE) and not any(term in text for term in NEGATIVE)


def google_search(query, lang="en", country="us"):
    from google_play_scraper import search
    try:
        results = search(query, lang=lang, country=country, n_hits=100)
    except (TypeError, KeyError, IndexError):
        # Some localized store responses are incompatible with the unofficial parser.
        # Retry with an English interface but preserve the localized query and country.
        if lang == "en":
            raise
        results = search(query, lang="en", country=country, n_hits=100)
    if not isinstance(results, list):
        raise RuntimeError("Unexpected Google Play response")
    return [
        {"id": str(x["appId"]), "name": x.get("title", ""),
         "description": x.get("description") or x.get("summary") or "",
         "url": "https://play.google.com/store/apps/details?id=" + x["appId"]}
        for x in results if x.get("appId")
    ]


def apple_search(query, lang="en", country="us"):
    response = requests.get(
        "https://itunes.apple.com/search",
        params={"term": query, "country": country, "media": "software",
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
        total_queries = sum(len(queries) for _, _, queries in LOCALES)
        for lang, country, queries in LOCALES:
            for query in queries:
                try:
                    for item in lookup(query, lang=lang, country=country):
                        # Multiple country/language appearances share the same store app ID.
                        key = item["id"]
                        if key not in found or (not relevant(found[key]) and relevant(item)):
                            found[key] = item
                except Exception as exc:
                    errors.append(f"{lang}-{country} / {query}: {type(exc).__name__}: {str(exc)[:120]}")
                time.sleep(0.25)
        success = not errors
        matched = sorted((x for x in found.values() if relevant(x)),
                         key=lambda x: x["name"].lower())
        history["runs"] = [r for r in history["runs"]
                           if not (r["day"] == day and r["platform"] == store)]
        history["runs"].append({
            "day": day, "platform": store, "status": "ok" if success else "error",
            "queries_ok": total_queries-len(errors),
            "queries_total": total_queries, "error": "; ".join(errors),
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
