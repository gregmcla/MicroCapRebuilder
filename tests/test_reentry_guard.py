#!/usr/bin/env python3
"""Tests for reentry_guard module."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from reentry_guard import _format_reentry_block, get_reentry_context


def _make_csv(tmp_path, rows):
    """Write a transactions CSV with the given rows and return the path."""
    df = pd.DataFrame(rows)
    p = tmp_path / "transactions.csv"
    df.to_csv(p, index=False)
    return p


TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
LAST_WEEK = TODAY - timedelta(days=6)
LONG_AGO = TODAY - timedelta(days=45)


def _buy(ticker, factor_scores=None, d=None):
    d = d or (TODAY - timedelta(days=14))
    return {
        "ticker": ticker, "action": "BUY", "date": str(d),
        "factor_scores": json.dumps(factor_scores) if factor_scores else "",
    }


def _sell(ticker, reason="STOP_LOSS", d=None):
    d = d or LAST_WEEK
    return {"ticker": ticker, "action": "SELL", "date": str(d), "reason": reason, "factor_scores": ""}


ENTRY_SCORES = {"price_momentum": 60.0, "quality": 70.0, "volume": 55.0,
                "volatility": 65.0, "earnings_growth": 50.0, "value_timing": 45.0}

CURRENT_SCORES = {"price_momentum": 72.0, "quality": 71.0, "volume": 56.0,
                  "volatility": 64.0, "earnings_growth": 51.0, "value_timing": 46.0}  # momentum +12


def test_returns_none_no_recent_sell(tmp_path):
    """No SELL transaction at all → None."""
    p = _make_csv(tmp_path, [_buy("AAPL", ENTRY_SCORES)])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is None


def test_returns_none_sell_outside_window(tmp_path):
    """SELL older than lookback_days → None."""
    p = _make_csv(tmp_path, [_sell("AAPL", d=LONG_AGO)])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is None


def test_returns_context_with_delta(tmp_path):
    """SELL + BUY both found with factor_scores → dict with delta not None."""
    p = _make_csv(tmp_path, [_buy("AAPL", ENTRY_SCORES), _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is not None
    assert result["delta"] is not None
    assert "price_momentum" in result["delta"]


def test_returns_context_without_delta_no_buy_scores(tmp_path):
    """SELL found, BUY has no factor_scores → dict with delta=None."""
    p = _make_csv(tmp_path, [_buy("AAPL", factor_scores=None), _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is not None
    assert result["delta"] is None


def test_meaningful_change_true(tmp_path):
    """price_momentum delta of +12 >= threshold 10 → meaningful_change=True."""
    p = _make_csv(tmp_path, [_buy("AAPL", ENTRY_SCORES), _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result["meaningful_change"] is True


def test_meaningful_change_false(tmp_path):
    """All factor deltas < threshold 10 → meaningful_change=False."""
    small_change = {k: v + 2.0 for k, v in ENTRY_SCORES.items()}  # all +2, < 10
    p = _make_csv(tmp_path, [_buy("AAPL", ENTRY_SCORES), _sell("AAPL")])
    result = get_reentry_context("AAPL", p, small_change, 30, 10)
    assert result["meaningful_change"] is False


def test_uses_most_recent_sell(tmp_path):
    """Two SELLs in window — context uses the more recent one."""
    older_sell = _sell("AAPL", d=TODAY - timedelta(days=10))
    newer_sell = _sell("AAPL", reason="TAKE_PROFIT", d=TODAY - timedelta(days=3))
    p = _make_csv(tmp_path, [_buy("AAPL", ENTRY_SCORES), older_sell, newer_sell])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result["exit_reason"] == "TAKE_PROFIT"
    assert result["days_since_exit"] == 3


def test_uses_most_recent_buy_for_entry_scores(tmp_path):
    """Two BUYs — more recent BUY scores are used for delta baseline."""
    old_scores = {k: 40.0 for k in ENTRY_SCORES}
    new_scores = ENTRY_SCORES
    older_buy = _buy("AAPL", old_scores, d=TODAY - timedelta(days=60))
    newer_buy = _buy("AAPL", new_scores, d=TODAY - timedelta(days=14))
    p = _make_csv(tmp_path, [older_buy, newer_buy, _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    # delta should be vs new_scores (60.0), not old_scores (40.0)
    expected_momentum_delta = CURRENT_SCORES["price_momentum"] - new_scores["price_momentum"]
    assert abs(result["delta"]["price_momentum"] - expected_momentum_delta) < 0.01


def test_sell_exactly_on_boundary(tmp_path):
    """SELL date == today - lookback_days → included (>= boundary)."""
    boundary_date = TODAY - timedelta(days=30)
    p = _make_csv(tmp_path, [_sell("AAPL", d=boundary_date)])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is not None


def test_sell_one_day_outside_boundary(tmp_path):
    """SELL date == today - lookback_days - 1 → None."""
    just_outside = TODAY - timedelta(days=31)
    p = _make_csv(tmp_path, [_sell("AAPL", d=just_outside)])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is None


def test_handles_missing_transactions_file():
    """Path does not exist → None (no exception raised)."""
    result = get_reentry_context("AAPL", Path("/nonexistent/transactions.csv"), CURRENT_SCORES, 30, 10)
    assert result is None


def test_handles_missing_ticker_column(tmp_path):
    """CSV has no ticker column → None (no exception raised)."""
    df = pd.DataFrame([{"symbol": "AAPL", "action": "SELL", "date": str(LAST_WEEK)}])
    p = tmp_path / "transactions.csv"
    df.to_csv(p, index=False)
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is None


def test_handles_malformed_factor_scores_json(tmp_path):
    """factor_scores contains invalid JSON → context with exit_scores=None."""
    row = _buy("AAPL")
    row["factor_scores"] = "{not valid json"
    p = _make_csv(tmp_path, [row, _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is not None
    assert result["exit_scores"] is None
    assert result["delta"] is None


def test_handles_empty_factor_scores(tmp_path):
    """factor_scores is empty string → context with exit_scores=None."""
    p = _make_csv(tmp_path, [_buy("AAPL", factor_scores=None), _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is not None
    assert result["exit_scores"] is None


def test_excludes_composite_from_delta(tmp_path):
    """BUY factor_scores includes 'composite' key → delta dict does not contain 'composite'."""
    scores_with_composite = dict(ENTRY_SCORES, composite=65.0)
    p = _make_csv(tmp_path, [_buy("AAPL", scores_with_composite), _sell("AAPL")])
    current_with_composite = dict(CURRENT_SCORES, composite=70.0)
    result = get_reentry_context("AAPL", p, current_with_composite, 30, 10)
    assert result is not None
    assert result["delta"] is not None
    assert "composite" not in result["delta"]
