#!/usr/bin/env python3
"""
Portfolio Analytics Module for MicroCapRebuilder.

Provides professional-grade risk-adjusted metrics:
- Sharpe Ratio
- Sortino Ratio
- Maximum Drawdown
- Calmar Ratio
- Portfolio Exposure

Usage:
    from analytics import PortfolioAnalytics
    analytics = PortfolioAnalytics()
    metrics = analytics.calculate_all_metrics()
"""

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from data_files import get_daily_snapshots_file, load_config as load_base_config, CONFIG_FILE


@dataclass
class RiskMetrics:
    """Container for portfolio risk metrics."""
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    max_drawdown_start: str
    max_drawdown_end: str
    calmar_ratio: float
    volatility_annual: float
    total_return_pct: float
    cagr_pct: float
    current_drawdown_pct: float
    exposure_pct: float
    days_tracked: int


def load_config() -> dict:
    """Load configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"starting_capital": 5000.0}


class PortfolioAnalytics:
    """Calculate professional risk-adjusted portfolio metrics."""

    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize analytics.

        Args:
            risk_free_rate: Annual risk-free rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate
        self.config = load_config()

    def load_equity_curve(self) -> pd.DataFrame:
        """Load daily equity snapshots."""
        snapshots_file = get_daily_snapshots_file()
        if not snapshots_file.exists():
            return pd.DataFrame()

        df = pd.read_csv(snapshots_file)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
        return df

    def calculate_returns(self, equity_series: pd.Series) -> pd.Series:
        """Calculate daily returns from equity series."""
        return equity_series.pct_change().dropna()

    def calculate_sharpe_ratio(self, returns: pd.Series) -> float:
        """
        Calculate annualized Sharpe Ratio.

        Sharpe = (Return - Risk-free Rate) / Volatility

        Args:
            returns: Daily returns series

        Returns:
            Annualized Sharpe Ratio
        """
        if len(returns) < 2:
            return 0.0

        # Annualize
        annual_return = returns.mean() * 252
        annual_vol = returns.std() * np.sqrt(252)

        if annual_vol == 0:
            return 0.0

        sharpe = (annual_return - self.risk_free_rate) / annual_vol
        return round(sharpe, 2)

    def calculate_sortino_ratio(self, returns: pd.Series) -> float:
        """
        Calculate annualized Sortino Ratio.

        Sortino = (Return - Risk-free Rate) / Downside Volatility

        Args:
            returns: Daily returns series

        Returns:
            Annualized Sortino Ratio
        """
        if len(returns) < 2:
            return 0.0

        # Annualize
        annual_return = returns.mean() * 252

        # Downside deviation (only negative returns)
        negative_returns = returns[returns < 0]
        if len(negative_returns) == 0:
            return 10.0  # No downside = very high ratio

        downside_vol = negative_returns.std() * np.sqrt(252)

        if downside_vol == 0:
            return 10.0

        sortino = (annual_return - self.risk_free_rate) / downside_vol
        return round(sortino, 2)

    def calculate_max_drawdown(
        self, equity_series: pd.Series
    ) -> tuple[float, str, str]:
        """
        Calculate maximum drawdown.

        Args:
            equity_series: Daily equity values

        Returns:
            Tuple of (max_drawdown_pct, peak_date, trough_date)
        """
        if len(equity_series) < 2:
            return 0.0, "", ""

        # Calculate running maximum
        running_max = equity_series.expanding().max()

        # Drawdown at each point
        drawdowns = (equity_series - running_max) / running_max

        # Find max drawdown
        max_dd_idx = drawdowns.idxmin()
        max_dd = drawdowns.iloc[drawdowns.index.get_loc(max_dd_idx)]

        # Find peak before max drawdown
        peak_idx = running_max.iloc[:drawdowns.index.get_loc(max_dd_idx) + 1].idxmax()

        peak_date = str(peak_idx)[:10] if hasattr(peak_idx, '__str__') else ""
        trough_date = str(max_dd_idx)[:10] if hasattr(max_dd_idx, '__str__') else ""

        return round(max_dd * 100, 2), peak_date, trough_date

    def calculate_current_drawdown(self, equity_series: pd.Series) -> float:
        """Calculate current drawdown from peak."""
        if len(equity_series) < 1:
            return 0.0

        peak = equity_series.max()
        current = equity_series.iloc[-1]

        if peak == 0:
            return 0.0

        dd = (current - peak) / peak * 100
        return round(dd, 2)

    def calculate_calmar_ratio(
        self, returns: pd.Series, max_drawdown: float
    ) -> float:
        """
        Calculate Calmar Ratio.

        Calmar = Annual Return / |Max Drawdown|

        Args:
            returns: Daily returns series
            max_drawdown: Maximum drawdown percentage (negative)

        Returns:
            Calmar Ratio
        """
        if len(returns) < 2 or max_drawdown == 0:
            return 0.0

        annual_return = returns.mean() * 252 * 100  # As percentage

        calmar = annual_return / abs(max_drawdown)
        return round(calmar, 2)

    def calculate_cagr(self, equity_series: pd.Series, days: int) -> float:
        """
        Calculate Compound Annual Growth Rate.

        Args:
            equity_series: Equity values
            days: Number of trading days

        Returns:
            CAGR as percentage
        """
        if len(equity_series) < 2 or days == 0:
            return 0.0

        start_value = equity_series.iloc[0]
        end_value = equity_series.iloc[-1]

        if start_value == 0:
            return 0.0

        # Convert days to years (252 trading days)
        years = days / 252

        if years == 0:
            return 0.0

        cagr = ((end_value / start_value) ** (1 / years) - 1) * 100
        return round(cagr, 2)

    def calculate_exposure(self, positions_value: float, total_equity: float) -> float:
        """
        Calculate portfolio exposure percentage.

        Args:
            positions_value: Total value in positions
            total_equity: Total portfolio equity

        Returns:
            Exposure as percentage
        """
        if total_equity == 0:
            return 0.0

        return round((positions_value / total_equity) * 100, 1)

    def calculate_all_metrics(self) -> Optional[RiskMetrics]:
        """
        Calculate all portfolio metrics.

        Returns:
            RiskMetrics dataclass or None if insufficient data
        """
        df = self.load_equity_curve()

        if df.empty or "total_equity" not in df.columns:
            return None

        equity = df["total_equity"]
        returns = self.calculate_returns(equity)

        if len(returns) < 2:
            return None

        # Calculate all metrics
        sharpe = self.calculate_sharpe_ratio(returns)
        sortino = self.calculate_sortino_ratio(returns)
        max_dd, dd_start, dd_end = self.calculate_max_drawdown(equity)
        calmar = self.calculate_calmar_ratio(returns, max_dd)
        current_dd = self.calculate_current_drawdown(equity)

        # Volatility
        annual_vol = returns.std() * np.sqrt(252) * 100

        # Total return
        start_equity = self.config.get("starting_capital", equity.iloc[0])
        total_return = ((equity.iloc[-1] - start_equity) / start_equity) * 100

        # CAGR
        cagr = self.calculate_cagr(equity, len(df))

        # Exposure (from latest snapshot)
        positions_value = df["positions_value"].iloc[-1] if "positions_value" in df.columns else 0
        exposure = self.calculate_exposure(positions_value, equity.iloc[-1])

        return RiskMetrics(
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown_pct=max_dd,
            max_drawdown_start=dd_start,
            max_drawdown_end=dd_end,
            calmar_ratio=calmar,
            volatility_annual=round(annual_vol, 2),
            total_return_pct=round(total_return, 2),
            cagr_pct=cagr,
            current_drawdown_pct=current_dd,
            exposure_pct=exposure,
            days_tracked=len(df),
        )

    def print_metrics_report(self):
        """Print a formatted metrics report."""
        metrics = self.calculate_all_metrics()

        if metrics is None:
            print("  Insufficient data for metrics calculation")
            return

        print("\n─── Portfolio Risk Metrics ───\n")
        print(f"  Days Tracked:     {metrics.days_tracked}")
        print(f"  Total Return:     {metrics.total_return_pct:+.2f}%")
        print(f"  CAGR:             {metrics.cagr_pct:+.2f}%")
        print(f"  Annual Volatility: {metrics.volatility_annual:.2f}%")
        print()
        print(f"  Sharpe Ratio:     {metrics.sharpe_ratio:.2f}")
        print(f"  Sortino Ratio:    {metrics.sortino_ratio:.2f}")
        print(f"  Calmar Ratio:     {metrics.calmar_ratio:.2f}")
        print()
        print(f"  Max Drawdown:     {metrics.max_drawdown_pct:.2f}%")
        print(f"    From: {metrics.max_drawdown_start}")
        print(f"    To:   {metrics.max_drawdown_end}")
        print(f"  Current Drawdown: {metrics.current_drawdown_pct:.2f}%")
        print()
        print(f"  Exposure:         {metrics.exposure_pct:.1f}%")
        print()


if __name__ == "__main__":
    analytics = PortfolioAnalytics()
    analytics.print_metrics_report()
