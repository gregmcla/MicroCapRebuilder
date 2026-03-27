#!/usr/bin/env python3
"""
Stock Scorer Module for GScott.

Multi-factor scoring system for ranking watchlist candidates.
Weights are configurable per market regime (BULL/SIDEWAYS/BEAR).

Factors:
- Price Momentum: Multi-TF momentum + RS vs benchmark (combined)
- Earnings Growth: earningsQuarterlyGrowth + revenueGrowth + P/E comparison
- Quality: Gross margins + ROE + debt-to-equity
- Volume: Recent volume vs average (liquidity)
- Volatility: Lower volatility = higher score
- Value Timing: SMA distance + RSI sweet-spot (combined)

Usage:
    from stock_scorer import StockScorer
    from market_regime import MarketRegime

    scorer = StockScorer(regime=MarketRegime.BULL)
    scores = scorer.score_watchlist(tickers)
"""

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from yf_session import cached_download

# Import MarketRegime if available (avoid circular import)
try:
    from market_regime import MarketRegime
except ImportError:
    # Define a simple enum if market_regime not available
    class MarketRegime(Enum):
        BULL = "bull"
        BEAR = "bear"
        SIDEWAYS = "sideways"
        UNKNOWN = "unknown"

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


@dataclass
class StockScore:
    """Holds scoring data for a single stock."""
    ticker: str
    price_momentum_score: float   # replaces momentum + relative_strength
    earnings_growth_score: float  # NEW: fundamental factor
    quality_score: float          # NEW: fundamental factor
    volume_score: float
    volatility_score: float
    value_timing_score: float     # replaces mean_reversion + rsi
    composite_score: float
    current_price: float
    atr_pct: float  # Average True Range as % of price (for position sizing)
    # Metadata for explainability
    rsi_value: float = 0.0
    momentum_5d: float = 0.0
    momentum_20d: float = 0.0
    momentum_60d: float = 0.0
    momentum_alignment: str = ""
    # Fundamental metadata (populated when .info dict is passed)
    revenue_growth: Optional[float] = None
    earnings_growth_pct: Optional[float] = None
    gross_margins: Optional[float] = None
    roe: Optional[float] = None
    debt_to_equity: Optional[float] = None
    forward_pe: Optional[float] = None
    trailing_pe: Optional[float] = None
    company_description: str = ""


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
    """Multi-factor stock scoring system with regime-aware weights."""

    # Default weights (used if config doesn't specify)
    DEFAULT_WEIGHTS = {
        "price_momentum": 0.25,
        "earnings_growth": 0.15,
        "quality": 0.15,
        "volume": 0.10,
        "volatility": 0.15,
        "value_timing": 0.20,
    }

    def __init__(self, regime: Optional[MarketRegime] = None, lookback_days: int = 20):
        """
        Initialize scorer with optional market regime.

        Args:
            regime: Current market regime (BULL/SIDEWAYS/BEAR) for weight selection
            lookback_days: Number of days for technical calculations
        """
        self.config = load_config()
        self.regime = regime
        self.lookback_days = lookback_days
        self._benchmark_data = None
        self._weights = self._load_weights()

    def _load_weights(self) -> Dict[str, float]:
        """
        Load weights from config default_weights.

        Regime weights are intentionally ignored — the composite score already
        reflects market conditions through real-time factors (momentum, volume,
        volatility). Regime reweighting toward stale fundamental factors (quality,
        earnings) adds noise, not signal. The learning pipeline owns weight
        optimization based on actual trade outcomes.
        """
        scoring_config = self.config.get("scoring", {})
        raw_defaults = scoring_config.get("default_weights") or dict(self.DEFAULT_WEIGHTS)
        return self._migrate_weight_keys(raw_defaults)

    @staticmethod
    def _migrate_weight_keys(weights: Dict[str, float]) -> Dict[str, float]:
        """
        Convert old weight keys to new keys for backward compatibility.

        Old: momentum, relative_strength, mean_reversion, rsi, volume, volatility
        New: price_momentum, earnings_growth, quality, volume, volatility, value_timing
        """
        if not weights:
            return weights

        old_keys = {"momentum", "relative_strength", "mean_reversion", "rsi"}
        if not any(k in weights for k in old_keys):
            return weights  # Already using new keys

        # Merge correlated factors
        momentum = weights.get("momentum", 0.0)
        rel_strength = weights.get("relative_strength", 0.0)
        mean_rev = weights.get("mean_reversion", 0.0)
        rsi_w = weights.get("rsi", 0.0)

        combined_pm = momentum + rel_strength   # → price_momentum
        combined_vt = mean_rev + rsi_w          # → value_timing
        vol = weights.get("volume", 0.0)
        volatility = weights.get("volatility", 0.0)

        # Scale existing factors to 0.70 to make room for 2 new fundamentals (0.30)
        existing_total = combined_pm + combined_vt + vol + volatility
        if existing_total > 0:
            scale = 0.70 / existing_total
            combined_pm *= scale
            combined_vt *= scale
            vol *= scale
            volatility *= scale

        migrated: Dict[str, float] = {
            "price_momentum": combined_pm,
            "value_timing": combined_vt,
            "volume": vol,
            "volatility": volatility,
            "earnings_growth": 0.15,
            "quality": 0.15,
        }

        # Normalize to sum exactly 1.0
        total = sum(migrated.values())
        if total > 0:
            migrated = {k: round(v / total, 4) for k, v in migrated.items()}
            diff = round(1.0 - sum(migrated.values()), 4)
            if diff != 0:
                largest = max(migrated, key=migrated.get)
                migrated[largest] = round(migrated[largest] + diff, 4)

        return migrated

    def get_active_weights(self) -> Dict[str, float]:
        """Return the currently active weights for transparency."""
        return self._weights.copy()

    def get_min_score_threshold(self) -> float:
        """Get minimum score threshold (flat, regime-independent)."""
        scoring_config = self.config.get("scoring", {})
        threshold = scoring_config.get("min_score_threshold", 35.0)
        # Support legacy dict format — use the most permissive value
        if isinstance(threshold, dict):
            return min(threshold.values()) if threshold else 35.0
        return float(threshold)

    def _fetch_price_data(self, ticker: str, period: str = "1mo") -> Optional[pd.DataFrame]:
        """Fetch historical price data for a ticker."""
        try:
            df = cached_download(ticker, period=period, progress=False, auto_adjust=True)
            if df.empty:
                return None
            # Flatten multi-level columns if present (newer yfinance versions)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            # Deduplicate columns — yfinance can return duplicate "Close" etc.
            df = df.loc[:, ~df.columns.duplicated()]
            # Ensure key columns are scalar (not Series) by squeezing
            for col in ["Close", "High", "Low", "Volume", "Open"]:
                if col in df.columns and hasattr(df[col], "ndim") and df[col].ndim > 1:
                    df[col] = df[col].iloc[:, 0]
            return df
        except Exception as e:
            print(f"Warning: price data fetch failed: {e}")
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

    # ─── RSI Calculation ─────────────────────────────────────────────────────────

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).

        Args:
            df: DataFrame with Close prices
            period: RSI period (default 14)

        Returns:
            Series of RSI values
        """
        if df is None or len(df) < period + 1:
            return pd.Series([50.0])

        close = df["Close"]
        delta = close.diff()

        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        # Use exponential moving average for smoothing
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()

        # Avoid division by zero
        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))

        return rsi.fillna(50.0)

    def score_rsi(self, df: pd.DataFrame) -> Tuple[float, float]:
        """
        Score based on RSI for momentum strategy.

        For momentum: prefer RSI 50-70 (healthy momentum)
        Avoid: RSI > 80 (overextended) or RSI < 30 (might be broken)

        Args:
            df: DataFrame with price data

        Returns:
            Tuple of (score 0-100, raw RSI value)
        """
        rsi_config = self.config.get("scoring", {}).get("rsi", {})
        period = rsi_config.get("period", 14)
        hard_filter = rsi_config.get("hard_filter_above", 85)

        rsi_series = self._calculate_rsi(df, period)
        current_rsi = float(rsi_series.iloc[-1])

        # Hard filter: extremely overbought = very low score
        if current_rsi > hard_filter:
            return 10.0, current_rsi

        # Scoring zones for momentum strategy
        if 50 <= current_rsi <= 65:
            score = 90.0  # Sweet spot for momentum
        elif 65 < current_rsi <= 72:
            score = 75.0  # Good momentum but getting extended
        elif 72 < current_rsi <= 78:
            score = 55.0  # Overbought warning
        elif 78 < current_rsi <= 85:
            score = 35.0  # Significantly overbought
        elif 45 <= current_rsi < 50:
            score = 70.0  # Just below momentum zone
        elif 40 <= current_rsi < 45:
            score = 55.0  # Neutral-low
        elif 35 <= current_rsi < 40:
            score = 45.0  # Getting oversold
        elif 30 <= current_rsi < 35:
            score = 40.0  # Oversold zone
        else:  # < 30
            score = 30.0  # Extremely oversold (risky for momentum)

        return score, current_rsi

    # ─── Multi-Timeframe Momentum ────────────────────────────────────────────────

    def _calculate_momentum_pct(self, df: pd.DataFrame, days: int) -> float:
        """Calculate momentum (percent change) over N days."""
        if df is None or len(df) < days:
            return 0.0

        lookback = min(days, len(df))
        start_price = float(df["Close"].iloc[-lookback])
        end_price = float(df["Close"].iloc[-1])

        if math.isnan(start_price) or math.isnan(end_price) or start_price <= 0:
            return 0.0

        return ((end_price - start_price) / start_price) * 100

    def _score_single_momentum(self, pct_change: float) -> float:
        """Convert a momentum percentage to a 0-100 score."""
        # Map: -20% = 0, 0% = 50, +20% = 100
        score = 50 + (pct_change * 2.5)
        return max(0, min(100, score))

    def _calculate_momentum_alignment(
        self, mom_5d: float, mom_20d: float, mom_60d: float
    ) -> Tuple[str, float]:
        """
        Calculate alignment across timeframes.

        Returns:
            Tuple of (alignment label, bonus points)
        """
        # Check signs
        signs = [
            1 if mom_5d > 0 else -1,
            1 if mom_20d > 0 else -1,
            1 if mom_60d > 0 else -1,
        ]

        alignment_sum = sum(signs)

        if alignment_sum == 3:
            # All positive - check for acceleration
            if mom_5d > mom_20d > mom_60d:
                return "ACCELERATING", 15.0
            elif mom_5d > mom_20d:
                return "ALIGNED_STRONG", 10.0
            else:
                return "ALIGNED", 5.0
        elif alignment_sum == -3:
            return "BEARISH", -10.0
        elif alignment_sum == 1:
            return "MIXED_BULLISH", 0.0
        else:
            return "MIXED_BEARISH", -5.0

    def score_momentum(self, df: pd.DataFrame) -> Tuple[float, Dict]:
        """
        Multi-timeframe momentum score with alignment bonus.

        Analyzes 5-day, 20-day, and 60-day momentum with weighted combination
        and bonuses for timeframe alignment and acceleration.

        Args:
            df: DataFrame with price data

        Returns:
            Tuple of (score 0-100, metadata dict)
        """
        if df is None or len(df) < 5:
            return 50.0, {"mom_5d": 0, "mom_20d": 0, "mom_60d": 0, "alignment": "UNKNOWN"}

        # Get momentum config
        mom_config = self.config.get("scoring", {}).get("momentum", {})
        multi_tf_enabled = mom_config.get("multi_timeframe_enabled", True)

        # Calculate momentum for each timeframe
        mom_5d = self._calculate_momentum_pct(df, 5)
        mom_20d = self._calculate_momentum_pct(df, 20)
        mom_60d = self._calculate_momentum_pct(df, min(60, len(df)))

        metadata = {
            "mom_5d": round(mom_5d, 2),
            "mom_20d": round(mom_20d, 2),
            "mom_60d": round(mom_60d, 2),
        }

        if not multi_tf_enabled:
            # Fall back to simple 20-day momentum
            score = self._score_single_momentum(mom_20d)
            metadata["alignment"] = "SINGLE_TF"
            return score, metadata

        # Get timeframe weights from config
        tf_config = mom_config.get("timeframes", {})
        weight_5d = tf_config.get("short", {}).get("weight", 0.20)
        weight_20d = tf_config.get("medium", {}).get("weight", 0.50)
        weight_60d = tf_config.get("long", {}).get("weight", 0.30)

        # Score each timeframe
        score_5d = self._score_single_momentum(mom_5d)
        score_20d = self._score_single_momentum(mom_20d)
        score_60d = self._score_single_momentum(mom_60d)

        # Weighted base score
        base_score = (
            score_5d * weight_5d +
            score_20d * weight_20d +
            score_60d * weight_60d
        )

        # Calculate alignment bonus
        alignment_label, alignment_bonus = self._calculate_momentum_alignment(
            mom_5d, mom_20d, mom_60d
        )
        metadata["alignment"] = alignment_label

        # Apply alignment bonus (capped)
        max_bonus = mom_config.get("alignment_bonus_max", 15)
        final_bonus = max(-max_bonus, min(max_bonus, alignment_bonus))

        final_score = base_score + final_bonus
        return max(0, min(100, final_score)), metadata

    def score_momentum_simple(self, df: pd.DataFrame) -> float:
        """
        Simple momentum score based on price momentum (20-day return).
        Legacy method kept for backwards compatibility.
        Returns 0-100 score.
        """
        if df is None or len(df) < 5:
            return 50.0  # Neutral score if insufficient data

        lookback = min(self.lookback_days, len(df))
        start_price = float(df["Close"].iloc[-lookback])
        end_price = float(df["Close"].iloc[-1])

        if math.isnan(start_price) or math.isnan(end_price) or start_price <= 0:
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
        if math.isnan(volatility):
            return 50.0

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

        recent_vol = float(df["Volume"].iloc[-5:].mean())
        avg_vol = float(df["Volume"].iloc[-20:].mean())

        if math.isnan(avg_vol) or math.isnan(recent_vol) or avg_vol <= 0:
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

        stock_start = float(df["Close"].iloc[-lookback])
        stock_end = float(df["Close"].iloc[-1])
        if math.isnan(stock_start) or math.isnan(stock_end) or stock_start <= 0:
            stock_return = 0.0
        else:
            stock_return = ((stock_end - stock_start) / stock_start) * 100

        bench_start = float(benchmark_df["Close"].iloc[-lookback])
        bench_end = float(benchmark_df["Close"].iloc[-1])
        if math.isnan(bench_start) or math.isnan(bench_end) or bench_start <= 0:
            bench_return = 0.0
        else:
            bench_return = ((bench_end - bench_start) / bench_start) * 100

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

        current_price = float(df["Close"].iloc[-1])
        sma_20 = float(df["Close"].iloc[-20:].mean())

        if math.isnan(current_price) or math.isnan(sma_20) or sma_20 <= 0:
            return 50.0

        # Distance from SMA as percentage
        distance_pct = ((current_price - sma_20) / sma_20) * 100

        # Map to 0-100 scale (closer to SMA = higher score)
        # At SMA = 100, 10% away = 50, 20%+ away = 0
        score = 100 - abs(distance_pct) * 5
        return max(0, min(100, score))

    def score_price_momentum(self, df: pd.DataFrame) -> Tuple[float, Dict]:
        """
        Combined price momentum score: 60% multi-TF momentum + 40% relative strength.
        Alignment bonus is already embedded in the momentum component.
        """
        if df is None or len(df) < 5:
            return 50.0, {"mom_5d": 0, "mom_20d": 0, "mom_60d": 0, "alignment": "UNKNOWN"}

        mom_score, mom_metadata = self.score_momentum(df)
        rs_score = self.score_relative_strength(df)

        combined = mom_score * 0.60 + rs_score * 0.40
        return max(0.0, min(100.0, round(combined, 1))), mom_metadata

    def score_earnings_growth(self, info: dict) -> float:
        """
        Score based on earnings and revenue growth from yfinance .info dict.
        Returns 50 (neutral) when data is unavailable — never penalizes missing data.
        """
        if not info:
            return 50.0

        scores = []

        # Earnings quarterly growth
        eq_growth = info.get("earningsQuarterlyGrowth")
        if eq_growth is not None:
            if eq_growth > 0.20:
                scores.append(85.0)
            elif eq_growth > 0.05:
                scores.append(70.0)
            elif eq_growth > -0.05:
                scores.append(50.0)
            else:
                scores.append(30.0)

        # Revenue growth
        rev_growth = info.get("revenueGrowth")
        if rev_growth is not None:
            if rev_growth > 0.15:
                scores.append(80.0)
            elif rev_growth > 0.05:
                scores.append(65.0)
            elif rev_growth > -0.05:
                scores.append(50.0)
            else:
                scores.append(30.0)

        # Forward vs trailing P/E (lower forward PE = earnings expected to grow)
        try:
            trailing_pe = float(info.get("trailingPE") or 0) or None
            forward_pe = float(info.get("forwardPE") or 0) or None
        except (ValueError, TypeError):
            trailing_pe = None
            forward_pe = None
        if trailing_pe and forward_pe and trailing_pe > 0 and forward_pe > 0:
            if forward_pe < trailing_pe * 0.85:
                scores.append(75.0)
            elif forward_pe < trailing_pe:
                scores.append(62.0)
            else:
                scores.append(45.0)

        if not scores:
            return 50.0
        return round(sum(scores) / len(scores), 1)

    def score_quality(self, info: dict) -> float:
        """
        Score based on business quality metrics from yfinance .info dict.
        Returns 50 (neutral) when data is unavailable — never penalizes missing data.
        Note: yfinance debtToEquity is often in ×100 form (50 = 0.5 ratio).
        """
        if not info:
            return 50.0

        scores = []

        # Gross margins
        gross_margins = info.get("grossMargins")
        if gross_margins is not None:
            if gross_margins > 0.40:
                scores.append(85.0)
            elif gross_margins > 0.20:
                scores.append(65.0)
            elif gross_margins > 0.00:
                scores.append(50.0)
            else:
                scores.append(20.0)

        # Return on equity
        roe = info.get("returnOnEquity")
        if roe is not None:
            if roe > 0.15:
                scores.append(80.0)
            elif roe > 0.05:
                scores.append(60.0)
            elif roe > 0.00:
                scores.append(50.0)
            else:
                scores.append(20.0)

        # Debt to equity (lower = better; yfinance uses ×100 form: 50 = 0.5 ratio)
        d2e = info.get("debtToEquity")
        if d2e is not None and d2e >= 0:
            if d2e < 50:     # < 0.5 ratio
                scores.append(80.0)
            elif d2e < 100:  # < 1.0 ratio
                scores.append(65.0)
            elif d2e < 200:  # < 2.0 ratio
                scores.append(50.0)
            else:
                scores.append(30.0)

        if not scores:
            return 50.0
        return round(sum(scores) / len(scores), 1)

    def score_value_timing(self, df: pd.DataFrame) -> float:
        """
        Combined value/timing score: 50% SMA distance + 50% RSI sweet-spot.
        Replaces separate mean_reversion and rsi factors.
        """
        if df is None or len(df) < 14:
            return 50.0

        mean_rev = self.score_mean_reversion(df)
        rsi_score, _ = self.score_rsi(df)

        combined = mean_rev * 0.50 + rsi_score * 0.50
        return max(0.0, min(100.0, round(combined, 1)))

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
        atr = float(tr.iloc[-14:].mean())

        current_price = float(close.iloc[-1])
        if math.isnan(atr) or math.isnan(current_price) or current_price <= 0:
            return 3.0

        atr_pct = (atr / current_price) * 100
        return round(atr_pct, 2)

    def score_stock(self, ticker: str, info: Optional[dict] = None) -> Optional["StockScore"]:
        """
        Calculate composite score for a single stock.

        Args:
            ticker: Stock ticker symbol
            info: Optional yfinance .info dict for fundamental scoring.
                  If None, fundamental scores default to 50 (neutral).

        Returns:
            StockScore object or None if price data unavailable.
        """
        # Fetch extended data for multi-timeframe analysis
        df = self._fetch_price_data(ticker, period="3mo")
        if df is None or df.empty:
            return None

        info_dict = info or {}

        # Price/volume factors
        price_momentum, mom_metadata = self.score_price_momentum(df)
        volume = self.score_volume(df)
        volatility = self.score_volatility(df)
        value_timing = self.score_value_timing(df)

        # Fundamental factors (default 50 if no info)
        earnings_growth = self.score_earnings_growth(info_dict)
        quality = self.score_quality(info_dict)

        # RSI value for metadata
        rsi_series = self._calculate_rsi(df)
        rsi_value = float(rsi_series.iloc[-1])

        # Weighted composite score using regime-aware weights
        w = self._weights
        composite = (
            price_momentum * w.get("price_momentum", 0.25)
            + earnings_growth * w.get("earnings_growth", 0.15)
            + quality * w.get("quality", 0.15)
            + volume * w.get("volume", 0.10)
            + volatility * w.get("volatility", 0.15)
            + value_timing * w.get("value_timing", 0.20)
        )

        current_price = float(df["Close"].iloc[-1])
        if math.isnan(current_price) or current_price <= 0:
            return None

        atr_pct = self.calculate_atr_percent(df)
        if math.isnan(atr_pct) or atr_pct <= 0:
            atr_pct = 2.0  # Safe fallback: 2% ATR

        return StockScore(
            ticker=ticker,
            price_momentum_score=round(price_momentum, 1),
            earnings_growth_score=round(earnings_growth, 1),
            quality_score=round(quality, 1),
            volume_score=round(volume, 1),
            volatility_score=round(volatility, 1),
            value_timing_score=round(value_timing, 1),
            composite_score=round(composite, 1),
            current_price=round(current_price, 2),
            atr_pct=atr_pct,
            rsi_value=round(rsi_value, 1),
            momentum_5d=mom_metadata.get("mom_5d", 0.0),
            momentum_20d=mom_metadata.get("mom_20d", 0.0),
            momentum_60d=mom_metadata.get("mom_60d", 0.0),
            momentum_alignment=mom_metadata.get("alignment", ""),
            revenue_growth=info_dict.get("revenueGrowth"),
            earnings_growth_pct=info_dict.get("earningsQuarterlyGrowth"),
            gross_margins=info_dict.get("grossMargins"),
            roe=info_dict.get("returnOnEquity"),
            debt_to_equity=info_dict.get("debtToEquity"),
            forward_pe=info_dict.get("forwardPE"),
            trailing_pe=info_dict.get("trailingPE"),
            company_description=(info_dict.get("longBusinessSummary") or "")[:200],
        )

    def score_watchlist(self, tickers: List[str], info_cache: Optional[Dict[str, dict]] = None) -> List[StockScore]:
        """
        Score all tickers in watchlist and return sorted by composite score.

        Args:
            tickers: List of ticker symbols
            info_cache: Optional dict mapping ticker -> yfinance .info dict.
                        When provided, enables fundamental scoring.

        Returns:
            List of StockScore objects, sorted by composite score (highest first)
        """
        scores = []

        for ticker in tickers:
            info = (info_cache or {}).get(ticker)
            score = self.score_stock(ticker, info=info)
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
