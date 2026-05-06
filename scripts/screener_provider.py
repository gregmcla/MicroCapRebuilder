#!/usr/bin/env python3
"""
screener_provider.py — Universe building via yfscreen (Yahoo Finance screener).

Replaces the broken ETF-holdings approach (yfinance top-10 truncation) with
full result sets from yfscreen.
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cache_layer import TTL, cache_key, get_logger
from schema import CLAUDE_MODEL
from yfscreen import create_query, create_payload, get_data

DATA_DIR = Path(__file__).parent.parent / "data"

_screener_log = get_logger("screener")
_refinement_log = get_logger("refinement")

# Hash files older than this get swept on every call. Keeps the per-portfolio
# cache directory from growing unbounded as filters drift over time.
_HASH_FILE_RETENTION_SECONDS = 7 * 86_400  # 7 days


def _filter_signature(config: dict) -> dict:
    """
    Pull just the screener filter fields out of config and normalize them.

    Used as input to cache_key(). Sorting `sectors` and `industries` makes the
    hash insensitive to list ordering — what matters is the *set* of filters,
    not the order they happen to appear in.
    """
    return {
        "sectors": sorted(config.get("sectors") or []),
        "industries": sorted(config.get("industries") or []),
        "market_cap_min": config.get("market_cap_min"),
        "market_cap_max": config.get("market_cap_max"),
        "region": config.get("region", "us"),
    }


def _screener_cache_path(portfolio_id: str, key: str) -> Path:
    return DATA_DIR / "portfolios" / portfolio_id / f"screener_cache.{key}.json"


def _refinement_cache_path(portfolio_id: str, key: str) -> Path:
    return DATA_DIR / "portfolios" / portfolio_id / f"refinement_cache.{key}.json"


def _sweep_stale_cache_files(portfolio_id: str, prefix: str) -> int:
    """
    Remove `prefix.*.json` files older than _HASH_FILE_RETENTION_SECONDS.

    Each filter change creates a new hash file; without sweeping, the per-portfolio
    cache dir grows unbounded as users iterate on configs. Returns the number of
    files deleted (for logging).
    """
    portfolio_dir = DATA_DIR / "portfolios" / portfolio_id
    if not portfolio_dir.exists():
        return 0
    now = time.time()
    deleted = 0
    for f in portfolio_dir.glob(f"{prefix}.*.json"):
        try:
            if now - f.stat().st_mtime > _HASH_FILE_RETENTION_SECONDS:
                f.unlink(missing_ok=True)
                deleted += 1
        except OSError:
            pass
    return deleted


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
    # Cache key hashes the filter signature: any change to sectors/industries/cap
    # bounds/region produces a different hash → different file → guaranteed miss.
    # This is the fix for the bug where editing config silently served stale
    # results until the 24h TTL expired.
    cache_path = None
    key = ""
    if portfolio_id:
        key = cache_key(_filter_signature(config))
        cache_path = _screener_cache_path(portfolio_id, key)
        if cache_path.exists():
            try:
                with cache_path.open() as f:
                    cached = json.load(f)
                ts = datetime.fromisoformat(cached["timestamp"])
                now = datetime.now(timezone.utc)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_seconds = (now - ts).total_seconds()
                if age_seconds < TTL.UNIVERSE_DAILY:
                    tickers = cached["tickers"]
                    _screener_log.hit(key, age_seconds, count=cached.get("count", len(tickers)))
                    print(
                        f"[screener] Using cached results ({cached['count']} tickers,"
                        f" {age_seconds / 3600:.1f}h old)"
                    )
                    return tickers
                _screener_log.miss(key, reason="ttl_expired", age_s=int(age_seconds))
            except Exception as e:
                _screener_log.miss(key, reason="read_error", error=str(e))
                print(f"[screener] Cache read error, re-running screen: {e}")
        else:
            _screener_log.miss(key, reason="absent")

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
            payload_str = json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "count": len(unique),
                    "tickers": unique,
                    "filter_signature": _filter_signature(config),
                },
                indent=2,
            )
            cache_path.write_text(payload_str)
            _screener_log.write(key, size_bytes=len(payload_str), count=len(unique))
        except Exception as e:
            print(f"[screener] Cache write error: {e}")

        # Sweep stale hash files (>7d) so the dir doesn't grow forever as
        # users iterate on filters. Cheap; runs at most once per scan.
        swept = _sweep_stale_cache_files(portfolio_id, "screener_cache")
        if swept:
            _screener_log.evict(key, reason="retention_sweep", count=swept)

    return unique


# ---------------------------------------------------------------------------
# Claude AI Refinement
# ---------------------------------------------------------------------------

def _get_api_key() -> Optional[str]:
    """Get Anthropic API key from environment.

    Cron scripts and run_dashboard.sh source .env via `set -a; source .env; set +a`
    so the env var is set by the time this runs. Don't manually parse .env here —
    that pattern breaks under any deployment that exports the var differently
    (systemd, Docker, CI, manual export)."""
    return os.environ.get("ANTHROPIC_API_KEY")


def _refinement_key(prompt_text: str, upstream_tickers: list[str]) -> str:
    """
    Hash the refinement prompt + an upstream-result fingerprint.

    Including upstream_tickers means refinement auto-invalidates whenever the
    screener feeding it produces a different ticker set. Editing the prompt
    alone OR widening/narrowing the screener ALONE both bust the cache.
    Without this, prompt edits would silently serve stale Claude output for
    up to 7 days.
    """
    upstream_hash = cache_key(sorted(upstream_tickers))
    return cache_key({"prompt": prompt_text, "upstream": upstream_hash})


def _load_refinement_cache(
    portfolio_id: str,
    key: str,
    max_age_days: int = 7,
) -> Optional[list]:
    """Load refinement cache if it exists and is within max_age_days."""
    cache_path = _refinement_cache_path(portfolio_id, key)
    if not cache_path.exists():
        _refinement_log.miss(key, reason="absent")
        return None
    try:
        with cache_path.open() as f:
            cached = json.load(f)
        ts = datetime.fromisoformat(cached["timestamp"])
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_seconds = (now - ts).total_seconds()
        if age_seconds < max_age_days * 86_400:
            _refinement_log.hit(key, age_seconds, count=cached.get("count", 0))
            print(f"[refinement] Using cached results ({cached['count']} tickers, {age_seconds / 86_400:.1f}d old)")
            return cached["tickers"]
        _refinement_log.miss(key, reason="ttl_expired", age_s=int(age_seconds))
    except Exception as e:
        _refinement_log.miss(key, reason="read_error", error=str(e))
        print(f"[refinement] Cache read error: {e}")
    return None


def _save_refinement_cache(tickers: list, portfolio_id: str, key: str) -> None:
    """Save refinement results to cache."""
    cache_path = _refinement_cache_path(portfolio_id, key)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "count": len(tickers),
                "tickers": tickers,
            },
            indent=2,
        )
        cache_path.write_text(payload)
        _refinement_log.write(key, size_bytes=len(payload), count=len(tickers))
    except Exception as e:
        print(f"[refinement] Cache write error: {e}")

    # Same sweep as screener — keep dir bounded.
    swept = _sweep_stale_cache_files(portfolio_id, "refinement_cache")
    if swept:
        _refinement_log.evict(key, reason="retention_sweep", count=swept)


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

    # Check cache. Key combines prompt + upstream ticker set so that any change
    # to either invalidates the cache automatically. No more "edit refinement
    # prompt, get last week's filtered result for 7 days."
    refinement_key = ""
    if portfolio_id:
        refinement_key = _refinement_key(prompt_text, tickers)
        cached = _load_refinement_cache(portfolio_id, refinement_key)
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
            model=CLAUDE_MODEL,
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

        if portfolio_id and refinement_key:
            _save_refinement_cache(filtered, portfolio_id, refinement_key)

        return filtered

    except Exception as e:
        print(f"[refinement] Warning: Claude refinement failed ({e}) — returning original tickers")
        return tickers
