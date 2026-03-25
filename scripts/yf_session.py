#!/usr/bin/env python3
"""
DataFrame-level disk cache for yfinance downloads.

yfinance ≥ 0.2.50 uses curl_cffi internally and rejects custom requests-cache
sessions. This module caches the *output* DataFrames to disk instead.

- Cache TTL: 4 hours (configurable via YF_CACHE_TTL_SECONDS env var)
- Backend: pickle files in data/yf_cache/
- Thread-safe: uses file-level locking via a lock dict

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

_CACHE_DIR = Path(__file__).parent.parent / "data" / "yf_cache"
_TTL = int(os.environ.get("YF_CACHE_TTL_SECONDS", 14400))  # 4 hour default
_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


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

    lock = _get_lock(cache_key)
    with lock:
        # Cache hit?
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < _TTL:
                try:
                    with open(cache_file, "rb") as f:
                        return pickle.load(f)
                except Exception as e:
                    print(f"Warning: corrupt cache file, removing: {e}")
                    cache_file.unlink(missing_ok=True)

        # Cache miss — download (no custom session; yfinance handles curl_cffi)
        try:
            df = yf.download(tickers, period=period, **kwargs)
        except Exception as e:
            print(f"Warning: yf.download failed for {tickers}: {e}")
            df = pd.DataFrame()

        # Persist non-empty results
        if not df.empty:
            try:
                with open(cache_file, "wb") as f:
                    pickle.dump(df, f)
            except Exception as e:
                print(f"Warning: failed to write cache file: {e}")

        return df


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
