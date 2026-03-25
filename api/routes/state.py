"""Portfolio state endpoints."""

import threading
import time
from datetime import date

import pandas as pd
from fastapi import APIRouter
from api.deps import serialize

from portfolio_state import load_portfolio_state, save_positions, save_snapshot, invalidate_regime_cache

# In-memory cache for ticker company info (name + description) — 24hr TTL
_ticker_info_cache: dict[str, tuple[dict, float]] = {}
_TICKER_INFO_TTL = 86400

router = APIRouter(prefix="/api/{portfolio_id}")


def _compute_benchmark_comparison(snapshots, total_return_pct: float) -> dict:
    """Compute since-inception returns for SPX, NDX, RUT and alpha vs portfolio."""
    try:
        import pandas as pd
        from yf_session import cached_download
    except ImportError:
        return {}

    if snapshots is None or (hasattr(snapshots, 'empty') and snapshots.empty):
        return {}
    if "date" not in snapshots.columns or len(snapshots) < 1:
        return {}

    inception_date = str(snapshots.iloc[0]["date"])[:10]  # YYYY-MM-DD

    benchmarks = [("spx", "^GSPC"), ("ndx", "^NDX"), ("rut", "^RUT")]

    import concurrent.futures

    def _fetch_one(label_symbol):
        label, symbol = label_symbol
        r = {f"{label}_return_pct": None, f"{label}_alpha": None}
        try:
            df = cached_download(symbol, start=inception_date, progress=False, auto_adjust=True)
            if df.empty:
                return r
            if isinstance(df.columns, pd.MultiIndex):
                if ("Close", symbol) in df.columns:
                    closes = df[("Close", symbol)]
                elif "Close" in df.columns.get_level_values(0):
                    closes = df["Close"].iloc[:, 0]
                else:
                    return r
            else:
                if "Close" not in df.columns:
                    return r
                closes = df["Close"]
            closes = closes.dropna()
            if len(closes) < 2:
                return r
            inception_price = float(closes.iloc[0])
            current_price = float(closes.iloc[-1])
            if inception_price <= 0:
                return r
            bm_return = (current_price - inception_price) / inception_price * 100
            r[f"{label}_return_pct"] = round(bm_return, 2)
            r[f"{label}_alpha"] = round(total_return_pct - bm_return, 2)
        except Exception:
            pass
        return r

    result = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_map = {executor.submit(_fetch_one, b): b for b in benchmarks}
        try:
            for future in concurrent.futures.as_completed(future_map, timeout=8):
                try:
                    result.update(future.result())
                except Exception:
                    label = future_map[future][0]
                    result[f"{label}_return_pct"] = None
                    result[f"{label}_alpha"] = None
        except concurrent.futures.TimeoutError:
            for future, b in future_map.items():
                label = b[0]
                if f"{label}_return_pct" not in result:
                    result[f"{label}_return_pct"] = None
                    result[f"{label}_alpha"] = None

    return result


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

    # Benchmark comparison — since-inception returns for SPX, NDX, RUT
    bm = _compute_benchmark_comparison(snapshots, total_return_pct)

    # Realized P&L: replay buy→sell pairs from transaction history.
    # Only counts trades where we have a complete BUY record — excludes
    # manual close-all remnants from before transaction tracking began.
    # Also builds per-trade P&L map for display in the activity feed.
    realized_pnl = 0.0
    trade_pnl: dict[str, tuple[float, float, float]] = {}  # transaction_id -> (pnl_dollar, pnl_pct, entry_price)
    txns = state.transactions
    if not txns.empty and "action" in txns.columns:
        _holdings: dict = {}  # ticker -> (shares, total_cost)
        for _, tx in txns.sort_values("date").iterrows():
            _tid = str(tx.get("transaction_id", ""))
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
                    _pnl = _total - _cost
                    _pnl_pct = (_pnl / _cost) * 100 if _cost > 0 else 0.0
                    realized_pnl += _pnl
                    _holdings[_ticker] = (max(0.0, _hs - _shares), max(0.0, _hc - _cost))
                    if _tid:
                        trade_pnl[_tid] = (round(_pnl, 2), round(_pnl_pct, 2), round(_avg, 2))
    realized_pnl = round(realized_pnl, 2)

    # Re-compute total return from actual P&L to exclude accounting artifacts
    # (equity-minus-starting-capital can be inflated by reconciliation entries).
    if starting_capital > 0:
        _unrealized = float(positions["unrealized_pnl"].sum()) if not positions.empty and "unrealized_pnl" in positions.columns else 0.0
        total_return_pct = round(((realized_pnl + _unrealized) / starting_capital) * 100, 2)
        all_time_pnl = round(realized_pnl + _unrealized, 2)

    # Build position_rationales: ticker -> parsed trade_rationale JSON for active positions.
    # Allows the UI to display "why was this trade opened" when clicking a position.
    import json as _json
    position_rationales: dict = {}
    if not positions.empty and not txns.empty and "trade_rationale" in txns.columns:
        held_tickers = positions["ticker"].tolist() if "ticker" in positions.columns else []
        for _ticker in held_tickers:
            _buy_txns = txns[
                (txns["ticker"] == _ticker) &
                (txns["action"] == "BUY") &
                (txns["trade_rationale"].notna()) &
                (txns["trade_rationale"] != "")
            ]
            if not _buy_txns.empty:
                _raw = str(_buy_txns.iloc[-1]["trade_rationale"])
                try:
                    position_rationales[_ticker] = _json.loads(_raw)
                except Exception:
                    pass

    # Annotate transactions with per-trade P&L before serializing
    transactions_out = transactions.tail(50).copy()
    if trade_pnl and "transaction_id" in transactions_out.columns:
        transactions_out["realized_pnl"] = transactions_out["transaction_id"].apply(
            lambda tid: trade_pnl.get(str(tid), (None, None, None))[0]
        )
        transactions_out["realized_pnl_pct"] = transactions_out["transaction_id"].apply(
            lambda tid: trade_pnl.get(str(tid), (None, None, None))[1]
        )
        transactions_out["entry_price"] = transactions_out["transaction_id"].apply(
            lambda tid: trade_pnl.get(str(tid), (None, None, None))[2]
        )

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
        "transactions": serialize(transactions_out),
        "snapshots": serialize(snapshots.tail(30)),
        "regime": serialize(state.regime),
        "regime_analysis": serialize(state.regime_analysis),
        "positions_value": state.positions_value,
        "total_equity": state.total_equity,
        "num_positions": state.num_positions,
        "config": state.config,
        "stale_alerts": state.stale_alerts,
        "paper_mode": state.paper_mode,
        "ai_driven": bool(state.config.get("ai_driven", False)),
        "price_failures": state.price_failures,
        "day_pnl": day_pnl,
        "day_pnl_pct": day_pnl_pct,
        "total_return_pct": total_return_pct,
        "all_time_pnl": round(all_time_pnl, 2),
        "realized_pnl": realized_pnl,
        "cagr_pct": cagr_pct,
        "spx_return_pct": bm.get("spx_return_pct"),
        "ndx_return_pct": bm.get("ndx_return_pct"),
        "rut_return_pct": bm.get("rut_return_pct"),
        "spx_alpha": bm.get("spx_alpha"),
        "ndx_alpha": bm.get("ndx_alpha"),
        "rut_alpha": bm.get("rut_alpha"),
        "starting_capital": starting_capital,
        "position_rationales": position_rationales,
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


@router.get("/position/{ticker}/rationale")
def get_position_rationale(portfolio_id: str, ticker: str):
    """Trade rationale for a current position (from most recent BUY transaction)."""
    import json as _json
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    txns = state.transactions
    if txns.empty or "trade_rationale" not in txns.columns:
        return {}
    buy_txns = txns[
        (txns["ticker"] == ticker) &
        (txns["action"] == "BUY") &
        (txns["trade_rationale"].notna()) &
        (txns["trade_rationale"] != "")
    ]
    if buy_txns.empty:
        return {}
    raw = str(buy_txns.iloc[-1]["trade_rationale"])
    try:
        return _json.loads(raw)
    except Exception:
        return {}


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
