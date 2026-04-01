#!/usr/bin/env python3
"""
ScoreStore — per-portfolio daily composite score persistence.

Stores ticker scores as an append-only JSONL log.
Enables score-delta detection: surface tickers whose signal improved overnight.

Data file: data/portfolios/{id}/daily_scores.jsonl
Line format (one per ticker per day):
  {"date": "2026-04-02", "ticker": "AAPL", "composite": 72.5,
   "momentum": 80.0, "quality": 65.0, "earnings": 55.0,
   "volume": 70.0, "volatility": 60.0, "value_timing": 75.0}
"""

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPT_DIR = Path(__file__).parent
DEFAULT_DATA_DIR = SCRIPT_DIR.parent / "data"


class ScoreStore:
    """Manages daily score persistence and delta computation for one portfolio."""

    def __init__(self, portfolio_id: str, data_dir: Path = None):
        self.portfolio_id = portfolio_id
        _data_dir = data_dir or DEFAULT_DATA_DIR
        self._path = _data_dir / "portfolios" / portfolio_id / "daily_scores.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save_scores(self, scores: List[Dict]) -> None:
        """Append today's scores for a list of tickers.

        Skips tickers already written today (idempotent within a day).

        Args:
            scores: List of dicts with keys: ticker, composite, momentum, quality,
                    earnings, volume, volatility, value_timing
        """
        today = date.today().isoformat()

        # Read already-written tickers for today to avoid duplicates
        written_today: set = set()
        if self._path.exists():
            with open(self._path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                        if row.get("date") == today:
                            written_today.add(row["ticker"])
                    except Exception:
                        continue

        new_lines = []
        for s in scores:
            ticker = s.get("ticker", "")
            if not ticker or ticker in written_today:
                continue
            new_lines.append(json.dumps({
                "date": today,
                "ticker": ticker,
                "composite": round(float(s.get("composite", 0)), 2),
                "momentum": round(float(s.get("momentum", 0)), 2),
                "quality": round(float(s.get("quality", 0)), 2),
                "earnings": round(float(s.get("earnings", 0)), 2),
                "volume": round(float(s.get("volume", 0)), 2),
                "volatility": round(float(s.get("volatility", 0)), 2),
                "value_timing": round(float(s.get("value_timing", 0)), 2),
            }))

        if new_lines:
            with open(self._path, "a") as f:
                f.write("\n".join(new_lines) + "\n")

    def get_latest_scores(self) -> Dict[str, float]:
        """Return most recent composite score per ticker (any date)."""
        by_ticker: Dict[str, Tuple[str, float]] = {}  # ticker -> (date, composite)
        if not self._path.exists():
            return {}
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    ticker = row["ticker"]
                    d = row["date"]
                    comp = float(row["composite"])
                    if ticker not in by_ticker or d > by_ticker[ticker][0]:
                        by_ticker[ticker] = (d, comp)
                except Exception:
                    continue
        return {ticker: v[1] for ticker, v in by_ticker.items()}

    def get_all_deltas(self) -> Dict[str, float]:
        """Return today_score - prev_score for every ticker.

        Returns 0.0 for tickers with only one day of history.
        """
        # Collect last two entries per ticker (sorted by date)
        by_ticker: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        if not self._path.exists():
            return {}
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    by_ticker[row["ticker"]].append((row["date"], float(row["composite"])))
                except Exception:
                    continue

        deltas: Dict[str, float] = {}
        for ticker, entries in by_ticker.items():
            entries.sort(key=lambda x: x[0])  # ascending by date
            if len(entries) < 2:
                deltas[ticker] = 0.0
            else:
                deltas[ticker] = round(entries[-1][1] - entries[-2][1], 2)
        return deltas

    def get_top_by_blended(
        self, n: int, delta_weight: float = 0.3
    ) -> List[Tuple[str, float, float]]:
        """Return top-N tickers by blended rank: composite + delta_weight * delta.

        Returns list of (ticker, composite, delta) sorted by blended score desc.
        """
        latest = self.get_latest_scores()
        deltas = self.get_all_deltas()

        blended = []
        for ticker, composite in latest.items():
            delta = deltas.get(ticker, 0.0)
            blended_score = composite + delta_weight * delta
            blended.append((ticker, composite, delta, blended_score))

        blended.sort(key=lambda x: x[3], reverse=True)
        return [(t, c, d) for t, c, d, _ in blended[:n]]

    def cleanup(self, keep_days: int = 30) -> int:
        """Remove entries older than keep_days. Returns number of lines removed."""
        if not self._path.exists():
            return 0
        cutoff = (date.today() - timedelta(days=keep_days)).isoformat()
        kept = []
        removed = 0
        with open(self._path) as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                    if row.get("date", "") >= cutoff:
                        kept.append(stripped)
                    else:
                        removed += 1
                except Exception:
                    kept.append(stripped)
        if removed:
            tmp = self._path.with_suffix(".jsonl.tmp")
            tmp.write_text("\n".join(kept) + "\n")
            tmp.rename(self._path)
        return removed
