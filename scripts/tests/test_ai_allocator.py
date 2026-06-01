#!/usr/bin/env python3
"""
Tests for ai_allocator._parse_json and _validate_allocation.

These are the trust boundary between Claude's output and trade execution.
_parse_json: cleans raw LLM text → dict
_validate_allocation: enforces hard constraints before any trade is committed
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_allocator import _parse_json, _validate_allocation


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _candidates(*tickers_prices):
    """Build a minimal scored_candidates list from (ticker, price) pairs."""
    return [
        {"ticker": t, "current_price": p, "factor_scores": {}, "data_completeness": 6}
        for t, p in tickers_prices
    ]

def _buy(ticker, shares, price, stop=None, take=None, reasoning="AI"):
    """Build a minimal allocation_plan entry."""
    entry = {"ticker": ticker, "shares": shares, "price": price, "reasoning": reasoning}
    if stop is not None:
        entry["stop_loss"] = stop
    if take is not None:
        entry["take_profit"] = take
    return entry

def _sell(ticker, shares, price, reasoning="AI sell"):
    return {"ticker": ticker, "shares": shares, "price": price, "reasoning": reasoning}


# ═══════════════════════════════════════════════════════════════════════════════
# _parse_json
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseJson:

    def test_plain_json_returns_dict(self):
        raw = '{"allocation_plan": [], "sells": [], "portfolio_thesis": "hold"}'
        result = _parse_json(raw)
        assert result["allocation_plan"] == []
        assert result["portfolio_thesis"] == "hold"

    def test_strips_markdown_json_fence(self):
        raw = '```json\n{"allocation_plan": [], "sells": []}\n```'
        result = _parse_json(raw)
        assert "allocation_plan" in result

    def test_strips_plain_code_fence(self):
        raw = '```\n{"allocation_plan": [], "sells": []}\n```'
        result = _parse_json(raw)
        assert "allocation_plan" in result

    def test_extracts_json_from_preamble(self):
        raw = 'Here is my allocation:\n{"allocation_plan": [], "sells": [], "portfolio_thesis": "cautious"}'
        result = _parse_json(raw)
        assert result["portfolio_thesis"] == "cautious"

    def test_fixes_trailing_commas(self):
        """LLMs commonly emit trailing commas — must be auto-fixed."""
        raw = '{"allocation_plan": [{"ticker": "AAPL",}], "sells": [],}'
        result = _parse_json(raw)
        assert result["allocation_plan"][0]["ticker"] == "AAPL"

    def test_raises_on_empty_string(self):
        with pytest.raises((ValueError, Exception)):
            _parse_json("")

    def test_raises_on_no_json_object(self):
        with pytest.raises((ValueError, Exception)):
            _parse_json("Sorry, I cannot provide an allocation at this time.")

    def test_raises_on_corrupt_json(self):
        with pytest.raises((ValueError, Exception)):
            _parse_json('{"allocation_plan": [{"ticker": "AAPL" BROKEN')

    def test_nested_structure_preserved(self):
        raw = '{"allocation_plan": [{"ticker": "MSFT", "shares": 10, "price": 400.0, "stop_loss": 380.0, "take_profit": 440.0, "reasoning": "strong"}], "sells": [], "portfolio_thesis": "tech"}'
        result = _parse_json(raw)
        buy = result["allocation_plan"][0]
        assert buy["ticker"] == "MSFT"
        assert buy["shares"] == 10
        assert buy["stop_loss"] == 380.0

    def test_whitespace_padded_response(self):
        raw = '   \n  {"allocation_plan": [], "sells": []}  \n  '
        result = _parse_json(raw)
        assert result["sells"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_allocation — buys
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateAllocationBuys:

    def test_valid_buy_accepted(self):
        data = {"allocation_plan": [_buy("AAPL", 10, 150.0, stop=138.0, take=180.0)], "sells": []}
        buys, sells = _validate_allocation(data, 10_000, 50_000, _candidates(("AAPL", 150.0)))
        assert len(buys) == 1
        assert buys[0]["ticker"] == "AAPL"
        assert buys[0]["shares"] == 10

    def test_missing_stop_loss_skipped(self):
        data = {"allocation_plan": [_buy("AAPL", 10, 150.0, take=180.0)], "sells": []}
        buys, _ = _validate_allocation(data, 10_000, 50_000, _candidates(("AAPL", 150.0)))
        assert len(buys) == 0

    def test_missing_take_profit_skipped(self):
        data = {"allocation_plan": [_buy("AAPL", 10, 150.0, stop=138.0)], "sells": []}
        buys, _ = _validate_allocation(data, 10_000, 50_000, _candidates(("AAPL", 150.0)))
        assert len(buys) == 0

    def test_stop_at_price_skipped(self):
        """stop_loss == price would trigger immediately — must be rejected."""
        data = {"allocation_plan": [_buy("AAPL", 10, 150.0, stop=150.0, take=180.0)], "sells": []}
        buys, _ = _validate_allocation(data, 10_000, 50_000, _candidates(("AAPL", 150.0)))
        assert len(buys) == 0

    def test_stop_above_price_skipped(self):
        data = {"allocation_plan": [_buy("AAPL", 10, 150.0, stop=155.0, take=180.0)], "sells": []}
        buys, _ = _validate_allocation(data, 10_000, 50_000, _candidates(("AAPL", 150.0)))
        assert len(buys) == 0

    def test_target_at_price_skipped(self):
        data = {"allocation_plan": [_buy("AAPL", 10, 150.0, stop=138.0, take=150.0)], "sells": []}
        buys, _ = _validate_allocation(data, 10_000, 50_000, _candidates(("AAPL", 150.0)))
        assert len(buys) == 0

    def test_target_below_price_skipped(self):
        data = {"allocation_plan": [_buy("AAPL", 10, 150.0, stop=138.0, take=140.0)], "sells": []}
        buys, _ = _validate_allocation(data, 10_000, 50_000, _candidates(("AAPL", 150.0)))
        assert len(buys) == 0

    def test_zero_price_skipped(self):
        data = {"allocation_plan": [_buy("AAPL", 10, 0.0, stop=0.0, take=180.0)], "sells": []}
        buys, _ = _validate_allocation(data, 10_000, 50_000, _candidates(("AAPL", 0.0)))
        assert len(buys) == 0

    def test_zero_shares_skipped(self):
        data = {"allocation_plan": [_buy("AAPL", 0, 150.0, stop=138.0, take=180.0)], "sells": []}
        buys, _ = _validate_allocation(data, 10_000, 50_000, _candidates(("AAPL", 150.0)))
        assert len(buys) == 0

    def test_invalid_shares_string_skipped(self):
        data = {"allocation_plan": [_buy("AAPL", "ten", 150.0, stop=138.0, take=180.0)], "sells": []}
        buys, _ = _validate_allocation(data, 10_000, 50_000, _candidates(("AAPL", 150.0)))
        assert len(buys) == 0

    def test_equity_cap_enforced(self):
        """No position may exceed 25% of total equity."""
        # 1000 shares @ $50 = $50k; total equity $100k → cap at 25% = $25k → 500 shares
        data = {"allocation_plan": [_buy("XYZ", 1000, 50.0, stop=45.0, take=60.0)], "sells": []}
        buys, _ = _validate_allocation(data, 100_000, 100_000, _candidates(("XYZ", 50.0)))
        assert len(buys) == 1
        assert buys[0]["shares"] <= 500  # 25% of $100k / $50 = 500

    def test_cash_constraint_reduces_shares(self):
        """When buy cost exceeds remaining cash, shares are reduced to fit."""
        # Asking for 100 shares @ $100 = $10k, but only $5k cash
        data = {"allocation_plan": [_buy("XYZ", 100, 100.0, stop=90.0, take=120.0)], "sells": []}
        buys, _ = _validate_allocation(data, 5_000, 50_000, _candidates(("XYZ", 100.0)))
        assert len(buys) == 1
        assert buys[0]["shares"] == 50  # $5k / $100 = 50

    def test_second_buy_skipped_when_cash_exhausted(self):
        """After first buy exhausts cash, second buy must be skipped."""
        data = {
            "allocation_plan": [
                _buy("AAA", 90, 100.0, stop=90.0, take=120.0),   # $9k
                _buy("BBB", 10, 100.0, stop=90.0, take=120.0),    # $1k — only $1k left
            ],
            "sells": [],
        }
        # $9k cash, first buy takes all of it (90 shares * $100)
        buys, _ = _validate_allocation(data, 9_000, 50_000, _candidates(("AAA", 100.0), ("BBB", 100.0)))
        assert len(buys) == 1
        assert buys[0]["ticker"] == "AAA"

    def test_price_drift_corrected(self):
        """If Claude's price is >5% off the scored price, use scored price."""
        # Claude says $100, scored price is $90 (>5% drift)
        data = {"allocation_plan": [_buy("XYZ", 100, 100.0, stop=90.0, take=120.0)], "sells": []}
        buys, _ = _validate_allocation(data, 100_000, 200_000, _candidates(("XYZ", 90.0)))
        assert len(buys) == 1
        assert buys[0]["price"] == 90.0

    def test_price_within_tolerance_kept(self):
        """Price within 5% of scored price should not be adjusted."""
        data = {"allocation_plan": [_buy("XYZ", 10, 101.0, stop=90.0, take=120.0)], "sells": []}
        buys, _ = _validate_allocation(data, 100_000, 200_000, _candidates(("XYZ", 100.0)))
        assert len(buys) == 1
        assert buys[0]["price"] == 101.0

    def test_empty_allocation_plan(self):
        data = {"allocation_plan": [], "sells": []}
        buys, sells = _validate_allocation(data, 10_000, 50_000, [])
        assert buys == []
        assert sells == []

    def test_factor_scores_passed_through(self):
        """factor_scores from the scored_candidates dict must be on the validated buy."""
        candidates = [{"ticker": "AAPL", "current_price": 150.0, "factor_scores": {"price_momentum": 80}, "data_completeness": 5}]
        data = {"allocation_plan": [_buy("AAPL", 10, 150.0, stop=138.0, take=180.0)], "sells": []}
        buys, _ = _validate_allocation(data, 10_000, 50_000, candidates)
        assert buys[0]["factor_scores"] == {"price_momentum": 80}


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_allocation — sells
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateAllocationSells:

    def test_valid_sell_accepted(self):
        data = {"allocation_plan": [], "sells": [_sell("AAPL", 10, 160.0)]}
        _, sells = _validate_allocation(
            data, 0, 50_000, [],
            held_tickers={"AAPL"},
            held_shares_map={"AAPL": 20},
        )
        assert len(sells) == 1
        assert sells[0]["ticker"] == "AAPL"
        assert sells[0]["shares"] == 10

    def test_phantom_sell_blocked(self):
        """Selling a ticker not in held_tickers must be blocked."""
        data = {"allocation_plan": [], "sells": [_sell("MSFT", 10, 400.0)]}
        _, sells = _validate_allocation(
            data, 0, 50_000, [],
            held_tickers={"AAPL"},
            held_shares_map={"AAPL": 20},
        )
        assert len(sells) == 0

    def test_sell_capped_to_held_shares(self):
        """Claude asking to sell more than held shares must be capped."""
        data = {"allocation_plan": [], "sells": [_sell("AAPL", 50, 160.0)]}
        _, sells = _validate_allocation(
            data, 0, 50_000, [],
            held_tickers={"AAPL"},
            held_shares_map={"AAPL": 20},
        )
        assert len(sells) == 1
        assert sells[0]["shares"] == 20  # capped to held

    def test_trim_sell_accepted_as_is(self):
        """Partial sell (trim) where shares < held must be accepted unchanged."""
        data = {"allocation_plan": [], "sells": [_sell("AAPL", 5, 160.0)]}
        _, sells = _validate_allocation(
            data, 0, 50_000, [],
            held_tickers={"AAPL"},
            held_shares_map={"AAPL": 20},
        )
        assert len(sells) == 1
        assert sells[0]["shares"] == 5

    def test_sell_with_zero_shares_skipped(self):
        data = {"allocation_plan": [], "sells": [_sell("AAPL", 0, 160.0)]}
        _, sells = _validate_allocation(
            data, 0, 50_000, [],
            held_tickers={"AAPL"},
            held_shares_map={"AAPL": 20},
        )
        assert len(sells) == 0

    def test_sell_with_zero_price_skipped(self):
        data = {"allocation_plan": [], "sells": [_sell("AAPL", 10, 0.0)]}
        _, sells = _validate_allocation(
            data, 0, 50_000, [],
            held_tickers={"AAPL"},
            held_shares_map={"AAPL": 20},
        )
        assert len(sells) == 0

    def test_empty_held_tickers_blocks_all_sells(self):
        """When nothing is held, all sells must be phantom-blocked."""
        data = {"allocation_plan": [], "sells": [_sell("AAPL", 10, 160.0), _sell("MSFT", 5, 400.0)]}
        _, sells = _validate_allocation(data, 0, 50_000, [], held_tickers=set(), held_shares_map={})
        assert len(sells) == 0

    def test_multiple_sells_mixed_held_and_phantom(self):
        data = {
            "allocation_plan": [],
            "sells": [
                _sell("AAPL", 10, 160.0),   # held — OK
                _sell("MSFT", 5, 400.0),    # not held — phantom
                _sell("XYZ", 100, 50.0),    # not held — phantom
            ],
        }
        _, sells = _validate_allocation(
            data, 0, 50_000, [],
            held_tickers={"AAPL"},
            held_shares_map={"AAPL": 20},
        )
        assert len(sells) == 1
        assert sells[0]["ticker"] == "AAPL"

    def test_sell_reasoning_preserved(self):
        data = {"allocation_plan": [], "sells": [_sell("AAPL", 10, 160.0, reasoning="Thesis broken")]}
        _, sells = _validate_allocation(
            data, 0, 50_000, [],
            held_tickers={"AAPL"},
            held_shares_map={"AAPL": 20},
        )
        assert sells[0]["reasoning"] == "Thesis broken"


# ═══════════════════════════════════════════════════════════════════════════════
# _build_allocation_prompt — mode parameter
# ═══════════════════════════════════════════════════════════════════════════════

from types import SimpleNamespace
import pandas as pd

# Helper to call _build_allocation_prompt with minimum viable args
def _minimal_prompt(mode: str = "full") -> str:
    from unittest.mock import patch
    from ai_allocator import _build_allocation_prompt
    from market_regime import MarketRegime

    state = SimpleNamespace(
        positions=pd.DataFrame(columns=["ticker", "shares", "avg_cost_basis",
                                        "current_price", "market_value",
                                        "unrealized_pnl_pct", "stop_loss",
                                        "take_profit", "entry_date"]),
        transactions=pd.DataFrame(),
        cash=100_000.0,
        total_equity=100_000.0,
        num_positions=0,
        regime=MarketRegime.SIDEWAYS,
        config={"max_positions": 10, "default_stop_loss_pct": 8.0},
        portfolio_id="_test_prompt",
        regime_analysis=None,
    )
    with patch("ai_allocator.get_macro_context", return_value=""):
        return _build_allocation_prompt(
            state=state,
            layer1_sells=[],
            scored_candidates=[],
            sector_map={},
            regime=MarketRegime.SIDEWAYS,
            warning_severity="NORMAL",
            strategy_dna="Test strategy",
            available_cash=100_000.0,
            info_cache={},
            full_watchlist=False,
            regime_analysis=None,
            prompt_extras=None,
            portfolio_id="_test_prompt",
            mode=mode,
        )


def test_build_prompt_full_mode_omits_directive():
    p = _minimal_prompt(mode="full")
    assert "CASH DEPLOYMENT MODE" not in p
    assert "RISK REVIEW MODE" not in p


def test_build_prompt_buys_only_includes_cash_deployment_directive():
    p = _minimal_prompt(mode="buys_only")
    assert "CASH DEPLOYMENT MODE" in p
    assert "do not propose any sells" in p.lower()
    # Directive must appear before HARD CONSTRAINTS so Claude reads it first
    assert p.index("CASH DEPLOYMENT MODE") < p.index("HARD CONSTRAINTS")


def test_build_prompt_sells_only_includes_risk_review_directive():
    p = _minimal_prompt(mode="sells_only")
    assert "RISK REVIEW MODE" in p
    assert "do not propose any new buys" in p.lower()
    assert p.index("RISK REVIEW MODE") < p.index("HARD CONSTRAINTS")


def test_validate_allocation_buys_only_drops_sells_even_if_claude_returns_them():
    from ai_allocator import _validate_allocation
    allocation_data = {
        "allocation_plan": [
            {"ticker": "AAPL", "shares": 10, "price": 150.0,
             "stop_loss": 138.0, "take_profit": 180.0, "reasoning": "buy"},
        ],
        "sells": [
            {"ticker": "MSFT", "shares": 5, "price": 200.0, "reasoning": "claude misbehaving"},
        ],
    }
    valid_buys, ai_sells = _validate_allocation(
        allocation_data,
        available_cash=100_000.0,
        total_equity=100_000.0,
        scored_candidates=[{"ticker": "AAPL", "composite_score": 70, "current_price": 150.0,
                            "factor_scores": {}, "data_completeness": 6}],
        held_tickers={"MSFT"},
        held_shares_map={"MSFT": 5},
        max_positions=None,
        mode="buys_only",
    )
    assert len(valid_buys) == 1
    assert ai_sells == [], "buys_only mode must drop all sells"


def test_validate_allocation_sells_only_drops_buys_even_if_claude_returns_them():
    from ai_allocator import _validate_allocation
    allocation_data = {
        "allocation_plan": [
            {"ticker": "AAPL", "shares": 10, "price": 150.0,
             "stop_loss": 138.0, "take_profit": 180.0, "reasoning": "claude misbehaving"},
        ],
        "sells": [
            {"ticker": "MSFT", "shares": 5, "price": 200.0, "reasoning": "trim winner"},
        ],
    }
    valid_buys, ai_sells = _validate_allocation(
        allocation_data,
        available_cash=100_000.0,
        total_equity=100_000.0,
        scored_candidates=[],
        held_tickers={"MSFT"},
        held_shares_map={"MSFT": 5},
        max_positions=None,
        mode="sells_only",
    )
    assert valid_buys == [], "sells_only mode must drop all buys"
    assert len(ai_sells) == 1


def test_validate_allocation_full_mode_keeps_both_sides_unchanged():
    from ai_allocator import _validate_allocation
    allocation_data = {
        "allocation_plan": [
            {"ticker": "AAPL", "shares": 10, "price": 150.0,
             "stop_loss": 138.0, "take_profit": 180.0, "reasoning": "buy"},
        ],
        "sells": [
            {"ticker": "MSFT", "shares": 5, "price": 200.0, "reasoning": "sell"},
        ],
    }
    valid_buys, ai_sells = _validate_allocation(
        allocation_data,
        available_cash=100_000.0,
        total_equity=100_000.0,
        scored_candidates=[{"ticker": "AAPL", "composite_score": 70, "current_price": 150.0,
                            "factor_scores": {}, "data_completeness": 6}],
        held_tickers={"MSFT"},
        held_shares_map={"MSFT": 5},
        max_positions=None,
        mode="full",
    )
    assert len(valid_buys) == 1
    assert len(ai_sells) == 1


def test_run_ai_allocation_threads_mode_to_prompt_and_validate(monkeypatch):
    """Verify mode arg is passed through to both _build_allocation_prompt and _validate_allocation."""
    from ai_allocator import run_ai_allocation
    from market_regime import MarketRegime

    state = SimpleNamespace(
        positions=pd.DataFrame(),
        transactions=pd.DataFrame(),
        cash=100_000.0,
        total_equity=100_000.0,
        num_positions=0,
        regime=MarketRegime.SIDEWAYS,
        config={"max_positions": 10, "ai_model": "claude-opus-4-7"},
        portfolio_id="_test_thread",
        regime_analysis=None,
    )

    captured = {"prompt_mode": None, "validate_mode": None}

    def _fake_build(*args, **kwargs):
        captured["prompt_mode"] = kwargs.get("mode")
        return "PROMPT_BODY"

    def _fake_validate(*args, **kwargs):
        captured["validate_mode"] = kwargs.get("mode")
        return [], []

    monkeypatch.setattr("ai_allocator._build_allocation_prompt", _fake_build)
    monkeypatch.setattr("ai_allocator._validate_allocation", _fake_validate)
    monkeypatch.setattr("ai_allocator._parse_json", lambda _t: {"allocation_plan": [], "sells": []})

    class _FakeClient:
        class messages:
            @staticmethod
            def create(**_kw):
                resp = SimpleNamespace()
                resp.content = [SimpleNamespace(text='{"allocation_plan":[],"sells":[]}')]
                resp.model = "claude-opus-4-7"
                return resp
    monkeypatch.setattr("ai_allocator.get_ai_client", lambda: _FakeClient())

    run_ai_allocation(
        state=state,
        layer1_sells=[],
        scored_candidates=[],
        sector_map={},
        regime=MarketRegime.SIDEWAYS,
        warning_severity="NORMAL",
        strategy_dna="test",
        info_cache={},
        regime_analysis=None,
        prompt_extras=None,
        mode="buys_only",
    )

    assert captured["prompt_mode"] == "buys_only"
    assert captured["validate_mode"] == "buys_only"


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_allocation — held-position price correction (regression 2026-06-01)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Bug: Claude's allocation only had its price cross-checked against the
# scored-candidate price map. Held positions being pressed (and ALL sells) are
# not in that map, so Claude's hallucinated round-number prices (e.g. NBIS @
# $374 when real was $272) passed through to the Actions tab unaltered. Fix:
# pin held buys/sells to held_price_map and rescale stop/target + shares.

class TestValidateAllocationHeldPriceCorrection:

    def test_held_press_buy_repriced_to_real_with_stops_rescaled(self):
        # Claude: NBIS 400 @ $374, stop $320 (~14.4% below), target $450 (~20.3% above).
        # Held position's real price is $272.15 and NBIS is not a scored candidate.
        data = {"allocation_plan": [_buy("NBIS", 400, 374.0, stop=320.0, take=450.0)], "sells": []}
        buys, _ = _validate_allocation(
            data, 5_000_000, 6_000_000, _candidates(),  # NBIS absent from candidates
            held_tickers={"NBIS"}, held_shares_map={"NBIS": 1579},
            held_price_map={"NBIS": 272.15},
        )
        assert len(buys) == 1
        b = buys[0]
        assert abs(b["price"] - 272.15) < 0.01                       # re-anchored to real price
        assert b["stop_loss"] < b["price"] < b["take_profit"]        # straddle preserved
        assert abs(b["stop_loss"] / 272.15 - 320 / 374) < 0.01       # stop % preserved
        assert abs(b["take_profit"] / 272.15 - 450 / 374) < 0.01     # target % preserved
        assert abs(b["shares"] * b["price"] - 400 * 374) < b["price"]  # dollar allocation preserved

    def test_scored_candidate_price_unchanged_within_tolerance(self):
        # Candidate price within 5% of Claude's — must NOT be altered, and the
        # candidate map takes priority over any held map.
        data = {"allocation_plan": [_buy("RPRX", 8000, 54.53, stop=49.0, take=62.0)], "sells": []}
        buys, _ = _validate_allocation(
            data, 5_000_000, 6_000_000, _candidates(("RPRX", 54.54)),
            held_tickers=set(), held_shares_map={}, held_price_map={},
        )
        assert buys[0]["price"] == 54.53 and buys[0]["shares"] == 8000

    def test_held_sell_price_pinned_to_real_price(self):
        # Claude: SELL SEDG @ $89; real held price $74.85.
        data = {"allocation_plan": [], "sells": [_sell("SEDG", 3617, 89.0)]}
        _, sells = _validate_allocation(
            data, 0, 6_000_000, [],
            held_tickers={"SEDG"}, held_shares_map={"SEDG": 3617},
            held_price_map={"SEDG": 74.85},
        )
        assert len(sells) == 1
        assert abs(sells[0]["price"] - 74.85) < 0.01

    def test_no_held_price_falls_back_to_claude_price(self):
        # If we have no trusted price at all, behavior is unchanged (Claude's price).
        data = {"allocation_plan": [], "sells": [_sell("ZZZ", 100, 12.34)]}
        _, sells = _validate_allocation(
            data, 0, 6_000_000, [],
            held_tickers={"ZZZ"}, held_shares_map={"ZZZ": 100}, held_price_map={},
        )
        assert sells[0]["price"] == 12.34
