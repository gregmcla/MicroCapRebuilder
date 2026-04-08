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
