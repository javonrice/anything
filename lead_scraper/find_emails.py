"""
Enrich NPI leads with a website + contact email, found via public web search
and each agency's own published contact info.

This step is heavier and slower than npi_leads.py, and less reliable —
DuckDuckGo's HTML endpoint isn't an official API, so keep volume modest and
don't hammer it. If you'd rather stay fully on the safe/official side, swap
`find_website()` for the Google Places Text Search API (paid, has a free
monthly credit) and skip the DuckDuckGo lookup entirely.

Usage:
    python find_emails.py --in leads_tx.csv --out leads_tx_enriched.csv --limit 50
"""
import argparse
import csv
import re
import sys
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; lead-research/1.0)"}
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
SKIP_DOMAINS = {
    "facebook.com", "yelp.com", "linkedin.com", "instagram.com", "twitter.com",
    "x.com", "npidb.org", "npino.com", "healthgrades.com", "bbb.org",
    "yellowpages.com", "mapquest.com", "google.com", "wikipedia.org",
}
CONTACT_PATHS = ["", "/contact", "/contact-us", "/about", "/about-us"]


def find_website(org_name: str, city: str, state: str):
    query = f"{org_name} {city} {state} home health"
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None
    links = re.findall(r'href="(https?://[^"]+)"', resp.text)
    for link in links:
        domain = re.sub(r"^https?://(www\.)?", "", link).split("/")[0].lower()
        if domain and not any(skip in domain for skip in SKIP_DOMAINS):
            return f"https://{domain}"
    return None


def find_email_on_site(website: str):
    domain = re.sub(r"^https?://(www\.)?", "", website).split("/")[0].lower()
    candidates = []
    for path in CONTACT_PATHS:
        try:
            resp = requests.get(website.rstrip("/") + path, headers=HEADERS, timeout=10)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        found = EMAIL_RE.findall(resp.text)
        candidates.extend(found)
        if candidates:
            break
        time.sleep(0.5)
    if not candidates:
        return ""
    same_domain = [e for e in candidates if e.lower().endswith(domain)]
    pool = same_domain or candidates
    preferred = [e for e in pool if e.lower().split("@")[0] in ("info", "contact", "office", "admin", "hello")]
    return (preferred or pool)[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--out", dest="outfile", required=True)
    ap.add_argument("--limit", type=int, default=50, help="Max leads to process this run")
    ap.add_argument("--delay", type=float, default=2.0, help="Seconds between leads")
    args = ap.parse_args()

    with open(args.infile, newline="") as f:
        rows = list(csv.DictReader(f))

    fieldnames = list(rows[0].keys()) + ["website", "email"] if rows else []
    with open(args.outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, row in enumerate(rows[: args.limit]):
            print(f"[{i+1}/{min(args.limit, len(rows))}] {row['org_name']}", file=sys.stderr)
            website = find_website(row["org_name"], row["city"], row["state"])
            email = find_email_on_site(website) if website else ""
            row["website"] = website or ""
            row["email"] = email
            writer.writerow(row)
            time.sleep(args.delay)

    print(f"Enriched leads written to {args.outfile}", file=sys.stderr)


if __name__ == "__main__":
    main()
