import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import types
import pandas as pd
from api.routes.state import _serialize_state


def _make_state(cash: float, positions: list[dict], starting_capital: float):
    """Build a minimal PortfolioState-like object for testing."""
    state = types.SimpleNamespace()
    state.cash = cash
    state.positions = pd.DataFrame(positions) if positions else pd.DataFrame(
        columns=["ticker", "shares", "avg_cost_basis", "current_price",
                 "market_value", "unrealized_pnl", "unrealized_pnl_pct",
                 "day_change", "day_change_pct"]
    )
    state.transactions = pd.DataFrame()
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


def test_realized_pnl_no_positions():
    """All cash, no positions: realized = cash - starting_capital."""
    state = _make_state(cash=60000, positions=[], starting_capital=50000)
    result = _serialize_state(state)
    assert "realized_pnl" in result
    assert result["realized_pnl"] == 10000.0


def test_realized_pnl_with_open_positions():
    """Cash + deployed capital - starting: realized excludes unrealized gains."""
    state = _make_state(
        cash=30000,
        positions=[{
            "ticker": "AAPL",
            "shares": 10,
            "avg_cost_basis": 150.0,
            "current_price": 200.0,
            "market_value": 2000.0,
            "unrealized_pnl": 500.0,
            "unrealized_pnl_pct": 33.3,
            "day_change": 0.0,
            "day_change_pct": 0.0,
        }],
        starting_capital=50000,
    )
    # realized = cash(30000) + cost_deployed(10 * 150 = 1500) - starting(50000) = -18500
    result = _serialize_state(state)
    assert result["realized_pnl"] == -18500.0


def test_realized_pnl_break_even():
    """Starting capital all in cash means 0 realized P&L."""
    state = _make_state(cash=50000, positions=[], starting_capital=50000)
    result = _serialize_state(state)
    assert result["realized_pnl"] == 0.0
