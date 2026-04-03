#!/usr/bin/env python3
"""
screener_provider.py — Universe building via yfscreen (Yahoo Finance screener).

Replaces the broken ETF-holdings approach (yfinance top-10 truncation) with
full result sets from yfscreen.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from yfscreen import create_query, create_payload, get_data

DATA_DIR = Path(__file__).parent.parent / "data"


def build_screener_filters(config: dict) -> list:
    """
    Build yfscreen filter list from a config dict.

    Supported keys:
        sectors (list[str])      — OR'd eq filters on 'sector'
        industries (list[str])   — OR'd eq filters on 'industry'
        market_cap_min (int)     — lower bound of intradaymarketcap
        market_cap_max (int)     — upper bound of intradaymarketcap
        region (str)             — default "us"

    Returns list of yfscreen filter tuples.
    """
    filters = []

    region = config.get("region", "us")
    filters.append(["eq", ["region", region]])

    sectors = config.get("sectors") or []
    for sector in sectors:
        filters.append(["eq", ["sector", sector]])

    industries = config.get("industries") or []
    for industry in industries:
        filters.append(["eq", ["industry", industry]])

    cap_min = config.get("market_cap_min")
    cap_max = config.get("market_cap_max")
    if cap_min is not None and cap_max is not None:
        filters.append(["btwn", ["intradaymarketcap", cap_min, cap_max]])
    elif cap_min is not None:
        filters.append(["gt", ["intradaymarketcap", cap_min]])
    elif cap_max is not None:
        filters.append(["lt", ["intradaymarketcap", cap_max]])

    return filters


def filter_us_listed(tickers: list) -> list:
    """
    Remove non-US-listed tickers:
      - Symbols containing a dot (e.g., "BLD.TO")
      - Symbols with 5+ characters ending in F or Y (OTC ADRs, e.g., "CRWOF", "AVHNY")

    Returns filtered list preserving original order.
    """
    result = []
    for ticker in tickers:
        if "." in ticker:
            continue
        if len(ticker) >= 5 and ticker[-1].upper() in ("F", "Y"):
            continue
        result.append(ticker)
    return result


def run_screen(config: dict, portfolio_id: str = None) -> list:
    """
    Run a yfscreen query and return a deduplicated list of US-listed ticker strings.

    Caches results for 24 hours at:
        data/portfolios/{portfolio_id}/screener_cache.json

    Cache is skipped if portfolio_id is None.

    Args:
        config:       Screener config dict (see build_screener_filters).
        portfolio_id: Portfolio identifier used for cache path.

    Returns:
        List of ticker strings.
    """
    # --- cache check ---
    cache_path = None
    if portfolio_id:
        cache_path = DATA_DIR / "portfolios" / portfolio_id / "screener_cache.json"
        if cache_path.exists():
            try:
                with cache_path.open() as f:
                    cached = json.load(f)
                ts = datetime.fromisoformat(cached["timestamp"])
                now = datetime.now(timezone.utc)
                # make ts timezone-aware if needed
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_hours = (now - ts).total_seconds() / 3600
                if age_hours < 24:
                    tickers = cached["tickers"]
                    print(
                        f"[screener] Using cached results ({cached['count']} tickers,"
                        f" {age_hours:.1f}h old)"
                    )
                    return tickers
            except Exception as e:
                print(f"[screener] Cache read error, re-running screen: {e}")

    # --- build query ---
    filters = build_screener_filters(config)
    query = create_query(filters)
    payload = create_payload(
        "equity",
        query,
        sort_field="intradaymarketcap",
        sort_type="DESC",
    )
    payload["size"] = 250

    all_tickers = []
    max_pages = 20

    for page in range(max_pages):
        payload["offset"] = page * 250
        try:
            df = get_data(payload)
        except Exception as e:
            print(f"[screener] Page {page} fetch error: {e}")
            break

        if df is None or df.empty:
            break

        if "symbol" not in df.columns:
            print(f"[screener] Page {page}: no 'symbol' column in response")
            break

        page_tickers = df["symbol"].dropna().tolist()
        all_tickers.extend(page_tickers)

        # If fewer than a full page came back, we've exhausted the results
        if len(page_tickers) < 250:
            break

    raw_count = len(all_tickers)
    filtered = filter_us_listed(all_tickers)
    # deduplicate while preserving order
    seen = set()
    unique = []
    for t in filtered:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    print(f"[screener] {raw_count} raw → {len(unique)} US-listed unique tickers")

    # --- write cache ---
    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("w") as f:
                json.dump(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "count": len(unique),
                        "tickers": unique,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            print(f"[screener] Cache write error: {e}")

    return unique


# ---------------------------------------------------------------------------
# Claude AI Refinement
# ---------------------------------------------------------------------------

def _get_api_key() -> Optional[str]:
    """Get Anthropic API key from environment or .env file."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _refinement_cache_path(portfolio_id: str) -> Path:
    """Return path to the refinement cache file for a portfolio."""
    return DATA_DIR / "portfolios" / portfolio_id / "refinement_cache.json"


def _load_refinement_cache(portfolio_id: str, max_age_days: int = 7) -> Optional[list]:
    """Load refinement cache if it exists and is within max_age_days."""
    cache_path = _refinement_cache_path(portfolio_id)
    if not cache_path.exists():
        return None
    try:
        with cache_path.open() as f:
            cached = json.load(f)
        ts = datetime.fromisoformat(cached["timestamp"])
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_days = (now - ts).total_seconds() / 86400
        if age_days < max_age_days:
            print(f"[refinement] Using cached results ({cached['count']} tickers, {age_days:.1f}d old)")
            return cached["tickers"]
    except Exception as e:
        print(f"[refinement] Cache read error: {e}")
    return None


def _save_refinement_cache(tickers: list, portfolio_id: str) -> None:
    """Save refinement results to cache."""
    cache_path = _refinement_cache_path(portfolio_id)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w") as f:
            json.dump(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "count": len(tickers),
                    "tickers": tickers,
                },
                f,
                indent=2,
            )
    except Exception as e:
        print(f"[refinement] Cache write error: {e}")


def maybe_refine_with_claude(tickers: list, refinement_config: dict, portfolio_id: str = None) -> list:
    """
    Optionally filter a ticker list using Claude for thematic portfolio refinement.

    Args:
        tickers:           List of ticker strings from the screener.
        refinement_config: Dict with keys: enabled (bool), prompt (str).
        portfolio_id:      Portfolio identifier used for cache path.

    Returns:
        Filtered list of tickers (subset of input), or original list unchanged.
    """
    if not refinement_config.get("enabled", False):
        return tickers

    if len(tickers) < 50:
        print(f"[refinement] Skipping — only {len(tickers)} tickers (need ≥50)")
        return tickers

    prompt_text = refinement_config.get("prompt", "")
    if not prompt_text:
        return tickers

    # Check cache
    if portfolio_id:
        cached = _load_refinement_cache(portfolio_id)
        if cached is not None:
            # Validate cached tickers against current ticker set
            original_set = set(tickers)
            valid = [t for t in cached if t in original_set]
            return valid

    # Call Claude
    try:
        import anthropic

        api_key = _get_api_key()
        if not api_key:
            print("[refinement] Warning: ANTHROPIC_API_KEY not found — skipping refinement")
            return tickers

        client = anthropic.Anthropic(api_key=api_key, timeout=120.0)

        ticker_list_str = ", ".join(tickers)
        user_prompt = (
            f"You are filtering a stock universe for a thematic portfolio.\n\n"
            f"SCREENER RESULTS ({len(tickers)} tickers):\n"
            f"{ticker_list_str}\n\n"
            f"FILTER CRITERIA:\n"
            f"{prompt_text}\n\n"
            f"Return ONLY a JSON array of ticker symbols that match the criteria. "
            f"Include tickers that clearly fit and exclude those that don't. "
            f"Aim for 30-100 tickers.\n\n"
            f'Example: ["STRL", "ACM", "DY", "BLD"]'
        )

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = message.content[0].text

        # Parse JSON array from response
        match = re.search(r"\[.*?\]", response_text, re.DOTALL)
        if not match:
            print("[refinement] Warning: could not find JSON array in Claude response — returning original")
            return tickers

        raw_filtered = json.loads(match.group(0))

        # Validate: only keep tickers that were in the original list
        original_set = set(tickers)
        filtered = [t.upper() for t in raw_filtered if isinstance(t, str) and t.upper() in original_set]

        print(f"[refinement] Claude filtered {len(tickers)} → {len(filtered)} tickers")

        if portfolio_id:
            _save_refinement_cache(filtered, portfolio_id)

        return filtered

    except Exception as e:
        print(f"[refinement] Warning: Claude refinement failed ({e}) — returning original tickers")
        return tickers
