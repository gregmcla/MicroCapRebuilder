#!/usr/bin/env python3
"""
Data Provider Module for Mommy Bot.

Provides a unified interface for fetching stock data from multiple sources:
- yfinance (default, free, no API key)
- Alpha Vantage (reliable, free tier with 25 calls/day)
- Finnhub (optional, for news/sentiment)

Usage:
    from data_provider import get_price, get_historical, DataProvider

    # Use default provider (auto-selects best available)
    price = get_price("AAPL")

    # Use specific provider
    provider = DataProvider(source="alpha_vantage", api_key="YOUR_KEY")
    data = provider.get_historical("AAPL", days=30)

Configuration in config.json:
    "data_provider": {
        "primary": "yfinance",
        "fallback": "alpha_vantage",
        "alpha_vantage_api_key": "YOUR_KEY",
        "cache_minutes": 15,
        "retry_count": 3
    }
"""

import json
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass
from functools import lru_cache
import hashlib

import pandas as pd

# Load environment variables from .env file (for API keys)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # dotenv not installed, will use os.environ directly

# ─── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"
CACHE_DIR = DATA_DIR / ".cache"


@dataclass
class StockQuote:
    """Represents a stock quote."""
    ticker: str
    price: float
    change: float
    change_pct: float
    volume: int
    timestamp: datetime
    source: str


@dataclass
class HistoricalData:
    """Represents historical price data."""
    ticker: str
    df: pd.DataFrame  # DataFrame with date, open, high, low, close, volume
    source: str


def load_config():
    """Load configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def get_api_key(provider: str) -> Optional[str]:
    """Get API key for a provider from environment or config.

    Priority: Environment variables (secure) > config.json (less secure)
    """
    # Environment variable mapping
    env_var_map = {
        "alpha_vantage": "ALPHA_VANTAGE_API_KEY",
        "finnhub": "FINNHUB_API_KEY",
        "polygon": "POLYGON_API_KEY",
    }

    # Check environment variables FIRST (more secure)
    env_var = env_var_map.get(provider)
    if env_var:
        key = os.environ.get(env_var)
        if key:
            return key

    # Fallback to config (less secure, but convenient for testing)
    config = load_config()
    provider_config = config.get("data_provider", {})
    key = provider_config.get(f"{provider}_api_key")
    if key:
        return key

    return None


class CacheManager:
    """Simple file-based cache for API responses."""

    def __init__(self, cache_minutes: int = 15):
        self.cache_dir = CACHE_DIR
        self.cache_minutes = cache_minutes
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key."""
        hash_key = hashlib.md5(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{hash_key}.json"

    def get(self, key: str) -> Optional[dict]:
        """Get cached value if still valid."""
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                cached = json.load(f)

            # Check if expired
            cached_time = datetime.fromisoformat(cached["timestamp"])
            if datetime.now() - cached_time > timedelta(minutes=self.cache_minutes):
                cache_path.unlink()  # Delete expired
                return None

            return cached["data"]
        except:
            return None

    def set(self, key: str, data: dict):
        """Cache a value."""
        cache_path = self._get_cache_path(key)

        try:
            with open(cache_path, "w") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "data": data
                }, f)
        except:
            pass  # Cache write failures are not critical

    def clear(self):
        """Clear all cached data."""
        for f in self.cache_dir.glob("*.json"):
            f.unlink()


class YFinanceProvider:
    """Yahoo Finance data provider (via yfinance library)."""

    def __init__(self):
        self.name = "yfinance"

    def get_quote(self, ticker: str) -> Optional[StockQuote]:
        """Get current quote for a ticker."""
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            info = stock.info

            # Get current price
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price is None:
                # Fallback to last close
                hist = stock.history(period="1d")
                if hist.empty:
                    return None
                price = float(hist["Close"].iloc[-1])

            # Get change
            prev_close = info.get("previousClose", price)
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0

            return StockQuote(
                ticker=ticker,
                price=price,
                change=change,
                change_pct=change_pct,
                volume=info.get("volume", 0),
                timestamp=datetime.now(),
                source=self.name
            )
        except Exception as e:
            print(f"  [yfinance] Error fetching {ticker}: {e}")
            return None

    def get_historical(self, ticker: str, days: int = 60) -> Optional[HistoricalData]:
        """Get historical data for a ticker."""
        try:
            import yfinance as yf

            # Add buffer for weekends/holidays
            period_days = int(days * 1.5)
            period = f"{period_days}d"

            stock = yf.Ticker(ticker)
            df = stock.history(period=period, auto_adjust=True)

            if df.empty:
                return None

            # Standardize column names
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]

            # Ensure we have required columns
            required = ["date", "open", "high", "low", "close", "volume"]
            for col in required:
                if col not in df.columns:
                    return None

            # Trim to requested days
            df = df.tail(days)

            return HistoricalData(
                ticker=ticker,
                df=df,
                source=self.name
            )
        except Exception as e:
            print(f"  [yfinance] Error fetching history for {ticker}: {e}")
            return None


class AlphaVantageProvider:
    """Alpha Vantage data provider."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None):
        self.name = "alpha_vantage"
        self.api_key = api_key or get_api_key("alpha_vantage")

        if not self.api_key:
            print("  [alpha_vantage] No API key configured")
            print("  Get a free key at: https://www.alphavantage.co/support/#api-key")

    def _make_request(self, params: dict) -> Optional[dict]:
        """Make API request."""
        if not self.api_key:
            return None

        try:
            import requests

            params["apikey"] = self.api_key
            response = requests.get(self.BASE_URL, params=params, timeout=10)

            if response.status_code != 200:
                print(f"  [alpha_vantage] API error: {response.status_code}")
                return None

            data = response.json()

            # Check for API errors
            if "Error Message" in data:
                print(f"  [alpha_vantage] {data['Error Message']}")
                return None

            if "Note" in data:  # Rate limit message
                print(f"  [alpha_vantage] Rate limited: {data['Note'][:50]}...")
                return None

            return data
        except ImportError:
            print("  [alpha_vantage] requests library not installed")
            return None
        except Exception as e:
            print(f"  [alpha_vantage] Request error: {e}")
            return None

    def get_quote(self, ticker: str) -> Optional[StockQuote]:
        """Get current quote for a ticker."""
        data = self._make_request({
            "function": "GLOBAL_QUOTE",
            "symbol": ticker
        })

        if not data or "Global Quote" not in data:
            return None

        quote = data["Global Quote"]

        try:
            price = float(quote.get("05. price", 0))
            prev_close = float(quote.get("08. previous close", price))
            change = float(quote.get("09. change", 0))
            change_pct = float(quote.get("10. change percent", "0%").rstrip("%"))
            volume = int(quote.get("06. volume", 0))

            return StockQuote(
                ticker=ticker,
                price=price,
                change=change,
                change_pct=change_pct,
                volume=volume,
                timestamp=datetime.now(),
                source=self.name
            )
        except Exception as e:
            print(f"  [alpha_vantage] Parse error for {ticker}: {e}")
            return None

    def get_historical(self, ticker: str, days: int = 60) -> Optional[HistoricalData]:
        """Get historical data for a ticker."""
        # Use daily adjusted for clean data
        data = self._make_request({
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "outputsize": "compact" if days <= 100 else "full"
        })

        if not data or "Time Series (Daily)" not in data:
            return None

        try:
            ts = data["Time Series (Daily)"]

            records = []
            for date_str, values in sorted(ts.items(), reverse=True)[:days]:
                records.append({
                    "date": datetime.strptime(date_str, "%Y-%m-%d"),
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["5. adjusted close"]),  # Use adjusted
                    "volume": int(values["6. volume"])
                })

            df = pd.DataFrame(records)
            df = df.sort_values("date").reset_index(drop=True)

            return HistoricalData(
                ticker=ticker,
                df=df,
                source=self.name
            )
        except Exception as e:
            print(f"  [alpha_vantage] Parse error for {ticker} history: {e}")
            return None


class DataProvider:
    """
    Unified data provider with automatic fallback.

    Tries primary provider first, falls back to secondary on failure.
    Includes caching to minimize API calls.
    """

    def __init__(
        self,
        primary: str = "yfinance",
        fallback: str = "alpha_vantage",
        cache_minutes: int = 15
    ):
        self.cache = CacheManager(cache_minutes)

        # Initialize providers
        self.providers = {}

        if primary == "yfinance" or fallback == "yfinance":
            self.providers["yfinance"] = YFinanceProvider()

        if primary == "alpha_vantage" or fallback == "alpha_vantage":
            self.providers["alpha_vantage"] = AlphaVantageProvider()

        self.primary = primary
        self.fallback = fallback

    def _try_providers(self, method: str, *args, **kwargs):
        """Try primary provider, fall back on failure."""
        # Try primary
        if self.primary in self.providers:
            provider = self.providers[self.primary]
            result = getattr(provider, method)(*args, **kwargs)
            if result is not None:
                return result

        # Try fallback
        if self.fallback in self.providers and self.fallback != self.primary:
            provider = self.providers[self.fallback]
            result = getattr(provider, method)(*args, **kwargs)
            if result is not None:
                return result

        return None

    def get_quote(self, ticker: str, use_cache: bool = True) -> Optional[StockQuote]:
        """Get current quote with caching."""
        cache_key = f"quote:{ticker}"

        # Check cache
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return StockQuote(**cached)

        # Fetch from providers
        quote = self._try_providers("get_quote", ticker)

        # Cache result
        if quote and use_cache:
            self.cache.set(cache_key, {
                "ticker": quote.ticker,
                "price": quote.price,
                "change": quote.change,
                "change_pct": quote.change_pct,
                "volume": quote.volume,
                "timestamp": quote.timestamp.isoformat(),
                "source": quote.source
            })

        return quote

    def get_historical(self, ticker: str, days: int = 60) -> Optional[HistoricalData]:
        """Get historical data (not cached due to DataFrame)."""
        return self._try_providers("get_historical", ticker, days)

    def get_prices(self, tickers: List[str]) -> Dict[str, float]:
        """Get prices for multiple tickers."""
        prices = {}
        for ticker in tickers:
            quote = self.get_quote(ticker)
            if quote:
                prices[ticker] = quote.price
        return prices


# ─── Convenience Functions ───────────────────────────────────────────────────

# Default provider instance
_default_provider = None


def _get_default_provider() -> DataProvider:
    """Get or create default provider."""
    global _default_provider

    if _default_provider is None:
        config = load_config()
        provider_config = config.get("data_provider", {})

        _default_provider = DataProvider(
            primary=provider_config.get("primary", "yfinance"),
            fallback=provider_config.get("fallback", "alpha_vantage"),
            cache_minutes=provider_config.get("cache_minutes", 15)
        )

    return _default_provider


def get_price(ticker: str) -> Optional[float]:
    """Get current price for a ticker."""
    quote = _get_default_provider().get_quote(ticker)
    return quote.price if quote else None


def get_prices(tickers: List[str]) -> Dict[str, float]:
    """Get prices for multiple tickers."""
    return _get_default_provider().get_prices(tickers)


def get_historical(ticker: str, days: int = 60) -> Optional[pd.DataFrame]:
    """Get historical data DataFrame."""
    data = _get_default_provider().get_historical(ticker, days)
    return data.df if data else None


def clear_cache():
    """Clear the data cache."""
    _get_default_provider().cache.clear()


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    """Test data providers."""
    import argparse

    parser = argparse.ArgumentParser(description="Test data providers")
    parser.add_argument("ticker", nargs="?", default="AAPL", help="Ticker to test")
    parser.add_argument("--provider", choices=["yfinance", "alpha_vantage"], help="Specific provider")
    parser.add_argument("--history", type=int, default=0, help="Fetch N days of history")
    parser.add_argument("--clear-cache", action="store_true", help="Clear cache")

    args = parser.parse_args()

    if args.clear_cache:
        clear_cache()
        print("✅ Cache cleared")
        return

    print(f"\n─── Testing Data Provider: {args.ticker} ───\n")

    if args.provider:
        if args.provider == "yfinance":
            provider = YFinanceProvider()
        else:
            provider = AlphaVantageProvider()

        print(f"Using: {provider.name}")

        quote = provider.get_quote(args.ticker)
        if quote:
            print(f"Price: ${quote.price:.2f}")
            print(f"Change: {quote.change:+.2f} ({quote.change_pct:+.2f}%)")
            print(f"Volume: {quote.volume:,}")
        else:
            print("❌ Failed to get quote")
    else:
        # Use unified provider
        print("Using: Unified provider (yfinance -> alpha_vantage fallback)")

        quote = get_price(args.ticker)
        if quote:
            print(f"Price: ${quote:.2f}")
        else:
            print("❌ Failed to get price")

    if args.history > 0:
        print(f"\nFetching {args.history} days of history...")
        df = get_historical(args.ticker, args.history)
        if df is not None:
            print(df.tail(5).to_string())
        else:
            print("❌ Failed to get history")


if __name__ == "__main__":
    main()
