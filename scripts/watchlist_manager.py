#!/usr/bin/env python3
"""
Watchlist Manager Module for GScott.

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
import threading
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

from data_files import (
    get_watchlist_file, get_core_watchlist_file,
    get_transactions_file as get_transactions_file_for_portfolio,
    load_config as load_config_from_files,
    _resolve_data_dir,
)


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

    def __init__(self, portfolio_id: str = None):
        self.portfolio_id = portfolio_id
        self.config = load_config_from_files(portfolio_id) if portfolio_id else load_config()
        self.discovery_config = self.config.get("discovery", {}).get("watchlist", {})
        self.max_tickers = self.discovery_config.get("max_tickers", 150)
        self.stale_days = self.discovery_config.get("stale_days_threshold", 30)
        # Resolve paths based on portfolio
        self._watchlist_file = get_watchlist_file(portfolio_id) if portfolio_id else WATCHLIST_FILE
        self._core_watchlist_file = get_core_watchlist_file(portfolio_id) if portfolio_id else CORE_WATCHLIST_FILE

    def _load_watchlist(self) -> List[WatchlistEntry]:
        """Load watchlist from JSONL file."""
        entries = []
        if self._watchlist_file.exists():
            with open(self._watchlist_file) as f:
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
        """Save watchlist to JSONL file using atomic write (temp + rename)."""
        # Backup existing
        if self._watchlist_file.exists():
            BACKUP_DIR.mkdir(exist_ok=True)
            backup_path = BACKUP_DIR / f"watchlist_{date.today().isoformat()}.jsonl"
            shutil.copy(self._watchlist_file, backup_path)

        # Atomic write: write to temp file then rename to avoid partial writes
        tmp_path = self._watchlist_file.with_suffix(".jsonl.tmp")
        try:
            with open(tmp_path, "w") as f:
                for entry in entries:
                    f.write(json.dumps(asdict(entry)) + "\n")
            tmp_path.replace(self._watchlist_file)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    def _load_core_watchlist(self) -> Set[str]:
        """Load core watchlist tickers."""
        core_tickers = set()

        # First check for dedicated core file
        if self._core_watchlist_file.exists():
            with open(self._core_watchlist_file) as f:
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
                # Add new entry — normalize missing sector to "Unknown" so
                # downstream code can reliably check sector == "Unknown" vs ""
                new_entry = WatchlistEntry(
                    ticker=stock.ticker,
                    added_date=stock.discovered_date,
                    source=stock.source,
                    discovery_score=stock.discovery_score,
                    sector=stock.sector if stock.sector else "Unknown",
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

    def _fetch_sector_with_timeout(self, ticker: str, timeout: float = 5.0) -> str:
        """
        Fetch sector for a single ticker from yfinance using a daemon thread
        with a hard timeout (same pattern as StockDiscovery._get_stock_info).

        Returns the sector string, or "" on failure/timeout.
        """
        import yfinance as yf

        result: list = [""]

        def _fetch() -> None:
            try:
                info = yf.Ticker(ticker).info
                result[0] = info.get("sector", "")
            except Exception:
                pass

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()
        t.join(timeout=timeout)
        return result[0]

    def _backfill_missing_sectors(self, entries: List[WatchlistEntry], batch_limit: int = 20) -> int:
        """
        Self-healing backfill: find ACTIVE entries with missing/Unknown sector
        and attempt to fetch from yfinance. Updates entries in-place.

        Args:
            entries: The current list of WatchlistEntry objects (mutated in-place).
            batch_limit: Maximum number of tickers to backfill per call (avoids
                         slowing down the scan cycle).

        Returns:
            Number of entries successfully backfilled with a real sector.
        """
        needs_backfill = [
            e for e in entries
            if e.status == "ACTIVE" and (not e.sector or e.sector == "Unknown")
        ]

        if not needs_backfill:
            return 0

        batch = needs_backfill[:batch_limit]
        print(f"  Backfilling sectors for {len(batch)} watchlist entries (of {len(needs_backfill)} missing)...")

        filled = 0
        for entry in batch:
            sector = self._fetch_sector_with_timeout(entry.ticker, timeout=5.0)
            if sector and sector != "Unknown":
                entry.sector = sector
                filled += 1
            else:
                # Explicitly mark as Unknown so we don't retry endlessly
                # (next backfill cycle will skip entries already == "Unknown"
                #  that haven't been re-discovered with real data)
                if not entry.sector:
                    entry.sector = "Unknown"

        print(f"  Sector backfill: {filled}/{len(batch)} resolved")
        return filled

    def update_watchlist(self, run_discovery: bool = True) -> Dict:
        """
        Full watchlist update cycle.

        1. Remove poor performers (consistent losers)
        2. Run discovery scans (optional)
        3. Add discovered stocks
        4. Mark stale tickers
        5. Remove old stale tickers
        6. Balance sectors
        7. Enforce max size

        Args:
            run_discovery: Whether to run discovery scans

        Returns:
            Dict with update statistics
        """
        stats = {
            "discovered": 0,
            "added": 0,
            "sectors_backfilled": 0,
            "marked_stale": 0,
            "removed": 0,
            "poor_performers_removed": 0,
            "sector_balanced": {},
            "total_active": 0,
        }

        # Remove consistent losers first
        stats["poor_performers_removed"] = self.remove_poor_performers()

        if run_discovery:
            try:
                from stock_discovery import discover_stocks
                discovered = discover_stocks(portfolio_id=self.portfolio_id)
                stats["discovered"] = len(discovered)
                stats["added"] = self.add_discovered_stocks(discovered)
            except Exception as e:
                print(f"Discovery error: {e}")

        # Self-healing sector backfill: fix entries with missing/Unknown sector
        # (up to 20 per cycle to avoid slowing down scans)
        try:
            entries = self._load_watchlist()
            filled = self._backfill_missing_sectors(entries, batch_limit=20)
            if filled > 0:
                self._save_watchlist(entries)
            stats["sectors_backfilled"] = filled
        except Exception as e:
            print(f"Sector backfill error: {e}")

        stats["marked_stale"] = self.mark_stale_tickers()
        stats["removed"] = self.remove_stale_tickers()

        # Balance sectors
        stats["sector_balanced"] = self.balance_sectors()

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

    def remove_poor_performers(self, min_trades: int = 3, max_loss_rate: float = 0.75) -> int:
        """
        Remove tickers that consistently lose money when traded.

        Args:
            min_trades: Minimum trades to evaluate (default 3)
            max_loss_rate: Remove if loss rate exceeds this (default 75%)

        Returns:
            Number of tickers removed
        """
        tx_file = get_transactions_file_for_portfolio(self.portfolio_id)
        if not tx_file.exists():
            return 0

        import pandas as pd
        transactions = pd.read_csv(tx_file)

        if transactions.empty or "ticker" not in transactions.columns:
            return 0

        entries = self._load_watchlist()
        core_tickers = self._load_core_watchlist()

        # Analyze completed trades (sells)
        sells = transactions[transactions["action"] == "SELL"]
        if sells.empty:
            return 0

        # Calculate win/loss by ticker
        ticker_stats = {}
        for ticker in sells["ticker"].unique():
            ticker_sells = sells[sells["ticker"] == ticker]
            total_trades = len(ticker_sells)

            if total_trades < min_trades:
                continue

            # Count losses (where reason is STOP_LOSS or realized negative)
            losses = len(ticker_sells[ticker_sells["reason"] == "STOP_LOSS"])
            loss_rate = losses / total_trades

            ticker_stats[ticker] = {
                "trades": total_trades,
                "losses": losses,
                "loss_rate": loss_rate,
            }

        # Remove poor performers
        removed_count = 0
        new_entries = []

        for entry in entries:
            if entry.ticker in core_tickers:
                new_entries.append(entry)
                continue

            stats = ticker_stats.get(entry.ticker)
            if stats and stats["loss_rate"] > max_loss_rate:
                # Poor performer - remove
                print(f"  Removing {entry.ticker}: {stats['loss_rate']:.0%} loss rate ({stats['losses']}/{stats['trades']} trades)")
                removed_count += 1
                continue

            new_entries.append(entry)

        if removed_count > 0:
            self._save_watchlist(new_entries)

        return removed_count

    def balance_sectors(self, max_sector_pct: float = 25.0) -> Dict[str, int]:
        """
        Balance sectors to prevent over-concentration.

        Args:
            max_sector_pct: Maximum percentage per sector (default 25%)

        Returns:
            Dict of sectors and how many removed from each
        """
        entries = self._load_watchlist()
        core_tickers = self._load_core_watchlist()

        active_entries = [e for e in entries if e.status == "ACTIVE"]
        total_active = len(active_entries)

        if total_active == 0:
            return {}

        max_per_sector = int(total_active * max_sector_pct / 100)
        if max_per_sector < 3:
            max_per_sector = 3  # Minimum 3 per sector

        # Group by sector
        by_sector = {}
        for entry in active_entries:
            sector = entry.sector or "Unknown"
            if sector not in by_sector:
                by_sector[sector] = []
            by_sector[sector].append(entry)

        # Remove excess from over-represented sectors
        removed_by_sector = {}
        to_remove = set()

        for sector, sector_entries in by_sector.items():
            if len(sector_entries) > max_per_sector:
                # Sort by discovery score (keep highest)
                sector_entries.sort(key=lambda x: x.discovery_score, reverse=True)

                # Remove lowest scoring (but not core)
                for entry in sector_entries[max_per_sector:]:
                    if entry.ticker not in core_tickers:
                        to_remove.add(entry.ticker)
                        removed_by_sector[sector] = removed_by_sector.get(sector, 0) + 1

        if to_remove:
            new_entries = [e for e in entries if e.ticker not in to_remove]
            self._save_watchlist(new_entries)

        return removed_by_sector

    def get_sector_balance(self) -> Dict[str, Dict]:
        """
        Get current sector balance analysis.

        Returns:
            Dict with sector counts and percentages
        """
        entries = self._load_watchlist()
        active_entries = [e for e in entries if e.status == "ACTIVE"]
        total = len(active_entries)

        if total == 0:
            return {}

        by_sector = {}
        for entry in active_entries:
            sector = entry.sector or "Unknown"
            by_sector[sector] = by_sector.get(sector, 0) + 1

        result = {}
        for sector, count in sorted(by_sector.items(), key=lambda x: x[1], reverse=True):
            result[sector] = {
                "count": count,
                "pct": round(count / total * 100, 1),
            }

        return result

    def get_underrepresented_sectors(self, target_sectors: List[str] = None) -> List[str]:
        """
        Identify sectors that are underrepresented.

        Args:
            target_sectors: List of sectors that should be represented

        Returns:
            List of underrepresented sector names
        """
        if target_sectors is None:
            target_sectors = [
                "Technology", "Healthcare", "Financial Services",
                "Consumer Cyclical", "Industrials", "Energy",
                "Communication Services", "Consumer Defensive",
            ]

        balance = self.get_sector_balance()
        current_sectors = set(balance.keys())

        missing = []
        for sector in target_sectors:
            if sector not in current_sectors:
                missing.append(sector)
            elif balance[sector]["pct"] < 5.0:  # Less than 5%
                missing.append(sector)

        return missing


def get_watchlist_tickers(portfolio_id: str = None) -> List[str]:
    """
    Convenience function to get active watchlist tickers.

    Returns:
        List of ticker symbols
    """
    manager = WatchlistManager(portfolio_id=portfolio_id)
    return manager.get_active_tickers()


def update_watchlist(run_discovery: bool = True, portfolio_id: str = None) -> Dict:
    """
    Convenience function to update the watchlist.

    Args:
        run_discovery: Whether to run discovery scans
        portfolio_id: Portfolio ID (default: registry default)

    Returns:
        Update statistics
    """
    manager = WatchlistManager(portfolio_id=portfolio_id)
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

    parser = argparse.ArgumentParser(description="GScott Watchlist Manager")
    parser.add_argument("--update", action="store_true", help="Run full watchlist update")
    parser.add_argument("--status", action="store_true", help="Show watchlist status")
    parser.add_argument("--list", action="store_true", help="List all active tickers")
    parser.add_argument("--portfolio", default=None, help="Portfolio ID (default: registry default)")
    args = parser.parse_args()

    manager = WatchlistManager(portfolio_id=args.portfolio)

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
