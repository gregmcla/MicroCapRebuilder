import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import types
import pandas as pd
from api.routes.state import _serialize_state


def _make_state(cash: float, positions: list[dict], starting_capital: float,
                transactions: list[dict] | None = None):
    """Build a minimal PortfolioState-like object for testing."""
    state = types.SimpleNamespace()
    state.cash = cash
    state.positions = pd.DataFrame(positions) if positions else pd.DataFrame(
        columns=["ticker", "shares", "avg_cost_basis", "current_price",
                 "market_value", "unrealized_pnl", "unrealized_pnl_pct",
                 "day_change", "day_change_pct"]
    )
    state.transactions = pd.DataFrame(transactions) if transactions else pd.DataFrame()
    state.snapshots = pd.DataFrame()
    state.regime = "BULL"
    state.regime_analysis = {}
    state.positions_value = sum(p.get("market_value", 0) for p in positions)
    state.total_equity = cash + state.positions_value
    state.num_positions = len(positions)
    state.config = {"starting_capital": starting_capital}
    state.stale_alerts = []
    state.paper_mode = True
    state.price_failures = []
    state.timestamp = None
    return state


def test_realized_pnl_key_present():
    """realized_pnl field is always in the response."""
    state = _make_state(cash=50000, positions=[], starting_capital=50000)
    result = _serialize_state(state)
    assert "realized_pnl" in result


def test_realized_pnl_no_transactions():
    """No completed trades: realized = 0."""
    state = _make_state(cash=60000, positions=[], starting_capital=50000)
    result = _serialize_state(state)
    assert result["realized_pnl"] == 0.0


def test_realized_pnl_completed_gain():
    """Bought 10 shares at $100, sold at $110: gain = $100."""
    state = _make_state(
        cash=50000, positions=[], starting_capital=50000,
        transactions=[
            {"ticker": "AAPL", "action": "BUY",  "shares": 10, "total_value": 1000.0, "date": "2026-01-01"},
            {"ticker": "AAPL", "action": "SELL", "shares": 10, "total_value": 1100.0, "date": "2026-01-15"},
        ],
    )
    result = _serialize_state(state)
    assert result["realized_pnl"] == 100.0


def test_realized_pnl_completed_loss():
    """Bought at $100, sold at $90: loss = -$100."""
    state = _make_state(
        cash=50000, positions=[], starting_capital=50000,
        transactions=[
            {"ticker": "AAPL", "action": "BUY",  "shares": 10, "total_value": 1000.0, "date": "2026-01-01"},
            {"ticker": "AAPL", "action": "SELL", "shares": 10, "total_value":  900.0, "date": "2026-01-15"},
        ],
    )
    result = _serialize_state(state)
    assert result["realized_pnl"] == -100.0


def test_realized_pnl_excludes_sell_without_buy():
    """SELL with no prior BUY (close-all remnant) is excluded from calculation."""
    state = _make_state(
        cash=50000, positions=[], starting_capital=50000,
        transactions=[
            {"ticker": "AMZN", "action": "SELL", "shares": 5, "total_value": 500.0, "date": "2026-01-01"},
        ],
    )
    result = _serialize_state(state)
    assert result["realized_pnl"] == 0.0


def test_realized_pnl_open_position_not_counted():
    """Unrealized gains on open positions do not affect realized P&L."""
    state = _make_state(
        cash=45000,
        positions=[{
            "ticker": "AAPL", "shares": 10, "avg_cost_basis": 150.0,
            "current_price": 200.0, "market_value": 2000.0,
            "unrealized_pnl": 500.0, "unrealized_pnl_pct": 33.3,
            "day_change": 0.0, "day_change_pct": 0.0,
        }],
        starting_capital=50000,
        transactions=[
            {"ticker": "AAPL", "action": "BUY", "shares": 10, "total_value": 1500.0, "date": "2026-01-01"},
        ],
    )
    # No sell yet — realized = 0
    result = _serialize_state(state)
    assert result["realized_pnl"] == 0.0


def test_realized_pnl_multiple_buys_avg_cost():
    """Multiple buys use weighted average cost for the sell."""
    # Buy 10@$100 then 10@$120 → avg cost $110. Sell 10@$130 → gain = $200.
    state = _make_state(
        cash=50000, positions=[], starting_capital=50000,
        transactions=[
            {"ticker": "X", "action": "BUY",  "shares": 10, "total_value": 1000.0, "date": "2026-01-01"},
            {"ticker": "X", "action": "BUY",  "shares": 10, "total_value": 1200.0, "date": "2026-01-05"},
            {"ticker": "X", "action": "SELL", "shares": 10, "total_value": 1300.0, "date": "2026-01-15"},
        ],
    )
    result = _serialize_state(state)
    assert result["realized_pnl"] == 200.0
