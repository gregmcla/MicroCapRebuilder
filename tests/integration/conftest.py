"""
pytest fixtures for the analyze→execute integration suite.

Strategy:
- Real fixture portfolio under data/portfolios/_test_pipeline_<hex>/ (auto-cleanup).
- All external services mocked at their import boundaries:
  * Anthropic client via ai_review.get_ai_client (used by ai_review + ai_allocator)
  * yfinance batch fetcher via portfolio_state.fetch_prices_batch
  * Public.com via public_quotes.fetch_live_quotes
  * Social sentiment via DISABLE_SOCIAL=true env var
  * News fetch via macro_context._fetch_ticker_news → []
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts/ + tests/integration are on the import path
REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(INTEGRATION_DIR))

from fixtures.seed_portfolio import (  # noqa: E402
    SeededPortfolio,
    cleanup_orphans,
    seed_portfolio as _seed_portfolio,
)


@pytest.fixture(scope="session", autouse=True)
def _clean_orphan_test_portfolios():
    """Sweep any leftover _test_pipeline_* dirs from prior crashed runs."""
    cleanup_orphans()
    yield
    cleanup_orphans()


@pytest.fixture
def seed_portfolio(request):
    """
    Factory fixture: tests call seed_portfolio(positions=[...], watchlist=[...], ...)
    and receive a SeededPortfolio object. Cleanup runs automatically on test exit.
    """
    created: list[SeededPortfolio] = []

    def _factory(**kwargs) -> SeededPortfolio:
        sp = _seed_portfolio(**kwargs)
        created.append(sp)
        return sp

    yield _factory

    for sp in created:
        sp.cleanup()


# ─── External service mocks ───────────────────────────────────────────────────


class MockAnthropicClient:
    """
    Stand-in for an anthropic.Anthropic client.

    Tests assign `.next_response` (a single MagicMock or a list to round-robin)
    or `.side_effect` (a callable raised/returned on each call) before exercising
    the pipeline. messages.create() consumes from these.
    """

    def __init__(self):
        self.next_response = None
        self.side_effect = None
        self.calls: list[dict] = []
        self.messages = MagicMock()
        self.messages.create = self._create

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.side_effect is not None:
            return self.side_effect(**kwargs)
        if isinstance(self.next_response, list):
            if not self.next_response:
                raise AssertionError("MockAnthropicClient ran out of canned responses")
            return self.next_response.pop(0)
        if self.next_response is None:
            raise AssertionError(
                "MockAnthropicClient.messages.create called but no response queued"
            )
        return self.next_response


@pytest.fixture
def mock_anthropic():
    """Patch get_ai_client across ai_review + ai_allocator. Returns the mock client."""
    client = MockAnthropicClient()

    # Both modules import get_ai_client from ai_review; patching at the source
    # plus at the consumer reference covers both `from x import get_ai_client`
    # and `import x; x.get_ai_client()` patterns.
    patches = [
        patch("ai_review.get_ai_client", return_value=client),
        patch("ai_allocator.get_ai_client", return_value=client),
    ]
    for p in patches:
        p.start()
    yield client
    for p in patches:
        p.stop()


@pytest.fixture
def mock_yfinance():
    """
    Replace portfolio_state.fetch_prices_batch with a controllable mock.

    Tests assign `.prices` (dict[ticker, price]) and optionally `.prev_closes`.
    Returns the canonical 3-tuple shape: (prices, failures, prev_closes).
    """
    holder = MagicMock()
    holder.prices = {}
    holder.prev_closes = {}
    holder.failures = []

    def _fetch(tickers):
        prices = {t: holder.prices.get(t, 50.0) for t in tickers}
        prev = {t: holder.prev_closes.get(t, holder.prices.get(t, 50.0)) for t in tickers}
        return prices, list(holder.failures), prev

    # Patch every consumer reference. `from portfolio_state import fetch_prices_batch`
    # rebinds the name at import time, so patching only the source module misses
    # callers like unified_analysis.execute_approved_actions.
    targets = [
        "portfolio_state.fetch_prices_batch",
        "unified_analysis.fetch_prices_batch",
    ]
    patches = []
    for tgt in targets:
        try:
            p = patch(tgt, side_effect=_fetch)
            p.start()
            patches.append(p)
        except (AttributeError, ModuleNotFoundError):
            pass
    yield holder
    for p in patches:
        p.stop()


@pytest.fixture
def mock_public_com():
    """
    Replace public_quotes.fetch_live_quotes with a controllable mock.

    Tests assign `.prices` (dict[ticker, price]). When a ticker is missing,
    falls back to None to simulate an outage on that name.
    """
    holder = MagicMock()
    holder.prices = {}

    def _fetch(tickers):
        # public_quotes.fetch_live_quotes returns (prices_dict, failures_list)
        prices = {t: holder.prices[t] for t in tickers if t in holder.prices}
        failures = [t for t in tickers if t not in holder.prices]
        return prices, failures

    # Patch at the consumer references inside unified_analysis as well, since
    # `from public_quotes import fetch_live_quotes` rebinds the name.
    p1 = patch("public_quotes.fetch_live_quotes", side_effect=_fetch)
    p2 = patch("unified_analysis.fetch_live_quotes", side_effect=_fetch, create=True)
    p1.start()
    try:
        p2.start()
    except (AttributeError, ModuleNotFoundError):
        p2 = None
    yield holder
    p1.stop()
    if p2 is not None:
        p2.stop()


@pytest.fixture(autouse=True)
def mock_social_off(monkeypatch):
    """Disable social sentiment for every integration test (no Stocktwits/ApeWisdom calls)."""
    monkeypatch.setenv("DISABLE_SOCIAL", "true")


@pytest.fixture
def mock_news_off(monkeypatch):
    """Stub macro_context news fetch to empty list (non-fatal failure simulation)."""
    try:
        import macro_context

        monkeypatch.setattr(macro_context, "_fetch_ticker_news", lambda *a, **k: [])
    except (ImportError, AttributeError):
        pass


@pytest.fixture
def mock_bars(monkeypatch):
    """
    Patch yf_session.cached_download (+ consumer references) to return seeded bars.

    Tests assign holder.bars[ticker] = pd.DataFrame(...) with at least 'Close', 'High',
    'Low', 'Open', 'Volume' columns. Returns the holder. Period argument is ignored
    by default — tests that need period-specific bars can set holder.bars_by_period.
    """
    import pandas as pd

    holder = MagicMock()
    holder.bars = {}
    holder.bars_by_period = {}  # {(ticker, period): df}
    holder.calls: list[tuple] = []

    def _fetch(tickers, period: str = "1y", **kwargs):
        ticker = tickers if isinstance(tickers, str) else tickers[0]
        holder.calls.append((ticker, period))
        df = holder.bars_by_period.get((ticker, period))
        if df is None:
            df = holder.bars.get(ticker)
        return df.copy() if df is not None else pd.DataFrame()

    targets = [
        "yf_session.cached_download",
        "stock_scorer.cached_download",
        "stock_discovery.cached_download",
    ]
    patches = []
    for tgt in targets:
        try:
            p = patch(tgt, side_effect=_fetch)
            p.start()
            patches.append(p)
        except (AttributeError, ModuleNotFoundError):
            pass
    yield holder
    for p in patches:
        p.stop()


@pytest.fixture
def mock_info_prewarm(monkeypatch):
    """
    Patch stock_discovery.prewarm_info_for_tickers to return seeded .info dicts.

    Tests assign holder.info[ticker] = {"sector": ..., "marketCap": ..., ...}.
    """
    holder = MagicMock()
    holder.info = {}

    def _prewarm(tickers, *args, **kwargs):
        return {t: holder.info.get(t, {}) for t in tickers}

    # Patch at all consumer reference points
    targets = [
        "stock_discovery.prewarm_info_for_tickers",
        "unified_analysis.prewarm_info_for_tickers",
    ]
    patches = []
    for tgt in targets:
        try:
            p = patch(tgt, side_effect=_prewarm)
            p.start()
            patches.append(p)
        except (AttributeError, ModuleNotFoundError):
            pass
    yield holder
    for p in patches:
        p.stop()


def make_bars_df(closes: list[float], start_date: str = "2026-01-01") -> "pd.DataFrame":
    """
    Helper: build a DataFrame of OHLCV bars from a list of closing prices.

    Used by tests to seed mock_bars. Open/High/Low/Volume are derived deterministically
    from Close so the scorer's calculations don't div-by-zero.
    """
    import pandas as pd

    n = len(closes)
    dates = pd.date_range(start=start_date, periods=n, freq="B")
    return pd.DataFrame(
        {
            "Open": [c * 0.99 for c in closes],
            "High": [c * 1.02 for c in closes],
            "Low": [c * 0.97 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * n,
        },
        index=dates,
    )


@pytest.fixture(autouse=True)
def _no_real_anthropic_key(monkeypatch):
    """
    Guard against accidental real API calls if a test forgets to use mock_anthropic.
    Forces ANTHROPIC_API_KEY="" so get_ai_client() returns None and the code path
    falls through to mechanical handling rather than hitting the real API.
    Tests that need an AI client must use the mock_anthropic fixture, which patches
    get_ai_client directly and bypasses this.
    """
    if not os.environ.get("INTEGRATION_TEST_ALLOW_REAL_API"):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")


@pytest.fixture(autouse=True)
def _bypass_validate_portfolio_id_for_test_portfolios():
    """
    Allow tests that hit the FastAPI app via TestClient to use the
    `_test_pipeline_<hex>` portfolios created by seed_portfolio — those
    aren't in the global registry, so validate_portfolio_id would 404.

    For test-prefixed IDs, return the id unchanged. For everything else,
    fall through to the real registry check.
    """
    from api.main import app
    from api import deps as api_deps

    real = api_deps.validate_portfolio_id

    def _bypass(portfolio_id: str = "") -> str:
        if portfolio_id.startswith("_test_pipeline_"):
            return portfolio_id
        return real(portfolio_id)

    app.dependency_overrides[api_deps.validate_portfolio_id] = _bypass
    try:
        yield
    finally:
        app.dependency_overrides.pop(api_deps.validate_portfolio_id, None)
