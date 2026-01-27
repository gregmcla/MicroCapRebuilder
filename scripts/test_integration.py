#!/usr/bin/env python3
"""
Integration test for MicroCapRebuilder.
Tests the full workflow with mock price data.
"""

import json
import uuid
from datetime import date
from pathlib import Path

import pandas as pd

from schema import TRANSACTION_COLUMNS, POSITION_COLUMNS, DAILY_SNAPSHOT_COLUMNS, Action, Reason
from risk_manager import RiskManager
from analytics import PortfolioAnalytics
from trade_analyzer import TradeAnalyzer

DATA_DIR = Path(__file__).parent.parent / "data"
TEST_DIR = Path(__file__).parent.parent / "test_data"


def setup_test_data():
    """Create test data directory with sample data."""
    TEST_DIR.mkdir(exist_ok=True)

    # Create test transactions (some buys and sells)
    transactions = [
        {"transaction_id": "test001", "date": "2026-01-20", "ticker": "AAPL", "action": "BUY",
         "shares": 10, "price": 100.0, "total_value": 1000.0, "stop_loss": 92.0, "take_profit": 120.0, "reason": "SIGNAL"},
        {"transaction_id": "test002", "date": "2026-01-21", "ticker": "MSFT", "action": "BUY",
         "shares": 5, "price": 200.0, "total_value": 1000.0, "stop_loss": 184.0, "take_profit": 240.0, "reason": "SIGNAL"},
        {"transaction_id": "test003", "date": "2026-01-22", "ticker": "GOOGL", "action": "BUY",
         "shares": 8, "price": 125.0, "total_value": 1000.0, "stop_loss": 115.0, "take_profit": 150.0, "reason": "SIGNAL"},
        {"transaction_id": "test004", "date": "2026-01-25", "ticker": "AAPL", "action": "SELL",
         "shares": 10, "price": 115.0, "total_value": 1150.0, "stop_loss": "", "take_profit": "", "reason": "TAKE_PROFIT"},
        {"transaction_id": "test005", "date": "2026-01-26", "ticker": "MSFT", "action": "SELL",
         "shares": 5, "price": 180.0, "total_value": 900.0, "stop_loss": "", "take_profit": "", "reason": "STOP_LOSS"},
    ]

    df_txn = pd.DataFrame(transactions)
    df_txn.to_csv(TEST_DIR / "transactions.csv", index=False)

    # Create test positions (only GOOGL remains open)
    positions = [
        {"ticker": "GOOGL", "shares": 8, "avg_cost_basis": 125.0, "current_price": 130.0,
         "market_value": 1040.0, "unrealized_pnl": 40.0, "unrealized_pnl_pct": 4.0,
         "stop_loss": 115.0, "take_profit": 150.0, "entry_date": "2026-01-22"},
    ]

    df_pos = pd.DataFrame(positions)
    df_pos.to_csv(TEST_DIR / "positions.csv", index=False)

    # Create test daily snapshots
    snapshots = [
        {"date": "2026-01-20", "cash": 4000.0, "positions_value": 1000.0, "total_equity": 5000.0, "day_pnl": 0, "day_pnl_pct": 0, "benchmark_value": 100},
        {"date": "2026-01-21", "cash": 3000.0, "positions_value": 2050.0, "total_equity": 5050.0, "day_pnl": 50, "day_pnl_pct": 1.0, "benchmark_value": 101},
        {"date": "2026-01-22", "cash": 2000.0, "positions_value": 3100.0, "total_equity": 5100.0, "day_pnl": 50, "day_pnl_pct": 0.99, "benchmark_value": 102},
        {"date": "2026-01-23", "cash": 2000.0, "positions_value": 3200.0, "total_equity": 5200.0, "day_pnl": 100, "day_pnl_pct": 1.96, "benchmark_value": 103},
        {"date": "2026-01-24", "cash": 2000.0, "positions_value": 3000.0, "total_equity": 5000.0, "day_pnl": -200, "day_pnl_pct": -3.85, "benchmark_value": 101},
        {"date": "2026-01-25", "cash": 3150.0, "positions_value": 2100.0, "total_equity": 5250.0, "day_pnl": 250, "day_pnl_pct": 5.0, "benchmark_value": 104},
        {"date": "2026-01-26", "cash": 4050.0, "positions_value": 1040.0, "total_equity": 5090.0, "day_pnl": -160, "day_pnl_pct": -3.05, "benchmark_value": 103},
    ]

    df_snap = pd.DataFrame(snapshots)
    df_snap.to_csv(TEST_DIR / "daily_snapshots.csv", index=False)

    # Config
    config = {"starting_capital": 5000.0, "risk_per_trade_pct": 10.0}
    with open(TEST_DIR / "config.json", "w") as f:
        json.dump(config, f)

    return df_txn, df_pos, df_snap


def test_risk_manager():
    """Test risk manager functionality."""
    print("\n═══ Testing Risk Manager ═══\n")

    rm = RiskManager()

    # Test stop loss calculation
    stop = rm.calculate_stop_loss_price(100.0)
    print(f"  Stop loss for $100 entry: ${stop} (expected: $92)")
    assert stop == 92.0, f"Stop loss incorrect: {stop}"

    # Test take profit calculation
    take = rm.calculate_take_profit_price(100.0)
    print(f"  Take profit for $100 entry: ${take} (expected: $120)")
    assert take == 120.0, f"Take profit incorrect: {take}"

    # Test position sizing
    shares = rm.calculate_position_size(price=50.0, cash=1000.0)
    print(f"  Position size for $50 stock with $1000 cash: {shares} shares")
    assert shares == 2, f"Position size incorrect: {shares}"  # 10% of 1000 = 100, 100/50 = 2

    # Test stop loss trigger
    positions = pd.DataFrame([{
        "ticker": "TEST", "shares": 10, "stop_loss": 95.0, "take_profit": 120.0
    }])

    # Price below stop
    signals = rm.check_stop_losses(positions, {"TEST": 90.0})
    print(f"  Stop loss signals (price $90, stop $95): {len(signals)} signals")
    assert len(signals) == 1, "Should trigger stop loss"

    # Price above stop
    signals = rm.check_stop_losses(positions, {"TEST": 100.0})
    print(f"  Stop loss signals (price $100, stop $95): {len(signals)} signals")
    assert len(signals) == 0, "Should not trigger stop loss"

    # Test take profit trigger
    signals = rm.check_take_profits(positions, {"TEST": 125.0})
    print(f"  Take profit signals (price $125, target $120): {len(signals)} signals")
    assert len(signals) == 1, "Should trigger take profit"

    print("\n  ✅ Risk Manager tests passed!")


def test_trade_analyzer():
    """Test trade analyzer with test data."""
    print("\n═══ Testing Trade Analyzer ═══\n")

    # Setup test data
    setup_test_data()

    # Temporarily point to test data
    import trade_analyzer
    original_file = trade_analyzer.TRANSACTIONS_FILE
    trade_analyzer.TRANSACTIONS_FILE = TEST_DIR / "transactions.csv"

    analyzer = TradeAnalyzer()

    # Test trade matching
    completed = analyzer.match_trades()
    print(f"  Completed trades found: {len(completed)}")
    assert len(completed) == 2, f"Expected 2 completed trades, got {len(completed)}"

    # Test stats calculation
    stats = analyzer.calculate_trade_stats()
    print(f"  Total trades: {stats.total_trades}")
    print(f"  Win rate: {stats.win_rate_pct}%")
    print(f"  Winning trades: {stats.winning_trades}")
    print(f"  Losing trades: {stats.losing_trades}")
    print(f"  Realized P&L: ${stats.total_realized_pnl}")

    # AAPL: bought at 100, sold at 115 = +15% WIN
    # MSFT: bought at 200, sold at 180 = -10% LOSS
    assert stats.total_trades == 2, f"Expected 2 trades, got {stats.total_trades}"
    assert stats.winning_trades == 1, f"Expected 1 winner, got {stats.winning_trades}"
    assert stats.losing_trades == 1, f"Expected 1 loser, got {stats.losing_trades}"
    assert stats.win_rate_pct == 50.0, f"Expected 50% win rate, got {stats.win_rate_pct}"

    # P&L: AAPL +$150, MSFT -$100 = +$50 total
    assert stats.total_realized_pnl == 50.0, f"Expected $50 P&L, got {stats.total_realized_pnl}"

    # Restore original path
    trade_analyzer.TRANSACTIONS_FILE = original_file

    print("\n  ✅ Trade Analyzer tests passed!")


def test_analytics():
    """Test portfolio analytics."""
    print("\n═══ Testing Portfolio Analytics ═══\n")

    # Setup test data
    setup_test_data()

    # Temporarily point to test data
    import analytics
    original_file = analytics.DAILY_SNAPSHOTS_FILE
    original_config = analytics.CONFIG_FILE
    analytics.DAILY_SNAPSHOTS_FILE = TEST_DIR / "daily_snapshots.csv"
    analytics.CONFIG_FILE = TEST_DIR / "config.json"

    pa = PortfolioAnalytics()

    # Load equity curve
    df = pa.load_equity_curve()
    print(f"  Days of data: {len(df)}")
    assert len(df) == 7, f"Expected 7 days, got {len(df)}"

    # Calculate returns
    returns = pa.calculate_returns(df["total_equity"])
    print(f"  Daily returns calculated: {len(returns)}")

    # Calculate metrics
    metrics = pa.calculate_all_metrics()
    print(f"  Total return: {metrics.total_return_pct}%")
    print(f"  Max drawdown: {metrics.max_drawdown_pct}%")
    print(f"  Sharpe ratio: {metrics.sharpe_ratio}")
    print(f"  Days tracked: {metrics.days_tracked}")

    # Equity went from 5000 to 5090 = +1.8%
    assert metrics.total_return_pct == 1.8, f"Expected 1.8% return, got {metrics.total_return_pct}"
    assert metrics.days_tracked == 7, f"Expected 7 days, got {metrics.days_tracked}"

    # Restore original paths
    analytics.DAILY_SNAPSHOTS_FILE = original_file
    analytics.CONFIG_FILE = original_config

    print("\n  ✅ Analytics tests passed!")


def test_data_flow():
    """Test the data flow between components."""
    print("\n═══ Testing Data Flow ═══\n")

    setup_test_data()

    # Load transactions
    df_txn = pd.read_csv(TEST_DIR / "transactions.csv")
    print(f"  Transactions loaded: {len(df_txn)}")

    # Calculate cash from transactions
    buys = df_txn[df_txn["action"] == "BUY"]["total_value"].sum()
    sells = df_txn[df_txn["action"] == "SELL"]["total_value"].sum()
    starting = 5000.0
    cash = starting - buys + sells
    print(f"  Starting capital: ${starting}")
    print(f"  Total buys: ${buys}")
    print(f"  Total sells: ${sells}")
    print(f"  Calculated cash: ${cash}")

    # Cash should be: 5000 - 3000 (buys) + 2050 (sells) = 4050
    assert cash == 4050.0, f"Expected $4050 cash, got ${cash}"

    # Load positions and verify
    df_pos = pd.read_csv(TEST_DIR / "positions.csv")
    positions_value = df_pos["market_value"].sum()
    print(f"  Positions value: ${positions_value}")

    # Total equity
    total_equity = cash + positions_value
    print(f"  Total equity: ${total_equity}")

    # Should be 4050 + 1040 = 5090
    assert total_equity == 5090.0, f"Expected $5090 equity, got ${total_equity}"

    print("\n  ✅ Data Flow tests passed!")


def cleanup():
    """Clean up test data."""
    import shutil
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    print("\n  Cleaned up test data")


def main():
    print("\n" + "=" * 60)
    print("  MicroCapRebuilder Integration Tests")
    print("=" * 60)

    try:
        test_risk_manager()
        test_trade_analyzer()
        test_analytics()
        test_data_flow()

        print("\n" + "=" * 60)
        print("  ✅ ALL TESTS PASSED!")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n  ❌ TEST FAILED: {e}")
        raise
    finally:
        cleanup()


if __name__ == "__main__":
    main()
