"""Build rich per-trade detail block for Claude's analyze prompt.

Replaces the aggregate-stats trade history block with the last N closed trades
shown one-by-one: entry reasoning, factor scores at entry, regime, outcome, exit
summary, pattern tags. Lets Claude reason about its prior decisions specifically.
"""
import ast
import json
import os
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd


def _data_dir() -> Path:
    return Path(os.environ.get("MCR_DATA_DIR") or (Path(__file__).parent.parent / "data"))


def _parse_list(raw) -> list:
    """Handle Python list-repr ('[a, b]') and JSON list strings."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, list):
        return raw
    s = str(raw).strip()
    if not s or s in ("[]", "{}"):
        return []
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        try:
            v = ast.literal_eval(s)
            return v if isinstance(v, list) else []
        except (ValueError, SyntaxError):
            return []


def _parse_json(raw) -> dict:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return {}
    s = str(raw).strip()
    if not s or s == "{}":
        return {}
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return {}


def get_recent_trade_details(portfolio_id: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Return the last N closed trades with rich per-trade detail.

    Joins transactions.csv (BUY rows for entry context) with post_mortems.csv
    (exit context) using buy_transaction_id — avoids the ticker-only matching
    bug that plagues factor_learning.py.
    """
    pdir = _data_dir() / "portfolios" / portfolio_id
    tx_file = pdir / "transactions.csv"
    pm_file = pdir / "post_mortems.csv"
    if not tx_file.exists() or not pm_file.exists():
        return []

    try:
        tx = pd.read_csv(tx_file, dtype=str)
        pm = pd.read_csv(pm_file, dtype=str)
    except Exception:
        return []
    if pm.empty:
        return []

    pm["close_date"] = pd.to_datetime(pm["close_date"], errors="coerce", format="mixed")
    pm = pm.sort_values("close_date", ascending=False).head(limit)

    buys = tx[tx["action"] == "BUY"].set_index("transaction_id", drop=False)
    out: List[Dict[str, Any]] = []
    for _, row in pm.iterrows():
        buy_id = row.get("buy_transaction_id", "")
        buy = buys.loc[buy_id] if buy_id in buys.index else None

        factor_scores = _parse_json(buy["factor_scores"]) if buy is not None else {}
        top_factors = sorted(
            ((k, int(float(v))) for k, v in factor_scores.items() if v not in (None, "")),
            key=lambda kv: -kv[1],
        )[:3]

        rationale = _parse_json(buy["trade_rationale"]) if buy is not None else {}
        entry_reasoning = rationale.get("ai_reasoning") or rationale.get("quant_reason") or ""

        out.append({
            "ticker": row["ticker"],
            "entry_date": str(buy["date"])[:10] if buy is not None else "",
            "exit_date": str(row["close_date"])[:10],
            "pnl_pct": float(row.get("pnl_pct") or 0.0),
            "holding_days": int(float(row.get("holding_days") or 0)),
            "regime": row.get("regime_at_entry") or "UNKNOWN",
            "exit_reason": row.get("exit_reason") or "",
            "entry_reasoning": entry_reasoning[:240],
            "top_factors": top_factors,
            "exit_summary": (row.get("summary") or "")[:200],
            "pattern_tags": _parse_list(row.get("pattern_tags")),
        })
    return out


def format_trade_history_block(trades: List[Dict[str, Any]]) -> str:
    """Render trades as a multiline string for prompt injection."""
    if not trades:
        return ""
    wins = sum(1 for t in trades if t["pnl_pct"] > 0)
    header = (
        f"YOUR RECENT TRADE DECISIONS ({len(trades)} most recent closes, "
        f"{wins} winners / {len(trades) - wins} losers):\n"
        "Each entry shows what you said at entry, the factor scores you saw, and what happened.\n"
        "Look for systematic patterns — entries you'd want to repeat or avoid.\n\n"
    )
    lines = []
    for t in trades:
        factors_str = ", ".join(f"{k}={v}" for k, v in t["top_factors"]) or "n/a"
        tags_str = f" [{', '.join(t['pattern_tags'])}]" if t["pattern_tags"] else ""
        lines.append(
            f"  {t['ticker']:6} {t['entry_date']} → {t['exit_date']} "
            f"({t['holding_days']}d, {t['regime']}) "
            f"{t['pnl_pct']:+.1f}% [{t['exit_reason']}]\n"
            f"    Top factors at entry: {factors_str}\n"
            f"    You said: \"{t['entry_reasoning']}\"\n"
            f"    Outcome: {t['exit_summary']}{tags_str}\n"
        )
    return header + "\n".join(lines) + "\n"
