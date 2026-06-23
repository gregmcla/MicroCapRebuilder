#!/usr/bin/env python3
"""Tests for risk_adjustments log + drift detector."""
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pytest

from risk_adjustments import (
    record_adjustment,
    read_adjustments,
    detect_and_log_drift,
)


_TEST_PID = "_test_risk_adjustments"
_BASE = Path(__file__).parent.parent.parent / "data" / "portfolios" / _TEST_PID


@pytest.fixture(autouse=True)
def _cleanup():
    shutil.rmtree(_BASE, ignore_errors=True)
    yield
    shutil.rmtree(_BASE, ignore_errors=True)


# ─── Basic write/read ────────────────────────────────────────────────────────

def test_record_and_read_single():
    assert record_adjustment(_TEST_PID, "SPCX", "stop_loss", 125.55, 164.75, "manual")
    rows = read_adjustments(_TEST_PID)
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "SPCX"
    assert r["field"] == "stop_loss"
    assert r["old"] == 125.55
    assert r["new"] == 164.75
    assert r["source"] == "manual"


def test_invalid_field_rejected():
    assert not record_adjustment(_TEST_PID, "X", "weird_field", 1.0, 2.0, "manual")
    assert read_adjustments(_TEST_PID) == []


def test_no_op_change_skipped():
    """Old == new should not log (avoids noise from save-without-change)."""
    assert not record_adjustment(_TEST_PID, "X", "stop_loss", 100.0, 100.0, "trailing")
    assert read_adjustments(_TEST_PID) == []


def test_filter_by_ticker():
    record_adjustment(_TEST_PID, "A", "stop_loss", 10, 20, "manual")
    record_adjustment(_TEST_PID, "B", "stop_loss", 30, 40, "trailing")
    a = read_adjustments(_TEST_PID, ticker="A")
    assert len(a) == 1
    assert a[0]["ticker"] == "A"


def test_trace_id_preserved():
    record_adjustment(_TEST_PID, "X", "take_profit", 100, 200, "trailing", trace_id="trace_abc")
    rows = read_adjustments(_TEST_PID)
    assert rows[0]["trace_id"] == "trace_abc"


# ─── Drift detector ──────────────────────────────────────────────────────────

def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_drift_no_log_on_new_position():
    """A position appearing for the first time should NOT log a manual
    adjustment — the BUY event records initial stops."""
    positions = _df([
        {"ticker": "AAPL", "stop_loss": 90.0, "take_profit": 120.0},
    ])
    n = detect_and_log_drift(_TEST_PID, positions)
    assert n == 0
    assert read_adjustments(_TEST_PID) == []


def test_drift_logs_changes_on_existing_position():
    # First save establishes the shadow (no log on the establishment pass).
    detect_and_log_drift(_TEST_PID, _df([
        {"ticker": "SPCX", "stop_loss": 125.55, "take_profit": 162.0},
    ]))
    # Greg edits the CSV; next save sees deltas.
    n = detect_and_log_drift(_TEST_PID, _df([
        {"ticker": "SPCX", "stop_loss": 164.75, "take_profit": 400.0},
    ]))
    assert n == 2
    rows = read_adjustments(_TEST_PID, ticker="SPCX")
    assert len(rows) == 2
    fields = {r["field"]: r for r in rows}
    assert fields["stop_loss"]["old"] == 125.55
    assert fields["stop_loss"]["new"] == 164.75
    assert fields["stop_loss"]["source"] == "manual"
    assert fields["take_profit"]["new"] == 400.0


def test_drift_no_log_when_unchanged():
    detect_and_log_drift(_TEST_PID, _df([
        {"ticker": "X", "stop_loss": 90.0, "take_profit": 120.0},
    ]))
    n = detect_and_log_drift(_TEST_PID, _df([
        {"ticker": "X", "stop_loss": 90.0, "take_profit": 120.0},
    ]))
    assert n == 0


def test_drift_dedupes_against_recent_pipeline_log():
    """If the pipeline already logged a 'trailing' adjustment to X.stop_loss,
    a subsequent drift detection with the same new value should NOT duplicate."""
    # Establish shadow
    detect_and_log_drift(_TEST_PID, _df([{"ticker": "X", "stop_loss": 100.0, "take_profit": 120.0}]))
    # Pipeline records the change first (e.g. execute_approved_actions)
    record_adjustment(_TEST_PID, "X", "stop_loss", 100.0, 110.0, "trailing")
    # Then save_positions runs; drift detector sees same delta — should skip
    n = detect_and_log_drift(_TEST_PID, _df([{"ticker": "X", "stop_loss": 110.0, "take_profit": 120.0}]))
    assert n == 0
    rows = read_adjustments(_TEST_PID)
    # Only the pipeline-emitted row exists
    assert len(rows) == 1
    assert rows[0]["source"] == "trailing"


def test_drift_does_log_when_pipeline_log_is_old():
    """If the pipeline log is older than the dedup window, drift detector
    should still log (treating it as a separate manual edit)."""
    detect_and_log_drift(_TEST_PID, _df([{"ticker": "X", "stop_loss": 100.0, "take_profit": 120.0}]))
    # Inject an "old" pipeline-emitted log (use ts in the past)
    record_adjustment(_TEST_PID, "X", "stop_loss", 100.0, 110.0, "trailing", ts="2020-01-01T00:00:00")
    # Then drift sees the new value 110 — old log is too old, should log
    n = detect_and_log_drift(_TEST_PID, _df([{"ticker": "X", "stop_loss": 110.0, "take_profit": 120.0}]))
    assert n == 1
    rows = read_adjustments(_TEST_PID, ticker="X")
    sources = sorted(r["source"] for r in rows)
    assert sources == ["manual", "trailing"]


def test_empty_positions_resets_shadow_without_logging():
    detect_and_log_drift(_TEST_PID, _df([{"ticker": "X", "stop_loss": 100.0, "take_profit": 120.0}]))
    n = detect_and_log_drift(_TEST_PID, _df([]))
    assert n == 0
    # Shadow should be empty now; next pop won't spuriously log
    n2 = detect_and_log_drift(_TEST_PID, _df([{"ticker": "X", "stop_loss": 100.0, "take_profit": 120.0}]))
    assert n2 == 0


def test_missing_file_reads_empty():
    assert read_adjustments(_TEST_PID) == []
    assert read_adjustments(_TEST_PID, ticker="X") == []
