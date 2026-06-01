# tests/test_social_sentiment.py
import pytest
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, "scripts")

from social_sentiment import SocialSentimentProvider, SocialSignal, classify_heat


# Stocktwits was removed 2026-06-01 (HTTP 403 on every request, never a usable
# signal). Heat is now driven purely by ApeWisdom (WSB) rank:
#   SPIKING <= 10, HOT <= 50, WARM <= 100, COLD otherwise / unranked.
# classify_heat keeps a second positional param for backward-compatible call
# sites; it is ignored.


def test_classify_heat_cold():
    assert classify_heat(None) == "COLD"
    assert classify_heat(None, 40.0) == "COLD"   # legacy 2nd arg ignored
    assert classify_heat(150) == "COLD"           # outside the top 100


def test_classify_heat_warm():
    assert classify_heat(75) == "WARM"   # rank 51-100
    assert classify_heat(100) == "WARM"  # inclusive upper boundary


def test_classify_heat_hot():
    assert classify_heat(35) == "HOT"    # rank 11-50
    assert classify_heat(50) == "HOT"    # inclusive upper boundary


def test_classify_heat_spiking():
    assert classify_heat(10) == "SPIKING"  # rank <= 10
    assert classify_heat(1) == "SPIKING"


def test_classify_heat_boundaries():
    assert classify_heat(10) == "SPIKING"
    assert classify_heat(11) == "HOT"     # just past spiking
    assert classify_heat(50) == "HOT"
    assert classify_heat(51) == "WARM"    # just past hot
    assert classify_heat(100) == "WARM"
    assert classify_heat(101) == "COLD"   # just past warm


def test_classify_heat_ignores_legacy_second_arg():
    # The old Stocktwits bullish-% arg must be accepted and ignored, never crash.
    assert classify_heat(5, 99.0) == "SPIKING"
    assert classify_heat(80, 10.0) == "WARM"
    assert classify_heat(30, None) == "HOT"


def test_social_signal_defaults():
    sig = SocialSignal(ticker="TSLA")
    assert sig.heat == "COLD"
    assert sig.ape_rank is None
    assert sig.error is None


def test_get_signals_returns_cold_on_error():
    provider = SocialSentimentProvider(portfolio_id="test")
    provider._cache = {}  # don't depend on on-disk cache
    with patch("social_sentiment.requests.get", side_effect=Exception("network error")):
        signals = provider.get_signals(["AAPL", "TSLA"])
    assert "AAPL" in signals
    # ApeWisdom failed → no rank → COLD (degrades gracefully, no crash)
    assert signals["AAPL"].heat == "COLD"
    assert signals["AAPL"].ape_rank is None


def test_get_signals_uses_apewisdom_rank():
    provider = SocialSentimentProvider(portfolio_id="test")
    provider._cache = {}
    mock_ape = {"TSLA": {"rank": 5, "mentions": 500, "upvotes": 200}}
    with patch.object(provider, "_fetch_apewisdom", return_value=mock_ape):
        signals = provider.get_signals(["TSLA"])
    assert signals["TSLA"].ape_rank == 5
    assert signals["TSLA"].heat == "SPIKING"        # rank <= 10
    assert signals["TSLA"].st_bullish_pct is None   # Stocktwits removed


def test_cache_is_written_and_read(tmp_path):
    provider = SocialSentimentProvider(portfolio_id="test")
    provider._cache = {}
    provider._cache_file = tmp_path / "test_social.json"
    with patch.object(provider, "_fetch_apewisdom", return_value={}):
        provider.get_signals(["NVDA"])
    assert provider._cache_file.exists()
    # Second call should read from cache without fetching ApeWisdom again.
    with patch.object(provider, "_fetch_apewisdom", side_effect=Exception("should not call")):
        signals = provider.get_signals(["NVDA"])
    assert "NVDA" in signals
