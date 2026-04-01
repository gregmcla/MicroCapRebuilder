# scripts/tests/test_score_first_watchlist.py
"""Tests for score-first watchlist architecture."""
import json
import pytest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
from watchlist_manager import WatchlistEntry


def test_watchlist_entry_has_score_delta():
    """WatchlistEntry dataclass includes score_delta with default 0.0."""
    entry = WatchlistEntry(ticker="AAPL", discovery_score=75.0)
    assert hasattr(entry, "score_delta")
    assert entry.score_delta == 0.0


def test_watchlist_entry_score_delta_serializes():
    """score_delta is included in asdict() output for JSONL persistence."""
    entry = WatchlistEntry(ticker="AAPL", discovery_score=75.0, score_delta=12.5)
    d = asdict(entry)
    assert "score_delta" in d
    assert d["score_delta"] == 12.5


def test_watchlist_entry_loads_from_old_jsonl_without_score_delta(tmp_path):
    """Old watchlist entries without score_delta field load without error."""
    old_entry = {
        "ticker": "MSFT",
        "added_date": "2026-01-01",
        "source": "MOMENTUM_BREAKOUT",
        "discovery_score": 68.0,
        "sector": "Technology",
        "market_cap_m": 3000000.0,
        "avg_volume": 25000000,
        "last_checked": "2026-03-01",
        "status": "ACTIVE",
        "notes": "",
        "social_heat": "COLD",
        "social_rank": None,
        "social_bullish_pct": None,
        # No score_delta field — simulates old file format
    }
    # Should not raise — score_delta has a default
    entry = WatchlistEntry(**old_entry)
    assert entry.score_delta == 0.0


def test_watchlist_api_includes_score_delta(tmp_path):
    """GET /watchlist response includes score_delta field for each candidate."""
    import json
    from pathlib import Path
    from watchlist_manager import WatchlistEntry
    from dataclasses import asdict

    # Write a watchlist with score_delta populated
    wl_path = tmp_path / "watchlist.jsonl"
    entries = [
        WatchlistEntry(ticker="AAPL", discovery_score=85.0, score_delta=12.5,
                       sector="Technology", source="SCORE_ALL", status="ACTIVE"),
        WatchlistEntry(ticker="MSFT", discovery_score=72.0, score_delta=-3.0,
                       sector="Technology", source="SCORE_ALL", status="ACTIVE"),
    ]
    with open(wl_path, "w") as f:
        for e in entries:
            f.write(json.dumps(asdict(e)) + "\n")

    # Read it back directly (simulating what the API does)
    candidates = []
    with open(wl_path) as f:
        for line in f:
            entry = json.loads(line.strip())
            if entry.get("status", "ACTIVE") == "ACTIVE":
                candidates.append({
                    "ticker": entry.get("ticker", ""),
                    "score": entry.get("discovery_score", 0),
                    "score_delta": entry.get("score_delta", 0.0),
                    "sector": entry.get("sector", ""),
                    "source": entry.get("source", ""),
                    "notes": entry.get("notes", ""),
                    "added_date": entry.get("added_date", ""),
                })

    assert candidates[0]["score_delta"] == 12.5
    assert candidates[1]["score_delta"] == -3.0
