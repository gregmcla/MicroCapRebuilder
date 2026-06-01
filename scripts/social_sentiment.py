#!/usr/bin/env python3
"""
Social Sentiment Provider — ApeWisdom retail-attention risk overlay.

Fetches retail sentiment signals to detect pump-and-dump risk.
(Stocktwits was removed 2026-06-01 — it served HTTP 403 on every request and
never produced a usable signal; heat is now driven purely by ApeWisdom rank.)
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

from cache_layer import TTL, get_logger

DATA_DIR = Path(__file__).parent.parent / "data"
SOCIAL_CACHE_DIR = DATA_DIR / "social_cache"
SOCIAL_CACHE_DIR.mkdir(exist_ok=True)

# Tightened from 2h → 1h (Fix 19c). Sentiment shifts faster than 2 hours;
# stale heat readings led to "WARM" labels on names that had cooled overnight.
CACHE_TTL = TTL.SOCIAL_SHORT  # 1 hour
_log = get_logger("social")

APE_URL = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"

APE_TIMEOUT = 8


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


def classify_heat(ape_rank: Optional[int], _st_bullish_pct: Optional[float] = None) -> str:
    """
    Classify social heat from ApeWisdom (WSB) trending rank.

    Stocktwits was removed, so heat is now driven purely by ApeWisdom rank — a
    proxy for retail attention / pump risk. The second parameter is retained for
    backward-compatible call sites and is ignored.

      SPIKING — rank <= 10   (extreme retail frenzy; AI gets a pump warning)
      HOT     — rank <= 50
      WARM    — rank <= 100
      COLD    — unranked / outside the top 100
    """
    if ape_rank is None:
        return "COLD"
    if ape_rank <= 10:
        return "SPIKING"
    if ape_rank <= 50:
        return "HOT"
    if ape_rank <= 100:
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
        Fetches ApeWisdom once (a single call returns the whole top-100 rank
        map); heat is derived from rank — no per-ticker network calls.
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
                ape_data = ape_map.get(ticker, {})
                heat = classify_heat(ape_data.get("rank"))

                self._cache[ticker] = {
                    "ticker": ticker,
                    "ape_rank": ape_data.get("rank"),
                    "ape_mentions": ape_data.get("mentions", 0),
                    "ape_upvotes": ape_data.get("upvotes", 0),
                    "st_bullish_pct": None,    # Stocktwits removed
                    "st_message_count": 0,
                    "heat": heat,
                    "fetched_at": now,
                    "error": None,
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

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _is_fresh(self, ticker: str, now: float) -> bool:
        entry = self._cache.get(ticker)
        if not entry:
            _log.miss(f"{self.portfolio_id}:{ticker}", reason="absent")
            return False
        # Error entries are never considered fresh — always re-fetch
        if entry.get("error"):
            _log.miss(f"{self.portfolio_id}:{ticker}", reason="prior_error")
            return False
        age = now - entry.get("fetched_at", 0)
        if age < CACHE_TTL:
            _log.hit(f"{self.portfolio_id}:{ticker}", age)
            return True
        _log.miss(f"{self.portfolio_id}:{ticker}", reason="ttl_expired", age_s=int(age))
        return False

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
