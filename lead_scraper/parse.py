"""
Parses raw state files into the standard schema.
Handles CSV and Excel, normalizes columns, filters to active licenses only.
"""

import re
from pathlib import Path

import pandas as pd

from config import OUTPUT_FIELDS


PHONE_RE = re.compile(r"[\D]")


def normalize_phone(val) -> str:
    if not val or pd.isna(val):
        return ""
    digits = PHONE_RE.sub("", str(val))
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits[0] == "1":
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return str(val).strip()


def normalize_email(val) -> str:
    if not val or pd.isna(val):
        return ""
    e = str(val).strip().lower()
    return e if "@" in e else ""


def load_raw(path: Path, cfg: dict) -> pd.DataFrame:
    fmt = cfg.get("format", "csv")
    if fmt == "excel":
        df = pd.read_excel(
            path,
            sheet_name=cfg.get("sheet", 0),
            skiprows=cfg.get("skip_rows", 0),
            dtype=str,
            engine="openpyxl",
        )
    else:
        enc = cfg.get("encoding", "utf-8")
        try:
            df = pd.read_csv(path, dtype=str, encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(path, dtype=str, encoding="latin-1", low_memory=False)
    return df


def remap_columns(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    # Normalize source column names (strip whitespace, case-insensitive match)
    col_map_lower = {k.strip().lower(): v for k, v in col_map.items()}
    rename = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in col_map_lower:
            rename[col] = col_map_lower[key]
    df = df.rename(columns=rename)
    return df


def filter_active(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    fc = cfg.get("filter_col")
    fv = cfg.get("filter_val", [])
    if not fc or not fv:
        return df
    # Find the actual column name after remapping
    col_map_lower = {k.strip().lower(): v for k, v in cfg["col_map"].items()}
    mapped = col_map_lower.get(fc.strip().lower(), fc)
    if mapped not in df.columns and fc not in df.columns:
        print(f"    [warn] filter column '{fc}' not found — keeping all rows")
        return df
    target_col = mapped if mapped in df.columns else fc
    fv_lower = [v.lower() for v in fv]
    mask = df[target_col].fillna("").str.strip().str.lower().isin(fv_lower)
    return df[mask]


def parse(path: Path, cfg: dict) -> pd.DataFrame:
    df = load_raw(path, cfg)
    print(f"    raw rows: {len(df):,}")

    df = remap_columns(df, cfg["col_map"])
    df = filter_active(df, cfg)
    print(f"    active rows: {len(df):,}")

    # Ensure all standard fields exist
    for field in OUTPUT_FIELDS:
        if field not in df.columns:
            df[field] = ""

    # Normalize phone + email
    if "phone" in df.columns:
        df["phone"] = df["phone"].apply(normalize_phone)
    if "email" in df.columns:
        df["email"] = df["email"].apply(normalize_email)

    # Fill metadata
    df["category"] = cfg["category"]
    df["state"] = cfg["state"]
    df["source_url"] = cfg["url"]

    # Strip whitespace from all string columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df[OUTPUT_FIELDS]
