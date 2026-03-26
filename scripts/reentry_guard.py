#!/usr/bin/env python3
"""Reentry guard — detects recent exits and computes factor score delta for AI review."""
import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd


def get_reentry_context(
    ticker: str,
    transactions_path: Path,
    current_scores: Optional[dict],
    lookback_days: int,
    meaningful_change_threshold_pts: float,
) -> Optional[dict]:
    """Return reentry context dict if ticker was recently sold, else None."""
    if not Path(transactions_path).exists():
        return None

    try:
        df = pd.read_csv(transactions_path, dtype=str)

        if "ticker" not in df.columns:
            return None

        df["ticker"] = df["ticker"].str.strip().str.upper()
        ticker = ticker.strip().upper()
        ticker_df = df[df["ticker"] == ticker]

        # Find most recent SELL within lookback window
        cutoff = date.today() - timedelta(days=lookback_days)
        sells = ticker_df[ticker_df["action"] == "SELL"].copy()
        if sells.empty:
            return None

        sells["_date"] = pd.to_datetime(sells["date"], errors="coerce").dt.date
        sells = sells.dropna(subset=["_date"])
        sells = sells[sells["_date"] >= cutoff]
        if sells.empty:
            return None

        most_recent_sell = sells.sort_values("_date", ascending=False).iloc[0]
        exit_date = most_recent_sell["_date"]
        days_since_exit = (date.today() - exit_date).days
        exit_reason = most_recent_sell.get("reason", "SIGNAL") if "reason" in most_recent_sell.index else "SIGNAL"
        if pd.isna(exit_reason) or not str(exit_reason).strip():
            exit_reason = "SIGNAL"

        # Find most recent BUY for entry scores
        buys = ticker_df[ticker_df["action"] == "BUY"].copy()
        exit_scores = None
        if not buys.empty and "factor_scores" in buys.columns:
            buys["_date"] = pd.to_datetime(buys["date"], errors="coerce").dt.date
            buys = buys.dropna(subset=["_date"])
            if not buys.empty:
                most_recent_buy = buys.sort_values("_date", ascending=False).iloc[0]
                raw = most_recent_buy.get("factor_scores", "")
                if raw and str(raw).strip() not in ("", "nan", "null", "None"):
                    try:
                        parsed = json.loads(str(raw))
                        if isinstance(parsed, dict) and parsed:
                            exit_scores = {k: v for k, v in parsed.items() if k != "composite"}
                    except Exception as e:
                        logging.warning("reentry_guard: failed to parse factor_scores for %s: %s", ticker, e)

        # Compute delta
        delta = None
        if exit_scores is not None and current_scores is not None:
            filtered_current = {k: v for k, v in current_scores.items() if k != "composite"}
            delta = {
                f: float(filtered_current[f]) - float(exit_scores[f])
                for f in exit_scores
                if f in filtered_current
            }

        meaningful_change = (
            any(abs(v) >= meaningful_change_threshold_pts for v in delta.values())
            if delta
            else False
        )

        return {
            "exit_date": str(exit_date),
            "exit_reason": str(exit_reason),
            "days_since_exit": days_since_exit,
            "exit_scores": exit_scores,
            "current_scores": current_scores if exit_scores is not None else None,
            "delta": delta,
            "meaningful_change": meaningful_change,
        }

    except Exception as e:
        logging.warning("reentry_guard: get_reentry_context failed for %s: %s", ticker, e)
        return None


def _format_reentry_block(ctx: dict) -> str:
    """Format reentry context dict into a multi-line string for AI prompts."""
    days = ctx["days_since_exit"]
    reason = ctx["exit_reason"]
    delta = ctx.get("delta")
    exit_scores = ctx.get("exit_scores")
    meaningful = ctx.get("meaningful_change", False)
    flag_threshold = 10  # display threshold (hardcoded — meaningful_change already reflects portfolio threshold)

    if exit_scores is None:
        return (
            f"\n  ↻ Reentry Context: Sold {days} days ago ({reason})."
            f" No entry scores available for delta comparison.\n"
        )

    # Build factor delta lines
    factor_parts = []
    if delta:
        for factor, change in delta.items():
            entry_val = exit_scores.get(factor, 0)
            current_val = entry_val + change
            flag = ""
            if abs(change) >= flag_threshold:
                flag = " ⚠" if change < 0 else " ✓"
            sign = "+" if change >= 0 else ""
            factor_parts.append(
                f"{factor}: {entry_val:.0f}→{current_val:.0f} ({sign}{change:.0f}{flag})"
            )

    delta_line = ", ".join(factor_parts) if factor_parts else "no delta"

    if meaningful:
        header = f"↻ Reentry Context: Sold {days} days ago ({reason})."
        footer = "Significant shifts detected. Re-entry may be valid if thesis is fresh."
    else:
        header = f"⚠ Reentry Warning: Sold {days} days ago ({reason})."
        footer = f"No factor changed ≥{flag_threshold}pts. Critically justify reentry or reject."

    return f"\n  {header}\n  Factor delta vs entry — {delta_line}\n  {footer}\n"
