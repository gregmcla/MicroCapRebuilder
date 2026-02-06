#!/usr/bin/env python3
"""
Intelligence Action Executor

Executes the actions recommended by the Portfolio Intelligence engine.
This script takes AI recommendations and translates them into actual trades.

Supports:
- BUY: Open new position
- SELL: Close entire position
- TRIM: Partial sell (reduce position by X%)
- ADD: Increase existing position
- ADJUST_STOP: Modify stop loss level
- ADJUST_TARGET: Modify take profit level
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
import pandas as pd
import yfinance as yf

from data_files import (
    get_positions_file, get_transactions_file, get_config_file,
    is_paper_mode
)
from schema import TRANSACTION_COLUMNS, POSITION_COLUMNS, Action, Reason

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
LOGS_DIR = SCRIPT_DIR.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def load_config() -> dict:
    """Load configuration."""
    config_file = get_config_file()
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    return {"starting_capital": 50000.0}


def load_positions() -> pd.DataFrame:
    """Load current positions."""
    pos_file = get_positions_file()
    if not pos_file.exists():
        return pd.DataFrame(columns=POSITION_COLUMNS)
    return pd.read_csv(pos_file)


def save_positions(positions: pd.DataFrame):
    """Save positions to file."""
    pos_file = get_positions_file()
    positions.to_csv(pos_file, index=False)


def load_transactions() -> pd.DataFrame:
    """Load transactions."""
    tx_file = get_transactions_file()
    if not tx_file.exists():
        return pd.DataFrame(columns=TRANSACTION_COLUMNS)
    return pd.read_csv(tx_file)


def save_transactions(transactions: pd.DataFrame):
    """Save transactions to file."""
    tx_file = get_transactions_file()
    transactions.to_csv(tx_file, index=False)


def get_current_price(ticker: str) -> float:
    """Fetch current price for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if not data.empty:
            return data["Close"].iloc[-1]
    except Exception:
        pass
    return 0.0


def calculate_cash(config: dict, transactions: pd.DataFrame) -> float:
    """Calculate current cash from transactions."""
    starting = config.get("starting_capital", 50000.0)
    if transactions.empty:
        return starting

    cash = starting
    for _, tx in transactions.iterrows():
        if tx["action"] in ["BUY", "ADD"]:
            cash -= tx["total_value"]
        elif tx["action"] in ["SELL", "TRIM"]:
            cash += tx["total_value"]
    return cash


def record_transaction(
    transactions: pd.DataFrame,
    ticker: str,
    action: str,
    shares: int,
    price: float,
    stop_loss: float = None,
    take_profit: float = None,
    reason: str = Reason.INTELLIGENCE,
) -> pd.DataFrame:
    """Record a new transaction."""

    tx_id = str(uuid.uuid4())[:8]
    today = datetime.now().strftime("%Y-%m-%d")

    new_tx = {
        "transaction_id": tx_id,
        "date": today,
        "ticker": ticker,
        "action": action,
        "shares": shares,
        "price": price,
        "total_value": round(shares * price, 2),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "reason": reason,
    }

    # Add optional explainability columns if they exist
    for col in TRANSACTION_COLUMNS:
        if col not in new_tx:
            new_tx[col] = None

    return pd.concat([transactions, pd.DataFrame([new_tx])], ignore_index=True)


def execute_buy(
    action: dict,
    positions: pd.DataFrame,
    transactions: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Execute a BUY action."""

    ticker = action["ticker"]
    amount = action.get("amount", 0)

    if amount <= 0:
        return positions, transactions, {"status": "SKIPPED", "reason": "Invalid amount"}

    # Get current price
    price = get_current_price(ticker)
    if price <= 0:
        return positions, transactions, {"status": "FAILED", "reason": f"Could not get price for {ticker}"}

    # Check cash
    cash = calculate_cash(config, transactions)
    if amount > cash * 0.9:  # Leave 10% buffer
        return positions, transactions, {"status": "FAILED", "reason": "Insufficient cash"}

    # Calculate shares
    shares = int(amount / price)
    if shares <= 0:
        return positions, transactions, {"status": "SKIPPED", "reason": "Amount too small for 1 share"}

    # Calculate stop/target
    stop_pct = config.get("default_stop_loss_pct", 8.0)
    target_pct = config.get("default_take_profit_pct", 20.0)
    stop_loss = round(price * (1 - stop_pct / 100), 2)
    take_profit = round(price * (1 + target_pct / 100), 2)

    # Record transaction
    transactions = record_transaction(
        transactions, ticker, Action.BUY, shares, price,
        stop_loss, take_profit, Reason.INTELLIGENCE
    )

    # Update positions
    if ticker in positions["ticker"].values:
        # Add to existing position
        idx = positions[positions["ticker"] == ticker].index[0]
        old_shares = positions.loc[idx, "shares"]
        old_cost = positions.loc[idx, "avg_cost_basis"]
        new_shares = old_shares + shares
        new_cost = (old_shares * old_cost + shares * price) / new_shares
        positions.loc[idx, "shares"] = new_shares
        positions.loc[idx, "avg_cost_basis"] = round(new_cost, 2)
        positions.loc[idx, "current_price"] = price
        positions.loc[idx, "market_value"] = round(new_shares * price, 2)
    else:
        # New position
        new_pos = {
            "ticker": ticker,
            "shares": shares,
            "avg_cost_basis": price,
            "current_price": price,
            "market_value": round(shares * price, 2),
            "unrealized_pnl": 0,
            "unrealized_pnl_pct": 0,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "entry_date": datetime.now().strftime("%Y-%m-%d"),
        }
        positions = pd.concat([positions, pd.DataFrame([new_pos])], ignore_index=True)

    return positions, transactions, {
        "status": "EXECUTED",
        "shares": shares,
        "price": price,
        "total": round(shares * price, 2),
    }


def execute_sell(
    action: dict,
    positions: pd.DataFrame,
    transactions: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Execute a SELL action (close entire position)."""

    ticker = action["ticker"]

    # Find position
    if ticker not in positions["ticker"].values:
        return positions, transactions, {"status": "SKIPPED", "reason": f"No position in {ticker}"}

    pos = positions[positions["ticker"] == ticker].iloc[0]
    shares = int(pos["shares"])

    # Get current price
    price = get_current_price(ticker)
    if price <= 0:
        return positions, transactions, {"status": "FAILED", "reason": f"Could not get price for {ticker}"}

    # Record transaction
    transactions = record_transaction(
        transactions, ticker, Action.SELL, shares, price,
        reason=Reason.INTELLIGENCE
    )

    # Remove position
    positions = positions[positions["ticker"] != ticker].reset_index(drop=True)

    # Calculate P&L
    cost_basis = pos["avg_cost_basis"]
    pnl = (price - cost_basis) * shares
    pnl_pct = (price / cost_basis - 1) * 100 if cost_basis > 0 else 0

    return positions, transactions, {
        "status": "EXECUTED",
        "shares": shares,
        "price": price,
        "total": round(shares * price, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
    }


def execute_trim(
    action: dict,
    positions: pd.DataFrame,
    transactions: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Execute a TRIM action (partial sell)."""

    ticker = action["ticker"]
    trim_pct = action.get("percent", 0)

    if trim_pct <= 0 or trim_pct > 100:
        return positions, transactions, {"status": "SKIPPED", "reason": "Invalid trim percentage"}

    # Find position
    if ticker not in positions["ticker"].values:
        return positions, transactions, {"status": "SKIPPED", "reason": f"No position in {ticker}"}

    pos = positions[positions["ticker"] == ticker].iloc[0]
    idx = positions[positions["ticker"] == ticker].index[0]
    total_shares = int(pos["shares"])

    # Calculate shares to sell
    shares_to_sell = int(total_shares * trim_pct / 100)
    if shares_to_sell <= 0:
        return positions, transactions, {"status": "SKIPPED", "reason": "Trim too small"}

    # Get current price
    price = get_current_price(ticker)
    if price <= 0:
        return positions, transactions, {"status": "FAILED", "reason": f"Could not get price for {ticker}"}

    # Record transaction
    transactions = record_transaction(
        transactions, ticker, Action.SELL, shares_to_sell, price,
        reason=Reason.TRIM_PROFIT
    )

    # Update position
    remaining_shares = total_shares - shares_to_sell
    if remaining_shares <= 0:
        # Sold everything
        positions = positions[positions["ticker"] != ticker].reset_index(drop=True)
    else:
        positions.loc[idx, "shares"] = remaining_shares
        positions.loc[idx, "current_price"] = price
        positions.loc[idx, "market_value"] = round(remaining_shares * price, 2)
        pnl = (price - pos["avg_cost_basis"]) * remaining_shares
        positions.loc[idx, "unrealized_pnl"] = round(pnl, 2)
        positions.loc[idx, "unrealized_pnl_pct"] = round(
            (price / pos["avg_cost_basis"] - 1) * 100 if pos["avg_cost_basis"] > 0 else 0, 2
        )

    # Calculate realized P&L
    cost_basis = pos["avg_cost_basis"]
    pnl = (price - cost_basis) * shares_to_sell

    return positions, transactions, {
        "status": "EXECUTED",
        "shares_sold": shares_to_sell,
        "shares_remaining": remaining_shares,
        "price": price,
        "total": round(shares_to_sell * price, 2),
        "pnl": round(pnl, 2),
    }


def execute_add(
    action: dict,
    positions: pd.DataFrame,
    transactions: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Execute an ADD action (increase existing position)."""

    ticker = action["ticker"]

    # Find position
    if ticker not in positions["ticker"].values:
        return positions, transactions, {"status": "SKIPPED", "reason": f"No position in {ticker} to add to"}

    # Delegate to execute_buy (same logic)
    return execute_buy(action, positions, transactions, config)


def execute_adjust_stop(
    action: dict,
    positions: pd.DataFrame,
    transactions: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Execute an ADJUST_STOP action."""

    ticker = action["ticker"]
    new_stop = action.get("price", 0)

    if new_stop <= 0:
        return positions, transactions, {"status": "SKIPPED", "reason": "Invalid stop price"}

    # Find position
    if ticker not in positions["ticker"].values:
        return positions, transactions, {"status": "SKIPPED", "reason": f"No position in {ticker}"}

    idx = positions[positions["ticker"] == ticker].index[0]
    old_stop = positions.loc[idx, "stop_loss"]

    # Update stop
    positions.loc[idx, "stop_loss"] = new_stop

    return positions, transactions, {
        "status": "EXECUTED",
        "old_stop": old_stop,
        "new_stop": new_stop,
    }


def execute_adjust_target(
    action: dict,
    positions: pd.DataFrame,
    transactions: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Execute an ADJUST_TARGET action."""

    ticker = action["ticker"]
    new_target = action.get("price", 0)

    if new_target <= 0:
        return positions, transactions, {"status": "SKIPPED", "reason": "Invalid target price"}

    # Find position
    if ticker not in positions["ticker"].values:
        return positions, transactions, {"status": "SKIPPED", "reason": f"No position in {ticker}"}

    idx = positions[positions["ticker"] == ticker].index[0]
    old_target = positions.loc[idx, "take_profit"]

    # Update target
    positions.loc[idx, "take_profit"] = new_target

    return positions, transactions, {
        "status": "EXECUTED",
        "old_target": old_target,
        "new_target": new_target,
    }


def execute_actions(actions: list[dict]) -> list[dict]:
    """Execute a list of actions from the intelligence engine."""

    config = load_config()
    positions = load_positions()
    transactions = load_transactions()

    results = []

    mode = "PAPER" if is_paper_mode() else "LIVE"
    print(f"\n🚀 Executing Intelligence Actions ({mode} MODE)")
    print("=" * 60)

    for action in actions:
        # Skip errors or blocked actions
        if "error" in action:
            results.append({"action": action, "result": {"status": "ERROR", "error": action["error"]}})
            continue

        if action.get("safety_check") == "BLOCKED":
            results.append({"action": action, "result": {"status": "BLOCKED", "reason": action.get("block_reason")}})
            print(f"⛔ BLOCKED: {action.get('action')} {action.get('ticker', '')}")
            print(f"   Reason: {action.get('block_reason')}")
            continue

        action_type = action.get("action", "")
        ticker = action.get("ticker", "-")

        # Skip HOLD actions
        if action_type == "HOLD":
            results.append({"action": action, "result": {"status": "HOLD"}})
            print(f"⏸️  HOLD: {action.get('reason', 'No changes needed')}")
            continue

        # Execute based on action type
        if action_type == "BUY":
            positions, transactions, result = execute_buy(action, positions, transactions, config)
        elif action_type == "SELL":
            positions, transactions, result = execute_sell(action, positions, transactions, config)
        elif action_type == "TRIM":
            positions, transactions, result = execute_trim(action, positions, transactions, config)
        elif action_type == "ADD":
            positions, transactions, result = execute_add(action, positions, transactions, config)
        elif action_type == "ADJUST_STOP":
            positions, transactions, result = execute_adjust_stop(action, positions, transactions, config)
        elif action_type == "ADJUST_TARGET":
            positions, transactions, result = execute_adjust_target(action, positions, transactions, config)
        else:
            result = {"status": "UNKNOWN", "reason": f"Unknown action type: {action_type}"}

        results.append({"action": action, "result": result})

        # Print result
        status = result.get("status", "?")
        if status == "EXECUTED":
            emoji = "✅"
            if action_type in ["BUY", "ADD"]:
                detail = f"Bought {result.get('shares')} @ ${result.get('price'):.2f}"
            elif action_type == "SELL":
                pnl = result.get("pnl", 0)
                pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                detail = f"Sold {result.get('shares')} @ ${result.get('price'):.2f} ({pnl_str})"
            elif action_type == "TRIM":
                detail = f"Sold {result.get('shares_sold')} shares, {result.get('shares_remaining')} remaining"
            elif action_type in ["ADJUST_STOP", "ADJUST_TARGET"]:
                detail = f"${result.get('old_stop', result.get('old_target')):.2f} → ${result.get('new_stop', result.get('new_target')):.2f}"
            else:
                detail = str(result)
        else:
            emoji = "❌" if status == "FAILED" else "⏭️"
            detail = result.get("reason", status)

        print(f"{emoji} {action_type} {ticker}: {detail}")

    # Save updated data
    save_positions(positions)
    save_transactions(transactions)

    print()
    print(f"💾 Saved to {'paper' if is_paper_mode() else 'live'} data files")

    return results


def run_full_intelligence():
    """Run the full intelligence cycle: analyze + execute."""

    from portfolio_intelligence import run_intelligence

    # Get recommendations
    result = run_intelligence()
    actions = result.get("actions", [])

    # Filter to executable actions
    executable = [a for a in actions if a.get("safety_check") == "PASSED" or a.get("action") == "HOLD"]

    if not executable:
        print("\n📭 No actions to execute")
        return

    # Execute
    execute_actions(actions)


if __name__ == "__main__":
    run_full_intelligence()
