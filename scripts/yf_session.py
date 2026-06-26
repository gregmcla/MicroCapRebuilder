#!/usr/bin/env python3
"""
DataFrame-level disk cache for yfinance downloads.

yfinance ≥ 0.2.50 uses curl_cffi internally and rejects custom requests-cache
sessions. This module caches the *output* DataFrames to disk instead.

- Tiered TTL: 4h during US market hours (9:30-16:00 ET), 12h overnight.
  Override globally via YF_CACHE_TTL_SECONDS env var (used by tests + manual
  cache stretching when yfinance is rate-limiting).
- sweep_stale_cache() bounds the cache dir; call it at scan start.
- Backend: pickle files in data/yf_cache/
- Thread-safe: uses file-level locking via a lock dict
- Defense: content validation rejects MultiIndex DataFrames whose ticker label
  doesn't match the request (Fix 19a).
- Observability: every read/write/eviction emits a structured log event via
  cache_layer.CacheLogger.

Usage:
    from yf_session import cached_download
    df = cached_download("AAPL", period="1y", progress=False)
    df = cached_download(["AAPL", "MSFT"], period="3mo", progress=False)
"""

import hashlib
import os
import pickle
import threading
import time
from pathlib import Path
from typing import Union

import pandas as pd
import yfinance as yf

from cache_layer import TTL, bars_ttl, get_logger
from logging_setup import get_logger as _get_diag_logger

_diag = _get_diag_logger(__name__)

_CACHE_DIR = Path(__file__).parent.parent / "data" / "yf_cache"
# Optional global override for tests / manual cache stretching. When set, it
# takes precedence over the tiered intraday/overnight values; leave unset for
# normal operation so bars_ttl() chooses based on market hours.
_TTL_OVERRIDE: int | None = (
    int(os.environ["YF_CACHE_TTL_SECONDS"])
    if os.environ.get("YF_CACHE_TTL_SECONDS")
    else None
)
_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()
_log = get_logger("yf_bars")


def _current_ttl() -> int:
    """Pick the right TTL: env override beats tiered, tiered picks intraday vs overnight."""
    if _TTL_OVERRIDE is not None:
        return _TTL_OVERRIDE
    return bars_ttl()


def sweep_stale_cache(max_age_s: int | None = None) -> int:
    """Delete bars-cache pickle files older than max_age_s (default: overnight TTL).

    The per-request keys accumulate forever otherwise — production had 18k files /
    6.3 GB, 92% of them stale. Anything older than the overnight TTL can never be a
    valid hit, so it's safe to remove. Skips the shared stock_info_cache.pkl.
    Returns the number of files deleted. Call once at scan start, not per download.
    """
    if max_age_s is None:
        max_age_s = TTL.BARS_OVERNIGHT
    if not _CACHE_DIR.exists():
        return 0
    now = time.time()
    deleted = 0
    for f in _CACHE_DIR.glob("*.pkl"):
        if f.name == "stock_info_cache.pkl":
            continue
        try:
            if now - f.stat().st_mtime > max_age_s:
                f.unlink(missing_ok=True)
                deleted += 1
        except OSError:
            continue
    if deleted:
        _diag.info("swept %d stale bars-cache files (older than %ds)", deleted, max_age_s)
    return deleted


def _get_lock(key: str) -> threading.Lock:
    with _locks_lock:
        if key not in _locks:
            _locks[key] = threading.Lock()
        return _locks[key]


def cached_download(
    tickers: Union[str, list],
    period: str = "1y",
    **kwargs,
) -> pd.DataFrame:
    """
    Download price data with disk caching.

    Args:
        tickers: Single ticker string or list of tickers
        period:  yfinance period string ("1y", "3mo", etc.)
        **kwargs: Passed through to yf.download()

    Returns:
        DataFrame of OHLCV data (may be empty on error)
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Build a stable cache key
    ticker_str = tickers if isinstance(tickers, str) else " ".join(sorted(tickers))
    key_parts = f"{ticker_str}|{period}|{sorted(kwargs.items())}"
    cache_key = hashlib.md5(key_parts.encode()).hexdigest()
    cache_file = _CACHE_DIR / f"{cache_key}.pkl"

    expected_tickers = (
        {tickers.upper()} if isinstance(tickers, str) else {t.upper() for t in tickers}
    )

    lock = _get_lock(cache_key)
    ttl = _current_ttl()
    with lock:
        # Cache hit?
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < ttl:
                try:
                    with open(cache_file, "rb") as f:
                        cached_df = pickle.load(f)
                    if _content_matches_tickers(cached_df, expected_tickers):
                        _log.hit(cache_key, age, ticker=ticker_str, period=period, ttl=ttl)
                        return cached_df
                    _log.evict(cache_key, reason="content_mismatch", ticker=ticker_str)
                    print(
                        f"Warning: cache content mismatch for {tickers} ({cache_key[:8]}); "
                        "deleting and refetching"
                    )
                    cache_file.unlink(missing_ok=True)
                except Exception as e:
                    _log.evict(cache_key, reason="corrupt", error=str(e))
                    _diag.warning("corrupt cache file, removing: %s", e)
                    cache_file.unlink(missing_ok=True)
            else:
                _log.miss(cache_key, reason="ttl_expired", age_s=int(age), ttl=ttl, ticker=ticker_str)
        else:
            _log.miss(cache_key, reason="absent", ticker=ticker_str, period=period)

        # Cache miss — download with hard timeout to prevent indefinite hangs
        _DOWNLOAD_TIMEOUT = 60  # seconds per batch chunk
        result = [pd.DataFrame()]

        def _do_download():
            try:
                result[0] = yf.download(tickers, period=period, **kwargs)
            except Exception as e:
                _diag.warning("yf.download failed for %s: %s", tickers, e)

        t = threading.Thread(target=_do_download, daemon=True)
        t.start()
        t.join(timeout=_DOWNLOAD_TIMEOUT)
        if t.is_alive():
            ticker_label = tickers if isinstance(tickers, str) else f"{len(tickers)} tickers"
            _diag.warning("yf.download timed out after %ss for %s", _DOWNLOAD_TIMEOUT, ticker_label)
        df = result[0]

        # Persist non-empty results — but only if the response actually matches the request.
        # yfinance has historically returned wrong-ticker data on rare race/rate-limit paths;
        # writing that to disk poisons future scoring with hallucinated prices (HUT@$74 incident).
        if not df.empty:
            if not _content_matches_tickers(df, expected_tickers):
                _log.evict(cache_key, reason="download_mismatch", ticker=ticker_str)
                print(
                    f"Warning: yf.download returned mismatched ticker data for {tickers}; "
                    "discarding response, not caching"
                )
                return pd.DataFrame()
            try:
                with open(cache_file, "wb") as f:
                    pickle.dump(df, f)
                _log.write(cache_key, size_bytes=cache_file.stat().st_size, ticker=ticker_str, period=period)
            except Exception as e:
                _diag.warning("failed to write cache file: %s", e)

        return df


def _content_matches_tickers(df: pd.DataFrame, expected: set[str]) -> bool:
    """
    Verify a cached/downloaded DataFrame actually contains data for the requested tickers.

    yfinance returns MultiIndex columns when group_by='ticker' or when multiple tickers
    are requested; the second level of that index carries the ticker symbol. If that
    label set diverges from what we asked for, the file was poisoned (e.g. HUT cache
    file ended up holding MNDY data) and must be rejected.

    For single-ticker, non-MultiIndex DataFrames there's no ticker label embedded, so
    we can't verify; return True (no signal either way).
    """
    if df is None or df.empty:
        return True
    if not isinstance(df.columns, pd.MultiIndex):
        return True
    # Try every level except the first ('Close','High',...) — ticker can sit at level 0 or 1
    expected_upper = {t.upper() for t in expected}
    for level in range(df.columns.nlevels):
        labels = {str(v).upper() for v in df.columns.get_level_values(level)}
        # skip OHLCV-style levels
        if labels & {"CLOSE", "HIGH", "LOW", "OPEN", "VOLUME", "ADJ CLOSE"}:
            continue
        if labels and labels.issubset(expected_upper):
            return True
        if labels and not (labels & expected_upper):
            return False
    return True


def clear_cache() -> int:
    """Remove all cached files. Returns number of files deleted."""
    if not _CACHE_DIR.exists():
        return 0
    deleted = 0
    for f in _CACHE_DIR.glob("*.pkl"):
        f.unlink(missing_ok=True)
        deleted += 1
    return deleted


# ---------------------------------------------------------------------------
# Legacy shim — older code that calls get_session() will get None, which is
# the same as not passing a session (yfinance uses its own curl_cffi session).
# ---------------------------------------------------------------------------
def get_session():
    """Deprecated. yfinance now manages its own session via curl_cffi."""
    return None
