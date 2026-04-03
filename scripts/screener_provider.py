#!/usr/bin/env python3
"""
screener_provider.py — Universe building via yfscreen (Yahoo Finance screener).

Replaces the broken ETF-holdings approach (yfinance top-10 truncation) with
full result sets from yfscreen.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

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
