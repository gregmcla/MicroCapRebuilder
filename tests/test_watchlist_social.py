# tests/test_watchlist_social.py
import pytest
import sys
sys.path.insert(0, "scripts")
from watchlist_manager import WatchlistEntry

def test_watchlist_entry_has_social_fields():
    e = WatchlistEntry(ticker="AAPL")
    assert hasattr(e, "social_heat")
    assert hasattr(e, "social_rank")
    assert hasattr(e, "social_bullish_pct")
    assert e.social_heat == ""
    assert e.social_rank is None
    assert e.social_bullish_pct is None

def test_watchlist_entry_serializes_social_fields():
    import dataclasses
    e = WatchlistEntry(ticker="AAPL", social_heat="HOT", social_rank=35, social_bullish_pct=71.5)
    d = dataclasses.asdict(e)
    assert d["social_heat"] == "HOT"
    assert d["social_rank"] == 35
    assert d["social_bullish_pct"] == 71.5
