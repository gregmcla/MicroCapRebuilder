"""
Integration tests for run_unified_analysis().

Test 1 is the harness smoke test — must pass before any other test
is meaningful. Tests 2-5 cover the three analysis branches plus
analyze-side regressions (no candidates, stop-loss triggered).
"""
import pandas as pd

from fixtures.mock_responses import (
    ai_allocator_buy_basket,
    ai_review_approve_all,
)


def _bars(closes: list[float], start: str = "2026-01-01") -> pd.DataFrame:
    """Helper: build OHLCV DataFrame from a list of closes."""
    n = len(closes)
    dates = pd.date_range(start=start, periods=n, freq="B")
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


def _wl_entry(ticker: str, score: float, sector: str = "Technology") -> dict:
    """Helper: build a watchlist.jsonl entry."""
    return {
        "ticker": ticker,
        "added_date": "2026-05-01",
        "source": "SCORE_ALL",
        "discovery_score": score,
        "score_delta": 0.0,
        "sector": sector,
        "market_cap_m": 5_000.0,
        "avg_volume": 1_000_000,
        "last_checked": "2026-05-06",
        "status": "ACTIVE",
        "notes": "",
        "social_heat": "",
        "social_rank": None,
        "social_bullish_pct": None,
    }


def test_analyze_ai_driven_path(
    seed_portfolio,
    mock_anthropic,
    mock_yfinance,
    mock_public_com,
    mock_news_off,
):
    """
    Smoke test: AI-driven analysis returns a result with ai_mode='claude'
    and the BUY actions Claude proposed.

    Setup:
      - Empty positions, empty watchlist (no scoring needed)
      - Mock Anthropic returns a 2-ticker BUY basket
      - All external services neutralized

    This test proves the harness works end-to-end. Once green, the rest
    of the suite (tests 2-17) can be built on top with confidence.
    """
    # Mock yfinance regardless — needed for benchmark/regime fetch in
    # load_portfolio_state. Empty positions means no per-ticker fetch.
    mock_yfinance.prices = {}

    # Mock Public.com — empty since no positions
    mock_public_com.prices = {}

    # Queue Claude's response for the AI allocator call.
    mock_anthropic.next_response = ai_allocator_buy_basket(
        ["AAPL", "MSFT"],
        shares_each=10,
        price_each=100.0,
    )

    sp = seed_portfolio(
        starting_capital=100_000.0,
        config_overrides={
            "ai_driven": True,
            "full_watchlist_prompt": False,
            # Disable enhanced layers so AI-driven branch is unambiguous
            "enhanced_trading": {"enable_layers": False},
        },
        positions=[],
        transactions=[],
        watchlist=[],
    )

    # Import here so the fixture-injected sys.path is in effect
    from unified_analysis import run_unified_analysis

    result = run_unified_analysis(dry_run=True, portfolio_id=sp.portfolio_id)

    # ── Assertions on the result dict ─────────────────────────────────
    assert isinstance(result, dict), "result should be a dict"
    assert result.get("ai_mode") == "claude", (
        f"AI-driven path should set ai_mode='claude', got {result.get('ai_mode')!r}"
    )

    # The mock client should have been called at least once (allocator call)
    assert len(mock_anthropic.calls) >= 1, (
        "AI-driven path should have invoked the Anthropic client at least once"
    )

    # Reviewed actions should contain the 2 BUYs Claude proposed
    reviewed = result.get("reviewed_actions") or result.get("approved") or []
    buy_tickers = []
    for a in reviewed:
        ticker = getattr(a, "ticker", None) or (a.get("ticker") if isinstance(a, dict) else None)
        if ticker is None:
            original = getattr(a, "original", None)
            ticker = getattr(original, "ticker", None) if original is not None else None
        action_type = (
            getattr(a, "action_type", None)
            or (a.get("action_type") if isinstance(a, dict) else None)
            or getattr(getattr(a, "original", None), "action_type", None)
        )
        if action_type == "BUY" and ticker:
            buy_tickers.append(ticker)
    assert set(buy_tickers) >= {"AAPL", "MSFT"}, (
        f"Expected AAPL and MSFT BUYs from Claude, got {buy_tickers}"
    )


# ── Test 2: Enhanced Layers path ─────────────────────────────────────────────
def test_analyze_enhanced_layers_path(
    seed_portfolio,
    mock_anthropic,
    mock_yfinance,
    mock_public_com,
    mock_bars,
    mock_info_prewarm,
    mock_news_off,
):
    """
    Enhanced Layers (Layer 2/3/4) path: ai_driven=false, enable_layers=true.

    Watchlist has 2 candidates; OpportunityLayer scores and proposes buys;
    AI review approves them. Result must have ai_mode == "mechanical".
    """
    aapl_bars = _bars([100.0 + i * 0.3 for i in range(70)])
    msft_bars = _bars([200.0 + i * 0.5 for i in range(70)])
    for t, df in [("AAPL", aapl_bars), ("MSFT", msft_bars)]:
        mock_bars.bars[t] = df
        mock_bars.bars_by_period[(t, "3mo")] = df
        mock_bars.bars_by_period[(t, "1y")] = df

    mock_info_prewarm.info["AAPL"] = {"sector": "Technology", "marketCap": 3e12}
    mock_info_prewarm.info["MSFT"] = {"sector": "Technology", "marketCap": 3.5e12}

    mock_yfinance.prices = {"AAPL": 120.0, "MSFT": 235.0}
    mock_public_com.prices = {"AAPL": 120.0, "MSFT": 235.0}

    sp = seed_portfolio(
        starting_capital=100_000.0,
        config_overrides={
            "ai_driven": False,
            "enhanced_trading": {"enable_layers": True},
        },
        watchlist=[_wl_entry("AAPL", 70.0), _wl_entry("MSFT", 75.0)],
    )

    # Default: approve any review request. ai_review may or may not be called
    # depending on whether OpportunityLayer produces proposals from this seed.
    mock_anthropic.next_response = ai_review_approve_all([])

    from unified_analysis import run_unified_analysis
    result = run_unified_analysis(dry_run=True, portfolio_id=sp.portfolio_id)

    assert isinstance(result, dict)
    assert result.get("ai_mode") == "mechanical", (
        f"Enhanced layers path should set ai_mode='mechanical', got {result.get('ai_mode')!r}"
    )
    # The result shape must be consistent with AI-driven runs (executor uses same keys)
    assert "reviewed_actions" in result
    assert "summary" in result
    assert "regime" in result


# ── Test 3: Fallback path (no ai_driven, no enhanced_layers) ─────────────────
def test_analyze_fallback_path(
    seed_portfolio,
    mock_anthropic,
    mock_yfinance,
    mock_public_com,
    mock_bars,
    mock_news_off,
):
    """
    Fallback path: neither ai_driven nor enable_layers set. Basic scoring runs.
    Asserts result shape + ai_mode == "mechanical".
    """
    aapl_bars = _bars([100.0 + i * 0.3 for i in range(70)])
    mock_bars.bars["AAPL"] = aapl_bars
    mock_bars.bars_by_period[("AAPL", "3mo")] = aapl_bars
    mock_bars.bars_by_period[("AAPL", "1y")] = aapl_bars

    mock_yfinance.prices = {"AAPL": 120.0}
    mock_public_com.prices = {"AAPL": 120.0}

    sp = seed_portfolio(
        starting_capital=50_000.0,
        config_overrides={
            "ai_driven": False,
            "enhanced_trading": {"enable_layers": False},
        },
        watchlist=[_wl_entry("AAPL", 60.0)],
    )

    mock_anthropic.next_response = ai_review_approve_all([])

    from unified_analysis import run_unified_analysis
    result = run_unified_analysis(dry_run=True, portfolio_id=sp.portfolio_id)

    assert isinstance(result, dict)
    assert result.get("ai_mode") == "mechanical", (
        f"Fallback path should set ai_mode='mechanical', got {result.get('ai_mode')!r}"
    )
    assert "reviewed_actions" in result


# ── Test 4: Empty watchlist (no candidates) ──────────────────────────────────
def test_analyze_no_candidates(
    seed_portfolio,
    mock_anthropic,
    mock_yfinance,
    mock_public_com,
    mock_news_off,
):
    """
    Empty watchlist + empty positions. Pipeline must not crash and must return
    a valid result dict with no proposed buys.
    """
    mock_yfinance.prices = {}
    mock_public_com.prices = {}
    mock_anthropic.next_response = ai_review_approve_all([])

    sp = seed_portfolio(
        starting_capital=50_000.0,
        config_overrides={
            "ai_driven": False,
            "enhanced_trading": {"enable_layers": False},
        },
        watchlist=[],
    )

    from unified_analysis import run_unified_analysis
    result = run_unified_analysis(dry_run=True, portfolio_id=sp.portfolio_id)

    assert isinstance(result, dict)
    reviewed = result.get("reviewed_actions") or []
    buys = [
        a for a in reviewed
        if (
            getattr(getattr(a, "original", None), "action_type", None) == "BUY"
            or (isinstance(a, dict) and a.get("action_type") == "BUY")
        )
    ]
    assert len(buys) == 0, f"Empty watchlist should yield zero BUYs, got {len(buys)}"


# ── Test 5: Stop-loss triggered on held position ─────────────────────────────
def test_analyze_stop_loss_triggered(
    seed_portfolio,
    mock_anthropic,
    mock_yfinance,
    mock_public_com,
    mock_bars,
    mock_news_off,
):
    """
    Position with current_price below stop_loss must produce a SELL proposed
    action with reason indicating stop-loss (Layer 1 risk management).
    """
    # Held position: AAPL @ avg cost $150, stop $140. Mock current price $130.
    aapl_bars = _bars([150.0 + i * 0.1 for i in range(40)] + [130.0] * 30)
    mock_bars.bars["AAPL"] = aapl_bars
    mock_bars.bars_by_period[("AAPL", "3mo")] = aapl_bars
    mock_bars.bars_by_period[("AAPL", "1y")] = aapl_bars

    mock_yfinance.prices = {"AAPL": 130.0}
    mock_public_com.prices = {"AAPL": 130.0}

    sp = seed_portfolio(
        starting_capital=200_000.0,
        config_overrides={
            "ai_driven": False,
            "enhanced_trading": {"enable_layers": False},
        },
        positions=[
            {
                "ticker": "AAPL",
                "shares": 100,
                "avg_cost_basis": 150.0,
                "current_price": 130.0,
                "market_value": 13_000.0,
                "unrealized_pnl": -2_000.0,
                "unrealized_pnl_pct": -13.3,
                "stop_loss": 140.0,
                "take_profit": 180.0,
                "entry_date": "2026-04-01",
                "day_change": 0.0,
                "day_change_pct": 0.0,
                "price_high": 150.0,
            }
        ],
        transactions=[
            {
                "transaction_id": "seed-aapl-buy",
                "date": "2026-04-01T09:30:00",
                "ticker": "AAPL",
                "action": "BUY",
                "shares": 100,
                "price": 150.0,
                "total_value": 15_000.0,
                "stop_loss": 140.0,
                "take_profit": 180.0,
                "reason": "MIGRATION",
                "regime_at_entry": "BULL",
                "composite_score": 70.0,
                "factor_scores": "{}",
                "signal_rank": 1,
                "trade_rationale": "{}",
            }
        ],
        watchlist=[],
    )

    mock_anthropic.next_response = ai_review_approve_all([])

    from unified_analysis import run_unified_analysis
    result = run_unified_analysis(dry_run=True, portfolio_id=sp.portfolio_id)

    assert isinstance(result, dict)
    reviewed = result.get("reviewed_actions") or []

    sells = []
    for a in reviewed:
        original = getattr(a, "original", a if isinstance(a, dict) else None)
        if original is None:
            continue
        action_type = (
            getattr(original, "action_type", None)
            or (original.get("action_type") if isinstance(original, dict) else None)
        )
        ticker = (
            getattr(original, "ticker", None)
            or (original.get("ticker") if isinstance(original, dict) else None)
        )
        reason = (
            getattr(original, "reason", None)
            or (original.get("reason") if isinstance(original, dict) else None)
        )
        if action_type == "SELL":
            sells.append({"ticker": ticker, "reason": reason})

    assert any(s["ticker"] == "AAPL" for s in sells), (
        f"Expected a SELL proposal for AAPL when current<stop, got {sells}"
    )


# ── Test 6: AI allocator BUYs are capped to max_positions ────────────────────
def test_ai_allocator_caps_buys_to_max_positions(
    seed_portfolio,
    mock_anthropic,
    mock_yfinance,
    mock_public_com,
    mock_news_off,
):
    """
    Regression for the live bug Greg hit 2026-05-06: cluster-ignition with
    max_positions=8 received 10 BUYs from Claude through analyze + execute,
    opening 10 positions over the configured cap.

    With the fix in place: Claude proposes 10 BUYs, _validate_allocation drops
    the marginal extras so only `max_positions - held` BUYs reach reviewed.
    """
    mock_yfinance.prices = {}
    mock_public_com.prices = {}

    sp = seed_portfolio(
        starting_capital=1_000_000.0,
        config_overrides={
            "ai_driven": True,
            "full_watchlist_prompt": False,
            "max_positions": 4,
            "enforce_max_positions": True,
            "enhanced_trading": {"enable_layers": False},
        },
        positions=[],
        transactions=[],
        watchlist=[],
    )

    mock_anthropic.next_response = ai_allocator_buy_basket(
        ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ"],
        shares_each=10,
        price_each=50.0,
    )

    from unified_analysis import run_unified_analysis
    result = run_unified_analysis(dry_run=True, portfolio_id=sp.portfolio_id)

    assert result.get("ai_mode") == "claude"
    reviewed = result.get("reviewed_actions") or []
    buys = [
        a for a in reviewed
        if (
            getattr(getattr(a, "original", None), "action_type", None) == "BUY"
            or (isinstance(a, dict) and a.get("original", {}).get("action_type") == "BUY")
        )
    ]
    assert len(buys) == 4, (
        f"max_positions=4 + enforce_max_positions=true should cap BUYs to 4; got {len(buys)}"
    )


def test_ai_allocator_no_cap_when_flag_absent(
    seed_portfolio,
    mock_anthropic,
    mock_yfinance,
    mock_public_com,
    mock_news_off,
):
    """
    Backward-compatibility guard: portfolios without `enforce_max_positions`
    flag in their config (i.e. all portfolios that existed before 2026-05-06)
    must keep their old behavior — Claude's BUY count is NOT truncated.

    This codifies that the cap is opt-in. If someone refactors the validator
    and accidentally makes the cap default-on, this test fails and the
    existing 35 portfolios are protected.
    """
    mock_yfinance.prices = {}
    mock_public_com.prices = {}

    sp = seed_portfolio(
        starting_capital=1_000_000.0,
        config_overrides={
            "ai_driven": True,
            "full_watchlist_prompt": False,
            "max_positions": 4,
            # NOTE: no `enforce_max_positions` key → opt-out (old behavior)
            "enhanced_trading": {"enable_layers": False},
        },
        positions=[], transactions=[], watchlist=[],
    )

    mock_anthropic.next_response = ai_allocator_buy_basket(
        ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ"],
        shares_each=10, price_each=50.0,
    )

    from unified_analysis import run_unified_analysis
    result = run_unified_analysis(dry_run=True, portfolio_id=sp.portfolio_id)

    reviewed = result.get("reviewed_actions") or []
    buys = [
        a for a in reviewed
        if (
            getattr(getattr(a, "original", None), "action_type", None) == "BUY"
            or (isinstance(a, dict) and a.get("original", {}).get("action_type") == "BUY")
        )
    ]
    assert len(buys) == 10, (
        f"Without enforce_max_positions=true, the cap must NOT apply; "
        f"existing portfolios should see all 10 BUYs as before. Got {len(buys)}."
    )
