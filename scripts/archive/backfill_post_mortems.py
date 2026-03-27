#!/usr/bin/env python3
"""
One-time backfill: Generate post-mortems for all historical SELL transactions.

The unified analysis pipeline didn't generate post-mortems for sells,
so this script retroactively creates them from transaction history.

Usage: python scripts/backfill_post_mortems.py
"""

import pandas as pd
from pathlib import Path

from post_mortem import PostMortemAnalyzer, save_post_mortem, load_post_mortems, POST_MORTEMS_FILE
from data_files import get_transactions_file

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"


def main():
    print("\n--- Backfill Post-Mortems ---\n")

    # Load transactions
    tx_file = get_transactions_file()
    if not tx_file.exists():
        print("  No transactions file found")
        return

    df = pd.read_csv(tx_file)
    sells = df[df["action"] == "SELL"]
    buys = df[df["action"] == "BUY"]

    print(f"  Total transactions: {len(df)}")
    print(f"  SELL transactions: {len(sells)}")
    print(f"  BUY transactions: {len(buys)}")

    # Load existing post-mortems to skip already-processed
    existing_tickers_dates = set()
    if POST_MORTEMS_FILE.exists():
        existing = load_post_mortems()
        for pm in existing:
            existing_tickers_dates.add((pm.ticker, pm.close_date))
        print(f"  Existing post-mortems: {len(existing)}")
    else:
        print(f"  Existing post-mortems: 0")

    # Generate post-mortems
    analyzer = PostMortemAnalyzer()
    generated = 0
    skipped = 0
    failed = 0

    for _, sell in sells.iterrows():
        ticker = sell["ticker"]
        sell_date = str(sell["date"])

        # Skip if already processed
        if (ticker, sell_date) in existing_tickers_dates:
            skipped += 1
            continue

        # Find matching BUY
        ticker_buys = buys[buys["ticker"] == ticker]
        if ticker_buys.empty:
            print(f"  [skip] {ticker} - no matching BUY found")
            failed += 1
            continue

        buy_txn = ticker_buys.iloc[-1].to_dict()
        sell_txn = sell.to_dict()

        try:
            pm = analyzer.analyze_trade(sell_txn, buy_txn, current_regime="UNKNOWN")
            save_post_mortem(pm)
            generated += 1
            print(f"  📝 {ticker}: {pm.summary}")
        except Exception as e:
            print(f"  [error] {ticker}: {e}")
            failed += 1

    print(f"\n  Generated: {generated}")
    print(f"  Skipped (already exists): {skipped}")
    print(f"  Failed: {failed}")
    print("--- Done ---\n")


if __name__ == "__main__":
    main()
