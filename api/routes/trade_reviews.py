"""Trade reviews route — GET closed trade history, POST re-analyze with Claude."""

import json
import math
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "portfolios"

router = APIRouter(prefix="/api/{portfolio_id}")


def _safe_float(val) -> float | None:
    """Return float or None; never returns NaN/Inf."""
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _parse_ai_reasoning(rationale_str) -> str:
    """Extract ai_reasoning from a JSON trade_rationale string."""
    if not rationale_str or not isinstance(rationale_str, str):
        return ""
    try:
        parsed = json.loads(rationale_str)
        return str(parsed.get("ai_reasoning", ""))
    except (json.JSONDecodeError, AttributeError):
        return ""


def _parse_factor_scores(factor_str) -> dict:
    """Parse factor_scores JSON field; return {} on any failure."""
    if not factor_str or not isinstance(factor_str, str):
        return {}
    try:
        result = json.loads(factor_str)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, AttributeError):
        return {}


def _parse_json_list(val) -> str:
    """Parse a JSON-encoded list field from CSV into a readable string."""
    if not val or not isinstance(val, str) or val.strip() in ("", "[]", "null"):
        return ""
    try:
        parsed = json.loads(val)
        if isinstance(parsed, list):
            return " ".join(str(item) for item in parsed if item)
        return str(parsed)
    except (json.JSONDecodeError, AttributeError):
        return str(val)


def _load_closed_trades(portfolio_id: str, data_dir: Path = DATA_DIR) -> list[dict]:
    """Join transactions + post_mortems into enriched closed-trade objects.

    Only fully closed round-trips are returned (BUY matched to SELL, FIFO).
    Open positions are excluded. Missing post-mortem rows are handled gracefully.
    """
    portfolio_dir = data_dir / portfolio_id
    txn_path = portfolio_dir / "transactions.csv"

    if not txn_path.exists():
        return []

    txn_df = pd.read_csv(txn_path, dtype=str)
    if txn_df.empty:
        return []

    buys = txn_df[txn_df["action"] == "BUY"].copy()
    sells = txn_df[txn_df["action"] == "SELL"].copy()

    if buys.empty or sells.empty:
        return []

    # Load post-mortems keyed by (ticker, close_date_prefix)
    pm_map: dict[tuple, dict] = {}
    pm_path = portfolio_dir / "post_mortems.csv"
    if pm_path.exists():
        pm_df = pd.read_csv(pm_path, dtype=str)
        for _, row in pm_df.iterrows():
            key = (str(row.get("ticker", "")), str(row.get("close_date", ""))[:10])
            pm_map[key] = row.to_dict()

    # Build FIFO queue per ticker
    # FIFO queue per ticker — assumes dates are ISO-8601 sortable strings (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    ticker_buys: dict[str, list] = {}
    for _, buy in buys.sort_values("date").iterrows():
        t = str(buy.get("ticker", ""))
        ticker_buys.setdefault(t, []).append(buy)

    results: list[dict] = []

    for _, sell in sells.sort_values("date").iterrows():
        t = str(sell.get("ticker", ""))
        if t not in ticker_buys or not ticker_buys[t]:
            continue
        buy = ticker_buys[t].pop(0)  # FIFO match

        close_date = str(sell["date"])[:10]
        pm = pm_map.get((t, close_date), {})

        entry_price = _safe_float(buy.get("price"))
        exit_price = _safe_float(sell.get("price"))
        shares = _safe_float(buy.get("shares"))

        # P&L from post-mortem if available, else compute as percentage
        pnl_pct = _safe_float(pm.get("pnl_pct"))
        if pnl_pct is None and entry_price is not None and exit_price is not None and entry_price > 0:
            pnl_pct = (exit_price - entry_price) / entry_price * 100

        pnl = _safe_float(pm.get("pnl"))
        if pnl is None and entry_price is not None and exit_price is not None and shares is not None:
            pnl = (exit_price - entry_price) * shares

        holding_days_raw = _safe_float(pm.get("holding_days"))
        holding_days = int(holding_days_raw) if holding_days_raw is not None else 0

        results.append({
            "trade_id": str(buy.get("transaction_id", "")),
            "ticker": t,
            "entry_date": str(buy["date"])[:10],
            "exit_date": close_date,
            "holding_days": holding_days,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "shares": shares,
            "stop_loss": _safe_float(buy.get("stop_loss")),
            "take_profit": _safe_float(buy.get("take_profit")),
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "exit_reason": str(sell.get("reason") or pm.get("exit_reason") or "UNKNOWN"),
            "regime_at_entry": str(buy.get("regime_at_entry") or pm.get("regime_at_entry") or ""),
            "regime_at_exit": str(pm.get("regime_at_exit") or ""),
            "entry_ai_reasoning": _parse_ai_reasoning(buy.get("trade_rationale")),
            "exit_ai_reasoning": _parse_ai_reasoning(sell.get("trade_rationale")),
            "factor_scores": _parse_factor_scores(buy.get("factor_scores")),
            "what_worked": _parse_json_list(pm.get("what_worked")),
            "what_failed": _parse_json_list(pm.get("what_failed")),
            "recommendation": str(pm.get("recommendation") or ""),
            "summary": str(pm.get("summary") or ""),
        })

    # Sort by exit_date descending
    results.sort(key=lambda x: x["exit_date"], reverse=True)
    return results


@router.get("/trade-reviews")
def get_trade_reviews(portfolio_id: str) -> dict:
    """Return all closed trades for a portfolio as enriched objects."""
    trades = _load_closed_trades(portfolio_id)
    return {"trades": trades}
