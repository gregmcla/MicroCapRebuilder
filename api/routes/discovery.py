"""Stock discovery/scan endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/{portfolio_id}")


@router.post("/scan")
def run_scan(portfolio_id: str):
    """Trigger watchlist discovery scan and return stats."""
    from watchlist_manager import update_watchlist

    stats = update_watchlist(run_discovery=True, portfolio_id=portfolio_id)
    return stats
