#!/usr/bin/env python3
"""
Factor Learning Module for GScott.

Tracks factor performance over time and suggests weight adjustments:
- Calculates win rate and contribution per factor
- Tracks performance by market regime
- Suggests conservative weight changes (max 5% per review)
- Provides confidence multipliers for position sizing

This enables the system to learn from its trading history.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import date, datetime, timedelta
from enum import Enum

import pandas as pd

# ─── Paths ───
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"
POST_MORTEMS_FILE = DATA_DIR / "post_mortems.csv"
FACTOR_PERFORMANCE_FILE = DATA_DIR / "factor_performance.csv"
CONFIG_FILE = DATA_DIR / "config.json"

from data_files import (
    get_transactions_file, get_post_mortems_file,
    get_factor_performance_file, load_config as load_config_from_files,
    save_config,
)


class PerformanceTrend(Enum):
    """Factor performance trend."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


@dataclass
class FactorPerformance:
    """Performance metrics for a single factor."""
    factor: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float  # 0-100
    avg_contribution_winning: float  # Average $ contribution on wins
    avg_contribution_losing: float  # Average $ contribution on losses
    total_contribution: float  # Net $ contribution
    regime_performance: Dict[str, float]  # {BULL: 65%, SIDEWAYS: 45%, BEAR: 30%}
    trend: str  # improving/stable/declining
    last_updated: str


@dataclass
class WeightSuggestion:
    """Suggested weight adjustment for a factor."""
    factor: str
    current_weight: float
    suggested_weight: float
    change_pct: float  # Percentage change (capped at 5%)
    reason: str
    confidence: str  # LOW/MEDIUM/HIGH


@dataclass
class ConfidenceScore:
    """Confidence score for position sizing."""
    score: float  # 0.5 to 1.5 multiplier
    factors_contributing: List[str]
    explanation: str


class FactorLearner:
    """Learns from factor performance to improve scoring."""

    FACTOR_NAMES = ["price_momentum", "earnings_growth", "quality", "volume", "volatility", "value_timing"]

    def __init__(self, portfolio_id: str = None):
        self.portfolio_id = portfolio_id
        self.config = load_config_from_files(portfolio_id) if portfolio_id else self._load_config()
        self.learning_config = self.config.get("learning", {})
        self._transactions_file = get_transactions_file(portfolio_id) if portfolio_id else TRANSACTIONS_FILE
        self._post_mortems_file = get_post_mortems_file(portfolio_id) if portfolio_id else POST_MORTEMS_FILE
        self._factor_performance_file = get_factor_performance_file(portfolio_id) if portfolio_id else FACTOR_PERFORMANCE_FILE
        self.transactions_df = self._load_transactions()
        self.post_mortems_df = self._load_post_mortems()

    def _load_config(self) -> dict:
        """Load configuration."""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                return json.load(f)
        return {}

    def _load_transactions(self) -> pd.DataFrame:
        """Load transactions with factor scores."""
        if not self._transactions_file.exists():
            return pd.DataFrame()
        df = pd.read_csv(self._transactions_file)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def _load_post_mortems(self) -> pd.DataFrame:
        """Load post-mortems for outcome data."""
        if not self._post_mortems_file.exists():
            return pd.DataFrame()
        return pd.read_csv(self._post_mortems_file)

    def calculate_factor_performance(self) -> List[FactorPerformance]:
        """Calculate performance metrics for each factor."""
        performances = []

        if self.transactions_df.empty or self.post_mortems_df.empty:
            return performances

        # Get buy transactions with factor scores
        buys = self.transactions_df[
            (self.transactions_df["action"] == "BUY") &
            (self.transactions_df["factor_scores"].notna()) &
            (self.transactions_df["factor_scores"] != "")
        ].copy()

        if buys.empty:
            return performances

        # Match with post-mortems for outcomes
        trades_with_outcomes = []
        for _, buy in buys.iterrows():
            # Find matching post-mortem
            ticker = buy["ticker"]
            pm = self.post_mortems_df[
                self.post_mortems_df["ticker"] == ticker
            ]
            if not pm.empty:
                latest_pm = pm.iloc[-1]
                try:
                    factor_scores = json.loads(buy["factor_scores"])
                    trades_with_outcomes.append({
                        "ticker": ticker,
                        "factor_scores": factor_scores,
                        "regime": buy.get("regime_at_entry", "UNKNOWN"),
                        "pnl": latest_pm.get("pnl", 0),
                        "pnl_pct": latest_pm.get("pnl_pct", 0),
                        "is_win": latest_pm.get("pnl", 0) >= 0,
                    })
                except (json.JSONDecodeError, TypeError):
                    pass

        if not trades_with_outcomes:
            return performances

        # Calculate per-factor metrics
        for factor in self.FACTOR_NAMES:
            factor_data = {
                "wins": [],
                "losses": [],
                "regime_wins": {"BULL": 0, "SIDEWAYS": 0, "BEAR": 0, "UNKNOWN": 0},
                "regime_total": {"BULL": 0, "SIDEWAYS": 0, "BEAR": 0, "UNKNOWN": 0},
            }

            for trade in trades_with_outcomes:
                factor_score = trade["factor_scores"].get(factor, None)
                # Backward compat: migrate old factor key names
                if factor_score is None:
                    if factor == "price_momentum":
                        m = trade["factor_scores"].get("momentum", 0)
                        rs = trade["factor_scores"].get("relative_strength", 0)
                        factor_score = (m * 0.6 + rs * 0.4) if (m and rs) else (m or rs or 0)
                    elif factor == "value_timing":
                        mr = trade["factor_scores"].get("mean_reversion", 0)
                        rsi = trade["factor_scores"].get("rsi", 0)
                        factor_score = ((mr + rsi) / 2) if (mr and rsi) else (mr or rsi or 0)
                    elif factor in ("earnings_growth", "quality"):
                        factor_score = 50  # Neutral default for new factors not in old transactions
                    else:
                        factor_score = 0
                if not factor_score:
                    continue

                # Calculate factor's contribution to this trade
                total_score = sum(trade["factor_scores"].values())
                if total_score == 0:
                    continue

                factor_contribution = trade["pnl"] * (factor_score / total_score)

                if trade["is_win"]:
                    factor_data["wins"].append(factor_contribution)
                else:
                    factor_data["losses"].append(factor_contribution)

                # Track by regime
                regime = trade["regime"] or "UNKNOWN"
                factor_data["regime_total"][regime] = factor_data["regime_total"].get(regime, 0) + 1
                if trade["is_win"]:
                    factor_data["regime_wins"][regime] = factor_data["regime_wins"].get(regime, 0) + 1

            # Calculate metrics
            total_trades = len(factor_data["wins"]) + len(factor_data["losses"])
            if total_trades == 0:
                continue

            win_rate = (len(factor_data["wins"]) / total_trades) * 100
            avg_win = sum(factor_data["wins"]) / len(factor_data["wins"]) if factor_data["wins"] else 0
            avg_loss = sum(factor_data["losses"]) / len(factor_data["losses"]) if factor_data["losses"] else 0
            total_contribution = sum(factor_data["wins"]) + sum(factor_data["losses"])

            # Calculate regime performance
            regime_perf = {}
            for regime in ["BULL", "SIDEWAYS", "BEAR"]:
                total = factor_data["regime_total"].get(regime, 0)
                wins = factor_data["regime_wins"].get(regime, 0)
                if total > 0:
                    regime_perf[regime] = round((wins / total) * 100, 1)

            # Determine trend (would need historical data, simplified here)
            trend = self._calculate_trend(factor, win_rate)

            performances.append(FactorPerformance(
                factor=factor,
                total_trades=total_trades,
                winning_trades=len(factor_data["wins"]),
                losing_trades=len(factor_data["losses"]),
                win_rate=round(win_rate, 1),
                avg_contribution_winning=round(avg_win, 2),
                avg_contribution_losing=round(avg_loss, 2),
                total_contribution=round(total_contribution, 2),
                regime_performance=regime_perf,
                trend=trend,
                last_updated=date.today().isoformat(),
            ))

        return performances

    def _calculate_trend(self, factor: str, current_win_rate: float) -> str:
        """
        Calculate performance trend for a factor.

        Compares current performance to historical baseline.
        """
        # Load historical performance if available
        if self._factor_performance_file.exists():
            try:
                df = pd.read_csv(self._factor_performance_file)
                historical = df[df["factor"] == factor]
                if not historical.empty and len(historical) >= 2:
                    prev_win_rate = historical.iloc[-2].get("win_rate", current_win_rate)
                    diff = current_win_rate - prev_win_rate
                    if diff > 5:
                        return PerformanceTrend.IMPROVING.value
                    elif diff < -5:
                        return PerformanceTrend.DECLINING.value
            except Exception:
                pass

        return PerformanceTrend.STABLE.value

    def suggest_weight_adjustments(
        self,
        current_regime: str = None
    ) -> List[WeightSuggestion]:
        """
        Suggest weight adjustments based on factor performance.

        Constraints:
        - Max 5% change per factor per review
        - Requires minimum trades before suggesting changes
        - Changes are regime-aware
        """
        suggestions = []
        performances = self.calculate_factor_performance()

        if not performances:
            return suggestions

        # Get current weights
        scoring_config = self.config.get("scoring", {})
        if current_regime:
            current_weights = scoring_config.get("regime_weights", {}).get(
                current_regime, scoring_config.get("default_weights", {})
            )
        else:
            current_weights = scoring_config.get("default_weights", {})

        # Learning thresholds from config
        min_trades = self.learning_config.get("min_trades_for_adjustment", 10)
        max_change = self.learning_config.get("max_weight_change_pct", 5.0) / 100

        for perf in performances:
            current_weight = current_weights.get(perf.factor, 0.2)

            # Skip if insufficient data
            if perf.total_trades < min_trades:
                continue

            # Calculate suggested adjustment
            # Base adjustment on win rate vs baseline (50%)
            win_rate_diff = perf.win_rate - 50

            # Scale adjustment: +/- 10% win rate diff = +/- 5% weight change
            raw_adjustment = (win_rate_diff / 10) * max_change

            # Cap adjustment
            adjustment = max(-max_change, min(max_change, raw_adjustment))

            # Calculate new weight (ensure stays positive and reasonable)
            new_weight = max(0.05, min(0.50, current_weight + adjustment))

            # Only suggest if meaningful change
            if abs(new_weight - current_weight) < 0.01:
                continue

            # Generate reason
            if adjustment > 0:
                reason = f"{perf.factor.replace('_', ' ').title()} has {perf.win_rate:.0f}% win rate, above baseline"
                confidence = "HIGH" if perf.win_rate > 60 else "MEDIUM"
            else:
                reason = f"{perf.factor.replace('_', ' ').title()} has {perf.win_rate:.0f}% win rate, below baseline"
                confidence = "HIGH" if perf.win_rate < 40 else "MEDIUM"

            # Lower confidence if trend is opposite to suggestion
            if adjustment > 0 and perf.trend == PerformanceTrend.DECLINING.value:
                confidence = "LOW"
            elif adjustment < 0 and perf.trend == PerformanceTrend.IMPROVING.value:
                confidence = "LOW"

            suggestions.append(WeightSuggestion(
                factor=perf.factor,
                current_weight=round(current_weight, 3),
                suggested_weight=round(new_weight, 3),
                change_pct=round((new_weight - current_weight) * 100, 1),
                reason=reason,
                confidence=confidence,
            ))

        # Sort by absolute change (most impactful first)
        suggestions.sort(key=lambda x: abs(x.change_pct), reverse=True)
        return suggestions

    def apply_weight_adjustments(self, portfolio_id: str = None) -> bool:
        """
        Apply suggested weight adjustments to the portfolio's config.json.

        Only proceeds when there are suggestions with at least MEDIUM confidence.
        Constraints enforced:
          - Each factor weight: min 5%, max 40%
          - All weights normalized to sum exactly 1.0

        Returns True if any weights were actually changed, False otherwise.
        """
        effective_portfolio_id = portfolio_id or self.portfolio_id

        # Only adjust default_weights (not regime_weights — blending handles regime influence)
        suggestions = self.suggest_weight_adjustments(current_regime=None)

        # Filter to MEDIUM/HIGH confidence only — LOW confidence means mixed signals
        actionable = [s for s in suggestions if s.confidence in ("MEDIUM", "HIGH")]
        if not actionable:
            print("[factor_learning] No actionable weight suggestions (need MEDIUM+ confidence).")
            return False

        # Load fresh config for writing
        config = load_config_from_files(effective_portfolio_id)
        scoring = config.setdefault("scoring", {})
        current_defaults = dict(scoring.get("default_weights", {}))

        if not current_defaults:
            print("[factor_learning] No default_weights in config — skipping apply.")
            return False

        # Apply each suggestion
        changed = []
        updated_weights = dict(current_defaults)
        for s in actionable:
            if s.factor not in updated_weights:
                continue
            old = updated_weights[s.factor]
            # Clamp to [0.05, 0.40]
            new = max(0.05, min(0.40, s.suggested_weight))
            if abs(new - old) < 0.001:
                continue
            updated_weights[s.factor] = round(new, 4)
            changed.append((s.factor, old, new, s.confidence, s.reason))

        if not changed:
            print("[factor_learning] Weight changes below minimum threshold — no update needed.")
            return False

        # Normalize so weights sum to 1.0
        total = sum(updated_weights.values())
        if total > 0:
            updated_weights = {k: round(v / total, 4) for k, v in updated_weights.items()}
            # Fix floating-point rounding: assign remainder to largest weight
            diff = round(1.0 - sum(updated_weights.values()), 4)
            if diff != 0:
                largest = max(updated_weights, key=updated_weights.get)
                updated_weights[largest] = round(updated_weights[largest] + diff, 4)

        scoring["default_weights"] = updated_weights
        save_config(config, effective_portfolio_id)

        print("[factor_learning] Applied weight adjustments to config.json:")
        for factor, old, new, conf, reason in changed:
            direction = "+" if new > old else ""
            print(f"  {factor}: {old:.1%} → {new:.1%} ({direction}{(new-old)*100:.1f}pp) [{conf}] {reason}")
        print(f"  Normalized weights sum: {sum(updated_weights.values()):.4f}")
        return True

    def calculate_confidence_multiplier(
        self,
        factor_scores: Dict[str, float],
        regime: str = None
    ) -> ConfidenceScore:
        """
        Calculate position size confidence multiplier based on factor track record.

        Returns 0.5x to 1.5x multiplier based on how well the dominant
        factors have performed historically.

        Args:
            factor_scores: Factor scores for the candidate trade
            regime: Current market regime

        Returns:
            ConfidenceScore with multiplier and explanation
        """
        performances = self.calculate_factor_performance()

        if not performances or not factor_scores:
            return ConfidenceScore(
                score=1.0,
                factors_contributing=[],
                explanation="Insufficient data - using default position size"
            )

        # Create performance lookup
        perf_by_factor = {p.factor: p for p in performances}

        # Find top 2 contributing factors
        sorted_factors = sorted(
            factor_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:2]

        # Calculate weighted confidence based on factor performance
        total_weight = 0
        weighted_confidence = 0
        contributing_factors = []

        for factor, score in sorted_factors:
            if factor not in perf_by_factor:
                continue

            perf = perf_by_factor[factor]

            # Use regime-specific win rate if available
            if regime and regime in perf.regime_performance:
                factor_win_rate = perf.regime_performance[regime]
            else:
                factor_win_rate = perf.win_rate

            # Convert win rate to confidence multiplier (50% = 1.0x)
            # 70% = 1.4x, 30% = 0.6x, capped at 0.5-1.5
            factor_confidence = 0.5 + (factor_win_rate / 100)
            factor_confidence = max(0.5, min(1.5, factor_confidence))

            weight = score / 100  # Normalize score to weight
            weighted_confidence += factor_confidence * weight
            total_weight += weight

            contributing_factors.append(factor)

        if total_weight == 0:
            return ConfidenceScore(
                score=1.0,
                factors_contributing=[],
                explanation="No factor performance data available"
            )

        # Calculate final multiplier
        final_multiplier = weighted_confidence / total_weight
        final_multiplier = max(0.5, min(1.5, final_multiplier))

        # Generate explanation
        if final_multiplier > 1.1:
            explanation = f"High confidence: {', '.join(contributing_factors)} performing well"
        elif final_multiplier < 0.9:
            explanation = f"Low confidence: {', '.join(contributing_factors)} underperforming"
        else:
            explanation = "Moderate confidence based on factor track record"

        return ConfidenceScore(
            score=round(final_multiplier, 2),
            factors_contributing=contributing_factors,
            explanation=explanation,
        )

    def get_factor_summary(self) -> Dict:
        """Get summary of factor performance for display."""
        performances = self.calculate_factor_performance()

        if not performances:
            return {
                "status": "insufficient_data",
                "message": "Need more closed trades to calculate factor performance",
                "factors": [],
            }

        factor_summaries = []
        for perf in performances:
            factor_summaries.append({
                "factor": perf.factor,
                "win_rate": perf.win_rate,
                "total_trades": perf.total_trades,
                "total_contribution": perf.total_contribution,
                "trend": perf.trend,
                "best_regime": max(
                    perf.regime_performance.items(),
                    key=lambda x: x[1]
                )[0] if perf.regime_performance else "N/A",
            })

        # Sort by total contribution
        factor_summaries.sort(key=lambda x: x["total_contribution"], reverse=True)

        return {
            "status": "ok",
            "total_analyzed_trades": sum(p.total_trades for p in performances) // len(performances),
            "factors": factor_summaries,
            "last_updated": date.today().isoformat(),
        }


def save_factor_performance(performances: List[FactorPerformance], portfolio_id: str = None):
    """Save factor performance data to CSV."""
    if not performances:
        return

    data = [asdict(p) for p in performances]
    # Convert regime_performance dict to JSON string
    for d in data:
        d["regime_performance"] = json.dumps(d["regime_performance"])

    df_new = pd.DataFrame(data)

    perf_file = get_factor_performance_file(portfolio_id) if portfolio_id else FACTOR_PERFORMANCE_FILE
    if perf_file.exists():
        df_existing = pd.read_csv(perf_file)
        # Keep history, append new
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new

    df_combined.to_csv(perf_file, index=False)


def get_factor_performance(portfolio_id: str = None) -> List[FactorPerformance]:
    """Get current factor performance metrics."""
    learner = FactorLearner(portfolio_id=portfolio_id)
    performances = learner.calculate_factor_performance()

    # Save for historical tracking
    if performances:
        save_factor_performance(performances, portfolio_id=portfolio_id)

    return performances


def get_weight_suggestions(regime: str = None, portfolio_id: str = None) -> List[WeightSuggestion]:
    """Get weight adjustment suggestions."""
    learner = FactorLearner(portfolio_id=portfolio_id)
    return learner.suggest_weight_adjustments(regime)


def apply_weight_adjustments(portfolio_id: str = None) -> bool:
    """
    Persist learned weight adjustments to config.json for the given portfolio.

    Call this after executing trades when there are 10+ completed trades.
    Returns True if config was updated, False otherwise.
    """
    learner = FactorLearner(portfolio_id=portfolio_id)
    return learner.apply_weight_adjustments(portfolio_id=portfolio_id)


def get_confidence_multiplier(
    factor_scores: Dict[str, float],
    regime: str = None,
    portfolio_id: str = None,
) -> float:
    """
    Get confidence multiplier for position sizing.

    Returns float between 0.5 and 1.5.
    """
    learner = FactorLearner(portfolio_id=portfolio_id)
    confidence = learner.calculate_confidence_multiplier(factor_scores, regime)
    return confidence.score


def format_factor_performance_text(performances: List[FactorPerformance]) -> str:
    """Format factor performance as readable text."""
    if not performances:
        return "No factor performance data available yet."

    lines = []
    lines.append("Factor Performance Summary")
    lines.append("=" * 50)

    for perf in sorted(performances, key=lambda x: x.total_contribution, reverse=True):
        trend_icon = {
            "improving": "^",
            "stable": "-",
            "declining": "v",
        }.get(perf.trend, "?")

        lines.append(f"\n{perf.factor.upper().replace('_', ' ')}")
        lines.append(f"  Win Rate:     {perf.win_rate:.0f}% ({perf.winning_trades}W / {perf.losing_trades}L)")
        lines.append(f"  Contribution: ${perf.total_contribution:+,.2f}")
        lines.append(f"  Trend:        {trend_icon} {perf.trend}")

        if perf.regime_performance:
            regime_str = ", ".join(
                f"{r}: {v:.0f}%" for r, v in perf.regime_performance.items()
            )
            lines.append(f"  By Regime:    {regime_str}")

    return "\n".join(lines)


# ─── CLI for Testing ───
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Factor Learning")
    parser.add_argument("--portfolio", default=None, help="Portfolio ID (default: registry default)")
    args = parser.parse_args()

    print("\n─── Factor Learning Demo ───\n")

    learner = FactorLearner(portfolio_id=args.portfolio)

    # Get factor performance
    performances = learner.calculate_factor_performance()
    if performances:
        print(format_factor_performance_text(performances))

        print("\n" + "=" * 50)
        print("Weight Suggestions")
        print("=" * 50)

        suggestions = learner.suggest_weight_adjustments()
        if suggestions:
            for s in suggestions:
                print(f"\n{s.factor}:")
                print(f"  Current: {s.current_weight:.1%} -> Suggested: {s.suggested_weight:.1%}")
                print(f"  Change:  {s.change_pct:+.1f}%")
                print(f"  Reason:  {s.reason}")
                print(f"  Confidence: {s.confidence}")
        else:
            print("No weight changes suggested (need more data or changes too small)")
    else:
        print("No factor performance data available yet.")
        print("(Need closed trades with factor scores to analyze)")
