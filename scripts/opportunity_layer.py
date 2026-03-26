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
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from enhanced_structures import (
    BuyProposal, ConvictionScore, ConvictionLevel,
    PatternSignal, PatternType, SellProposal, UrgencyLevel
)
from stock_scorer import StockScorer, StockScore
from portfolio_state import PortfolioState, load_watchlist
from market_regime import MarketRegime, get_position_size_multiplier
from data_files import get_transactions_file
from reentry_guard import get_reentry_context


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

        # Validate conviction multiplier config: if min_conviction >= 60 and the
        # "acceptable" multiplier is < 1.0, stocks scoring 60-74 can never reach
        # min_conviction (e.g. 74 × 0.75 = 55.5 < 60) — the "acceptable" band is
        # a dead zone.  Log a clear warning so the misconfiguration is visible.
        acceptable_mult = self.conviction_multipliers.get("acceptable", 1.0)
        if self.min_conviction >= 60 and acceptable_mult < 1.0:
            logging.warning(
                "OpportunityLayer config dead zone: min_conviction=%s but "
                "conviction_multipliers.acceptable=%.2f. Stocks scoring 60–74 "
                "can never reach min_conviction (e.g. 74 × %.2f = %.1f). "
                "Set acceptable multiplier to 1.0 or raise it above 1.0 to fix.",
                self.min_conviction,
                acceptable_mult,
                acceptable_mult,
                74 * acceptable_mult,
            )

    def process(self, state: PortfolioState, risk_layer_output: dict, social_signals=None, info_cache: Optional[Dict] = None) -> dict:
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
        rg_config = self.config.get("enhanced_trading", {}).get("reentry_guard", {})
        reentry_guard_enabled = bool(rg_config.get("enabled", True))
        stop_loss_cooldown_days = int(rg_config.get("stop_loss_cooldown_days", 7))
        lookback_days = int(rg_config.get("lookback_days", 30))
        meaningful_change_threshold_pts = float(rg_config.get("meaningful_change_threshold_pts", 10))

        # Score all watchlist candidates (exclude tickers we already hold)
        watchlist = load_watchlist(portfolio_id=state.portfolio_id)
        if not watchlist:
            return {"conviction_scores": {}, "buy_proposals": []}

        current_tickers = set(state.positions["ticker"].tolist()) if not state.positions.empty else set()

        # Guard: if positions are empty but num_positions > 0, the positions DataFrame
        # failed to load. An empty current_tickers set would let ALL watchlist tickers
        # pass the filter — including ones we already own. Bail out early to avoid
        # proposing buys for potentially already-held positions.
        if state.positions.empty and state.num_positions > 0:
            logging.warning(
                "OpportunityLayer: positions DataFrame is empty but num_positions=%d. "
                "Possible load failure — skipping buy proposals to avoid duplicate buys.",
                state.num_positions,
            )
            return {"conviction_scores": {}, "buy_proposals": []}

        candidates = [t for t in watchlist if t not in current_tickers]
        if not candidates:
            return {"conviction_scores": {}, "buy_proposals": []}

        # ── Bug #7 fix: Cooldown after stop-out ──────────────────────────────
        # Exclude tickers that were stopped out in the last N days to prevent
        # immediately re-entering a position that just triggered a stop loss.
        tx_file = get_transactions_file(state.portfolio_id)
        if reentry_guard_enabled:
            cooled_down_tickers: set = set()
            try:
                if tx_file.exists():
                    tx_df = pd.read_csv(tx_file, dtype=str)
                    if not tx_df.empty and "date" in tx_df.columns and "reason" in tx_df.columns:
                        cutoff = date.today() - timedelta(days=stop_loss_cooldown_days)
                        for _, row in tx_df.iterrows():
                            try:
                                tx_date = date.fromisoformat(str(row["date"])[:10])
                            except Exception as e:
                                print(f"Warning: failed to parse transaction date: {e}")
                                continue
                            if tx_date >= cutoff and str(row.get("reason", "")).upper() == "STOP_LOSS":
                                ticker = str(row.get("ticker", "")).strip().upper()
                                if ticker:
                                    cooled_down_tickers.add(ticker)
            except Exception as e:
                logging.warning("OpportunityLayer: failed to load cooldown tickers: %s", e)

            if cooled_down_tickers:
                before = len(candidates)
                candidates = [t for t in candidates if t not in cooled_down_tickers]
                excluded = before - len(candidates)
                if excluded:
                    logging.info(
                        "OpportunityLayer: excluded %d candidate(s) due to %d-day stop-loss cooldown: %s",
                        excluded,
                        stop_loss_cooldown_days,
                        sorted(cooled_down_tickers & set([t for t in watchlist if t not in current_tickers])),
                    )
        # ─────────────────────────────────────────────────────────────────────

        # Use StockScorer to get base composite scores
        scorer = StockScorer(regime=state.regime)
        stock_scores = scorer.score_watchlist(candidates, info_cache=info_cache)

        # Calculate conviction scores with multipliers
        conviction_scores = {}
        price_map = {}
        for stock_score in stock_scores:
            # Always populate price_map for every scored stock so _generate_buy_proposals
            # never has to fall back to state.price_cache (which only has held positions).
            price_map[stock_score.ticker] = stock_score.current_price
            conviction = self.calculate_conviction(stock_score, state.regime)
            if conviction.final_conviction >= self.min_conviction:
                conviction_scores[conviction.ticker] = conviction

        # Generate buy proposals from high-conviction candidates
        buy_proposals = self._generate_buy_proposals(conviction_scores, state, price_map,
                                                     social_signals=social_signals)

        if reentry_guard_enabled:
            # Attach reentry context to each buy proposal so AI review can see
            # whether the ticker has been traded before and how scores have changed.
            for proposal in buy_proposals:
                try:
                    current_scores = {
                        k: v for k, v in proposal.conviction_score.factors.items()
                        if k != "composite"
                    }
                    proposal.reentry_context = get_reentry_context(
                        ticker=proposal.ticker,
                        transactions_path=tx_file,
                        current_scores=current_scores,
                        lookback_days=lookback_days,
                        meaningful_change_threshold_pts=meaningful_change_threshold_pts,
                    )
                except Exception as e:
                    logging.warning(
                        "OpportunityLayer: reentry_guard failed for %s: %s", proposal.ticker, e
                    )

        # ── Bug #6 fix: Rotation trigger ─────────────────────────────────────
        # Trigger rotation when:
        #   (a) No normal buy proposals were generated (likely low cash), OR
        #   (b) Portfolio is fully deployed (cash < 5% of equity) AND there are
        #       high-conviction candidates that could upgrade held positions.
        # This makes rotation useful even when some cash is technically available.
        rotation_output = {"rotation_sells": [], "rotation_buys": []}
        fully_deployed = (
            state.total_equity > 0
            and state.cash < state.total_equity * 0.05
        )
        if conviction_scores and (not buy_proposals or fully_deployed):
            rotation_output = self._generate_rotation_proposals(
                conviction_scores, state, risk_layer_output, price_map,
                social_signals=social_signals
            )
        # ─────────────────────────────────────────────────────────────────────

        return {
            "conviction_scores": conviction_scores,
            "buy_proposals": buy_proposals,
            **rotation_output,
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
            "price_momentum": stock_score.price_momentum_score,
            "earnings_growth": stock_score.earnings_growth_score,
            "quality": stock_score.quality_score,
            "volume": stock_score.volume_score,
            "volatility": stock_score.volatility_score,
            "value_timing": stock_score.value_timing_score,
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
            stock_score.price_momentum_score > 75 and
            stock_score.volume_score > 75 and
            stock_score.earnings_growth_score > 60
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
            return stock_score.price_momentum_score > 70
        elif regime == MarketRegime.SIDEWAYS:
            # In sideways: prefer low volatility + value timing
            return stock_score.volatility_score > 70 and stock_score.value_timing_score > 60
        elif regime == MarketRegime.BEAR:
            # In bear market: prefer defensive (quality + low volatility)
            return stock_score.volatility_score > 80 and stock_score.quality_score > 60
        else:
            # Unknown regime: neutral check
            return stock_score.composite_score > 60

    def _generate_buy_proposals(
        self,
        conviction_scores: Dict[str, ConvictionScore],
        state: PortfolioState,
        price_map: Dict[str, float] = None,
        social_signals=None
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

        # Detect initial deployment: portfolio is below its deployment target.
        # This handles new portfolios that bought a few positions then ran ANALYZE
        # again — num_positions > 0 but most capital is still idle.
        initial_target_pct = self.config.get("initial_deployment_target_pct", 90.0)
        deployed_pct = (state.positions_value / state.total_equity * 100.0) if state.total_equity > 0 else 0.0
        is_initial_deployment = deployed_pct < (initial_target_pct * 0.5)  # below 50% of target = still filling up
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

            # Skip if position would be too small to be meaningful
            min_notional = max(price * 5, 250.0)  # at least 5 shares or $250
            if position_value < min_notional:
                continue

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
                rationale=rationale,
                social_signal=social_signals.get(conviction.ticker) if social_signals else None,
            )

            proposals.append(proposal)
            remaining_cash -= total_value

            # Stop if remaining cash (after reserve) is too small for any meaningful buy
            if remaining_cash - cash_reserve < min_meaningful_buy:
                break

        return proposals

    def _generate_rotation_proposals(
        self,
        conviction_scores: Dict[str, "ConvictionScore"],
        state: "PortfolioState",
        risk_layer_output: dict,
        price_map: Dict[str, float],
        social_signals=None
    ) -> dict:
        """
        Generate rotation sell+buy pairs when portfolio is fully deployed.

        Sells the lowest-scoring held position to fund a significantly better
        watchlist candidate (requires min_upgrade_score_gap).

        Returns:
            Dict with rotation_sells and rotation_buys lists.
        """
        rotation_cfg = self.config.get("enhanced_trading", {}).get("rotation", {})
        if not rotation_cfg.get("enabled", False):
            return {"rotation_sells": [], "rotation_buys": []}

        min_gap = rotation_cfg.get("min_upgrade_score_gap", 20)
        max_rotations = rotation_cfg.get("max_rotations_per_cycle", 3)
        min_held_days = rotation_cfg.get("min_held_days_before_rotation", 5)
        max_loss_pct = rotation_cfg.get("max_unrealized_loss_pct_for_rotation", -15)

        # Get held score map from Layer 1 (StockScore objects keyed by ticker)
        held_score_map = risk_layer_output.get("held_score_map", {})
        if not held_score_map or state.positions.empty:
            return {"rotation_sells": [], "rotation_buys": []}

        # Tickers already flagged for sell by Layer 1 — don't double-sell
        already_selling = {sp.ticker for sp in risk_layer_output.get("sell_proposals", [])}

        today = date.today()

        # Build eligible held positions
        eligible_held = []
        for _, pos in state.positions.iterrows():
            ticker = pos["ticker"]
            if ticker in already_selling:
                continue
            if ticker not in held_score_map:
                continue

            # Check minimum hold duration
            try:
                entry_date = date.fromisoformat(str(pos["entry_date"])[:10])
                days_held = (today - entry_date).days
            except Exception as e:
                print(f"Warning: failed to parse entry date: {e}")
                days_held = 0
            if days_held < min_held_days:
                continue

            # Don't lock in large losses
            unrealized_pct = float(pos.get("unrealized_pnl_pct", 0))
            if unrealized_pct < max_loss_pct:
                continue

            held_score = held_score_map[ticker].composite_score
            current_price = state.price_cache.get(ticker, float(pos.get("current_price", 0)))
            eligible_held.append({
                "ticker": ticker,
                "shares": int(pos["shares"]),
                "current_price": current_price,
                "composite_score": held_score,
                "stop_loss": float(pos.get("stop_loss", 0)),
                "take_profit": float(pos.get("take_profit", 0)),
            })

        if not eligible_held:
            return {"rotation_sells": [], "rotation_buys": []}

        # Sort held by score ascending (worst first)
        eligible_held.sort(key=lambda x: x["composite_score"])

        # Sort candidates by composite_score descending (best first)
        sorted_candidates = sorted(
            conviction_scores.values(),
            key=lambda c: c.composite_score,
            reverse=True
        )

        rotation_sells = []
        rotation_buys = []
        used_buy_tickers = set()
        used_sell_tickers = set()

        for held in eligible_held:
            if len(rotation_sells) >= max_rotations:
                break

            held_score = held["composite_score"]

            # Find best candidate with sufficient gap
            best_candidate = None
            for candidate in sorted_candidates:
                if candidate.ticker in used_buy_tickers:
                    continue
                gap = candidate.composite_score - held_score
                if gap >= min_gap:
                    best_candidate = candidate
                    break

            if best_candidate is None:
                continue

            gap = best_candidate.composite_score - held_score
            sell_ticker = held["ticker"]
            buy_ticker = best_candidate.ticker

            # Build sell proposal
            sell_reason = (
                f"ROTATION: Upgrading to {buy_ticker} "
                f"(score gap +{gap:.0f}: {held_score:.0f} → {best_candidate.composite_score:.0f})"
            )
            sell_proposal = SellProposal(
                ticker=sell_ticker,
                shares=held["shares"],
                current_price=held["current_price"],
                reason=sell_reason,
                urgency_level=UrgencyLevel.LOW,
                urgency_score=35,
                stop_loss=held["stop_loss"],
                take_profit=held["take_profit"],
            )

            # Size the buy from sell proceeds
            sell_proceeds = held["shares"] * held["current_price"]
            buy_price = price_map.get(buy_ticker) or state.price_cache.get(buy_ticker)
            if not buy_price or buy_price <= 0:
                continue

            # Conviction-based size (capped by sell proceeds)
            if best_candidate.final_conviction >= 80:
                base_size_pct = self.position_sizing["high_conviction_pct"]
            elif best_candidate.final_conviction >= 70:
                base_size_pct = self.position_sizing["medium_conviction_pct"]
            else:
                base_size_pct = self.position_sizing["low_conviction_pct"]

            conviction_value = state.total_equity * (base_size_pct / 100.0)
            position_value = min(conviction_value, sell_proceeds)

            min_notional = max(buy_price * 5, 250.0)  # at least 5 shares or $250
            if position_value < min_notional:
                continue

            buy_shares = int(position_value / buy_price)
            if buy_shares < 1:
                continue

            total_value = buy_shares * buy_price

            # Build buy rationale
            base_rationale = self._build_rationale(best_candidate, base_size_pct, state.regime)
            buy_rationale = f"{base_rationale} | ROTATION from {sell_ticker} (+{gap:.0f} score upgrade)"

            buy_proposal = BuyProposal(
                ticker=buy_ticker,
                shares=buy_shares,
                price=buy_price,
                total_value=total_value,
                conviction_score=best_candidate,
                position_size_pct=round(base_size_pct, 2),
                rationale=buy_rationale,
                social_signal=social_signals.get(buy_ticker) if social_signals else None,
            )

            rotation_sells.append(sell_proposal)
            rotation_buys.append(buy_proposal)
            used_sell_tickers.add(sell_ticker)
            used_buy_tickers.add(buy_ticker)

        return {"rotation_sells": rotation_sells, "rotation_buys": rotation_buys}

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
