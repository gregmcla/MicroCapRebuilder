"""Portfolio state endpoints."""

import threading
import time
from datetime import date

from fastapi import APIRouter
from api.deps import serialize

from portfolio_state import load_portfolio_state, save_positions, save_snapshot, invalidate_regime_cache

# In-memory cache for ticker company info (name + description) — 24hr TTL
_ticker_info_cache: dict[str, tuple[dict, float]] = {}
_TICKER_INFO_TTL = 86400

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

    # CAGR — annualized total return using snapshot history (252 trading days/yr)
    cagr_pct = 0.0
    snaps = state.snapshots
    if not snaps.empty and "total_equity" in snaps.columns and len(snaps) >= 2:
        _start_eq = float(snaps.iloc[0]["total_equity"])
        _end_eq = float(snaps.iloc[-1]["total_equity"])
        _days = len(snaps)
        if _start_eq > 0 and _days > 0:
            _years = _days / 252
            cagr_pct = round(((_end_eq / _start_eq) ** (1 / _years) - 1) * 100, 2)

    # Realized P&L: replay buy→sell pairs from transaction history.
    # Only counts trades where we have a complete BUY record — excludes
    # manual close-all remnants from before transaction tracking began.
    realized_pnl = 0.0
    txns = state.transactions
    if not txns.empty and "action" in txns.columns:
        _holdings: dict = {}  # ticker -> (shares, total_cost)
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
    realized_pnl = round(realized_pnl, 2)

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
        "realized_pnl": realized_pnl,
        "cagr_pct": cagr_pct,
        "starting_capital": starting_capital,
        "timestamp": serialize(state.timestamp),
    }


@router.get("/position/{ticker}/info")
def get_ticker_info(portfolio_id: str, ticker: str):
    """Company name and short description for a ticker."""
    now = time.time()
    cached = _ticker_info_cache.get(ticker)
    if cached and now - cached[1] < _TICKER_INFO_TTL:
        return cached[0]

    result: dict = {"ticker": ticker, "name": ticker, "description": None, "sector": None}

    def fetch():
        try:
            import yfinance as yf
            import math
            info = yf.Ticker(ticker).info

            def _safe(v, default=None):
                try:
                    if v is None:
                        return default
                    fv = float(v)
                    return default if math.isnan(fv) or math.isinf(fv) else fv
                except Exception:
                    return default

            result["name"] = info.get("longName") or info.get("shortName") or ticker
            result["sector"] = info.get("sector") or None
            result["industry"] = info.get("industry") or None
            result["website"] = info.get("website") or None
            result["employees"] = info.get("fullTimeEmployees") or None
            result["market_cap"] = _safe(info.get("marketCap"))
            result["trailing_pe"] = _safe(info.get("trailingPE"))
            result["forward_pe"] = _safe(info.get("forwardPE"))
            result["week_52_high"] = _safe(info.get("fiftyTwoWeekHigh"))
            result["week_52_low"] = _safe(info.get("fiftyTwoWeekLow"))
            result["analyst_target"] = _safe(info.get("targetMeanPrice"))
            result["analyst_rating"] = info.get("recommendationKey") or None
            result["analyst_count"] = info.get("numberOfAnalystOpinions") or None
            result["dividend_yield"] = _safe(info.get("dividendYield"))
            result["beta"] = _safe(info.get("beta"))

            summary = info.get("longBusinessSummary") or ""
            if len(summary) > 300:
                truncated = summary[:300]
                last_period = truncated.rfind(". ")
                summary = truncated[: last_period + 1] if last_period > 80 else truncated.rstrip() + "…"
            result["description"] = summary or None
        except Exception:
            pass

    t = threading.Thread(target=fetch, daemon=True)
    t.start()
    t.join(timeout=15)

    # Only cache if we got real data — don't poison cache with empty defaults
    # (empty result happens when yfinance is rate-limited during concurrent scans)
    if result.get("name") != ticker or result.get("sector") is not None:
        _ticker_info_cache[ticker] = (result, now)
    return result


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
