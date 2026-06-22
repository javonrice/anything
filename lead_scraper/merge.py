"""
Combines all per-state parsed CSVs into leads_master.csv.
Deduplicates by phone first, then email.
"""

from pathlib import Path

import pandas as pd

from config import OUTPUT_FIELDS

PARSED_DIR = Path("parsed_data")
OUTPUT = Path("leads_master.csv")


def merge():
    files = sorted(PARSED_DIR.glob("*.csv"))
    if not files:
        print("No parsed files found in parsed_data/")
        return

    frames = [pd.read_csv(f, dtype=str) for f in files]
    df = pd.concat(frames, ignore_index=True)
    print(f"Total before dedup: {len(df):,}")

    # Dedup by phone (non-empty)
    has_phone = df["phone"].str.len() > 0
    phone_dupes = df[has_phone].duplicated(subset=["phone"], keep="first")
    df = df[~(has_phone & phone_dupes)]

    # Dedup by email (non-empty)
    has_email = df["email"].str.len() > 0
    email_dupes = df[has_email].duplicated(subset=["email"], keep="first")
    df = df[~(has_email & email_dupes)]

    print(f"Total after dedup:  {len(df):,}")

    # Sort
    df = df.sort_values(["state", "category", "full_name"])

    df.to_csv(OUTPUT, index=False)
    print(f"\n✓ Saved {len(df):,} leads → {OUTPUT}")

    # Summary table
    print("\n--- Breakdown ---")
    summary = df.groupby(["state", "category"]).size().reset_index(name="count")
    for _, row in summary.iterrows():
        has_email = (df[(df["state"] == row["state"]) & (df["category"] == row["category"])]["email"].str.len() > 0).sum()
        has_phone = (df[(df["state"] == row["state"]) & (df["category"] == row["category"])]["phone"].str.len() > 0).sum()
        print(f"  {row['state']} {row['category']:<15} {row['count']:>7,}  |  email: {has_email:>6,}  phone: {has_phone:>6,}")


if __name__ == "__main__":
    merge()
