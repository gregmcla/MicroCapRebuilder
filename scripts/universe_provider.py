#!/usr/bin/env python3
"""
Universe Provider for GScott.

Aggregates stock tickers from multiple sources into a two-tier universe:
- Tier 1 (Core): Hand-curated quality stocks, scanned daily
- Tier 2 (Extended): ETF holdings, scanned on 3-day rotation

Usage:
    from universe_provider import UniverseProvider

    provider = UniverseProvider()
    todays_tickers = provider.get_todays_scan_universe()
    print(f"Scanning {len(todays_tickers)} tickers today")
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"
CURATED_UNIVERSE_FILE = DATA_DIR / "curated_universe.json"
UNIVERSE_CACHE_FILE = DATA_DIR / "universe_cache.json"


class UniverseTier(Enum):
    """Universe tier for scan frequency."""
    CORE = 1       # Daily scan
    EXTENDED = 2   # 3-day rotation


class UniverseSource(Enum):
    """Source of the ticker."""
    CURATED_CORE = "CURATED_CORE"
    CURATED_EXTENDED = "CURATED_EXTENDED"
    ETF_IWM = "ETF_IWM"
    ETF_IJR = "ETF_IJR"
    ETF_VB = "ETF_VB"
    ETF_OTHER = "ETF_OTHER"


@dataclass
class UniverseTicker:
    """A ticker in the universe with metadata."""
    ticker: str
    tier: int  # 1 = Core, 2 = Extended
    source: str
    sector: str = ""
    added_date: str = ""


def load_config(portfolio_id: str = None) -> dict:
    """Load configuration, optionally portfolio-scoped."""
    if portfolio_id:
        from data_files import load_config as load_config_from_files
        return load_config_from_files(portfolio_id)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def load_curated_universe() -> Dict[str, List[str]]:
    """Load curated universe from JSON file."""
    if CURATED_UNIVERSE_FILE.exists():
        with open(CURATED_UNIVERSE_FILE) as f:
            data = json.load(f)
            return data.get("sectors", {})
    return {}


class UniverseProvider:
    """
    Provides a dynamic stock universe from multiple sources.

    Features:
    - Two-tier system: Core (daily) and Extended (rotating)
    - Smart rotation for extended tier (1/3 scanned each day)
    - Deduplication across sources
    - Configurable via config.json
    """

    def __init__(self, portfolio_id: str = None):
        """Initialize the universe provider."""
        self.portfolio_id = portfolio_id
        self.config = load_config(portfolio_id)
        self.universe_config = self.config.get("universe", {})

        # Default settings if not in config
        self.enabled = self.universe_config.get("enabled", True)
        self.core_max = self.universe_config.get("tiers", {}).get("core", {}).get("max_tickers", 100)
        self.extended_max = self.universe_config.get("tiers", {}).get("extended", {}).get("max_tickers", 300)

        # Source toggles
        sources_config = self.universe_config.get("sources", {})
        self.curated_enabled = sources_config.get("curated", {}).get("enabled", True)
        self.etf_enabled = sources_config.get("etf_holdings", {}).get("enabled", True)

        # Build the universe
        self._universe: Dict[str, UniverseTicker] = {}
        self._core_tickers: List[str] = []
        self._extended_tickers: List[str] = []

        self._build_universe()

    def _build_universe(self):
        """Build the universe from all sources."""
        # 1. Load curated universe
        if self.curated_enabled:
            self._load_curated()

        # 2. Load ETF holdings
        if self.etf_enabled:
            self._load_etf_holdings()

        # 3. Deduplicate and assign final tiers
        self._finalize_tiers()

        # 4. Save cache
        self._save_cache()

    def _load_curated(self):
        """Load tickers from curated universe file.

        The curated universe file is microcap-specific. Skip it for
        non-microcap portfolios to avoid polluting their universe.
        """
        if self.portfolio_id:
            try:
                from portfolio_registry import load_registry
                registry = load_registry()
                universe = registry.get("portfolios", {}).get(self.portfolio_id, {}).get("universe", "microcap")
                if universe not in ("microcap", "smallcap"):
                    return  # Skip curated file for mid/large-cap portfolios
            except Exception:
                pass  # If we can't determine universe, load curated as fallback

        curated = load_curated_universe()

        for sector, tickers in curated.items():
            if isinstance(tickers, dict):
                # New format with tier_1_core and tier_2_extended
                core_list = tickers.get("tier_1_core", [])
                extended_list = tickers.get("tier_2_extended", [])

                for ticker in core_list:
                    self._add_ticker(ticker, UniverseTier.CORE, "CURATED_CORE", sector)

                for ticker in extended_list:
                    self._add_ticker(ticker, UniverseTier.EXTENDED, "CURATED_EXTENDED", sector)

            elif isinstance(tickers, list):
                # Old format - all core
                for ticker in tickers:
                    self._add_ticker(ticker, UniverseTier.CORE, "CURATED_CORE", sector)

    def _load_etf_holdings(self):
        """Load tickers from ETF holdings."""
        try:
            from etf_holdings_provider import ETFHoldingsProvider, seed_cache_with_fallbacks

            # Ensure we have fallback data for this portfolio's ETFs
            seed_cache_with_fallbacks(portfolio_id=self.portfolio_id)

            provider = ETFHoldingsProvider(portfolio_id=self.portfolio_id)
            holdings = provider.get_all_holdings(use_cache=True)

            for ticker in holdings:
                # ETF holdings go to extended tier
                self._add_ticker(ticker, UniverseTier.EXTENDED, "ETF_HOLDINGS", "")

        except ImportError as e:
            print(f"Warning: Could not load ETF holdings: {e}")
        except Exception as e:
            print(f"Warning: Error loading ETF holdings: {e}")

    def _add_ticker(self, ticker: str, tier: UniverseTier, source: str, sector: str):
        """Add a ticker to the universe."""
        ticker = ticker.upper().strip()

        if not ticker or len(ticker) > 10:
            return

        # Skip certain problematic tickers
        if ticker in ["", "N/A", "NONE", "NULL"]:
            return

        # If ticker already exists, prefer higher tier (Core over Extended)
        if ticker in self._universe:
            existing = self._universe[ticker]
            if tier.value < existing.tier:  # Lower value = higher priority
                self._universe[ticker] = UniverseTicker(
                    ticker=ticker,
                    tier=tier.value,
                    source=source,
                    sector=sector or existing.sector,
                    added_date=date.today().isoformat()
                )
        else:
            self._universe[ticker] = UniverseTicker(
                ticker=ticker,
                tier=tier.value,
                source=source,
                sector=sector,
                added_date=date.today().isoformat()
            )

    def _finalize_tiers(self):
        """Finalize tier assignments and create tier lists."""
        self._core_tickers = []
        self._extended_tickers = []

        for ticker, data in self._universe.items():
            if data.tier == UniverseTier.CORE.value:
                self._core_tickers.append(ticker)
            else:
                self._extended_tickers.append(ticker)

        # Enforce limits
        if len(self._core_tickers) > self.core_max:
            # Keep first N (curated tickers are added first)
            overflow = self._core_tickers[self.core_max:]
            self._core_tickers = self._core_tickers[:self.core_max]
            # Move overflow to extended
            self._extended_tickers = overflow + self._extended_tickers

        if len(self._extended_tickers) > self.extended_max:
            self._extended_tickers = self._extended_tickers[:self.extended_max]

        # Sort for consistency
        self._core_tickers.sort()
        self._extended_tickers.sort()

    def _save_cache(self):
        """Save universe to cache file."""
        cache_data = {
            "last_refresh": datetime.now().isoformat(),
            "core_count": len(self._core_tickers),
            "extended_count": len(self._extended_tickers),
            "total_count": len(self._universe),
            "tickers": {
                ticker: asdict(data) for ticker, data in self._universe.items()
            }
        }

        try:
            with open(UNIVERSE_CACHE_FILE, "w") as f:
                json.dump(cache_data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save universe cache: {e}")

    def get_core_tickers(self) -> List[str]:
        """Get all core tier tickers (scanned daily)."""
        return self._core_tickers.copy()

    def get_extended_tickers(self) -> List[str]:
        """Get all extended tier tickers."""
        return self._extended_tickers.copy()

    def get_full_universe(self) -> List[str]:
        """Get all tickers in the universe."""
        return self._core_tickers + self._extended_tickers

    def get_todays_extended_batch(self) -> List[str]:
        """
        Get today's batch of extended tickers (1/3 of extended tier).

        Uses day-of-year to rotate through extended tickers in 3-day cycle.
        """
        if not self._extended_tickers:
            return []

        # Determine which third to scan today
        day_of_year = datetime.now().timetuple().tm_yday
        batch_index = day_of_year % 3  # 0, 1, or 2

        # Split extended into 3 batches
        batch_size = len(self._extended_tickers) // 3 + 1
        start_idx = batch_index * batch_size
        end_idx = min(start_idx + batch_size, len(self._extended_tickers))

        return self._extended_tickers[start_idx:end_idx]

    def get_todays_scan_universe(self) -> List[str]:
        """
        Get the tickers to scan today.

        Returns:
            All core tickers + extended tickers (all or rotating batch based on config)
        """
        if not self.enabled:
            # Fallback to legacy hardcoded list
            return self._get_legacy_universe()

        core = self.get_core_tickers()

        # Respect scan_frequency setting: "daily" scans all extended, otherwise rotate
        extended_freq = self.universe_config.get("tiers", {}).get("extended", {}).get("scan_frequency", "rotating_3day")
        if extended_freq == "daily":
            extended_batch = self.get_extended_tickers()
        else:
            extended_batch = self.get_todays_extended_batch()

        # Deduplicate (core takes priority)
        core_set = set(core)
        extended_filtered = [t for t in extended_batch if t not in core_set]

        return core + extended_filtered

    def _get_legacy_universe(self) -> List[str]:
        """Get the legacy hardcoded universe as fallback."""
        return [
            "CRDO", "MOD", "EAT", "JBT", "OKLO", "AVAV", "IDCC", "SMR", "ITRI", "UPST",
            "GH", "FOLD", "ADMA", "AXSM", "ARWR", "ADUS", "CRSP", "SFBS", "WSBC", "BOH",
            "CBU", "BANF", "PFSI", "ANF", "URBN", "SMPL", "FUN", "AEO", "CAKE", "GOLF",
            "SM", "MGY", "TDW", "CRC", "BTU", "TEX", "KTB", "HASI", "SBRA", "OUT", "KRG",
            "AWR", "ALE", "MGEE", "WDFC", "AGYS", "CALX", "MGRC", "ABM", "RIOT", "AI",
            "LMND", "AX", "BANR", "IDYA", "VAC", "HURN", "MTRN", "KFY", "ACLS", "SYNA",
            "MGNI", "BELFB", "GFF", "VC", "EXTR"
        ]

    def get_ticker_info(self, ticker: str) -> Optional[UniverseTicker]:
        """Get metadata for a specific ticker."""
        return self._universe.get(ticker.upper())

    def get_tier_for_ticker(self, ticker: str) -> Optional[int]:
        """Get the tier for a specific ticker."""
        info = self.get_ticker_info(ticker)
        return info.tier if info else None

    def get_stats(self) -> Dict:
        """Get universe statistics."""
        return {
            "enabled": self.enabled,
            "core_count": len(self._core_tickers),
            "extended_count": len(self._extended_tickers),
            "total_count": len(self._universe),
            "todays_scan_count": len(self.get_todays_scan_universe()),
            "sources": self._get_source_breakdown()
        }

    def _get_source_breakdown(self) -> Dict[str, int]:
        """Get count of tickers by source."""
        breakdown: Dict[str, int] = {}
        for data in self._universe.values():
            source = data.source
            breakdown[source] = breakdown.get(source, 0) + 1
        return breakdown

    def refresh(self):
        """Refresh the universe from all sources."""
        self._universe = {}
        self._core_tickers = []
        self._extended_tickers = []
        self._build_universe()


# ─── Convenience Functions ────────────────────────────────────────────────────

def get_todays_scan_universe(portfolio_id: str = None) -> List[str]:
    """Get today's scan universe (convenience function)."""
    provider = UniverseProvider(portfolio_id=portfolio_id)
    return provider.get_todays_scan_universe()


def get_universe_stats(portfolio_id: str = None) -> Dict:
    """Get universe statistics (convenience function)."""
    provider = UniverseProvider(portfolio_id=portfolio_id)
    return provider.get_stats()


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("UNIVERSE PROVIDER")
    print("=" * 60)

    provider = UniverseProvider()
    stats = provider.get_stats()

    print(f"\nUniverse Statistics:")
    print(f"  Enabled: {stats['enabled']}")
    print(f"  Core Tier: {stats['core_count']} tickers (daily)")
    print(f"  Extended Tier: {stats['extended_count']} tickers (3-day rotation)")
    print(f"  Total Universe: {stats['total_count']} tickers")
    print(f"  Today's Scan: {stats['todays_scan_count']} tickers")

    print(f"\nSources:")
    for source, count in sorted(stats['sources'].items()):
        print(f"  {source}: {count}")

    print(f"\nCore Tickers (first 20):")
    for ticker in provider.get_core_tickers()[:20]:
        print(f"  {ticker}")

    print(f"\nToday's Extended Batch (first 20):")
    for ticker in provider.get_todays_extended_batch()[:20]:
        print(f"  {ticker}")

    print(f"\nToday's Full Scan Universe (first 30):")
    for ticker in provider.get_todays_scan_universe()[:30]:
        info = provider.get_ticker_info(ticker)
        tier = "Core" if info and info.tier == 1 else "Extended"
        print(f"  {ticker} ({tier})")
