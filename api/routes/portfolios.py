#!/usr/bin/env python3
"""Portfolio management endpoints."""

import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
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

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge overrides into base dict."""
    result = base.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _config_path(portfolio_id: str) -> Path:
    return DATA_DIR / "portfolios" / portfolio_id / "config.json"

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


class CreatePortfolioRequest(BaseModel):
    id: str
    name: str
    universe: str
    starting_capital: float
    sectors: list[str] | None = None
    trading_style: str | None = None
    ai_config: dict | None = None
    sector_weights: dict[str, int] | None = None


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
            sector_weights=req.sector_weights,
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
            "sector_weights": strategy.sector_weights,
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


@router.get("/{portfolio_id}/config")
def get_portfolio_config(portfolio_id: str):
    """Return the raw config.json for a portfolio."""
    path = _config_path(portfolio_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Portfolio '{portfolio_id}' not found")
    return json.loads(path.read_text())


class UpdateConfigRequest(BaseModel):
    changes: dict


def _trigger_scan(portfolio_id: str):
    """Background task: re-scan watchlist with updated config."""
    try:
        import sys
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from watchlist_manager import WatchlistManager
        state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
        mgr = WatchlistManager(state.config, portfolio_id=portfolio_id)
        mgr.update_watchlist(run_discovery=True)
    except Exception as e:
        print(f"[config rescan] {portfolio_id}: {e}")


@router.put("/{portfolio_id}/config")
def update_portfolio_config(portfolio_id: str, req: UpdateConfigRequest, background_tasks: BackgroundTasks):
    """Deep-merge changes into config.json and trigger a watchlist rescan."""
    path = _config_path(portfolio_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Portfolio '{portfolio_id}' not found")
    current = json.loads(path.read_text())
    updated = _deep_merge(current, req.changes)
    path.write_text(json.dumps(updated, indent=2))
    background_tasks.add_task(_trigger_scan, portfolio_id)
    return {"success": True, "message": "Config updated. Rescanning watchlist in background."}


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
    total_equity = 0.0
    total_cash = 0.0
    total_day_pnl = 0.0
    total_unrealized_pnl = 0.0
    total_positions = 0
    total_all_time_pnl = 0.0
    all_positions = []  # cross-portfolio position list for top/bottom movers

    for p in portfolios:
        try:
            state = load_portfolio_state(fetch_prices=False, portfolio_id=p.id)

            # Compute day P&L from snapshots — only if markets were open today.
            snapshots = state.snapshots
            day_pnl = 0.0
            market_open_today = date.today().weekday() < 5  # Mon=0 … Fri=4
            if market_open_today and len(snapshots) >= 1:
                today_row = snapshots.iloc[-1]
                snapshot_date = str(today_row.get("date", ""))
                if snapshot_date.startswith(date.today().isoformat()):
                    day_pnl = float(today_row.get("day_pnl", 0) or 0)

            # Total return % + all-time P&L from starting capital
            starting_capital = float(state.config.get("starting_capital", 50000))
            total_return_pct = 0.0
            all_time_pnl = 0.0
            if starting_capital > 0:
                total_return_pct = ((state.total_equity - starting_capital) / starting_capital) * 100
                all_time_pnl = state.total_equity - starting_capital

            # Unrealized P&L and deployment
            positions = state.positions
            unrealized_pnl = 0.0
            deployed_pct = 0.0
            if len(positions) > 0 and "unrealized_pnl" in positions.columns:
                unrealized_pnl = float(positions["unrealized_pnl"].sum())
            if state.total_equity > 0:
                deployed_pct = round(state.positions_value / state.total_equity * 100, 1)

            # Collect positions for cross-portfolio movers
            if len(positions) > 0:
                for _, pos in positions.iterrows():
                    try:
                        def _f(v, default=0.0):
                            import math
                            try:
                                fv = float(v)
                                return default if math.isnan(fv) or math.isinf(fv) else fv
                            except Exception:
                                return default
                        all_positions.append({
                            "portfolio_id": p.id,
                            "portfolio_name": p.name,
                            "ticker": str(pos["ticker"]),
                            "pnl": _f(pos.get("unrealized_pnl")),
                            "pnl_pct": _f(pos.get("unrealized_pnl_pct")),
                            "market_value": _f(pos.get("market_value")),
                            "day_change_pct": _f(pos.get("day_change_pct")),
                        })
                    except Exception:
                        pass

            # Sparkline: last 30 daily equity values from snapshots
            sparkline: list[float] = []
            if len(snapshots) >= 2:
                sparkline = [float(v) for v in snapshots["total_equity"].tail(30).tolist()]

            summary = {
                "id": p.id, "name": p.name, "universe": p.universe,
                "equity": state.total_equity, "cash": state.cash,
                "positions_value": state.positions_value,
                "num_positions": state.num_positions,
                "regime": state.regime.value if state.regime else None,
                "paper_mode": state.paper_mode,
                "unrealized_pnl": round(unrealized_pnl, 2),
                "day_pnl": round(day_pnl, 2),
                "all_time_pnl": round(all_time_pnl, 2),
                "total_return_pct": round(total_return_pct, 2),
                "deployed_pct": deployed_pct,
                "sparkline": sparkline,
            }
            total_equity += state.total_equity
            total_cash += state.cash
            total_day_pnl += day_pnl
            total_unrealized_pnl += unrealized_pnl
            total_all_time_pnl += all_time_pnl
            total_positions += state.num_positions
            summaries.append(summary)
        except Exception as e:
            summaries.append({"id": p.id, "name": p.name, "universe": p.universe, "error": str(e)})

    # Sort cross-portfolio positions for top/bottom movers
    valid = [x for x in all_positions if x["pnl_pct"] != 0]
    top_movers = sorted(valid, key=lambda x: x["pnl_pct"], reverse=True)[:5]
    bottom_movers = sorted(valid, key=lambda x: x["pnl_pct"])[:5]

    return {
        "total_equity": round(total_equity, 2),
        "total_cash": round(total_cash, 2),
        "total_day_pnl": round(total_day_pnl, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_all_time_pnl": round(total_all_time_pnl, 2),
        "total_positions": total_positions,
        "top_movers": top_movers,
        "bottom_movers": bottom_movers,
        "all_positions": all_positions,
        "portfolios": summaries,
    }
