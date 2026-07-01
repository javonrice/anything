"""
Pull home health agency leads from the NPI Registry (npiregistry.cms.hhs.gov).

This is public U.S. government data (NPPES) meant for exactly this kind of
lookup, so there's no ToS problem here. It gives org name, address, and
phone — it does NOT include email or website, so run find_emails.py next.

Usage:
    python npi_leads.py --state TX --out leads_tx.csv
    python npi_leads.py --state TX --state CA --out leads.csv
"""
import argparse
import csv
import sys
import time

import requests

API_URL = "https://npiregistry.cms.hhs.gov/api/"
PAGE_SIZE = 200
MAX_SKIP = 1000  # NPI registry caps skip+limit at 1200 total results per query

FIELDS = [
    "npi", "org_name", "address_1", "address_2",
    "city", "state", "postal_code", "phone", "taxonomy",
]


def fetch_state(state: str, taxonomy_description: str):
    skip = 0
    while skip <= MAX_SKIP:
        params = {
            "version": "2.1",
            "enumeration_type": "NPI-2",  # organizations, not individuals
            "taxonomy_description": taxonomy_description,
            "state": state,
            "limit": PAGE_SIZE,
            "skip": skip,
        }
        resp = requests.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return
        for r in results:
            yield parse_result(r)
        if len(results) < PAGE_SIZE:
            return
        skip += PAGE_SIZE
        time.sleep(0.3)  # be polite


def parse_result(r):
    basic = r.get("basic", {})
    org_name = basic.get("organization_name", "")
    addresses = r.get("addresses", [])
    loc = next((a for a in addresses if a.get("address_purpose") == "LOCATION"), None)
    loc = loc or (addresses[0] if addresses else {})
    taxonomies = r.get("taxonomies", [])
    primary_tax = next((t for t in taxonomies if t.get("primary")), taxonomies[0] if taxonomies else {})
    return {
        "npi": r.get("number", ""),
        "org_name": org_name,
        "address_1": loc.get("address_1", ""),
        "address_2": loc.get("address_2", ""),
        "city": loc.get("city", ""),
        "state": loc.get("state", ""),
        "postal_code": loc.get("postal_code", ""),
        "phone": loc.get("telephone_number", ""),
        "taxonomy": primary_tax.get("desc", ""),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", action="append", required=True, help="Two-letter state code, repeatable")
    ap.add_argument("--taxonomy", default="Home Health Agency", help="NPI taxonomy_description to search")
    ap.add_argument("--out", default="leads.csv")
    args = ap.parse_args()

    seen_npi = set()
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        total = 0
        for state in args.state:
            print(f"Fetching {args.taxonomy!r} agencies in {state}...", file=sys.stderr)
            for row in fetch_state(state, args.taxonomy):
                if row["npi"] in seen_npi:
                    continue
                seen_npi.add(row["npi"])
                writer.writerow(row)
                total += 1
        print(f"Wrote {total} leads to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
