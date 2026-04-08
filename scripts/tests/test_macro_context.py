#!/usr/bin/env python3
"""Tests for macro_context module."""
import sys
import time
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


import tempfile
import os


def test_headline_cache_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("macro_context._NEWS_CACHE_DIR", tmp_path)
    from macro_context import _save_cached_headlines, _load_cached_headlines
    payload = [{"title": "test", "publisher": "Reuters", "age_minutes": 10}]
    _save_cached_headlines("AAPL", payload)
    loaded = _load_cached_headlines("AAPL", ttl_seconds=3600)
    assert loaded == payload


def test_headline_cache_expires(tmp_path, monkeypatch):
    monkeypatch.setattr("macro_context._NEWS_CACHE_DIR", tmp_path)
    from macro_context import _save_cached_headlines, _load_cached_headlines
    _save_cached_headlines("AAPL", [{"title": "test", "publisher": "X", "age_minutes": 1}])
    # Force the cache file to look 2 hours old
    cache_file = tmp_path / "AAPL.json"
    old_time = time.time() - 7200
    os.utime(cache_file, (old_time, old_time))
    loaded = _load_cached_headlines("AAPL", ttl_seconds=3600)
    assert loaded is None


def test_headline_cache_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr("macro_context._NEWS_CACHE_DIR", tmp_path)
    from macro_context import _load_cached_headlines
    assert _load_cached_headlines("NEVERHEARD", ttl_seconds=3600) is None
