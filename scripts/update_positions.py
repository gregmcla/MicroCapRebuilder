#!/usr/bin/env python3
"""
Update current positions with live prices and append daily snapshot.

Replaces fix_total_today.py with enhanced functionality:
1. Reads positions from positions.csv
2. Fetches current prices via yfinance
3. Calculates unrealized P&L
4. Updates positions.csv with current values
5. Appends daily snapshot to daily_snapshots.csv

Usage: python scripts/update_positions.py
"""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

from schema import POSITION_COLUMNS, DAILY_SNAPSHOT_COLUMNS

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
POSITIONS_FILE = DATA_DIR / "positions.csv"
DAILY_SNAPSHOTS_FILE = DATA_DIR / "daily_snapshots.csv"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config():
    """Load configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "starting_capital": 5000.0,
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
    }


def fetch_current_price(ticker):
    """Fetch current price for a ticker."""
    try:
        df = yf.download(ticker, period="1d", progress=False, auto_adjust=True)
        if df.empty:
            return None
        return df["Close"].iloc[-1].item()
    except Exception as e:
        print(f"  [warn] Failed to fetch {ticker}: {e}")
        return None


def fetch_benchmark_value(config):
    """Fetch benchmark value for comparison."""
    for symbol in [config["benchmark_symbol"], config.get("fallback_benchmark", "IWM")]:
        price = fetch_current_price(symbol)
        if price is not None:
            return round(price, 2)
    return None


def calculate_cash_from_transactions():
    """Calculate current cash from transaction history."""
    config = load_config()
    transactions_file = DATA_DIR / "transactions.csv"

    if not transactions_file.exists():
        return config["starting_capital"]

    df = pd.read_csv(transactions_file)
    if df.empty:
        return config["starting_capital"]

    # Sum all transaction values (BUY reduces cash, SELL increases)
    total_spent = 0
    total_received = 0

    for _, row in df.iterrows():
        if row["action"] == "BUY":
            total_spent += row["total_value"]
        elif row["action"] == "SELL":
            total_received += row["total_value"]

    cash = config["starting_capital"] - total_spent + total_received
    return cash


def update_positions():
    """Update positions with current prices and calculate P&L."""
    if not POSITIONS_FILE.exists():
        print("  No positions.csv found, nothing to update")
        return pd.DataFrame(columns=POSITION_COLUMNS), 0

    df = pd.read_csv(POSITIONS_FILE)
    if df.empty:
        print("  No positions to update")
        return df, 0

    print(f"  Updating {len(df)} positions...")

    # Fetch prices for all tickers
    tickers = df["ticker"].tolist()

    for idx, row in df.iterrows():
        ticker = row["ticker"]
        shares = row["shares"]
        avg_cost = row["avg_cost_basis"]

        # Fetch current price
        current_price = fetch_current_price(ticker)
        if current_price is None:
            current_price = avg_cost  # Fallback to cost basis
            print(f"    [warn] Using cost basis for {ticker}")

        # Calculate values
        market_value = shares * current_price
        cost_value = shares * avg_cost
        unrealized_pnl = market_value - cost_value
        unrealized_pnl_pct = (unrealized_pnl / cost_value * 100) if cost_value > 0 else 0

        # Update row
        df.at[idx, "current_price"] = round(current_price, 2)
        df.at[idx, "market_value"] = round(market_value, 2)
        df.at[idx, "unrealized_pnl"] = round(unrealized_pnl, 2)
        df.at[idx, "unrealized_pnl_pct"] = round(unrealized_pnl_pct, 2)

    # Save updated positions
    df.to_csv(POSITIONS_FILE, index=False)

    total_value = df["market_value"].sum()
    total_pnl = df["unrealized_pnl"].sum()
    print(f"  ✅ Positions updated: ${total_value:,.2f} (P&L: ${total_pnl:+,.2f})")

    return df, total_value


def get_previous_equity():
    """Get previous day's equity for P&L calculation."""
    if not DAILY_SNAPSHOTS_FILE.exists():
        return None

    df = pd.read_csv(DAILY_SNAPSHOTS_FILE)
    if df.empty:
        return None

    return df.iloc[-1]["total_equity"]


def append_daily_snapshot(positions_value, cash, benchmark_value=None):
    """Append today's snapshot to daily_snapshots.csv."""
    today = date.today().isoformat()
    total_equity = positions_value + cash

    # Calculate day's P&L
    prev_equity = get_previous_equity()
    if prev_equity is not None and prev_equity > 0:
        day_pnl = total_equity - prev_equity
        day_pnl_pct = (day_pnl / prev_equity) * 100
    else:
        day_pnl = 0
        day_pnl_pct = 0

    snapshot = {
        "date": today,
        "cash": round(cash, 2),
        "positions_value": round(positions_value, 2),
        "total_equity": round(total_equity, 2),
        "day_pnl": round(day_pnl, 2),
        "day_pnl_pct": round(day_pnl_pct, 2),
        "benchmark_value": benchmark_value if benchmark_value else "",
    }

    # Load or create snapshots file
    if DAILY_SNAPSHOTS_FILE.exists():
        df = pd.read_csv(DAILY_SNAPSHOTS_FILE)
        # Remove existing entry for today if any
        df = df[df["date"] != today]
    else:
        df = pd.DataFrame(columns=DAILY_SNAPSHOT_COLUMNS)

    # Append today's snapshot
    df = pd.concat([df, pd.DataFrame([snapshot])], ignore_index=True)
    df.to_csv(DAILY_SNAPSHOTS_FILE, index=False)

    return total_equity, day_pnl


def main():
    print("\n─── Updating Positions ───\n")

    config = load_config()

    # Step 1: Update positions with current prices
    print("Step 1: Fetching current prices...")
    positions_df, positions_value = update_positions()
    print()

    # Step 2: Calculate cash
    print("Step 2: Calculating cash balance...")
    cash = calculate_cash_from_transactions()
    print(f"  Cash: ${cash:,.2f}")
    print()

    # Step 3: Fetch benchmark
    print("Step 3: Fetching benchmark...")
    benchmark = fetch_benchmark_value(config)
    if benchmark:
        print(f"  Benchmark ({config['benchmark_symbol']}): ${benchmark:,.2f}")
    print()

    # Step 4: Append daily snapshot
    print("Step 4: Recording daily snapshot...")
    total_equity, day_pnl = append_daily_snapshot(positions_value, cash, benchmark)
    print()

    # Summary
    print("─" * 40)
    print(f"✅ TOTAL for {date.today().isoformat()}")
    print(f"   Positions: ${positions_value:,.2f}")
    print(f"   Cash:      ${cash:,.2f}")
    print(f"   Equity:    ${total_equity:,.2f}")
    print(f"   Day P&L:   ${day_pnl:+,.2f}")
    print("─" * 40)


if __name__ == "__main__":
    main()
