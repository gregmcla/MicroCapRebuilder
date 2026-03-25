#!/usr/bin/env python3
"""
Exchange Universe Provider for GScott.

Downloads NASDAQ exchange listing files to build a complete universe of
all US-listed common stocks. Used by UniverseProvider as a third source
alongside curated tickers and ETF holdings.

No API key required. Files are published daily by NASDAQ for free.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
CACHE_FILE = DATA_DIR / "exchange_universe_cache.json"

CACHE_TTL_DAYS = 7

NASDAQ_TRADED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
OTHER_LISTED_URL  = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


class ExchangeUniverseProvider:
    """
    Provides a complete list of US-listed common stock tickers from NASDAQ's
    free public exchange listing files.

    Caches results for 7 days. Falls back to stale cache if download fails.
    """

    def __init__(self, cache_file: Path = CACHE_FILE):
        self._cache_file = cache_file

    # ── Public API ──────────────────────────────────────────────────────────

    def get_tickers(self) -> List[str]:
        """Return all US common stock tickers, using cache when fresh."""
        cache = self._load_cache()
        if cache and self._is_fresh(cache) and "tickers" in cache:
            return cache["tickers"]

        try:
            tickers = self._download_and_parse()
            self._save_cache(tickers)
            print(f"  [ExchangeUniverse] Downloaded {len(tickers):,} tickers from exchange listings")
            return tickers
        except Exception as e:
            if cache and "tickers" in cache:
                print(f"  [ExchangeUniverse] Download failed ({e}), using {len(cache['tickers']):,} cached tickers")
                return cache["tickers"]
            print(f"  [ExchangeUniverse] Download failed ({e}) and no cache available, returning empty list")
            return []

    # ── Internal ────────────────────────────────────────────────────────────

    def _download_and_parse(self) -> List[str]:
        """Download both NASDAQ files and return combined filtered ticker list."""
        tickers: set = set()
        tickers.update(self._parse_nasdaq_traded())
        tickers.update(self._parse_other_listed())
        return sorted(tickers)

    def _parse_nasdaq_traded(self) -> set:
        """Parse nasdaqtraded.txt — all tickers traded on NASDAQ systems."""
        symbols = set()
        lines = self._fetch_lines(NASDAQ_TRADED_URL)
        for line in lines[1:]:  # skip header
            if line.startswith("File Creation"):
                break
            parts = line.split("|")
            if len(parts) < 9:
                continue
            # parts[5]=ETF, parts[7]=Test Issue, parts[8]=Financial Status
            if parts[5] == "N" and parts[7] == "N" and parts[8] == "N":
                sym = parts[1].strip()
                if self._is_valid_symbol(sym):
                    symbols.add(sym)
        return symbols

    def _parse_other_listed(self) -> set:
        """Parse otherlisted.txt — NYSE Arca, BATS, and other exchanges."""
        symbols = set()
        lines = self._fetch_lines(OTHER_LISTED_URL)
        for line in lines[1:]:  # skip header
            if line.startswith("File Creation"):
                break
            parts = line.split("|")
            if len(parts) < 7:
                continue
            # parts[4]=ETF, parts[6]=Test Issue
            if parts[4] == "N" and parts[6] == "N":
                sym = parts[0].strip()
                if self._is_valid_symbol(sym):
                    symbols.add(sym)
        return symbols

    def _is_valid_symbol(self, sym: str) -> bool:
        """Return True if this looks like a real common stock symbol."""
        if not sym or not sym.isalpha():
            return False
        if len(sym) > 5:
            return False
        # Exclude 5-char SPAC derivatives: warrants (W), rights (R), units (U)
        if len(sym) == 5 and sym[-1] in ("W", "R", "U"):
            return False
        return True

    def _fetch_lines(self, url: str) -> List[str]:
        """Download a URL and return its lines."""
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8").splitlines()

    def _is_fresh(self, cache: dict) -> bool:
        """Return True if cache was populated within TTL."""
        ts = cache.get("timestamp")
        if not ts:
            return False
        try:
            age = datetime.now() - datetime.fromisoformat(ts)
            return age < timedelta(days=CACHE_TTL_DAYS)
        except (ValueError, TypeError):
            return False

    def _load_cache(self) -> dict:
        """Load cache file, return empty dict if missing/corrupt."""
        if not self._cache_file.exists():
            return {}
        try:
            with open(self._cache_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_cache(self, tickers: List[str]):
        """Save tickers to cache atomically with timestamp."""
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._cache_file.with_suffix(".tmp")
        try:
            with open(tmp, "w") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "count": len(tickers),  # convenience field for human inspection
                    "tickers": tickers,
                }, f)
            tmp.replace(self._cache_file)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            raise
