#!/usr/bin/env python3
"""
Unified Analysis Engine - The single source of truth for trading decisions.

This module combines:
1. Quantitative scoring (momentum, volatility, volume, relative strength)
2. Stop loss/take profit trigger checking
3. AI review and reasoning
4. Safety rails enforcement

Output is a unified set of recommendations that can be executed.

Usage:
    from unified_analysis import run_unified_analysis, execute_approved_actions

    result = run_unified_analysis()
    # result contains proposed_buys, proposed_sells, all with AI review

    execute_approved_actions(result)
"""

import json
import uuid
from datetime import date, datetime

from schema import Action, Reason
from stock_scorer import StockScorer
from market_regime import MarketRegime, get_position_size_multiplier
from risk_manager import RiskManager
from capital_preservation import get_preservation_status
from ai_review import (
    ProposedAction, ReviewedAction, ReviewDecision,
    review_proposed_actions, format_review_summary
)
from post_mortem import PostMortemAnalyzer, save_post_mortem
from data_files import get_mode_indicator
from portfolio_state import (
    load_portfolio_state,
    load_watchlist,
    save_transactions_batch,
    update_position,
    remove_position,
    save_positions,
)


# ─── Unified Analysis ─────────────────────────────────────────────────────────

def run_unified_analysis(dry_run: bool = True) -> dict:
    """
    Run the complete unified analysis pipeline.

    Steps:
    1. Check stop loss / take profit triggers (sells)
    2. Score watchlist candidates (potential buys)
    3. AI reviews all proposed actions
    4. Return unified recommendations

    Args:
        dry_run: If True, don't execute - just return recommendations

    Returns:
        dict with keys:
            - proposed_sells: List of sell recommendations (stop/target triggers)
            - proposed_buys: List of buy recommendations (scored candidates)
            - reviewed_actions: All actions after AI review
            - summary: Human-readable summary
            - can_execute: Whether there are actions to execute
    """
    print(f"\n{'='*60}")
    print(f"UNIFIED ANALYSIS - {get_mode_indicator()}")
    print(f"{'='*60}\n")

    # Single state load replaces 5 separate loads
    state = load_portfolio_state(fetch_prices=True)
    config = state.config
    regime = state.regime
    position_multiplier = get_position_size_multiplier(regime)

    print(f"Portfolio: ${state.total_equity:,.0f} | Cash: ${state.cash:,.0f} | Positions: {state.num_positions}")
    print(f"Market Regime: {regime.value} | Position Multiplier: {position_multiplier:.0%}")
    print()

    # Check preservation mode
    try:
        preservation = get_preservation_status()
        preservation_active = preservation.active
        if preservation_active:
            print("⚠️  CAPITAL PRESERVATION MODE ACTIVE - No new buys")
    except Exception as e:
        print(f"  [WARN] Capital preservation check failed: {e}")
        print(f"  [WARN] Defaulting to preservation_active=True (safe default)")
        preservation_active = True  # Fail safe: halt buys on error

    proposed_actions = []

    # ─── Step 1: Check Stop Loss / Take Profit Triggers ───────────────────────
    print("Checking stop loss / take profit triggers...")

    if not state.positions.empty:
        risk_manager = RiskManager()

        for _, pos in state.positions.iterrows():
            ticker = pos["ticker"]
            current_price = state.price_cache.get(ticker, pos["current_price"])
            stop_loss = pos.get("stop_loss", 0)
            take_profit = pos.get("take_profit", 0)
            shares = pos["shares"]

            # Check stop loss
            if stop_loss > 0 and current_price <= stop_loss:
                proposed_actions.append(ProposedAction(
                    action_type="SELL",
                    ticker=ticker,
                    shares=int(shares),
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    quant_score=0,  # N/A for sells
                    factor_scores={},
                    regime=regime.value,
                    reason=f"STOP LOSS triggered: ${current_price:.2f} <= ${stop_loss:.2f}"
                ))
                print(f"  🔴 {ticker}: Stop loss triggered at ${current_price:.2f}")

            # Check take profit
            elif take_profit > 0 and current_price >= take_profit:
                proposed_actions.append(ProposedAction(
                    action_type="SELL",
                    ticker=ticker,
                    shares=int(shares),
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    quant_score=0,
                    factor_scores={},
                    regime=regime.value,
                    reason=f"TAKE PROFIT triggered: ${current_price:.2f} >= ${take_profit:.2f}"
                ))
                print(f"  🟢 {ticker}: Take profit triggered at ${current_price:.2f}")

    num_sells = len([a for a in proposed_actions if a.action_type == "SELL"])
    print(f"  Found {num_sells} sell trigger(s)")
    print()

    # ─── Step 2: Score Watchlist Candidates ───────────────────────────────────
    print("Scoring watchlist candidates...")

    # Skip buying in bear markets or preservation mode
    if regime == MarketRegime.BEAR:
        print("  ⚠️  Bear market - skipping new buys")
    elif preservation_active:
        print("  ⚠️  Preservation mode - skipping new buys")
    elif state.num_positions >= config.get("max_positions", 15):
        print(f"  ⚠️  At max positions ({state.num_positions}) - skipping new buys")
    else:
        watchlist = load_watchlist()
        current_tickers = set(state.positions["ticker"].tolist()) if not state.positions.empty else set()
        candidates = [t for t in watchlist if t not in current_tickers]

        if candidates:
            scorer = StockScorer()
            scored_results = scorer.score_watchlist(candidates)
            # Convert StockScore objects to dicts with factor_scores built from individual attributes
            scored = []
            for s in scored_results:
                if s:
                    scored.append({
                        "ticker": s.ticker,
                        "composite_score": s.composite_score,
                        "current_price": s.current_price,
                        "factor_scores": {
                            "momentum": s.momentum_score,
                            "volatility": s.volatility_score,
                            "volume": s.volume_score,
                            "relative_strength": s.relative_strength_score,
                            "mean_reversion": s.mean_reversion_score,
                            "rsi": s.rsi_score,
                        }
                    })

            # Filter to top candidates with score >= 60
            top_candidates = [s for s in scored if s.get("composite_score", 0) >= 60]
            top_candidates = sorted(top_candidates, key=lambda x: x.get("composite_score", 0), reverse=True)

            # Calculate position size
            risk_per_trade = config.get("risk_per_trade_pct", 10.0) / 100
            max_position_value = state.total_equity * risk_per_trade * position_multiplier
            stop_loss_pct = config.get("default_stop_loss_pct", 8.0) / 100
            take_profit_pct = config.get("default_take_profit_pct", 20.0) / 100

            slots_available = config.get("max_positions", 15) - state.num_positions
            remaining_cash = state.cash  # Track how much cash is left as we propose buys

            for i, candidate in enumerate(top_candidates[:slots_available]):
                ticker = candidate["ticker"]
                price = candidate.get("current_price", 0)
                score = candidate.get("composite_score", 0)
                factor_scores = candidate.get("factor_scores", {})

                if price <= 0:
                    continue

                # Calculate position size (capped by remaining cash)
                position_value = min(max_position_value, remaining_cash)
                shares = int(position_value / price)
                if shares < 1:
                    print(f"  ⏸️ Skipping {ticker} - insufficient cash (${remaining_cash:.0f} remaining)")
                    continue

                actual_cost = shares * price
                if actual_cost > remaining_cash:
                    # Reduce shares to fit remaining cash
                    shares = int(remaining_cash / price)
                    if shares < 1:
                        continue
                    actual_cost = shares * price

                stop_loss = round(price * (1 - stop_loss_pct), 2)
                take_profit = round(price * (1 + take_profit_pct), 2)

                proposed_actions.append(ProposedAction(
                    action_type="BUY",
                    ticker=ticker,
                    shares=shares,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    quant_score=score,
                    factor_scores=factor_scores,
                    regime=regime.value,
                    reason=f"Quant score {score:.0f}/100 - Rank #{i+1}"
                ))
                remaining_cash -= actual_cost
                print(f"  📈 {ticker}: Score {score:.0f}, {shares} shares @ ${price:.2f} (${actual_cost:.0f}, ${remaining_cash:.0f} remaining)")

    num_buys = len([a for a in proposed_actions if a.action_type == "BUY"])
    print(f"  Found {num_buys} buy candidate(s)")
    print()

    # ─── Step 3: AI Review ────────────────────────────────────────────────────
    print("AI reviewing proposed actions...")

    # Build portfolio context for AI
    portfolio_context = {
        "total_equity": state.total_equity,
        "cash": state.cash,
        "num_positions": state.num_positions,
        "regime": regime.value,
        "win_rate": 0.5,  # Could calculate from transactions
        "positions": [
            {
                "ticker": pos["ticker"],
                "shares": pos["shares"],
                "pnl_pct": pos.get("unrealized_pnl_pct", 0),
                "weight": (pos["market_value"] / state.total_equity * 100) if state.total_equity > 0 else 0
            }
            for _, pos in state.positions.iterrows()
        ] if not state.positions.empty else []
    }

    reviewed_actions = review_proposed_actions(proposed_actions, portfolio_context)
    print(format_review_summary(reviewed_actions))

    # ─── Build Result ─────────────────────────────────────────────────────────
    approved = [r for r in reviewed_actions if r.decision == ReviewDecision.APPROVE]
    modified = [r for r in reviewed_actions if r.decision == ReviewDecision.MODIFY]
    vetoed = [r for r in reviewed_actions if r.decision == ReviewDecision.VETO]

    result = {
        "proposed_actions": proposed_actions,
        "reviewed_actions": reviewed_actions,
        "approved": approved,
        "modified": modified,
        "vetoed": vetoed,
        "summary": {
            "total_proposed": len(proposed_actions),
            "approved": len(approved),
            "modified": len(modified),
            "vetoed": len(vetoed),
            "can_execute": len(approved) + len(modified) > 0,
        },
        "portfolio_context": portfolio_context,
        "regime": regime.value,
        "timestamp": datetime.now().isoformat(),
    }

    return result


def execute_approved_actions(analysis_result: dict) -> dict:
    """
    Execute the approved and modified actions from unified analysis.

    Returns:
        dict with execution results
    """
    approved = analysis_result.get("approved", [])
    modified = analysis_result.get("modified", [])

    actions_to_execute = approved + modified
    if not actions_to_execute:
        return {"executed": 0, "message": "No actions to execute"}

    # Load fresh state for execution
    state = load_portfolio_state(fetch_prices=False)
    transactions = []

    print(f"\n{'='*60}")
    print("EXECUTING APPROVED ACTIONS")
    print(f"{'='*60}\n")

    for reviewed in actions_to_execute:
        action = reviewed.original

        # Apply modifications if any
        shares = reviewed.modified_shares or action.shares
        stop_loss = reviewed.modified_stop or action.stop_loss
        take_profit = reviewed.modified_target or action.take_profit

        tx = {
            "transaction_id": str(uuid.uuid4())[:8],
            "date": date.today().isoformat(),
            "ticker": action.ticker,
            "action": action.action_type,
            "shares": shares,
            "price": round(action.price, 2),
            "total_value": round(shares * action.price, 2),
            "stop_loss": round(stop_loss, 2) if action.action_type == "BUY" else "",
            "take_profit": round(take_profit, 2) if action.action_type == "BUY" else "",
            "reason": "SIGNAL" if action.action_type == "BUY" else (
                "STOP_LOSS" if "STOP LOSS" in action.reason else
                "TAKE_PROFIT" if "TAKE PROFIT" in action.reason else "MANUAL"
            ),
            "regime_at_entry": action.regime if action.action_type == "BUY" else "",
            "composite_score": action.quant_score if action.action_type == "BUY" else "",
            "factor_scores": json.dumps(action.factor_scores) if action.action_type == "BUY" else "",
            "signal_rank": "",
        }
        transactions.append(tx)

        # Update positions
        if action.action_type == "BUY":
            state = update_position(state, action.ticker, shares, action.price, stop_loss, take_profit)
        elif action.action_type == "SELL":
            state = remove_position(state, action.ticker)

        mod_note = " (MODIFIED)" if reviewed.decision == ReviewDecision.MODIFY else ""
        print(f"  ✅ {action.action_type} {action.ticker}: {shares} shares @ ${action.price:.2f}{mod_note}")
        print(f"     AI: {reviewed.ai_reasoning}")

    # Save everything at once
    if transactions:
        state = save_transactions_batch(state, transactions)
        save_positions(state)

    # Generate post-mortems for sells
    sell_data = [
        (reviewed, tx)
        for reviewed, tx in zip(actions_to_execute, transactions)
        if reviewed.original.action_type == "SELL"
    ]
    if sell_data:
        print("\n  Generating post-mortems...")
        try:
            analyzer = PostMortemAnalyzer()
            for reviewed, sell_tx in sell_data:
                ticker = sell_tx["ticker"]
                buy_txns = state.transactions[
                    (state.transactions["ticker"] == ticker) &
                    (state.transactions["action"] == "BUY")
                ]
                if not buy_txns.empty:
                    buy_txn = buy_txns.iloc[-1].to_dict()
                    pm = analyzer.analyze_trade(sell_tx, buy_txn, analysis_result.get("regime", "UNKNOWN"))
                    save_post_mortem(pm)
                    print(f"    📝 {ticker}: {pm.summary}")
        except Exception as e:
            print(f"    [warn] Post-mortem generation failed: {e}")

    print(f"\n✅ Executed {len(transactions)} action(s)")
    return {"executed": len(transactions), "transactions": transactions}


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Unified Analysis Engine")
    parser.add_argument("--execute", action="store_true", help="Execute approved actions")
    parser.add_argument("--dry-run", action="store_true", help="Show recommendations without executing")
    args = parser.parse_args()

    result = run_unified_analysis(dry_run=not args.execute)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total Proposed: {result['summary']['total_proposed']}")
    print(f"Approved: {result['summary']['approved']}")
    print(f"Modified: {result['summary']['modified']}")
    print(f"Vetoed: {result['summary']['vetoed']}")
    print(f"Can Execute: {result['summary']['can_execute']}")

    if args.execute and result['summary']['can_execute']:
        execute_approved_actions(result)
