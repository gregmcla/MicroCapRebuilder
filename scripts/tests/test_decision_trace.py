#!/usr/bin/env python3
"""Tests for decision_trace module — typed step variants, round-trip, index."""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from decision_trace import (
    DecisionTrace,
    RegimeDetectionStep,
    Layer1RiskStep,
    WatchlistScoringStep,
    AiAllocatorPromptStep,
    AiAllocatorCallStep,
    AiAllocatorParseStep,
    AiAllocatorValidateStep,
    ResultAssembleStep,
    ExecuteStep,
    new_trace,
    save_trace,
    load_trace,
    list_recent,
    list_by_ticker,
    find_trace_id_by_proposal,
    STEP_REGISTRY,
)


_TEST_PID = "_test_decision_trace"
_DATA_BASE = Path(__file__).parent.parent.parent / "data" / "portfolios" / _TEST_PID


@pytest.fixture(autouse=True)
def _cleanup_test_portfolio():
    """Remove the test portfolio dir before and after each test."""
    shutil.rmtree(_DATA_BASE, ignore_errors=True)
    yield
    shutil.rmtree(_DATA_BASE, ignore_errors=True)


# ─── Step variants ───────────────────────────────────────────────────────────

def test_all_step_types_registered():
    expected = {
        "regime_detection", "layer1_risk", "watchlist_scoring",
        "ai_allocator_prompt", "ai_allocator_call", "ai_allocator_parse",
        "ai_allocator_validate", "result_assemble", "execute",
    }
    assert set(STEP_REGISTRY.keys()) == expected


def test_base_step_required_fields():
    s = RegimeDetectionStep(
        step_name="regime_detection",
        started_at="2026-06-22T16:00:00",
        duration_ms=12,
        benchmark_symbol="^GSPC",
        regime="BULL",
        sma_50=4800.0,
        sma_200=4500.0,
        position_size_factor=1.0,
        cache_hit=True,
    )
    assert s.step_name == "regime_detection"
    assert s.error is None  # default


# ─── Trace construction ──────────────────────────────────────────────────────

def test_new_trace_generates_unique_id():
    cfg = {"starting_capital": 10000}
    t1 = new_trace(_TEST_PID, "Test", "full", "ai_driven", cfg)
    t2 = new_trace(_TEST_PID, "Test", "full", "ai_driven", cfg)
    assert t1.trace_id != t2.trace_id
    assert t1.trace_id.startswith(_TEST_PID + "_")
    assert t1.portfolio_id == _TEST_PID


def test_config_snapshot_sanitizes_api_key():
    cfg = {
        "starting_capital": 10000,
        "data_provider": {"alpha_vantage_api_key": "SECRET_KEY_XYZ"},
    }
    t = new_trace(_TEST_PID, "Test", "full", "ai_driven", cfg)
    assert t.config_snapshot["data_provider"]["alpha_vantage_api_key"] == "***"
    # Original not mutated
    assert cfg["data_provider"]["alpha_vantage_api_key"] == "SECRET_KEY_XYZ"


# ─── Round-trip ──────────────────────────────────────────────────────────────

def _build_full_trace() -> DecisionTrace:
    t = new_trace(_TEST_PID, "Test", "full", "ai_driven", {"starting_capital": 50000})
    t.add_step(RegimeDetectionStep(
        step_name="regime_detection", started_at="2026-06-22T16:00:00", duration_ms=12,
        benchmark_symbol="^GSPC", regime="BULL", sma_50=4800.0, sma_200=4500.0,
        position_size_factor=1.0, cache_hit=True,
    ))
    t.add_step(Layer1RiskStep(
        step_name="layer1_risk", started_at="2026-06-22T16:00:01", duration_ms=80,
        positions_reviewed=10,
        flagged=[{"ticker": "INTC", "reason": "stop_loss_breached"}],
        not_flagged=["NVDA"],
    ))
    t.add_step(WatchlistScoringStep(
        step_name="watchlist_scoring", started_at="2026-06-22T16:00:02", duration_ms=400,
        total_scored=200, threshold_applied=35.0, top_n_selected=8,
        candidates=[{"ticker": "AVGO", "score": 78.5}, {"ticker": "TSM", "score": 76.2}],
    ))
    t.add_step(AiAllocatorPromptStep(
        step_name="ai_allocator_prompt", started_at="2026-06-22T16:00:03", duration_ms=120,
        blocks_included=["macro", "observations", "factor_scores"],
        prompt_char_count=30000, prompt_text="<<prompt>>",
        candidate_count=8, held_count=10,
    ))
    t.add_step(AiAllocatorCallStep(
        step_name="ai_allocator_call", started_at="2026-06-22T16:00:04", duration_ms=15000,
        model="claude-opus-4-7", response_char_count=4000, response_token_count=850,
        finish_reason="end_turn", raw_response="<<response>>",
    ))
    t.add_step(AiAllocatorParseStep(
        step_name="ai_allocator_parse", started_at="2026-06-22T16:00:19", duration_ms=5,
        cleanup_applied=["stripped_markdown"],
        parsed_buys=[{"ticker": "AVGO", "shares": 50}],
        parsed_sells=[],
        parsed_trims=[],
    ))
    t.add_step(AiAllocatorValidateStep(
        step_name="ai_allocator_validate", started_at="2026-06-22T16:00:19", duration_ms=8,
        validations=[
            {"proposal_id": "abc12345", "ticker": "AVGO", "action_type": "BUY",
             "accepted": True, "modifications": [], "rejection_reason": None},
        ],
    ))
    t.add_step(ResultAssembleStep(
        step_name="result_assemble", started_at="2026-06-22T16:00:19", duration_ms=2,
        mode_filter="full", approved_count=1, modified_count=0, vetoed_count=0,
        micro_position_dropped=[],
    ))
    t.execute_step = ExecuteStep(
        step_name="execute", started_at="2026-06-22T16:05:00", duration_ms=900,
        proposal_ids_processed=["abc12345"],
        transactions_written=[
            {"proposal_id": "abc12345", "transaction_id": "tx0001",
             "ticker": "AVGO", "action": "BUY", "shares": 50, "price": 1500.00},
        ],
        drops=[],
    )
    t.final_summary = {"approved": 1, "modified": 0, "vetoed": 0, "can_execute": True}
    return t


def test_round_trip_preserves_typed_steps():
    t = _build_full_trace()
    save_trace(t)
    t2 = load_trace(_TEST_PID, t.trace_id)
    assert t2.trace_id == t.trace_id
    assert len(t2.steps) == 8
    assert isinstance(t2.steps[0], RegimeDetectionStep)
    assert isinstance(t2.steps[1], Layer1RiskStep)
    assert isinstance(t2.steps[2], WatchlistScoringStep)
    assert isinstance(t2.steps[6], AiAllocatorValidateStep)
    assert t2.steps[6].validations[0]["proposal_id"] == "abc12345"
    assert isinstance(t2.execute_step, ExecuteStep)
    assert t2.execute_step.transactions_written[0]["ticker"] == "AVGO"


def test_finalize_sets_completed_at_and_duration():
    t = new_trace(_TEST_PID, "Test", "full", "ai_driven", {})
    t.add_step(RegimeDetectionStep(
        step_name="regime_detection", started_at="2026-06-22T16:00:00", duration_ms=1,
        benchmark_symbol="^GSPC", regime="BULL", sma_50=0.0, sma_200=0.0,
        position_size_factor=1.0, cache_hit=False,
    ))
    save_trace(t)  # calls finalize internally
    assert t.completed_at != ""
    assert t.duration_ms >= 0


# ─── Index ───────────────────────────────────────────────────────────────────

def test_index_includes_proposal_ids_and_tickers():
    t = _build_full_trace()
    save_trace(t)
    recent = list_recent(_TEST_PID, limit=5)
    assert len(recent) == 1
    line = recent[0]
    assert line["trace_id"] == t.trace_id
    assert "abc12345" in line["proposal_ids"]
    # Tickers gathered from watchlist + validate + flagged + executed
    assert "AVGO" in line["tickers"]
    assert "INTC" in line["tickers"]


def test_list_recent_newest_first():
    t1 = _build_full_trace()
    save_trace(t1)
    t2 = _build_full_trace()
    save_trace(t2)
    recent = list_recent(_TEST_PID, limit=5)
    assert len(recent) == 2
    # Most-recently-saved is first
    assert recent[0]["trace_id"] == t2.trace_id
    assert recent[1]["trace_id"] == t1.trace_id


def test_find_trace_id_by_proposal():
    t = _build_full_trace()
    save_trace(t)
    found = find_trace_id_by_proposal(_TEST_PID, "abc12345")
    assert found == t.trace_id
    missing = find_trace_id_by_proposal(_TEST_PID, "does_not_exist")
    assert missing is None


def test_list_by_ticker():
    t = _build_full_trace()
    save_trace(t)
    avgo = list_by_ticker(_TEST_PID, "AVGO")
    assert len(avgo) == 1
    assert avgo[0]["trace_id"] == t.trace_id
    empty = list_by_ticker(_TEST_PID, "NOSUCHTICKER")
    assert empty == []


# ─── Persistence guarantees ──────────────────────────────────────────────────

def test_atomic_write_replaces_file():
    t = _build_full_trace()
    p = save_trace(t)
    # No leftover .tmp
    assert not p.with_suffix(".json.tmp").exists()
    # File exists with valid JSON
    with p.open() as f:
        data = json.load(f)
    assert data["trace_id"] == t.trace_id


def test_missing_index_file_returns_empty():
    # No saves at all → no index file → empty lists
    assert list_recent(_TEST_PID) == []
    assert list_by_ticker(_TEST_PID, "NVDA") == []
    assert find_trace_id_by_proposal(_TEST_PID, "anything") is None
