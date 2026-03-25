#!/usr/bin/env python3
"""
Sector Mapper - Maps tickers to sectors for composition analysis.

Uses static JSON file with yfinance fallback for missing tickers.
"""

import json
from pathlib import Path
from typing import Optional, Dict
import yfinance as yf

DATA_DIR = Path(__file__).parent.parent / "data"
SECTOR_FILE = DATA_DIR / "sector_mapping.json"


def load_sector_mapping() -> Dict[str, str]:
    """Load sector mapping from JSON file."""
    if SECTOR_FILE.exists():
        with open(SECTOR_FILE) as f:
            return json.load(f)
    return {}


def save_sector_mapping(mapping: Dict[str, str]) -> None:
    """Save sector mapping to JSON file."""
    with open(SECTOR_FILE, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)


def get_sector(ticker: str, mapping: Optional[Dict[str, str]] = None) -> str:
    """
    Get sector for ticker.

    Args:
        ticker: Stock ticker
        mapping: Optional pre-loaded mapping (for performance)

    Returns:
        Sector name or "Unknown" if not found
    """
    if mapping is None:
        mapping = load_sector_mapping()

    # Check static mapping first
    if ticker in mapping:
        return mapping[ticker]

    # Fallback to yfinance
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "Unknown")

        # Cache for next time
        mapping[ticker] = sector
        save_sector_mapping(mapping)

        return sector
    except Exception as e:
        print(f"Warning: sector lookup failed for ticker: {e}")
        return "Unknown"


def update_sector_mapping(tickers: list) -> Dict[str, str]:
    """
    Update sector mapping for list of tickers.

    Fetches missing sectors from yfinance and updates JSON file.

    Args:
        tickers: List of ticker symbols

    Returns:
        Updated mapping dict
    """
    mapping = load_sector_mapping()

    for ticker in tickers:
        if ticker not in mapping:
            sector = get_sector(ticker, mapping)
            print(f"  {ticker}: {sector}")

    return mapping
