import json
from pathlib import Path
import pandas as pd
import pytest
from recent_trades import get_recent_trade_details


def _write_csvs(tmp_path, transactions, post_mortems):
    pdir = tmp_path / "portfolios" / "testp"
    pdir.mkdir(parents=True)
    pd.DataFrame(transactions).to_csv(pdir / "transactions.csv", index=False)
    pd.DataFrame(post_mortems).to_csv(pdir / "post_mortems.csv", index=False)
    return pdir


def test_returns_empty_when_no_trades(tmp_path, monkeypatch):
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    (tmp_path / "portfolios" / "empty").mkdir(parents=True)
    result = get_recent_trade_details("empty", limit=15)
    assert result == []


def test_joins_buy_and_post_mortem_by_buy_transaction_id(tmp_path, monkeypatch):
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    _write_csvs(
        tmp_path,
        transactions=[
            {
                "transaction_id": "BUY-1", "date": "2026-04-10", "ticker": "NVDA",
                "action": "BUY", "shares": 10, "price": 100.0, "regime_at_entry": "BULL",
                "factor_scores": json.dumps({"price_momentum": 82, "quality": 41}),
                "trade_rationale": json.dumps({"ai_reasoning": "Strong AI demand thesis"}),
            },
            {
                "transaction_id": "SELL-1", "date": "2026-04-20", "ticker": "NVDA",
                "action": "SELL", "shares": 10, "price": 92.0,
                "factor_scores": "{}", "trade_rationale": "{}",
            },
        ],
        post_mortems=[{
            "transaction_id": "SELL-1", "buy_transaction_id": "BUY-1", "ticker": "NVDA",
            "close_date": "2026-04-20", "entry_price": 100.0, "exit_price": 92.0,
            "pnl": -80.0, "pnl_pct": -8.0, "exit_reason": "STOP_LOSS", "holding_days": 10,
            "regime_at_entry": "BULL", "regime_at_exit": "BULL",
            "composite_score_at_entry": 72, "summary": "Stopped at trailing stop",
            "pattern_tags": "['momentum_fade']",
            "what_worked": "[]", "what_failed": "['Entry too late']",
            "recommendation": "Tighten momentum filter",
        }],
    )
    details = get_recent_trade_details("testp", limit=15)
    assert len(details) == 1
    t = details[0]
    assert t["ticker"] == "NVDA"
    assert t["pnl_pct"] == -8.0
    assert t["regime"] == "BULL"
    assert "Strong AI demand thesis" in t["entry_reasoning"]
    assert t["top_factors"] == [("price_momentum", 82), ("quality", 41)]
    assert t["exit_summary"] == "Stopped at trailing stop"
    assert t["pattern_tags"] == ["momentum_fade"]


def test_sorted_by_close_date_desc_limit_applied(tmp_path, monkeypatch):
    """20 trades, limit=15 → returns 15 most recent closes."""
    monkeypatch.setenv("MCR_DATA_DIR", str(tmp_path))
    txs, pms = [], []
    for i in range(20):
        txs.append({
            "transaction_id": f"BUY-{i}", "date": f"2026-03-{i+1:02d}", "ticker": f"T{i}",
            "action": "BUY", "shares": 1, "price": 10.0, "regime_at_entry": "BULL",
            "factor_scores": "{}", "trade_rationale": "{}",
        })
        txs.append({
            "transaction_id": f"SELL-{i}", "date": f"2026-04-{i+1:02d}", "ticker": f"T{i}",
            "action": "SELL", "shares": 1, "price": 11.0,
            "factor_scores": "{}", "trade_rationale": "{}",
        })
        pms.append({
            "transaction_id": f"SELL-{i}", "buy_transaction_id": f"BUY-{i}", "ticker": f"T{i}",
            "close_date": f"2026-04-{i+1:02d}", "entry_price": 10, "exit_price": 11,
            "pnl": 1, "pnl_pct": 10.0, "exit_reason": "TAKE_PROFIT", "holding_days": 5,
            "regime_at_entry": "BULL", "regime_at_exit": "BULL",
            "composite_score_at_entry": 60, "summary": f"win {i}", "pattern_tags": "[]",
            "what_worked": "[]", "what_failed": "[]", "recommendation": "",
        })
    _write_csvs(tmp_path, txs, pms)
    details = get_recent_trade_details("testp", limit=15)
    assert len(details) == 15
    # Most recent first
    assert details[0]["ticker"] == "T19"
    assert details[-1]["ticker"] == "T5"


def test_format_trade_history_block_renders_text():
    from recent_trades import format_trade_history_block
    trades = [{
        "ticker": "NVDA", "entry_date": "2026-04-10", "exit_date": "2026-04-20",
        "pnl_pct": -8.0, "holding_days": 10, "regime": "BULL", "exit_reason": "STOP_LOSS",
        "entry_reasoning": "Strong AI demand thesis",
        "top_factors": [("price_momentum", 82), ("quality", 41)],
        "exit_summary": "Stopped at trailing stop", "pattern_tags": ["momentum_fade"],
    }]
    text = format_trade_history_block(trades)
    assert "NVDA" in text
    assert "-8.0%" in text
    assert "STOP_LOSS" in text
    assert "Strong AI demand thesis" in text
    assert "price_momentum=82" in text


def test_cluster_by_dominant_factor_groups_correctly():
    from recent_trades import cluster_by_dominant_factor
    trades = [
        {"ticker": "A", "top_factors": [("price_momentum", 85), ("volume", 70)], "pnl_pct": 5.0, "holding_days": 10, "regime": "BULL"},
        {"ticker": "B", "top_factors": [("price_momentum", 82), ("volatility", 60)], "pnl_pct": -3.0, "holding_days": 8, "regime": "BULL"},
        {"ticker": "C", "top_factors": [("value_timing", 80), ("quality", 70)], "pnl_pct": 12.0, "holding_days": 20, "regime": "BULL"},
        {"ticker": "D", "top_factors": [], "pnl_pct": 1.0, "holding_days": 5, "regime": "BULL"},
    ]
    clusters = cluster_by_dominant_factor(trades)
    assert "price_momentum" in clusters
    assert len(clusters["price_momentum"]) == 2
    assert "value_timing" in clusters
    assert "unknown" in clusters  # D has no top_factors


def test_format_clustered_history_block_renders_stats():
    from recent_trades import format_clustered_history_block
    trades = [
        {"ticker": "WIN1", "top_factors": [("price_momentum", 85)], "pnl_pct": 5.0,  "holding_days": 10, "regime": "BULL"},
        {"ticker": "WIN2", "top_factors": [("price_momentum", 82)], "pnl_pct": 12.0, "holding_days": 8,  "regime": "BULL"},
        {"ticker": "LOSE", "top_factors": [("price_momentum", 80)], "pnl_pct": -8.0, "holding_days": 6,  "regime": "BULL"},
    ]
    text = format_clustered_history_block(trades)
    assert "TRADES CLUSTERED BY DOMINANT ENTRY FACTOR" in text
    assert "price_momentum" in text
    assert "3 trades" in text
    assert "2W/1L" in text
    assert "+3.0%" in text  # avg pnl = (5 + 12 - 8) / 3
    assert "WIN1" in text or "WIN2" in text  # at least one ticker shown


def test_format_clustered_history_block_empty():
    from recent_trades import format_clustered_history_block
    assert format_clustered_history_block([]) == ""
