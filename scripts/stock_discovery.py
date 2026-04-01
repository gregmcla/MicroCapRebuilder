#!/usr/bin/env python3
"""
Stock Discovery Module for GScott.

Automatically discovers new trading candidates through multiple scan types:
- Momentum Breakouts: Stocks near 52-week highs with volume surge
- Oversold Bounces: Quality stocks at oversold RSI levels recovering
- Sector Leaders: Top performers in leading sectors
- Volume Anomalies: Unusual accumulation signals

Usage:
    from stock_discovery import StockDiscovery

    discovery = StockDiscovery()
    candidates = discovery.run_all_scans()
"""

import json
import pickle
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import warnings

import logging
import numpy as np
import pandas as pd
import yfinance as yf
from yf_session import cached_download

warnings.filterwarnings("ignore", category=FutureWarning)

# yfinance logs 401/429 errors at ERROR level via its internal logger, but we
# already surface failures via our own "Warning: info fetch failed" messages.
# Suppress yfinance logger to avoid duplicate/bare error lines in API output.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"
WATCHLIST_FILE = DATA_DIR / "watchlist.jsonl"
CORE_WATCHLIST_FILE = DATA_DIR / "core_watchlist.jsonl"


class DiscoverySource(Enum):
    """Source of stock discovery."""
    CORE = "CORE"
    MOMENTUM_BREAKOUT = "MOMENTUM_BREAKOUT"
    OVERSOLD_BOUNCE = "OVERSOLD_BOUNCE"
    SECTOR_LEADER = "SECTOR_LEADER"
    VOLUME_ANOMALY = "VOLUME_ANOMALY"
    RELATIVE_VOLUME_SURGE = "RELATIVE_VOLUME_SURGE"
    SCREENER = "SCREENER"


@dataclass
class DiscoveredStock:
    """A discovered stock candidate."""
    ticker: str
    source: str
    discovery_score: float
    sector: str
    market_cap_m: float
    avg_volume: int
    current_price: float
    momentum_20d: float
    rsi_14: float
    volume_ratio: float
    near_52wk_high_pct: float
    discovered_date: str
    notes: str


def load_config(portfolio_id: str = None) -> dict:
    """Load configuration, optionally portfolio-scoped."""
    if portfolio_id:
        from data_files import load_config as load_config_from_files
        return load_config_from_files(portfolio_id)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """Calculate RSI for a price series."""
    if len(prices) < period + 1:
        return 50.0

    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.inf)
    rsi = 100 - (100 / (1 + rs))

    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0


def _compute_rsi_series(prices: pd.Series, period: int = 14) -> pd.Series:
    """Compute the full RSI series vectorially (single pass, O(n)).

    This is ~100× faster than the naive approach of calling calculate_rsi()
    repeatedly for each bar, which recomputes the entire ewm from scratch each call.
    """
    if len(prices) < period + 1:
        return pd.Series([50.0] * len(prices), index=prices.index)

    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.inf)
    return 100 - (100 / (1 + rs))


def _sector_matches(yf_sector: str, filter_sectors: list) -> bool:
    """
    Fuzzy sector match: handles mismatches like "Communication" vs "Communication Services".
    Returns True if the yfinance sector string contains any filter string, or vice versa.
    """
    if not yf_sector:
        return False
    yf_lower = yf_sector.lower()
    return any(
        f.lower() in yf_lower or yf_lower in f.lower()
        for f in filter_sectors
    )


def prewarm_info_for_tickers(
    tickers: List[str],
    max_workers: int = 8,
    timeout: float = 5.0,
) -> Dict[str, dict]:
    """
    Fetch yfinance .info for a list of tickers in parallel.
    Returns a dict mapping ticker -> info dict.
    Caps at 500 tickers; shuffles first to avoid alphabetical bias.
    Used by unified_analysis.py to pre-warm info before scoring.
    """
    import random as _random

    shuffled = list(tickers)
    _random.shuffle(shuffled)
    to_fetch = shuffled[:500]

    info_cache: Dict[str, dict] = {}

    def _fetch_one(ticker: str) -> tuple:
        result: list = [{}]

        def _do_fetch() -> None:
            try:
                result[0] = yf.Ticker(ticker).info
            except Exception as e:
                print(f"Warning: info fetch failed for {ticker}: {e}")

        t = threading.Thread(target=_do_fetch, daemon=True)
        t.start()
        t.join(timeout=timeout)
        return ticker, result[0]

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, t): t for t in to_fetch}
        for future in as_completed(futures):
            try:
                ticker, info = future.result(timeout=8)
                info_cache[ticker] = info
            except Exception as e:
                ticker = futures[future]
                print(f"Warning: prewarm future failed for {ticker}: {e}")
                info_cache[ticker] = {}

    elapsed = time.time() - t0
    print(f"  prewarm_info_for_tickers: {len(info_cache)} tickers in {elapsed:.1f}s")
    return info_cache


class StockDiscovery:
    """
    Discovers new stock candidates through multiple scanning strategies.

    Uses yfinance for data (no external API keys required).
    Now uses dynamic universe from UniverseProvider instead of hardcoded list.
    """

    # Sector ETFs for rotation analysis
    SECTOR_ETFS = {
        "Technology": "XLK",
        "Financials": "XLF",
        "Healthcare": "XLV",
        "Consumer Discretionary": "XLY",
        "Industrials": "XLI",
        "Energy": "XLE",
        "Materials": "XLB",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Communication": "XLC",
        "Consumer Staples": "XLP",
    }

    def __init__(self, universe: List[str] = None, portfolio_id: str = None):
        """
        Initialize the discovery engine.

        Args:
            universe: Optional list of tickers to scan. If None, uses UniverseProvider.
            portfolio_id: Optional portfolio ID for portfolio-scoped config/universe.
        """
        self.portfolio_id = portfolio_id
        self.config = load_config(portfolio_id)
        self.discovery_config = self.config.get("discovery", {})
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._info_cache: Dict[str, dict] = {}
        self._live_prices: Dict[str, float] = {}  # Public.com real-time prices

        # Get scan universe from provider or use provided list
        if universe is not None:
            self.scan_universe = universe
        else:
            self.scan_universe = self._get_dynamic_universe()

    def _get_dynamic_universe(self) -> List[str]:
        """Get the scan universe from UniverseProvider."""
        try:
            from universe_provider import UniverseProvider
            provider = UniverseProvider(portfolio_id=self.portfolio_id)
            universe = provider.get_todays_scan_universe()
            stats = provider.get_stats()
            print(f"Universe: {stats['core_count']} core + {len(provider.get_todays_extended_batch())} extended = {len(universe)} tickers today")
            return universe
        except ImportError:
            print("Warning: UniverseProvider not available, using legacy universe")
            return self._get_legacy_universe()
        except Exception as e:
            print(f"Warning: Error loading universe: {e}, using legacy")
            return self._get_legacy_universe()

    def _get_legacy_universe(self) -> List[str]:
        """Legacy hardcoded universe as fallback."""
        return [
            "CRDO", "MOD", "OKLO", "AVAV", "IDCC", "UPST", "AI", "SYNA", "MGNI",
            "CALX", "ACLS", "EXTR", "AGYS", "AX", "SFBS", "WSBC", "BOH", "CBU",
            "BANF", "PFSI", "BANR", "ANF", "URBN", "AEO", "CAKE", "EAT", "FUN",
            "GOLF", "CRC", "BTU", "MGY", "SM", "KTB", "GH", "FOLD", "ADMA",
            "AXSM", "ARWR", "ADUS", "CRSP", "JBT", "TEX", "TDW", "ABM", "HURN",
            "GFF", "VC", "SBRA", "KRG", "OUT", "HASI", "AWR", "ALE", "MGEE",
            "WDFC", "SMPL", "BELFB", "LMND", "RIOT", "SMR", "ITRI",
        ]

    def _fetch_price_data(self, ticker: str, period: str = "3mo") -> Optional[pd.DataFrame]:
        """Fetch and cache price data."""
        cache_key = f"{ticker}_{period}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        try:
            df = cached_download(ticker, period=period, progress=False, auto_adjust=True)
            if df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            # Deduplicate columns and squeeze 2D columns to 1D
            df = df.loc[:, ~df.columns.duplicated()]
            for col in ["Close", "High", "Low", "Volume", "Open"]:
                if col in df.columns and hasattr(df[col], "ndim") and df[col].ndim > 1:
                    df[col] = df[col].iloc[:, 0]
            self._price_cache[cache_key] = df
            return df
        except Exception as e:
            print(f"Warning: price data fetch failed for {cache_key}: {e}")
            return None

    # Disk cache for .info data — persists across scan instances (4hr TTL)
    _INFO_DISK_CACHE_DIR = DATA_DIR / "yf_cache"
    _INFO_DISK_CACHE_FILE = _INFO_DISK_CACHE_DIR / "stock_info_cache.pkl"
    _INFO_DISK_CACHE_TTL = 4 * 3600  # 4 hours
    _disk_info_cache: Dict[str, tuple] = {}  # ticker -> (info_dict, timestamp)
    _disk_cache_loaded = False
    _disk_cache_lock = threading.Lock()

    @classmethod
    def _load_disk_info_cache(cls) -> None:
        """Load the disk info cache into class-level dict (once per process)."""
        if cls._disk_cache_loaded:
            return
        with cls._disk_cache_lock:
            if cls._disk_cache_loaded:
                return
            try:
                cls._INFO_DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                if cls._INFO_DISK_CACHE_FILE.exists():
                    with open(cls._INFO_DISK_CACHE_FILE, "rb") as f:
                        cls._disk_info_cache = pickle.load(f)
            except Exception as e:
                print(f"Warning: failed to load disk info cache: {e}")
                cls._disk_info_cache = {}
            cls._disk_cache_loaded = True

    @classmethod
    def _save_disk_info_cache(cls) -> None:
        """Persist the disk info cache to disk."""
        try:
            cls._INFO_DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cls._INFO_DISK_CACHE_FILE, "wb") as f:
                pickle.dump(cls._disk_info_cache, f)
        except Exception as e:
            print(f"Warning: failed to save disk info cache: {e}")

    def _get_stock_info(self, ticker: str, timeout: float = 5.0) -> dict:
        """Fetch and cache stock info with a hard per-ticker timeout."""
        # 1. In-memory cache (per scan instance)
        if ticker in self._info_cache:
            return self._info_cache[ticker]

        # 2. Disk cache (persists across scan instances, 4hr TTL)
        self._load_disk_info_cache()
        cached = self._disk_info_cache.get(ticker)
        if cached:
            info_dict, ts = cached
            if time.time() - ts < self._INFO_DISK_CACHE_TTL:
                self._info_cache[ticker] = info_dict
                return info_dict

        result: list = [{}]

        def _fetch() -> None:
            try:
                result[0] = yf.Ticker(ticker).info
            except Exception as e:
                print(f"Warning: info fetch failed for {ticker}: {e}")

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()
        t.join(timeout=timeout)
        # If thread is still alive after timeout, it's hung — skip the ticker
        info = result[0]
        self._info_cache[ticker] = info
        # Only persist to disk if we got real data (non-empty)
        if info:
            self._disk_info_cache[ticker] = (info, time.time())
        return info

    def _passes_price_volume_filter(self, ticker: str, df: pd.DataFrame) -> bool:
        """Fast pre-filter using only price data — no API call needed."""
        filters = self.discovery_config.get("filters", {})

        if df is None or len(df) == 0:
            return False

        # Price filter
        try:
            current_price = float(df["Close"].iloc[-1])
        except Exception as e:
            print(f"Warning: failed to read price for filter: {e}")
            return False
        min_price = filters.get("min_price") or 5.0
        _max_price = filters.get("max_price")
        max_price = _max_price if _max_price is not None else float("inf")
        if current_price < min_price or current_price > max_price:
            return False

        # Volume filter
        if "Volume" in df.columns:
            _vol_mean = df["Volume"].iloc[-20:].mean()
            avg_vol = int(_vol_mean) if pd.notna(_vol_mean) else 0
            min_vol = filters.get("min_avg_volume") or 200000
            if avg_vol < min_vol:
                # Escape hatch: let through stocks whose recent 5-day average
                # volume is at least 2× the minimum — catches emerging momentum
                # stocks that spiked recently but have a low 3-month average.
                _recent_mean = df["Volume"].iloc[-5:].mean()
                recent_vol = int(_recent_mean) if pd.notna(_recent_mean) else 0
                if recent_vol < min_vol * 2:
                    return False

        return True

    def _passes_filters(self, ticker: str, df: pd.DataFrame, info: dict) -> bool:
        """Check if stock passes all filters (price/volume then market cap/sector)."""
        filters = self.discovery_config.get("filters", {})

        # Price and volume first — cheap, uses cached price data
        if not self._passes_price_volume_filter(ticker, df):
            return False

        # Market cap filter — requires info (pre-cached for survivors)
        market_cap = info.get("marketCap", 0)
        _min_cap_m = filters.get("min_market_cap_m") or 0
        min_cap = _min_cap_m * 1e6
        _max_cap_m = filters.get("max_market_cap_m")
        max_cap = (_max_cap_m * 1e6) if _max_cap_m is not None else float("inf")
        if market_cap < min_cap or market_cap > max_cap:
            return False

        # Sector filter (for strategy-focused portfolios)
        sector_filter = self.discovery_config.get("sector_filter")
        if sector_filter:
            stock_sector = info.get("sector", "")
            if not _sector_matches(stock_sector, sector_filter):
                return False

        # Fundamental pre-screen: reject stocks with clearly broken fundamentals
        # None values skip the check (permissive — data gaps are not a red flag)
        gross_margins = info.get("grossMargins")
        if gross_margins is not None and gross_margins < 0:
            return False  # Negative gross margins = structurally broken business

        rev_growth = info.get("revenueGrowth")
        if rev_growth is not None and rev_growth < -0.15:
            return False  # >15% revenue decline — avoid unless mean reversion strategy

        # Reject SPACs and blank check companies
        long_name = (info.get("longName") or "").lower()
        short_name = (info.get("shortName") or "").lower()
        company_name = long_name or short_name
        if any(kw in company_name for kw in ("acquisition", "spac", "blank check")):
            return False

        return True

    def _calculate_discovery_score(
        self,
        momentum: float,
        rsi: float,
        volume_ratio: float,
        near_high_pct: float,
        source: DiscoverySource,
    ) -> float:
        """Calculate a discovery score for ranking candidates."""
        score = 50.0

        # Momentum contribution (0-30 points)
        if momentum > 0:
            score += min(30, momentum * 1.5)
        else:
            score += max(-20, momentum * 0.5)

        # RSI contribution (0-20 points)
        # Sweet spot: 45-65
        if 45 <= rsi <= 65:
            score += 20
        elif 35 <= rsi < 45 or 65 < rsi <= 72:
            score += 10
        elif rsi > 80:
            score -= 15
        elif rsi < 30:
            score += 5  # Potential bounce

        # Volume contribution (0-15 points)
        if volume_ratio > 1.5:
            score += min(15, (volume_ratio - 1) * 10)

        # Near 52-week high bonus (0-15 points)
        if near_high_pct <= 5:
            score += 15
        elif near_high_pct <= 10:
            score += 10
        elif near_high_pct <= 15:
            score += 5

        # Source bonus
        source_bonuses = {
            DiscoverySource.MOMENTUM_BREAKOUT: 10,
            DiscoverySource.RELATIVE_VOLUME_SURGE: 10,  # high-signal same-day event
            DiscoverySource.SECTOR_LEADER: 8,
            DiscoverySource.OVERSOLD_BOUNCE: 5,
            DiscoverySource.VOLUME_ANOMALY: 5,
        }
        score += source_bonuses.get(source, 0)

        return max(0, min(100, score))

    def _analyze_stock(self, ticker: str, source: DiscoverySource) -> Optional[DiscoveredStock]:
        """Analyze a single stock and create discovery record."""
        df = self._fetch_price_data(ticker, "3mo")
        if df is None or len(df) < 20:
            return None

        info = self._get_stock_info(ticker)
        if not self._passes_filters(ticker, df, info):
            return None

        # Calculate metrics
        close = df["Close"]
        current_price = self._live_prices.get(ticker) or float(close.iloc[-1])

        # Momentum
        mom_20d = 0.0
        if len(close) >= 20:
            mom_20d = ((current_price - close.iloc[-20]) / close.iloc[-20]) * 100

        # RSI
        rsi = calculate_rsi(close, 14)

        # Volume ratio
        volume_ratio = 1.0
        if "Volume" in df.columns and len(df) >= 20:
            recent_vol = df["Volume"].iloc[-5:].mean()
            avg_vol = df["Volume"].iloc[-20:].mean()
            if avg_vol > 0:
                volume_ratio = recent_vol / avg_vol

        # 52-week high proximity — use 1y data if available for true 52wk calculation.
        # The `df` here is 3mo; using it would compute a 3-month high, not a 52-week high.
        df_1y = self._price_cache.get(f"{ticker}_1y")
        if df_1y is not None and not df_1y.empty and "Close" in df_1y.columns:
            high_52wk = float(df_1y["Close"].dropna().max())
        else:
            high_52wk = float(close.max())  # Fallback to 3mo range
        near_high_pct = ((high_52wk - current_price) / high_52wk) * 100 if high_52wk > 0 else 100

        # Calculate discovery score
        discovery_score = self._calculate_discovery_score(
            mom_20d, rsi, volume_ratio, near_high_pct, source
        )

        # Get sector
        sector = info.get("sector", "Unknown")

        # Market cap in millions
        market_cap_m = info.get("marketCap", 0) / 1e6

        # Average volume
        _vol_mean = df["Volume"].iloc[-20:].mean() if "Volume" in df.columns else float("nan")
        avg_volume = int(_vol_mean) if pd.notna(_vol_mean) else 0

        # Generate notes
        notes_parts = []
        if mom_20d > 15:
            notes_parts.append("Strong momentum")
        if near_high_pct <= 5:
            notes_parts.append("Near 52wk high")
        if volume_ratio > 2:
            notes_parts.append("Volume surge")
        if rsi < 35:
            notes_parts.append("Oversold")
        elif rsi > 70:
            notes_parts.append("Overbought")

        return DiscoveredStock(
            ticker=ticker,
            source=source.value,
            discovery_score=round(discovery_score, 1),
            sector=sector,
            market_cap_m=round(market_cap_m, 1),
            avg_volume=avg_volume,
            current_price=round(current_price, 2),
            momentum_20d=round(mom_20d, 2),
            rsi_14=round(rsi, 1),
            volume_ratio=round(volume_ratio, 2),
            near_52wk_high_pct=round(near_high_pct, 2),
            discovered_date=date.today().isoformat(),
            notes=", ".join(notes_parts) if notes_parts else "Standard candidate",
        )

    # ─── Bucketed Selection ───────────────────────────────────────────────────────

    def _select_by_buckets(
        self,
        candidates: List[DiscoveredStock],
        sector_weights: Dict[str, int],
        total_slots: int,
    ) -> List[DiscoveredStock]:
        """Select top-scoring candidates per sector bucket based on weight ratios.

        Candidates compete within their sector bucket, not globally.
        Uses fuzzy sector matching (via _sector_matches) to handle yfinance naming
        mismatches (e.g., 'Communication Services' matches 'Communication').

        Args:
            candidates: All passing candidates (already deduplicated, sorted by score).
            sector_weights: Maps sector name → relative integer weight.
            total_slots: Total watchlist slots to fill.

        Returns:
            Selected candidates, at most total_slots total. Empty buckets stay empty.
        """
        # Compute per-bucket slot counts (proportional to weights)
        total_weight = sum(sector_weights.values()) or 1
        sorted_sectors = sorted(sector_weights.items(), key=lambda x: x[1], reverse=True)
        bucket_sizes: Dict[str, int] = {}
        allocated = 0
        for sector, weight in sorted_sectors:
            size = round(total_slots * weight / total_weight)
            bucket_sizes[sector] = size
            allocated += size
        # Fix rounding: remainder goes to highest-weight sector
        diff = total_slots - allocated
        if diff != 0 and sorted_sectors:
            bucket_sizes[sorted_sectors[0][0]] += diff

        # Group candidates into buckets using fuzzy sector matching
        by_bucket: Dict[str, List[DiscoveredStock]] = {s: [] for s in sector_weights}
        for candidate in candidates:
            for bucket_key in sector_weights:
                if _sector_matches(candidate.sector, [bucket_key]):
                    by_bucket[bucket_key].append(candidate)
                    break  # assign to first matching bucket only

        # Fill each bucket: top N by discovery_score
        selected: List[DiscoveredStock] = []
        for bucket_key, limit in bucket_sizes.items():
            bucket = by_bucket[bucket_key]
            bucket.sort(key=lambda x: x.discovery_score, reverse=True)
            selected.extend(bucket[:limit])

        return selected

    # ─── Scan Types ──────────────────────────────────────────────────────────────

    def scan_momentum_breakouts(self, universe: List[str] = None) -> List[DiscoveredStock]:
        """
        Find stocks breaking out with momentum.

        Criteria (configurable via discovery.scan_thresholds):
        - Within X% of 52-week high (default 10%)
        - 20-day momentum > X% (default 10%)
        - Volume ratio > Xx average (default 1.3x)
        """
        print("  Scanning for momentum breakouts...")
        universe = universe or self.scan_universe
        candidates = []

        thresholds = self.discovery_config.get("scan_thresholds", {}).get("momentum_breakouts", {})
        max_pct_from_high = thresholds.get("max_pct_from_high", 10)
        min_momentum_20d = thresholds.get("min_momentum_20d", 10)
        min_volume_ratio = thresholds.get("min_volume_ratio", 1.3)

        for ticker in universe:
            df = self._fetch_price_data(ticker, "1y")
            if df is None or len(df) < 50 or "Close" not in df.columns:
                continue

            close = df["Close"]
            current = float(close.iloc[-1])
            high_52wk = close.max()

            # Check if near 52-week high
            pct_from_high = ((high_52wk - current) / high_52wk) * 100
            if pct_from_high > max_pct_from_high:
                continue

            # Check momentum
            if len(close) >= 20:
                mom_20d = ((current - close.iloc[-20]) / close.iloc[-20]) * 100
                if mom_20d < min_momentum_20d:
                    continue
            else:
                continue

            # Check volume
            if "Volume" in df.columns:
                recent_vol = df["Volume"].iloc[-5:].mean()
                avg_vol = df["Volume"].iloc[-20:].mean()
                if avg_vol > 0 and recent_vol / avg_vol < min_volume_ratio:
                    continue

            discovered = self._analyze_stock(ticker, DiscoverySource.MOMENTUM_BREAKOUT)
            if discovered:
                candidates.append(discovered)

        print(f"    Found {len(candidates)} momentum breakouts")
        return candidates

    def scan_oversold_bounces(self, universe: List[str] = None) -> List[DiscoveredStock]:
        """
        Find quality stocks at oversold levels starting to recover.

        Criteria (configurable via discovery.scan_thresholds):
        - RSI recently < threshold (default 35), now crossing above
        - Still above 200-day SMA (uptrend intact)
        - Volume pickup on recovery
        """
        print("  Scanning for oversold bounces...")
        universe = universe or self.scan_universe
        candidates = []

        thresholds = self.discovery_config.get("scan_thresholds", {}).get("oversold_bounces", {})
        rsi_oversold = thresholds.get("rsi_oversold", 35)

        for ticker in universe:
            df = self._fetch_price_data(ticker, "1y")
            if df is None or len(df) < 200 or "Close" not in df.columns:
                continue

            close = df["Close"]
            current = float(close.iloc[-1])

            # Check if above 200 SMA
            sma_200 = close.rolling(200).mean().iloc[-1]
            if current < sma_200:
                continue

            # Compute full RSI series vectorially (single pass) — checking 14 bars
            # for a cleaner cross-above signal. The previous approach recomputed RSI
            # from scratch 5× per ticker (O(n×m)), which was ~100× slower.
            rsi_full = _compute_rsi_series(close, 14)
            rsi_window = rsi_full.iloc[-14:]  # last 14 bars
            if len(rsi_window) < 5:
                continue

            # Was oversold in window (not just current bar) and is now recovering
            was_oversold = rsi_window.iloc[:-1].min() < rsi_oversold
            now_recovering = float(rsi_window.iloc[-1]) > rsi_oversold

            if not (was_oversold and now_recovering):
                continue

            # Volume confirmation: recovery should have above-average participation.
            # Thin-air bounces (low volume recovery) are unreliable.
            min_vol_confirmation = thresholds.get("min_volume_confirmation_ratio", 1.3)
            if "Volume" in df.columns and len(df) >= 20:
                recent_vol = df["Volume"].iloc[-3:].mean()
                avg_vol = df["Volume"].iloc[-20:].mean()
                if avg_vol > 0 and recent_vol < avg_vol * min_vol_confirmation:
                    continue

            discovered = self._analyze_stock(ticker, DiscoverySource.OVERSOLD_BOUNCE)
            if discovered:
                candidates.append(discovered)

        print(f"    Found {len(candidates)} oversold bounces")
        return candidates

    def scan_sector_leaders(self, universe: List[str] = None) -> List[DiscoveredStock]:
        """
        Find top performers in leading sectors.

        Criteria (configurable via discovery.scan_thresholds):
        - Sector ETF showing positive 1-month momentum > threshold (default 5%)
        - Stock outperforming its sector ETF
        - Strong relative strength
        """
        print("  Scanning for sector leaders...")
        universe = universe or self.scan_universe
        candidates = []

        thresholds = self.discovery_config.get("scan_thresholds", {}).get("sector_leaders", {})
        min_sector_momentum = thresholds.get("min_sector_momentum", 5)

        # First, identify leading sectors
        leading_sectors = []
        for sector, etf in self.SECTOR_ETFS.items():
            df = self._fetch_price_data(etf, "3mo")
            if df is None or len(df) < 20:
                continue
            close = df["Close"]
            mom = ((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]) * 100
            if mom > min_sector_momentum:  # Sector showing positive momentum
                leading_sectors.append((sector, etf, mom))

        # Sort by momentum
        leading_sectors.sort(key=lambda x: x[2], reverse=True)
        top_sectors = [s[0] for s in leading_sectors[:3]]

        if not top_sectors:
            print("    No leading sectors found")
            return candidates

        print(f"    Leading sectors: {', '.join(top_sectors)}")

        # Find stocks in leading sectors
        # Use ONLY pre-cached info — avoids 500+ sequential .info calls that cause 3min hangs
        for ticker in universe:
            df = self._fetch_price_data(ticker, "3mo")
            if not self._passes_price_volume_filter(ticker, df):
                continue

            # Only use pre-warmed info cache — no lazy fetches here
            info = self._info_cache.get(ticker)
            if not info:
                continue
            sector = info.get("sector", "")
            if sector not in top_sectors:
                continue

            # Check if outperforming sector
            if len(df) < 20:
                continue

            stock_mom = ((df["Close"].iloc[-1] - df["Close"].iloc[-20]) / df["Close"].iloc[-20]) * 100

            # Find sector momentum
            sector_etf = self.SECTOR_ETFS.get(sector)
            if sector_etf:
                sector_df = self._fetch_price_data(sector_etf, "3mo")
                if sector_df is not None and len(sector_df) >= 20:
                    sector_mom = ((sector_df["Close"].iloc[-1] - sector_df["Close"].iloc[-20]) / sector_df["Close"].iloc[-20]) * 100
                    if stock_mom <= sector_mom:
                        continue  # Not outperforming

            discovered = self._analyze_stock(ticker, DiscoverySource.SECTOR_LEADER)
            if discovered:
                candidates.append(discovered)

        print(f"    Found {len(candidates)} sector leaders")
        return candidates

    def scan_volume_anomalies(self, universe: List[str] = None) -> List[DiscoveredStock]:
        """
        Find stocks with unusual volume activity (potential accumulation).

        Criteria (configurable via discovery.scan_thresholds):
        - Recent volume > Xx 20-day average (default 2.5x)
        - Price up (not distribution)
        - Consistent over multiple days
        """
        print("  Scanning for volume anomalies...")
        universe = universe or self.scan_universe
        candidates = []

        thresholds = self.discovery_config.get("scan_thresholds", {}).get("volume_anomalies", {})
        min_volume_ratio = thresholds.get("min_volume_ratio", 2.0)

        for ticker in universe:
            df = self._fetch_price_data(ticker, "3mo")
            if df is None or len(df) < 25:
                continue

            if "Volume" not in df.columns:
                continue

            close = df["Close"]
            volume = df["Volume"]

            # Check volume ratio
            recent_vol = volume.iloc[-3:].mean()
            avg_vol = volume.iloc[-25:-5].mean()

            if avg_vol <= 0:
                continue

            vol_ratio = recent_vol / avg_vol
            if vol_ratio < min_volume_ratio:
                continue

            # Check price action over 3-day window, not just last 1 day.
            # A stock that had up-volume but gave back intraday is bullish consolidation —
            # the single-day check incorrectly filtered these out.
            if len(close) < 4:
                continue
            price_change_3d = ((close.iloc[-1] - close.iloc[-4]) / close.iloc[-4]) * 100
            if price_change_3d < 0:
                continue  # Net distribution over the accumulation window, not accumulation

            discovered = self._analyze_stock(ticker, DiscoverySource.VOLUME_ANOMALY)
            if discovered:
                candidates.append(discovered)

        print(f"    Found {len(candidates)} volume anomalies")
        return candidates

    def scan_relative_volume_surge(self, universe: List[str] = None) -> List[DiscoveredStock]:
        """
        Find stocks with same-day relative volume surges — the highest-signal
        small-cap discovery trigger.

        Criteria (configurable via discovery.scan_thresholds):
        - Current-day volume ≥ 4x the 30-day average (default threshold: 4.0x)
        - Price up ≥ 2% on the day (default: 2.0%)
        - 30-day baseline excludes last 5 days to avoid spike contamination

        Unlike scan_volume_anomalies (which looks at 3-day average vs 20-day),
        this scan focuses on the current single day vs a clean 30-day baseline.
        A stock trading 4x+ normal volume today with a 2%+ price gain has
        institutional sponsorship happening NOW.
        """
        print("  Scanning for relative volume surges...")
        universe = universe or self.scan_universe
        candidates = []

        thresholds = self.discovery_config.get("scan_thresholds", {}).get("relative_volume_surge", {})
        min_rvol = thresholds.get("min_rvol", 4.0)
        min_price_change_pct = thresholds.get("min_price_change_pct", 2.0)

        for ticker in universe:
            df = self._fetch_price_data(ticker, "3mo")
            if df is None or len(df) < 31:
                continue

            if "Volume" not in df.columns or "Close" not in df.columns:
                continue

            close = df["Close"]
            volume = df["Volume"]

            # Baseline: 30-day average excluding last 5 days (no contamination)
            baseline_vol = volume.iloc[-35:-5].mean() if len(volume) >= 35 else volume.iloc[:-5].mean()
            if baseline_vol <= 0 or pd.isna(baseline_vol):
                continue

            current_vol = float(volume.iloc[-1])
            if pd.isna(current_vol) or current_vol <= 0:
                continue

            rvol = current_vol / baseline_vol
            if rvol < min_rvol:
                continue

            # Price must be up on the day (accumulation, not distribution)
            if len(close) < 2:
                continue
            prev_close = float(close.iloc[-2])
            current_close = self._live_prices.get(ticker) or float(close.iloc[-1])
            if prev_close <= 0:
                continue

            price_change_pct = (current_close - prev_close) / prev_close * 100
            if price_change_pct < min_price_change_pct:
                continue

            discovered = self._analyze_stock(ticker, DiscoverySource.RELATIVE_VOLUME_SURGE)
            if discovered:
                # Annotate with rvol data in notes
                discovered.notes = (
                    f"RVOL {rvol:.1f}x ({price_change_pct:+.1f}% today)"
                    + (f", {discovered.notes}" if discovered.notes and discovered.notes != "Standard candidate" else "")
                )
                candidates.append(discovered)

        print(f"    Found {len(candidates)} relative volume surges")
        return candidates

    def _prewarm_cache(self, tickers: List[str], chunk_size: int = 200) -> None:
        """Batch-download price data in chunks to avoid rate limits."""
        import time

        for period in ("1y", "3mo"):
            uncached = [t for t in tickers if f"{t}_{period}" not in self._price_cache]
            if not uncached:
                continue

            # Split into chunks to avoid Yahoo rate limiting on large batches
            chunks = [uncached[i:i + chunk_size] for i in range(0, len(uncached), chunk_size)]
            print(f"  Batch downloading {len(uncached)} tickers ({period}) in {len(chunks)} chunk(s)...")

            for chunk_idx, chunk in enumerate(chunks):
                if chunk_idx > 0:
                    time.sleep(5)  # Pause between chunks to avoid rate limits
                try:
                    raw = cached_download(
                        chunk, period=period, progress=False, auto_adjust=True, group_by="ticker"
                    )
                    if raw.empty:
                        continue
                    for ticker in chunk:
                        try:
                            if len(chunk) == 1:
                                df = raw.copy()
                            else:
                                df = raw[ticker].copy()
                            if df.empty:
                                continue
                            if isinstance(df.columns, pd.MultiIndex):
                                df.columns = df.columns.get_level_values(0)
                            df = df.loc[:, ~df.columns.duplicated()]
                            for col in ["Close", "High", "Low", "Volume", "Open"]:
                                if col in df.columns and hasattr(df[col], "ndim") and df[col].ndim > 1:
                                    df[col] = df[col].iloc[:, 0]
                            if not df.empty:
                                self._price_cache[f"{ticker}_{period}"] = df
                        except Exception as e:
                            print(f"Warning: failed to cache price data for {ticker}: {e}")
                except Exception as e:
                    print(f"  Chunk {chunk_idx+1} failed ({period}): {e}")

    def _prewarm_info_cache(self, tickers: List[str], max_workers: int = 8) -> None:
        """Fetch stock info for tickers in parallel, with per-ticker timeout."""
        # Cap to avoid drowning in .info calls — shuffle first so we don't bias toward
        # alphabetically early tickers (A-B) when the universe is sorted A-Z
        import random as _random
        shuffled = list(tickers)
        _random.shuffle(shuffled)
        tickers = shuffled[:500]
        uncached = [t for t in tickers if t not in self._info_cache]
        if not uncached:
            return
        print(f"  Parallel info fetch for {len(uncached)} tickers ({max_workers} workers, 5s timeout/ticker)...")
        t0 = time.time()

        def _fetch_with_timeout(ticker: str) -> tuple:
            """Each worker uses _get_stock_info which has a hard 5s timeout."""
            return ticker, self._get_stock_info(ticker, timeout=5.0)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_with_timeout, t): t for t in uncached}
            for future in as_completed(futures):
                try:
                    ticker, info = future.result(timeout=8)
                    self._info_cache[ticker] = info
                except Exception as e:
                    ticker = futures[future]
                    print(f"  Warning: info fetch failed for {ticker}: {e}")
                    self._info_cache[ticker] = {}

        print(f"  Info pre-warm done in {time.time() - t0:.1f}s")
        # Persist newly fetched info to disk so next scan reuses it
        self._save_disk_info_cache()

    def _score_all_universe(self) -> List["DiscoveredStock"]:
        """Score every ticker in the universe directly, bypassing scan gates.

        Used when universe < 500 tickers. Runs the full 6-factor scorer on each
        ticker and returns those above min_discovery_score as candidates.
        """
        from stock_scorer import StockScorer

        scan_start = time.time()

        # Phase 1: Batch download price data
        t0 = time.time()
        self._prewarm_cache(self.scan_universe)
        print(f"  Price pre-warm done in {time.time() - t0:.1f}s")

        # Phase 1b: Public.com live prices
        try:
            from public_quotes import fetch_live_quotes, is_configured as public_configured
            if public_configured():
                t0 = time.time()
                live_prices, failures = fetch_live_quotes(self.scan_universe)
                self._live_prices = live_prices
                print(f"  Public.com live prices: {len(live_prices)} tickers in {time.time() - t0:.1f}s")
        except Exception as e:
            print(f"  Public.com price refresh skipped: {e}")

        # Phase 2: Price/volume pre-filter
        def _get_cached_df(ticker: str):
            df = self._price_cache.get(f"{ticker}_3mo")
            if df is None:
                df = self._price_cache.get(f"{ticker}_1y")
            return df

        survivors = [
            t for t in self.scan_universe
            if self._passes_price_volume_filter(t, _get_cached_df(t))
        ]
        print(f"  Price/volume pre-filter: {len(self.scan_universe)} → {len(survivors)} survivors")

        if not survivors:
            return []

        # Phase 3: Pre-warm .info for survivors
        import random as _random
        shuffled = list(survivors)
        _random.shuffle(shuffled)
        self._prewarm_info_cache(shuffled)

        # Phase 4: Score all survivors with full 6-factor model
        scorer = StockScorer(portfolio_id=self.portfolio_id)
        candidates = []

        for ticker in survivors:
            try:
                info = self._info_cache.get(ticker)
                df = _get_cached_df(ticker)
                if not self._passes_filters(ticker, df, info if isinstance(info, dict) else {}):
                    continue
                score = scorer.score_stock(ticker, info=info)
                if score and score.composite_score >= self.discovery_config.get("min_discovery_score", 30):
                    sector = ""
                    market_cap_m = (info.get("marketCap", 0) or 0) / 1e6 if isinstance(info, dict) else 0.0
                    if isinstance(info, dict):
                        sector = info.get("sector", "")
                    if self._live_prices.get(ticker):
                        current_price = float(self._live_prices[ticker])
                    elif df is not None and len(df) > 0:
                        current_price = float(df["Close"].iloc[-1])
                    else:
                        current_price = 0.0
                    avg_volume = 0
                    if df is not None and "Volume" in df.columns:
                        _vol_mean = df["Volume"].iloc[-20:].mean()
                        avg_volume = int(_vol_mean) if pd.notna(_vol_mean) else 0
                    candidates.append(DiscoveredStock(
                        ticker=ticker,
                        source="SCORE_ALL",
                        discovery_score=score.composite_score,
                        sector=sector,
                        market_cap_m=round(market_cap_m, 1),
                        avg_volume=avg_volume,
                        current_price=current_price,
                        momentum_20d=0.0,
                        rsi_14=0.0,
                        volume_ratio=0.0,
                        near_52wk_high_pct=0.0,
                        discovered_date=date.today().isoformat(),
                        notes=f"score_all | momentum={score.price_momentum_score} "
                              f"value={score.value_timing_score} quality={score.quality_score}",
                    ))
            except Exception as e:
                print(f"  Score-all: skip {ticker} ({e})")

        candidates.sort(key=lambda x: x.discovery_score, reverse=True)
        total_elapsed = time.time() - scan_start
        print(f"\nScore-all complete: {len(candidates)} candidates from {len(survivors)} scored "
              f"(in {total_elapsed:.1f}s)")

        # Write to shared cache
        try:
            from shared_universe import SharedUniverse, SharedScanResult
            from datetime import datetime as _dt
            shared = SharedUniverse()
            shared.write_results(
                self.portfolio_id or "unknown",
                [
                    SharedScanResult(
                        ticker=c.ticker,
                        composite_score=c.discovery_score,
                        scan_type="score_all",
                        sector=c.sector if hasattr(c, "sector") else "",
                        scanned_by=self.portfolio_id or "unknown",
                        scanned_at=_dt.now().isoformat(),
                        factor_scores={},
                    )
                    for c in candidates
                ],
            )
        except Exception as e:
            print(f"  Shared cache write failed (non-fatal): {e}")

        return candidates

    def run_all_scans(self) -> List[DiscoveredStock]:
        """
        Run all enabled discovery scans.

        Returns:
            List of discovered stocks, deduplicated and sorted by score
        """
        scan_types = self.discovery_config.get("scan_types", {
            "momentum_breakouts": True,
            "oversold_bounces": True,
            "sector_leaders": True,
            "volume_anomalies": True,
            "relative_volume_surge": True,
        })

        all_candidates = []
        scan_start = time.time()

        # Shuffle before capping so the MAX_UNIVERSE slice is letter-diverse,
        # not alphabetically biased toward A/B/C tickers.
        import random as _rand
        _rand.shuffle(self.scan_universe)

        # Cap universe to avoid exceeding the API timeout (~480s).
        # At ~150s per 1000 tickers, 3000 is safe; upstream extended_max already
        # limits allcap portfolios to 3000 so this is mainly a safety ceiling.
        MAX_UNIVERSE = 3000
        if len(self.scan_universe) > MAX_UNIVERSE:
            print(f"  Universe capped at {MAX_UNIVERSE} (was {len(self.scan_universe)})")
            self.scan_universe = self.scan_universe[:MAX_UNIVERSE]

        print(f"Running discovery scans on {len(self.scan_universe)} tickers...")

        # Score-All Mode: for small universes, skip scan gates and score everything directly.
        # Strict scan filters (near 52wk high, RSI < 35, volume > 2x baseline) reject everything
        # in new/small-universe portfolios — scoring all bypasses this cold-start problem.
        SCORE_ALL_THRESHOLD = 500
        if len(self.scan_universe) < SCORE_ALL_THRESHOLD:
            print(f"  Score-all mode: {len(self.scan_universe)} tickers < {SCORE_ALL_THRESHOLD} threshold")
            return self._score_all_universe()

        # Phase 1: Batch download price data
        t0 = time.time()
        self._prewarm_cache(self.scan_universe)
        print(f"  Price pre-warm done in {time.time() - t0:.1f}s")

        # Phase 1b: Refresh current prices via Public.com (real-time, single batch call).
        # Overwrites only the "today's close" data point used in scoring — OHLCV history
        # from yfinance is still used for all multi-period calculations.
        try:
            from public_quotes import fetch_live_quotes, is_configured as public_configured
            if public_configured():
                t0 = time.time()
                live_prices, failures = fetch_live_quotes(self.scan_universe)
                self._live_prices = live_prices
                print(f"  Public.com live prices: {len(live_prices)} tickers "
                      f"({len(failures)} unavailable) in {time.time() - t0:.1f}s")
        except Exception as e:
            print(f"  Public.com price refresh skipped: {e}")

        # Phase 2: Price/volume pre-filter (no .info calls, just cached price data)
        def _get_cached_df(ticker: str):
            df = self._price_cache.get(f"{ticker}_3mo")
            if df is None:
                df = self._price_cache.get(f"{ticker}_1y")
            return df

        price_vol_survivors = [
            t for t in self.scan_universe
            if self._passes_price_volume_filter(t, _get_cached_df(t))
        ]
        cached_count = sum(1 for t in self.scan_universe if _get_cached_df(t) is not None)
        print(f"  Price data cached: {cached_count}/{len(self.scan_universe)} tickers")
        print(f"  Price/volume pre-filter: {len(self.scan_universe)} → {len(price_vol_survivors)} survivors")

        if not price_vol_survivors:
            print("  WARNING: 0 survivors after price/volume filter — data fetch may have failed")
            return []

        # Phase 3: Pre-warm .info for survivors only (not the full universe).
        # Shuffle before slicing so we don't bias toward alphabetically early tickers.
        import random as _random
        shuffled_survivors = list(price_vol_survivors)
        _random.shuffle(shuffled_survivors)
        self._prewarm_info_cache(shuffled_survivors)

        # Phase 4: Run scans — each wrapped independently so one crash doesn't kill the rest
        if scan_types.get("momentum_breakouts", True):
            t0 = time.time()
            try:
                all_candidates.extend(self.scan_momentum_breakouts())
            except Exception as e:
                print(f"    Momentum scan error (skipped): {e}")
            print(f"    Momentum scan: {time.time() - t0:.1f}s")

        if scan_types.get("oversold_bounces", True):
            t0 = time.time()
            try:
                all_candidates.extend(self.scan_oversold_bounces())
            except Exception as e:
                print(f"    Oversold scan error (skipped): {e}")
            print(f"    Oversold scan: {time.time() - t0:.1f}s")

        if scan_types.get("sector_leaders", True):
            t0 = time.time()
            try:
                all_candidates.extend(self.scan_sector_leaders())
            except Exception as e:
                print(f"    Sector scan error (skipped): {e}")
            print(f"    Sector scan: {time.time() - t0:.1f}s")

        if scan_types.get("volume_anomalies", True):
            t0 = time.time()
            try:
                all_candidates.extend(self.scan_volume_anomalies())
            except Exception as e:
                print(f"    Volume scan error (skipped): {e}")
            print(f"    Volume scan: {time.time() - t0:.1f}s")

        if scan_types.get("relative_volume_surge", True):
            t0 = time.time()
            try:
                all_candidates.extend(self.scan_relative_volume_surge())
            except Exception as e:
                print(f"    Relative volume surge scan error (skipped): {e}")
            print(f"    Relative volume surge scan: {time.time() - t0:.1f}s")

        # Deduplicate by ticker (keep highest score)
        ticker_map: Dict[str, DiscoveredStock] = {}
        for candidate in all_candidates:
            existing = ticker_map.get(candidate.ticker)
            if existing is None or candidate.discovery_score > existing.discovery_score:
                ticker_map[candidate.ticker] = candidate

        # Sort by discovery score (global sort — used as-is in global mode,
        # or as pre-sort before bucket selection in bucketed mode)
        result = list(ticker_map.values())
        result.sort(key=lambda x: x.discovery_score, reverse=True)

        # Write results to shared scan cache for cross-portfolio visibility
        try:
            from shared_universe import SharedUniverse, SharedScanResult
            from datetime import datetime as _dt
            shared = SharedUniverse()
            shared.write_results(
                self.portfolio_id or "unknown",
                [
                    SharedScanResult(
                        ticker=c.ticker,
                        composite_score=c.discovery_score,
                        scan_type=c.source if hasattr(c, "source") else "unknown",
                        sector=c.sector if hasattr(c, "sector") else "",
                        scanned_by=self.portfolio_id or "unknown",
                        scanned_at=_dt.now().isoformat(),
                        factor_scores={},
                    )
                    for c in result
                ],
            )
        except Exception as e:
            print(f"  Shared cache write failed (non-fatal): {e}")

        # Bucketed mode: select top-N per sector bucket when sector_weights configured
        watchlist_cfg = self.discovery_config.get("watchlist", {})
        sector_weights = watchlist_cfg.get("sector_weights", {})
        if sector_weights:
            total_slots = watchlist_cfg.get(
                "total_watchlist_slots",
                watchlist_cfg.get("max_tickers", 150),
            )
            result = self._select_by_buckets(result, sector_weights, total_slots)
            print(f"  Bucketed selection: {len(result)} candidates across {len(sector_weights)} sectors")

        total_elapsed = time.time() - scan_start
        print(f"\nTotal unique candidates: {len(result)} (scan completed in {total_elapsed:.1f}s)")
        return result


def discover_stocks(portfolio_id: str = None) -> List[DiscoveredStock]:
    """
    Convenience function to run discovery scans.

    Args:
        portfolio_id: Optional portfolio ID for portfolio-scoped config/universe.

    Returns:
        List of discovered stock candidates
    """
    discovery = StockDiscovery(portfolio_id=portfolio_id)
    return discovery.run_all_scans()


def format_discovery_report(candidates: List[DiscoveredStock], top_n: int = 20) -> str:
    """Format discovery results as a text report."""
    lines = []
    lines.append("=" * 70)
    lines.append("STOCK DISCOVERY REPORT")
    lines.append(f"Date: {date.today().isoformat()}")
    lines.append(f"Total Candidates: {len(candidates)}")
    lines.append("=" * 70)

    if not candidates:
        lines.append("\nNo candidates found matching criteria.")
        return "\n".join(lines)

    lines.append(f"\nTOP {min(top_n, len(candidates))} DISCOVERIES:\n")
    lines.append(f"{'Rank':<5} {'Ticker':<8} {'Score':<7} {'Source':<18} {'Mom%':<8} {'RSI':<6} {'Notes'}")
    lines.append("-" * 70)

    for i, c in enumerate(candidates[:top_n], 1):
        lines.append(
            f"{i:<5} {c.ticker:<8} {c.discovery_score:<7.1f} {c.source:<18} "
            f"{c.momentum_20d:>+6.1f}% {c.rsi_14:<6.0f} {c.notes[:25]}"
        )

    # Summary by source
    lines.append("\n" + "-" * 70)
    lines.append("BY SOURCE:")
    source_counts = {}
    for c in candidates:
        source_counts[c.source] = source_counts.get(c.source, 0) + 1
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  {source}: {count}")

    return "\n".join(lines)


# ─── CLI for Testing ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n─── GScott Stock Discovery ───\n")

    candidates = discover_stocks()

    if candidates:
        report = format_discovery_report(candidates, top_n=25)
        print(report)

        # Show top 5 details
        print("\n" + "=" * 70)
        print("DETAILED VIEW - TOP 5:")
        print("=" * 70)
        for c in candidates[:5]:
            print(f"\n{c.ticker} ({c.sector})")
            print(f"  Score: {c.discovery_score} | Source: {c.source}")
            print(f"  Price: ${c.current_price} | Market Cap: ${c.market_cap_m:.0f}M")
            print(f"  Momentum: {c.momentum_20d:+.1f}% | RSI: {c.rsi_14:.0f}")
            print(f"  Volume Ratio: {c.volume_ratio:.1f}x | Near 52wk High: {c.near_52wk_high_pct:.1f}%")
            print(f"  Notes: {c.notes}")
    else:
        print("No candidates discovered.")
