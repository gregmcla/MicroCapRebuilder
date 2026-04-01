# scripts/tests/test_score_store.py
import json
import pytest
from datetime import date, timedelta
from pathlib import Path
from score_store import ScoreStore


def _make_score(ticker: str, composite: float, momentum: float = 50.0) -> dict:
    return {
        "ticker": ticker,
        "composite": composite,
        "momentum": momentum,
        "quality": 50.0,
        "earnings": 50.0,
        "volume": 50.0,
        "volatility": 50.0,
        "value_timing": 50.0,
    }


def test_save_and_get_latest(tmp_path):
    """Saved scores are returned by get_latest_scores."""
    store = ScoreStore("test-port", data_dir=tmp_path)
    store.save_scores([_make_score("AAPL", 75.0), _make_score("MSFT", 60.0)])
    latest = store.get_latest_scores()
    assert latest["AAPL"] == 75.0
    assert latest["MSFT"] == 60.0


def test_delta_is_zero_on_first_day(tmp_path):
    """Score delta is 0.0 when there's only one day of history."""
    store = ScoreStore("test-port", data_dir=tmp_path)
    store.save_scores([_make_score("AAPL", 75.0)])
    deltas = store.get_all_deltas()
    assert deltas.get("AAPL", 0.0) == 0.0


def test_delta_computed_across_two_days(tmp_path):
    """Delta is today's score minus yesterday's score."""
    store = ScoreStore("test-port", data_dir=tmp_path)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()

    # Write yesterday manually
    line = json.dumps({"date": yesterday, "ticker": "AAPL", "composite": 60.0,
                       "momentum": 50.0, "quality": 50.0, "earnings": 50.0,
                       "volume": 50.0, "volatility": 50.0, "value_timing": 50.0})
    store._path.parent.mkdir(parents=True, exist_ok=True)
    store._path.write_text(line + "\n")

    # Write today via save_scores
    store.save_scores([_make_score("AAPL", 75.0)])

    deltas = store.get_all_deltas()
    assert abs(deltas["AAPL"] - 15.0) < 0.01


def test_get_top_by_blended(tmp_path):
    """Blended ranking boosts tickers with large positive deltas."""
    store = ScoreStore("test-port", data_dir=tmp_path)
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Yesterday: AAPL=70, MSFT=80
    for ticker, score in [("AAPL", 70.0), ("MSFT", 80.0)]:
        line = json.dumps({"date": yesterday, "ticker": ticker, "composite": score,
                           "momentum": 50.0, "quality": 50.0, "earnings": 50.0,
                           "volume": 50.0, "volatility": 50.0, "value_timing": 50.0})
        store._path.parent.mkdir(parents=True, exist_ok=True)
        with open(store._path, "a") as f:
            f.write(line + "\n")

    # Today: AAPL jumps to 90 (+20 delta), MSFT stays at 80 (+0 delta)
    store.save_scores([_make_score("AAPL", 90.0), _make_score("MSFT", 80.0)])

    top = store.get_top_by_blended(n=2, delta_weight=0.3)
    # AAPL: 90 + 0.3*20 = 96. MSFT: 80 + 0.3*0 = 80. AAPL should rank first.
    assert top[0][0] == "AAPL"
    assert top[1][0] == "MSFT"


def test_cleanup_removes_old_entries(tmp_path):
    """cleanup() removes entries older than keep_days."""
    store = ScoreStore("test-port", data_dir=tmp_path)
    old_date = (date.today() - timedelta(days=35)).isoformat()
    today = date.today().isoformat()

    store._path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"date": old_date, "ticker": "OLD", "composite": 50.0,
                    "momentum": 50.0, "quality": 50.0, "earnings": 50.0,
                    "volume": 50.0, "volatility": 50.0, "value_timing": 50.0}),
        json.dumps({"date": today, "ticker": "NEW", "composite": 70.0,
                    "momentum": 50.0, "quality": 50.0, "earnings": 50.0,
                    "volume": 50.0, "volatility": 50.0, "value_timing": 50.0}),
    ]
    store._path.write_text("\n".join(lines) + "\n")

    removed = store.cleanup(keep_days=30)
    assert removed == 1
    latest = store.get_latest_scores()
    assert "OLD" not in latest
    assert "NEW" in latest


def test_score_store_written_by_score_all(tmp_path):
    """_score_all_universe() writes all scored tickers to ScoreStore, not just candidates."""
    store = ScoreStore("microcap", data_dir=tmp_path)
    # Write a score below any threshold
    store.save_scores([_make_score("LOWSCORE", 15.0)])
    # Should still be in the score store
    latest = store.get_latest_scores()
    assert "LOWSCORE" in latest
    assert latest["LOWSCORE"] == 15.0
