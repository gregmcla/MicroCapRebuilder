#!/usr/bin/env python3
"""Portfolio management endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.deps import serialize

from portfolio_registry import (
    list_portfolios, create_portfolio,
    archive_portfolio, get_default_portfolio_id, UNIVERSE_PRESETS,
    TRADING_STYLES, SECTOR_ETF_MAP, ALL_SECTORS,
)
from strategy_generator import generate_strategy
from portfolio_state import load_portfolio_state
from dataclasses import asdict

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


class CreatePortfolioRequest(BaseModel):
    id: str
    name: str
    universe: str
    starting_capital: float
    sectors: list[str] | None = None
    trading_style: str | None = None
    ai_config: dict | None = None


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
            sectors=req.sectors, trading_style=req.trading_style,
            ai_config=req.ai_config,
        )
        return {"portfolio": asdict(meta), "message": f"Created portfolio '{req.name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class GenerateStrategyRequest(BaseModel):
    prompt: str
    universe: str
    starting_capital: float


@router.post("/generate-strategy")
def generate_strategy_endpoint(req: GenerateStrategyRequest):
    """Use AI to generate a portfolio strategy from a text description."""
    try:
        strategy = generate_strategy(req.prompt, req.universe, req.starting_capital)
        return {
            "sectors": strategy.sectors,
            "trading_style": strategy.trading_style,
            "scoring_weights": strategy.scoring_weights,
            "stop_loss_pct": strategy.stop_loss_pct,
            "risk_per_trade_pct": strategy.risk_per_trade_pct,
            "max_position_pct": strategy.max_position_pct,
            "scan_types": strategy.scan_types,
            "etf_sources": strategy.etf_sources,
            "strategy_name": strategy.strategy_name,
            "rationale": strategy.rationale,
            "prompt": strategy.prompt,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading-styles")
def get_trading_styles():
    return {k: {"label": v["label"], "description": v["description"]} for k, v in TRADING_STYLES.items()}


@router.get("/sectors")
def get_sectors():
    return {"sectors": ALL_SECTORS}


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
