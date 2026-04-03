#!/usr/bin/env python3
"""Tests for scripts/screener_provider.py"""

import sys
from pathlib import Path

# Ensure the scripts directory is on the path so we can import screener_provider
sys.path.insert(0, str(Path(__file__).parent.parent))

from screener_provider import build_screener_filters, filter_us_listed


# ---------------------------------------------------------------------------
# build_screener_filters
# ---------------------------------------------------------------------------

def test_build_filters_single_sector():
    """Single sector produces a region filter and one sector eq filter."""
    config = {
        "sectors": ["Industrials"],
        "market_cap_min": 500_000_000,
        "market_cap_max": 15_000_000_000,
    }
    filters = build_screener_filters(config)

    # Region default
    assert ["eq", ["region", "us"]] in filters

    # Exactly one sector filter
    sector_filters = [f for f in filters if f[0] == "eq" and f[1][0] == "sector"]
    assert len(sector_filters) == 1
    assert sector_filters[0] == ["eq", ["sector", "Industrials"]]

    # Market cap range filter
    cap_filters = [f for f in filters if f[0] == "btwn"]
    assert len(cap_filters) == 1
    assert cap_filters[0] == ["btwn", ["intradaymarketcap", 500_000_000, 15_000_000_000]]


def test_build_filters_multiple_industries():
    """Multiple industries each get their own eq filter (OR semantics in yfscreen)."""
    config = {
        "industries": ["Engineering & Construction", "Infrastructure Operations"],
    }
    filters = build_screener_filters(config)

    industry_filters = [f for f in filters if f[0] == "eq" and f[1][0] == "industry"]
    assert len(industry_filters) == 2
    industry_values = [f[1][1] for f in industry_filters]
    assert "Engineering & Construction" in industry_values
    assert "Infrastructure Operations" in industry_values


def test_build_filters_no_sector_or_industry():
    """Config with only market cap + region produces no sector/industry filters."""
    config = {
        "market_cap_min": 100_000_000,
        "market_cap_max": 2_000_000_000,
        "region": "us",
    }
    filters = build_screener_filters(config)

    sector_filters = [f for f in filters if f[0] == "eq" and f[1][0] == "sector"]
    industry_filters = [f for f in filters if f[0] == "eq" and f[1][0] == "industry"]
    assert sector_filters == []
    assert industry_filters == []

    # Region still present
    assert ["eq", ["region", "us"]] in filters

    # Market cap filter present
    cap_filters = [f for f in filters if f[0] == "btwn"]
    assert len(cap_filters) == 1


def test_filter_us_listed():
    """
    Removes:
      - Tickers with dots (BLD.TO)
      - 5+ char tickers ending in F or Y (CRWOF, STBBF, SKBSY, AVHNY)
    Keeps normal US tickers (AAPL, ACM, STRL).
    """
    input_tickers = ["AAPL", "CRWOF", "STBBF", "SKBSY", "ACM", "STRL", "AVHNY", "BLD.TO"]
    result = filter_us_listed(input_tickers)
    assert result == ["AAPL", "ACM", "STRL"]


def test_universe_provider_screener_config_recognized():
    """UniverseProvider should recognize screener source in config."""
    config = {
        "universe": {
            "enabled": True,
            "sources": {
                "screener": {
                    "enabled": True,
                    "sectors": ["Industrials"],
                    "market_cap_min": 500000000,
                    "market_cap_max": 15000000000,
                }
            }
        }
    }
    screener_config = config["universe"]["sources"].get("screener", {})
    assert screener_config.get("enabled") is True
    assert "Industrials" in screener_config.get("sectors", [])


# ---------------------------------------------------------------------------
# maybe_refine_with_claude — unit tests (no network calls)
# ---------------------------------------------------------------------------

def test_refinement_skipped_when_disabled():
    """Refinement should return original tickers when disabled."""
    from screener_provider import maybe_refine_with_claude
    tickers = ["AAPL", "MSFT", "GOOG"]
    config = {"enabled": False}
    result = maybe_refine_with_claude(tickers, config, portfolio_id="test")
    assert result == tickers


def test_refinement_skipped_when_too_few_tickers():
    """Refinement should skip if fewer than 50 tickers."""
    from screener_provider import maybe_refine_with_claude
    tickers = ["AAPL"] * 10
    config = {"enabled": True, "prompt": "test prompt"}
    result = maybe_refine_with_claude(tickers, config, portfolio_id="test")
    assert result == tickers


def test_refinement_skipped_when_no_prompt():
    """Refinement should skip if prompt is empty."""
    from screener_provider import maybe_refine_with_claude
    tickers = ["AAPL"] * 100
    config = {"enabled": True, "prompt": ""}
    result = maybe_refine_with_claude(tickers, config, portfolio_id="test")
    assert result == tickers
