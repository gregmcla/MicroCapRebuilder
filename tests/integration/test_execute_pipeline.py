"""
Integration tests for execute_approved_actions() and the /execute API endpoint.

Tests 6-15 cover the execute side of the pipeline: happy path file writes,
phantom-sell prevention, double-execute race, atomic .last_analysis writes,
cash double-count prevention, stale-price filtering, factor_scores recording,
ai_mode propagation, micro-position floor, insufficient cash handling.

Each test codifies a regression that has hit production. If any go red after
a refactor, look at the most recent change to unified_analysis.py.
"""
import json
import threading
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from fixtures.seed_portfolio import PIPELINE_STATUS_DIR


# ── builders for the analysis_result input shape ─────────────────────────────


def _proposed_buy(
    ticker: str,
    shares: int,
    price: float,
    stop: float,
    target: float,
    factor_scores: dict | None = None,
) -> dict:
    return {
        "original": {
            "action_type": "BUY",
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "stop_loss": stop,
            "take_profit": target,
            "quant_score": 70,
            "factor_scores": factor_scores or {},
            "regime": "BULL",
            "reason": "AI allocation",
        },
        "decision": "APPROVE",
        "confidence": 0.9,
        "ai_reasoning": "test",
    }


def _proposed_sell(ticker: str, shares: int, price: float, reason: str = "SIGNAL") -> dict:
    return {
        "original": {
            "action_type": "SELL",
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "quant_score": 0,
            "factor_scores": {},
            "regime": "BULL",
            "reason": reason,
        },
        "decision": "APPROVE",
        "confidence": 0.9,
        "ai_reasoning": "test",
    }


def _analysis_result(approved: list[dict], ai_mode: str = "claude") -> dict:
    return {"approved": approved, "modified": [], "ai_mode": ai_mode}


# ── Test 6: happy path BUY+SELL writes all expected files ────────────────────


def test_execute_writes_transactions_and_positions(
    seed_portfolio,
    mock_yfinance,
    mock_public_com,
):
    """Happy path: 1 BUY + 1 SELL → transactions.csv has 2 rows, positions.csv updated, pipeline_status.json written."""
    mock_yfinance.prices = {"AAPL": 175.0, "MSFT": 300.0}
    mock_public_com.prices = {"AAPL": 175.0, "MSFT": 300.0}

    sp = seed_portfolio(
        starting_capital=200_000.0,
        config_overrides={"ai_driven": True},
        positions=[
            {
                "ticker": "MSFT", "shares": 50, "avg_cost_basis": 280.0,
                "current_price": 300.0, "market_value": 15_000.0,
                "unrealized_pnl": 1_000.0, "unrealized_pnl_pct": 7.1,
                "stop_loss": 250.0, "take_profit": 350.0,
                "entry_date": "2026-04-01", "day_change": 0.0,
                "day_change_pct": 0.0, "price_high": 305.0,
            }
        ],
        transactions=[{
            "transaction_id": "seed-msft", "date": "2026-04-01T09:30:00",
            "ticker": "MSFT", "action": "BUY", "shares": 50, "price": 280.0,
            "total_value": 14_000.0, "stop_loss": 250.0, "take_profit": 350.0,
            "reason": "MIGRATION", "regime_at_entry": "BULL",
            "composite_score": 70.0, "factor_scores": "{}", "signal_rank": 1,
            "trade_rationale": "{}",
        }],
    )

    analysis = _analysis_result([
        _proposed_buy("AAPL", 100, 175.0, 160.0, 200.0,
                      factor_scores={"price_momentum": 80.0, "value_timing": 65.0}),
        _proposed_sell("MSFT", 50, 300.0, reason="TAKE_PROFIT"),
    ])

    from unified_analysis import execute_approved_actions
    result = execute_approved_actions(analysis, portfolio_id=sp.portfolio_id)

    assert result["executed"] == 2

    txns = pd.read_csv(sp.transactions_path())
    assert len(txns) == 3, f"expected 1 seed + 2 new = 3, got {len(txns)}"
    new_actions = sorted(txns.tail(2)["action"].tolist())
    assert new_actions == ["BUY", "SELL"], f"got {new_actions}"

    positions = pd.read_csv(sp.positions_path())
    assert "AAPL" in positions["ticker"].tolist()
    assert "MSFT" not in positions["ticker"].tolist(), "sold position should be removed"

    assert sp.pipeline_status_path().exists(), "pipeline_status JSON not written"
    status = json.loads(sp.pipeline_status_path().read_text())
    assert status["executed"] == {"buys": 1, "sells": 1}
    assert status["ai_mode"] == "claude"


# ── Test 7: phantom sell (ticker not held) is dropped ────────────────────────


def test_execute_phantom_sell_blocked(seed_portfolio, mock_yfinance, mock_public_com):
    """Claude hallucinated a SELL of an unheld ticker → must be filtered out."""
    mock_yfinance.prices = {"GHOST": 50.0}
    mock_public_com.prices = {"GHOST": 50.0}

    sp = seed_portfolio(starting_capital=100_000.0, positions=[], transactions=[])

    analysis = _analysis_result([_proposed_sell("GHOST", 100, 50.0)])

    from unified_analysis import execute_approved_actions
    result = execute_approved_actions(analysis, portfolio_id=sp.portfolio_id)

    txns = pd.read_csv(sp.transactions_path())
    ghost_txns = txns[txns["ticker"] == "GHOST"]
    assert len(ghost_txns) == 0, "phantom GHOST sell should be blocked"
    assert result["executed"] == 0


# ── Test 10: cash double-count prevention (sell + buy same ticker, same run) ─


def test_execute_cash_double_count_prevented(seed_portfolio, mock_yfinance, mock_public_com):
    """SELL X then BUY X in the same execute run: cash delta = sell_proceeds - buy_cost (net once)."""
    mock_yfinance.prices = {"AAPL": 175.0}
    mock_public_com.prices = {"AAPL": 175.0}

    sp = seed_portfolio(
        starting_capital=100_000.0,
        positions=[{
            "ticker": "AAPL", "shares": 50, "avg_cost_basis": 150.0,
            "current_price": 175.0, "market_value": 8_750.0,
            "unrealized_pnl": 1_250.0, "unrealized_pnl_pct": 16.7,
            "stop_loss": 140.0, "take_profit": 200.0,
            "entry_date": "2026-04-01", "day_change": 0.0,
            "day_change_pct": 0.0, "price_high": 180.0,
        }],
        transactions=[{
            "transaction_id": "seed-aapl-buy", "date": "2026-04-01T09:30:00",
            "ticker": "AAPL", "action": "BUY", "shares": 50, "price": 150.0,
            "total_value": 7_500.0, "stop_loss": 140.0, "take_profit": 200.0,
            "reason": "MIGRATION", "regime_at_entry": "BULL",
            "composite_score": 70.0, "factor_scores": "{}", "signal_rank": 1,
            "trade_rationale": "{}",
        }],
    )

    analysis = _analysis_result([
        _proposed_sell("AAPL", 50, 175.0),
        _proposed_buy("AAPL", 30, 175.0, 160.0, 200.0),
    ])

    from unified_analysis import execute_approved_actions, load_portfolio_state
    execute_approved_actions(analysis, portfolio_id=sp.portfolio_id)

    new_state = load_portfolio_state(fetch_prices=False, portfolio_id=sp.portfolio_id)
    expected_cash = (
        100_000.0
        - 7_500.0
        + 50 * 175.0
        - 30 * 175.0
    )
    assert abs(new_state.cash - expected_cash) < 0.01, (
        f"cash mismatch: got {new_state.cash}, expected {expected_cash}"
    )


# ── Test 11: stale-price BUY rejected when live > 1.30× prev_close ───────────


def test_execute_stale_price_blocked(seed_portfolio, mock_yfinance, mock_public_com):
    """BUY with live_price > 1.30× prev_close is dropped as bad data."""
    mock_yfinance.prices = {"BAD": 150.0}
    mock_yfinance.prev_closes = {"BAD": 100.0}
    mock_public_com.prices = {"BAD": 150.0}

    sp = seed_portfolio(starting_capital=100_000.0, positions=[], transactions=[])

    analysis = _analysis_result([_proposed_buy("BAD", 10, 100.0, 90.0, 120.0)])

    from unified_analysis import execute_approved_actions
    execute_approved_actions(analysis, portfolio_id=sp.portfolio_id)

    txns = pd.read_csv(sp.transactions_path())
    bad_rows = txns[txns["ticker"] == "BAD"]
    assert len(bad_rows) == 0, "stale-price BUY should be filtered"


# ── Test 12: factor_scores recorded as JSON in transaction row ───────────────


def test_execute_factor_scores_recorded(seed_portfolio, mock_yfinance, mock_public_com):
    """BUY transactions must persist the factor_scores dict (not {}) for Factor Learning."""
    mock_yfinance.prices = {"AAPL": 150.0}
    mock_public_com.prices = {"AAPL": 150.0}

    sp = seed_portfolio(starting_capital=50_000.0, positions=[], transactions=[])

    factors = {
        "price_momentum": 85.0, "earnings_growth": 60.0, "quality": 65.0,
        "value_timing": 70.0, "volume": 55.0, "volatility": 40.0,
    }
    analysis = _analysis_result([
        _proposed_buy("AAPL", 50, 150.0, 135.0, 180.0, factor_scores=factors),
    ])

    from unified_analysis import execute_approved_actions
    execute_approved_actions(analysis, portfolio_id=sp.portfolio_id)

    txns = pd.read_csv(sp.transactions_path())
    aapl = txns[txns["ticker"] == "AAPL"].iloc[-1]
    recorded = json.loads(aapl["factor_scores"]) if isinstance(aapl["factor_scores"], str) else aapl["factor_scores"]
    assert recorded, "factor_scores should be non-empty"
    assert recorded.get("price_momentum") == 85.0


# ── Test 13: ai_mode propagates into execution_summary + pipeline_status ─────


def test_execute_ai_mode_field_present(seed_portfolio, mock_yfinance, mock_public_com):
    """Whatever ai_mode the analysis carried must show up in execute's summary."""
    mock_yfinance.prices = {"AAPL": 100.0}
    mock_public_com.prices = {"AAPL": 100.0}

    sp = seed_portfolio(starting_capital=50_000.0, positions=[], transactions=[])

    for tag in ("claude", "mechanical", "mechanical_fallback"):
        analysis = _analysis_result(
            [_proposed_buy("AAPL", 10, 100.0, 90.0, 120.0)],
            ai_mode=tag,
        )
        from unified_analysis import execute_approved_actions
        result = execute_approved_actions(analysis, portfolio_id=sp.portfolio_id)
        assert result["execution_summary"]["ai_mode"] == tag, (
            f"ai_mode round-trip failed for {tag}"
        )


# ── Test 14: micro-position floor drops tiny BUYs ────────────────────────────


def test_execute_micro_position_dropped(seed_portfolio, mock_yfinance, mock_public_com):
    """BUY with total value < max(price*5, $250) should be dropped pre-trade."""
    mock_yfinance.prices = {"TINY": 50.0}
    mock_public_com.prices = {"TINY": 50.0}

    sp = seed_portfolio(starting_capital=100_000.0, positions=[], transactions=[])

    # 4 shares × $50 = $200 — below max($50*5=$250, $250) = $250 floor
    analysis = _analysis_result([_proposed_buy("TINY", 4, 50.0, 45.0, 60.0)])

    from unified_analysis import execute_approved_actions
    execute_approved_actions(analysis, portfolio_id=sp.portfolio_id)

    txns = pd.read_csv(sp.transactions_path())
    tiny_rows = txns[txns["ticker"] == "TINY"]
    assert len(tiny_rows) == 0, "micro-position BUY should be filtered"


# ── Test 15: insufficient cash drops the BUY ─────────────────────────────────


def test_execute_insufficient_cash_dropped(seed_portfolio, mock_yfinance, mock_public_com):
    """
    BUY proposed beyond available cash must never overdraw the account.

    The actual code path either (a) caps shares to max_affordable when shares*price
    exceeds cash but max_affordable >= 1, or (b) drops with reason 'insufficient cash'
    when even 1 share is unaffordable. Either way the invariant is: post-execute
    cash >= 0 AND the recorded BUY was sized to fit. That's what we verify.
    """
    mock_yfinance.prices = {"BIG": 1000.0}
    mock_public_com.prices = {"BIG": 1000.0}

    sp = seed_portfolio(starting_capital=10_000.0, positions=[], transactions=[])

    # 100 shares × $1000 = $100k proposed; only $10k cash → must cap to 10 shares
    analysis = _analysis_result([_proposed_buy("BIG", 100, 1000.0, 900.0, 1200.0)])

    from unified_analysis import execute_approved_actions, load_portfolio_state
    execute_approved_actions(analysis, portfolio_id=sp.portfolio_id)

    state = load_portfolio_state(fetch_prices=False, portfolio_id=sp.portfolio_id)
    assert state.cash >= 0, f"cash overdrawn: {state.cash}"

    txns = pd.read_csv(sp.transactions_path())
    big_rows = txns[txns["ticker"] == "BIG"]
    if len(big_rows) > 0:
        recorded = big_rows.iloc[-1]
        # Cap behavior: shares × price ≤ original cash
        assert recorded["shares"] * recorded["price"] <= 10_000.0 + 0.01, (
            f"BUY sized to ${recorded['shares'] * recorded['price']:.0f} but only $10k cash"
        )


# ── Tests 8 + 9: API-layer concurrency + atomic write (FastAPI TestClient) ───


@pytest.fixture
def api_client(monkeypatch):
    """
    FastAPI TestClient with validate_portfolio_id bypassed for test portfolios.

    Test portfolios are real dirs under data/portfolios/ but not in the registry.
    Patching the validator returns the portfolio_id unchanged when it has the
    test prefix, so endpoints work without polluting the global registry.
    """
    from fastapi.testclient import TestClient
    from api.main import app
    from api import deps as api_deps

    def _bypass(portfolio_id: str = "") -> str:
        if portfolio_id.startswith("_test_pipeline_"):
            return portfolio_id
        return api_deps.validate_portfolio_id(portfolio_id)

    app.dependency_overrides[api_deps.validate_portfolio_id] = _bypass
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(api_deps.validate_portfolio_id, None)


def test_execute_atomic_last_analysis(api_client, seed_portfolio, mock_yfinance, mock_public_com, mock_anthropic):
    """If the .last_analysis.json write fails mid-replace, the prior file must remain intact."""
    from fixtures.mock_responses import ai_allocator_buy_basket
    mock_anthropic.next_response = ai_allocator_buy_basket(["AAPL"], shares_each=10, price_each=100.0)
    mock_yfinance.prices = {"AAPL": 100.0}
    mock_public_com.prices = {"AAPL": 100.0}

    sp = seed_portfolio(
        starting_capital=50_000.0,
        config_overrides={"ai_driven": True, "full_watchlist_prompt": False},
        watchlist=[],
    )

    # First analyze succeeds → seeds a valid .last_analysis.json
    r1 = api_client.post(f"/api/{sp.portfolio_id}/analyze")
    assert r1.status_code == 200, r1.text
    original = sp.last_analysis_path().read_text()
    assert json.loads(original).get("ai_mode") == "claude"

    # Second analyze: force the atomic replace to fail. Original file must remain.
    real_replace = Path.replace

    def _broken_replace(self, target):
        if str(target).endswith(".last_analysis.json"):
            raise OSError("simulated mid-write failure")
        return real_replace(self, target)

    with patch.object(Path, "replace", _broken_replace):
        mock_anthropic.next_response = ai_allocator_buy_basket(["AAPL"], shares_each=999, price_each=999.0)
        r2 = api_client.post(f"/api/{sp.portfolio_id}/analyze")
        assert r2.status_code == 500

    # File still has the original payload (NOT the failed second call's payload)
    after = sp.last_analysis_path().read_text()
    assert after == original, "atomic write didn't roll back — last_analysis.json was corrupted"


def test_execute_double_call_race(api_client, seed_portfolio, mock_yfinance, mock_public_com):
    """Two concurrent /execute calls: one wins (200), one gets 409. No double bookkeeping."""
    mock_yfinance.prices = {"AAPL": 100.0}
    mock_public_com.prices = {"AAPL": 100.0}

    sp = seed_portfolio(
        starting_capital=50_000.0,
        config_overrides={"ai_driven": True},
        positions=[], transactions=[], watchlist=[],
    )

    # Seed a .last_analysis.json by hand (single approved BUY)
    seeded = {
        "approved": [_proposed_buy("AAPL", 10, 100.0, 90.0, 120.0)],
        "modified": [], "ai_mode": "claude",
    }
    sp.last_analysis_path().write_text(json.dumps(seeded))

    statuses: list[int] = []
    lock = threading.Lock()

    def _hit():
        r = api_client.post(f"/api/{sp.portfolio_id}/execute")
        with lock:
            statuses.append(r.status_code)

    t1 = threading.Thread(target=_hit)
    t2 = threading.Thread(target=_hit)
    t1.start(); t2.start()
    t1.join(timeout=15); t2.join(timeout=15)

    assert sorted(statuses) == [200, 409], f"expected one 200 + one 409, got {statuses}"

    # Books only reflect the one successful execution
    txns = pd.read_csv(sp.transactions_path())
    aapl = txns[txns["ticker"] == "AAPL"]
    assert len(aapl) == 1, f"expected one AAPL transaction, got {len(aapl)}"
