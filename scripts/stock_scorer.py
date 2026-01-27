#!/usr/bin/env python3
"""
Stock Scorer Module for MicroCapRebuilder.

Multi-factor scoring system for ranking watchlist candidates:
- Momentum (30%): 20-day price change
- Volatility (20%): Lower volatility = higher score
- Volume (15%): Recent volume vs average (liquidity)
- Relative Strength (25%): Performance vs benchmark
- Mean Reversion (10%): Distance from 20-day SMA

Usage:
    from stock_scorer import StockScorer
    scorer = StockScorer()
    scores = scorer.score_watchlist(tickers)
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


@dataclass
class StockScore:
    """Holds scoring data for a single stock."""
    ticker: str
    momentum_score: float
    volatility_score: float
    volume_score: float
    relative_strength_score: float
    mean_reversion_score: float
    composite_score: float
    current_price: float
    atr_pct: float  # Average True Range as % of price (for position sizing)


def load_config() -> dict:
    """Load configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
        "volatility_lookback_days": 20,
    }


class StockScorer:
    """Multi-factor stock scoring system."""

    # Factor weights (must sum to 1.0)
    WEIGHTS = {
        "momentum": 0.30,
        "volatility": 0.20,
        "volume": 0.15,
        "relative_strength": 0.25,
        "mean_reversion": 0.10,
    }

    def __init__(self, lookback_days: int = 20):
        self.config = load_config()
        self.lookback_days = lookback_days
        self._benchmark_data = None

    def _fetch_price_data(self, ticker: str, period: str = "1mo") -> Optional[pd.DataFrame]:
        """Fetch historical price data for a ticker."""
        try:
            df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
            if df.empty:
                return None
            # Flatten multi-level columns if present (newer yfinance versions)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
        except Exception:
            return None

    def _get_benchmark_data(self) -> Optional[pd.DataFrame]:
        """Fetch benchmark data (cached)."""
        if self._benchmark_data is not None:
            return self._benchmark_data

        for symbol in [self.config["benchmark_symbol"], self.config.get("fallback_benchmark", "IWM")]:
            df = self._fetch_price_data(symbol, period="1mo")
            if df is not None and not df.empty:
                self._benchmark_data = df
                return df
        return None

    def score_momentum(self, df: pd.DataFrame) -> float:
        """
        Score based on price momentum (20-day return).
        Returns 0-100 score.
        """
        if df is None or len(df) < 5:
            return 50.0  # Neutral score if insufficient data

        lookback = min(self.lookback_days, len(df))
        start_price = df["Close"].iloc[-lookback]
        end_price = df["Close"].iloc[-1]

        if start_price <= 0:
            return 50.0

        pct_change = ((end_price - start_price) / start_price) * 100

        # Map to 0-100 scale
        # -20% or worse = 0, +20% or better = 100
        score = 50 + (pct_change * 2.5)
        return max(0, min(100, score))

    def score_volatility(self, df: pd.DataFrame) -> float:
        """
        Score based on volatility (lower = better for microcaps).
        Returns 0-100 score.
        """
        if df is None or len(df) < 5:
            return 50.0

        # Calculate daily returns volatility
        returns = df["Close"].pct_change().dropna()
        if len(returns) < 5:
            return 50.0

        volatility = returns.std() * 100  # As percentage

        # Map to 0-100 scale (inverted - lower volatility = higher score)
        # 0% vol = 100, 5%+ daily vol = 0
        score = 100 - (volatility * 20)
        return max(0, min(100, score))

    def score_volume(self, df: pd.DataFrame) -> float:
        """
        Score based on recent volume vs average (liquidity check).
        Returns 0-100 score.
        """
        if df is None or len(df) < 10:
            return 50.0

        if "Volume" not in df.columns:
            return 50.0

        recent_vol = df["Volume"].iloc[-5:].mean()
        avg_vol = df["Volume"].iloc[-20:].mean()

        if avg_vol <= 0:
            return 50.0

        vol_ratio = recent_vol / avg_vol

        # Map to 0-100 scale
        # 0.5x average = 25, 1x = 50, 2x = 100
        score = vol_ratio * 50
        return max(0, min(100, score))

    def score_relative_strength(self, df: pd.DataFrame) -> float:
        """
        Score based on performance vs benchmark.
        Returns 0-100 score.
        """
        if df is None or len(df) < 5:
            return 50.0

        benchmark_df = self._get_benchmark_data()
        if benchmark_df is None or len(benchmark_df) < 5:
            return 50.0

        # Calculate returns over matching period
        lookback = min(self.lookback_days, len(df), len(benchmark_df))

        stock_start = df["Close"].iloc[-lookback]
        stock_end = df["Close"].iloc[-1]
        stock_return = ((stock_end - stock_start) / stock_start) * 100 if stock_start > 0 else 0

        bench_start = benchmark_df["Close"].iloc[-lookback]
        bench_end = benchmark_df["Close"].iloc[-1]
        bench_return = ((bench_end - bench_start) / bench_start) * 100 if bench_start > 0 else 0

        # Relative strength = outperformance
        outperformance = stock_return - bench_return

        # Map to 0-100 scale
        # -10% underperformance = 25, 0 = 50, +10% outperformance = 75
        score = 50 + (outperformance * 2.5)
        return max(0, min(100, score))

    def score_mean_reversion(self, df: pd.DataFrame) -> float:
        """
        Score based on distance from 20-day SMA.
        Stocks near SMA score higher (less extended).
        Returns 0-100 score.
        """
        if df is None or len(df) < 20:
            return 50.0

        current_price = df["Close"].iloc[-1]
        sma_20 = df["Close"].iloc[-20:].mean()

        if sma_20 <= 0:
            return 50.0

        # Distance from SMA as percentage
        distance_pct = ((current_price - sma_20) / sma_20) * 100

        # Map to 0-100 scale (closer to SMA = higher score)
        # At SMA = 100, 10% away = 50, 20%+ away = 0
        score = 100 - abs(distance_pct) * 5
        return max(0, min(100, score))

    def calculate_atr_percent(self, df: pd.DataFrame) -> float:
        """
        Calculate Average True Range as percentage of price.
        Used for volatility-adjusted position sizing.
        """
        if df is None or len(df) < 14:
            return 3.0  # Default to 3%

        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        # True Range calculation
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.iloc[-14:].mean()

        current_price = close.iloc[-1]
        if current_price <= 0:
            return 3.0

        atr_pct = (atr / current_price) * 100
        return round(atr_pct, 2)

    def score_stock(self, ticker: str) -> Optional[StockScore]:
        """
        Calculate composite score for a single stock.
        Returns StockScore object or None if data unavailable.
        """
        df = self._fetch_price_data(ticker, period="1mo")
        if df is None or df.empty:
            return None

        momentum = self.score_momentum(df)
        volatility = self.score_volatility(df)
        volume = self.score_volume(df)
        rel_strength = self.score_relative_strength(df)
        mean_rev = self.score_mean_reversion(df)

        # Weighted composite score
        composite = (
            momentum * self.WEIGHTS["momentum"]
            + volatility * self.WEIGHTS["volatility"]
            + volume * self.WEIGHTS["volume"]
            + rel_strength * self.WEIGHTS["relative_strength"]
            + mean_rev * self.WEIGHTS["mean_reversion"]
        )

        current_price = float(df["Close"].iloc[-1])
        atr_pct = self.calculate_atr_percent(df)

        return StockScore(
            ticker=ticker,
            momentum_score=round(momentum, 1),
            volatility_score=round(volatility, 1),
            volume_score=round(volume, 1),
            relative_strength_score=round(rel_strength, 1),
            mean_reversion_score=round(mean_rev, 1),
            composite_score=round(composite, 1),
            current_price=round(current_price, 2),
            atr_pct=atr_pct,
        )

    def score_watchlist(self, tickers: List[str]) -> List[StockScore]:
        """
        Score all tickers in watchlist and return sorted by composite score.

        Args:
            tickers: List of ticker symbols

        Returns:
            List of StockScore objects, sorted by composite score (highest first)
        """
        scores = []

        for ticker in tickers:
            score = self.score_stock(ticker)
            if score is not None:
                scores.append(score)

        # Sort by composite score (highest first)
        scores.sort(key=lambda s: s.composite_score, reverse=True)
        return scores

    def get_top_picks(
        self, tickers: List[str], n: int = 5, min_score: float = 50.0
    ) -> List[StockScore]:
        """
        Get top N picks from watchlist that meet minimum score.

        Args:
            tickers: List of ticker symbols
            n: Number of top picks to return
            min_score: Minimum composite score to include

        Returns:
            Top N StockScore objects meeting criteria
        """
        all_scores = self.score_watchlist(tickers)
        filtered = [s for s in all_scores if s.composite_score >= min_score]
        return filtered[:n]
