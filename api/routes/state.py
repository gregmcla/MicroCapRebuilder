"""Portfolio state endpoints."""

from datetime import date

from fastapi import APIRouter
from api.deps import serialize

from portfolio_state import load_portfolio_state, save_positions, save_snapshot, invalidate_regime_cache

router = APIRouter(prefix="/api/{portfolio_id}")


def _serialize_state(state):
    """Convert PortfolioState to a JSON-safe dict."""
    positions = state.positions
    transactions = state.transactions
    snapshots = state.snapshots

    # Day P&L from last snapshot — only if markets were open today.
    # Weekends (weekday >= 5) mean no trading; snapshot day_pnl would be
    # yesterday's gain mislabeled as today's.
    day_pnl = 0.0
    day_pnl_pct = 0.0
    today = date.today()
    market_open_today = today.weekday() < 5  # Mon=0 … Fri=4
    if market_open_today and len(snapshots) >= 1:
        last = snapshots.iloc[-1]
        snapshot_date = str(last.get("date", ""))
        if snapshot_date.startswith(today.isoformat()):
            day_pnl = float(last.get("day_pnl", 0) or 0)
            day_pnl_pct = float(last.get("day_pnl_pct", 0) or 0)

    # Total return + all-time P&L
    starting_capital = float(state.config.get("starting_capital", 50000))
    total_return_pct = 0.0
    all_time_pnl = 0.0
    if starting_capital > 0:
        total_return_pct = ((state.total_equity - starting_capital) / starting_capital) * 100
        all_time_pnl = state.total_equity - starting_capital

    # Zero out stale day_change values in positions when markets are closed.
    # The CSV retains the last computed day_change (from the last trading session)
    # which would show as today's gain/loss when markets haven't opened.
    if not market_open_today and not positions.empty:
        positions = positions.copy()
        positions["day_change"] = 0.0
        positions["day_change_pct"] = 0.0

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
        "all_time_pnl": round(all_time_pnl, 2),
        "starting_capital": starting_capital,
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
