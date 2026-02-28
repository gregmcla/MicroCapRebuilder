#!/usr/bin/env python3
"""
Risk Scoreboard for Mommy Bot.

Provides portfolio-level risk assessment with:
- Overall risk score (0-100, higher = safer)
- Component breakdown (concentration, drawdown, exposure, volatility, stop proximity)
- Human-readable narratives
- Recommended actions
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
import json
import pandas as pd
import numpy as np

from market_regime import get_market_regime, MarketRegime
from portfolio_state import load_portfolio_state


# ─── Risk Levels ───
RISK_LEVELS = [
    (80, 100, "LOW", "green"),
    (60, 79, "MODERATE", "yellow"),
    (40, 59, "ELEVATED", "orange"),
    (20, 39, "HIGH", "red"),
    (0, 19, "CRITICAL", "darkred"),
]


@dataclass
class RiskComponent:
    """Individual risk component score."""
    name: str
    score: float  # 0-100 (100 = safest)
    weight: float
    value: float  # Raw value (e.g., 15% concentration)
    threshold_warning: float
    threshold_danger: float
    status: str  # OK, WARNING, DANGER
    narrative: str


@dataclass
class RiskScoreboard:
    """Portfolio-level risk assessment."""
    overall_score: float  # 0-100 (100 = safest)
    risk_level: str  # LOW/MODERATE/ELEVATED/HIGH/CRITICAL
    risk_color: str  # Color for display
    components: List[RiskComponent] = field(default_factory=list)
    narrative: str = ""
    recommended_actions: List[str] = field(default_factory=list)


class RiskScoreboardCalculator:
    """Calculate portfolio risk scoreboard."""

    # Component weights
    WEIGHTS = {
        "concentration": 0.25,
        "drawdown": 0.25,
        "exposure": 0.20,
        "volatility": 0.15,
        "stop_proximity": 0.15,
    }

    # Thresholds for each component
    THRESHOLDS = {
        "concentration": {"warning": 20.0, "danger": 35.0},  # % in single position
        "drawdown": {"warning": 8.0, "danger": 15.0},  # % from peak
        "exposure": {"warning": 85.0, "danger": 95.0},  # % invested
        "volatility": {"warning": 25.0, "danger": 40.0},  # annualized vol %
        "stop_proximity": {"warning": 3.0, "danger": 2.0},  # % from stop
    }

    # Optimal exposure by regime
    REGIME_OPTIMAL_EXPOSURE = {
        MarketRegime.BULL: 80.0,
        MarketRegime.SIDEWAYS: 60.0,
        MarketRegime.BEAR: 30.0,
    }

    def __init__(self, portfolio_id: str = None):
        self.state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)

    def calculate(self) -> RiskScoreboard:
        """Calculate full risk scoreboard."""
        positions_df = self.state.positions
        snapshots_df = self.state.snapshots
        regime = self.state.regime

        # Calculate each component
        components = []

        # 1. Concentration Risk
        concentration = self._calc_concentration(positions_df)
        components.append(concentration)

        # 2. Drawdown Risk
        drawdown = self._calc_drawdown(snapshots_df)
        components.append(drawdown)

        # 3. Exposure Risk
        exposure = self._calc_exposure(positions_df, snapshots_df, regime)
        components.append(exposure)

        # 4. Volatility Risk
        volatility = self._calc_volatility(snapshots_df)
        components.append(volatility)

        # 5. Stop Proximity Risk
        stop_proximity = self._calc_stop_proximity(positions_df)
        components.append(stop_proximity)

        # Calculate overall score
        overall_score = sum(c.score * c.weight for c in components)

        # Determine risk level
        risk_level, risk_color = self._get_risk_level(overall_score)

        # Generate narrative
        narrative = self._generate_narrative(components, regime)

        # Generate recommendations
        recommendations = self._generate_recommendations(components, regime)

        return RiskScoreboard(
            overall_score=round(overall_score, 1),
            risk_level=risk_level,
            risk_color=risk_color,
            components=components,
            narrative=narrative,
            recommended_actions=recommendations,
        )

    def _calc_concentration(self, positions_df: pd.DataFrame) -> RiskComponent:
        """Calculate concentration risk (largest position %)."""
        if positions_df.empty or "market_value" not in positions_df.columns:
            return RiskComponent(
                name="Concentration",
                score=100.0,
                weight=self.WEIGHTS["concentration"],
                value=0.0,
                threshold_warning=self.THRESHOLDS["concentration"]["warning"],
                threshold_danger=self.THRESHOLDS["concentration"]["danger"],
                status="OK",
                narrative="No positions - no concentration risk",
            )

        total_value = positions_df["market_value"].sum()
        if total_value == 0:
            max_pct = 0.0
        else:
            max_value = positions_df["market_value"].max()
            max_pct = (max_value / total_value) * 100
            largest_ticker = positions_df.loc[positions_df["market_value"].idxmax(), "ticker"]

        # Score: 0% concentration = 100, 40%+ = 0
        score = max(0, 100 - (max_pct * 2.5))

        # Status
        if max_pct >= self.THRESHOLDS["concentration"]["danger"]:
            status = "DANGER"
            narrative = f"High concentration: {largest_ticker} is {max_pct:.1f}% of portfolio"
        elif max_pct >= self.THRESHOLDS["concentration"]["warning"]:
            status = "WARNING"
            narrative = f"Elevated concentration: {largest_ticker} is {max_pct:.1f}% of portfolio"
        else:
            status = "OK"
            narrative = f"Concentration OK: largest position is {max_pct:.1f}%"

        return RiskComponent(
            name="Concentration",
            score=round(score, 1),
            weight=self.WEIGHTS["concentration"],
            value=round(max_pct, 1),
            threshold_warning=self.THRESHOLDS["concentration"]["warning"],
            threshold_danger=self.THRESHOLDS["concentration"]["danger"],
            status=status,
            narrative=narrative,
        )

    def _calc_drawdown(self, snapshots_df: pd.DataFrame) -> RiskComponent:
        """Calculate drawdown risk (current % from peak)."""
        if snapshots_df.empty or "total_equity" not in snapshots_df.columns:
            return RiskComponent(
                name="Drawdown",
                score=100.0,
                weight=self.WEIGHTS["drawdown"],
                value=0.0,
                threshold_warning=self.THRESHOLDS["drawdown"]["warning"],
                threshold_danger=self.THRESHOLDS["drawdown"]["danger"],
                status="OK",
                narrative="No history - no drawdown",
            )

        peak = snapshots_df["total_equity"].max()
        current = snapshots_df["total_equity"].iloc[-1]

        if peak == 0:
            drawdown_pct = 0.0
        else:
            drawdown_pct = ((peak - current) / peak) * 100

        # Score: 0% drawdown = 100, 20%+ = 0
        score = max(0, 100 - (drawdown_pct * 5))

        # Status
        if drawdown_pct >= self.THRESHOLDS["drawdown"]["danger"]:
            status = "DANGER"
            narrative = f"Significant drawdown: {drawdown_pct:.1f}% below peak (${peak:,.0f})"
        elif drawdown_pct >= self.THRESHOLDS["drawdown"]["warning"]:
            status = "WARNING"
            narrative = f"Moderate drawdown: {drawdown_pct:.1f}% below peak"
        else:
            status = "OK"
            narrative = f"Drawdown minimal: {drawdown_pct:.1f}% from peak"

        return RiskComponent(
            name="Drawdown",
            score=round(score, 1),
            weight=self.WEIGHTS["drawdown"],
            value=round(drawdown_pct, 1),
            threshold_warning=self.THRESHOLDS["drawdown"]["warning"],
            threshold_danger=self.THRESHOLDS["drawdown"]["danger"],
            status=status,
            narrative=narrative,
        )

    def _calc_exposure(self, positions_df: pd.DataFrame, snapshots_df: pd.DataFrame, regime: MarketRegime) -> RiskComponent:
        """Calculate exposure risk (% invested vs regime-appropriate level)."""
        if snapshots_df.empty or "total_equity" not in snapshots_df.columns:
            return RiskComponent(
                name="Exposure",
                score=100.0,
                weight=self.WEIGHTS["exposure"],
                value=0.0,
                threshold_warning=self.THRESHOLDS["exposure"]["warning"],
                threshold_danger=self.THRESHOLDS["exposure"]["danger"],
                status="OK",
                narrative="No data for exposure calculation",
            )

        total_equity = snapshots_df["total_equity"].iloc[-1]
        if positions_df.empty or "market_value" not in positions_df.columns:
            positions_value = 0.0
        else:
            positions_value = positions_df["market_value"].sum()

        if total_equity == 0:
            exposure_pct = 0.0
        else:
            exposure_pct = (positions_value / total_equity) * 100

        # Get optimal exposure for current regime
        optimal = self.REGIME_OPTIMAL_EXPOSURE.get(regime, 60.0)

        # Score based on deviation from optimal
        # Being over-exposed in bear market is worse than being under-exposed
        deviation = exposure_pct - optimal

        if deviation > 0:  # Over-exposed
            # Penalty increases with regime risk
            if regime == MarketRegime.BEAR:
                penalty_multiplier = 3.0
            elif regime == MarketRegime.SIDEWAYS:
                penalty_multiplier = 2.0
            else:
                penalty_multiplier = 1.0
            score = max(0, 100 - (deviation * penalty_multiplier))
        else:  # Under-exposed (less risky, but opportunity cost)
            score = max(0, 100 - (abs(deviation) * 0.5))

        # Status based on absolute exposure
        if exposure_pct >= self.THRESHOLDS["exposure"]["danger"]:
            status = "DANGER"
            narrative = f"Very high exposure: {exposure_pct:.0f}% invested (optimal for {regime.value}: {optimal:.0f}%)"
        elif exposure_pct >= self.THRESHOLDS["exposure"]["warning"]:
            status = "WARNING"
            narrative = f"High exposure: {exposure_pct:.0f}% invested (optimal for {regime.value}: {optimal:.0f}%)"
        else:
            status = "OK"
            narrative = f"Exposure OK: {exposure_pct:.0f}% invested (optimal for {regime.value}: {optimal:.0f}%)"

        return RiskComponent(
            name="Exposure",
            score=round(score, 1),
            weight=self.WEIGHTS["exposure"],
            value=round(exposure_pct, 1),
            threshold_warning=self.THRESHOLDS["exposure"]["warning"],
            threshold_danger=self.THRESHOLDS["exposure"]["danger"],
            status=status,
            narrative=narrative,
        )

    def _calc_volatility(self, snapshots_df: pd.DataFrame) -> RiskComponent:
        """Calculate portfolio volatility risk."""
        if len(snapshots_df) < 5 or "total_equity" not in snapshots_df.columns:
            return RiskComponent(
                name="Volatility",
                score=75.0,  # Assume moderate if unknown
                weight=self.WEIGHTS["volatility"],
                value=0.0,
                threshold_warning=self.THRESHOLDS["volatility"]["warning"],
                threshold_danger=self.THRESHOLDS["volatility"]["danger"],
                status="OK",
                narrative="Insufficient data for volatility calculation",
            )

        # Calculate daily returns
        equity = snapshots_df["total_equity"]
        returns = equity.pct_change().dropna()

        if len(returns) < 2:
            return RiskComponent(
                name="Volatility",
                score=75.0,
                weight=self.WEIGHTS["volatility"],
                value=0.0,
                threshold_warning=self.THRESHOLDS["volatility"]["warning"],
                threshold_danger=self.THRESHOLDS["volatility"]["danger"],
                status="OK",
                narrative="Insufficient data for volatility calculation",
            )

        # Annualized volatility
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252) * 100

        # Score: 0% vol = 100, 50%+ = 0
        score = max(0, 100 - (annual_vol * 2))

        # Status
        if annual_vol >= self.THRESHOLDS["volatility"]["danger"]:
            status = "DANGER"
            narrative = f"High portfolio volatility: {annual_vol:.1f}% annualized"
        elif annual_vol >= self.THRESHOLDS["volatility"]["warning"]:
            status = "WARNING"
            narrative = f"Elevated volatility: {annual_vol:.1f}% annualized"
        else:
            status = "OK"
            narrative = f"Volatility acceptable: {annual_vol:.1f}% annualized"

        return RiskComponent(
            name="Volatility",
            score=round(score, 1),
            weight=self.WEIGHTS["volatility"],
            value=round(annual_vol, 1),
            threshold_warning=self.THRESHOLDS["volatility"]["warning"],
            threshold_danger=self.THRESHOLDS["volatility"]["danger"],
            status=status,
            narrative=narrative,
        )

    def _calc_stop_proximity(self, positions_df: pd.DataFrame) -> RiskComponent:
        """Calculate how many positions are near their stop loss."""
        if positions_df.empty or "stop_loss" not in positions_df.columns:
            return RiskComponent(
                name="Stop Proximity",
                score=100.0,
                weight=self.WEIGHTS["stop_proximity"],
                value=0.0,
                threshold_warning=self.THRESHOLDS["stop_proximity"]["warning"],
                threshold_danger=self.THRESHOLDS["stop_proximity"]["danger"],
                status="OK",
                narrative="No positions with stop losses",
            )

        # Calculate distance to stop for each position
        positions_df = positions_df.copy()
        positions_df["stop_distance_pct"] = (
            (positions_df["current_price"] - positions_df["stop_loss"])
            / positions_df["current_price"] * 100
        )

        # Count positions near stop
        near_stop = (positions_df["stop_distance_pct"] <= self.THRESHOLDS["stop_proximity"]["warning"]).sum()
        very_near_stop = (positions_df["stop_distance_pct"] <= self.THRESHOLDS["stop_proximity"]["danger"]).sum()
        total_positions = len(positions_df)

        if total_positions == 0:
            pct_near_stop = 0.0
        else:
            pct_near_stop = (near_stop / total_positions) * 100

        # Score: 0 positions near stop = 100, all positions near stop = 0
        score = max(0, 100 - (pct_near_stop * 1.5))

        # Status
        if very_near_stop > 0:
            tickers = positions_df[positions_df["stop_distance_pct"] <= self.THRESHOLDS["stop_proximity"]["danger"]]["ticker"].tolist()
            status = "DANGER"
            narrative = f"{very_near_stop} position(s) very close to stop: {', '.join(tickers)}"
        elif near_stop > 0:
            status = "WARNING"
            narrative = f"{near_stop} position(s) within {self.THRESHOLDS['stop_proximity']['warning']}% of stop loss"
        else:
            status = "OK"
            narrative = "All positions have comfortable distance from stops"

        return RiskComponent(
            name="Stop Proximity",
            score=round(score, 1),
            weight=self.WEIGHTS["stop_proximity"],
            value=round(pct_near_stop, 1),
            threshold_warning=self.THRESHOLDS["stop_proximity"]["warning"],
            threshold_danger=self.THRESHOLDS["stop_proximity"]["danger"],
            status=status,
            narrative=narrative,
        )

    def _get_risk_level(self, score: float) -> tuple:
        """Get risk level and color from score."""
        for low, high, level, color in RISK_LEVELS:
            if low <= score <= high:
                return level, color
        return "CRITICAL", "darkred"

    def _generate_narrative(self, components: List[RiskComponent], regime: MarketRegime) -> str:
        """Generate overall risk narrative."""
        # Find worst components
        danger_components = [c for c in components if c.status == "DANGER"]
        warning_components = [c for c in components if c.status == "WARNING"]

        if danger_components:
            worst = danger_components[0]
            return f"Portfolio risk elevated due to {worst.name.lower()}. {worst.narrative}"
        elif warning_components:
            worst = warning_components[0]
            return f"Minor concerns with {worst.name.lower()}. {worst.narrative}"
        else:
            return f"Portfolio risk well-managed for current {regime.value} market conditions."

    def _generate_recommendations(self, components: List[RiskComponent], regime: MarketRegime) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        for component in components:
            if component.status == "DANGER":
                if component.name == "Concentration":
                    recommendations.append("Consider trimming largest position to reduce concentration risk")
                elif component.name == "Drawdown":
                    recommendations.append("Review all positions for potential exits to stop the bleeding")
                elif component.name == "Exposure":
                    recommendations.append(f"Reduce exposure to match {regime.value} market conditions")
                elif component.name == "Volatility":
                    recommendations.append("Consider rotating into lower-volatility positions")
                elif component.name == "Stop Proximity":
                    recommendations.append("Prepare for potential stop-loss executions")
            elif component.status == "WARNING":
                if component.name == "Concentration":
                    recommendations.append("Monitor largest position for potential trimming")
                elif component.name == "Drawdown":
                    recommendations.append("Tighten stops on underperforming positions")
                elif component.name == "Exposure":
                    recommendations.append("Consider holding more cash given market conditions")

        if not recommendations:
            recommendations.append("Portfolio risk is well-managed - maintain current strategy")

        return recommendations


def get_risk_scoreboard(portfolio_id: str = None) -> RiskScoreboard:
    """Get current risk scoreboard."""
    calculator = RiskScoreboardCalculator(portfolio_id=portfolio_id)
    return calculator.calculate()


# ─── CLI for Testing ───
if __name__ == "__main__":
    print("\n─── Risk Scoreboard ───\n")

    scoreboard = get_risk_scoreboard()

    print(f"Overall Risk Score: {scoreboard.overall_score}/100 ({scoreboard.risk_level})")
    print()

    print("Components:")
    for c in scoreboard.components:
        status_icon = "✓" if c.status == "OK" else ("⚠" if c.status == "WARNING" else "✗")
        print(f"  {status_icon} {c.name}: {c.score:.0f}/100 (value: {c.value:.1f})")

    print()
    print(f"Narrative: {scoreboard.narrative}")

    print()
    print("Recommendations:")
    for rec in scoreboard.recommended_actions:
        print(f"  - {rec}")
