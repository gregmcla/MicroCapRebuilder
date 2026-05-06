"""
Canned Anthropic SDK responses for integration tests.

Reuses the MagicMock pattern from tests/test_suggest_config.py:
mock_resp.content = [MagicMock(text=...)]
"""
import json
from unittest.mock import MagicMock


def _wrap(text: str, model: str = "claude-opus-4-7") -> MagicMock:
    """Build a mock Anthropic response object with `.content[0].text` and `.model`."""
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.model = model
    return resp


def ai_review_approve_all(actions: list[dict]) -> MagicMock:
    """Every proposed action APPROVED, confidence 0.9."""
    decisions = []
    for a in actions:
        decisions.append({
            "ticker": a["ticker"],
            "action_type": a.get("action_type", a.get("action", "BUY")),
            "decision": "APPROVE",
            "confidence": 0.9,
            "reasoning": "Test approve.",
        })
    return _wrap(json.dumps({"decisions": decisions}))


def ai_review_veto_all(actions: list[dict], reason: str = "Test veto.") -> MagicMock:
    decisions = []
    for a in actions:
        decisions.append({
            "ticker": a["ticker"],
            "action_type": a.get("action_type", a.get("action", "BUY")),
            "decision": "VETO",
            "confidence": 0.9,
            "reasoning": reason,
        })
    return _wrap(json.dumps({"decisions": decisions}))


def ai_allocator_buy_basket(
    tickers: list[str],
    *,
    shares_each: int = 100,
    price_each: float = 50.0,
    stop_loss_pct: float = -0.10,
    take_profit_pct: float = 0.20,
) -> MagicMock:
    """
    AI allocator returns a basket of BUYs. Used for ai_driven path tests.

    Schema matches what `_validate_allocation` in ai_allocator.py expects:
    `allocation_plan` (BUYs) and `sells` (SELLs).
    """
    plan = []
    for t in tickers:
        plan.append({
            "ticker": t,
            "shares": shares_each,
            "price": price_each,
            "stop_loss": round(price_each * (1 + stop_loss_pct), 2),
            "take_profit": round(price_each * (1 + take_profit_pct), 2),
            "reasoning": f"Test buy {t}",
        })
    return _wrap(json.dumps({
        "allocation_plan": plan,
        "sells": [],
        "portfolio_thesis": "test thesis",
    }))


def ai_allocator_phantom_sell(unheld_ticker: str = "GHOST") -> MagicMock:
    """AI hallucinates a sell of a ticker not held. Tests the phantom-sell guard."""
    return _wrap(json.dumps({
        "allocation_plan": [],
        "sells": [{
            "ticker": unheld_ticker,
            "shares": 100,
            "price": 50.0,
            "reasoning": "phantom sell",
        }],
        "portfolio_thesis": "test phantom",
    }))


def ai_allocator_failure_factory():
    """Returns a side_effect that raises APITimeoutError, simulating Claude unavailable."""
    import anthropic

    def _raise(*_args, **_kwargs):
        raise anthropic.APITimeoutError("test timeout")

    return _raise


def ai_allocator_empty() -> MagicMock:
    """No actions proposed."""
    return _wrap(json.dumps({
        "allocation_plan": [],
        "sells": [],
        "portfolio_thesis": "",
    }))
