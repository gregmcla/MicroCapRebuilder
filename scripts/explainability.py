#!/usr/bin/env python3
"""
Trade Explainability Module for Mommy Bot.

Provides human-readable explanations for every trade:
- Why a stock was bought (key factors, regime context)
- Trade rationale storage and retrieval
- Summary generation for reports

Every trade should have a "why" - this module makes that happen.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from pathlib import Path
from datetime import date

from market_regime import MarketRegime

# ─── Paths ───
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
RATIONALE_FILE = DATA_DIR / "trade_rationales.jsonl"


@dataclass
class FactorContribution:
    """Individual factor contribution to a trade decision."""
    name: str  # momentum, volatility, volume, relative_strength, mean_reversion
    score: float  # 0-100
    weight: float  # 0.0-1.0
    contribution: float  # score * weight
    narrative: str  # Human-readable explanation


@dataclass
class TradeRationale:
    """Complete rationale for a trade."""
    transaction_id: str
    ticker: str
    action: str  # BUY or SELL
    date: str

    # Summary
    summary: str  # "Strong momentum in bull market with manageable volatility"

    # Key factors
    key_factors: List[FactorContribution] = field(default_factory=list)

    # Context
    regime: str = ""  # BULL/BEAR/SIDEWAYS
    regime_context: str = ""  # "Bull market favors momentum plays"

    # Scores
    composite_score: float = 0.0
    signal_rank: int = 0  # 1 = top pick

    # Risk assessment at entry
    risk_assessment: str = ""  # "Moderate risk with 8% stop loss"


class RationaleGenerator:
    """Generates human-readable trade rationales."""

    # Factor narratives based on score ranges
    FACTOR_NARRATIVES = {
        "momentum": {
            "high": "Strong upward price momentum",
            "medium": "Moderate price momentum",
            "low": "Weak or negative momentum",
        },
        "volatility": {
            "high": "Low volatility (stable price action)",
            "medium": "Moderate volatility",
            "low": "High volatility (erratic price swings)",
        },
        "volume": {
            "high": "Strong trading volume (high liquidity)",
            "medium": "Average trading volume",
            "low": "Low trading volume (liquidity concerns)",
        },
        "relative_strength": {
            "high": "Outperforming benchmark significantly",
            "medium": "Performing in line with benchmark",
            "low": "Underperforming benchmark",
        },
        "mean_reversion": {
            "high": "Trading near support (potential bounce)",
            "medium": "Trading near fair value",
            "low": "Trading extended from mean",
        },
    }

    # Regime context descriptions
    REGIME_CONTEXT = {
        MarketRegime.BULL: "Bull market conditions favor momentum and growth plays",
        MarketRegime.SIDEWAYS: "Sideways market favors mean reversion and low volatility",
        MarketRegime.BEAR: "Bear market requires defensive positioning and quality focus",
    }

    def generate_buy_rationale(
        self,
        transaction_id: str,
        ticker: str,
        composite_score: float,
        factor_scores: Dict[str, float],
        weights: Dict[str, float],
        regime: MarketRegime,
        signal_rank: int,
        stop_loss_pct: float = 8.0,
        take_profit_pct: float = 20.0,
    ) -> TradeRationale:
        """
        Generate a complete rationale for a BUY trade.

        Args:
            transaction_id: Unique transaction ID
            ticker: Stock symbol
            composite_score: Overall score (0-100)
            factor_scores: Dict of factor name -> score
            weights: Dict of factor name -> weight
            regime: Current market regime
            signal_rank: Rank among candidates (1=best)
            stop_loss_pct: Stop loss percentage
            take_profit_pct: Take profit percentage

        Returns:
            Complete TradeRationale object
        """
        # Build factor contributions
        key_factors = []
        for factor_name, score in factor_scores.items():
            weight = weights.get(factor_name, 0.0)
            contribution = score * weight

            # Determine narrative based on score level
            level = "high" if score >= 70 else ("medium" if score >= 40 else "low")
            narrative = self.FACTOR_NARRATIVES.get(factor_name, {}).get(
                level, f"{factor_name}: {score:.0f}"
            )

            key_factors.append(FactorContribution(
                name=factor_name,
                score=score,
                weight=weight,
                contribution=contribution,
                narrative=narrative,
            ))

        # Sort by contribution (highest first)
        key_factors.sort(key=lambda x: x.contribution, reverse=True)

        # Generate summary from top 2-3 factors
        top_factors = key_factors[:3]
        top_narratives = [f.narrative.lower() for f in top_factors if f.score >= 50]

        if len(top_narratives) >= 2:
            summary = f"{top_narratives[0].capitalize()} with {top_narratives[1]}"
        elif len(top_narratives) == 1:
            summary = top_narratives[0].capitalize()
        else:
            summary = f"Selected as #{signal_rank} pick with score {composite_score:.0f}"

        # Regime context
        regime_context = self.REGIME_CONTEXT.get(
            regime, "Market conditions uncertain"
        )

        # Risk assessment
        risk_reward = take_profit_pct / stop_loss_pct if stop_loss_pct > 0 else 0
        risk_assessment = (
            f"Risk/Reward: {risk_reward:.1f}:1 "
            f"(stop: -{stop_loss_pct:.0f}%, target: +{take_profit_pct:.0f}%)"
        )

        return TradeRationale(
            transaction_id=transaction_id,
            ticker=ticker,
            action="BUY",
            date=date.today().isoformat(),
            summary=summary,
            key_factors=key_factors,
            regime=regime.value if regime else "UNKNOWN",
            regime_context=regime_context,
            composite_score=composite_score,
            signal_rank=signal_rank,
            risk_assessment=risk_assessment,
        )

    def generate_sell_rationale(
        self,
        transaction_id: str,
        ticker: str,
        reason: str,
        entry_price: float,
        exit_price: float,
        regime: Optional[MarketRegime] = None,
    ) -> TradeRationale:
        """
        Generate a rationale for a SELL trade.

        Args:
            transaction_id: Unique transaction ID
            ticker: Stock symbol
            reason: STOP_LOSS, TAKE_PROFIT, MANUAL, SIGNAL
            entry_price: Original purchase price
            exit_price: Sale price
            regime: Current market regime

        Returns:
            TradeRationale object
        """
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100

        # Generate summary based on reason
        if reason == "STOP_LOSS":
            summary = f"Stop loss triggered at {pnl_pct:+.1f}% - protecting capital"
        elif reason == "TAKE_PROFIT":
            summary = f"Take profit target hit at {pnl_pct:+.1f}% - locking in gains"
        elif reason == "MANUAL":
            summary = f"Manual exit at {pnl_pct:+.1f}%"
        else:
            summary = f"Signal-based exit at {pnl_pct:+.1f}%"

        regime_context = ""
        if regime:
            regime_context = self.REGIME_CONTEXT.get(regime, "")

        return TradeRationale(
            transaction_id=transaction_id,
            ticker=ticker,
            action="SELL",
            date=date.today().isoformat(),
            summary=summary,
            key_factors=[],
            regime=regime.value if regime else "UNKNOWN",
            regime_context=regime_context,
            composite_score=0,
            signal_rank=0,
            risk_assessment=f"Exit P&L: {pnl_pct:+.1f}%",
        )


def save_rationale(rationale: TradeRationale):
    """Save a trade rationale to the JSONL file."""
    # Convert to dict, handling nested dataclasses
    data = asdict(rationale)

    # Append to file
    with open(RATIONALE_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")


def load_rationales() -> List[TradeRationale]:
    """Load all trade rationales from file."""
    if not RATIONALE_FILE.exists():
        return []

    rationales = []
    with open(RATIONALE_FILE, "r") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                # Convert factor dicts back to FactorContribution objects
                factors = [
                    FactorContribution(**f) for f in data.get("key_factors", [])
                ]
                data["key_factors"] = factors
                rationales.append(TradeRationale(**data))

    return rationales


def get_rationale_for_transaction(transaction_id: str) -> Optional[TradeRationale]:
    """Get rationale for a specific transaction."""
    rationales = load_rationales()
    for r in rationales:
        if r.transaction_id == transaction_id:
            return r
    return None


def format_rationale_text(rationale: TradeRationale) -> str:
    """Format a rationale as human-readable text."""
    lines = []
    lines.append(f"Trade: {rationale.action} {rationale.ticker}")
    lines.append(f"Date: {rationale.date}")
    lines.append(f"Summary: {rationale.summary}")
    lines.append("")

    if rationale.key_factors:
        lines.append("Key Factors:")
        for f in rationale.key_factors[:3]:
            lines.append(f"  - {f.name}: {f.narrative} (score: {f.score:.0f})")
        lines.append("")

    if rationale.regime:
        lines.append(f"Market Regime: {rationale.regime}")
        if rationale.regime_context:
            lines.append(f"  {rationale.regime_context}")
        lines.append("")

    if rationale.risk_assessment:
        lines.append(f"Risk: {rationale.risk_assessment}")

    return "\n".join(lines)


# ─── CLI for Testing ───
if __name__ == "__main__":
    from market_regime import MarketRegime

    print("\n─── Trade Explainability Demo ───\n")

    # Create a sample rationale
    generator = RationaleGenerator()

    sample_factors = {
        "momentum": 78.5,
        "volatility": 65.2,
        "volume": 55.0,
        "relative_strength": 82.1,
        "mean_reversion": 45.0,
    }

    sample_weights = {
        "momentum": 0.35,
        "volatility": 0.15,
        "volume": 0.15,
        "relative_strength": 0.25,
        "mean_reversion": 0.10,
    }

    rationale = generator.generate_buy_rationale(
        transaction_id="demo123",
        ticker="CRDO",
        composite_score=72.5,
        factor_scores=sample_factors,
        weights=sample_weights,
        regime=MarketRegime.BULL,
        signal_rank=1,
    )

    print(format_rationale_text(rationale))
