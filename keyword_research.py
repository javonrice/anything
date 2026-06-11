"""
Keyword Opportunity Finder
Pulls keyword data from RapidAPI, scores by purchase intent + low competition,
and exports results to CSV.

APIs used (rotate when rate limited):
  1. Google Keyword Insight  (rhmueed/google-keyword-insight1)
  2. Twinword Keyword Suggestion (twinword/keyword-suggestion)

Setup:
  pip install requests python-dotenv
  Copy .env.example to .env and fill in your API keys.
"""

import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED_KEYWORDS = [
    "automate",
    "template",
    "tracker",
    "calculator",
    "dashboard",
    "app for",
    "tool for",
    "software for small business",
    "crm for",
    "for contractors",
    "for coaches",
    "for real estate",
    "for gyms",
    "for freelancers",
    "client portal",
    "invoice generator",
    "booking app",
    "lead tracker",
    "proposal template",
    "onboarding tool",
]

# Minimum thresholds — tune these to widen/narrow results
MIN_MONTHLY_VOLUME = 200
MAX_COMPETITION = 0.5      # 0.0 (none) → 1.0 (max)
MIN_CPC = 1.0              # USD — higher CPC = more purchase intent

# Opportunity score weights (must sum to 1.0)
W_VOLUME = 0.25
W_CPC = 0.45
W_COMPETITION = 0.30       # inverted: lower competition → higher score

OUTPUT_DIR = Path(".")

# ---------------------------------------------------------------------------
# API clients
# ---------------------------------------------------------------------------

class RateLimitError(Exception):
    pass


class GoogleKeywordInsightClient:
    """
    RapidAPI: rhmueed/google-keyword-insight1
    Env vars: RAPIDAPI_KEY_1
    """
    BASE_URL = "https://google-keyword-insight1.p.rapidapi.com/globalkey/"

    def __init__(self):
        self.key = "4809f29274msh8fc3b37e2f08a5cp1f44f9jsn4f902fb893c0"

    def fetch(self, keyword: str) -> list[dict]:
        headers = {
            "x-rapidapi-host": "google-keyword-insight1.p.rapidapi.com",
            "x-rapidapi-key": self.key,
        }
        params = {"keyword": keyword, "lang": "en", "country": "us"}
        resp = requests.get(self.BASE_URL, headers=headers, params=params, timeout=15)

        if resp.status_code == 429:
            raise RateLimitError("Google Keyword Insight rate limit hit")
        resp.raise_for_status()

        data = resp.json()
        results = []
        for item in data if isinstance(data, list) else data.get("data", []):
            kw = item.get("keyword") or item.get("text") or ""
            vol = item.get("volume") or item.get("search_volume") or 0
            cpc = item.get("cpc") or item.get("avg_cpc") or 0.0
            comp = item.get("competition") or item.get("competition_index") or 0.0
            if isinstance(comp, str):
                comp = {"LOW": 0.2, "MEDIUM": 0.5, "HIGH": 0.9}.get(comp.upper(), 0.5)
            results.append({
                "keyword": kw,
                "monthly_volume": int(vol),
                "cpc_usd": float(cpc),
                "competition": float(comp),
                "source": "google-keyword-insight",
                "seed": keyword,
            })
        return results


class TwinwordClient:
    """
    RapidAPI: twinword/keyword-suggestion
    Env vars: RAPIDAPI_KEY_2
    """
    BASE_URL = "https://twinword-keyword-suggestion.p.rapidapi.com/suggest/"

    def __init__(self):
        self.key = "4809f29274msh8fc3b37e2f08a5cp1f44f9jsn4f902fb893c0"

    def fetch(self, keyword: str) -> list[dict]:
        headers = {
            "x-rapidapi-host": "twinword-keyword-suggestion.p.rapidapi.com",
            "x-rapidapi-key": self.key,
        }
        params = {"phrase": keyword, "lang": "en"}
        resp = requests.get(self.BASE_URL, headers=headers, params=params, timeout=15)

        if resp.status_code == 429:
            raise RateLimitError("Twinword rate limit hit")
        resp.raise_for_status()

        data = resp.json()
        results = []
        keywords = data.get("keywords", {})
        for kw, meta in keywords.items():
            vol = meta.get("search_volume") or 0
            cpc = meta.get("cpc") or 0.0
            comp = meta.get("competition") or 0.0
            results.append({
                "keyword": kw,
                "monthly_volume": int(vol),
                "cpc_usd": float(cpc),
                "competition": float(comp),
                "source": "twinword",
                "seed": keyword,
            })
        return results


# ---------------------------------------------------------------------------
# Rotation logic
# ---------------------------------------------------------------------------

class KeywordFetcher:
    def __init__(self):
        self.clients = []
        try:
            self.clients.append(GoogleKeywordInsightClient())
            print("✓ Google Keyword Insight client ready")
        except EnvironmentError as e:
            print(f"⚠ Skipping Google Keyword Insight: {e}")

        try:
            self.clients.append(TwinwordClient())
            print("✓ Twinword client ready")
        except EnvironmentError as e:
            print(f"⚠ Skipping Twinword: {e}")

        if not self.clients:
            raise RuntimeError("No API clients configured. Check your .env file.")

        self.current = 0

    def fetch(self, keyword: str) -> list[dict]:
        attempts = 0
        while attempts < len(self.clients):
            client = self.clients[self.current]
            try:
                return client.fetch(keyword)
            except RateLimitError as e:
                print(f"  ↩ {e} — rotating to next API")
                self.current = (self.current + 1) % len(self.clients)
                attempts += 1
        print(f"  ✗ All APIs rate limited for '{keyword}', skipping.")
        return []


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def opportunity_score(row: dict, max_volume: int, max_cpc: float) -> float:
    vol_norm = row["monthly_volume"] / max_volume if max_volume else 0
    cpc_norm = row["cpc_usd"] / max_cpc if max_cpc else 0
    comp_inv = 1.0 - row["competition"]
    return round(W_VOLUME * vol_norm + W_CPC * cpc_norm + W_COMPETITION * comp_inv, 4)


def filter_and_score(rows: list[dict]) -> list[dict]:
    filtered = [
        r for r in rows
        if r["monthly_volume"] >= MIN_MONTHLY_VOLUME
        and r["competition"] <= MAX_COMPETITION
        and r["cpc_usd"] >= MIN_CPC
        and r["keyword"].strip()
    ]

    if not filtered:
        return []

    max_vol = max(r["monthly_volume"] for r in filtered) or 1
    max_cpc = max(r["cpc_usd"] for r in filtered) or 1

    for r in filtered:
        r["opportunity_score"] = opportunity_score(r, max_vol, max_cpc)

    return sorted(filtered, key=lambda r: r["opportunity_score"], reverse=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n=== Keyword Opportunity Finder ===\n")
    fetcher = KeywordFetcher()

    all_results: list[dict] = []
    seen: set[str] = set()

    for i, seed in enumerate(SEED_KEYWORDS, 1):
        print(f"[{i}/{len(SEED_KEYWORDS)}] Fetching: '{seed}'")
        try:
            rows = fetcher.fetch(seed)
        except Exception as e:
            print(f"  ✗ Error: {e}")
            rows = []

        for r in rows:
            key = r["keyword"].lower().strip()
            if key and key not in seen:
                seen.add(key)
                all_results.append(r)

        print(f"  → {len(rows)} keywords returned ({len(all_results)} unique so far)")
        time.sleep(1.2)  # stay within per-second rate limits

    print(f"\nTotal unique keywords collected: {len(all_results)}")

    scored = filter_and_score(all_results)
    print(f"After filtering (vol≥{MIN_MONTHLY_VOLUME}, comp≤{MAX_COMPETITION}, cpc≥${MIN_CPC}): {len(scored)} opportunities\n")

    if not scored:
        print("No results passed the filters. Try loosening MIN_MONTHLY_VOLUME, MAX_COMPETITION, or MIN_CPC.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = OUTPUT_DIR / f"keyword_opportunities_{timestamp}.csv"

    fieldnames = ["opportunity_score", "keyword", "monthly_volume", "cpc_usd", "competition", "seed", "source"]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scored)

    print(f"✓ Results saved to: {out_file}")
    print("\nTop 10 opportunities:")
    print(f"{'Score':<8} {'Volume':<10} {'CPC':>6} {'Comp':>6}  Keyword")
    print("-" * 70)
    for r in scored[:10]:
        print(f"{r['opportunity_score']:<8} {r['monthly_volume']:<10} ${r['cpc_usd']:>5.2f} {r['competition']:>6.2f}  {r['keyword']}")


if __name__ == "__main__":
    main()
