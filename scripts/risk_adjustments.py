#!/usr/bin/env python3
"""
Risk adjustment log — append-only history of every stop_loss / take_profit
change for a position.

Consumed by position_lineage.py to surface stop-adjustment events in a
position's story. Two write paths:

  1. **AI / pipeline writes** — `unified_analysis.execute_approved_actions`
     and any controls endpoint that mutates a stop call `record_adjustment(...)`
     directly with `source="trailing"|"volatility"|"manual"|...` and a
     `trace_id` when AI-driven.
  2. **Drift detector** — `detect_and_log_drift(state)` compares the current
     positions DataFrame against a shadow `.last_known_stops.json` snapshot
     and emits "manual" adjustments for any deltas. This catches direct
     CSV edits (like Greg's SPCX adjustment on 2026-06-16). Runs on
     `save_positions` and updates the shadow afterwards.

Storage:
  data/portfolios/{id}/risk_adjustments.jsonl     — append-only log
  data/portfolios/{id}/.last_known_stops.json     — shadow state for drift

Line format:
  {"ts": "2026-06-16T16:13:00", "ticker": "SPCX", "field": "stop_loss",
   "old": 125.55, "new": 164.75, "source": "manual", "trace_id": null}
"""

import fcntl
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


_DATA_DIR = Path(__file__).parent.parent / "data"


def _log_path(portfolio_id: str) -> Path:
    p = _DATA_DIR / "portfolios" / portfolio_id / "risk_adjustments.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _shadow_path(portfolio_id: str) -> Path:
    return _DATA_DIR / "portfolios" / portfolio_id / ".last_known_stops.json"


# ─── Write API ───────────────────────────────────────────────────────────────

def record_adjustment(
    portfolio_id: str,
    ticker: str,
    field: str,                   # "stop_loss" or "take_profit"
    old_value: float,
    new_value: float,
    source: str,                  # "trailing" / "volatility" / "manual" / "regime" / "preservation" / "execute"
    trace_id: Optional[str] = None,
    ts: Optional[str] = None,
) -> bool:
    """Append one adjustment event. Returns True on success, False on any
    failure (logged but non-fatal — never raises)."""
    if not portfolio_id or not ticker or field not in ("stop_loss", "take_profit"):
        return False
    try:
        # Skip no-op writes (a save with unchanged stops shouldn't log).
        try:
            if round(float(old_value), 6) == round(float(new_value), 6):
                return False
        except Exception:
            pass
        line = {
            "ts": ts or datetime.now().isoformat(),
            "ticker": ticker.upper(),
            "field": field,
            "old": round(float(old_value), 4),
            "new": round(float(new_value), 4),
            "source": source or "unknown",
            "trace_id": trace_id,
        }
        path = _log_path(portfolio_id)
        with path.open("a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(json.dumps(line) + "\n")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return True
    except Exception as e:
        print(f"  [risk_adjustments] record failed for {ticker} {field}: {e}")
        return False


# ─── Read API ────────────────────────────────────────────────────────────────

def read_adjustments(portfolio_id: str, ticker: Optional[str] = None) -> list[dict]:
    """All adjustments, oldest first; optionally filter by ticker."""
    path = _log_path(portfolio_id)
    if not path.exists():
        return []
    out: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if ticker and (row.get("ticker") or "").upper() != ticker.upper():
                continue
            out.append(row)
    except Exception:
        return out
    return out


# ─── Drift detector ──────────────────────────────────────────────────────────

def detect_and_log_drift(portfolio_id: str, positions: pd.DataFrame) -> int:
    """Diff `positions` (about to be saved) against the shadow snapshot;
    emit `source="manual"` adjustments for any deltas not preceded by an
    API-logged adjustment for the same ticker+field in the last few seconds.

    Returns count of adjustments logged. Also rewrites the shadow snapshot
    to reflect the current positions state (atomically).

    Call this from `portfolio_state.save_positions()` immediately before
    writing positions.csv.
    """
    if positions is None or positions.empty:
        # Still refresh shadow to empty so a subsequent re-population won't
        # spuriously log all positions as manual.
        _write_shadow(portfolio_id, {})
        return 0

    shadow = _read_shadow(portfolio_id)
    new_shadow: dict[str, dict] = {}
    logged = 0

    for _, row in positions.iterrows():
        try:
            ticker = str(row["ticker"]).upper()
        except Exception:
            continue
        try:
            stop = float(row.get("stop_loss") or 0)
            target = float(row.get("take_profit") or 0)
        except Exception:
            continue
        new_shadow[ticker] = {"stop_loss": stop, "take_profit": target}

        prior = shadow.get(ticker)
        if prior is None:
            # New position — not a manual edit; the buy itself records initial stop/TP.
            continue

        for field, current in (("stop_loss", stop), ("take_profit", target)):
            old = float(prior.get(field, 0) or 0)
            if round(current, 4) == round(old, 4):
                continue
            # Was this same change already logged by the pipeline in the last
            # 60s? If yes, skip — avoid double-logging API + drift.
            if _recently_logged(portfolio_id, ticker, field, current, window_seconds=60):
                continue
            if record_adjustment(
                portfolio_id=portfolio_id,
                ticker=ticker,
                field=field,
                old_value=old,
                new_value=current,
                source="manual",
            ):
                logged += 1

    _write_shadow(portfolio_id, new_shadow)
    return logged


def _read_shadow(portfolio_id: str) -> dict:
    path = _shadow_path(portfolio_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _write_shadow(portfolio_id: str, snapshot: dict) -> None:
    path = _shadow_path(portfolio_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(snapshot))
        tmp.replace(path)
    except Exception as e:
        print(f"  [risk_adjustments] shadow write failed: {e}")


def _recently_logged(
    portfolio_id: str,
    ticker: str,
    field: str,
    new_value: float,
    window_seconds: int = 60,
) -> bool:
    """Heuristic to avoid double-logging an adjustment that the pipeline
    already recorded (e.g., execute_approved_actions wrote a `trailing`
    adjustment, then save_positions runs and the drift detector sees the
    same delta)."""
    path = _log_path(portfolio_id)
    if not path.exists():
        return False
    cutoff = datetime.now().timestamp() - window_seconds
    try:
        # Cheap: only check the tail (last 200 lines is more than enough).
        lines = path.read_text().splitlines()[-200:]
    except Exception:
        return False
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        try:
            row_ts = datetime.fromisoformat(row.get("ts", "")).timestamp()
        except Exception:
            continue
        if row_ts < cutoff:
            # Older than our window — older rows are even older.
            return False
        if (
            (row.get("ticker") or "").upper() == ticker.upper()
            and row.get("field") == field
            and round(float(row.get("new", 0) or 0), 4) == round(new_value, 4)
        ):
            return True
    return False
