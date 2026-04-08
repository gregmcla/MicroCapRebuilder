#!/usr/bin/env python3
"""Tests for macro_context module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from macro_context import INDICATORS


def test_indicators_constant_has_expected_symbols():
    symbols = {ind["symbol"] for ind in INDICATORS}
    assert symbols == {"CL=F", "BZ=F", "GC=F", "DX-Y.NYB", "^VIX", "^TNX", "SPY"}


def test_indicators_have_display_names():
    for ind in INDICATORS:
        assert "symbol" in ind
        assert "name" in ind
        assert ind["name"]


from unittest.mock import patch
import pandas as pd


def test_get_indicator_snapshots_returns_one_dict_per_indicator():
    fake_df = pd.DataFrame({
        "Close": [100.0, 95.0],  # yesterday, today
    }, index=pd.date_range("2026-04-07", periods=2))

    with patch("macro_context.cached_download", return_value=fake_df):
        from macro_context import get_indicator_snapshots
        result = get_indicator_snapshots()

    assert len(result) == len(INDICATORS)
    for entry in result:
        assert "symbol" in entry
        assert "name" in entry
        assert "price" in entry
        assert "day_pct" in entry
    # -5% drop expected on every indicator with this fake data
    for entry in result:
        assert entry["price"] == 95.0
        assert round(entry["day_pct"], 1) == -5.0


def test_get_indicator_snapshots_handles_fetch_failure():
    with patch("macro_context.cached_download", side_effect=Exception("network err")):
        from macro_context import get_indicator_snapshots
        result = get_indicator_snapshots()
    # Failure mode: empty list, no crash
    assert result == []
