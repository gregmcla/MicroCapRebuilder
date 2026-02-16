"""Portfolio state endpoints."""

from fastapi import APIRouter
from api.deps import serialize

from portfolio_state import load_portfolio_state, save_positions, save_snapshot, invalidate_regime_cache

router = APIRouter(prefix="/api/{portfolio_id}")


def _serialize_state(state):
    """Convert PortfolioState to a JSON-safe dict."""
    positions = state.positions
    transactions = state.transactions
    snapshots = state.snapshots

    # Day P&L from last two snapshots
    day_pnl = 0.0
    day_pnl_pct = 0.0
    if len(snapshots) >= 2:
        today = snapshots.iloc[-1]
        yesterday = snapshots.iloc[-2]
        day_pnl = float(today.get("day_pnl", 0) or 0)
        day_pnl_pct = float(today.get("day_pnl_pct", 0) or 0)
    elif len(snapshots) == 1:
        today = snapshots.iloc[-1]
        day_pnl = float(today.get("day_pnl", 0) or 0)
        day_pnl_pct = float(today.get("day_pnl_pct", 0) or 0)

    # Total return from snapshots
    total_return_pct = 0.0
    if len(snapshots) >= 1:
        starting = state.config.get("starting_capital", 50000)
        current = state.total_equity
        if starting > 0:
            total_return_pct = ((current - starting) / starting) * 100

    return {
        "cash": state.cash,
        "positions": serialize(positions.tail(50)),
        "transactions": serialize(transactions.tail(50)),
        "snapshots": serialize(snapshots.tail(30)),
        "regime": serialize(state.regime),
        "regime_analysis": serialize(state.regime_analysis),
        "positions_value": state.positions_value,
        "total_equity": state.total_equity,
        "num_positions": state.num_positions,
        "config": state.config,
        "stale_alerts": state.stale_alerts,
        "paper_mode": state.paper_mode,
        "price_failures": state.price_failures,
        "day_pnl": day_pnl,
        "day_pnl_pct": day_pnl_pct,
        "total_return_pct": total_return_pct,
        "timestamp": serialize(state.timestamp),
    }


@router.get("/state")
def get_state(portfolio_id: str):
    """Portfolio state without refreshing prices (fast)."""
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    return _serialize_state(state)


@router.get("/state/refresh")
def get_state_refresh(portfolio_id: str):
    """Portfolio state with fresh prices (slower)."""
    invalidate_regime_cache()
    state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)
    save_positions(state)
    save_snapshot(state)
    # Reload so _serialize_state reads the updated snapshot for day_pnl
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    return _serialize_state(state)
