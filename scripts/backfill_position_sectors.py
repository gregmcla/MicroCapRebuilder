#!/usr/bin/env python3
"""
One-time backfill: add sector column to positions.csv for all active portfolios.

Priority: watchlist.jsonl → sector_mapping.json → yfinance live fetch
"""
import json
import sys
import threading
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))

PORTFOLIOS = ["microcap", "ai", "new", "largeboi"]
DATA_DIR = Path(__file__).parent.parent / "data" / "portfolios"
SECTOR_FILE = Path(__file__).parent.parent / "data" / "sector_mapping.json"


def fetch_sector_yf(ticker: str, timeout: int = 5) -> str:
    result = [None]

    def _fetch():
        try:
            info = yf.Ticker(ticker).info
            result[0] = info.get("sector", "Unknown")
        except Exception as e:
            print(f"Warning: sector fetch failed for {ticker}: {e}")
            result[0] = "Unknown"

    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout)
    return result[0] or "Unknown"


def main():
    static_map = json.loads(SECTOR_FILE.read_text()) if SECTOR_FILE.exists() else {}
    updated_static = dict(static_map)
    total_backfilled = 0

    for pid in PORTFOLIOS:
        pos_file = DATA_DIR / pid / "positions.csv"
        if not pos_file.exists():
            continue

        # Load watchlist sectors for this portfolio
        wl_file = DATA_DIR / pid / "watchlist.jsonl"
        wl_sectors = {}
        if wl_file.exists():
            for line in wl_file.read_text().splitlines():
                if line.strip():
                    w = json.loads(line)
                    if w.get("sector"):
                        wl_sectors[w["ticker"]] = w["sector"]

        df = pd.read_csv(pos_file)
        if "sector" not in df.columns:
            df["sector"] = ""

        changed = 0
        for idx, row in df.iterrows():
            ticker = row["ticker"]
            existing = str(row.get("sector", "")).strip()
            if existing and existing not in ("nan", "Unknown", ""):
                print(f"  {pid}/{ticker}: already has sector '{existing}'")
                continue

            # Priority: watchlist → static map → yfinance
            sector = wl_sectors.get(ticker) or updated_static.get(ticker)
            if not sector:
                print(f"  {pid}/{ticker}: fetching from yfinance...", end="", flush=True)
                sector = fetch_sector_yf(ticker)
                print(f" {sector}")
                updated_static[ticker] = sector
            else:
                print(f"  {pid}/{ticker}: {sector} (cached)")

            if sector and sector != "Unknown":
                df.at[idx, "sector"] = sector
                changed += 1

        if changed:
            df.to_csv(pos_file, index=False)
            print(f"  ✓ {pid}: backfilled {changed} positions")
            total_backfilled += changed

    # Persist updated static mapping
    if updated_static != static_map:
        SECTOR_FILE.write_text(json.dumps(updated_static, indent=2, sort_keys=True))
        new_count = len(updated_static) - len(static_map)
        print(f"\nUpdated sector_mapping.json (+{new_count} new entries)")

    print(f"\nDone. Total positions backfilled: {total_backfilled}")


if __name__ == "__main__":
    main()
