#!/usr/bin/env python3
"""
Strategy Health Dashboard for Mommy Bot.

Provides a holistic "health check" that grades the current strategy A-F
across 5 components:
- Performance (30%): Returns vs benchmark, Sharpe ratio
- Risk Control (25%): Drawdown, stop adherence, position sizing
- Trading Edge (20%): Win rate, profit factor, expectancy
- Factor Alignment (15%): Are factor weights working for this regime?
- Market Fit (10%): Is strategy suited to current regime?

Usage:
    from strategy_health import get_strategy_health, StrategyHealth
    health = get_strategy_health()
    print(f"Grade: {health.grade} ({health.score}/100)")
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json
import pandas as pd
import numpy as np

from analytics import PortfolioAnalytics, RiskMetrics
from trade_analyzer import TradeAnalyzer, TradeStats
from market_regime import get_market_regime, get_regime_analysis, MarketRegime
from risk_scoreboard import get_risk_scoreboard, RiskScoreboard
from portfolio_state import load_portfolio_state


# ─── Grade Thresholds ───
GRADES = [
    (90, 100, "A", "Strategy crushing it - stay the course"),
    (80, 89, "A-", "Excellent performance - minor tweaks possible"),
    (75, 79, "B+", "Performing well - continue monitoring"),
    (70, 74, "B", "Good performance with room for improvement"),
    (65, 69, "B-", "Acceptable but could be stronger"),
    (60, 64, "C+", "Underperforming - review factors"),
    (55, 59, "C", "Below expectations - consider adjustments"),
    (50, 54, "C-", "Struggling - parameter changes recommended"),
    (40, 49, "D", "Significant issues - PIVOT recommended"),
    (0, 39, "F", "Strategy broken for current conditions - PIVOT needed"),
]


@dataclass
class HealthComponent:
    """Individual health component score."""
    name: str
    score: float  # 0-100
    weight: float
    grade: str
    details: Dict[str, any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)


@dataclass
class StrategyHealth:
    """Overall strategy health assessment."""
    score: float  # 0-100
    grade: str  # A, B+, C-, etc.
    grade_description: str
    components: List[HealthComponent] = field(default_factory=list)
    diagnosis: str = ""
    what_working: List[str] = field(default_factory=list)
    what_struggling: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    pivot_recommended: bool = False
    pivot_urgency: str = "none"  # none, low, medium, high, critical


class StrategyHealthCalculator:
    """Calculate comprehensive strategy health."""

    # Component weights
    WEIGHTS = {
        "performance": 0.30,
        "risk_control": 0.25,
        "trading_edge": 0.20,
        "factor_alignment": 0.15,
        "market_fit": 0.10,
    }

    def __init__(self):
        # Load config on-demand from portfolio state
        state = load_portfolio_state(fetch_prices=False)
        self.config = state.config
        self.analytics = PortfolioAnalytics()
        self.trade_analyzer = TradeAnalyzer()

    def calculate(self) -> StrategyHealth:
        """Calculate full strategy health."""
        # Gather data
        risk_metrics = self.analytics.calculate_all_metrics()
        trade_stats = self.trade_analyzer.calculate_trade_stats()
        regime_analysis = get_regime_analysis()
        risk_scoreboard = get_risk_scoreboard()
        positions_df = self._load_positions()

        # Calculate each component
        components = []

        # 1. Performance Component (30%)
        performance = self._calc_performance(risk_metrics)
        components.append(performance)

        # 2. Risk Control Component (25%)
        risk_control = self._calc_risk_control(risk_scoreboard, risk_metrics)
        components.append(risk_control)

        # 3. Trading Edge Component (20%)
        trading_edge = self._calc_trading_edge(trade_stats)
        components.append(trading_edge)

        # 4. Factor Alignment Component (15%)
        factor_alignment = self._calc_factor_alignment(trade_stats, regime_analysis.regime)
        components.append(factor_alignment)

        # 5. Market Fit Component (10%)
        market_fit = self._calc_market_fit(risk_metrics, regime_analysis, positions_df)
        components.append(market_fit)

        # Calculate overall score
        overall_score = sum(c.score * c.weight for c in components)

        # Determine grade
        grade, description = self._get_grade(overall_score)

        # Collect strengths and issues
        what_working = []
        what_struggling = []
        for c in components:
            what_working.extend(c.strengths)
            what_struggling.extend(c.issues)

        # Generate diagnosis
        diagnosis = self._generate_diagnosis(components, regime_analysis.regime, overall_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(components, regime_analysis.regime)

        # Determine pivot urgency
        pivot_recommended, pivot_urgency = self._assess_pivot_need(overall_score, components)

        return StrategyHealth(
            score=round(overall_score, 1),
            grade=grade,
            grade_description=description,
            components=components,
            diagnosis=diagnosis,
            what_working=what_working[:5],  # Top 5 strengths
            what_struggling=what_struggling[:5],  # Top 5 issues
            recommendations=recommendations,
            pivot_recommended=pivot_recommended,
            pivot_urgency=pivot_urgency,
        )

    def _load_positions(self) -> pd.DataFrame:
        """Load current positions."""
        state = load_portfolio_state(fetch_prices=False)
        return state.positions

    def _calc_performance(self, metrics: Optional[RiskMetrics]) -> HealthComponent:
        """Calculate performance health (returns, Sharpe, alpha)."""
        if metrics is None:
            return HealthComponent(
                name="Performance",
                score=50.0,
                weight=self.WEIGHTS["performance"],
                grade="C",
                details={"reason": "Insufficient data"},
                issues=["Not enough trading history to assess performance"],
            )

        score = 50.0  # Base score
        details = {}
        issues = []
        strengths = []

        # Total return contribution (up to 30 points)
        total_return = metrics.total_return_pct
        details["total_return"] = total_return
        if total_return > 20:
            score += 30
            strengths.append(f"Strong total return: {total_return:+.1f}%")
        elif total_return > 10:
            score += 20
            strengths.append(f"Good total return: {total_return:+.1f}%")
        elif total_return > 0:
            score += 10
        elif total_return > -5:
            score -= 10
            issues.append(f"Slightly negative return: {total_return:+.1f}%")
        else:
            score -= 25
            issues.append(f"Poor return: {total_return:+.1f}%")

        # Sharpe ratio contribution (up to 25 points)
        sharpe = metrics.sharpe_ratio
        details["sharpe"] = sharpe
        if sharpe > 1.5:
            score += 25
            strengths.append(f"Excellent risk-adjusted returns (Sharpe: {sharpe:.2f})")
        elif sharpe > 1.0:
            score += 15
            strengths.append(f"Good Sharpe ratio: {sharpe:.2f}")
        elif sharpe > 0.5:
            score += 5
        elif sharpe > 0:
            pass  # Neutral
        else:
            score -= 15
            issues.append(f"Negative Sharpe ratio: {sharpe:.2f}")

        # Alpha contribution (up to 15 points)
        alpha = metrics.alpha_pct
        details["alpha"] = alpha
        if alpha > 5:
            score += 15
            strengths.append(f"Generating alpha: {alpha:+.1f}% vs benchmark")
        elif alpha > 0:
            score += 5
        elif alpha < -5:
            score -= 10
            issues.append(f"Negative alpha: {alpha:+.1f}% vs benchmark")

        score = max(0, min(100, score))
        grade, _ = self._get_grade(score)

        return HealthComponent(
            name="Performance",
            score=round(score, 1),
            weight=self.WEIGHTS["performance"],
            grade=grade,
            details=details,
            issues=issues,
            strengths=strengths,
        )

    def _calc_risk_control(self, risk_scoreboard: RiskScoreboard, metrics: Optional[RiskMetrics]) -> HealthComponent:
        """Calculate risk control health."""
        # Use existing risk scoreboard as base
        score = risk_scoreboard.overall_score
        details = {
            "risk_level": risk_scoreboard.risk_level,
            "components": {c.name: c.score for c in risk_scoreboard.components},
        }
        issues = []
        strengths = []

        # Analyze risk components
        for c in risk_scoreboard.components:
            if c.status == "DANGER":
                issues.append(f"{c.name}: {c.narrative}")
            elif c.status == "OK" and c.score >= 80:
                strengths.append(f"{c.name} well-managed ({c.score:.0f}/100)")

        # Check drawdown specifically
        if metrics and metrics.max_drawdown_pct < -15:
            issues.append(f"Significant max drawdown: {metrics.max_drawdown_pct:.1f}%")
            score -= 10

        score = max(0, min(100, score))
        grade, _ = self._get_grade(score)

        return HealthComponent(
            name="Risk Control",
            score=round(score, 1),
            weight=self.WEIGHTS["risk_control"],
            grade=grade,
            details=details,
            issues=issues,
            strengths=strengths,
        )

    def _calc_trading_edge(self, stats: Optional[TradeStats]) -> HealthComponent:
        """Calculate trading edge health (win rate, profit factor, expectancy)."""
        if stats is None or stats.total_trades == 0:
            return HealthComponent(
                name="Trading Edge",
                score=50.0,
                weight=self.WEIGHTS["trading_edge"],
                grade="C",
                details={"reason": "No completed trades"},
                issues=["No completed trades to analyze edge"],
            )

        score = 50.0  # Base score
        details = {}
        issues = []
        strengths = []

        # Win rate contribution (up to 25 points)
        win_rate = stats.win_rate_pct
        details["win_rate"] = win_rate
        if win_rate >= 60:
            score += 25
            strengths.append(f"Strong win rate: {win_rate:.1f}%")
        elif win_rate >= 50:
            score += 15
            strengths.append(f"Positive win rate: {win_rate:.1f}%")
        elif win_rate >= 40:
            score += 5
        else:
            score -= 15
            issues.append(f"Low win rate: {win_rate:.1f}%")

        # Profit factor contribution (up to 25 points)
        profit_factor = stats.profit_factor
        details["profit_factor"] = profit_factor
        if profit_factor >= 2.0:
            score += 25
            strengths.append(f"Excellent profit factor: {profit_factor:.2f}x")
        elif profit_factor >= 1.5:
            score += 15
            strengths.append(f"Good profit factor: {profit_factor:.2f}x")
        elif profit_factor >= 1.0:
            score += 5
        else:
            score -= 20
            issues.append(f"Losing money: profit factor {profit_factor:.2f}x")

        # Average trade (expectancy)
        avg_trade = stats.avg_trade_pct
        details["avg_trade"] = avg_trade
        if avg_trade > 5:
            score += 10
            strengths.append(f"High average trade: {avg_trade:+.1f}%")
        elif avg_trade > 0:
            score += 5
        elif avg_trade < -2:
            score -= 10
            issues.append(f"Negative average trade: {avg_trade:+.1f}%")

        # Position count analysis (check for over-diversification)
        open_positions = stats.open_positions
        details["open_positions"] = open_positions
        if open_positions > 30:
            score -= 15
            issues.append(f"Over-diversified: {open_positions} positions may dilute edge")
        elif open_positions > 20:
            score -= 5
            issues.append(f"Many positions ({open_positions}) - consider consolidating")

        score = max(0, min(100, score))
        grade, _ = self._get_grade(score)

        return HealthComponent(
            name="Trading Edge",
            score=round(score, 1),
            weight=self.WEIGHTS["trading_edge"],
            grade=grade,
            details=details,
            issues=issues,
            strengths=strengths,
        )

    def _calc_factor_alignment(self, stats: Optional[TradeStats], regime: MarketRegime) -> HealthComponent:
        """Calculate factor alignment health - are our factors working?"""
        # This requires factor-level performance data which we may not have
        # For now, use trade stats as a proxy and regime-appropriate behavior

        score = 60.0  # Base score
        details = {"regime": regime.value}
        issues = []
        strengths = []

        config = self.config
        scoring_config = config.get("scoring", {})

        # Check if we have regime-specific weights configured
        regime_weights = scoring_config.get("regime_weights", {})
        if regime.value in regime_weights:
            strengths.append(f"Using regime-specific weights for {regime.value}")
            score += 10
        else:
            issues.append("Not using regime-specific factor weights")

        # Check learning config
        learning = config.get("learning", {})
        if learning.get("enabled", False):
            strengths.append("Adaptive learning enabled")
            score += 10

        # If we have trade stats, check win rate trend
        if stats and stats.total_trades >= 10:
            if stats.win_rate_pct >= 50:
                strengths.append(f"Factors producing {stats.win_rate_pct:.0f}% win rate")
                score += 15
            elif stats.win_rate_pct < 40:
                issues.append(f"Factor selection producing low {stats.win_rate_pct:.0f}% win rate")
                score -= 15

        score = max(0, min(100, score))
        grade, _ = self._get_grade(score)

        return HealthComponent(
            name="Factor Alignment",
            score=round(score, 1),
            weight=self.WEIGHTS["factor_alignment"],
            grade=grade,
            details=details,
            issues=issues,
            strengths=strengths,
        )

    def _calc_market_fit(self, metrics: Optional[RiskMetrics], regime_analysis, positions_df: pd.DataFrame) -> HealthComponent:
        """Calculate market fit - is strategy suited to current conditions?"""
        regime = regime_analysis.regime

        score = 60.0  # Base score
        details = {
            "regime": regime.value,
            "regime_strength": regime_analysis.regime_strength,
        }
        issues = []
        strengths = []

        # Check regime appropriateness
        num_positions = len(positions_df) if not positions_df.empty else 0
        details["num_positions"] = num_positions

        if regime == MarketRegime.BULL:
            # In bull market, being invested is good
            if num_positions >= 5:
                strengths.append(f"Well-positioned for BULL market ({num_positions} positions)")
                score += 20
            elif num_positions < 3:
                issues.append(f"Under-invested for BULL market (only {num_positions} positions)")
                score -= 10

        elif regime == MarketRegime.BEAR:
            # In bear market, cash is king
            if num_positions > 15:
                issues.append(f"Over-exposed for BEAR market ({num_positions} positions)")
                score -= 25
            elif num_positions <= 5:
                strengths.append(f"Defensive positioning for BEAR market ({num_positions} positions)")
                score += 15

        elif regime == MarketRegime.SIDEWAYS:
            # Sideways = moderate exposure
            if num_positions > 25:
                issues.append(f"Many positions ({num_positions}) in SIDEWAYS market - consider consolidating")
                score -= 10
            elif 5 <= num_positions <= 15:
                strengths.append("Moderate positioning appropriate for SIDEWAYS market")
                score += 10

        # Check if we're outperforming or underperforming benchmark
        if metrics:
            alpha = metrics.alpha_pct
            details["alpha"] = alpha
            if alpha > 5:
                strengths.append(f"Outperforming benchmark by {alpha:.1f}%")
                score += 15
            elif alpha < -5:
                issues.append(f"Underperforming benchmark by {abs(alpha):.1f}%")
                score -= 15

        score = max(0, min(100, score))
        grade, _ = self._get_grade(score)

        return HealthComponent(
            name="Market Fit",
            score=round(score, 1),
            weight=self.WEIGHTS["market_fit"],
            grade=grade,
            details=details,
            issues=issues,
            strengths=strengths,
        )

    def _get_grade(self, score: float) -> Tuple[str, str]:
        """Get letter grade and description from score."""
        for low, high, grade, description in GRADES:
            if low <= score <= high:
                return grade, description
        return "F", "Strategy needs immediate attention"

    def _generate_diagnosis(self, components: List[HealthComponent], regime: MarketRegime, score: float) -> str:
        """Generate human-readable diagnosis."""
        grade, _ = self._get_grade(score)

        # Find weakest and strongest components
        sorted_components = sorted(components, key=lambda c: c.score)
        weakest = sorted_components[0]
        strongest = sorted_components[-1]

        if score >= 80:
            return f"Strategy performing well in {regime.value} market. {strongest.name} is particularly strong ({strongest.score:.0f}/100)."
        elif score >= 60:
            return f"Strategy acceptable but {weakest.name} needs attention ({weakest.score:.0f}/100). Consider reviewing {weakest.name.lower()} factors."
        elif score >= 40:
            return f"Strategy struggling, particularly with {weakest.name} ({weakest.score:.0f}/100). A pivot may be needed to adapt to {regime.value} conditions."
        else:
            return f"Strategy is not working in current {regime.value} market. Immediate pivot recommended. Major issue: {weakest.name} at {weakest.score:.0f}/100."

    def _generate_recommendations(self, components: List[HealthComponent], regime: MarketRegime) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        for c in sorted(components, key=lambda x: x.score):
            if c.score < 50:
                if c.name == "Performance":
                    recommendations.append("Review position selection criteria - focus on higher-probability setups")
                elif c.name == "Risk Control":
                    recommendations.append("Tighten risk parameters - consider reducing position sizes or tightening stops")
                elif c.name == "Trading Edge":
                    if c.details.get("open_positions", 0) > 20:
                        recommendations.append("Consolidate positions - too many small positions dilutes edge")
                    else:
                        recommendations.append("Review entry criteria - win rate needs improvement")
                elif c.name == "Factor Alignment":
                    recommendations.append(f"Adjust factor weights for {regime.value} market conditions")
                elif c.name == "Market Fit":
                    if regime == MarketRegime.BEAR:
                        recommendations.append("Reduce exposure significantly - BEAR market requires defensive positioning")
                    else:
                        recommendations.append("Adjust positioning to match current market regime")
            elif c.score < 70:
                # Minor recommendations for components needing attention
                if c.issues:
                    recommendations.append(f"Monitor {c.name.lower()}: {c.issues[0]}")

        if not recommendations:
            recommendations.append("Maintain current strategy - all components healthy")

        return recommendations[:5]  # Top 5 recommendations

    def _assess_pivot_need(self, score: float, components: List[HealthComponent]) -> Tuple[bool, str]:
        """Assess if a strategy pivot is recommended."""
        if score < 40:
            return True, "critical"
        elif score < 50:
            return True, "high"
        elif score < 60:
            # Check if multiple components are struggling
            struggling = sum(1 for c in components if c.score < 50)
            if struggling >= 2:
                return True, "medium"
            return False, "low"
        else:
            return False, "none"


def get_strategy_health() -> StrategyHealth:
    """Get current strategy health assessment."""
    calculator = StrategyHealthCalculator()
    return calculator.calculate()


# ─── CLI for Testing ───
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("STRATEGY HEALTH DASHBOARD")
    print("=" * 60)

    health = get_strategy_health()

    # Grade display
    grade_color = {
        "A": "green", "A-": "green",
        "B+": "blue", "B": "blue", "B-": "blue",
        "C+": "yellow", "C": "yellow", "C-": "yellow",
        "D": "red", "F": "red"
    }

    print(f"\nOverall Grade: {health.grade} ({health.score}/100)")
    print(f"Assessment: {health.grade_description}")
    print()

    # Components
    print("Component Breakdown:")
    print("-" * 40)
    for c in health.components:
        bar_len = int(c.score / 5)  # 20 char max
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  {c.name:18} {c.grade:3} {bar} {c.score:.0f}")

    print()
    print("Diagnosis:")
    print(f"  {health.diagnosis}")

    if health.what_working:
        print()
        print("What's Working:")
        for item in health.what_working:
            print(f"  ✓ {item}")

    if health.what_struggling:
        print()
        print("What's Struggling:")
        for item in health.what_struggling:
            print(f"  ✗ {item}")

    print()
    print("Recommendations:")
    for rec in health.recommendations:
        print(f"  → {rec}")

    if health.pivot_recommended:
        print()
        print(f"⚠️  PIVOT RECOMMENDED (urgency: {health.pivot_urgency.upper()})")
