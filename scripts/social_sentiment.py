#!/usr/bin/env python3
"""
Social Sentiment Provider — ApeWisdom + Stocktwits risk overlay.

Fetches retail sentiment signals to detect pump-and-dump risk.
Never modifies quant scores — metadata only.

Heat levels:
  COLD    — not trending, factor signal likely organic
  WARM    — some retail interest, watch it
  HOT     — high retail attention, scrutinize entry
  SPIKING — pump watch, AI gets hard warning
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
SOCIAL_CACHE_DIR = DATA_DIR / "social_cache"
SOCIAL_CACHE_DIR.mkdir(exist_ok=True)

CACHE_TTL = 7200  # 2 hours

APE_URL = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"
ST_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"

APE_TIMEOUT = 8
ST_TIMEOUT = 5
ST_DELAY = 0.4  # seconds between Stocktwits calls (~150/hr max)


@dataclass
class SocialSignal:
    ticker: str
    ape_rank: Optional[int] = None
    ape_mentions: int = 0
    ape_upvotes: int = 0
    st_bullish_pct: Optional[float] = None
    st_message_count: int = 0
    heat: str = "COLD"
    fetched_at: float = field(default_factory=time.time)
    error: Optional[str] = None


def classify_heat(ape_rank: Optional[int], st_bullish_pct: Optional[float]) -> str:
    """
    Classify social heat level from ApeWisdom rank and Stocktwits bullish %.

    SPIKING requires BOTH rank <=20 AND st_bullish_pct > 75.
    HOT requires rank 21-50 OR st_bullish_pct 65-80 (or rank <=20 without ST data).
    WARM requires rank 51-100 OR st_bullish_pct 55-65.
    COLD otherwise.
    """
    rank_spiking = ape_rank is not None and ape_rank <= 20
    st_spiking = st_bullish_pct is not None and st_bullish_pct > 75

    if rank_spiking and st_spiking:
        return "SPIKING"

    rank_hot = ape_rank is not None and ape_rank <= 50
    st_hot = st_bullish_pct is not None and st_bullish_pct > 65

    if rank_hot or st_hot:
        return "HOT"

    rank_warm = ape_rank is not None and ape_rank <= 100
    st_warm = st_bullish_pct is not None and st_bullish_pct > 55

    # When both signals are present, ST cold (<= 55%) overrides rank-based WARM
    if rank_warm and st_bullish_pct is not None and not st_warm:
        return "COLD"

    if rank_warm or st_warm:
        return "WARM"

    return "COLD"


class SocialSentimentProvider:
    """Fetches and caches social sentiment signals for a portfolio's watchlist."""

    def __init__(self, portfolio_id: str = None):
        self.portfolio_id = portfolio_id or "default"
        self._cache_file = SOCIAL_CACHE_DIR / f"{self.portfolio_id}_social.json"
        self._cache: dict[str, dict] = self._load_cache()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_signals(self, tickers: list[str]) -> dict[str, SocialSignal]:
        """
        Return SocialSignal for each ticker. Uses cache where fresh.
        Fetches ApeWisdom once then Stocktwits per-ticker for uncached.
        """
        tickers = [t.upper() for t in tickers]
        now = time.time()

        # Check which tickers need fresh data
        stale = [t for t in tickers if not self._is_fresh(t, now)]

        if stale:
            try:
                ape_map = self._fetch_apewisdom()
            except Exception as e:
                ape_map = {}
                print(f"[social] ApeWisdom fetch failed: {e}")

            for ticker in stale:
                ticker_error = None
                try:
                    st_bullish, st_count = self._fetch_stocktwits(ticker)
                    time.sleep(ST_DELAY)
                except Exception as e:
                    st_bullish, st_count = None, 0
                    ticker_error = str(e)
                    print(f"[social] Stocktwits fetch failed for {ticker}: {e}")

                ape_data = ape_map.get(ticker, {})
                heat = classify_heat(ape_data.get("rank"), st_bullish)

                self._cache[ticker] = {
                    "ticker": ticker,
                    "ape_rank": ape_data.get("rank"),
                    "ape_mentions": ape_data.get("mentions", 0),
                    "ape_upvotes": ape_data.get("upvotes", 0),
                    "st_bullish_pct": st_bullish,
                    "st_message_count": st_count,
                    "heat": heat,
                    "fetched_at": now,
                    "error": ticker_error,
                }

            self._save_cache()

        return {t: self._to_signal(self._cache.get(t, {"ticker": t})) for t in tickers}

    # ── Fetchers ──────────────────────────────────────────────────────────────

    def _fetch_apewisdom(self) -> dict[str, dict]:
        """One call — returns rank map for all top-100 tickers."""
        resp = requests.get(APE_URL, timeout=APE_TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return {
            r["ticker"].upper(): {
                "rank": r["rank"],
                "mentions": r.get("mentions", 0),
                "upvotes": r.get("upvotes", 0),
            }
            for r in results
            if r.get("ticker")
        }

    def _fetch_stocktwits(self, ticker: str) -> tuple[Optional[float], int]:
        """Returns (bullish_pct, message_count) from last 30 Stocktwits messages."""
        url = ST_URL.format(ticker=ticker)
        resp = requests.get(url, timeout=ST_TIMEOUT)
        if resp.status_code == 404:
            return None, 0
        resp.raise_for_status()
        messages = resp.json().get("messages", [])
        sentiments = [
            m["entities"]["sentiment"]["basic"]
            for m in messages
            if m.get("entities", {}).get("sentiment")
        ]
        if not sentiments:
            return None, 0
        bullish = sum(1 for s in sentiments if s == "Bullish")
        return round(bullish / len(sentiments) * 100, 1), len(sentiments)

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _is_fresh(self, ticker: str, now: float) -> bool:
        entry = self._cache.get(ticker)
        if not entry:
            return False
        # Error entries are never considered fresh — always re-fetch
        if entry.get("error"):
            return False
        return (now - entry.get("fetched_at", 0)) < CACHE_TTL

    def _load_cache(self) -> dict:
        if self._cache_file.exists():
            try:
                return json.loads(self._cache_file.read_text())
            except Exception as e:
                print(f"[social] Cache load failed, starting fresh: {e}")
                return {}
        return {}

    def _save_cache(self):
        # Only persist entries without errors to avoid polluting cache with transient failures
        clean = {k: v for k, v in self._cache.items() if not v.get("error")}
        self._cache_file.write_text(json.dumps(clean, indent=2))

    def _to_signal(self, d: dict) -> SocialSignal:
        return SocialSignal(
            ticker=d.get("ticker", ""),
            ape_rank=d.get("ape_rank"),
            ape_mentions=d.get("ape_mentions", 0),
            ape_upvotes=d.get("ape_upvotes", 0),
            st_bullish_pct=d.get("st_bullish_pct"),
            st_message_count=d.get("st_message_count", 0),
            heat=d.get("heat", "COLD"),
            fetched_at=d.get("fetched_at", 0.0),
            error=d.get("error"),
        )
