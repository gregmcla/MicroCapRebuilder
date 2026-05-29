#!/usr/bin/env python3
"""Aggregation logic for the Daily Digest home screen.

Composes existing PortfolioState data into a single payload for GET /api/digest.
Scopes to ACTIVE + LIVE-mode portfolios (filtering happens in build_digest);
respects exclude_from_aggregates for book totals.
"""
import math
from pathlib import Path


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
