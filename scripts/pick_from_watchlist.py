#!/usr/bin/env python3
"""
Intelligent Stock Picker for Mommy Bot.

Enhanced picking logic with:
- Multi-factor scoring with regime-adaptive weights
- Market regime awareness (reduce/skip buying in bear markets)
- Volatility-adjusted position sizing
- Stop loss and take profit levels set at entry
- Portfolio limit enforcement

Usage: python scripts/pick_from_watchlist.py
"""

import json
import sys
import uuid
from datetime import date
from pathlib import Path

import pandas as pd

from schema import TRANSACTION_COLUMNS, POSITION_COLUMNS, Action, Reason
from risk_manager import RiskManager
from stock_scorer import StockScorer
from market_regime import get_market_regime, get_position_size_multiplier, MarketRegime
from capital_preservation import get_preservation_status

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.jsonl"
CONFIG_PATH = DATA_DIR / "config.json"
POSITIONS_FILE = DATA_DIR / "positions.csv"
TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"
DAILY_SNAPSHOTS_FILE = DATA_DIR / "daily_snapshots.csv"


def load_config() -> dict:
    """Load configuration."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "starting_capital": 5000.0,
        "risk_per_trade_pct": 10.0,
        "max_positions": 15,
    }


def load_watchlist() -> list:
    """Load tickers from watchlist."""
    if not WATCHLIST_PATH.exists():
        sys.exit(f"{WATCHLIST_PATH} not found")

    with open(WATCHLIST_PATH, "r") as f:
        watchlist = [json.loads(line) for line in f if line.strip()]

    return [item["ticker"] for item in watchlist]


def get_current_positions() -> pd.DataFrame:
    """Load current positions."""
    if not POSITIONS_FILE.exists():
        return pd.DataFrame(columns=POSITION_COLUMNS)
    return pd.read_csv(POSITIONS_FILE)


def calculate_cash() -> float:
    """Calculate available cash from transactions."""
    config = load_config()

    if not TRANSACTIONS_FILE.exists():
        return config["starting_capital"]

    df = pd.read_csv(TRANSACTIONS_FILE)
    if df.empty:
        return config["starting_capital"]

    total_spent = df[df["action"] == "BUY"]["total_value"].sum()
    total_received = df[df["action"] == "SELL"]["total_value"].sum()

    return config["starting_capital"] - total_spent + total_received


def get_total_equity(positions_df: pd.DataFrame, cash: float) -> float:
    """Calculate total portfolio equity."""
    positions_value = positions_df["market_value"].sum() if not positions_df.empty else 0
    return positions_value + cash


def record_buy_transaction(
    ticker: str,
    shares: int,
    price: float,
    stop_loss: float,
    take_profit: float,
) -> dict:
    """Create a BUY transaction record."""
    return {
        "transaction_id": str(uuid.uuid4())[:8],
        "date": date.today().isoformat(),
        "ticker": ticker,
        "action": Action.BUY,
        "shares": shares,
        "price": round(price, 2),
        "total_value": round(shares * price, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "reason": Reason.SIGNAL,
    }


def update_position(
    positions_df: pd.DataFrame,
    ticker: str,
    shares: int,
    price: float,
    stop_loss: float,
    take_profit: float,
) -> pd.DataFrame:
    """Add or update a position."""
    today = date.today().isoformat()

    if ticker in positions_df["ticker"].values:
        # Update existing position (average in)
        idx = positions_df[positions_df["ticker"] == ticker].index[0]
        existing_shares = positions_df.at[idx, "shares"]
        existing_cost = positions_df.at[idx, "avg_cost_basis"]

        new_shares = existing_shares + shares
        new_cost = ((existing_shares * existing_cost) + (shares * price)) / new_shares

        positions_df.at[idx, "shares"] = new_shares
        positions_df.at[idx, "avg_cost_basis"] = round(new_cost, 2)
        positions_df.at[idx, "current_price"] = round(price, 2)
        positions_df.at[idx, "market_value"] = round(new_shares * price, 2)
        positions_df.at[idx, "stop_loss"] = round(stop_loss, 2)
        positions_df.at[idx, "take_profit"] = round(take_profit, 2)
    else:
        # Add new position
        new_row = {
            "ticker": ticker,
            "shares": shares,
            "avg_cost_basis": round(price, 2),
            "current_price": round(price, 2),
            "market_value": round(shares * price, 2),
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "entry_date": today,
        }
        positions_df = pd.concat([positions_df, pd.DataFrame([new_row])], ignore_index=True)

    return positions_df


def append_transactions(transactions: list):
    """Append transactions to transactions.csv."""
    if not transactions:
        return

    df_new = pd.DataFrame(transactions, columns=TRANSACTION_COLUMNS)

    if TRANSACTIONS_FILE.exists():
        df_existing = pd.read_csv(TRANSACTIONS_FILE)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new

    df_combined.to_csv(TRANSACTIONS_FILE, index=False)


def main():
    print("\n─── Intelligent Stock Picker ───\n")

    config = load_config()
    rm = RiskManager()

    # Step 1: Check market regime
    print("Step 1: Analyzing market regime...")
    regime = get_market_regime()
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

    # Step 2: Load current state
    print("\nStep 2: Loading portfolio state...")
    positions_df = get_current_positions()
    cash = calculate_cash()
    total_equity = get_total_equity(positions_df, cash)
    current_tickers = positions_df["ticker"].tolist() if not positions_df.empty else []

    print(f"  Cash available: ${cash:,.2f}")
    print(f"  Current positions: {len(current_tickers)}")
    print(f"  Total equity: ${total_equity:,.2f}")

    # Check if max positions reached
    max_positions = config.get("max_positions", 15)
    if len(current_tickers) >= max_positions:
        print(f"\n  ⚠️  Max positions ({max_positions}) reached - skipping new buys")
        print("─" * 40)
        return

    # Step 3: Score watchlist candidates
    print("\nStep 3: Scoring watchlist candidates...")
    all_tickers = load_watchlist()

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

    for score in scores:
        # Check cash
        if cash < 100:  # Minimum $100 to trade
            print("  Insufficient cash remaining")
            break

        # Check position limits
        allowed, reason = rm.check_portfolio_limits(
            positions_df, score.ticker, risk_capital, total_equity
        )
        if not allowed:
            print(f"  Skipping {score.ticker}: {reason}")
            continue

        # Calculate position size (volatility-adjusted)
        shares = rm.calculate_position_size(
            price=score.current_price,
            cash=cash,
            volatility=score.atr_pct / 100 if score.atr_pct > 0 else None,
        )

        if shares < 1:
            continue

        total_cost = shares * score.current_price
        if total_cost > cash:
            continue

        # Calculate stop loss and take profit
        stop_loss = rm.calculate_stop_loss_price(score.current_price)
        take_profit = rm.calculate_take_profit_price(score.current_price)

        # Record transaction
        transaction = record_buy_transaction(
            ticker=score.ticker,
            shares=shares,
            price=score.current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        new_transactions.append(transaction)

        # Update position
        positions_df = update_position(
            positions_df,
            score.ticker,
            shares,
            score.current_price,
            stop_loss,
            take_profit,
        )

        # Update cash
        cash -= total_cost
        total_spent += total_cost
        buys_executed += 1

        print(f"  ✅ BUY {score.ticker}: {shares} shares @ ${score.current_price:.2f}")
        print(f"      Stop: ${stop_loss:.2f} | Target: ${take_profit:.2f}")

    # Step 5: Save changes
    if new_transactions:
        print("\nStep 5: Saving changes...")
        append_transactions(new_transactions)
        positions_df.to_csv(POSITIONS_FILE, index=False)
        print(f"  Saved {len(new_transactions)} transactions")

    # Summary
    print("\n" + "─" * 40)
    print(f"✅ Picks complete for {date.today().isoformat()}")
    print(f"   Buys executed: {buys_executed}")
    print(f"   Total spent:   ${total_spent:,.2f}")
    print(f"   Cash remaining: ${cash:,.2f}")
    print("─" * 40)


if __name__ == "__main__":
    main()
