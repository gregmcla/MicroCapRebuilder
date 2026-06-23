"""Position Lineage endpoints — chronological event timeline per position."""

from fastapi import APIRouter, Depends, Query

from api.deps import validate_portfolio_id

from position_lineage import build_lineage, build_summary, event_to_dict


router = APIRouter(prefix="/api/{portfolio_id}/lineage")


@router.get("/{ticker}")
def get_lineage(
    ticker: str,
    portfolio_id: str = Depends(validate_portfolio_id),
    from_date: str | None = Query(default=None, alias="from"),
    limit: int = Query(default=200, ge=1, le=2000),
):
    """Return a chronological (newest first) timeline of every event that
    touched this ticker — watchlist add/remove, AI considered, buys, sells,
    stop adjustments, post-mortems, and material score changes.
    """
    events = build_lineage(portfolio_id, ticker, from_date=from_date, limit=limit)
    return {
        "ticker": ticker.upper(),
        "portfolio_id": portfolio_id,
        "events": [event_to_dict(e) for e in events],
    }


@router.get("/{ticker}/summary")
def get_lineage_summary(
    ticker: str,
    portfolio_id: str = Depends(validate_portfolio_id),
):
    """Lightweight summary for hover/preview cards: first_seen, first_bought,
    last_traded, total_trades, total_pnl, current_status."""
    return build_summary(portfolio_id, ticker)
