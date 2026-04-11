import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import json
import pytest
import pandas as pd


from api.routes.trade_reviews import _load_closed_trades


def _write_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture
def portfolio_dir(tmp_path: Path) -> Path:
    d = tmp_path / "portfolios" / "test"
    d.mkdir(parents=True)
    return d


def test_no_transactions_returns_empty(portfolio_dir: Path) -> None:
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert trades == []


def test_open_position_excluded(portfolio_dir: Path) -> None:
    """A BUY with no matching SELL must not appear in results."""
    _write_csv(portfolio_dir / "transactions.csv", [
        {"transaction_id": "aaa", "date": "2026-01-10", "ticker": "AAPL",
         "action": "BUY", "shares": 10, "price": 100.0, "total_value": 1000.0,
         "stop_loss": 90.0, "take_profit": 120.0, "reason": "SIGNAL",
         "regime_at_entry": "BULL", "composite_score": 75.0,
         "signal_rank": 1, "factor_scores": "{}", "trade_rationale": "{}"},
    ])
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert trades == []


def test_closed_trade_basic_fields(portfolio_dir: Path) -> None:
    """A matched BUY+SELL round-trip returns an enriched trade object."""
    rationale = json.dumps({"ai_reasoning": "Strong momentum play"})
    sell_rationale = json.dumps({"ai_reasoning": "Stop loss triggered"})
    _write_csv(portfolio_dir / "transactions.csv", [
        {"transaction_id": "buy-1", "date": "2026-01-10", "ticker": "RCKT",
         "action": "BUY", "shares": 100, "price": 10.0, "total_value": 1000.0,
         "stop_loss": 9.0, "take_profit": 15.0, "reason": "SIGNAL",
         "regime_at_entry": "BULL", "composite_score": 70.0,
         "signal_rank": 2, "factor_scores": '{"momentum": 80.0, "quality": 60.0}',
         "trade_rationale": rationale},
        {"transaction_id": "sell-1", "date": "2026-01-15", "ticker": "RCKT",
         "action": "SELL", "shares": 100, "price": 9.50, "total_value": 950.0,
         "stop_loss": 0, "take_profit": 0, "reason": "STOP_LOSS",
         "regime_at_entry": "BULL", "composite_score": 0,
         "signal_rank": 0, "factor_scores": "{}", "trade_rationale": sell_rationale},
    ])
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert len(trades) == 1
    t = trades[0]
    assert t["trade_id"] == "buy-1"
    assert t["ticker"] == "RCKT"
    assert t["entry_date"] == "2026-01-10"
    assert t["exit_date"] == "2026-01-15"
    assert t["entry_price"] == pytest.approx(10.0)
    assert t["exit_price"] == pytest.approx(9.50)
    assert t["exit_reason"] == "STOP_LOSS"
    assert t["entry_ai_reasoning"] == "Strong momentum play"
    assert t["exit_ai_reasoning"] == "Stop loss triggered"
    assert t["factor_scores"]["momentum"] == pytest.approx(80.0)
    assert t["pnl"] == pytest.approx(-50.0)
    assert t["pnl_pct"] == pytest.approx(-5.0)


def test_missing_post_mortem_graceful(portfolio_dir: Path) -> None:
    """If post_mortems.csv doesn't exist, trade still returns with empty narrative fields."""
    _write_csv(portfolio_dir / "transactions.csv", [
        {"transaction_id": "buy-2", "date": "2026-02-01", "ticker": "XYZ",
         "action": "BUY", "shares": 50, "price": 20.0, "total_value": 1000.0,
         "stop_loss": 18.0, "take_profit": 26.0, "reason": "SIGNAL",
         "regime_at_entry": "SIDEWAYS", "composite_score": 55.0,
         "signal_rank": 3, "factor_scores": "{}", "trade_rationale": "{}"},
        {"transaction_id": "sell-2", "date": "2026-02-05", "ticker": "XYZ",
         "action": "SELL", "shares": 50, "price": 22.0, "total_value": 1100.0,
         "stop_loss": 0, "take_profit": 0, "reason": "TAKE_PROFIT",
         "regime_at_entry": "SIDEWAYS", "composite_score": 0,
         "signal_rank": 0, "factor_scores": "{}", "trade_rationale": "{}"},
    ])
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert len(trades) == 1
    t = trades[0]
    assert t["what_worked"] == ""
    assert t["what_failed"] == ""
    assert t["recommendation"] == ""


def test_post_mortem_json_arrays_parsed(portfolio_dir: Path) -> None:
    """what_worked and what_failed JSON arrays are joined into readable strings."""
    import json as _json
    _write_csv(portfolio_dir / "transactions.csv", [
        {"transaction_id": "buy-3", "date": "2026-03-01", "ticker": "FOO",
         "action": "BUY", "shares": 10, "price": 50.0, "total_value": 500.0,
         "stop_loss": 45.0, "take_profit": 65.0, "reason": "SIGNAL",
         "regime_at_entry": "BULL", "composite_score": 0, "signal_rank": 0,
         "factor_scores": "{}", "trade_rationale": "{}"},
        {"transaction_id": "sell-3", "date": "2026-03-10", "ticker": "FOO",
         "action": "SELL", "shares": 10, "price": 45.0, "total_value": 450.0,
         "stop_loss": 0, "take_profit": 0, "reason": "STOP_LOSS",
         "regime_at_entry": "BULL", "composite_score": 0, "signal_rank": 0,
         "factor_scores": "{}", "trade_rationale": "{}"},
    ])
    _write_csv(portfolio_dir / "post_mortems.csv", [
        {"transaction_id": "sell-3", "buy_transaction_id": "buy-3",
         "ticker": "FOO", "close_date": "2026-03-10",
         "entry_price": 50.0, "exit_price": 45.0,
         "pnl": -50.0, "pnl_pct": -10.0, "exit_reason": "STOP_LOSS",
         "holding_days": 9, "regime_at_entry": "BULL", "regime_at_exit": "BULL",
         "composite_score_at_entry": 0, "signal_rank_at_entry": 0,
         "summary": "Loss taken",
         "what_worked": _json.dumps(["Stop loss protected capital"]),
         "what_failed": _json.dumps(["Entry timing was poor", "Momentum faded quickly"]),
         "pattern_tags": "[]",
         "recommendation": "Wait for pullback before entry"},
    ])
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert len(trades) == 1
    t = trades[0]
    assert t["what_worked"] == "Stop loss protected capital"
    assert "Entry timing was poor" in t["what_failed"]
    assert "Momentum faded quickly" in t["what_failed"]
    assert t["holding_days"] == 9
    assert t["pnl"] == pytest.approx(-50.0)
    assert t["pnl_pct"] == pytest.approx(-10.0)


def test_same_ticker_multiple_roundtrips(portfolio_dir: Path) -> None:
    """Two BUY+SELL pairs for the same ticker become two separate entries (FIFO)."""
    _write_csv(portfolio_dir / "transactions.csv", [
        {"transaction_id": "b1", "date": "2026-01-01", "ticker": "AA",
         "action": "BUY", "shares": 10, "price": 10.0, "total_value": 100.0,
         "stop_loss": 9.0, "take_profit": 13.0, "reason": "SIGNAL",
         "regime_at_entry": "BULL", "composite_score": 0, "signal_rank": 0,
         "factor_scores": "{}", "trade_rationale": "{}"},
        {"transaction_id": "s1", "date": "2026-01-05", "ticker": "AA",
         "action": "SELL", "shares": 10, "price": 11.0, "total_value": 110.0,
         "stop_loss": 0, "take_profit": 0, "reason": "TAKE_PROFIT",
         "regime_at_entry": "BULL", "composite_score": 0, "signal_rank": 0,
         "factor_scores": "{}", "trade_rationale": "{}"},
        {"transaction_id": "b2", "date": "2026-01-10", "ticker": "AA",
         "action": "BUY", "shares": 10, "price": 12.0, "total_value": 120.0,
         "stop_loss": 10.8, "take_profit": 15.6, "reason": "SIGNAL",
         "regime_at_entry": "BEAR", "composite_score": 0, "signal_rank": 0,
         "factor_scores": "{}", "trade_rationale": "{}"},
        {"transaction_id": "s2", "date": "2026-01-15", "ticker": "AA",
         "action": "SELL", "shares": 10, "price": 11.5, "total_value": 115.0,
         "stop_loss": 0, "take_profit": 0, "reason": "STOP_LOSS",
         "regime_at_entry": "BEAR", "composite_score": 0, "signal_rank": 0,
         "factor_scores": "{}", "trade_rationale": "{}"},
    ])
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert len(trades) == 2
    # Default sort is exit_date descending
    assert trades[0]["trade_id"] == "b2"
    assert trades[1]["trade_id"] == "b1"


def test_build_analyze_prompt_contains_ticker(portfolio_dir: Path) -> None:
    """Prompt built for a trade contains the ticker, P&L, entry thesis, and factors."""
    from api.routes.trade_reviews import _build_analyze_prompt
    trade = {
        "trade_id": "x1", "ticker": "AAPL",
        "entry_date": "2026-01-01", "exit_date": "2026-01-10",
        "entry_price": 100.0, "exit_price": 110.0,
        "pnl": 100.0, "pnl_pct": 10.0,
        "holding_days": 9, "exit_reason": "TAKE_PROFIT",
        "regime_at_entry": "BULL", "regime_at_exit": "BULL",
        "entry_ai_reasoning": "Strong trend", "exit_ai_reasoning": "Target hit",
        "factor_scores": {"momentum": 90.0},
        "what_worked": "Momentum", "what_failed": "", "recommendation": "Scale up",
        "summary": "",
    }
    prompt = _build_analyze_prompt(trade)
    assert "AAPL" in prompt
    assert "+10.0%" in prompt
    assert "Strong trend" in prompt
    assert "momentum" in prompt.lower()
    assert "90" in prompt
