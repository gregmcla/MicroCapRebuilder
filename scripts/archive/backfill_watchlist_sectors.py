#!/usr/bin/env python3
"""
One-time script: backfill missing sector data in watchlist.jsonl files.
Fetches yf.Ticker.info for each entry with a blank sector field.
Uses concurrent threads (max 8) with 6s per-ticker timeout.
"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data" / "portfolios"

PORTFOLIOS = ["microcap", "ai"]  # largeboi and new already have sector data
TIMEOUT_S = 6
MAX_WORKERS = 8


def fetch_sector(ticker: str) -> str | None:
    """Fetch sector from yfinance .info with a hard timeout. Returns None on failure."""
    result: list[str | None] = [None]

    def _fetch():
        try:
            info = yf.Ticker(ticker).info
            result[0] = info.get("sector") or info.get("sectorDisp") or ""
        except Exception as e:
            print(f"Warning: sector fetch failed for {ticker}: {e}")

    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(TIMEOUT_S)
    return result[0]


def backfill_portfolio(portfolio_id: str) -> None:
    wl_path = DATA_DIR / portfolio_id / "watchlist.jsonl"
    if not wl_path.exists():
        print(f"[{portfolio_id}] No watchlist found, skipping.")
        return

    entries = []
    for line in wl_path.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))

    needs_sector = [
        (i, e) for i, e in enumerate(entries)
        if not e.get("sector", "").strip()
    ]

    if not needs_sector:
        print(f"[{portfolio_id}] All entries have sector data. Nothing to do.")
        return

    print(f"[{portfolio_id}] Fetching sectors for {len(needs_sector)} entries...")

    updated = 0
    failed = 0

    def task(idx_entry):
        idx, entry = idx_entry
        ticker = entry["ticker"]
        sector = fetch_sector(ticker)
        return idx, ticker, sector

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(task, ie): ie for ie in needs_sector}
        for i, future in enumerate(as_completed(futures), 1):
            idx, ticker, sector = future.result()
            if sector:
                entries[idx]["sector"] = sector
                print(f"  [{i}/{len(needs_sector)}] {ticker:8} → {sector}")
                updated += 1
            else:
                print(f"  [{i}/{len(needs_sector)}] {ticker:8} → (no data)")
                failed += 1

    # Write back
    wl_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    print(f"[{portfolio_id}] Done. {updated} updated, {failed} failed/skipped.\n")


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else PORTFOLIOS
    for pid in targets:
        backfill_portfolio(pid)
    print("Backfill complete.")
