#!/usr/bin/env python3
"""
Watchlist Manager Module for Mommy Bot.

Manages the dynamic watchlist with:
- Core watchlist (manually curated, always included)
- Discovered stocks (from discovery scans)
- Automatic maintenance (mark stale, remove old)
- Enhanced schema with metadata

Usage:
    from watchlist_manager import WatchlistManager

    manager = WatchlistManager()
    manager.update_watchlist()  # Run discovery and update
    tickers = manager.get_active_tickers()  # Get trading candidates
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
import shutil

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
BACKUP_DIR = SCRIPT_DIR.parent / "backup"
CONFIG_FILE = DATA_DIR / "config.json"
WATCHLIST_FILE = DATA_DIR / "watchlist.jsonl"
CORE_WATCHLIST_FILE = DATA_DIR / "core_watchlist.jsonl"


@dataclass
class WatchlistEntry:
    """Enhanced watchlist entry with metadata."""
    ticker: str
    added_date: str = ""
    source: str = "CORE"  # CORE, MOMENTUM_BREAKOUT, OVERSOLD_BOUNCE, etc.
    discovery_score: float = 0.0
    sector: str = ""
    market_cap_m: float = 0.0
    avg_volume: int = 0
    last_checked: str = ""
    status: str = "ACTIVE"  # ACTIVE, STALE, REMOVED
    notes: str = ""

    def __post_init__(self):
        if not self.added_date:
            self.added_date = date.today().isoformat()
        if not self.last_checked:
            self.last_checked = date.today().isoformat()


def load_config() -> dict:
    """Load configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


class WatchlistManager:
    """
    Manages the stock watchlist with discovery integration.

    Maintains a hybrid watchlist:
    - Core tickers: Always included, manually curated
    - Discovered tickers: Added from discovery scans, can expire
    """

    def __init__(self):
        self.config = load_config()
        self.discovery_config = self.config.get("discovery", {}).get("watchlist", {})
        self.max_tickers = self.discovery_config.get("max_tickers", 150)
        self.stale_days = self.discovery_config.get("stale_days_threshold", 30)

    def _load_watchlist(self) -> List[WatchlistEntry]:
        """Load watchlist from JSONL file."""
        entries = []
        if WATCHLIST_FILE.exists():
            with open(WATCHLIST_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        # Handle both old format (just ticker) and new format
                        if isinstance(data, dict):
                            if "ticker" in data:
                                entries.append(WatchlistEntry(**data))
                        elif isinstance(data, str):
                            entries.append(WatchlistEntry(ticker=data))
        return entries

    def _save_watchlist(self, entries: List[WatchlistEntry]):
        """Save watchlist to JSONL file."""
        # Backup existing
        if WATCHLIST_FILE.exists():
            BACKUP_DIR.mkdir(exist_ok=True)
            backup_path = BACKUP_DIR / f"watchlist_{date.today().isoformat()}.jsonl"
            shutil.copy(WATCHLIST_FILE, backup_path)

        # Save new
        with open(WATCHLIST_FILE, "w") as f:
            for entry in entries:
                f.write(json.dumps(asdict(entry)) + "\n")

    def _load_core_watchlist(self) -> Set[str]:
        """Load core watchlist tickers."""
        core_tickers = set()

        # First check for dedicated core file
        if CORE_WATCHLIST_FILE.exists():
            with open(CORE_WATCHLIST_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        if isinstance(data, dict) and "ticker" in data:
                            core_tickers.add(data["ticker"])
                        elif isinstance(data, str):
                            core_tickers.add(data)

        # Also include any CORE-sourced entries from main watchlist
        entries = self._load_watchlist()
        for entry in entries:
            if entry.source == "CORE":
                core_tickers.add(entry.ticker)

        return core_tickers

    def get_active_tickers(self) -> List[str]:
        """
        Get list of active tickers for trading.

        Returns only ACTIVE status tickers.
        """
        entries = self._load_watchlist()
        return [e.ticker for e in entries if e.status == "ACTIVE"]

    def get_all_entries(self) -> List[WatchlistEntry]:
        """Get all watchlist entries with full metadata."""
        return self._load_watchlist()

    def add_discovered_stocks(self, discovered_stocks: List) -> int:
        """
        Add discovered stocks to watchlist.

        Args:
            discovered_stocks: List of DiscoveredStock objects from stock_discovery

        Returns:
            Number of new stocks added
        """
        entries = self._load_watchlist()
        existing_tickers = {e.ticker for e in entries}
        core_tickers = self._load_core_watchlist()

        added_count = 0

        for stock in discovered_stocks:
            if stock.ticker in existing_tickers:
                # Update existing entry
                for entry in entries:
                    if entry.ticker == stock.ticker:
                        entry.last_checked = date.today().isoformat()
                        entry.discovery_score = stock.discovery_score
                        entry.status = "ACTIVE"  # Reactivate if was stale
                        if entry.source == "CORE":
                            pass  # Keep CORE designation
                        elif stock.discovery_score > entry.discovery_score:
                            entry.source = stock.source
                            entry.notes = stock.notes
                        break
            else:
                # Add new entry
                new_entry = WatchlistEntry(
                    ticker=stock.ticker,
                    added_date=stock.discovered_date,
                    source=stock.source,
                    discovery_score=stock.discovery_score,
                    sector=stock.sector,
                    market_cap_m=stock.market_cap_m,
                    avg_volume=stock.avg_volume,
                    last_checked=date.today().isoformat(),
                    status="ACTIVE",
                    notes=stock.notes,
                )
                entries.append(new_entry)
                added_count += 1

        self._save_watchlist(entries)
        return added_count

    def mark_stale_tickers(self) -> int:
        """
        Mark tickers that haven't been refreshed as stale.

        Core tickers are never marked stale.

        Returns:
            Number of tickers marked stale
        """
        entries = self._load_watchlist()
        core_tickers = self._load_core_watchlist()
        stale_threshold = date.today() - timedelta(days=self.stale_days)
        stale_count = 0

        for entry in entries:
            if entry.ticker in core_tickers:
                continue  # Never mark core as stale

            if entry.status != "ACTIVE":
                continue

            last_checked = datetime.fromisoformat(entry.last_checked).date()
            if last_checked < stale_threshold:
                entry.status = "STALE"
                stale_count += 1

        self._save_watchlist(entries)
        return stale_count

    def remove_stale_tickers(self, older_than_days: int = 60) -> int:
        """
        Remove tickers that have been stale for too long.

        Args:
            older_than_days: Remove if stale for this many days

        Returns:
            Number of tickers removed
        """
        entries = self._load_watchlist()
        core_tickers = self._load_core_watchlist()
        removal_threshold = date.today() - timedelta(days=older_than_days)

        new_entries = []
        removed_count = 0

        for entry in entries:
            if entry.ticker in core_tickers:
                new_entries.append(entry)
                continue

            if entry.status == "STALE":
                last_checked = datetime.fromisoformat(entry.last_checked).date()
                if last_checked < removal_threshold:
                    removed_count += 1
                    continue  # Don't include in new list

            new_entries.append(entry)

        self._save_watchlist(new_entries)
        return removed_count

    def enforce_max_size(self) -> int:
        """
        Enforce maximum watchlist size.

        Removes lowest-scoring non-core tickers if over limit.

        Returns:
            Number of tickers removed
        """
        entries = self._load_watchlist()

        if len(entries) <= self.max_tickers:
            return 0

        core_tickers = self._load_core_watchlist()

        # Separate core and non-core
        core_entries = [e for e in entries if e.ticker in core_tickers]
        non_core_entries = [e for e in entries if e.ticker not in core_tickers]

        # Sort non-core by discovery score (lowest first)
        non_core_entries.sort(key=lambda x: x.discovery_score)

        # Calculate how many to remove
        slots_for_non_core = self.max_tickers - len(core_entries)
        to_remove = len(non_core_entries) - slots_for_non_core

        if to_remove <= 0:
            return 0

        # Keep top scoring non-core
        kept_non_core = non_core_entries[to_remove:]
        final_entries = core_entries + kept_non_core

        self._save_watchlist(final_entries)
        return to_remove

    def update_watchlist(self, run_discovery: bool = True) -> Dict:
        """
        Full watchlist update cycle.

        1. Run discovery scans (optional)
        2. Add discovered stocks
        3. Mark stale tickers
        4. Remove old stale tickers
        5. Enforce max size

        Args:
            run_discovery: Whether to run discovery scans

        Returns:
            Dict with update statistics
        """
        stats = {
            "discovered": 0,
            "added": 0,
            "marked_stale": 0,
            "removed": 0,
            "total_active": 0,
        }

        if run_discovery:
            try:
                from stock_discovery import discover_stocks
                discovered = discover_stocks()
                stats["discovered"] = len(discovered)
                stats["added"] = self.add_discovered_stocks(discovered)
            except Exception as e:
                print(f"Discovery error: {e}")

        stats["marked_stale"] = self.mark_stale_tickers()
        stats["removed"] = self.remove_stale_tickers()
        stats["removed"] += self.enforce_max_size()
        stats["total_active"] = len(self.get_active_tickers())

        return stats

    def get_summary(self) -> Dict:
        """Get watchlist summary statistics."""
        entries = self._load_watchlist()
        core_tickers = self._load_core_watchlist()

        by_source = {}
        by_status = {}
        by_sector = {}

        for entry in entries:
            by_source[entry.source] = by_source.get(entry.source, 0) + 1
            by_status[entry.status] = by_status.get(entry.status, 0) + 1
            if entry.sector:
                by_sector[entry.sector] = by_sector.get(entry.sector, 0) + 1

        return {
            "total_entries": len(entries),
            "core_count": len([e for e in entries if e.ticker in core_tickers]),
            "active_count": by_status.get("ACTIVE", 0),
            "stale_count": by_status.get("STALE", 0),
            "by_source": by_source,
            "by_sector": by_sector,
        }


def get_watchlist_tickers() -> List[str]:
    """
    Convenience function to get active watchlist tickers.

    Returns:
        List of ticker symbols
    """
    manager = WatchlistManager()
    return manager.get_active_tickers()


def update_watchlist(run_discovery: bool = True) -> Dict:
    """
    Convenience function to update the watchlist.

    Args:
        run_discovery: Whether to run discovery scans

    Returns:
        Update statistics
    """
    manager = WatchlistManager()
    return manager.update_watchlist(run_discovery)


def format_watchlist_report(manager: WatchlistManager = None) -> str:
    """Format watchlist status as a text report."""
    if manager is None:
        manager = WatchlistManager()

    summary = manager.get_summary()
    entries = manager.get_all_entries()

    lines = []
    lines.append("=" * 60)
    lines.append("WATCHLIST STATUS REPORT")
    lines.append(f"Date: {date.today().isoformat()}")
    lines.append("=" * 60)

    lines.append(f"\nTotal Entries:  {summary['total_entries']}")
    lines.append(f"Core Tickers:   {summary['core_count']}")
    lines.append(f"Active:         {summary['active_count']}")
    lines.append(f"Stale:          {summary['stale_count']}")

    lines.append("\nBy Source:")
    for source, count in sorted(summary['by_source'].items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  {source}: {count}")

    lines.append("\nBy Sector:")
    for sector, count in sorted(summary['by_sector'].items(), key=lambda x: x[1], reverse=True)[:8]:
        lines.append(f"  {sector}: {count}")

    # Top 10 by score
    active_entries = [e for e in entries if e.status == "ACTIVE"]
    active_entries.sort(key=lambda x: x.discovery_score, reverse=True)

    if active_entries:
        lines.append("\nTop 10 by Discovery Score:")
        lines.append(f"{'Ticker':<8} {'Score':<7} {'Source':<20} {'Sector'}")
        lines.append("-" * 60)
        for entry in active_entries[:10]:
            lines.append(
                f"{entry.ticker:<8} {entry.discovery_score:<7.1f} "
                f"{entry.source:<20} {entry.sector[:15]}"
            )

    return "\n".join(lines)


# ─── CLI for Testing ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mommy Bot Watchlist Manager")
    parser.add_argument("--update", action="store_true", help="Run full watchlist update")
    parser.add_argument("--status", action="store_true", help="Show watchlist status")
    parser.add_argument("--list", action="store_true", help="List all active tickers")
    args = parser.parse_args()

    manager = WatchlistManager()

    if args.update:
        print("\n─── Running Watchlist Update ───\n")
        stats = manager.update_watchlist(run_discovery=True)
        print("\nUpdate Complete:")
        print(f"  Discovered: {stats['discovered']} candidates")
        print(f"  Added:      {stats['added']} new tickers")
        print(f"  Stale:      {stats['marked_stale']} marked stale")
        print(f"  Removed:    {stats['removed']} removed")
        print(f"  Active:     {stats['total_active']} total active")

    elif args.status:
        print(format_watchlist_report(manager))

    elif args.list:
        tickers = manager.get_active_tickers()
        print(f"\nActive Tickers ({len(tickers)}):")
        for i, ticker in enumerate(tickers, 1):
            print(f"  {i:3}. {ticker}")

    else:
        # Default: show status
        print(format_watchlist_report(manager))
