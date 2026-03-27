#!/usr/bin/env python3
"""
Intelligent Stock Picker for GScott.

# ── LEGACY PATH ──────────────────────────────────────────────────────────────
# This script is only used when UNIFIED_MODE=false in run_daily.sh.
# In production, the cron pipeline always uses unified_analysis.py directly.
# Kept as a valid fallback for no-API-key environments.
# ─────────────────────────────────────────────────────────────────────────────

Enhanced picking logic with:
- Multi-factor scoring with regime-adaptive weights
- Market regime awareness (reduce/skip buying in bear markets)
- Volatility-adjusted position sizing
- Stop loss and take profit levels set at entry
- Portfolio limit enforcement

Usage: python scripts/pick_from_watchlist.py
"""

import json
import uuid
from datetime import date, datetime

import pandas as pd

from schema import Action, Reason
from risk_manager import RiskManager
from stock_scorer import StockScorer
from market_regime import MarketRegime, get_position_size_multiplier
from capital_preservation import get_preservation_status
from explainability import RationaleGenerator, save_rationale
from data_files import get_mode_indicator
from portfolio_state import (
    load_portfolio_state,
    load_watchlist,
    save_transactions_batch,
    update_position,
    save_positions,
)


def record_buy_transaction(
    ticker: str,
    shares: int,
    price: float,
    stop_loss: float,
    take_profit: float,
    regime: MarketRegime = None,
    composite_score: float = 0.0,
    factor_scores: dict = None,
    signal_rank: int = 0,
) -> dict:
    """Create a BUY transaction record with explainability data."""
    return {
        "transaction_id": str(uuid.uuid4())[:8],
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "ticker": ticker,
        "action": Action.BUY,
        "shares": shares,
        "price": round(price, 2),
        "total_value": round(shares * price, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "reason": Reason.SIGNAL,
        # Explainability columns
        "regime_at_entry": regime.value if regime else "",
        "composite_score": round(composite_score, 1),
        "factor_scores": json.dumps(factor_scores) if factor_scores else "",
        "signal_rank": signal_rank,
    }


def main(portfolio_id: str = None):
    mode_indicator = get_mode_indicator()
    print(f"\n─── Intelligent Stock Picker {mode_indicator} ───\n")

    # Step 1: Load portfolio state (includes regime detection)
    print("Step 1: Loading portfolio state and analyzing regime...")
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    config = state.config
    regime = state.regime
    regime_multiplier = get_position_size_multiplier(regime)

    regime_emoji = {"BULL": "🐂", "BEAR": "🐻", "SIDEWAYS": "↔️", "UNKNOWN": "❓"}
    print(f"  Market regime: {regime_emoji.get(regime.value, '')} {regime.value}")
    print(f"  Position size multiplier: {regime_multiplier:.0%}")

    if regime == MarketRegime.BEAR:
        print("\n  ⚠️  Bear market detected - skipping new buys")
        print("─" * 40)
        return

    # Step 1b: Check capital preservation mode
    preservation = get_preservation_status()
    if preservation.active:
        print(f"\n  ⚠️  CAPITAL PRESERVATION MODE ACTIVE")
        for reason in preservation.trigger_reasons:
            print(f"      - {reason}")

        if preservation.halt_new_buys:
            print("\n  🛑 New buys halted - protecting capital")
            print("─" * 40)
            return

        # Show position size reduction if not halting
        if preservation.position_size_multiplier < 1.0:
            print(f"      Position sizes reduced to {preservation.position_size_multiplier:.0%}")

    # Step 2: Check portfolio state
    print("\nStep 2: Checking portfolio state...")
    cash = state.cash
    current_tickers = state.positions["ticker"].tolist() if not state.positions.empty else []

    print(f"  Cash available: ${cash:,.2f}")
    print(f"  Current positions: {state.num_positions}")
    print(f"  Total equity: ${state.total_equity:,.2f}")

    # Check if max positions reached
    max_positions = config.get("max_positions", 15)
    if state.num_positions >= max_positions:
        print(f"\n  ⚠️  Max positions ({max_positions}) reached - skipping new buys")
        print("─" * 40)
        return

    # Step 3: Score watchlist candidates
    print("\nStep 3: Scoring watchlist candidates...")
    all_tickers = load_watchlist(portfolio_id=state.portfolio_id)

    # Filter out tickers we already own
    candidates = [t for t in all_tickers if t not in current_tickers]
    print(f"  Candidates to score: {len(candidates)}")

    if not candidates:
        print("  No new candidates available")
        print("─" * 40)
        return

    scorer = StockScorer(regime=regime)
    min_score = scorer.get_min_score_threshold()
    scores = scorer.get_top_picks(candidates, n=10, min_score=min_score)

    print(f"  Using {regime.value.upper()} regime weights")
    print(f"  Minimum score threshold: {min_score}")

    if not scores:
        print("  ⚠️  No candidates met minimum score threshold")
        print("─" * 40)
        return

    print(f"  Top candidates scored: {len(scores)}")
    for s in scores[:5]:
        print(f"    {s.ticker}: {s.composite_score:.1f} (${s.current_price:.2f})")

    # Step 4: Execute buys for top picks
    print("\nStep 4: Executing buys...")
    rm = RiskManager()
    risk_pct = config.get("risk_per_trade_pct", 10.0) / 100

    # Apply both regime and preservation multipliers
    preservation_multiplier = preservation.position_size_multiplier if preservation.active else 1.0
    combined_multiplier = regime_multiplier * preservation_multiplier
    risk_capital = cash * risk_pct * combined_multiplier

    if combined_multiplier < 1.0:
        print(f"  Position size adjusted: {combined_multiplier:.0%} of normal")

    new_transactions = []
    buys_executed = 0
    total_spent = 0
    rationale_generator = RationaleGenerator()
    active_weights = scorer.get_active_weights()

    for rank, score in enumerate(scores, 1):
        # Check cash
        if cash < 100:  # Minimum $100 to trade
            print("  Insufficient cash remaining")
            break

        # Check position limits
        allowed, reason = rm.check_portfolio_limits(
            state.positions, score.ticker, risk_capital, state.total_equity
        )
        if not allowed:
            print(f"  Skipping {score.ticker}: {reason}")
            continue

        # RSI hard filter - never buy extremely overbought stocks
        rsi_config = config.get("scoring", {}).get("rsi", {})
        rsi_hard_filter = rsi_config.get("hard_filter_above", 85)
        if score.rsi_value > rsi_hard_filter:
            print(f"  Skipping {score.ticker}: RSI {score.rsi_value:.0f} > {rsi_hard_filter} (hard filter)")
            continue

        # Get factor scores for position sizing confidence
        factor_scores = {
            "price_momentum": score.price_momentum_score,
            "earnings_growth": score.earnings_growth_score,
            "quality": score.quality_score,
            "volume": score.volume_score,
            "volatility": score.volatility_score,
            "value_timing": score.value_timing_score,
        }

        # Calculate position size with confidence multiplier
        shares = rm.calculate_position_size_with_confidence(
            price=score.current_price,
            cash=cash,
            factor_scores=factor_scores,
            volatility=score.atr_pct / 100 if score.atr_pct > 0 else None,
            regime=regime.value if regime else None,
            regime_multiplier=combined_multiplier,
        )

        if shares < 1:
            continue

        total_cost = shares * score.current_price
        if total_cost > cash:
            continue

        # Calculate stop loss and take profit
        stop_loss = rm.calculate_stop_loss_price(score.current_price)
        take_profit = rm.calculate_take_profit_price(score.current_price)

        # Record transaction with explainability data
        transaction = record_buy_transaction(
            ticker=score.ticker,
            shares=shares,
            price=score.current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            regime=regime,
            composite_score=score.composite_score,
            factor_scores=factor_scores,
            signal_rank=rank,
        )
        new_transactions.append(transaction)

        # Generate and save trade rationale
        rationale = rationale_generator.generate_buy_rationale(
            transaction_id=transaction["transaction_id"],
            ticker=score.ticker,
            composite_score=score.composite_score,
            factor_scores=factor_scores,
            weights=active_weights,
            regime=regime,
            signal_rank=rank,
            stop_loss_pct=config.get("default_stop_loss_pct", 8.0),
            take_profit_pct=config.get("default_take_profit_pct", 20.0),
        )
        save_rationale(rationale)

        # Update state with new position
        state = update_position(
            state,
            score.ticker,
            shares,
            score.current_price,
            stop_loss,
            take_profit,
        )

        # Update cash tracking
        cash -= total_cost
        total_spent += total_cost
        buys_executed += 1

        print(f"  ✅ BUY {score.ticker}: {shares} shares @ ${score.current_price:.2f}")
        print(f"      Stop: ${stop_loss:.2f} | Target: ${take_profit:.2f}")

    # Step 5: Save changes
    if new_transactions:
        print(f"\nStep 5: Saving changes... {get_mode_indicator()}")
        state = save_transactions_batch(state, new_transactions)
        save_positions(state)
        print(f"  Saved {len(new_transactions)} transactions")

    # Summary
    print("\n" + "─" * 40)
    print(f"✅ Picks complete for {date.today().isoformat()}")
    print(f"   Buys executed: {buys_executed}")
    print(f"   Total spent:   ${total_spent:,.2f}")
    print(f"   Cash remaining: ${cash:,.2f}")
    print("─" * 40)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Intelligent Stock Picker")
    parser.add_argument("--portfolio", default=None, help="Portfolio ID (default: registry default)")
    args = parser.parse_args()

    main(portfolio_id=args.portfolio)
