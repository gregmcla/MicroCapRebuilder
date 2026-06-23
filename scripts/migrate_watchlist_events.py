#!/usr/bin/env python3
"""One-time backfill: seed watchlist_events.jsonl from current watchlist.jsonl state.

Run once per portfolio after deploying Feature #17 so the position-lineage
timeline isn't empty for tickers currently active in the watchlist (we'd
otherwise only see new add/remove events from this point forward).

Idempotent: if watchlist_events.jsonl already has an "added" event for a
ticker, this script won't double-add. Removed-ticker history is irrecoverable
(only current state exists on disk).

Usage:
  python3 scripts/migrate_watchlist_events.py --portfolio max
  python3 scripts/migrate_watchlist_events.py --all-active
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from watchlist_events import record_watchlist_event, read_events


def backfill_portfolio(portfolio_id: str) -> int:
    """Read current watchlist.jsonl for the portfolio, emit `added` events for
    any ticker not already in watchlist_events.jsonl. Returns count written."""
    wl_path = Path(__file__).parent.parent / "data" / "portfolios" / portfolio_id / "watchlist.jsonl"
    if not wl_path.exists():
        print(f"[{portfolio_id}] no watchlist.jsonl — skipping")
        return 0

    existing = {(e.get("ticker") or "").upper() for e in read_events(portfolio_id) if e.get("type") == "added"}

    written = 0
    for line in wl_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        ticker = (entry.get("ticker") or "").upper()
        if not ticker or ticker in existing:
            continue
        added_date = entry.get("added_date") or ""
        # Use noon as the time so the ordering relative to same-day BUYs is
        # roughly correct without forcing us to invent a precise minute.
        ts = f"{added_date}T12:00:00" if added_date else None
        source = entry.get("source") or "backfill"
        ok = record_watchlist_event(
            portfolio_id=portfolio_id,
            ticker=ticker,
            kind="added",
            reason=f"backfill:{source.lower()}",
            source=source.lower(),
            ts=ts,
        )
        if ok:
            written += 1
    print(f"[{portfolio_id}] backfilled {written} watchlist add events")
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio", help="single portfolio id")
    parser.add_argument("--all-active", action="store_true", help="backfill all active portfolios")
    args = parser.parse_args()

    if not args.portfolio and not args.all_active:
        parser.error("either --portfolio or --all-active is required")

    if args.portfolio:
        backfill_portfolio(args.portfolio)
        return

    # All active
    registry_path = Path(__file__).parent.parent / "data" / "portfolios.json"
    if not registry_path.exists():
        print("no portfolios.json — abort")
        return
    data = json.loads(registry_path.read_text())
    total = 0
    for pid, meta in (data.get("portfolios") or {}).items():
        if not meta.get("active"):
            continue
        total += backfill_portfolio(pid)
    print(f"backfilled {total} total events across active portfolios")


if __name__ == "__main__":
    main()
