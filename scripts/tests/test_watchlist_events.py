#!/usr/bin/env python3
"""Tests for watchlist_events append-only log."""
import shutil
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from watchlist_events import record_watchlist_event, record_many, read_events


_TEST_PID = "_test_watchlist_events"
_BASE = Path(__file__).parent.parent.parent / "data" / "portfolios" / _TEST_PID


@pytest.fixture(autouse=True)
def _cleanup():
    shutil.rmtree(_BASE, ignore_errors=True)
    yield
    shutil.rmtree(_BASE, ignore_errors=True)


def test_record_and_read_single_event():
    assert record_watchlist_event(_TEST_PID, "AAPL", "added",
                                   reason="scan:momentum", source="discovery")
    events = read_events(_TEST_PID)
    assert len(events) == 1
    assert events[0]["ticker"] == "AAPL"
    assert events[0]["type"] == "added"
    assert events[0]["reason"] == "scan:momentum"
    assert events[0]["source"] == "discovery"


def test_ticker_normalized_to_upper():
    record_watchlist_event(_TEST_PID, "aapl", "added")
    events = read_events(_TEST_PID, ticker="AAPL")
    assert len(events) == 1
    assert events[0]["ticker"] == "AAPL"


def test_invalid_kind_rejected():
    assert not record_watchlist_event(_TEST_PID, "AAPL", "weird_kind")
    assert read_events(_TEST_PID) == []


def test_filter_by_ticker():
    record_watchlist_event(_TEST_PID, "AAPL", "added")
    record_watchlist_event(_TEST_PID, "NVDA", "added")
    record_watchlist_event(_TEST_PID, "AAPL", "removed", reason="poor_performer")
    aapl = read_events(_TEST_PID, ticker="AAPL")
    assert len(aapl) == 2
    nvda = read_events(_TEST_PID, ticker="NVDA")
    assert len(nvda) == 1


def test_record_many_batch():
    n = record_many(_TEST_PID, [
        {"ticker": "AAPL", "type": "added", "reason": "x"},
        {"ticker": "NVDA", "type": "added", "reason": "y"},
        {"ticker": "INVALID"},  # missing type — skipped
    ])
    assert n == 2
    events = read_events(_TEST_PID)
    assert len(events) == 2


def test_missing_file_returns_empty():
    assert read_events(_TEST_PID) == []
    assert read_events(_TEST_PID, ticker="AAPL") == []


def test_concurrent_writes_under_flock():
    """Two threads each writing 10 events should produce 20 valid lines."""
    def _hammer(prefix):
        for i in range(10):
            record_watchlist_event(_TEST_PID, f"{prefix}{i}", "added", reason="concurrent")

    t1 = threading.Thread(target=_hammer, args=("A",))
    t2 = threading.Thread(target=_hammer, args=("B",))
    t1.start(); t2.start()
    t1.join(); t2.join()
    events = read_events(_TEST_PID)
    assert len(events) == 20
    tickers = sorted(e["ticker"] for e in events)
    assert tickers == sorted([f"A{i}" for i in range(10)] + [f"B{i}" for i in range(10)])


def test_record_failure_returns_false_without_raising():
    # Pass portfolio_id="" → record_watchlist_event short-circuits to False.
    assert not record_watchlist_event("", "AAPL", "added")
