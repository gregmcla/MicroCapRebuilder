#!/usr/bin/env python3
"""Tests for position_lineage aggregator."""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from position_lineage import (
    build_lineage,
    build_summary,
    event_to_dict,
    WatchlistAddedEvent,
    WatchlistRemovedEvent,
    ScoredEvent,
    AiConsideredEvent,
    BuyEvent,
    SellEvent,
    StopAdjustedEvent,
    PostMortemEvent,
)


_TEST_PID = "_test_position_lineage"
_DATA_BASE = Path(__file__).parent.parent.parent / "data" / "portfolios" / _TEST_PID


@pytest.fixture(autouse=True)
def _cleanup():
    shutil.rmtree(_DATA_BASE, ignore_errors=True)
    _DATA_BASE.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(_DATA_BASE, ignore_errors=True)


def _seed_transactions(rows: list[dict]) -> None:
    """Write rows to _TEST_PID/transactions.csv with the canonical columns."""
    import pandas as pd
    cols = [
        "transaction_id", "date", "ticker", "action", "shares", "price",
        "total_value", "stop_loss", "take_profit", "reason",
        "regime_at_entry", "composite_score", "factor_scores",
        "signal_rank", "trade_rationale",
        "source_proposal_id", "source_trace_id",
    ]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols]
    df.to_csv(_DATA_BASE / "transactions.csv", index=False)


def _seed_score_history(ticker: str, rows: list[dict]) -> None:
    path = _DATA_BASE / "daily_scores.jsonl"
    with path.open("w") as f:
        for r in rows:
            line = {"ticker": ticker, **r}
            line.setdefault("momentum", 0.0)
            line.setdefault("quality", 0.0)
            line.setdefault("earnings", 0.0)
            line.setdefault("volume", 0.0)
            line.setdefault("volatility", 0.0)
            line.setdefault("value_timing", 0.0)
            f.write(json.dumps(line) + "\n")


def _seed_watchlist_events(rows: list[dict]) -> None:
    path = _DATA_BASE / "watchlist_events.jsonl"
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _seed_risk_adjustments(rows: list[dict]) -> None:
    path = _DATA_BASE / "risk_adjustments.jsonl"
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ─── Empty / missing source resilience ───────────────────────────────────────

def test_empty_portfolio_returns_empty_lineage():
    assert build_lineage(_TEST_PID, "AAPL") == []


def test_missing_ticker_returns_empty():
    _seed_transactions([
        {"transaction_id": "tx001", "date": "2026-05-01", "ticker": "AAPL",
         "action": "BUY", "shares": 10, "price": 150.0},
    ])
    assert build_lineage(_TEST_PID, "NVDA") == []


# ─── Buy/Sell + FIFO realized P&L ────────────────────────────────────────────

def test_buy_event_emitted_with_all_fields():
    _seed_transactions([
        {"transaction_id": "tx001", "date": "2026-05-01T09:30:00",
         "ticker": "AAPL", "action": "BUY", "shares": 10, "price": 150.0,
         "stop_loss": 135.0, "take_profit": 180.0,
         "source_proposal_id": "abc12345", "source_trace_id": "trace_001",
         "factor_scores": json.dumps({"momentum": 75.0}),
         "trade_rationale": json.dumps({"ai_reasoning": "Strong breakout setup"}),
        },
    ])
    events = build_lineage(_TEST_PID, "AAPL")
    assert len(events) == 1
    e = events[0]
    assert isinstance(e, BuyEvent)
    assert e.ticker == "AAPL"
    assert e.shares == 10
    assert e.price == 150.0
    assert e.stop_loss == 135.0
    assert e.take_profit == 180.0
    assert e.proposal_id == "abc12345"
    assert e.trace_id == "trace_001"
    assert e.factor_scores == {"momentum": 75.0}
    assert "breakout" in e.ai_reasoning_excerpt


def test_sell_event_computes_realized_pnl_fifo():
    _seed_transactions([
        {"transaction_id": "tx001", "date": "2026-05-01", "ticker": "AAPL",
         "action": "BUY", "shares": 10, "price": 100.0},
        {"transaction_id": "tx002", "date": "2026-05-20", "ticker": "AAPL",
         "action": "SELL", "shares": 10, "price": 130.0, "reason": "TAKE_PROFIT"},
    ])
    events = build_lineage(_TEST_PID, "AAPL")
    assert len(events) == 2
    # Sorted newest first
    assert isinstance(events[0], SellEvent)
    assert isinstance(events[1], BuyEvent)
    sell = events[0]
    assert sell.realized_pnl == 300.0       # (130 - 100) * 10
    assert sell.realized_pnl_pct == 30.0
    assert sell.holding_days == 19
    assert sell.reason == "TAKE_PROFIT"


def test_sell_event_partial_fifo_across_two_buys():
    _seed_transactions([
        {"transaction_id": "tx001", "date": "2026-05-01", "ticker": "X",
         "action": "BUY", "shares": 5, "price": 100.0},
        {"transaction_id": "tx002", "date": "2026-05-10", "ticker": "X",
         "action": "BUY", "shares": 5, "price": 110.0},
        {"transaction_id": "tx003", "date": "2026-05-20", "ticker": "X",
         "action": "SELL", "shares": 8, "price": 120.0, "reason": "SIGNAL"},
    ])
    events = build_lineage(_TEST_PID, "X")
    sell = next(e for e in events if isinstance(e, SellEvent))
    # FIFO: first 5 from lot1 (cost 100), next 3 from lot2 (cost 110)
    # realized = (120-100)*5 + (120-110)*3 = 100 + 30 = 130
    assert sell.realized_pnl == 130.0
    # cost basis = 100*5 + 110*3 = 830; pct = 130/830 ≈ 15.66%
    assert sell.realized_pnl_pct == round(130.0 / 830.0 * 100, 2)
    # First sold lot's buy_date = 2026-05-01
    assert sell.holding_days == 19


# ─── Score events with dedup ─────────────────────────────────────────────────

def test_score_events_dedup_below_threshold():
    """Scores that change by <5pt between days should be deduped, only first+last."""
    _seed_score_history("AAPL", [
        {"date": "2026-05-01", "composite": 60.0},
        {"date": "2026-05-02", "composite": 61.0},  # +1, deduped
        {"date": "2026-05-03", "composite": 62.0},  # +2, deduped
        {"date": "2026-05-04", "composite": 70.0},  # +10 vs 60 emitted, kept
        {"date": "2026-05-05", "composite": 71.0},  # last, always kept
    ])
    events = [e for e in build_lineage(_TEST_PID, "AAPL") if isinstance(e, ScoredEvent)]
    # Expect: 2026-05-01 (first), 2026-05-04 (jumped), 2026-05-05 (last)
    assert len(events) == 3
    dates = sorted(e.timestamp for e in events)
    assert dates == ["2026-05-01", "2026-05-04", "2026-05-05"]


def test_score_events_include_factor_scores():
    _seed_score_history("AAPL", [
        {"date": "2026-05-01", "composite": 70.0, "momentum": 80.0, "quality": 60.0},
    ])
    events = [e for e in build_lineage(_TEST_PID, "AAPL") if isinstance(e, ScoredEvent)]
    assert len(events) == 1
    assert events[0].factor_scores["price_momentum"] == 80.0
    assert events[0].factor_scores["quality"] == 60.0


# ─── Watchlist events ────────────────────────────────────────────────────────

def test_watchlist_events_emitted():
    _seed_watchlist_events([
        {"ts": "2026-05-01T06:30:00", "ticker": "AAPL", "type": "added",
         "reason": "scan:momentum_breakouts", "source": "discovery"},
        {"ts": "2026-06-01T06:30:00", "ticker": "AAPL", "type": "removed",
         "reason": "poor_performer"},
        {"ts": "2026-05-01T06:30:00", "ticker": "NVDA", "type": "added",
         "reason": "manual", "source": "manual"},
    ])
    events = build_lineage(_TEST_PID, "AAPL")
    assert len(events) == 2
    kinds = sorted(type(e).__name__ for e in events)
    assert kinds == ["WatchlistAddedEvent", "WatchlistRemovedEvent"]
    added = next(e for e in events if isinstance(e, WatchlistAddedEvent))
    assert added.reason == "scan:momentum_breakouts"
    assert added.source == "discovery"


# ─── Risk adjustments ────────────────────────────────────────────────────────

def test_risk_adjustment_events_emitted():
    _seed_risk_adjustments([
        {"ts": "2026-06-16T16:13:00", "ticker": "SPCX", "field": "stop_loss",
         "old": 125.55, "new": 164.75, "source": "manual"},
        {"ts": "2026-06-16T16:13:00", "ticker": "SPCX", "field": "take_profit",
         "old": 162.0, "new": 400.0, "source": "manual"},
    ])
    events = build_lineage(_TEST_PID, "SPCX")
    assert len(events) == 2
    assert all(isinstance(e, StopAdjustedEvent) for e in events)
    fields = sorted(e.field_name for e in events)
    assert fields == ["stop_loss", "take_profit"]
    stop = next(e for e in events if e.field_name == "stop_loss")
    assert stop.old_value == 125.55
    assert stop.new_value == 164.75
    assert stop.source == "manual"


# ─── Merge + sort ────────────────────────────────────────────────────────────

def test_merge_all_sources_and_sort_desc():
    _seed_transactions([
        {"transaction_id": "tx001", "date": "2026-05-02T09:36:00", "ticker": "SPCX",
         "action": "BUY", "shares": 4188, "price": 135.0,
         "stop_loss": 125.55, "take_profit": 162.0},
    ])
    _seed_watchlist_events([
        {"ts": "2026-05-02T06:30:00", "ticker": "SPCX", "type": "added",
         "reason": "scan:score_all", "source": "discovery"},
    ])
    _seed_risk_adjustments([
        {"ts": "2026-06-16T16:13:00", "ticker": "SPCX", "field": "stop_loss",
         "old": 125.55, "new": 164.75, "source": "manual"},
    ])
    events = build_lineage(_TEST_PID, "SPCX")
    # 3 events: watchlist add (earliest), buy, stop adjust (newest)
    assert len(events) == 3
    assert isinstance(events[0], StopAdjustedEvent)
    assert isinstance(events[1], BuyEvent)
    assert isinstance(events[2], WatchlistAddedEvent)


def test_from_date_filter():
    _seed_transactions([
        {"transaction_id": "tx001", "date": "2026-01-01", "ticker": "X",
         "action": "BUY", "shares": 10, "price": 100.0},
        {"transaction_id": "tx002", "date": "2026-05-01", "ticker": "X",
         "action": "SELL", "shares": 10, "price": 120.0, "reason": "SIGNAL"},
    ])
    events = build_lineage(_TEST_PID, "X", from_date="2026-04-01")
    assert len(events) == 1
    assert isinstance(events[0], SellEvent)


def test_limit_trims_to_n():
    _seed_transactions([
        {"transaction_id": f"tx{i:03d}", "date": f"2026-05-{i:02d}",
         "ticker": "X", "action": "BUY", "shares": 1, "price": 100.0}
        for i in range(1, 11)
    ])
    events = build_lineage(_TEST_PID, "X", limit=3)
    assert len(events) == 3


# ─── Summary ─────────────────────────────────────────────────────────────────

def test_summary_basic():
    _seed_transactions([
        {"transaction_id": "tx001", "date": "2026-05-01", "ticker": "AAPL",
         "action": "BUY", "shares": 10, "price": 100.0},
        {"transaction_id": "tx002", "date": "2026-05-15", "ticker": "AAPL",
         "action": "SELL", "shares": 10, "price": 120.0, "reason": "SIGNAL"},
    ])
    s = build_summary(_TEST_PID, "AAPL")
    assert s["ticker"] == "AAPL"
    assert s["total_trades"] == 1
    assert s["total_pnl"] == 200.0
    assert s["current_status"] == "closed"
    assert s["first_bought"] == "2026-05-01"


def test_summary_open_position():
    _seed_transactions([
        {"transaction_id": "tx001", "date": "2026-05-01", "ticker": "X",
         "action": "BUY", "shares": 10, "price": 100.0},
    ])
    s = build_summary(_TEST_PID, "X")
    assert s["current_status"] == "held"
    assert s["total_trades"] == 0


# ─── Serialization ───────────────────────────────────────────────────────────

def test_event_to_dict_includes_kind_discriminator():
    e = BuyEvent(
        timestamp="2026-05-01", ticker="AAPL", transaction_id="tx001",
        shares=10, price=100.0, stop_loss=90.0, take_profit=120.0,
    )
    d = event_to_dict(e)
    assert d["kind"] == "buy"
    assert d["ticker"] == "AAPL"
    assert d["shares"] == 10


def test_all_event_kinds_have_discriminator():
    """Smoke-test: every event type round-trips with the right kind string."""
    from position_lineage import EVENT_KIND
    expected = {
        "watchlist_added", "watchlist_removed", "scored", "ai_considered",
        "buy", "sell", "stop_adjusted", "post_mortem",
    }
    assert set(EVENT_KIND.values()) == expected
