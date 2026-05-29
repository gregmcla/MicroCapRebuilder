#!/usr/bin/env python3
"""Aggregation logic for the Daily Digest home screen.

Composes existing PortfolioState data into a single payload for GET /api/digest.
Scopes to ACTIVE + LIVE-mode portfolios (filtering happens in build_digest);
respects exclude_from_aggregates for book totals.
"""
import math
from pathlib import Path
import pandas as pd


def _f(v, default=0.0):
    """NaN/inf-safe float coercion (mirrors api/routes/portfolios.py)."""
    try:
        fv = float(v)
        return default if math.isnan(fv) or math.isinf(fv) else fv
    except Exception:
        return default


def _roll_up_book(rows: list[dict]) -> dict:
    """rows: per-portfolio dicts with equity/day_pnl/total_return_pct/exclude."""
    included = [r for r in rows if not r.get("exclude")]
    equity = round(sum(_f(r["equity"]) for r in included), 2)
    day_pnl = round(sum(_f(r["day_pnl"]) for r in included), 2)
    green = sum(1 for r in included if _f(r["total_return_pct"]) >= 0)  # breakeven (0%) counts as green
    red = sum(1 for r in included if _f(r["total_return_pct"]) < 0)
    prev_equity = equity - day_pnl
    day_pnl_pct = round((day_pnl / prev_equity * 100), 2) if prev_equity > 0 else 0.0  # 0.0 when prev_equity <= 0 (e.g. equity wiped by a large loss)
    return {
        "equity": equity,
        "day_pnl": day_pnl,
        "day_pnl_pct": day_pnl_pct,
        "health": {"green": green, "red": red},
    }


def derive_trend(sparkline: list[float], vs_bench_pct: float) -> str:
    """ahead / flat / fading from 30d slope + benchmark alpha.

    Slope = last vs first over the series. Combined with alpha sign:
      - clearly positive slope OR strong positive alpha -> "ahead"
      - clearly negative slope OR strong negative alpha -> "fading"
      - otherwise -> "flat"
    """
    if not sparkline or len(sparkline) < 2:
        return "flat"
    first, last = _f(sparkline[0]), _f(sparkline[-1])
    slope_pct = ((last - first) / first * 100) if first > 0 else 0.0
    score = slope_pct + _f(vs_bench_pct)
    if score >= 4.0:
        return "ahead"
    if score <= -4.0:
        return "fading"
    return "flat"


_RANGE_DAYS = {"1W": 7, "1M": 30, "3M": 90, "YTD": None, "ALL": None}


def _fetch_spy_series(start: str, end: str) -> "pd.Series":
    """SPY daily closes between start/end (inclusive). Isolated for test mocking."""
    from yf_session import cached_download
    df = cached_download("SPY", start=start, end=end)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
    close.index = pd.to_datetime(close.index)
    return close


def build_book_curve(snapshots_by_pid: dict, range_key: str = "3M") -> dict:
    """Sum per-portfolio total_equity by date, normalize to 100, overlay SPY."""
    frames = []
    for pid, df in snapshots_by_pid.items():
        if df is None or df.empty or "total_equity" not in df.columns:
            continue
        s = df.set_index(pd.to_datetime(df["date"]))["total_equity"].astype(float)
        frames.append(s.rename(pid))
    if not frames:
        return {"range": range_key, "book": [], "spy": []}
    book = pd.concat(frames, axis=1).sort_index().ffill().dropna(how="all").sum(axis=1)

    days = _RANGE_DAYS.get(range_key)
    if days:
        book = book.tail(days)

    if book.empty:
        return {"range": range_key, "book": [], "spy": []}

    base = book.iloc[0] or 1.0
    book_norm = (book / base * 100).round(3)

    start = book.index[0].strftime("%Y-%m-%d")
    end = book.index[-1].strftime("%Y-%m-%d")
    spy_raw = _fetch_spy_series(start, end)
    if spy_raw.empty:
        spy_norm = []
    else:
        spy_aligned = spy_raw.reindex(book.index, method="ffill").bfill()
        spy_base = spy_aligned.iloc[0] or 1.0
        spy_norm = (spy_aligned / spy_base * 100).round(3).tolist()

    return {"range": range_key, "book": book_norm.tolist(), "spy": spy_norm}


def bench_symbol(config: dict) -> str:
    """Each portfolio's configured benchmark; default SPY."""
    return config.get("benchmark_symbol") or "SPY"


def _fetch_spy_series_for(symbol: str, start: str, end: str) -> "pd.Series":
    """Daily closes for an arbitrary benchmark symbol. Isolated for mocking."""
    from yf_session import cached_download
    df = cached_download(symbol, start=start, end=end)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    return (df["Close"] if "Close" in df.columns else df.iloc[:, 0]).astype(float)


def _bench_return_pct(symbol: str, snapshots: "pd.DataFrame") -> float:
    """Benchmark total return % over the snapshot window. Isolated for mocking."""
    if snapshots is None or snapshots.empty:
        return 0.0
    start = pd.to_datetime(snapshots["date"]).min().strftime("%Y-%m-%d")
    end = pd.to_datetime(snapshots["date"]).max().strftime("%Y-%m-%d")
    s = _fetch_spy_series_for(symbol, start, end)
    if s is None or len(s) < 2:
        return 0.0
    first, last = float(s.iloc[0]), float(s.iloc[-1])
    return round((last - first) / first * 100, 2) if first > 0 else 0.0


def vs_bench_pct(total_return_pct: float, bench: str, snapshots: "pd.DataFrame") -> float:
    """Alpha = portfolio total return - benchmark return over the same window."""
    return round(_f(total_return_pct) - _bench_return_pct(bench, snapshots), 2)


def _compute_all_time_pnl(state) -> float:
    """Transaction-replay all-time P&L (mirrors api/routes/portfolios.py lines 257-277).

    PortfolioState has no .all_time_pnl attribute, so we replay the ledger.
    """
    positions = state.positions
    unrealized_pnl = 0.0
    if positions is not None and len(positions) > 0 and "unrealized_pnl" in positions.columns:
        unrealized_pnl = float(positions["unrealized_pnl"].sum())

    realized_pnl = 0.0
    txns = state.transactions
    if txns is not None and not txns.empty and "action" in txns.columns:
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

    return round(realized_pnl + unrealized_pnl, 2)


def _book_vs_spy(curve: dict) -> float:
    b, s = curve.get("book", []), curve.get("spy", [])
    if not b or not s:
        return 0.0
    return round((b[-1] - 100) - (s[-1] - 100), 2)


def _book_regime() -> dict:
    """Best-effort regime detection. Never raises."""
    try:
        from market_regime import get_regime_analysis
        analysis = get_regime_analysis()
        label = getattr(analysis.regime, "value", str(analysis.regime))
        return {
            "label": label,
            "risk": 0,       # risk/risk_prev are placeholders (0 = not wired); frontend hides the clause when risk == 0
            "risk_prev": 0,  # risk/risk_prev are placeholders (0 = not wired); frontend hides the clause when risk == 0
        }
    except Exception:
        return {"label": "UNKNOWN", "risk": 0, "risk_prev": 0}


def build_digest(range_key: str = "3M") -> dict:
    """Top-level: load active+live portfolios, assemble book + portfolios + recap.

    Lazy-imports portfolio_state/registry so unit tests of helpers don't require yfinance.
    """
    from datetime import date, timedelta
    from portfolio_registry import list_portfolios
    from portfolio_state import load_portfolio_state

    portfolios = list_portfolios(active_only=True)
    rows, comp, snaps_by_pid, txns_by_pid = [], [], {}, {}
    movers = []
    prev_close = (date.today() - timedelta(days=1)).isoformat()

    for p in portfolios:
        try:
            state = load_portfolio_state(fetch_prices=False, portfolio_id=p.id)
            # Live-mode only: paper-mode portfolios excluded entirely (not shown, not summed).
            if state.paper_mode:
                continue
            snaps = state.snapshots
            spark = [float(v) for v in snaps["total_equity"].tail(30).tolist()] if (snaps is not None and len(snaps) >= 2) else []
            day_pnl = 0.0
            if snaps is not None and len(snaps) >= 1:
                row = snaps.iloc[-1]
                if str(row.get("date", "")).startswith(date.today().isoformat()):
                    day_pnl = _f(row.get("day_pnl"))
            starting = _f(state.config.get("starting_capital", 50000), 50000)
            # PortfolioState has no .all_time_pnl — compute via transaction replay
            all_time_pnl = _compute_all_time_pnl(state)
            total_ret = round((all_time_pnl / starting * 100), 2) if starting else 0.0
            bench = bench_symbol(state.config)
            alpha = vs_bench_pct(total_ret, bench, snaps)
            rows.append({"id": p.id, "equity": state.total_equity, "day_pnl": day_pnl,
                         "total_return_pct": total_ret, "exclude": p.exclude_from_aggregates})
            comp.append({"id": p.id, "name": p.name,
                         "strategy": state.config.get("strategy", {}).get("trading_style", ""),
                         "equity": round(_f(state.total_equity), 2),
                         "day_pct": round(day_pnl / state.total_equity * 100, 2) if state.total_equity else 0.0,
                         "total_pct": total_ret, "vs_bench_pct": alpha, "bench_symbol": bench,
                         "sparkline": spark, "trend": derive_trend(spark, alpha)})
            snaps_by_pid[p.id] = snaps
            txns_by_pid[p.id] = state.transactions
            # Collect movers inline — avoids a second full portfolio load in _book_movers
            pos = state.positions
            if pos is not None and len(pos) > 0 and "day_change_pct" in pos.columns:
                for _, r in pos.iterrows():
                    movers.append({"ticker": str(r["ticker"]), "pct": _f(r.get("day_change_pct"))})
        except Exception as e:
            comp.append({"id": p.id, "name": p.name, "error": str(e)})

    book = _roll_up_book(rows)
    book["curve"] = build_book_curve(snaps_by_pid, range_key)
    book["vs_spy_alltime_pct"] = _book_vs_spy(book["curve"])
    book["vs_spy_today_pct"] = 0.0  # TODO: intraday SPY comparison not yet computed
    regime = _book_regime()
    recap = build_recap(txns_by_pid, since=prev_close, movers=movers, regime=regime)
    comp.sort(key=lambda c: c.get("vs_bench_pct", -999), reverse=True)
    return {"book": book, "portfolios": comp, "recap": recap}


def compute_posture(regime: str, deployed_pct: float, book_alpha: float) -> dict:
    """Deterministic 0..1 posture (0=defensive, 1=aggressive) + label."""
    regime_base = {"BULL": 0.72, "SIDEWAYS": 0.5, "BEAR": 0.28}.get((regime or "").upper(), 0.5)
    exposure = max(0.0, min(1.0, _f(deployed_pct) / 100.0))
    alpha_tilt = max(-0.1, min(0.1, _f(book_alpha) / 100.0))
    value = max(0.0, min(1.0, regime_base * 0.6 + exposure * 0.4 + alpha_tilt))
    if value >= 0.6:
        label = "Risk-on · leaning momentum"
    elif value <= 0.4:
        label = "Defensive · capital-preserving"
    else:
        label = "Balanced · selective"
    return {"value": round(value, 2), "label": label}


def build_recap(txns_by_pid: dict, since: str, movers: list, regime: dict) -> dict:
    """Classify trades since `since` (prior session close, YYYY-MM-DD) into buys/exits."""
    buys, exits = [], []
    for pid, df in txns_by_pid.items():
        if df is None or df.empty or "action" not in df.columns:
            continue
        recent = df[df["date"].astype(str) >= since]
        for _, tx in recent.iterrows():
            entry = {"pid": pid, "ticker": str(tx.get("ticker", "")),
                     "value": _f(tx.get("total_value")), "reason": str(tx.get("reason", ""))}
            if str(tx.get("action")) == "BUY":
                buys.append(entry)
            elif str(tx.get("action")) == "SELL":
                exits.append(entry)
    return {
        "buys":  {"count": len(buys),  "items": buys,  "deployed": round(sum(b["value"] for b in buys), 2)},
        "exits": {"count": len(exits), "items": exits},
        "swings": sorted(movers, key=lambda m: abs(_f(m.get("pct"))), reverse=True)[:4],
        "regime": regime,
    }
