#!/usr/bin/env python3
"""
Execute Sells - Daily script to check and execute stop loss / take profit triggers.

Workflow:
1. Load current positions from positions.csv
2. Fetch current prices via yfinance
3. Check each position against stop_loss and take_profit levels
4. Execute sells by writing SELL transactions to transactions.csv
5. Update positions.csv to remove/reduce sold positions
6. Print summary of sells executed

Usage: python scripts/execute_sells.py
"""

import uuid
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

from schema import TRANSACTION_COLUMNS, POSITION_COLUMNS, Action, Reason
from risk_manager import RiskManager, SellSignal

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
POSITIONS_FILE = DATA_DIR / "positions.csv"
TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"


def fetch_current_prices(tickers: list) -> dict:
    """Fetch current prices for a list of tickers."""
    prices = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, period="1d", progress=False, auto_adjust=True)
            if not df.empty:
                prices[ticker] = df["Close"].iloc[-1].item()
        except Exception as e:
            print(f"  [warn] Failed to fetch {ticker}: {e}")
    return prices


def record_sell_transaction(signal: SellSignal) -> dict:
    """Create a transaction record for a sell."""
    return {
        "transaction_id": str(uuid.uuid4())[:8],
        "date": date.today().isoformat(),
        "ticker": signal.ticker,
        "action": Action.SELL,
        "shares": signal.shares,
        "price": round(signal.current_price, 2),
        "total_value": round(signal.shares * signal.current_price, 2),
        "stop_loss": "",
        "take_profit": "",
        "reason": signal.reason,
    }


def append_transactions(transactions: list):
    """Append new transactions to transactions.csv."""
    if not transactions:
        return

    df_new = pd.DataFrame(transactions, columns=TRANSACTION_COLUMNS)

    if TRANSACTIONS_FILE.exists():
        df_existing = pd.read_csv(TRANSACTIONS_FILE)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new

    df_combined.to_csv(TRANSACTIONS_FILE, index=False)


def update_positions_after_sells(signals: list):
    """
    Update positions.csv after sells.
    For full sells, remove the position.
    For partial sells, reduce shares (not implemented yet - sells are full position).
    """
    if not signals:
        return

    if not POSITIONS_FILE.exists():
        return

    df = pd.read_csv(POSITIONS_FILE)
    sold_tickers = [s.ticker for s in signals]

    # Remove sold positions
    df = df[~df["ticker"].isin(sold_tickers)]
    df.to_csv(POSITIONS_FILE, index=False)


def main():
    print("\n─── Execute Sells ───\n")

    # Check if positions file exists
    if not POSITIONS_FILE.exists():
        print("  No positions.csv found, nothing to check")
        return

    # Load positions
    df_positions = pd.read_csv(POSITIONS_FILE)
    if df_positions.empty:
        print("  No positions to check")
        return

    print(f"  Checking {len(df_positions)} positions for stop loss / take profit...")

    # Fetch current prices
    tickers = df_positions["ticker"].tolist()
    current_prices = fetch_current_prices(tickers)

    if not current_prices:
        print("  [warn] Could not fetch any prices, skipping sell checks")
        return

    # Initialize risk manager and check for signals
    rm = RiskManager()
    signals = rm.get_all_sell_signals(df_positions, current_prices)

    if not signals:
        print("  ✅ No stop loss or take profit triggers")
        return

    # Process signals
    print(f"\n  Found {len(signals)} sell signal(s):\n")

    transactions = []
    total_value = 0

    for signal in signals:
        reason_emoji = "🛑" if signal.reason == Reason.STOP_LOSS else "🎯"
        print(f"  {reason_emoji} {signal.ticker}: {signal.reason}")
        print(f"      Shares: {signal.shares}")
        print(f"      Trigger: ${signal.trigger_price:.2f}")
        print(f"      Current: ${signal.current_price:.2f}")
        print(f"      Value: ${signal.shares * signal.current_price:,.2f}")
        print()

        transactions.append(record_sell_transaction(signal))
        total_value += signal.shares * signal.current_price

    # Record transactions
    print("  Recording transactions...")
    append_transactions(transactions)

    # Update positions
    print("  Updating positions...")
    update_positions_after_sells(signals)

    # Summary
    stop_count = sum(1 for s in signals if s.reason == Reason.STOP_LOSS)
    take_count = sum(1 for s in signals if s.reason == Reason.TAKE_PROFIT)

    print("\n─" * 40)
    print(f"✅ Executed {len(signals)} sell(s)")
    print(f"   Stop losses:  {stop_count}")
    print(f"   Take profits: {take_count}")
    print(f"   Total value:  ${total_value:,.2f}")
    print("─" * 40)


if __name__ == "__main__":
    main()
