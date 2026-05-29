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
