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


def _save_cached_headlines(ticker: str, headlines: list[dict]) -> None:
    """Save headlines for a ticker to disk cache. Silent on failure."""
    try:
        _NEWS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = _NEWS_CACHE_DIR / f"{ticker.upper()}.json"
        with open(cache_file, "w") as f:
            json.dump(headlines, f)
    except Exception as e:
        logger.warning("macro_context: cache write failed for %s: %s", ticker, e)


def _load_cached_headlines(ticker: str, ttl_seconds: int) -> Optional[list[dict]]:
    """Load headlines from disk cache if fresh, else None."""
    try:
        cache_file = _NEWS_CACHE_DIR / f"{ticker.upper()}.json"
        if not cache_file.exists():
            return None
        age = time.time() - cache_file.stat().st_mtime
        if age > ttl_seconds:
            return None
        with open(cache_file) as f:
            return json.load(f)
    except Exception as e:
        logger.warning("macro_context: cache read failed for %s: %s", ticker, e)
        return None


def get_position_headlines(
    tickers: list[str],
    max_per_ticker: int = 2,
    ttl_seconds: int = 3600,
) -> dict[str, list[dict]]:
    """
    Fetch recent headlines for each ticker.

    For each ticker, returns up to max_per_ticker dicts:
        {"title": str, "publisher": str, "age_minutes": int}

    Uses disk cache (TTL ttl_seconds). Cache miss → yfinance Ticker.news call.
    Per-ticker failures yield empty lists, never raise.
    """
    if not tickers:
        return {}

    result: dict[str, list[dict]] = {}
    now = time.time()

    for ticker in tickers:
        try:
            ticker_uc = ticker.strip().upper()
            cached = _load_cached_headlines(ticker_uc, ttl_seconds)
            if cached is not None:
                result[ticker_uc] = cached[:max_per_ticker]
                continue

            # Cache miss — fetch from yfinance
            t = yf.Ticker(ticker_uc)
            raw_news = getattr(t, "news", None) or []
            parsed: list[dict] = []
            for n in raw_news[:max_per_ticker]:
                title = n.get("title") or ""
                publisher = n.get("publisher") or "unknown"
                pub_ts = n.get("providerPublishTime")
                if pub_ts:
                    age_minutes = max(0, int((now - pub_ts) / 60))
                else:
                    age_minutes = -1
                if title:
                    parsed.append({
                        "title": title,
                        "publisher": publisher,
                        "age_minutes": age_minutes,
                    })

            _save_cached_headlines(ticker_uc, parsed)
            result[ticker_uc] = parsed
        except Exception as e:
            logger.warning("macro_context: headline fetch failed for %s: %s", ticker, e)
            result[ticker.strip().upper()] = []

    return result


def _fmt_age(minutes: int) -> str:
    if minutes < 0:
        return "?"
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"


def format_macro_block(
    indicators: list[dict],
    headlines: dict[str, list[dict]],
) -> str:
    """
    Render indicator snapshots + per-ticker headlines as a prompt block.

    Returns an empty string if both inputs are empty (caller drops the block).
    No policy language — pure data, per the data-vs-policy bedrock.
    """
    if not indicators and not any(headlines.values()):
        return ""

    lines: list[str] = []
    fetched = datetime.now(timezone.utc).strftime("%H:%M UTC")
    lines.append(f"MACRO CONTEXT (fetched {fetched}):")

    # Indicators — single line, comma-separated
    if indicators:
        parts: list[str] = []
        for ind in indicators:
            sign = "+" if ind["day_pct"] >= 0 else ""
            parts.append(
                f"{ind['name']} ${ind['price']:,.2f} ({sign}{ind['day_pct']:.1f}%)"
            )
        lines.append("  INDICATORS: " + ", ".join(parts))

    # Headlines — one section per ticker that has any
    tickers_with_news = [t for t, hs in headlines.items() if hs]
    if tickers_with_news:
        lines.append("  POSITION HEADLINES (last 24-48h):")
        for ticker in tickers_with_news:
            for h in headlines[ticker]:
                age = _fmt_age(h.get("age_minutes", -1))
                title = h["title"]
                pub = h.get("publisher", "?")
                lines.append(f"    {ticker}: {title} — {pub}, {age}")

    return "\n".join(lines) + "\n"


def get_macro_context(held_tickers: list[str]) -> str:
    """
    Top-level entry point. Returns a fully formatted MACRO CONTEXT block,
    or empty string on total failure.

    Caller (ai_allocator) should treat empty string as "no block to inject".
    """
    try:
        indicators = get_indicator_snapshots()
        headlines = get_position_headlines(held_tickers, max_per_ticker=2, ttl_seconds=3600)
        return format_macro_block(indicators, headlines)
    except Exception as e:
        logger.warning("macro_context: get_macro_context failed: %s", e)
        return ""
