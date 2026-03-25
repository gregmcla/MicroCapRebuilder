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
from datetime import date, datetime

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
from yf_session import cached_download


def record_sell_transaction(signal: SellSignal) -> dict:
    """Create a transaction record for a sell."""
    return {
        "transaction_id": str(uuid.uuid4())[:8],
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
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


def check_liquidity_signals(positions_df: pd.DataFrame, price_cache: dict) -> list[SellSignal]:
    """
    Generate LIQUIDITY_DROP sell signals for positions where recent 5-day average
    volume has fallen below 30% of the 3-month average volume.

    Uses cached_download to fetch ~65 trading days of daily data per ticker.
    Skips any ticker where price data is unavailable — never raises.
    """
    signals = []

    for _, row in positions_df.iterrows():
        ticker = row["ticker"]
        current_price = price_cache.get(ticker)
        if current_price is None:
            continue

        try:
            data = cached_download(ticker, period="3mo", interval="1d")
            if data is None or data.empty:
                continue

            # Flatten MultiIndex columns if present (yfinance batch download)
            if isinstance(data.columns, pd.MultiIndex):
                try:
                    data = data.xs(ticker, axis=1, level=1)
                except KeyError:
                    continue

            if "Volume" not in data.columns:
                continue

            volume = data["Volume"].dropna()
            if len(volume) < 10:
                continue

            # 3-month average (all available rows, typically ~65 trading days)
            avg_3mo = volume.mean()
            if avg_3mo <= 0:
                continue

            # Most recent 5-day average
            avg_5d = volume.iloc[-5:].mean()

            # Trigger if 5-day avg is less than 30% of the 3-month avg
            if avg_5d < avg_3mo * 0.30:
                ratio_pct = (avg_5d / avg_3mo) * 100
                signals.append(SellSignal(
                    ticker=ticker,
                    shares=int(row["shares"]),
                    reason=Reason.LIQUIDITY_DROP,
                    trigger_price=current_price,
                    current_price=current_price,
                ))
                print(f"  [liquidity] {ticker}: 5d avg vol {avg_5d:,.0f} = {ratio_pct:.1f}% of 3mo avg {avg_3mo:,.0f}")

        except Exception as e:
            print(f"    [warn] Liquidity check failed for {ticker}: {e}")

    return signals


def check_stagnation_signals(positions_df: pd.DataFrame, price_cache: dict) -> list[SellSignal]:
    """
    Generate STAGNATION sell signals for positions held longer than 45 days
    with unrealized P&L between -5% and +5% (flat / going nowhere).

    Reads entry_date from positions_df. Skips rows with missing entry_date
    or missing current price — never raises.
    """
    signals = []
    today = date.today()

    for _, row in positions_df.iterrows():
        ticker = row["ticker"]
        current_price = price_cache.get(ticker)
        if current_price is None:
            continue

        # Parse entry_date
        raw_entry = row.get("entry_date")
        if not raw_entry or pd.isna(raw_entry):
            continue

        try:
            if isinstance(raw_entry, str):
                entry_date = datetime.strptime(raw_entry[:10], "%Y-%m-%d").date()
            elif hasattr(raw_entry, "date"):
                entry_date = raw_entry.date()
            else:
                entry_date = raw_entry
        except Exception as e:
            print(f"Warning: failed to parse entry date, skipping position: {e}")
            continue

        days_held = (today - entry_date).days
        if days_held <= 45:
            continue

        # Compute unrealized P&L %
        avg_cost = row.get("avg_cost_basis")
        if not avg_cost or pd.isna(avg_cost) or float(avg_cost) <= 0:
            continue

        avg_cost = float(avg_cost)
        pnl_pct = (current_price - avg_cost) / avg_cost * 100

        # Flat zone: between -5% and +5%
        if -5.0 <= pnl_pct <= 5.0:
            signals.append(SellSignal(
                ticker=ticker,
                shares=int(row["shares"]),
                reason=Reason.STAGNATION,
                trigger_price=current_price,
                current_price=current_price,
            ))
            print(f"  [stagnation] {ticker}: held {days_held}d, P&L {pnl_pct:+.1f}% — zombie position")

    return signals


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

    # --- Additional exit checks ---
    print("  Checking liquidity (volume) conditions...")
    liquidity_signals = check_liquidity_signals(state.positions, state.price_cache)
    signals.extend(liquidity_signals)

    print("  Checking for stagnant positions...")
    stagnation_signals = check_stagnation_signals(state.positions, state.price_cache)
    signals.extend(stagnation_signals)

    # Deduplicate: if a ticker already has a price-based signal, skip redundant extras
    seen_tickers = set()
    deduped_signals = []
    for sig in signals:
        if sig.ticker not in seen_tickers:
            seen_tickers.add(sig.ticker)
            deduped_signals.append(sig)
        else:
            print(f"    [skip] {sig.ticker} already has a sell signal ({sig.reason} suppressed)")
    signals = deduped_signals

    if not signals:
        print("  No sell triggers (stop loss, take profit, liquidity, or stagnation)")
        return

    # Process signals
    print(f"\n  Found {len(signals)} sell signal(s):\n")

    transactions = []
    total_value = 0

    REASON_EMOJI = {
        Reason.STOP_LOSS: "🛑",
        Reason.TAKE_PROFIT: "🎯",
        Reason.LIQUIDITY_DROP: "💧",
        Reason.STAGNATION: "🪨",
    }
    for signal in signals:
        reason_emoji = REASON_EMOJI.get(signal.reason, "📤")
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
    liquidity_count = sum(1 for s in signals if s.reason == Reason.LIQUIDITY_DROP)
    stagnation_count = sum(1 for s in signals if s.reason == Reason.STAGNATION)

    print("\n" + "─" * 40)
    print(f"Executed {len(signals)} sell(s)")
    print(f"   Stop losses:     {stop_count}")
    print(f"   Take profits:    {take_count}")
    print(f"   Liquidity drops: {liquidity_count}")
    print(f"   Stagnations:     {stagnation_count}")
    print(f"   Total value:     ${total_value:,.2f}")
    print("─" * 40)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Execute stop loss / take profit sells")
    parser.add_argument("--portfolio", default=None, help="Portfolio ID (default: registry default)")
    args = parser.parse_args()

    main(portfolio_id=args.portfolio)
