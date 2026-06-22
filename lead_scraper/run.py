"""
Orchestrator: download → parse → merge for all configured states.
Run: python run.py
Options:
  --states TX,GA     Only run specific states (comma-separated)
  --category real_estate|insurance   Only run one category
  --force            Re-download even if cached
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from config import OUTPUT_FIELDS, STATES
from download import download
from merge import merge
from parse import parse

PARSED_DIR = Path("parsed_data")
PARSED_DIR.mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--states", default="")
    parser.add_argument("--category", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    filter_states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    filter_cat = args.category.strip().lower()

    targets = STATES
    if filter_states:
        targets = [c for c in targets if c["state"] in filter_states]
    if filter_cat:
        targets = [c for c in targets if c["category"] == filter_cat]

    if not targets:
        print("No matching state configs.")
        sys.exit(1)

    print(f"\n=== Lead Scraper ===")
    print(f"Running {len(targets)} state/category combos\n")

    success = 0
    for cfg in targets:
        label = f"{cfg['state']} / {cfg['category']}"
        print(f"\n[{label}]")

        raw = download(cfg, force=args.force)
        if not raw:
            print(f"  Skipping {label} — download failed")
            continue

        try:
            df = parse(raw, cfg)
        except Exception as e:
            print(f"  [PARSE ERROR] {label}: {e}")
            continue

        out = PARSED_DIR / f"{cfg['state']}_{cfg['category']}.csv"
        df.to_csv(out, index=False)
        print(f"  → {out.name}  ({len(df):,} rows)")
        success += 1

    print(f"\n\n=== Merge ===")
    merge()
    print(f"\nDone. {success}/{len(targets)} sources succeeded.")


if __name__ == "__main__":
    main()
