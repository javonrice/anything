"""
Downloads raw licensee files from state sources.
Supports three strategies: direct URL, Socrata API, and link-discovery.
Caches to ./raw_data/ — skips re-download if file already exists today.
"""

import hashlib
import io
import time
import urllib.parse
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

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

SOCRATA_PAGE = 10_000  # rows per Socrata request


def cache_path(cfg: dict, suffix: str = "") -> Path:
    key = f"{cfg['state']}_{cfg['category']}_{date.today()}{suffix}"
    slug = hashlib.md5(key.encode()).hexdigest()[:8]
    ext = "xlsx" if cfg.get("format") == "excel" else "csv"
    return RAW_DIR / f"{cfg['state']}_{cfg['category']}_{slug}.{ext}"


# ---------------------------------------------------------------------------
# Strategy: direct URL
# ---------------------------------------------------------------------------

def _download_direct(url: str, dest: Path) -> Path | None:
    try:
        session = requests.Session()
        r = session.get(url, headers=HEADERS, timeout=60, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        return dest
    except Exception as e:
        print(f"    [direct fail] {url}: {e}")
        if dest.exists():
            dest.unlink()
        return None


# ---------------------------------------------------------------------------
# Strategy: Socrata open data
# ---------------------------------------------------------------------------

def _download_socrata(cfg: dict, dest: Path) -> Path | None:
    domain = cfg["socrata_domain"]
    ids = cfg.get("socrata_ids", [])

    for dataset_id in ids:
        url = f"https://{domain}/resource/{dataset_id}.csv"
        print(f"    [socrata] trying {url}")
        try:
            session = requests.Session()
            # Check if dataset exists first
            test = session.get(
                url,
                headers=HEADERS,
                params={"$limit": 1},
                timeout=30,
            )
            if test.status_code != 200:
                print(f"    [socrata skip] {dataset_id} → HTTP {test.status_code}")
                continue

            # Paginate and collect all rows
            rows = []
            offset = 0
            while True:
                r = session.get(
                    url,
                    headers=HEADERS,
                    params={"$limit": SOCRATA_PAGE, "$offset": offset},
                    timeout=120,
                )
                r.raise_for_status()
                text = r.text
                lines = text.strip().splitlines()
                if len(lines) <= 1:
                    break  # just header or empty
                if offset == 0:
                    rows.append(lines[0])  # header
                rows.extend(lines[1:])
                print(f"    [socrata] offset {offset}: +{len(lines)-1} rows")
                if len(lines) - 1 < SOCRATA_PAGE:
                    break
                offset += SOCRATA_PAGE
                time.sleep(0.5)

            with open(dest, "w", encoding="utf-8", newline="") as f:
                f.write("\n".join(rows))

            print(f"    [socrata ok] {dataset_id}: {len(rows)-1:,} rows")
            return dest

        except Exception as e:
            print(f"    [socrata fail] {dataset_id}: {e}")
            if dest.exists():
                dest.unlink()

    return None


# ---------------------------------------------------------------------------
# Strategy: discover download link on a page
# ---------------------------------------------------------------------------

def _discover_link(discover_url: str, patterns: list[str]) -> str | None:
    try:
        r = requests.get(discover_url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"    [discover fail] {discover_url}: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    patterns_lower = [p.lower() for p in patterns]

    # Find all <a> tags with href
    candidates = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = (a.get_text() or "").strip().lower()
        href_lower = href.lower()
        score = sum(1 for p in patterns_lower if p in text or p in href_lower)
        if score > 0:
            candidates.append((score, href, text))

    if not candidates:
        print(f"    [discover] no matching links on {discover_url}")
        # Print all links for debugging
        for a in soup.find_all("a", href=True)[:20]:
            print(f"      link: {a.get_text().strip()[:60]}  →  {a['href'][:80]}")
        return None

    candidates.sort(reverse=True)
    best_href = candidates[0][1]
    print(f"    [discover] found: {candidates[0][2][:60]} → {best_href[:80]}")

    # Make absolute if needed
    if best_href.startswith("http"):
        return best_href
    return urllib.parse.urljoin(discover_url, best_href)


def _download_discover(cfg: dict, dest: Path) -> Path | None:
    link = _discover_link(cfg["discover_url"], cfg.get("discover_pattern", []))
    if not link:
        return None
    return _download_direct(link, dest)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def download(cfg: dict, force: bool = False) -> Path | None:
    dest = cache_path(cfg)
    if dest.exists() and not force:
        print(f"  [cache] {dest.name}")
        return dest

    strategy = cfg.get("strategy", "direct")
    print(f"  [{strategy}] {cfg['state']} {cfg['category']} ...")

    if strategy == "direct":
        result = _download_direct(cfg["url"], dest)
    elif strategy == "socrata":
        result = _download_socrata(cfg, dest)
    elif strategy == "discover":
        result = _download_discover(cfg, dest)
    else:
        print(f"  [unknown strategy] {strategy}")
        return None

    if result:
        size_kb = dest.stat().st_size // 1024
        print(f"  [ok] {dest.name} ({size_kb:,} KB)")
        time.sleep(1.0)

    return result
