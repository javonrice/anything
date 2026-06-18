"""
Fiverr Demand Scraper — via RapidAPI
Pulls gig title, orders in queue, and URL for target keywords.
Sorted by orders desc — highest demand surfaces first.

API: Fiverr Data API on RapidAPI
Set RAPIDAPI_KEY as a GitHub Actions secret or hardcode below for testing.
"""

import csv
import http.client
import json
import os
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAPIDAPI_KEY  = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = "fiverr4.p.rapidapi.com"

KEYWORDS = [
    "logo design",
    "video editing",
    "social media management",
]

MAX_PAGES = 0   # 0 = all pages; set e.g. 5 to cap
OUTPUT    = "fiverr_demand.csv"

HEADERS = {
    "x-rapidapi-key":  RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_get(path: str) -> dict:
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    conn.request("GET", path, headers=HEADERS)
    res  = conn.getresponse()
    body = res.read().decode("utf-8")
    if res.status == 429:
        raise RuntimeError("Rate limit hit")
    if res.status != 200:
        raise RuntimeError(f"HTTP {res.status}: {body[:500]}")
    return json.loads(body)


def search_gigs(keyword: str, page: int = 1) -> dict:
    encoded = keyword.replace(" ", "%20")
    # fiverr4 endpoint — offset-based pagination, 48 per page
    offset = (page - 1) * 48
    return api_get(f"/search?query={encoded}&offset={offset}&filter=best_selling")


def get_gig_details(gig_id: str) -> dict:
    return api_get(f"/gig?gig_id={gig_id}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n=== Fiverr Demand Scraper ===\n")

    rows     = []
    seen_ids = set()

    for keyword in KEYWORDS:
        print(f"\nKeyword: '{keyword}'")
        page = 1

        while True:
            if MAX_PAGES and page > MAX_PAGES:
                break

            print(f"  Page {page}...")
            try:
                data = search_gigs(keyword, page)
            except Exception as e:
                print(f"  Search error: {e}")
                break

            # Debug: show top-level keys on first page so we can tune if needed
            if page == 1:
                print(f"  Response keys: {list(data.keys())[:10]}")

            # Normalize response — different RapidAPI endpoints vary
            gigs = (
                data.get("gigs") or
                data.get("results") or
                data.get("items") or
                data.get("data", {}).get("gigs") or
                data.get("data", {}).get("results") or
                (data.get("data") if isinstance(data.get("data"), list) else None) or
                []
            )

            if not gigs:
                print(f"  No gigs on page {page} — done.")
                break

            print(f"  Found {len(gigs)} gigs on page {page}")

            for gig in gigs:
                gig_id = str(gig.get("id") or gig.get("gig_id") or "")
                if not gig_id or gig_id in seen_ids:
                    continue
                seen_ids.add(gig_id)

                title = gig.get("title") or gig.get("gig_title") or ""
                url   = gig.get("url") or gig.get("gig_url") or ""
                if url and not url.startswith("http"):
                    url = "https://www.fiverr.com" + url

                # orders in queue may be in search result or need gig detail call
                orders = (
                    gig.get("orders_in_queue") or
                    gig.get("queue") or
                    gig.get("queue_size") or
                    ""
                )

                # if not in search result, fetch gig detail page
                if not orders and gig_id:
                    try:
                        detail = get_gig_details(gig_id)
                        orders = (
                            detail.get("orders_in_queue") or
                            detail.get("queue") or
                            detail.get("data", {}).get("orders_in_queue") or
                            ""
                        )
                        time.sleep(0.5)
                    except Exception:
                        pass

                rows.append({
                    "keyword":         keyword,
                    "title":           title,
                    "orders_in_queue": str(orders) if orders else "",
                    "url":             url,
                })

            page += 1
            time.sleep(1.0)

    # Sort by orders desc
    rows.sort(
        key=lambda r: int(r["orders_in_queue"]) if r["orders_in_queue"].isdigit() else 0,
        reverse=True,
    )

    out = Path(OUTPUT)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["keyword", "title", "orders_in_queue", "url"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n✓ Saved {len(rows)} gigs → {out}")
    print("\n--- Top 10 by orders in queue ---")
    print(f"{'Orders':>7}  {'Keyword':<22} {'Title'}")
    print("-" * 80)
    for r in rows[:10]:
        orders = r["orders_in_queue"] or "-"
        print(f"{orders:>7}  {r['keyword']:<22} {r['title'][:50]}")


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        raise SystemExit(1)
