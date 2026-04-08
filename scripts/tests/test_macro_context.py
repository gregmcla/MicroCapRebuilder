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


def test_get_position_headlines_uses_cache_when_fresh(tmp_path, monkeypatch):
    monkeypatch.setattr("macro_context._NEWS_CACHE_DIR", tmp_path)
    from macro_context import _save_cached_headlines, get_position_headlines
    cached = [{"title": "Cached AAPL story", "publisher": "Reuters", "age_minutes": 30}]
    _save_cached_headlines("AAPL", cached)
    # yfinance should NOT be called when cache is fresh
    with patch("macro_context.yf.Ticker") as mock_ticker:
        result = get_position_headlines(["AAPL"], max_per_ticker=2, ttl_seconds=3600)
    mock_ticker.assert_not_called()
    assert result["AAPL"] == cached


def test_get_position_headlines_fetches_when_cache_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("macro_context._NEWS_CACHE_DIR", tmp_path)
    fake_news = [
        {"title": "Test headline 1", "publisher": "Reuters",
         "providerPublishTime": int(time.time()) - 600},
        {"title": "Test headline 2", "publisher": "Bloomberg",
         "providerPublishTime": int(time.time()) - 1800},
        {"title": "Test headline 3", "publisher": "WSJ",
         "providerPublishTime": int(time.time()) - 3600},
    ]
    mock_ticker = type("T", (), {"news": fake_news})()
    with patch("macro_context.yf.Ticker", return_value=mock_ticker):
        from macro_context import get_position_headlines
        result = get_position_headlines(["TSLA"], max_per_ticker=2, ttl_seconds=3600)
    assert "TSLA" in result
    assert len(result["TSLA"]) == 2
    assert result["TSLA"][0]["title"] == "Test headline 1"
    assert result["TSLA"][0]["publisher"] == "Reuters"
    assert "age_minutes" in result["TSLA"][0]


def test_get_position_headlines_parses_current_yfinance_shape(tmp_path, monkeypatch):
    """yfinance changed its news schema — items are now {id, content: {title, provider, pubDate}}."""
    monkeypatch.setattr("macro_context._NEWS_CACHE_DIR", tmp_path)
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    fake_news = [
        {
            "id": "abc",
            "content": {
                "title": "Apple beats earnings expectations",
                "provider": {"displayName": "Reuters", "url": "https://reuters.com"},
                "pubDate": (now_utc - timedelta(minutes=240)).isoformat().replace("+00:00", "Z"),
            },
        },
        {
            "id": "def",
            "content": {
                "title": "Apple announces new product",
                "provider": {"displayName": "Bloomberg"},
                "pubDate": (now_utc - timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            },
        },
    ]
    mock_ticker = type("T", (), {"news": fake_news})()
    with patch("macro_context.yf.Ticker", return_value=mock_ticker):
        from macro_context import get_position_headlines
        result = get_position_headlines(["AAPL"], max_per_ticker=2, ttl_seconds=3600)
    assert len(result["AAPL"]) == 2
    assert result["AAPL"][0]["title"] == "Apple beats earnings expectations"
    assert result["AAPL"][0]["publisher"] == "Reuters"
    # 240 min ago → age should be approximately 240 (allow ±2 minutes for test execution drift)
    assert 238 <= result["AAPL"][0]["age_minutes"] <= 242
    assert result["AAPL"][1]["publisher"] == "Bloomberg"


def test_get_position_headlines_handles_per_ticker_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("macro_context._NEWS_CACHE_DIR", tmp_path)
    with patch("macro_context.yf.Ticker", side_effect=Exception("network err")):
        from macro_context import get_position_headlines
        result = get_position_headlines(["FOO"], max_per_ticker=2, ttl_seconds=3600)
    # One bad ticker yields empty headline list, not a crash
    assert result == {"FOO": []}


def test_get_position_headlines_empty_input():
    from macro_context import get_position_headlines
    assert get_position_headlines([], max_per_ticker=2, ttl_seconds=3600) == {}


def test_format_macro_block_renders_indicators_and_headlines():
    indicators = [
        {"symbol": "CL=F", "name": "WTI Crude", "price": 95.10, "day_pct": -15.2},
        {"symbol": "^VIX", "name": "VIX",        "price": 21.4,  "day_pct": 8.1},
    ]
    headlines = {
        "AAPL": [
            {"title": "Apple beats earnings", "publisher": "Reuters", "age_minutes": 240},
        ],
        "TSLA": [],
    }
    from macro_context import format_macro_block
    block = format_macro_block(indicators, headlines)

    assert "MACRO CONTEXT" in block
    assert "WTI Crude" in block
    assert "$95.10" in block
    assert "-15.2%" in block
    assert "VIX" in block
    assert "+8.1%" in block
    assert "AAPL" in block
    assert "Apple beats earnings" in block
    assert "Reuters" in block
    assert "4h" in block  # 240 minutes formatted as ~4h
    # TSLA had no headlines — should be omitted or marked, not crash
    assert block  # non-empty


def test_format_macro_block_empty_inputs_returns_empty_string():
    from macro_context import format_macro_block
    assert format_macro_block([], {}) == ""


def test_get_macro_context_orchestrator_returns_block_string(tmp_path, monkeypatch):
    monkeypatch.setattr("macro_context._NEWS_CACHE_DIR", tmp_path)
    fake_df = pd.DataFrame(
        {"Close": [100.0, 95.0]}, index=pd.date_range("2026-04-07", periods=2)
    )
    with patch("macro_context.cached_download", return_value=fake_df), \
         patch("macro_context.yf.Ticker") as mock_ticker:
        mock_ticker.return_value = type("T", (), {"news": []})()
        from macro_context import get_macro_context
        block = get_macro_context(["AAPL"])
    assert "MACRO CONTEXT" in block
    assert "WTI Crude" in block


def test_get_macro_context_returns_empty_string_on_total_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("macro_context._NEWS_CACHE_DIR", tmp_path)
    with patch("macro_context.cached_download", side_effect=Exception("boom")), \
         patch("macro_context.yf.Ticker", side_effect=Exception("boom")):
        from macro_context import get_macro_context
        block = get_macro_context(["AAPL"])
    # Indicators failed AND no headlines → returns empty string, no crash
    assert block == ""
