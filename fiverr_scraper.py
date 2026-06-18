"""
Fiverr Demand Scraper
Pulls gig title, orders in queue, and URL for target keywords.
Sorted by orders desc — highest demand surfaces first.
"""

import asyncio
import csv
import random
import re
import time
from pathlib import Path

from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

KEYWORDS = [
    "logo design",
    "video editing",
    "social media management",
]

PAGES_PER_KEYWORD = 3   # 48 gigs/page → ~144 gigs per keyword
OUTPUT = "fiverr_demand.csv"

HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

async def get_gig_urls(page, keyword: str, max_pages: int) -> list[tuple[str, str]]:
    """Return list of (title, url) from search results pages."""
    results = []
    for n in range(1, max_pages + 1):
        url = (
            f"https://www.fiverr.com/search/gigs"
            f"?query={keyword.replace(' ', '+')}"
            f"&sort=best_selling&page={n}"
        )
        print(f"  Searching page {n}: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        try:
            await page.wait_for_selector("[class*='gig-card']", timeout=15000)
        except Exception:
            print(f"  No gig cards found on page {n}, stopping pagination.")
            break

        cards = await page.query_selector_all("[class*='gig-card']")
        for card in cards:
            # title
            title_el = await card.query_selector("h3, [class*='title']")
            title = (await title_el.inner_text()).strip() if title_el else ""

            # url
            link_el = await card.query_selector("a")
            href = await link_el.get_attribute("href") if link_el else ""
            if href and not href.startswith("http"):
                href = "https://www.fiverr.com" + href

            if title and href:
                results.append((title, href))

        await asyncio.sleep(random.uniform(1.5, 2.5))

    return results


async def get_orders_in_queue(page, gig_url: str) -> str:
    """Visit a gig page and extract the orders-in-queue count."""
    try:
        await page.goto(gig_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(1.0, 2.0))

        content = await page.content()
        match = re.search(r"(\d+)\s+orders?\s+in\s+queue", content, re.IGNORECASE)
        if match:
            return match.group(1)

        # fallback: check visible text
        els = await page.query_selector_all("*")
        for el in els:
            try:
                text = (await el.inner_text()).strip()
                m = re.search(r"(\d+)\s+orders?\s+in\s+queue", text, re.IGNORECASE)
                if m:
                    return m.group(1)
            except Exception:
                continue
    except Exception as e:
        print(f"    Error fetching gig: {e}")

    return ""


async def main():
    print("\n=== Fiverr Demand Scraper ===\n")

    rows = []
    seen_urls = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=HEADERS["user-agent"],
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        for keyword in KEYWORDS:
            print(f"\nKeyword: '{keyword}'")
            gigs = await get_gig_urls(page, keyword, PAGES_PER_KEYWORD)
            print(f"  Found {len(gigs)} gigs")

            for title, url in gigs:
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                print(f"  Checking: {title[:60]}...")
                orders = await get_orders_in_queue(page, url)
                print(f"    Orders in queue: {orders or 'n/a'}")

                rows.append({
                    "keyword":          keyword,
                    "title":            title,
                    "orders_in_queue":  orders,
                    "url":              url,
                })

        await browser.close()

    # Sort by orders desc (blank = 0)
    rows.sort(key=lambda r: int(r["orders_in_queue"]) if r["orders_in_queue"] else 0, reverse=True)

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
    asyncio.run(main())
