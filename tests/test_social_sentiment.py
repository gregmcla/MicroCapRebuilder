# tests/test_social_sentiment.py
import pytest
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, "scripts")

from social_sentiment import SocialSentimentProvider, SocialSignal, classify_heat


def test_classify_heat_cold():
    assert classify_heat(None, None) == "COLD"
    assert classify_heat(None, 40.0) == "COLD"
    assert classify_heat(80, 40.0) == "COLD"


def test_classify_heat_warm():
    assert classify_heat(75, None) == "WARM"   # rank 51-100
    assert classify_heat(None, 60.0) == "WARM" # 55-65% bullish


def test_classify_heat_hot():
    assert classify_heat(35, None) == "HOT"    # rank 21-50
    assert classify_heat(None, 72.0) == "HOT"  # 65-80% bullish


def test_classify_heat_spiking():
    assert classify_heat(10, 80.0) == "SPIKING"  # rank <=20 AND >75% bullish


def test_classify_heat_hot_not_spiking_without_both():
    # rank <=20 but no Stocktwits data → HOT not SPIKING
    assert classify_heat(5, None) == "HOT"
    # Stocktwits >75% but rank >20 → HOT not SPIKING
    assert classify_heat(30, 80.0) == "HOT"


def test_social_signal_defaults():
    sig = SocialSignal(ticker="TSLA")
    assert sig.heat == "COLD"
    assert sig.ape_rank is None
    assert sig.error is None


def test_get_signals_returns_cold_on_error():
    provider = SocialSentimentProvider(portfolio_id="test")
    with patch("social_sentiment.requests.get", side_effect=Exception("network error")):
        signals = provider.get_signals(["AAPL", "TSLA"])
    assert "AAPL" in signals
    assert signals["AAPL"].heat == "COLD"
    assert signals["AAPL"].error is not None


def test_get_signals_uses_apewisdom_rank():
    provider = SocialSentimentProvider(portfolio_id="test")
    mock_ape = {"TSLA": {"rank": 5, "mentions": 500, "upvotes": 200}}
    with patch.object(provider, "_fetch_apewisdom", return_value=mock_ape), \
         patch.object(provider, "_fetch_stocktwits", return_value=(None, 0)):
        signals = provider.get_signals(["TSLA"])
    assert signals["TSLA"].ape_rank == 5
    assert signals["TSLA"].heat == "HOT"  # rank <=20 but no ST → HOT


def test_cache_is_written_and_read(tmp_path):
    provider = SocialSentimentProvider(portfolio_id="test")
    provider._cache_file = tmp_path / "test_social.json"
    mock_ape = {}
    with patch.object(provider, "_fetch_apewisdom", return_value=mock_ape), \
         patch.object(provider, "_fetch_stocktwits", return_value=(None, 0)):
        provider.get_signals(["NVDA"])
    assert provider._cache_file.exists()
    # Second call should read from cache without fetching
    with patch.object(provider, "_fetch_apewisdom", side_effect=Exception("should not call")):
        signals = provider.get_signals(["NVDA"])
    assert "NVDA" in signals
