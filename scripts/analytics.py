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

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from portfolio_state import load_portfolio_state


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
    # Benchmark comparison
    benchmark_return_pct: float = 0.0
    alpha_pct: float = 0.0
    beta: float = 0.0
    correlation: float = 0.0
    # Risk metrics
    var_95_pct: float = 0.0
    expected_shortfall_pct: float = 0.0


class PortfolioAnalytics:
    """Calculate professional risk-adjusted portfolio metrics."""

    def __init__(self, risk_free_rate: float = 0.05, portfolio_id: str = None):
        """
        Initialize analytics.

        Args:
            risk_free_rate: Annual risk-free rate (default 5%)
            portfolio_id: Portfolio to analyze (default: registry default)
        """
        self.risk_free_rate = risk_free_rate
        self.portfolio_id = portfolio_id
        # Load config on-demand from portfolio state
        state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
        self.config = state.config

    def load_equity_curve(self) -> pd.DataFrame:
        """Load daily equity snapshots."""
        state = load_portfolio_state(fetch_prices=False, portfolio_id=self.portfolio_id)
        df = state.snapshots
        if not df.empty and "date" in df.columns:
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

    def fetch_benchmark_data(self, start_date: str, end_date: str) -> pd.Series:
        """
        Fetch benchmark (Russell 2000) returns.

        Args:
            start_date: Start date string
            end_date: End date string

        Returns:
            Series of daily benchmark returns
        """
        try:
            import yfinance as yf

            # Try Russell 2000, fall back to IWM ETF
            for ticker in ["^RUT", "IWM"]:
                try:
                    data = yf.download(ticker, start=start_date, end=end_date, progress=False)
                    if not data.empty and "Close" in data.columns:
                        return data["Close"].pct_change().dropna()
                except Exception:
                    continue

            return pd.Series()
        except ImportError:
            return pd.Series()

    def calculate_beta(self, portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """
        Calculate portfolio beta (sensitivity to market).

        Beta > 1 = more volatile than market
        Beta < 1 = less volatile than market
        Beta < 0 = moves opposite to market

        Args:
            portfolio_returns: Daily portfolio returns
            benchmark_returns: Daily benchmark returns

        Returns:
            Portfolio beta
        """
        if len(portfolio_returns) < 10 or len(benchmark_returns) < 10:
            return 1.0

        # Align dates
        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join="inner")
        if len(aligned) < 10:
            return 1.0

        aligned.columns = ["portfolio", "benchmark"]

        # Beta = Cov(portfolio, benchmark) / Var(benchmark)
        covariance = aligned["portfolio"].cov(aligned["benchmark"])
        variance = aligned["benchmark"].var()

        if variance == 0:
            return 1.0

        return round(covariance / variance, 2)

    def calculate_alpha(
        self,
        portfolio_return: float,
        benchmark_return: float,
        beta: float,
        risk_free_rate: float = None
    ) -> float:
        """
        Calculate Jensen's Alpha (risk-adjusted excess return).

        Alpha = Portfolio Return - [Risk-free + Beta * (Benchmark Return - Risk-free)]

        Positive alpha = outperforming on risk-adjusted basis

        Args:
            portfolio_return: Total portfolio return (%)
            benchmark_return: Total benchmark return (%)
            beta: Portfolio beta
            risk_free_rate: Annual risk-free rate (default: self.risk_free_rate)

        Returns:
            Alpha as percentage
        """
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate * 100  # Convert to percentage

        expected_return = risk_free_rate + beta * (benchmark_return - risk_free_rate)
        alpha = portfolio_return - expected_return

        return round(alpha, 2)

    def calculate_var(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR) using historical method.

        VaR = What's the worst expected loss at X% confidence level?

        Args:
            returns: Daily returns series
            confidence: Confidence level (default 95%)

        Returns:
            VaR as percentage (negative number)
        """
        if len(returns) < 20:
            return 0.0

        percentile = (1 - confidence) * 100
        var = np.percentile(returns * 100, percentile)

        return round(var, 2)

    def calculate_expected_shortfall(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """
        Calculate Expected Shortfall (CVaR) - average loss beyond VaR.

        Also called Conditional VaR - answers "when things go bad, how bad?"

        Args:
            returns: Daily returns series
            confidence: Confidence level (default 95%)

        Returns:
            Expected shortfall as percentage (negative number)
        """
        if len(returns) < 20:
            return 0.0

        var = self.calculate_var(returns, confidence) / 100  # Convert back to decimal
        losses_beyond_var = returns[returns < var]

        if len(losses_beyond_var) == 0:
            return self.calculate_var(returns, confidence)

        es = losses_beyond_var.mean() * 100

        return round(es, 2)

    def calculate_correlation(self, portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """Calculate correlation with benchmark."""
        if len(portfolio_returns) < 10 or len(benchmark_returns) < 10:
            return 0.0

        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join="inner")
        if len(aligned) < 10:
            return 0.0

        aligned.columns = ["portfolio", "benchmark"]
        return round(aligned["portfolio"].corr(aligned["benchmark"]), 2)

    def stress_test(self, portfolio_returns: pd.Series, beta: float, market_drop_pct: float = -10.0) -> float:
        """
        Estimate portfolio impact from market drop.

        Args:
            portfolio_returns: Historical portfolio returns
            beta: Portfolio beta
            market_drop_pct: Hypothetical market drop (default -10%)

        Returns:
            Estimated portfolio drop as percentage
        """
        # Simple beta-based estimate
        estimated_drop = beta * market_drop_pct

        return round(estimated_drop, 2)

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

        # Benchmark comparison
        benchmark_return = 0.0
        alpha = 0.0
        beta = 1.0
        correlation = 0.0

        if "date" in df.columns and len(df) >= 5:
            start_date = df["date"].iloc[0]
            end_date = df["date"].iloc[-1]
            benchmark_returns = self.fetch_benchmark_data(str(start_date)[:10], str(end_date)[:10])

            if not benchmark_returns.empty:
                # Ensure benchmark_returns is a 1-D Series
                if hasattr(benchmark_returns, "columns"):
                    benchmark_returns = benchmark_returns.iloc[:, 0]

                # Calculate benchmark total return
                benchmark_equity = (1 + benchmark_returns).cumprod()
                if len(benchmark_equity) > 0:
                    benchmark_return = round(float((benchmark_equity.iloc[-1] - 1) * 100), 2)

                # Beta and correlation
                beta = float(self.calculate_beta(returns, benchmark_returns))
                correlation = float(self.calculate_correlation(returns, benchmark_returns))

                # Alpha (risk-adjusted excess return)
                alpha = float(self.calculate_alpha(total_return, benchmark_return, beta))

        # VaR and Expected Shortfall
        var_95 = self.calculate_var(returns, 0.95)
        expected_shortfall = self.calculate_expected_shortfall(returns, 0.95)

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
            benchmark_return_pct=benchmark_return,
            alpha_pct=alpha,
            beta=beta,
            correlation=correlation,
            var_95_pct=var_95,
            expected_shortfall_pct=expected_shortfall,
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
        print("─── Benchmark Comparison (vs Russell 2000) ───\n")
        print(f"  Portfolio Return: {metrics.total_return_pct:+.2f}%")
        print(f"  Benchmark Return: {metrics.benchmark_return_pct:+.2f}%")
        print(f"  Alpha:            {metrics.alpha_pct:+.2f}%")
        print(f"  Beta:             {metrics.beta:.2f}")
        print(f"  Correlation:      {metrics.correlation:.2f}")
        print()
        print("─── Risk Metrics ───\n")
        print(f"  VaR (95%):        {metrics.var_95_pct:.2f}% daily")
        print(f"  Expected Shortfall: {metrics.expected_shortfall_pct:.2f}% daily")
        print()

    def stress_test_report(self, scenarios: list[float] = None):
        """
        Print stress test report for various market scenarios.

        Args:
            scenarios: List of market drop percentages (default: -5, -10, -20, -30)
        """
        if scenarios is None:
            scenarios = [-5.0, -10.0, -20.0, -30.0]

        metrics = self.calculate_all_metrics()
        if metrics is None:
            print("  Insufficient data for stress testing")
            return

        print("\n─── Stress Test: What if Market Drops? ───\n")
        print(f"  Portfolio Beta: {metrics.beta:.2f}")
        print()

        for drop in scenarios:
            estimated_impact = metrics.beta * drop
            print(f"  If market drops {abs(drop):.0f}%: Portfolio ~{estimated_impact:+.1f}%")

        print()


if __name__ == "__main__":
    analytics = PortfolioAnalytics()
    analytics.print_metrics_report()
