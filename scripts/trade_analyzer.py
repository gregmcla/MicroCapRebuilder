#!/usr/bin/env python3
"""
Trade Analyzer Module for MicroCapRebuilder.

Analyzes completed trades (matched BUY/SELL pairs):
- Win rate
- Average gain/loss
- Profit factor
- Best/worst trades
- Performance by ticker

Usage:
    from trade_analyzer import TradeAnalyzer
    analyzer = TradeAnalyzer()
    stats = analyzer.calculate_trade_stats()
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd

from portfolio_state import load_portfolio_state


@dataclass
class TradeStats:
    """Container for trade statistics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    avg_trade_pct: float
    best_trade_ticker: str
    best_trade_pct: float
    worst_trade_ticker: str
    worst_trade_pct: float
    total_realized_pnl: float
    open_positions: int


@dataclass
class CompletedTrade:
    """Represents a completed (closed) trade."""
    ticker: str
    buy_date: str
    sell_date: str
    buy_price: float
    sell_price: float
    shares: int
    pnl: float
    pnl_pct: float
    reason: str  # Why sold: STOP_LOSS, TAKE_PROFIT, SIGNAL


class TradeAnalyzer:
    """Analyze trade performance."""

    def __init__(self, portfolio_id: str = None):
        self.portfolio_id = portfolio_id

    def load_transactions(self) -> pd.DataFrame:
        """Load all transactions."""
        state = load_portfolio_state(fetch_prices=False, portfolio_id=self.portfolio_id)
        return state.transactions

    def match_trades(self) -> List[CompletedTrade]:
        """
        Match BUY and SELL transactions to create completed trades.

        Uses FIFO (First In, First Out) matching.

        Returns:
            List of CompletedTrade objects
        """
        df = self.load_transactions()
        if df.empty:
            return []

        completed_trades = []

        # Group by ticker
        for ticker in df["ticker"].unique():
            ticker_txns = df[df["ticker"] == ticker].sort_values("date")

            buy_queue = []  # FIFO queue of buys

            for _, txn in ticker_txns.iterrows():
                if txn["action"] == "BUY":
                    buy_queue.append({
                        "date": txn["date"],
                        "price": txn["price"],
                        "shares": txn["shares"],
                    })
                elif txn["action"] == "SELL":
                    # Match with oldest buys (FIFO)
                    shares_to_sell = txn["shares"]
                    sell_price = txn["price"]
                    sell_date = txn["date"]
                    sell_reason = txn.get("reason", "SIGNAL")

                    while shares_to_sell > 0 and buy_queue:
                        buy = buy_queue[0]

                        shares_matched = min(shares_to_sell, buy["shares"])

                        # Calculate P&L for this portion
                        buy_value = shares_matched * buy["price"]
                        sell_value = shares_matched * sell_price
                        pnl = sell_value - buy_value
                        pnl_pct = (pnl / buy_value) * 100 if buy_value > 0 else 0

                        completed_trades.append(CompletedTrade(
                            ticker=ticker,
                            buy_date=buy["date"],
                            sell_date=sell_date,
                            buy_price=buy["price"],
                            sell_price=sell_price,
                            shares=shares_matched,
                            pnl=round(pnl, 2),
                            pnl_pct=round(pnl_pct, 2),
                            reason=sell_reason,
                        ))

                        # Update queues
                        shares_to_sell -= shares_matched
                        buy["shares"] -= shares_matched

                        if buy["shares"] == 0:
                            buy_queue.pop(0)

        return completed_trades

    def count_open_positions(self) -> int:
        """Count positions that haven't been sold."""
        df = self.load_transactions()
        if df.empty:
            return 0

        # Net shares per ticker
        position_counts = {}
        for _, txn in df.iterrows():
            ticker = txn["ticker"]
            shares = txn["shares"]

            if ticker not in position_counts:
                position_counts[ticker] = 0

            if txn["action"] == "BUY":
                position_counts[ticker] += shares
            elif txn["action"] == "SELL":
                position_counts[ticker] -= shares

        # Count tickers with positive shares
        return sum(1 for shares in position_counts.values() if shares > 0)

    def calculate_trade_stats(self) -> Optional[TradeStats]:
        """
        Calculate comprehensive trade statistics.

        Returns:
            TradeStats dataclass or None if no completed trades
        """
        completed_trades = self.match_trades()
        open_positions = self.count_open_positions()

        if not completed_trades:
            return TradeStats(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate_pct=0.0,
                avg_win_pct=0.0,
                avg_loss_pct=0.0,
                profit_factor=0.0,
                avg_trade_pct=0.0,
                best_trade_ticker="N/A",
                best_trade_pct=0.0,
                worst_trade_ticker="N/A",
                worst_trade_pct=0.0,
                total_realized_pnl=0.0,
                open_positions=open_positions,
            )

        # Separate winners and losers
        winners = [t for t in completed_trades if t.pnl > 0]
        losers = [t for t in completed_trades if t.pnl < 0]

        # Win rate
        win_rate = (len(winners) / len(completed_trades)) * 100 if completed_trades else 0

        # Average win/loss
        avg_win = sum(t.pnl_pct for t in winners) / len(winners) if winners else 0
        avg_loss = sum(t.pnl_pct for t in losers) / len(losers) if losers else 0

        # Profit factor (gross profit / gross loss)
        gross_profit = sum(t.pnl for t in winners)
        gross_loss = abs(sum(t.pnl for t in losers))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 10.0

        # Average trade
        avg_trade = sum(t.pnl_pct for t in completed_trades) / len(completed_trades)

        # Best and worst
        best_trade = max(completed_trades, key=lambda t: t.pnl_pct)
        worst_trade = min(completed_trades, key=lambda t: t.pnl_pct)

        # Total realized P&L
        total_pnl = sum(t.pnl for t in completed_trades)

        return TradeStats(
            total_trades=len(completed_trades),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate_pct=round(win_rate, 1),
            avg_win_pct=round(avg_win, 2),
            avg_loss_pct=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2),
            avg_trade_pct=round(avg_trade, 2),
            best_trade_ticker=best_trade.ticker,
            best_trade_pct=best_trade.pnl_pct,
            worst_trade_ticker=worst_trade.ticker,
            worst_trade_pct=worst_trade.pnl_pct,
            total_realized_pnl=round(total_pnl, 2),
            open_positions=open_positions,
        )

    def get_stats_by_reason(self) -> dict:
        """
        Get trade statistics grouped by exit reason.

        Returns:
            Dict mapping reason -> stats
        """
        completed_trades = self.match_trades()
        if not completed_trades:
            return {}

        stats_by_reason = {}

        for reason in ["STOP_LOSS", "TAKE_PROFIT", "SIGNAL", "MANUAL"]:
            trades = [t for t in completed_trades if t.reason == reason]
            if not trades:
                continue

            winners = [t for t in trades if t.pnl > 0]
            win_rate = (len(winners) / len(trades)) * 100

            stats_by_reason[reason] = {
                "count": len(trades),
                "win_rate": round(win_rate, 1),
                "total_pnl": round(sum(t.pnl for t in trades), 2),
            }

        return stats_by_reason

    def print_trade_report(self):
        """Print a formatted trade analysis report."""
        stats = self.calculate_trade_stats()

        if stats is None or stats.total_trades == 0:
            print("\n─── Trade Analysis ───\n")
            print("  No completed trades to analyze")
            print(f"  Open positions: {stats.open_positions if stats else 0}")
            return

        print("\n─── Trade Analysis ───\n")
        print(f"  Total Trades:     {stats.total_trades}")
        print(f"  Winners:          {stats.winning_trades}")
        print(f"  Losers:           {stats.losing_trades}")
        print(f"  Win Rate:         {stats.win_rate_pct:.1f}%")
        print()
        print(f"  Avg Win:          {stats.avg_win_pct:+.2f}%")
        print(f"  Avg Loss:         {stats.avg_loss_pct:+.2f}%")
        print(f"  Avg Trade:        {stats.avg_trade_pct:+.2f}%")
        print(f"  Profit Factor:    {stats.profit_factor:.2f}x")
        print()
        print(f"  Best Trade:       {stats.best_trade_ticker} ({stats.best_trade_pct:+.2f}%)")
        print(f"  Worst Trade:      {stats.worst_trade_ticker} ({stats.worst_trade_pct:+.2f}%)")
        print()
        print(f"  Realized P&L:     ${stats.total_realized_pnl:+,.2f}")
        print(f"  Open Positions:   {stats.open_positions}")
        print()

        # Stats by exit reason
        reason_stats = self.get_stats_by_reason()
        if reason_stats:
            print("  By Exit Reason:")
            for reason, s in reason_stats.items():
                print(f"    {reason}: {s['count']} trades, {s['win_rate']:.1f}% win, ${s['total_pnl']:+,.2f}")
        print()


if __name__ == "__main__":
    analyzer = TradeAnalyzer()
    analyzer.print_trade_report()
