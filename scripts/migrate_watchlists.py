#!/usr/bin/env python3
"""
One-time migration: Score-First Watchlist Architecture.

Extracts CORE tickers from all portfolios, writes them to core_watchlist.jsonl,
then wipes watchlist.jsonl files so they're rebuilt fresh by the new score-first process.

Run once before the first new-style scan:
    python3 scripts/migrate_watchlists.py [--dry-run]

After running, the next `watchlist_manager.py --update` for each portfolio
will use the new score-first flow and rebuild the watchlist from scratch.
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
PORTFOLIOS_DIR = DATA_DIR / "portfolios"


def extract_core_tickers(watchlist_path: Path) -> list:
    """Read watchlist.jsonl and return all entries with source='CORE'."""
    core = []
    if not watchlist_path.exists():
        return core
    with open(watchlist_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if isinstance(entry, dict) and entry.get("source") == "CORE":
                    core.append(entry)
            except Exception:
                continue
    return core


def migrate_portfolio(portfolio_id: str, dry_run: bool = False) -> dict:
    """Migrate one portfolio. Returns summary dict."""
    portfolio_dir = PORTFOLIOS_DIR / portfolio_id
    if not portfolio_dir.exists():
        return {"portfolio": portfolio_id, "status": "skipped", "reason": "directory not found"}

    watchlist_path = portfolio_dir / "watchlist.jsonl"
    core_watchlist_path = portfolio_dir / "core_watchlist.jsonl"

    if not watchlist_path.exists():
        return {"portfolio": portfolio_id, "status": "skipped", "reason": "no watchlist.jsonl"}

    # Count all entries
    total_entries = sum(1 for line in open(watchlist_path) if line.strip())

    # Extract CORE entries
    core_entries = extract_core_tickers(watchlist_path)
    core_tickers = [e["ticker"] for e in core_entries]

    # Check if core_watchlist.jsonl already has entries (don't duplicate)
    existing_core_tickers: set = set()
    if core_watchlist_path.exists():
        with open(core_watchlist_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    existing_core_tickers.add(e.get("ticker", ""))
                except Exception:
                    continue

    new_core_entries = [e for e in core_entries if e["ticker"] not in existing_core_tickers]

    print(f"\n  {portfolio_id}:")
    print(f"    Total watchlist entries: {total_entries}")
    print(f"    CORE tickers found: {len(core_tickers)} — {core_tickers}")
    print(f"    New entries to add to core_watchlist.jsonl: {len(new_core_entries)}")

    if not dry_run:
        # Append new CORE entries to core_watchlist.jsonl
        if new_core_entries:
            with open(core_watchlist_path, "a") as f:
                for e in new_core_entries:
                    f.write(json.dumps(e) + "\n")
            print(f"    Wrote {len(new_core_entries)} entries to core_watchlist.jsonl")

        # Wipe watchlist.jsonl — will be rebuilt on next score-first scan
        watchlist_path.write_text("")
        print(f"    Cleared watchlist.jsonl ({total_entries} entries removed)")
    else:
        print(f"    [DRY RUN] Would write {len(new_core_entries)} CORE entries and clear watchlist.jsonl")

    return {
        "portfolio": portfolio_id,
        "status": "migrated",
        "total_wiped": total_entries,
        "core_preserved": len(core_tickers),
    }


def main():
    parser = argparse.ArgumentParser(description="Migrate to score-first watchlist architecture")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    parser.add_argument("--portfolio", default=None, help="Migrate only this portfolio (default: all)")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN — no changes will be made\n")

    if args.portfolio:
        portfolios = [args.portfolio]
    else:
        portfolios = [p.name for p in PORTFOLIOS_DIR.iterdir() if p.is_dir()]
        portfolios.sort()

    print(f"Migrating {len(portfolios)} portfolio(s) to score-first watchlist architecture...")

    results = []
    for portfolio_id in portfolios:
        result = migrate_portfolio(portfolio_id, dry_run=args.dry_run)
        results.append(result)

    migrated = [r for r in results if r["status"] == "migrated"]
    total_wiped = sum(r.get("total_wiped", 0) for r in migrated)
    total_core = sum(r.get("core_preserved", 0) for r in migrated)

    print(f"\n{'='*50}")
    print(f"Migration {'(DRY RUN) ' if args.dry_run else ''}complete:")
    print(f"  Portfolios processed: {len(migrated)}")
    print(f"  Total watchlist entries cleared: {total_wiped}")
    print(f"  CORE tickers preserved: {total_core}")
    print(f"\nNext step: run a scan for each portfolio to rebuild watchlists.")
    print(f"  python3 scripts/watchlist_manager.py --update --portfolio <id>")


if __name__ == "__main__":
    main()
