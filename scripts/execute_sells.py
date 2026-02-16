#!/usr/bin/env python3
"""
Execute Sells - Daily script to check and execute stop loss / take profit triggers.

1. Load portfolio state (with current prices)
2. Check each position against stop_loss and take_profit levels
3. Execute sells by writing SELL transactions to transactions.csv
4. Update positions.csv to remove sold positions
5. Generate post-mortems for closed trades

Usage: python scripts/execute_sells.py
"""

import uuid
from datetime import date

import pandas as pd

from schema import TRANSACTION_COLUMNS, Action, Reason
from risk_manager import RiskManager, SellSignal
from market_regime import get_market_regime
from post_mortem import PostMortemAnalyzer, save_post_mortem
from data_files import get_mode_indicator, get_transactions_file
from portfolio_state import (
    load_portfolio_state,
    save_transactions_batch,
    remove_position,
    save_positions,
)


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
        # Explainability columns (empty for sells - data comes from original buy)
        "regime_at_entry": "",
        "composite_score": "",
        "factor_scores": "",
        "signal_rank": "",
    }


def get_buy_transaction_for_ticker(ticker: str, transactions_df: pd.DataFrame) -> dict:
    """Find the original BUY transaction for a ticker from state."""
    if transactions_df.empty:
        return {}

    buys = transactions_df[(transactions_df["ticker"] == ticker) & (transactions_df["action"] == "BUY")]
    if buys.empty:
        return {}

    # Return the most recent buy as a dict
    return buys.iloc[-1].to_dict()


def main(portfolio_id: str = None):
    mode_indicator = get_mode_indicator()
    print(f"\n─── Execute Sells {mode_indicator} ───\n")

    # Load portfolio state with current prices
    state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)

    if state.num_positions == 0:
        print("  No positions to check")
        return

    print(f"  Checking {state.num_positions} positions for stop loss / take profit...")

    if state.price_failures:
        for ticker in state.price_failures:
            print(f"    [warn] No price for {ticker} - using last known price")

    if state.stale_alerts:
        for ticker, days in state.stale_alerts.items():
            print(f"    ⚠️  STALE PRICE: {ticker} - no price for {days} consecutive days")

    # Check for sell signals using price cache
    rm = RiskManager()
    signals = rm.get_all_sell_signals(state.positions, state.price_cache)

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

    # Save transactions
    print("  Recording transactions...")
    state = save_transactions_batch(state, transactions)

    # Remove sold positions
    print("  Updating positions...")
    for signal in signals:
        state = remove_position(state, signal.ticker)
    save_positions(state)

    # Generate post-mortems for closed trades
    print("  Generating post-mortems...")
    try:
        regime = state.regime
        analyzer = PostMortemAnalyzer()

        for signal, sell_txn in zip(signals, transactions):
            buy_txn = get_buy_transaction_for_ticker(signal.ticker, state.transactions)
            if buy_txn:
                pm = analyzer.analyze_trade(
                    sell_txn=sell_txn,
                    buy_txn=buy_txn,
                    current_regime=regime.value if regime else "UNKNOWN"
                )
                save_post_mortem(pm)
                print(f"    📝 Post-mortem: {signal.ticker} - {pm.summary}")
    except Exception as e:
        print(f"    [warn] Post-mortem generation failed: {e}")

    # Summary
    stop_count = sum(1 for s in signals if s.reason == Reason.STOP_LOSS)
    take_count = sum(1 for s in signals if s.reason == Reason.TAKE_PROFIT)

    print("\n" + "─" * 40)
    print(f"✅ Executed {len(signals)} sell(s)")
    print(f"   Stop losses:  {stop_count}")
    print(f"   Take profits: {take_count}")
    print(f"   Total value:  ${total_value:,.2f}")
    print("─" * 40)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Execute stop loss / take profit sells")
    parser.add_argument("--portfolio", default=None, help="Portfolio ID (default: registry default)")
    args = parser.parse_args()

    main(portfolio_id=args.portfolio)
