#!/usr/bin/env python3
"""
One-time migration: move existing flat data/ files into data/portfolios/microcap/.

This script:
1. Creates data/portfolios/microcap/ directory
2. COPIES config.json (keeps original as global fallback)
3. MOVES per-portfolio data files (positions, transactions, snapshots, etc.)
4. Creates data/portfolios.json registry with microcap as the default portfolio

Safe to re-run: skips files that already exist at the destination.
"""

import json
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
PORTFOLIO_ID = "microcap"
PORTFOLIO_DIR = DATA_DIR / "portfolios" / PORTFOLIO_ID
REGISTRY_FILE = DATA_DIR / "portfolios.json"

# Files to MOVE from data/ to data/portfolios/microcap/
MOVE_FILES = [
    "positions.csv",
    "positions_paper.csv",
    "transactions.csv",
    "transactions_paper.csv",
    "daily_snapshots.csv",
    "daily_snapshots_paper.csv",
    "watchlist.jsonl",
    "post_mortems.csv",
    "stale_prices.json",
]


def migrate():
    print("=" * 60)
    print("  MicroCapRebuilder: Migrate to Multi-Portfolio Layout")
    print("=" * 60)

    # 1. Create portfolio directory
    print(f"\n1. Creating directory: {PORTFOLIO_DIR}")
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    print("   Done.")

    # 2. Copy config.json
    src_config = DATA_DIR / "config.json"
    dst_config = PORTFOLIO_DIR / "config.json"
    print(f"\n2. Copying config.json -> portfolios/{PORTFOLIO_ID}/config.json")
    if dst_config.exists():
        print("   Skipped (already exists at destination).")
    elif not src_config.exists():
        print("   Skipped (source config.json not found).")
    else:
        shutil.copy2(src_config, dst_config)
        print("   Copied.")

    # 3. Move data files
    print(f"\n3. Moving data files to portfolios/{PORTFOLIO_ID}/")
    for filename in MOVE_FILES:
        src = DATA_DIR / filename
        dst = PORTFOLIO_DIR / filename
        if dst.exists():
            print(f"   {filename}: skipped (already at destination)")
        elif not src.exists():
            print(f"   {filename}: skipped (not found in data/)")
        else:
            shutil.move(str(src), str(dst))
            print(f"   {filename}: moved")

    # 4. Create registry
    print(f"\n4. Creating registry: {REGISTRY_FILE}")
    if REGISTRY_FILE.exists():
        print("   Skipped (registry already exists).")
    else:
        from datetime import datetime

        registry = {
            "default_portfolio": PORTFOLIO_ID,
            "portfolios": {
                PORTFOLIO_ID: {
                    "id": PORTFOLIO_ID,
                    "name": "Micro-Cap Portfolio",
                    "universe": "microcap",
                    "created": datetime.now().isoformat(timespec="seconds"),
                    "starting_capital": 50000.0,
                    "active": True,
                }
            },
        }
        with open(REGISTRY_FILE, "w") as f:
            json.dump(registry, f, indent=2)
        print("   Created with microcap as default portfolio.")

    # 5. Summary
    print("\n" + "=" * 60)
    print("  Migration complete!")
    print(f"  Portfolio dir: {PORTFOLIO_DIR}")
    print(f"  Registry: {REGISTRY_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    migrate()
