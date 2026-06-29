#!/usr/bin/env python3
"""Portfolio management endpoints."""

import json
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, field_validator
from api.deps import serialize, validate_portfolio_id

from portfolio_registry import (
    list_portfolios, create_portfolio,
    archive_portfolio, rename_portfolio, get_default_portfolio_id, UNIVERSE_PRESETS,
)
from strategy_generator import suggest_config_for_dna
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
    ai_driven: bool = False
    strategy_dna: str | None = None

    @field_validator("id")
    @classmethod
    def safe_id(cls, v: str) -> str:
        # Prevents path traversal — id is used to construct filesystem paths.
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", v):
            raise ValueError(
                "id must be alphanumeric/dash/underscore, 1-64 chars, start with alphanumeric"
            )
        return v


@router.get("")
def get_portfolios():
    """List all active portfolios."""
    portfolios = list_portfolios(active_only=True)
    return {
        "portfolios": [asdict(p) for p in portfolios],
        "default_portfolio": get_default_portfolio_id(),
    }


@router.post("")
def create_new_portfolio(req: CreatePortfolioRequest, background_tasks: BackgroundTasks):
    try:
        meta = create_portfolio(
            portfolio_id=req.id, name=req.name,
            universe=req.universe, starting_capital=req.starting_capital,
            sectors=req.sectors, trading_style=req.trading_style,
            ai_config=req.ai_config,
            sector_weights=req.sector_weights,
            ai_driven=req.ai_driven,
            strategy_dna=req.strategy_dna,
        )
        background_tasks.add_task(_trigger_scan, req.id)
        return {"portfolio": asdict(meta), "message": f"Created portfolio '{req.name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/random-dna")
def random_dna():
    """Generate a random creative strategy DNA via Claude."""
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="No API key configured")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    "Generate a creative, specific, and actionable portfolio strategy DNA. "
                    "Be bold and opinionated. Use this structured brief format:\n\n"
                    "Style: [one of: Momentum, Value, Growth, Income, Contrarian, Thematic]\n"
                    "Aggression: [Conservative/Moderate/Aggressive/YOLO]\n"
                    "Cap: [Micro/Small/Mid/Large/All] with dollar range\n"
                    "Hold: [timeframe]\n"
                    "Concentration: [number of positions]\n"
                    "Sectors: [1-3 specific sectors]\n"
                    "Thesis: [2-3 sentences — the unique edge or angle. Be specific about WHAT to buy and WHY. "
                    "Make it something a real trader would actually run. No generic platitudes.]\n\n"
                    "Return ONLY the structured brief, nothing else."
                ),
            }],
        )
        dna = response.content[0].text.strip()
        return {"dna": dna}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SuggestConfigRequest(BaseModel):
    strategy_dna: str
    starting_capital: float


@router.post("/suggest-config")
def suggest_config(req: SuggestConfigRequest):
    """Use AI to suggest portfolio config from strategy DNA."""
    try:
        result = suggest_config_for_dna(req.strategy_dna, req.starting_capital)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{portfolio_id}/config")
def get_portfolio_config(portfolio_id: str = Depends(validate_portfolio_id)):
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
        mgr = WatchlistManager(portfolio_id=portfolio_id)
        mgr.update_watchlist(run_discovery=True)
    except Exception as e:
        print(f"[config rescan] {portfolio_id}: {e}")


@router.put("/{portfolio_id}/config")
def update_portfolio_config(
    req: UpdateConfigRequest,
    background_tasks: BackgroundTasks,
    portfolio_id: str = Depends(validate_portfolio_id),
):
    """Deep-merge changes into config.json and trigger a watchlist rescan."""
    path = _config_path(portfolio_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Portfolio '{portfolio_id}' not found")
    current = json.loads(path.read_text())
    updated = _deep_merge(current, req.changes)
    path.write_text(json.dumps(updated, indent=2))
    background_tasks.add_task(_trigger_scan, portfolio_id)
    return {"success": True, "message": "Config updated. Rescanning watchlist in background."}


class RenamePortfolioRequest(BaseModel):
    name: str


@router.put("/{portfolio_id}/rename")
def rename_portfolio_endpoint(
    req: RenamePortfolioRequest,
    portfolio_id: str = Depends(validate_portfolio_id),
):
    """Update the display name of a portfolio."""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    try:
        rename_portfolio(portfolio_id, req.name.strip())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"success": True, "name": req.name.strip()}


@router.delete("/{portfolio_id}")
def delete_portfolio(portfolio_id: str = Depends(validate_portfolio_id)):
    archive_portfolio(portfolio_id)
    return {"message": f"Archived portfolio '{portfolio_id}'"}


@router.get("/universes")
def get_universes():
    return {k: {"label": v["label"]} for k, v in UNIVERSE_PRESETS.items()}


@router.get("/overview")
def get_overview():
    """Aggregate view across all portfolios."""
    # Determine session status once — gates whether we fetch live prices for the
    # extended-hours split. During regular hours, AH is definitionally 0 so we
    # skip the price fetch entirely. After 4pm/pre-market we fetch (60s cache
    # per portfolio keeps repeat hits cheap).
    session_status = "closed"
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime as _dt, time as _time
        _now_et = _dt.now(ZoneInfo("America/New_York"))
        _is_weekday = _now_et.weekday() < 5
        _t = _now_et.time()
        if _is_weekday and _time(9, 30) <= _t <= _time(16, 0):
            session_status = "regular_hours"
        elif _is_weekday and _time(16, 0) < _t <= _time(20, 0):
            session_status = "after_hours"
        elif _is_weekday and _time(4, 0) <= _t < _time(9, 30):
            session_status = "pre_market"
        else:
            session_status = "closed"
    except Exception:
        session_status = "regular_hours" if date.today().weekday() < 5 else "closed"

    needs_live_prices = session_status in ("after_hours", "pre_market")

    portfolios = list_portfolios(active_only=True)

    def _f(v, default=0.0):
        try:
            fv = float(v)
            return default if math.isnan(fv) or math.isinf(fv) else fv
        except Exception:
            return default

    def _load_one(p):
        """Load and summarise a single portfolio. Runs in a thread pool."""
        try:
            state = load_portfolio_state(fetch_prices=needs_live_prices, portfolio_id=p.id)

            snapshots = state.snapshots
            day_pnl = 0.0
            market_open_today = date.today().weekday() < 5
            if market_open_today and len(snapshots) >= 1:
                today_row = snapshots.iloc[-1]
                if str(today_row.get("date", "")).startswith(date.today().isoformat()):
                    day_pnl = float(today_row.get("day_pnl", 0) or 0)

            regular_session_pnl = day_pnl
            extended_hours_pnl = 0.0
            if (
                needs_live_prices
                and not state.positions.empty
                and "extended_hours_change" in state.positions.columns
            ):
                extended_hours_pnl = float(state.positions["extended_hours_change"].fillna(0).sum())

            starting_capital = float(state.config.get("starting_capital", 50000))
            positions = state.positions
            unrealized_pnl = 0.0
            if len(positions) > 0 and "unrealized_pnl" in positions.columns:
                unrealized_pnl = float(positions["unrealized_pnl"].sum())

            realized_pnl = 0.0
            txns = state.transactions
            if not txns.empty and "action" in txns.columns:
                _holdings: dict = {}
                for _, tx in txns.sort_values("date").iterrows():
                    _ticker = str(tx.get("ticker", ""))
                    _action = str(tx.get("action", ""))
                    _shares = float(tx.get("shares", 0) or 0)
                    _total = float(tx.get("total_value", 0) or 0)
                    if _action == "BUY" and _shares > 0:
                        _ps, _pc = _holdings.get(_ticker, (0.0, 0.0))
                        _holdings[_ticker] = (_ps + _shares, _pc + _total)
                    elif _action == "SELL" and _shares > 0:
                        if _ticker in _holdings and _holdings[_ticker][0] > 0:
                            _hs, _hc = _holdings[_ticker]
                            _avg = _hc / _hs
                            _cost = _avg * _shares
                            realized_pnl += _total - _cost
                            _holdings[_ticker] = (max(0.0, _hs - _shares), max(0.0, _hc - _cost))

            all_time_pnl = round(realized_pnl + unrealized_pnl, 2)
            total_return_pct = round((all_time_pnl / starting_capital) * 100, 2) if starting_capital > 0 else 0.0

            deployed_pct = 0.0
            if state.total_equity > 0:
                deployed_pct = round(state.positions_value / state.total_equity * 100, 1)

            pos_rows = []
            if len(positions) > 0 and not p.exclude_from_aggregates and not state.paper_mode:
                for _, pos in positions.iterrows():
                    try:
                        pos_rows.append({
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

            sparkline: list[float] = []
            equity_curve: list[float] = []
            if len(snapshots) >= 2:
                sparkline = [float(v) for v in snapshots["total_equity"].tail(30).tolist()]
            if len(snapshots) >= 2 and "day_pnl_pct" in snapshots.columns:
                equity_curve = [float(v) for v in snapshots["day_pnl_pct"].tail(60).tolist()]

            summary = {
                "id": p.id, "name": p.name, "universe": p.universe,
                "equity": state.total_equity, "cash": state.cash,
                "positions_value": state.positions_value,
                "num_positions": state.num_positions,
                "regime": state.regime.value if state.regime else None,
                "paper_mode": state.paper_mode,
                "unrealized_pnl": round(unrealized_pnl, 2),
                "day_pnl": round(day_pnl, 2),
                "session_status": session_status,
                "regular_session_pnl": round(regular_session_pnl, 2),
                "extended_hours_pnl": round(extended_hours_pnl, 2),
                "all_time_pnl": round(all_time_pnl, 2),
                "total_return_pct": round(total_return_pct, 2),
                "deployed_pct": deployed_pct,
                "sparkline": sparkline,
                "equity_curve": equity_curve,
                "exclude_from_aggregates": p.exclude_from_aggregates,
            }
            contributes = not p.exclude_from_aggregates and not state.paper_mode
            return summary, pos_rows, state, starting_capital, unrealized_pnl, all_time_pnl, day_pnl, regular_session_pnl, extended_hours_pnl, contributes
        except Exception as e:
            return {"id": p.id, "name": p.name, "universe": p.universe, "error": str(e)}, [], None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False

    # Fetch all portfolios in parallel — wall-clock time = slowest single portfolio
    # instead of sum of all, which was causing the 25-30s overview timeout.
    summaries = []
    all_positions = []
    total_equity = 0.0
    total_cash = 0.0
    total_day_pnl = 0.0
    total_regular_session_pnl = 0.0
    total_extended_hours_pnl = 0.0
    total_unrealized_pnl = 0.0
    total_positions = 0
    total_all_time_pnl = 0.0
    total_starting_capital = 0.0

    with ThreadPoolExecutor(max_workers=min(len(portfolios), 8)) as pool:
        futures = {pool.submit(_load_one, p): p for p in portfolios}
        for fut in as_completed(futures):
            result = fut.result()
            summary, pos_rows, state, starting_capital, unrealized_pnl, all_time_pnl, day_pnl, regular_pnl, eh_pnl, contributes = result
            summaries.append(summary)
            all_positions.extend(pos_rows)
            if contributes and state is not None:
                total_equity += state.total_equity
                total_cash += state.cash
                total_day_pnl += day_pnl
                total_regular_session_pnl += regular_pnl
                total_extended_hours_pnl += eh_pnl
                total_unrealized_pnl += unrealized_pnl
                total_all_time_pnl += all_time_pnl
                total_starting_capital += starting_capital
                total_positions += state.num_positions

    # Restore deterministic portfolio ordering (futures complete in arrival order).
    portfolio_order = {p.id: i for i, p in enumerate(portfolios)}
    summaries.sort(key=lambda s: portfolio_order.get(s.get("id", ""), 999))

    # Sort cross-portfolio positions for top/bottom movers
    valid = [x for x in all_positions if x["pnl_pct"] != 0]
    top_movers = sorted(valid, key=lambda x: x["pnl_pct"], reverse=True)[:5]
    bottom_movers = sorted(valid, key=lambda x: x["pnl_pct"])[:5]

    return {
        "total_equity": round(total_equity, 2),
        "total_cash": round(total_cash, 2),
        "total_day_pnl": round(total_day_pnl, 2),
        "session_status": session_status,
        "total_regular_session_pnl": round(total_regular_session_pnl, 2),
        "total_extended_hours_pnl": round(total_extended_hours_pnl, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_all_time_pnl": round(total_all_time_pnl, 2),
        "total_starting_capital": round(total_starting_capital, 2),
        "total_return_pct": round((total_all_time_pnl / total_starting_capital * 100) if total_starting_capital > 0 else 0.0, 2),
        # Return on Invested Capital — P&L over capital currently deployed
        # (equity - cash = positions value), vs total_return_pct which is over
        # total capital. Higher than total return by the cash-drag amount.
        "total_roic_pct": round((total_all_time_pnl / (total_equity - total_cash) * 100) if (total_equity - total_cash) > 0 else 0.0, 2),
        "total_positions": total_positions,
        "top_movers": top_movers,
        "bottom_movers": bottom_movers,
        "all_positions": all_positions,
        "portfolios": summaries,
    }
