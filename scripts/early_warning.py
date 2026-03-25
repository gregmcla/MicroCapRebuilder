#!/usr/bin/env python3
"""
Early Warning System for GScott.

Detects potential issues before they cause damage:
- Regime shifts (benchmark crossing key moving averages)
- Strategy degradation (grade dropping, win rate declining)
- Factor breakdowns (specific factors underperforming)
- Concentration risk (single position too large)
- Losing streaks (consecutive losses)
- Volatility spikes (market turbulence)

Usage:
    from early_warning import get_warnings, Warning
    warnings = get_warnings()
    for w in warnings:
        print(f"[{w.severity}] {w.title}: {w.description}")
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import json
import pandas as pd
import numpy as np

from market_regime import get_regime_analysis, MarketRegime
from trade_analyzer import TradeAnalyzer
from portfolio_state import load_portfolio_state


class WarningSeverity(Enum):
    """Warning severity levels."""
    INFO = "info"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Warning:
    """An early warning alert."""
    id: str
    title: str
    description: str
    severity: WarningSeverity
    category: str  # regime, performance, risk, factor, pattern
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    action_suggestion: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class EarlyWarningSystem:
    """Detect early warning signs across the portfolio."""

    # Warning thresholds
    THRESHOLDS = {
        "losing_streak": 4,  # Consecutive losses
        "win_rate_low": 35.0,  # % over recent trades
        "drawdown_warning": 8.0,  # %
        "drawdown_critical": 12.0,  # %
        "concentration_warning": 20.0,  # % in single position
        "concentration_critical": 30.0,  # %
        "position_count_high": 30,  # Over-diversification warning
        "regime_sma_proximity": 2.0,  # % from 50-day SMA
    }

    def __init__(self, portfolio_id: str = None):
        self.state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
        self.trade_analyzer = TradeAnalyzer(portfolio_id=portfolio_id)

    def check_all(self) -> List[Warning]:
        """Run all warning checks and return active warnings."""
        warnings = []

        # Run all checks
        warnings.extend(self._check_regime_shift())
        warnings.extend(self._check_drawdown(self.state.snapshots))
        warnings.extend(self._check_losing_streak(self.state.transactions))
        warnings.extend(self._check_win_rate())
        warnings.extend(self._check_concentration(self.state.positions))
        warnings.extend(self._check_position_count(self.state.positions))
        warnings.extend(self._check_positions_near_stop(self.state.positions))

        # Sort by severity (critical first)
        severity_order = {
            WarningSeverity.CRITICAL: 0,
            WarningSeverity.HIGH: 1,
            WarningSeverity.MEDIUM: 2,
            WarningSeverity.INFO: 3,
        }
        warnings.sort(key=lambda w: severity_order.get(w.severity, 4))

        return warnings

    def _check_regime_shift(self) -> List[Warning]:
        """Check for potential regime shift."""
        warnings = []

        try:
            regime_analysis = get_regime_analysis()

            # Check if price is near 50-day SMA (potential crossover)
            if regime_analysis.current_price > 0 and regime_analysis.sma_50 > 0:
                distance_pct = abs(regime_analysis.current_price - regime_analysis.sma_50) / regime_analysis.sma_50 * 100

                if distance_pct <= self.THRESHOLDS["regime_sma_proximity"]:
                    # Price is very close to 50-day SMA
                    direction = "above" if regime_analysis.above_50 else "below"
                    potential_shift = "SIDEWAYS" if regime_analysis.regime == MarketRegime.BULL else "BULL/SIDEWAYS"

                    warnings.append(Warning(
                        id="regime_shift_possible",
                        title="Regime Shift Possible",
                        description=f"Benchmark is {distance_pct:.1f}% {direction} 50-day SMA. Potential shift to {potential_shift}.",
                        severity=WarningSeverity.MEDIUM,
                        category="regime",
                        metric_name="sma_distance",
                        metric_value=distance_pct,
                        threshold=self.THRESHOLDS["regime_sma_proximity"],
                        action_suggestion="Monitor regime closely and consider adjusting positioning",
                    ))

            # Check if in bear market
            if regime_analysis.regime == MarketRegime.BEAR:
                warnings.append(Warning(
                    id="bear_market_active",
                    title="Bear Market Active",
                    description=f"Benchmark below both 50-day and 200-day SMAs. Defensive positioning recommended.",
                    severity=WarningSeverity.HIGH,
                    category="regime",
                    action_suggestion="Consider reducing exposure and tightening stops",
                ))

        except Exception as e:
            pass  # Silently skip if regime check fails

        return warnings

    def _check_drawdown(self, snapshots_df: pd.DataFrame) -> List[Warning]:
        """Check current drawdown levels."""
        warnings = []

        if snapshots_df.empty or "total_equity" not in snapshots_df.columns:
            return warnings

        peak = snapshots_df["total_equity"].max()
        current = snapshots_df["total_equity"].iloc[-1]

        if peak > 0:
            drawdown_pct = ((peak - current) / peak) * 100

            if drawdown_pct >= self.THRESHOLDS["drawdown_critical"]:
                warnings.append(Warning(
                    id="drawdown_critical",
                    title="Critical Drawdown",
                    description=f"Portfolio is {drawdown_pct:.1f}% below peak. Capital preservation mode recommended.",
                    severity=WarningSeverity.CRITICAL,
                    category="risk",
                    metric_name="drawdown",
                    metric_value=drawdown_pct,
                    threshold=self.THRESHOLDS["drawdown_critical"],
                    action_suggestion="Consider switching to Cash Mode or Defensive Mode",
                ))
            elif drawdown_pct >= self.THRESHOLDS["drawdown_warning"]:
                warnings.append(Warning(
                    id="drawdown_warning",
                    title="Elevated Drawdown",
                    description=f"Portfolio is {drawdown_pct:.1f}% below peak. Monitor closely.",
                    severity=WarningSeverity.MEDIUM,
                    category="risk",
                    metric_name="drawdown",
                    metric_value=drawdown_pct,
                    threshold=self.THRESHOLDS["drawdown_warning"],
                    action_suggestion="Review underperforming positions and consider tightening stops",
                ))

        return warnings

    def _check_losing_streak(self, transactions_df: pd.DataFrame) -> List[Warning]:
        """Check for consecutive losing trades."""
        warnings = []

        if transactions_df.empty:
            return warnings

        # Get recent sells
        sells = transactions_df[transactions_df["action"] == "SELL"].copy()
        if len(sells) < 2:
            return warnings

        sells = sells.sort_values("date", ascending=False)

        # Check for losing streak by looking at recent stop losses
        recent_sells = sells.head(10)
        stop_losses = recent_sells[recent_sells["reason"] == "STOP_LOSS"]

        consecutive_losses = 0
        for _, sell in recent_sells.iterrows():
            if sell.get("reason") == "STOP_LOSS":
                consecutive_losses += 1
            else:
                break  # End streak on non-stop-loss

        if consecutive_losses >= self.THRESHOLDS["losing_streak"]:
            warnings.append(Warning(
                id="losing_streak",
                title="Losing Streak Detected",
                description=f"{consecutive_losses} consecutive stop-loss exits. Strategy may need adjustment.",
                severity=WarningSeverity.HIGH,
                category="pattern",
                metric_name="consecutive_losses",
                metric_value=consecutive_losses,
                threshold=self.THRESHOLDS["losing_streak"],
                action_suggestion="Run PIVOT analysis to identify strategy issues",
            ))

        return warnings

    def _check_win_rate(self) -> List[Warning]:
        """Check if recent win rate is declining."""
        warnings = []

        try:
            stats = self.trade_analyzer.calculate_trade_stats()
            if stats and stats.total_trades >= 10:
                if stats.win_rate_pct < self.THRESHOLDS["win_rate_low"]:
                    warnings.append(Warning(
                        id="win_rate_low",
                        title="Low Win Rate",
                        description=f"Win rate at {stats.win_rate_pct:.1f}% (below {self.THRESHOLDS['win_rate_low']:.0f}% threshold).",
                        severity=WarningSeverity.HIGH,
                        category="performance",
                        metric_name="win_rate",
                        metric_value=stats.win_rate_pct,
                        threshold=self.THRESHOLDS["win_rate_low"],
                        action_suggestion="Review entry criteria and consider factor weight adjustments",
                    ))
        except Exception as e:
            print(f"Warning: performance check failed: {e}")

        return warnings

    def _check_concentration(self, positions_df: pd.DataFrame) -> List[Warning]:
        """Check for position concentration risk."""
        warnings = []

        if positions_df.empty or "market_value" not in positions_df.columns:
            return warnings

        total_value = positions_df["market_value"].sum()
        if total_value == 0:
            return warnings

        max_position = positions_df.loc[positions_df["market_value"].idxmax()]
        max_pct = (max_position["market_value"] / total_value) * 100
        max_ticker = max_position["ticker"]

        if max_pct >= self.THRESHOLDS["concentration_critical"]:
            warnings.append(Warning(
                id="concentration_critical",
                title="Critical Concentration",
                description=f"{max_ticker} is {max_pct:.1f}% of portfolio. Significant single-stock risk.",
                severity=WarningSeverity.CRITICAL,
                category="risk",
                metric_name="concentration",
                metric_value=max_pct,
                threshold=self.THRESHOLDS["concentration_critical"],
                action_suggestion=f"Consider trimming {max_ticker} to reduce concentration risk",
            ))
        elif max_pct >= self.THRESHOLDS["concentration_warning"]:
            warnings.append(Warning(
                id="concentration_warning",
                title="Elevated Concentration",
                description=f"{max_ticker} is {max_pct:.1f}% of portfolio.",
                severity=WarningSeverity.MEDIUM,
                category="risk",
                metric_name="concentration",
                metric_value=max_pct,
                threshold=self.THRESHOLDS["concentration_warning"],
                action_suggestion=f"Monitor {max_ticker} closely",
            ))

        return warnings

    def _check_position_count(self, positions_df: pd.DataFrame) -> List[Warning]:
        """Check for over-diversification."""
        warnings = []

        num_positions = len(positions_df) if not positions_df.empty else 0

        if num_positions >= self.THRESHOLDS["position_count_high"]:
            avg_position = positions_df["market_value"].mean() if not positions_df.empty else 0
            warnings.append(Warning(
                id="over_diversified",
                title="Over-Diversified",
                description=f"{num_positions} positions (avg ${avg_position:,.0f} each). Edge may be diluted.",
                severity=WarningSeverity.MEDIUM,
                category="pattern",
                metric_name="position_count",
                metric_value=num_positions,
                threshold=self.THRESHOLDS["position_count_high"],
                action_suggestion="Consider consolidating to fewer, higher-conviction positions",
            ))

        return warnings

    def _check_positions_near_stop(self, positions_df: pd.DataFrame) -> List[Warning]:
        """Check for multiple positions near stop loss."""
        warnings = []

        if positions_df.empty or "stop_loss" not in positions_df.columns or "current_price" not in positions_df.columns:
            return warnings

        # Calculate distance to stop
        positions_df = positions_df.copy()
        positions_df["stop_distance_pct"] = (
            (positions_df["current_price"] - positions_df["stop_loss"])
            / positions_df["current_price"] * 100
        )

        # Count positions within 3% of stop
        near_stop = positions_df[positions_df["stop_distance_pct"] <= 3]
        count_near = len(near_stop)

        if count_near >= 3:
            tickers = ", ".join(near_stop["ticker"].tolist()[:5])
            warnings.append(Warning(
                id="multiple_near_stop",
                title="Multiple Positions Near Stop",
                description=f"{count_near} positions within 3% of stop loss: {tickers}",
                severity=WarningSeverity.HIGH,
                category="risk",
                metric_name="near_stop_count",
                metric_value=count_near,
                action_suggestion="Prepare for potential stop executions",
            ))

        return warnings


def get_warnings(portfolio_id: str = None) -> List[Warning]:
    """Get all current early warnings."""
    system = EarlyWarningSystem(portfolio_id=portfolio_id)
    return system.check_all()


def get_warning_severity(portfolio_id: str = None) -> str:
    """
    Return a severity level based on active warnings.

    Levels:
        "NORMAL"  — no HIGH or CRITICAL warnings
        "CAUTION" — at least one HIGH warning (reduce position sizing 25%)
        "DANGER"  — at least one CRITICAL warning (reduce position sizing 50%)

    The highest severity wins: DANGER takes precedence over CAUTION.
    """
    try:
        warnings = get_warnings(portfolio_id=portfolio_id)
    except Exception as e:
        print(f"Warning: failed to get warnings: {e}")
        return "NORMAL"

    severities = {w.severity for w in warnings}

    if WarningSeverity.CRITICAL in severities:
        return "DANGER"
    if WarningSeverity.HIGH in severities:
        return "CAUTION"
    return "NORMAL"


def format_warnings(warnings: List[Warning]) -> str:
    """Format warnings for display."""
    if not warnings:
        return "No active warnings - portfolio is healthy"

    lines = []
    for w in warnings:
        severity_icon = {
            WarningSeverity.CRITICAL: "🔴",
            WarningSeverity.HIGH: "🟠",
            WarningSeverity.MEDIUM: "🟡",
            WarningSeverity.INFO: "🔵",
        }.get(w.severity, "⚪")

        lines.append(f"{severity_icon} [{w.severity.value.upper()}] {w.title}")
        lines.append(f"   {w.description}")
        if w.action_suggestion:
            lines.append(f"   → {w.action_suggestion}")
        lines.append("")

    return "\n".join(lines)


# ─── CLI for Testing ───
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("EARLY WARNING SYSTEM")
    print("=" * 60)

    warnings = get_warnings()

    if not warnings:
        print("\n✓ No active warnings - portfolio is healthy")
    else:
        print(f"\n{len(warnings)} warning(s) detected:\n")
        print(format_warnings(warnings))
