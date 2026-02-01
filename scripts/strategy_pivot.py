#!/usr/bin/env python3
"""
Strategy Pivot Analyzer for Mommy Bot.

The PIVOT button performs deep holistic analysis and suggests alternative
strategies when the current approach isn't working.

Features:
- Diagnoses current state (what's working, what's failing)
- Generates alternative strategy recommendations
- Projects outcomes with tradeoffs
- Provides one-click pivot configurations

Usage:
    from strategy_pivot import analyze_pivot, PivotAnalysis
    pivot = analyze_pivot()
    if pivot.should_pivot:
        print(f"Recommended: {pivot.recommended_pivot.name}")
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from enum import Enum
import json
import pandas as pd
import numpy as np

from strategy_health import get_strategy_health, StrategyHealth
from analytics import PortfolioAnalytics
from trade_analyzer import TradeAnalyzer
from market_regime import get_market_regime, get_regime_analysis, MarketRegime
from risk_scoreboard import get_risk_scoreboard
from data_files import (
    get_positions_file, get_transactions_file, get_daily_snapshots_file,
    load_config as load_base_config, CONFIG_FILE
)


def load_config() -> dict:
    """Load configuration from config.json."""
    return load_base_config()


def save_config(config: dict):
    """Save configuration to config.json."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


class PivotType(Enum):
    """Types of strategy pivots."""
    CONSOLIDATE = "consolidate"  # Fewer, larger positions
    DEFENSIVE = "defensive"  # Reduce risk, tighten stops
    AGGRESSIVE = "aggressive"  # Lean into momentum
    CASH_MODE = "cash_mode"  # Significant exposure reduction
    REGIME_ADAPT = "regime_adapt"  # Adapt to current regime
    FACTOR_REBALANCE = "factor_rebalance"  # Adjust factor weights


@dataclass
class PivotRecommendation:
    """A specific pivot recommendation with config changes."""
    name: str
    pivot_type: PivotType
    description: str
    rationale: str
    config_changes: Dict[str, any] = field(default_factory=dict)
    projected_impact: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0  # 0-1
    risk_change: str = "neutral"  # reduced, neutral, increased
    priority: int = 1  # 1 = highest priority


@dataclass
class DiagnosisItem:
    """Individual diagnosis item (working or failing)."""
    category: str
    description: str
    severity: str  # info, warning, critical
    metric_value: Optional[float] = None
    metric_name: Optional[str] = None


@dataclass
class PivotAnalysis:
    """Complete pivot analysis result."""
    health: StrategyHealth
    should_pivot: bool
    urgency: str  # none, low, medium, high, critical
    diagnosis_working: List[DiagnosisItem] = field(default_factory=list)
    diagnosis_failing: List[DiagnosisItem] = field(default_factory=list)
    pivots: List[PivotRecommendation] = field(default_factory=list)
    recommended_pivot: Optional[PivotRecommendation] = None
    mommy_says: str = ""  # Personalized narrative from Mommy


class StrategyPivotAnalyzer:
    """Analyze strategy and generate pivot recommendations."""

    def __init__(self):
        self.config = load_config()
        self.analytics = PortfolioAnalytics()
        self.trade_analyzer = TradeAnalyzer()

    def analyze(self) -> PivotAnalysis:
        """Perform complete pivot analysis."""
        # Get current health
        health = get_strategy_health()
        regime_analysis = get_regime_analysis()
        regime = regime_analysis.regime
        trade_stats = self.trade_analyzer.calculate_trade_stats()
        risk_scoreboard = get_risk_scoreboard()
        positions_df = self._load_positions()

        # Diagnose what's working and failing
        working, failing = self._diagnose(health, trade_stats, risk_scoreboard, positions_df, regime)

        # Generate pivot recommendations
        pivots = self._generate_pivots(health, failing, regime, positions_df, trade_stats)

        # Determine if pivot is needed
        should_pivot = health.pivot_recommended
        urgency = health.pivot_urgency

        # Select recommended pivot (highest priority)
        recommended = pivots[0] if pivots else None

        # Generate Mommy's narrative
        mommy_says = self._generate_mommy_narrative(health, working, failing, recommended, regime)

        return PivotAnalysis(
            health=health,
            should_pivot=should_pivot,
            urgency=urgency,
            diagnosis_working=working,
            diagnosis_failing=failing,
            pivots=pivots,
            recommended_pivot=recommended,
            mommy_says=mommy_says,
        )

    def _load_positions(self) -> pd.DataFrame:
        """Load current positions."""
        positions_file = get_positions_file()
        if not positions_file.exists():
            return pd.DataFrame()
        return pd.read_csv(positions_file)

    def _diagnose(self, health: StrategyHealth, trade_stats, risk_scoreboard, positions_df, regime) -> Tuple[List[DiagnosisItem], List[DiagnosisItem]]:
        """Diagnose what's working and what's failing."""
        working = []
        failing = []

        # Check position count
        num_positions = len(positions_df) if not positions_df.empty else 0
        if num_positions > 30:
            failing.append(DiagnosisItem(
                category="Portfolio Structure",
                description=f"Over-diversified: {num_positions} positions dilutes edge",
                severity="warning",
                metric_value=num_positions,
                metric_name="positions",
            ))
        elif 5 <= num_positions <= 20:
            working.append(DiagnosisItem(
                category="Portfolio Structure",
                description=f"Reasonable position count: {num_positions}",
                severity="info",
                metric_value=num_positions,
                metric_name="positions",
            ))

        # Check average position size
        if not positions_df.empty and "market_value" in positions_df.columns:
            total_value = positions_df["market_value"].sum()
            avg_position = total_value / num_positions if num_positions > 0 else 0
            if avg_position < 1000 and num_positions > 10:
                failing.append(DiagnosisItem(
                    category="Position Sizing",
                    description=f"Positions too small: avg ${avg_position:.0f}",
                    severity="warning",
                    metric_value=avg_position,
                    metric_name="avg_position",
                ))

        # Check trade stats
        if trade_stats and trade_stats.total_trades > 0:
            # Win rate
            if trade_stats.win_rate_pct >= 55:
                working.append(DiagnosisItem(
                    category="Trading Edge",
                    description=f"Strong win rate: {trade_stats.win_rate_pct:.1f}%",
                    severity="info",
                    metric_value=trade_stats.win_rate_pct,
                    metric_name="win_rate",
                ))
            elif trade_stats.win_rate_pct < 40:
                failing.append(DiagnosisItem(
                    category="Trading Edge",
                    description=f"Low win rate: {trade_stats.win_rate_pct:.1f}%",
                    severity="critical",
                    metric_value=trade_stats.win_rate_pct,
                    metric_name="win_rate",
                ))

            # Profit factor
            if trade_stats.profit_factor >= 1.5:
                working.append(DiagnosisItem(
                    category="Trading Edge",
                    description=f"Good profit factor: {trade_stats.profit_factor:.2f}x",
                    severity="info",
                    metric_value=trade_stats.profit_factor,
                    metric_name="profit_factor",
                ))
            elif trade_stats.profit_factor < 1.0:
                failing.append(DiagnosisItem(
                    category="Trading Edge",
                    description=f"Losing money: profit factor {trade_stats.profit_factor:.2f}x",
                    severity="critical",
                    metric_value=trade_stats.profit_factor,
                    metric_name="profit_factor",
                ))

        # Check risk components
        for component in risk_scoreboard.components:
            if component.status == "OK" and component.score >= 75:
                working.append(DiagnosisItem(
                    category="Risk Management",
                    description=f"{component.name}: {component.narrative}",
                    severity="info",
                    metric_value=component.score,
                    metric_name=component.name.lower(),
                ))
            elif component.status == "DANGER":
                failing.append(DiagnosisItem(
                    category="Risk Management",
                    description=f"{component.name}: {component.narrative}",
                    severity="critical",
                    metric_value=component.score,
                    metric_name=component.name.lower(),
                ))
            elif component.status == "WARNING":
                failing.append(DiagnosisItem(
                    category="Risk Management",
                    description=f"{component.name}: {component.narrative}",
                    severity="warning",
                    metric_value=component.score,
                    metric_name=component.name.lower(),
                ))

        # Check regime alignment
        config = self.config
        scoring = config.get("scoring", {})
        regime_weights = scoring.get("regime_weights", {})
        if regime.value in regime_weights:
            working.append(DiagnosisItem(
                category="Strategy Alignment",
                description=f"Using regime-specific weights for {regime.value}",
                severity="info",
            ))
        else:
            failing.append(DiagnosisItem(
                category="Strategy Alignment",
                description=f"Not using optimized weights for {regime.value} regime",
                severity="warning",
            ))

        return working, failing

    def _generate_pivots(self, health: StrategyHealth, failing: List[DiagnosisItem],
                         regime: MarketRegime, positions_df: pd.DataFrame, trade_stats) -> List[PivotRecommendation]:
        """Generate pivot recommendations based on diagnosis."""
        pivots = []
        num_positions = len(positions_df) if not positions_df.empty else 0

        # 1. Consolidation Pivot (if over-diversified)
        if num_positions > 20:
            target_positions = 12 if regime == MarketRegime.BEAR else 15
            pivots.append(PivotRecommendation(
                name="Consolidation Mode",
                pivot_type=PivotType.CONSOLIDATE,
                description="Reduce to fewer, higher-conviction positions",
                rationale=f"Currently holding {num_positions} positions. Consolidating to {target_positions} allows for larger position sizes and more meaningful impact per trade.",
                config_changes={
                    "max_positions": target_positions,
                    "risk_per_trade_pct": 12.0,  # Larger positions
                },
                projected_impact={
                    "positions": f"{num_positions} → {target_positions}",
                    "avg_position_size": "Increase by ~50%",
                    "edge_impact": "Stronger (larger winners matter more)",
                },
                confidence=0.75,
                risk_change="neutral",
                priority=1 if num_positions > 30 else 2,
            ))

        # 2. Defensive Pivot (if risk elevated or bear market)
        if regime == MarketRegime.BEAR or health.score < 50:
            pivots.append(PivotRecommendation(
                name="Defensive Mode",
                pivot_type=PivotType.DEFENSIVE,
                description="Reduce risk exposure and tighten stops",
                rationale=f"{'BEAR market conditions' if regime == MarketRegime.BEAR else 'Strategy struggling'} - prioritize capital preservation over growth.",
                config_changes={
                    "risk_per_trade_pct": 6.0,
                    "default_stop_loss_pct": 6.0,  # Tighter stops
                    "max_position_pct": 10.0,
                },
                projected_impact={
                    "risk": "Reduced by ~30%",
                    "max_loss_per_trade": "Lower",
                    "potential_upside": "Limited but protected",
                },
                confidence=0.80 if regime == MarketRegime.BEAR else 0.65,
                risk_change="reduced",
                priority=1 if regime == MarketRegime.BEAR else 2,
            ))

        # 3. Cash Mode (if critical issues or deep bear)
        if health.score < 40 or (regime == MarketRegime.BEAR and health.score < 60):
            pivots.append(PivotRecommendation(
                name="Cash Mode",
                pivot_type=PivotType.CASH_MODE,
                description="Significantly reduce exposure, hold mostly cash",
                rationale="Conditions are not favorable. Preserving capital until better opportunities emerge.",
                config_changes={
                    "max_positions": 5,
                    "risk_per_trade_pct": 5.0,
                    "default_stop_loss_pct": 5.0,
                    "max_position_pct": 8.0,
                },
                projected_impact={
                    "exposure": "Target ~20-30% invested",
                    "positions": f"{num_positions} → 5 max",
                    "risk": "Significantly reduced",
                },
                confidence=0.85,
                risk_change="reduced",
                priority=1 if health.score < 40 else 3,
            ))

        # 4. Aggressive Pivot (if bull market and doing well)
        if regime == MarketRegime.BULL and health.score >= 70:
            pivots.append(PivotRecommendation(
                name="Aggressive Mode",
                pivot_type=PivotType.AGGRESSIVE,
                description="Lean into momentum with larger positions",
                rationale="BULL market with strong performance - capitalize on favorable conditions.",
                config_changes={
                    "risk_per_trade_pct": 12.0,
                    "max_position_pct": 18.0,
                    "default_take_profit_pct": 25.0,  # Let winners run
                },
                projected_impact={
                    "position_sizes": "Increase by ~20%",
                    "potential_upside": "Higher",
                    "risk": "Slightly increased",
                },
                confidence=0.70,
                risk_change="increased",
                priority=3,
            ))

        # 5. Regime Adaptation (if not using regime weights)
        has_regime_issue = any(d.category == "Strategy Alignment" and "regime" in d.description.lower()
                              for d in failing)
        if has_regime_issue:
            pivots.append(PivotRecommendation(
                name="Regime Adaptation",
                pivot_type=PivotType.REGIME_ADAPT,
                description="Adjust strategy parameters for current market regime",
                rationale=f"Strategy not optimized for {regime.value} conditions.",
                config_changes=self._get_regime_specific_config(regime),
                projected_impact={
                    "factor_weights": f"Optimized for {regime.value}",
                    "min_score": f"Adjusted threshold",
                },
                confidence=0.75,
                risk_change="neutral",
                priority=2,
            ))

        # Sort by priority
        pivots.sort(key=lambda p: p.priority)

        return pivots

    def _get_regime_specific_config(self, regime: MarketRegime) -> dict:
        """Get regime-specific configuration changes."""
        if regime == MarketRegime.BULL:
            return {
                "scoring.default_weights.momentum": 0.28,
                "scoring.default_weights.volatility": 0.12,
                "scoring.min_score_threshold.BULL": 40.0,
            }
        elif regime == MarketRegime.BEAR:
            return {
                "scoring.default_weights.momentum": 0.12,
                "scoring.default_weights.volatility": 0.25,
                "scoring.default_weights.mean_reversion": 0.20,
                "scoring.min_score_threshold.BEAR": 65.0,
            }
        else:  # SIDEWAYS
            return {
                "scoring.default_weights.momentum": 0.18,
                "scoring.default_weights.volatility": 0.22,
                "scoring.default_weights.mean_reversion": 0.15,
                "scoring.min_score_threshold.SIDEWAYS": 55.0,
            }

    def _generate_mommy_narrative(self, health: StrategyHealth, working: List[DiagnosisItem],
                                   failing: List[DiagnosisItem], recommended: Optional[PivotRecommendation],
                                   regime: MarketRegime) -> str:
        """Generate Mommy's personalized narrative."""
        grade = health.grade

        if grade in ["A", "A-"]:
            return f"Everything is looking great, sweetie! You're doing wonderfully in this {regime.value} market. Keep up the good work - no changes needed right now."

        elif grade in ["B+", "B", "B-"]:
            issues = [d.description for d in failing[:2]]
            if issues:
                return f"Things are going pretty well! There are a few small things to keep an eye on - {issues[0].lower()}. But overall, I'm pleased with how we're doing."
            return f"Good work! The portfolio is performing well in this {regime.value} market."

        elif grade in ["C+", "C", "C-"]:
            if recommended:
                return f"I've been watching things closely, and I think we should make some adjustments. {recommended.rationale} I'd recommend switching to {recommended.name} - it'll help us navigate these conditions better."
            return f"We're doing okay, but there's room for improvement. Let me look at some adjustments we could make."

        elif grade == "D":
            if recommended:
                return f"Honey, we need to talk about the portfolio. Things aren't going as well as I'd like. {failing[0].description if failing else 'Several factors are struggling.'} I think we should switch to {recommended.name} to protect what we have."
            return "The portfolio needs attention. I'm seeing several warning signs that we should address."

        else:  # F
            return f"Sweetie, I'm not going to sugarcoat this - the current strategy isn't working in this {regime.value} market. We need to make changes to protect your capital. Let me show you what I recommend."

    def apply_pivot(self, pivot: PivotRecommendation) -> bool:
        """Apply a pivot recommendation to the config."""
        try:
            config = load_config()

            for key, value in pivot.config_changes.items():
                # Handle nested keys like "scoring.default_weights.momentum"
                keys = key.split(".")
                target = config
                for k in keys[:-1]:
                    if k not in target:
                        target[k] = {}
                    target = target[k]
                target[keys[-1]] = value

            save_config(config)
            return True
        except Exception as e:
            print(f"Error applying pivot: {e}")
            return False


def analyze_pivot() -> PivotAnalysis:
    """Analyze current strategy and generate pivot recommendations."""
    analyzer = StrategyPivotAnalyzer()
    return analyzer.analyze()


def apply_recommended_pivot(analysis: PivotAnalysis) -> bool:
    """Apply the recommended pivot from an analysis."""
    if analysis.recommended_pivot is None:
        return False
    analyzer = StrategyPivotAnalyzer()
    return analyzer.apply_pivot(analysis.recommended_pivot)


# ─── CLI for Testing ───
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("STRATEGY PIVOT ANALYSIS")
    print("=" * 70)

    analysis = analyze_pivot()

    # Health summary
    print(f"\nCurrent Strategy Health: {analysis.health.grade} ({analysis.health.score}/100)")
    print(f"Pivot Recommended: {'YES' if analysis.should_pivot else 'No'}")
    if analysis.should_pivot:
        print(f"Urgency: {analysis.urgency.upper()}")

    # Mommy's take
    print("\n" + "-" * 70)
    print("MOMMY SAYS:")
    print("-" * 70)
    print(f"\n  \"{analysis.mommy_says}\"")

    # Diagnosis
    if analysis.diagnosis_working:
        print("\n" + "-" * 70)
        print("WHAT'S WORKING:")
        print("-" * 70)
        for item in analysis.diagnosis_working[:5]:
            icon = "✓"
            print(f"  {icon} [{item.category}] {item.description}")

    if analysis.diagnosis_failing:
        print("\n" + "-" * 70)
        print("WHAT'S STRUGGLING:")
        print("-" * 70)
        for item in analysis.diagnosis_failing[:5]:
            icon = "✗" if item.severity == "critical" else "⚠"
            print(f"  {icon} [{item.category}] {item.description}")

    # Pivot recommendations
    if analysis.pivots:
        print("\n" + "-" * 70)
        print("PIVOT OPTIONS:")
        print("-" * 70)
        for i, pivot in enumerate(analysis.pivots, 1):
            recommended = " ← RECOMMENDED" if pivot == analysis.recommended_pivot else ""
            print(f"\n  {i}. {pivot.name}{recommended}")
            print(f"     {pivot.description}")
            print(f"     Rationale: {pivot.rationale}")
            print(f"     Confidence: {pivot.confidence*100:.0f}%")
            print(f"     Risk change: {pivot.risk_change}")
            if pivot.config_changes:
                print(f"     Changes: {pivot.config_changes}")
            if pivot.projected_impact:
                print(f"     Impact: {pivot.projected_impact}")

    print("\n" + "=" * 70)
