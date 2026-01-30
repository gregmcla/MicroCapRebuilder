#!/usr/bin/env python3
"""
Stock Discovery Module for Mommy Bot.

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
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)

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


def load_config() -> dict:
    """Load configuration."""
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


class StockDiscovery:
    """
    Discovers new stock candidates through multiple scanning strategies.

    Uses yfinance for data (no external API keys required).
    """

    # Russell 2000 proxy - small cap ETF components would be ideal
    # For now, using a list of known small-cap tickers as seed universe
    SCAN_UNIVERSE = [
        # Technology
        "CRDO", "MOD", "OKLO", "AVAV", "IDCC", "UPST", "AI", "SYNA", "MGNI",
        "CALX", "ACLS", "EXTR", "AGYS", "AX",
        # Financials
        "SFBS", "WSBC", "BOH", "CBU", "BANF", "PFSI", "BANR",
        # Consumer
        "ANF", "URBN", "AEO", "CAKE", "EAT", "FUN", "GOLF",
        # Energy & Materials
        "CRC", "BTU", "MGY", "SM", "KTB",
        # Healthcare
        "GH", "FOLD", "ADMA", "AXSM", "ARWR", "ADUS", "CRSP",
        # Industrials
        "JBT", "TEX", "TDW", "ABM", "HURN", "GFF", "VC",
        # REITs
        "SBRA", "KRG", "OUT", "HASI",
        # Utilities
        "AWR", "ALE", "MGEE",
        # Other
        "WDFC", "SMPL", "BELFB", "LMND", "RIOT", "SMR", "ITRI",
        # Additional small caps for broader coverage
        "APPS", "PRFT", "PLAB", "LIVN", "HLIT", "DOMO", "BSIG",
        "PRGS", "RUN", "SEDG", "ENPH", "STEM", "CHPT", "BLNK",
        "IONQ", "RKLB", "ASTR", "MNDY", "GTLB", "PATH", "CFLT",
    ]

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

    def __init__(self):
        self.config = load_config()
        self.discovery_config = self.config.get("discovery", {})
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._info_cache: Dict[str, dict] = {}

    def _fetch_price_data(self, ticker: str, period: str = "3mo") -> Optional[pd.DataFrame]:
        """Fetch and cache price data."""
        cache_key = f"{ticker}_{period}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        try:
            df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
            if df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            self._price_cache[cache_key] = df
            return df
        except Exception:
            return None

    def _get_stock_info(self, ticker: str) -> dict:
        """Fetch and cache stock info."""
        if ticker in self._info_cache:
            return self._info_cache[ticker]

        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            self._info_cache[ticker] = info
            return info
        except Exception:
            return {}

    def _passes_filters(self, ticker: str, df: pd.DataFrame, info: dict) -> bool:
        """Check if stock passes basic filters."""
        filters = self.discovery_config.get("filters", {})

        # Market cap filter
        market_cap = info.get("marketCap", 0)
        min_cap = filters.get("min_market_cap_m", 300) * 1e6
        max_cap = filters.get("max_market_cap_m", 5000) * 1e6
        if market_cap < min_cap or market_cap > max_cap:
            return False

        # Volume filter
        if df is not None and "Volume" in df.columns:
            avg_vol = df["Volume"].iloc[-20:].mean()
            min_vol = filters.get("min_avg_volume", 200000)
            if avg_vol < min_vol:
                return False

        # Price filter
        if df is not None and len(df) > 0:
            current_price = float(df["Close"].iloc[-1])
            min_price = filters.get("min_price", 5.0)
            max_price = filters.get("max_price", 500.0)
            if current_price < min_price or current_price > max_price:
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
        current_price = float(close.iloc[-1])

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

        # 52-week high proximity
        high_52wk = close.max()
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
        avg_volume = int(df["Volume"].iloc[-20:].mean()) if "Volume" in df.columns else 0

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

    # ─── Scan Types ──────────────────────────────────────────────────────────────

    def scan_momentum_breakouts(self, universe: List[str] = None) -> List[DiscoveredStock]:
        """
        Find stocks breaking out with momentum.

        Criteria:
        - Within 10% of 52-week high
        - 20-day momentum > 10%
        - Volume ratio > 1.3x average
        """
        print("  Scanning for momentum breakouts...")
        universe = universe or self.SCAN_UNIVERSE
        candidates = []

        for ticker in universe:
            df = self._fetch_price_data(ticker, "1y")
            if df is None or len(df) < 50:
                continue

            close = df["Close"]
            current = float(close.iloc[-1])
            high_52wk = close.max()

            # Check if near 52-week high
            pct_from_high = ((high_52wk - current) / high_52wk) * 100
            if pct_from_high > 10:
                continue

            # Check momentum
            if len(close) >= 20:
                mom_20d = ((current - close.iloc[-20]) / close.iloc[-20]) * 100
                if mom_20d < 10:
                    continue
            else:
                continue

            # Check volume
            if "Volume" in df.columns:
                recent_vol = df["Volume"].iloc[-5:].mean()
                avg_vol = df["Volume"].iloc[-20:].mean()
                if avg_vol > 0 and recent_vol / avg_vol < 1.3:
                    continue

            discovered = self._analyze_stock(ticker, DiscoverySource.MOMENTUM_BREAKOUT)
            if discovered:
                candidates.append(discovered)

        print(f"    Found {len(candidates)} momentum breakouts")
        return candidates

    def scan_oversold_bounces(self, universe: List[str] = None) -> List[DiscoveredStock]:
        """
        Find quality stocks at oversold levels starting to recover.

        Criteria:
        - RSI recently < 35, now crossing above
        - Still above 200-day SMA (uptrend intact)
        - Volume pickup on recovery
        """
        print("  Scanning for oversold bounces...")
        universe = universe or self.SCAN_UNIVERSE
        candidates = []

        for ticker in universe:
            df = self._fetch_price_data(ticker, "1y")
            if df is None or len(df) < 200:
                continue

            close = df["Close"]
            current = float(close.iloc[-1])

            # Check if above 200 SMA
            sma_200 = close.rolling(200).mean().iloc[-1]
            if current < sma_200:
                continue

            # Check RSI recovery
            rsi_series = pd.Series([calculate_rsi(close.iloc[:i+1], 14) for i in range(len(close)-5, len(close))])
            if len(rsi_series) < 3:
                continue

            # Was recently oversold and now recovering
            was_oversold = rsi_series.iloc[:-1].min() < 35
            now_recovering = rsi_series.iloc[-1] > 35

            if not (was_oversold and now_recovering):
                continue

            discovered = self._analyze_stock(ticker, DiscoverySource.OVERSOLD_BOUNCE)
            if discovered:
                candidates.append(discovered)

        print(f"    Found {len(candidates)} oversold bounces")
        return candidates

    def scan_sector_leaders(self, universe: List[str] = None) -> List[DiscoveredStock]:
        """
        Find top performers in leading sectors.

        Criteria:
        - Sector ETF showing positive 1-month momentum
        - Stock outperforming its sector ETF
        - Strong relative strength
        """
        print("  Scanning for sector leaders...")
        universe = universe or self.SCAN_UNIVERSE
        candidates = []

        # First, identify leading sectors
        leading_sectors = []
        for sector, etf in self.SECTOR_ETFS.items():
            df = self._fetch_price_data(etf, "3mo")
            if df is None or len(df) < 20:
                continue
            close = df["Close"]
            mom = ((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]) * 100
            if mom > 5:  # Sector showing positive momentum
                leading_sectors.append((sector, etf, mom))

        # Sort by momentum
        leading_sectors.sort(key=lambda x: x[2], reverse=True)
        top_sectors = [s[0] for s in leading_sectors[:3]]

        if not top_sectors:
            print("    No leading sectors found")
            return candidates

        print(f"    Leading sectors: {', '.join(top_sectors)}")

        # Find stocks in leading sectors
        for ticker in universe:
            info = self._get_stock_info(ticker)
            sector = info.get("sector", "")
            if sector not in top_sectors:
                continue

            # Check if outperforming sector
            df = self._fetch_price_data(ticker, "3mo")
            if df is None or len(df) < 20:
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

        Criteria:
        - Recent volume > 2.5x 20-day average
        - Price up (not distribution)
        - Consistent over multiple days
        """
        print("  Scanning for volume anomalies...")
        universe = universe or self.SCAN_UNIVERSE
        candidates = []

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
            if vol_ratio < 2.5:
                continue

            # Check price action (should be up)
            price_change = ((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]) * 100
            if price_change < 0:
                continue  # Distribution, not accumulation

            discovered = self._analyze_stock(ticker, DiscoverySource.VOLUME_ANOMALY)
            if discovered:
                candidates.append(discovered)

        print(f"    Found {len(candidates)} volume anomalies")
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
            "volume_anomalies": False,
        })

        all_candidates = []

        print("Running discovery scans...")

        if scan_types.get("momentum_breakouts", True):
            all_candidates.extend(self.scan_momentum_breakouts())

        if scan_types.get("oversold_bounces", True):
            all_candidates.extend(self.scan_oversold_bounces())

        if scan_types.get("sector_leaders", True):
            all_candidates.extend(self.scan_sector_leaders())

        if scan_types.get("volume_anomalies", False):
            all_candidates.extend(self.scan_volume_anomalies())

        # Deduplicate by ticker (keep highest score)
        ticker_map: Dict[str, DiscoveredStock] = {}
        for candidate in all_candidates:
            existing = ticker_map.get(candidate.ticker)
            if existing is None or candidate.discovery_score > existing.discovery_score:
                ticker_map[candidate.ticker] = candidate

        # Sort by discovery score
        result = list(ticker_map.values())
        result.sort(key=lambda x: x.discovery_score, reverse=True)

        print(f"\nTotal unique candidates: {len(result)}")
        return result


def discover_stocks() -> List[DiscoveredStock]:
    """
    Convenience function to run discovery scans.

    Returns:
        List of discovered stock candidates
    """
    discovery = StockDiscovery()
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
    print("\n─── Mommy Bot Stock Discovery ───\n")

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
