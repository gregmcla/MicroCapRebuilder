#!/usr/bin/env python3
"""
Layer 2: Opportunity Management Layer

Conviction-based scoring and buy proposal generation with pattern detection,
regime alignment, and volatility-adjusted position sizing.

Key features:
- Conviction scoring with multipliers (0.75x-2.0x base composite score)
- Pattern detection (breakout, momentum surge, mean reversion)
- Multiple confirmations bonus (momentum + volume + RS all strong)
- Regime alignment check
- Conviction-based position sizing (5-12% base)
- Volatility adjustment for position sizes

Usage:
    from opportunity_layer import OpportunityLayer
    from portfolio_state import load_portfolio_state

    state = load_portfolio_state(fetch_prices=False)
    layer = OpportunityLayer()
    result = layer.process(state, {})

    for proposal in result['buy_proposals']:
        print(f"{proposal.ticker}: {proposal.conviction_score.final_conviction:.1f}")
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from enhanced_structures import (
    BuyProposal, ConvictionScore, ConvictionLevel,
    PatternSignal, PatternType
)
from stock_scorer import StockScorer, StockScore
from portfolio_state import PortfolioState, load_watchlist
from market_regime import MarketRegime, get_position_size_multiplier


# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


class OpportunityLayer:
    """Layer 2: Conviction-based opportunity identification and buy proposals."""

    def __init__(self, config: dict = None):
        """
        Initialize OpportunityLayer.

        Args:
            config: Optional config dict (if not provided, loads from file)
        """
        self.config = config or load_config()
        self.layer2_config = self.config.get("enhanced_trading", {}).get("layer2", {})

        # Extract thresholds and multipliers
        self.min_conviction = self.layer2_config.get("min_conviction", 60)
        self.conviction_thresholds = self.layer2_config.get("conviction_thresholds", {
            "exceptional": 90,
            "strong": 80,
            "good": 70,
            "acceptable": 60
        })
        self.conviction_multipliers = self.layer2_config.get("conviction_multipliers", {
            "exceptional": 2.0,
            "strong": 1.5,
            "good": 1.0,
            "acceptable": 0.75
        })
        self.conviction_adjustments = self.layer2_config.get("conviction_adjustments", {
            "multiple_confirmations": 0.3,
            "breakout_pattern": 0.2,
            "fresh_high": 0.2,
            "regime_alignment": 0.2,
            "low_volatility": 0.1
        })
        self.conviction_multiplier_max = self.layer2_config.get("conviction_multiplier_max", 2.0)

        # Position sizing config
        self.position_sizing = self.layer2_config.get("position_sizing", {
            "high_conviction_pct": 12.0,
            "medium_conviction_pct": 8.0,
            "low_conviction_pct": 5.0
        })

    def process(self, state: PortfolioState, risk_layer_output: dict) -> dict:
        """
        Main entry point for Layer 2 processing.

        Args:
            state: Current portfolio state
            risk_layer_output: Output from Layer 1 (not used yet in this layer)

        Returns:
            Dict with:
                - conviction_scores: Dict[ticker, ConvictionScore]
                - buy_proposals: List[BuyProposal]
        """
        # Score all watchlist candidates (exclude tickers we already hold)
        watchlist = load_watchlist(portfolio_id=state.portfolio_id)
        if not watchlist:
            return {"conviction_scores": {}, "buy_proposals": []}

        current_tickers = set(state.positions["ticker"].tolist()) if not state.positions.empty else set()
        candidates = [t for t in watchlist if t not in current_tickers]
        if not candidates:
            return {"conviction_scores": {}, "buy_proposals": []}

        # Use StockScorer to get base composite scores
        scorer = StockScorer(regime=state.regime)
        stock_scores = scorer.score_watchlist(candidates)

        # Calculate conviction scores with multipliers
        conviction_scores = {}
        price_map = {}
        for stock_score in stock_scores:
            conviction = self.calculate_conviction(stock_score, state.regime)
            if conviction.final_conviction >= self.min_conviction:
                conviction_scores[conviction.ticker] = conviction
                price_map[conviction.ticker] = stock_score.current_price

        # Generate buy proposals from high-conviction candidates
        buy_proposals = self._generate_buy_proposals(conviction_scores, state, price_map)

        return {
            "conviction_scores": conviction_scores,
            "buy_proposals": buy_proposals
        }

    def calculate_conviction(self, stock_score: StockScore, regime: MarketRegime) -> ConvictionScore:
        """
        Calculate conviction score with multipliers and pattern detection.

        Args:
            stock_score: Base StockScore from StockScorer
            regime: Current market regime

        Returns:
            ConvictionScore with final conviction, level, patterns
        """
        # Start with base composite score
        composite = stock_score.composite_score

        # Determine base multiplier from composite score
        if composite >= self.conviction_thresholds["exceptional"]:
            base_multiplier = self.conviction_multipliers["exceptional"]
            conviction_level = ConvictionLevel.EXCEPTIONAL
        elif composite >= self.conviction_thresholds["strong"]:
            base_multiplier = self.conviction_multipliers["strong"]
            conviction_level = ConvictionLevel.STRONG
        elif composite >= self.conviction_thresholds["good"]:
            base_multiplier = self.conviction_multipliers["good"]
            conviction_level = ConvictionLevel.GOOD
        else:
            base_multiplier = self.conviction_multipliers["acceptable"]
            conviction_level = ConvictionLevel.ACCEPTABLE

        # Calculate adjustments
        multiplier = base_multiplier
        patterns_detected = []

        # Check for multiple confirmations
        if self._check_multiple_confirmations(stock_score):
            multiplier += self.conviction_adjustments["multiple_confirmations"]

        # Detect entry patterns
        detected_patterns = self._detect_entry_patterns(stock_score)
        if detected_patterns:
            patterns_detected.extend(detected_patterns)
            # Add pattern bonus (use max if multiple patterns)
            pattern_bonus = self.conviction_adjustments["breakout_pattern"]
            multiplier += pattern_bonus

        # Check regime alignment
        if self._check_regime_alignment(stock_score, regime):
            multiplier += self.conviction_adjustments["regime_alignment"]

        # Low volatility bonus
        if stock_score.atr_pct < 3.0:  # Low volatility
            multiplier += self.conviction_adjustments["low_volatility"]

        # Cap multiplier at max
        multiplier = min(multiplier, self.conviction_multiplier_max)

        # Calculate final conviction (capped at 100)
        final_conviction = min(100, composite * multiplier)

        # Build factor dict for transparency
        factors = {
            "momentum": stock_score.momentum_score,
            "volatility": stock_score.volatility_score,
            "volume": stock_score.volume_score,
            "relative_strength": stock_score.relative_strength_score,
            "mean_reversion": stock_score.mean_reversion_score,
            "rsi": stock_score.rsi_score,
            "composite": composite,
        }

        return ConvictionScore(
            ticker=stock_score.ticker,
            composite_score=composite,
            conviction_multiplier=round(multiplier, 2),
            final_conviction=round(final_conviction, 1),
            conviction_level=conviction_level,
            patterns_detected=patterns_detected,
            factors=factors,
            atr_pct=stock_score.atr_pct
        )

    def _check_multiple_confirmations(self, stock_score: StockScore) -> bool:
        """
        Check if momentum, volume, and relative strength all confirm.

        Args:
            stock_score: StockScore to check

        Returns:
            True if all three factors are strong (>75)
        """
        return (
            stock_score.momentum_score > 75 and
            stock_score.volume_score > 75 and
            stock_score.relative_strength_score > 75
        )

    def _detect_entry_patterns(self, stock_score: StockScore) -> List[PatternSignal]:
        """
        Detect entry patterns from stock score data.

        Args:
            stock_score: StockScore to analyze

        Returns:
            List of detected PatternSignal objects
        """
        patterns = []

        # Breakout pattern: strong momentum + high volume
        if stock_score.momentum_20d > 10 and stock_score.volume_score > 75:
            patterns.append(PatternSignal(
                pattern_type=PatternType.BREAKOUT,
                confidence=80,
                description=f"Breakout: {stock_score.momentum_20d:.1f}% momentum with elevated volume",
                detected_at_price=stock_score.current_price
            ))

        # Momentum surge: aligned multi-timeframe momentum
        if stock_score.momentum_alignment in ["ALIGNED", "ACCELERATING", "ALIGNED_STRONG"]:
            confidence = 90 if stock_score.momentum_alignment == "ACCELERATING" else 75
            patterns.append(PatternSignal(
                pattern_type=PatternType.MOMENTUM_SURGE,
                confidence=confidence,
                description=f"Momentum surge: {stock_score.momentum_alignment} across timeframes",
                detected_at_price=stock_score.current_price
            ))

        # Mean reversion: oversold with good fundamentals
        if stock_score.rsi_value < 35 and stock_score.composite_score > 60:
            patterns.append(PatternSignal(
                pattern_type=PatternType.MEAN_REVERSION,
                confidence=70,
                description=f"Mean reversion: RSI {stock_score.rsi_value:.1f} (oversold)",
                detected_at_price=stock_score.current_price
            ))

        return patterns

    def _check_regime_alignment(self, stock_score: StockScore, regime: MarketRegime) -> bool:
        """
        Check if stock characteristics align with current market regime.

        Args:
            stock_score: StockScore to check
            regime: Current market regime

        Returns:
            True if stock aligns with regime strategy
        """
        if regime == MarketRegime.BULL:
            # In bull market: prefer strong momentum
            return stock_score.momentum_score > 70
        elif regime == MarketRegime.SIDEWAYS:
            # In sideways: prefer low volatility + mean reversion
            return stock_score.volatility_score > 70 and stock_score.mean_reversion_score > 60
        elif regime == MarketRegime.BEAR:
            # In bear market: prefer defensive (high volatility score = low volatility)
            return stock_score.volatility_score > 80
        else:
            # Unknown regime: neutral check
            return stock_score.composite_score > 60

    def _generate_buy_proposals(
        self,
        conviction_scores: Dict[str, ConvictionScore],
        state: PortfolioState,
        price_map: Dict[str, float] = None
    ) -> List[BuyProposal]:
        """
        Generate BuyProposal objects from conviction scores.

        For initial deployment (no existing positions), skips regime and ATR
        reductions and targets the configured initial_deployment_target_pct.

        Args:
            conviction_scores: Dict of ConvictionScore objects
            state: Current portfolio state

        Returns:
            List of BuyProposal objects, sorted by conviction (highest first)
        """
        proposals = []
        remaining_cash = state.cash
        max_position_pct = self.config.get("max_position_pct", 15.0)

        # Detect initial deployment: no positions held yet
        is_initial_deployment = state.num_positions == 0
        initial_target_pct = self.config.get("initial_deployment_target_pct", 90.0)
        # Stop when remaining cash falls below the reserve threshold
        cash_reserve = state.cash * (1.0 - initial_target_pct / 100.0) if is_initial_deployment else 100.0

        # Don't generate any buy proposals if available cash is too small to build a meaningful position
        # (avoids 1-share micro-buys when the portfolio is nearly fully deployed)
        min_meaningful_buy = max(500.0, state.total_equity * 0.005)  # at least $500 or 0.5% of equity
        if remaining_cash - cash_reserve < min_meaningful_buy:
            return []

        # Sort by conviction (highest first)
        sorted_scores = sorted(
            conviction_scores.values(),
            key=lambda c: c.final_conviction,
            reverse=True
        )

        for conviction in sorted_scores:
            if remaining_cash <= cash_reserve:
                break

            # Get current price from scoring results (price_map) or state cache
            price = (price_map or {}).get(conviction.ticker) or state.price_cache.get(conviction.ticker)
            if price is None:
                continue  # Skip if no price available

            # Determine base position size from conviction level
            if conviction.final_conviction >= 80:
                base_size_pct = self.position_sizing["high_conviction_pct"]
            elif conviction.final_conviction >= 70:
                base_size_pct = self.position_sizing["medium_conviction_pct"]
            else:
                base_size_pct = self.position_sizing["low_conviction_pct"]

            position_size_pct = base_size_pct

            if is_initial_deployment:
                # Initial deployment: use full position sizes — goal is full capital
                # deployment across top-ranked candidates. Regime and ATR reductions
                # are skipped; the AI review layer acts as the quality gate.
                pass
            else:
                # Ongoing management: apply conservative volatility and regime adjustments
                if conviction.atr_pct > 6.0:
                    position_size_pct *= 0.5
                elif conviction.atr_pct > 4.0:
                    position_size_pct *= 0.75
                regime_multiplier = get_position_size_multiplier(state.regime)
                position_size_pct *= regime_multiplier

            # Cap at max position size
            position_size_pct = min(position_size_pct, max_position_pct)

            # Calculate dollar value and shares
            position_value = state.total_equity * (position_size_pct / 100.0)

            # Don't exceed remaining cash (minus reserve)
            position_value = min(position_value, remaining_cash - cash_reserve)

            if position_value < price:
                continue  # Can't afford even 1 share

            shares = int(position_value / price)
            if shares < 1:
                continue

            total_value = shares * price

            # Build rationale
            rationale = self._build_rationale(conviction, position_size_pct, state.regime)

            # Create proposal
            proposal = BuyProposal(
                ticker=conviction.ticker,
                shares=shares,
                price=price,
                total_value=total_value,
                conviction_score=conviction,
                position_size_pct=round(position_size_pct, 2),
                rationale=rationale
            )

            proposals.append(proposal)
            remaining_cash -= total_value

        return proposals

    def _build_rationale(
        self,
        conviction: ConvictionScore,
        position_size_pct: float,
        regime: MarketRegime
    ) -> str:
        """
        Build human-readable rationale for a buy proposal.

        Args:
            conviction: ConvictionScore for this candidate
            position_size_pct: Position size percentage
            regime: Current market regime

        Returns:
            Rationale string
        """
        parts = []

        # Conviction level
        parts.append(f"{conviction.conviction_level.value} conviction ({conviction.final_conviction:.1f})")

        # Top factors
        sorted_factors = sorted(
            [(k, v) for k, v in conviction.factors.items() if k != "composite"],
            key=lambda x: x[1],
            reverse=True
        )[:3]
        factor_str = ", ".join([f"{k}={v:.0f}" for k, v in sorted_factors])
        parts.append(f"top factors: {factor_str}")

        # Patterns
        if conviction.patterns_detected:
            pattern_names = [p.pattern_type.value for p in conviction.patterns_detected]
            parts.append(f"patterns: {', '.join(pattern_names)}")

        # Regime context
        parts.append(f"{regime.value} market")

        # Position size
        parts.append(f"{position_size_pct:.1f}% position")

        return " | ".join(parts)


if __name__ == "__main__":
    """Quick test of OpportunityLayer."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    from portfolio_state import load_portfolio_state

    print("Loading portfolio state...")
    state = load_portfolio_state(fetch_prices=False)

    print("Running OpportunityLayer...")
    layer = OpportunityLayer()
    result = layer.process(state, {})

    print(f"\nBuy proposals: {len(result['buy_proposals'])}")
    print(f"Conviction scores: {len(result['conviction_scores'])}")

    if result['conviction_scores']:
        sample = list(result['conviction_scores'].values())[0]
        print(f"\nSample: {sample.ticker} = {sample.final_conviction:.1f} ({sample.conviction_level.value})")
        print(f"  Multiplier: {sample.conviction_multiplier:.2f}")
        print(f"  Patterns: {[p.pattern_type.value for p in sample.patterns_detected]}")

    if result['buy_proposals']:
        print(f"\nTop proposal: {result['buy_proposals'][0].ticker}")
        print(f"  Rationale: {result['buy_proposals'][0].rationale}")

    print("\nOK")
