"""Unit tests for scripts/cache_layer.py."""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from cache_layer import (
    TTL,
    CacheLogger,
    bars_ttl,
    cache_key,
    is_market_hours,
)


_NY = ZoneInfo("America/New_York")


# ─── cache_key ────────────────────────────────────────────────────────────────


def test_cache_key_stable():
    assert cache_key("HUT") == cache_key("HUT")
    assert cache_key({"a": 1}) == cache_key({"a": 1})


def test_cache_key_dict_order_independent():
    """Dicts with same content but different insertion order must hash identically."""
    assert cache_key({"a": 1, "b": 2}) == cache_key({"b": 2, "a": 1})


def test_cache_key_list_order_sensitive():
    """Lists are ordered; ['a','b'] must differ from ['b','a']."""
    assert cache_key(["a", "b"]) != cache_key(["b", "a"])


def test_cache_key_changes_on_input_change():
    """Adding 'Capital Markets' to industries must produce a different hash —
    this is the exact bug Greg hit live."""
    before = cache_key({"industries": ["Banks - Regional", "Credit Services"]})
    after = cache_key({"industries": ["Banks - Regional", "Credit Services", "Capital Markets"]})
    assert before != after


def test_cache_key_returns_16_hex_chars():
    k = cache_key("anything")
    assert len(k) == 16
    int(k, 16)  # raises if not valid hex


def test_cache_key_handles_unhashable_objects():
    """repr() fallback shouldn't crash on objects that aren't JSON-serializable."""

    class Custom:
        def __repr__(self):
            return "Custom()"

    k = cache_key(Custom())
    assert len(k) == 16


# ─── TTL constants ────────────────────────────────────────────────────────────


def test_ttl_constants_present_and_ordered():
    """Sanity check on the tier ordering — fundamentals are longest, AI is shortest."""
    assert TTL.AI_EPHEMERAL < TTL.NEWS_SHORT == TTL.SOCIAL_SHORT == TTL.BARS_INTRADAY
    assert TTL.BARS_INTRADAY < TTL.BARS_OVERNIGHT
    assert TTL.BARS_OVERNIGHT < TTL.UNIVERSE_DAILY
    assert TTL.UNIVERSE_DAILY < TTL.FUNDAMENTALS_QUARTERLY


# ─── is_market_hours / bars_ttl ───────────────────────────────────────────────


def test_market_hours_open():
    """Wednesday 14:00 ET → market open."""
    t = datetime(2026, 5, 6, 14, 0, tzinfo=_NY)  # Wed
    assert is_market_hours(t) is True


def test_market_hours_pre_open():
    """Wednesday 08:00 ET → before open."""
    t = datetime(2026, 5, 6, 8, 0, tzinfo=_NY)
    assert is_market_hours(t) is False


def test_market_hours_post_close():
    """Wednesday 17:00 ET → after close."""
    t = datetime(2026, 5, 6, 17, 0, tzinfo=_NY)
    assert is_market_hours(t) is False


def test_market_hours_weekend():
    """Saturday at noon → weekend, no trading."""
    t = datetime(2026, 5, 9, 12, 0, tzinfo=_NY)  # Sat
    assert is_market_hours(t) is False


def test_market_hours_open_boundary():
    """09:30 ET is open; 09:29 ET is not."""
    open_ = datetime(2026, 5, 6, 9, 30, tzinfo=_NY)
    pre = datetime(2026, 5, 6, 9, 29, tzinfo=_NY)
    assert is_market_hours(open_) is True
    assert is_market_hours(pre) is False


def test_bars_ttl_intraday_vs_overnight():
    intraday = datetime(2026, 5, 6, 14, 0, tzinfo=_NY)
    overnight = datetime(2026, 5, 6, 22, 0, tzinfo=_NY)
    assert bars_ttl(intraday) == TTL.BARS_INTRADAY
    assert bars_ttl(overnight) == TTL.BARS_OVERNIGHT


# ─── CacheLogger ──────────────────────────────────────────────────────────────


def test_cache_logger_emits_structured_extra(caplog):
    """Hit/miss/write each emit at INFO with cache name and key in extra."""
    log = CacheLogger("test_cache")
    with caplog.at_level(logging.INFO, logger="cache"):
        log.hit("abcdef0123456789", age_seconds=42)
        log.miss("ffffffffffffffff", reason="ttl_expired")
        log.write("abcdef0123456789", size_bytes=128)

    records = [r for r in caplog.records if r.name == "cache"]
    assert len(records) == 3
    assert records[0].cache == "test_cache"
    assert records[0].key == "abcdef012345"  # 12-char prefix
    assert records[0].age_s == 42
    assert records[1].reason == "ttl_expired"
    assert records[2].size == 128


def test_cache_logger_evict():
    log = CacheLogger("evict_test")
    # Smoke-test that evict() doesn't crash
    log.evict("0123456789abcdef", reason="manual")
