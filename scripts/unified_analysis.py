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
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional
import uuid

import pandas as pd

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from schema import TRANSACTION_COLUMNS, POSITION_COLUMNS, Action, Reason
from stock_scorer import StockScorer
from market_regime import get_market_regime, get_position_size_multiplier, MarketRegime, get_regime_analysis
from risk_manager import RiskManager
from capital_preservation import get_preservation_status
from ai_review import (
    ProposedAction, ReviewedAction, ReviewDecision,
    review_proposed_actions, format_review_summary
)
from data_files import (
    get_positions_file, get_transactions_file, get_daily_snapshots_file,
    load_config as load_base_config, is_paper_mode, get_mode_indicator,
    DATA_DIR, get_watchlist_file
)

# ─── Configuration ────────────────────────────────────────────────────────────

CONFIG_PATH = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load configuration."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "starting_capital": 50000.0,
        "risk_per_trade_pct": 10.0,
        "max_positions": 15,
        "default_stop_loss_pct": 8.0,
        "default_take_profit_pct": 20.0,
    }


def load_watchlist() -> list:
    """Load tickers from watchlist."""
    watchlist_path = get_watchlist_file()
    if not watchlist_path.exists():
        return []

    with open(watchlist_path, "r") as f:
        watchlist = [json.loads(line) for line in f if line.strip()]

    return [item["ticker"] for item in watchlist]


def load_positions() -> pd.DataFrame:
    """Load current positions."""
    positions_file = get_positions_file()
    if not positions_file.exists():
        return pd.DataFrame(columns=POSITION_COLUMNS)
    return pd.read_csv(positions_file)


def load_transactions() -> pd.DataFrame:
    """Load transactions."""
    tx_file = get_transactions_file()
    if not tx_file.exists():
        return pd.DataFrame()
    return pd.read_csv(tx_file)


def calculate_cash(config: dict, transactions_df: pd.DataFrame) -> float:
    """Calculate available cash."""
    if transactions_df.empty:
        return config["starting_capital"]

    total_spent = transactions_df[transactions_df["action"] == "BUY"]["total_value"].sum()
    total_received = transactions_df[transactions_df["action"] == "SELL"]["total_value"].sum()

    return config["starting_capital"] - total_spent + total_received


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

    config = load_config()
    positions_df = load_positions()
    transactions_df = load_transactions()
    cash = calculate_cash(config, transactions_df)

    positions_value = positions_df["market_value"].sum() if not positions_df.empty else 0
    total_equity = positions_value + cash
    num_positions = len(positions_df)

    # Get market regime
    try:
        regime_analysis = get_regime_analysis()
        regime = regime_analysis.regime
        position_multiplier = regime_analysis.position_multiplier
    except:
        regime = MarketRegime.SIDEWAYS
        position_multiplier = 0.5

    print(f"Portfolio: ${total_equity:,.0f} | Cash: ${cash:,.0f} | Positions: {num_positions}")
    print(f"Market Regime: {regime.value} | Position Multiplier: {position_multiplier:.0%}")
    print()

    # Check preservation mode
    try:
        preservation = get_preservation_status()
        preservation_active = preservation.get("preservation_mode", False)
        if preservation_active:
            print("⚠️  CAPITAL PRESERVATION MODE ACTIVE - No new buys")
    except:
        preservation_active = False

    proposed_actions = []

    # ─── Step 1: Check Stop Loss / Take Profit Triggers ───────────────────────
    print("Checking stop loss / take profit triggers...")

    if not positions_df.empty:
        risk_manager = RiskManager()

        for _, pos in positions_df.iterrows():
            ticker = pos["ticker"]
            current_price = pos["current_price"]
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
    elif num_positions >= config.get("max_positions", 15):
        print(f"  ⚠️  At max positions ({num_positions}) - skipping new buys")
    else:
        watchlist = load_watchlist()
        current_tickers = set(positions_df["ticker"].tolist()) if not positions_df.empty else set()
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
            max_position_value = total_equity * risk_per_trade * position_multiplier
            stop_loss_pct = config.get("default_stop_loss_pct", 8.0) / 100
            take_profit_pct = config.get("default_take_profit_pct", 20.0) / 100

            slots_available = config.get("max_positions", 15) - num_positions
            remaining_cash = cash  # Track how much cash is left as we propose buys

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
        "total_equity": total_equity,
        "cash": cash,
        "num_positions": num_positions,
        "regime": regime.value,
        "win_rate": 0.5,  # Could calculate from transactions
        "positions": [
            {
                "ticker": pos["ticker"],
                "shares": pos["shares"],
                "pnl_pct": pos.get("unrealized_pnl_pct", 0),
                "weight": (pos["market_value"] / total_equity * 100) if total_equity > 0 else 0
            }
            for _, pos in positions_df.iterrows()
        ] if not positions_df.empty else []
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

    config = load_config()
    positions_df = load_positions()
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

        mod_note = " (MODIFIED)" if reviewed.decision == ReviewDecision.MODIFY else ""
        print(f"  ✅ {action.action_type} {action.ticker}: {shares} shares @ ${action.price:.2f}{mod_note}")
        print(f"     AI: {reviewed.ai_reasoning}")

    # Save transactions
    if transactions:
        tx_file = get_transactions_file()
        df_new = pd.DataFrame(transactions)

        if tx_file.exists():
            df_existing = pd.read_csv(tx_file)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_combined = df_new

        df_combined.to_csv(tx_file, index=False)

        # Update positions
        positions_file = get_positions_file()
        for tx in transactions:
            if tx["action"] == "BUY":
                # Add or update position
                if tx["ticker"] in positions_df["ticker"].values:
                    idx = positions_df[positions_df["ticker"] == tx["ticker"]].index[0]
                    existing_shares = positions_df.at[idx, "shares"]
                    existing_cost = positions_df.at[idx, "avg_cost_basis"]
                    new_shares = existing_shares + tx["shares"]
                    new_cost = ((existing_shares * existing_cost) + (tx["shares"] * tx["price"])) / new_shares
                    positions_df.at[idx, "shares"] = new_shares
                    positions_df.at[idx, "avg_cost_basis"] = round(new_cost, 2)
                    positions_df.at[idx, "current_price"] = tx["price"]
                    positions_df.at[idx, "market_value"] = round(new_shares * tx["price"], 2)
                    positions_df.at[idx, "stop_loss"] = tx["stop_loss"]
                    positions_df.at[idx, "take_profit"] = tx["take_profit"]
                else:
                    new_row = {
                        "ticker": tx["ticker"],
                        "shares": tx["shares"],
                        "avg_cost_basis": tx["price"],
                        "current_price": tx["price"],
                        "market_value": tx["total_value"],
                        "unrealized_pnl": 0.0,
                        "unrealized_pnl_pct": 0.0,
                        "stop_loss": tx["stop_loss"],
                        "take_profit": tx["take_profit"],
                        "entry_date": tx["date"],
                    }
                    positions_df = pd.concat([positions_df, pd.DataFrame([new_row])], ignore_index=True)

            elif tx["action"] == "SELL":
                # Remove position
                positions_df = positions_df[positions_df["ticker"] != tx["ticker"]]

        positions_df.to_csv(positions_file, index=False)

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
