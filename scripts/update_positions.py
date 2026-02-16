#!/usr/bin/env python3
"""
Update current positions with live prices and append daily snapshot.

1. Loads portfolio state (fetches current prices)
2. Saves updated positions to positions.csv
3. Appends daily snapshot to daily_snapshots.csv

Usage: python scripts/update_positions.py
"""

from datetime import date

from data_files import get_mode_indicator
from portfolio_state import (
    load_portfolio_state,
    save_positions,
    save_snapshot,
)


def main(portfolio_id: str = None):
    mode_indicator = get_mode_indicator()
    print(f"\n─── Updating Positions {mode_indicator} ───\n")

    # Load complete state with current prices
    print("Step 1: Loading portfolio state and fetching prices...")
    state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)

    if state.price_failures:
        for ticker in state.price_failures:
            print(f"    [warn] Failed to fetch price for {ticker}")

    if state.num_positions == 0:
        print("  No positions to update")
    else:
        total_pnl = float(state.positions["unrealized_pnl"].sum())
        print(f"  ✅ {state.num_positions} positions updated: ${state.positions_value:,.2f} (P&L: ${total_pnl:+,.2f})")
    print()

    # Save updated positions
    print("Step 2: Saving positions...")
    save_positions(state)
    print(f"  Cash: ${state.cash:,.2f}")
    print()

    # Record daily snapshot
    print("Step 3: Recording daily snapshot...")
    total_equity, day_pnl = save_snapshot(state)
    print()

    # Summary
    print("─" * 40)
    print(f"✅ TOTAL for {date.today().isoformat()}")
    print(f"   Positions: ${state.positions_value:,.2f}")
    print(f"   Cash:      ${state.cash:,.2f}")
    print(f"   Equity:    ${total_equity:,.2f}")
    print(f"   Day P&L:   ${day_pnl:+,.2f}")
    print("─" * 40)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Update positions with live prices")
    parser.add_argument("--portfolio", default=None, help="Portfolio ID (default: registry default)")
    args = parser.parse_args()

    main(portfolio_id=args.portfolio)
