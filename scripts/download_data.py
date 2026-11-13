"""Download FIRMS country-yearly hotspot CSVs (Standard Processing, no API key needed).

Usage:
  python scripts/download_data.py --country Pakistan --start 2000 --end 2025
  python scripts/download_data.py --country Pakistan --sources modis viirs-snpp --dry-run

Files go to data/raw/<source>/<source>_<year>_<Country>.csv
Country names use underscores, e.g. United_States, Sri_Lanka. Check the exact name at
https://firms.modaps.eosdis.nasa.gov/country/
"""
import argparse
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://firms.modaps.eosdis.nasa.gov/data/country"
FIRST_YEAR = {"modis": 2000, "viirs-snpp": 2012, "viirs-jpss1": 2018}


def ssl_context():
    try:
        import certifi  # optional, fixes most Windows certificate errors
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--country", default="Pakistan")
    p.add_argument("--start", type=int, default=2000)
    p.add_argument("--end", type=int, default=2025)
    p.add_argument("--sources", nargs="+", default=list(FIRST_YEAR))
    p.add_argument("--out", default="data/raw")
    p.add_argument("--retries", type=int, default=8)
    p.add_argument("--dry-run", action="store_true", help="only print URLs")
    a = p.parse_args()

    ctx = ssl_context()
    failed = []
    for src in a.sources:
        for year in range(max(a.start, FIRST_YEAR.get(src, a.start)), a.end + 1):
            name = f"{src}_{year}_{a.country}.csv"
            url = f"{BASE}/{src}/{year}/{name}"
            dest = Path(a.out) / src / name
            if a.dry_run:
                print(url)
                continue
            if dest.exists() and dest.stat().st_size > 0:
                print(f"skip  {dest} (already there)")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            for attempt in range(1, a.retries + 1):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "spaceapps-firecalendar"})
                    # timeout is per socket operation, so a short value still allows big files
                    with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
                        data = r.read()
                    tmp = dest.with_suffix(".part")
                    tmp.write_bytes(data)
                    tmp.replace(dest)
                    print(f"ok    {dest}  {len(data)/1e6:.1f} MB")
                    break
                except urllib.error.HTTPError as e:
                    print(f"miss  {url}  HTTP {e.code} (no data for this year/country?)")
                    break
                except Exception as e:  # network / SSL problems
                    if attempt < a.retries:
                        wait = 3 * attempt
                        print(f"retry {attempt}/{a.retries - 1} in {wait}s  {name}  ({e.__class__.__name__})")
                        time.sleep(wait)
                    else:
                        print(f"FAIL  {url}  {e}")
                        failed.append(url)
            time.sleep(1)

    if failed:
        print("\nSome downloads failed. Just run the same command again: finished files are skipped.")
        print("If the error mentions SSL/certificate: pip install certifi")
        print("Or open these links in a browser and save them into data/raw/<source>/ :")
        for u in failed:
            print("  " + u)
        sys.exit(1)
    print("\nDone.")


if __name__ == "__main__":
    main()
