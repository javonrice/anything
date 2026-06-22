"""
Downloads raw licensee files from state URLs.
Caches to ./raw_data/ — skips re-download if file exists from today.
"""

import hashlib
import os
import time
from datetime import date
from pathlib import Path

import requests

RAW_DIR = Path("raw_data")
RAW_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def cache_path(state_cfg: dict) -> Path:
    key = f"{state_cfg['state']}_{state_cfg['category']}_{date.today()}"
    slug = hashlib.md5(key.encode()).hexdigest()[:8]
    ext = "xlsx" if state_cfg.get("format") == "excel" else "csv"
    return RAW_DIR / f"{state_cfg['state']}_{state_cfg['category']}_{slug}.{ext}"


def download(state_cfg: dict, force: bool = False) -> Path | None:
    dest = cache_path(state_cfg)
    if dest.exists() and not force:
        print(f"  [cache] {dest.name}")
        return dest

    url = state_cfg["url"]
    print(f"  [download] {state_cfg['state']} {state_cfg['category']} ...")
    try:
        session = requests.Session()
        resp = session.get(url, headers=HEADERS, timeout=60, stream=True)
        resp.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        size_kb = dest.stat().st_size // 1024
        print(f"  [ok] {dest.name}  ({size_kb:,} KB)")
        time.sleep(1.0)
        return dest

    except Exception as e:
        print(f"  [FAIL] {state_cfg['state']} {state_cfg['category']}: {e}")
        if dest.exists():
            dest.unlink()
        return None
