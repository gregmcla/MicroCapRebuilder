#!/usr/bin/env python3
"""
Watchlist event log — append-only history of every add/remove from a
portfolio's watchlist.

Consumed by position_lineage.py to surface "entered/left watchlist" events
in a position's story. Without this log, removed-ticker history was lost
(watchlist.jsonl only carries current state).

Storage: data/portfolios/{id}/watchlist_events.jsonl (gitignored, append-only).
Line format:
  {"ts": "2026-06-23T09:30:12-04:00", "ticker": "AAPL",
   "type": "added"|"removed", "reason": "scan:momentum", "source": "discovery"}

Writes are fcntl-locked for cron + API concurrency safety. Read paths swallow
errors and return empty lists — never block a watchlist mutation on event
logging failures.
"""

import fcntl
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


_DATA_DIR = Path(__file__).parent.parent / "data"


def _events_path(portfolio_id: str) -> Path:
    p = _DATA_DIR / "portfolios" / portfolio_id / "watchlist_events.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def record_watchlist_event(
    portfolio_id: str,
    ticker: str,
    kind: str,                    # "added" or "removed"
    reason: str = "",
    source: str = "",
    ts: Optional[str] = None,
) -> bool:
    """Append a single watchlist event. Returns True on success, False on
    any failure (logged but non-fatal — never raises)."""
    if not portfolio_id or not ticker or kind not in ("added", "removed"):
        return False
    try:
        path = _events_path(portfolio_id)
        line = {
            "ts": ts or datetime.now().isoformat(),
            "ticker": ticker.upper(),
            "type": kind,
            "reason": reason or "",
            "source": source or "",
        }
        with path.open("a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(json.dumps(line) + "\n")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return True
    except Exception as e:
        # Best-effort logging; the watchlist mutation must not fail because of
        # the audit trail.
        print(f"  [watchlist_events] record failed for {ticker} ({kind}): {e}")
        return False


def record_many(
    portfolio_id: str,
    events: Iterable[dict],
) -> int:
    """Append multiple events under a single lock. Returns number written.
    Each event dict: {ticker, type, reason?, source?, ts?}."""
    if not portfolio_id:
        return 0
    written = 0
    try:
        path = _events_path(portfolio_id)
        with path.open("a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                for ev in events:
                    if not isinstance(ev, dict):
                        continue
                    ticker = (ev.get("ticker") or "").upper()
                    kind = ev.get("type")
                    if not ticker or kind not in ("added", "removed"):
                        continue
                    line = {
                        "ts": ev.get("ts") or datetime.now().isoformat(),
                        "ticker": ticker,
                        "type": kind,
                        "reason": ev.get("reason") or "",
                        "source": ev.get("source") or "",
                    }
                    f.write(json.dumps(line) + "\n")
                    written += 1
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        print(f"  [watchlist_events] batch write failed: {e}")
    return written


def read_events(portfolio_id: str, ticker: Optional[str] = None) -> list[dict]:
    """Read all events for a portfolio, oldest first. Optionally filter to one ticker."""
    path = _events_path(portfolio_id)
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
