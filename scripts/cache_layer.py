"""
Shared utilities for caching across the trading system.

Three pieces:
  1. cache_key(parts) — canonical hash of arbitrary inputs. Use in cache file
     names so that ANY change to the inputs produces a different file. This is
     the fix for the "edit config, cache still serves old data" class of bugs.
  2. CacheLogger — structured wrapper around stdlib logging for cache events.
     Every hit/miss/write goes through here so we can grep activity by cache
     name, key prefix, or age.
  3. TTL — named TTL constants tiered by data volatility. Bars-intraday is
     short (1h) because prices move; fundamentals-quarterly is long (30d)
     because earnings cadence is quarterly. is_market_hours() helps callers
     pick between intraday and overnight bar TTLs.

Why a shared module: previously each cache file was hand-rolled with ad-hoc
keys, ad-hoc TTLs, and print() warnings. That made it impossible to (a) reason
about freshness consistently, (b) trace cache behavior under load, or (c) know
which keys had drifted from their inputs. Centralizing fixes all three.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


_NY = ZoneInfo("America/New_York")


# ─── TTL constants ────────────────────────────────────────────────────────────


class TTL:
    """Named TTLs in seconds, tiered by how fast the underlying data changes."""

    # yfinance bars during US market hours: prices move continuously
    BARS_INTRADAY = 3_600  # 1 hour

    # yfinance bars outside market hours: closes are settled, daily granularity
    BARS_OVERNIGHT = 43_200  # 12 hours

    # Universe membership (screener results, ETF holdings): tickers don't reclassify hourly
    UNIVERSE_DAILY = 86_400  # 24 hours

    # Fundamentals (.info dicts, earnings, margins): quarterly cadence
    FUNDAMENTALS_QUARTERLY = 2_592_000  # 30 days

    # News headlines: stale fast but not so fast we re-fetch every minute
    NEWS_SHORT = 3_600  # 1 hour

    # Social sentiment: heat shifts within hours
    SOCIAL_SHORT = 3_600  # 1 hour (down from previous 2h)

    # AI-generated outputs (audit briefs, narratives): re-render quickly
    AI_EPHEMERAL = 600  # 10 minutes


# ─── Cache key construction ───────────────────────────────────────────────────


def cache_key(parts: Any) -> str:
    """
    Build a stable 16-char hex key from arbitrary inputs.

    Uses canonical-form JSON (sorted keys, no whitespace) so that dicts hash to
    the same value regardless of insertion order. Falls back to repr() for
    non-JSON-serializable objects (preserves stability without throwing).

    Examples:
        cache_key("HUT") == cache_key("HUT")
        cache_key({"a": 1, "b": 2}) == cache_key({"b": 2, "a": 1})  # order-independent
        cache_key(["AAPL", "MSFT"]) != cache_key(["MSFT", "AAPL"])  # lists ARE order-sensitive

    Returns the first 16 hex chars of SHA256 — collision-resistant for the small
    universe of cache keys we generate while keeping filenames reasonable.
    """
    try:
        canonical = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=repr)
    except (TypeError, ValueError):
        canonical = repr(parts)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:16]


# ─── Market hours helper ──────────────────────────────────────────────────────


def is_market_hours(now: datetime | None = None) -> bool:
    """
    True if `now` falls within US equity regular session (9:30-16:00 ET, Mon-Fri).

    Doesn't account for half-days or holidays — those are rare and the cost of
    being wrong is "use a 12h TTL instead of 1h on a holiday afternoon," which
    is fine. Caller passes naive or UTC `now`; we convert to ET.
    """
    if now is None:
        now = datetime.now(tz=_NY)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=_NY)
    else:
        now = now.astimezone(_NY)

    # Mon=0 ... Sun=6
    if now.weekday() >= 5:
        return False
    open_minutes = 9 * 60 + 30
    close_minutes = 16 * 60
    cur_minutes = now.hour * 60 + now.minute
    return open_minutes <= cur_minutes < close_minutes


def bars_ttl(now: datetime | None = None) -> int:
    """Pick BARS_INTRADAY during market hours, BARS_OVERNIGHT otherwise."""
    return TTL.BARS_INTRADAY if is_market_hours(now) else TTL.BARS_OVERNIGHT


# ─── Structured cache logger ──────────────────────────────────────────────────


class CacheLogger:
    """
    Thin wrapper over `logging.getLogger("cache")` with structured fields.

    Every event carries: cache (name), key (12-char prefix), age_s (for hits),
    reason (for misses), size (for writes). Tools or humans can grep by cache
    name, sort by age, or filter on miss reasons ("config_hash_changed",
    "ttl_expired", "content_mismatch").

    Doesn't configure the logger itself — that's the caller's job (api/main.py
    sets the level and formatter at startup so all routes see the same format).
    """

    def __init__(self, cache_name: str):
        self._name = cache_name
        self._log = logging.getLogger("cache")

    def hit(self, key: str, age_seconds: float, **extra) -> None:
        self._log.info(
            "cache.hit",
            extra={
                "cache": self._name,
                "key": key[:12],
                "age_s": int(age_seconds),
                **extra,
            },
        )

    def miss(self, key: str, reason: str = "absent", **extra) -> None:
        self._log.info(
            "cache.miss",
            extra={"cache": self._name, "key": key[:12], "reason": reason, **extra},
        )

    def write(self, key: str, size_bytes: int = 0, **extra) -> None:
        self._log.info(
            "cache.write",
            extra={"cache": self._name, "key": key[:12], "size": size_bytes, **extra},
        )

    def evict(self, key: str, reason: str = "manual", **extra) -> None:
        self._log.info(
            "cache.evict",
            extra={"cache": self._name, "key": key[:12], "reason": reason, **extra},
        )


# ─── Module-level convenience ─────────────────────────────────────────────────


def get_logger(cache_name: str) -> CacheLogger:
    """Convenience constructor — `from cache_layer import get_logger`."""
    return CacheLogger(cache_name)


# Module exports
__all__ = [
    "TTL",
    "cache_key",
    "is_market_hours",
    "bars_ttl",
    "CacheLogger",
    "get_logger",
]


# Best-effort default config so any module that imports this and does its
# first cache hit before api/main.py runs still gets readable output.
# api/main.py can override the formatter and level for production runs.
def _ensure_default_config() -> None:
    log = logging.getLogger("cache")
    if log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s "
            "cache=%(cache)s key=%(key)s "
            "age_s=%(age_s)s reason=%(reason)s size=%(size)s",
            defaults={"cache": "-", "key": "-", "age_s": "-", "reason": "-", "size": "-"},
        )
    )
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    # Leave `propagate` at default True so test capture (caplog) and any
    # downstream root-logger handlers can also see cache events. Duplicate
    # output is rare in practice and easy to mute by removing the handler
    # below if api/main.py installs its own.


_ensure_default_config()
