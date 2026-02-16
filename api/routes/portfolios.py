#!/usr/bin/env python3
"""Portfolio management endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.deps import serialize

from portfolio_registry import (
    list_portfolios, create_portfolio,
    archive_portfolio, get_default_portfolio_id, UNIVERSE_PRESETS,
)
from portfolio_state import load_portfolio_state
from dataclasses import asdict

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


class CreatePortfolioRequest(BaseModel):
    id: str
    name: str
    universe: str
    starting_capital: float


@router.get("")
def get_portfolios():
    """List all active portfolios."""
    portfolios = list_portfolios(active_only=True)
    return {
        "portfolios": [asdict(p) for p in portfolios],
        "default_portfolio": get_default_portfolio_id(),
    }


@router.post("")
def create_new_portfolio(req: CreatePortfolioRequest):
    try:
        meta = create_portfolio(
            portfolio_id=req.id, name=req.name,
            universe=req.universe, starting_capital=req.starting_capital,
        )
        return {"portfolio": asdict(meta), "message": f"Created portfolio '{req.name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{portfolio_id}")
def delete_portfolio(portfolio_id: str):
    archive_portfolio(portfolio_id)
    return {"message": f"Archived portfolio '{portfolio_id}'"}


@router.get("/universes")
def get_universes():
    return {k: {"label": v["label"]} for k, v in UNIVERSE_PRESETS.items()}


@router.get("/overview")
def get_overview():
    """Aggregate view across all portfolios."""
    portfolios = list_portfolios(active_only=True)
    summaries = []
    total_equity = 0
    total_cash = 0

    for p in portfolios:
        try:
            state = load_portfolio_state(fetch_prices=False, portfolio_id=p.id)
            summary = {
                "id": p.id, "name": p.name, "universe": p.universe,
                "equity": state.total_equity, "cash": state.cash,
                "positions_value": state.positions_value,
                "num_positions": state.num_positions,
                "regime": state.regime.value if state.regime else None,
                "paper_mode": state.paper_mode,
            }
            total_equity += state.total_equity
            total_cash += state.cash
            summaries.append(summary)
        except Exception as e:
            summaries.append({"id": p.id, "name": p.name, "universe": p.universe, "error": str(e)})

    return {
        "total_equity": total_equity, "total_cash": total_cash,
        "total_day_pnl": 0, "portfolios": summaries,
    }
