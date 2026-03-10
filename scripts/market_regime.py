#!/usr/bin/env python3
"""
Market Regime Detection for MicroCapRebuilder.

Detects market regime based on benchmark position relative to moving averages:
- BULL: Benchmark above both 50-day and 200-day SMA
- BEAR: Benchmark below both 50-day and 200-day SMA
- SIDEWAYS: Mixed signals (above one, below the other)

Usage:
    from market_regime import get_market_regime, MarketRegime
    regime = get_market_regime()
    if regime == MarketRegime.BEAR:
        # Reduce position sizes or skip buying
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import pandas as pd
from yf_session import cached_download

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


class MarketRegime(Enum):
    """Market regime classification."""
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeAnalysis:
    """Detailed regime analysis data."""
    regime: MarketRegime
    benchmark_symbol: str
    current_price: float
    sma_50: float
    sma_200: float
    above_50: bool
    above_200: bool
    regime_strength: str  # "strong", "weak"


def load_config() -> dict:
    """Load configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
    }


def fetch_benchmark_data(symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """Fetch benchmark historical data."""
    try:
        df = cached_download(symbol, period=period, progress=False, auto_adjust=True)
        if df.empty:
            return None
        return df
    except Exception:
        return None


def analyze_regime(df: pd.DataFrame, symbol: str) -> RegimeAnalysis:
    """
    Analyze market regime from price data.

    Args:
        df: DataFrame with price data (needs 200+ days ideally)
        symbol: Benchmark symbol name

    Returns:
        RegimeAnalysis with detailed breakdown
    """
    if df is None or len(df) < 50:
        return RegimeAnalysis(
            regime=MarketRegime.UNKNOWN,
            benchmark_symbol=symbol,
            current_price=0,
            sma_50=0,
            sma_200=0,
            above_50=False,
            above_200=False,
            regime_strength="unknown",
        )

    # Handle multi-level columns from yfinance
    from portfolio_state import flatten_yf_close
    close_col = flatten_yf_close(df)

    current_price = float(close_col.iloc[-1])
    sma_50 = float(close_col.iloc[-50:].mean())

    # Use available data for 200 SMA, or fall back to what we have
    if len(df) >= 200:
        sma_200 = float(close_col.iloc[-200:].mean())
    else:
        sma_200 = float(close_col.mean())  # Use all available data

    # Require 3 consecutive closes on the same side of each MA to avoid
    # whipsawing when price oscillates around the moving average.
    recent_3 = close_col.iloc[-3:] if len(close_col) >= 3 else close_col
    above_50 = bool((recent_3 > sma_50).all())
    above_200 = bool((recent_3 > sma_200).all())
    below_50 = bool((recent_3 < sma_50).all())
    below_200 = bool((recent_3 < sma_200).all())

    # Determine regime
    if above_50 and above_200:
        regime = MarketRegime.BULL
        distance_50 = (current_price - sma_50) / sma_50
        distance_200 = (current_price - sma_200) / sma_200
        strength = "strong" if distance_50 > 0.05 and distance_200 > 0.05 else "weak"
    elif below_50 and below_200:
        regime = MarketRegime.BEAR
        distance_50 = (sma_50 - current_price) / sma_50
        distance_200 = (sma_200 - current_price) / sma_200
        strength = "strong" if distance_50 > 0.05 and distance_200 > 0.05 else "weak"
    else:
        regime = MarketRegime.SIDEWAYS
        strength = "weak"

    return RegimeAnalysis(
        regime=regime,
        benchmark_symbol=symbol,
        current_price=round(current_price, 2),
        sma_50=round(sma_50, 2),
        sma_200=round(sma_200, 2),
        above_50=above_50,
        above_200=above_200,
        regime_strength=strength,
    )


def get_market_regime(
    benchmark_symbol: str = None,
    fallback_benchmark: str = None,
) -> MarketRegime:
    """
    Get current market regime.

    Returns:
        MarketRegime enum value
    """
    analysis = get_regime_analysis(benchmark_symbol=benchmark_symbol,
                                   fallback_benchmark=fallback_benchmark)
    return analysis.regime


def get_regime_analysis(
    benchmark_symbol: str = None,
    fallback_benchmark: str = None,
) -> RegimeAnalysis:
    """
    Get detailed market regime analysis.

    Args:
        benchmark_symbol: Override benchmark (e.g. "^GSPC" for allcap portfolios).
                          Defaults to the global config value.
        fallback_benchmark: Override fallback ETF. Defaults to global config value.

    Returns:
        RegimeAnalysis with full breakdown
    """
    config = load_config()
    primary = benchmark_symbol or config["benchmark_symbol"]
    fallback = fallback_benchmark or config.get("fallback_benchmark", "IWM")

    # Try primary benchmark first
    for symbol in [primary, fallback]:
        df = fetch_benchmark_data(symbol, period="1y")
        if df is not None and not df.empty:
            return analyze_regime(df, symbol)

    # Return unknown if all benchmarks fail
    return RegimeAnalysis(
        regime=MarketRegime.UNKNOWN,
        benchmark_symbol="N/A",
        current_price=0,
        sma_50=0,
        sma_200=0,
        above_50=False,
        above_200=False,
        regime_strength="unknown",
    )


def get_position_size_multiplier(regime: MarketRegime) -> float:
    """
    Get position size multiplier based on market regime.

    Args:
        regime: Current market regime

    Returns:
        Multiplier (0.0 to 1.0) for position sizing
    """
    multipliers = {
        MarketRegime.BULL: 1.0,      # Full size in bull market
        MarketRegime.SIDEWAYS: 0.75, # Moderate size in sideways market
        MarketRegime.BEAR: 0.50,     # Half size — cautious buying, not a full stop
        MarketRegime.UNKNOWN: 0.75,  # Moderate size — new portfolio, assume neutral
    }
    return multipliers.get(regime, 0.5)


def should_buy_new_positions(regime: MarketRegime) -> bool:
    """
    Determine if new positions should be opened based on regime.

    Args:
        regime: Current market regime

    Returns:
        True if buying is allowed, False otherwise
    """
    return regime in [MarketRegime.BULL, MarketRegime.SIDEWAYS, MarketRegime.UNKNOWN]


def print_regime_report():
    """Print a formatted regime analysis report."""
    analysis = get_regime_analysis()

    emoji = {
        MarketRegime.BULL: "🐂",
        MarketRegime.BEAR: "🐻",
        MarketRegime.SIDEWAYS: "↔️",
        MarketRegime.UNKNOWN: "❓",
    }

    print("\n─── Market Regime Analysis ───\n")
    print(f"  Benchmark: {analysis.benchmark_symbol}")
    print(f"  Current:   ${analysis.current_price:,.2f}")
    print(f"  50-day SMA:  ${analysis.sma_50:,.2f} ({'above' if analysis.above_50 else 'below'})")
    print(f"  200-day SMA: ${analysis.sma_200:,.2f} ({'above' if analysis.above_200 else 'below'})")
    print(f"\n  Regime: {emoji.get(analysis.regime, '')} {analysis.regime.value} ({analysis.regime_strength})")
    print(f"  Position multiplier: {get_position_size_multiplier(analysis.regime):.0%}")
    print()


if __name__ == "__main__":
    print_regime_report()
