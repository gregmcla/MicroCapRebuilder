#!/usr/bin/env python3
"""
Macro context provider for the AI allocator prompt.

Two responsibilities:
  1. Snapshot key macro indicators (oil, gold, dxy, vix, 10y, spy) — current
     price + day % change. Reuses yf_session disk cache.
  2. Fetch recent headlines for each held position via yfinance Ticker.news,
     cached to disk for 60 minutes.

Failure mode: every public function catches Exception and returns an empty
result. The analyze pipeline must never break because of a news fetch issue.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yfinance as yf

from yf_session import cached_download

logger = logging.getLogger(__name__)

_NEWS_CACHE_DIR = Path(__file__).parent.parent / "data" / "news_cache"

# Hardcoded macro indicator universe — pure market data, no policy
INDICATORS: list[dict] = [
    {"symbol": "CL=F",     "name": "WTI Crude"},
    {"symbol": "BZ=F",     "name": "Brent"},
    {"symbol": "GC=F",     "name": "Gold"},
    {"symbol": "DX-Y.NYB", "name": "DXY"},
    {"symbol": "^VIX",     "name": "VIX"},
    {"symbol": "^TNX",     "name": "US 10Y"},
    {"symbol": "SPY",      "name": "SPY"},
]


def get_indicator_snapshots() -> list[dict]:
    """
    Fetch current price + day % change for each macro indicator.

    Returns list of dicts: [{symbol, name, price, day_pct}, ...].
    Returns [] on any failure — caller must handle empty result.
    """
    try:
        results: list[dict] = []
        for ind in INDICATORS:
            try:
                df = cached_download(ind["symbol"], period="5d", progress=False)
                if df is None or df.empty or "Close" not in df.columns:
                    continue
                closes = df["Close"].dropna()
                if len(closes) < 2:
                    continue
                today = float(closes.iloc[-1])
                prev = float(closes.iloc[-2])
                if prev == 0:
                    continue
                day_pct = (today - prev) / prev * 100.0
                results.append({
                    "symbol": ind["symbol"],
                    "name": ind["name"],
                    "price": today,
                    "day_pct": day_pct,
                })
            except Exception as e:
                logger.warning("macro_context: indicator fetch failed for %s: %s", ind["symbol"], e)
                continue
        return results
    except Exception as e:
        logger.warning("macro_context: get_indicator_snapshots failed: %s", e)
        return []
