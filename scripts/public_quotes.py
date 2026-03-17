"""
Live price fetching via Public.com API.

Replaces yfinance in execute_approved_actions() for real-time bid/ask data.
Falls back gracefully when the API key is not configured or on any error.

Setup:
    Add to .env:
        PUBLIC_API_KEY=your_secret_key_here
        PUBLIC_ACCOUNT_ID=your_account_number_here  (optional — auto-discovered)

Usage:
    from public_quotes import fetch_live_quotes
    prices, failures = fetch_live_quotes(["AAPL", "TSLA", "NVDA"])
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_client = None
_account_id: str | None = None


def _get_client():
    """Lazy-init the Public API client. Returns None if not configured."""
    global _client, _account_id
    if _client is not None:
        return _client

    api_key = os.getenv("PUBLIC_API_KEY")
    if not api_key:
        return None

    try:
        from public_api_sdk import PublicApiClient, ApiKeyAuthConfig
        _client = PublicApiClient(ApiKeyAuthConfig(api_secret_key=api_key))

        # Auto-discover account ID if not set in env
        _account_id = os.getenv("PUBLIC_ACCOUNT_ID")
        if not _account_id:
            resp = _client.get_accounts()
            if resp and resp.accounts:
                _account_id = str(resp.accounts[0].account_id)
                logger.info(f"[public_quotes] Using account {_account_id}")

        return _client
    except Exception as e:
        logger.warning(f"[public_quotes] Failed to init client: {e}")
        _client = None
        return None


def fetch_live_quotes(tickers: list[str]) -> tuple[dict[str, float], list[str]]:
    """
    Fetch real-time last-trade prices for a list of equity tickers.

    Returns:
        (prices dict {ticker: price}, failures list)
        Returns ({}, tickers) if Public API is not configured — caller should fall back.
    """
    if not tickers:
        return {}, []

    client = _get_client()
    if client is None:
        # Not configured — signal caller to fall back to yfinance
        return {}, tickers

    try:
        from public_api_sdk.models.order import OrderInstrument, InstrumentType

        instruments = [
            OrderInstrument(symbol=t, type=InstrumentType.EQUITY) for t in tickers
        ]
        quotes = client.get_quotes(instruments, account_id=_account_id)

        prices: dict[str, float] = {}
        failures: list[str] = []

        for quote in quotes:
            ticker = quote.instrument.symbol if quote.instrument else None
            if not ticker:
                continue

            if quote.outcome and quote.outcome.value == "UNKNOWN":
                failures.append(ticker)
                continue

            # Prefer last trade; fall back to mid-price if last is missing
            price = None
            if quote.last and float(quote.last) > 0:
                price = float(quote.last)
            elif quote.bid and quote.ask:
                bid, ask = float(quote.bid), float(quote.ask)
                if bid > 0 and ask > 0:
                    price = round((bid + ask) / 2, 4)

            if price and price > 0:
                prices[ticker] = price
            else:
                failures.append(ticker)

        # Any ticker not returned at all by the API is a failure
        returned = {q.instrument.symbol for q in quotes if q.instrument}
        for t in tickers:
            if t not in returned and t not in failures:
                failures.append(t)

        if failures:
            logger.debug(f"[public_quotes] No data for: {failures}")

        return prices, failures

    except Exception as e:
        logger.warning(f"[public_quotes] Quote fetch failed: {e}")
        return {}, tickers


def is_configured() -> bool:
    """Returns True if PUBLIC_API_KEY is set and client initialised successfully."""
    return _get_client() is not None
