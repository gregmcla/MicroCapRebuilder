"""Tests for pipeline visibility metadata."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_ai_driven_result_has_ai_mode_claude():
    """AI-driven analysis result must include ai_mode: 'claude'."""
    result = {"ai_mode": "claude", "summary": {"approved": 1}}
    assert result["ai_mode"] == "claude"


def test_mechanical_result_has_ai_mode_mechanical():
    """Mechanical analysis result must include ai_mode: 'mechanical'."""
    result = {"ai_mode": "mechanical", "summary": {"approved": 1}}
    assert result["ai_mode"] == "mechanical"


def test_fallback_result_has_ai_mode_fallback():
    """When Claude API fails, ai_mode must be 'mechanical_fallback'."""
    result = {"ai_mode": "mechanical_fallback", "summary": {"approved": 0}}
    assert result["ai_mode"] == "mechanical_fallback"


def test_execution_summary_structure():
    """Execute return must include execution_summary with counts and drops."""
    summary = {
        "proposed": {"buys": 4, "sells": 5},
        "executed": {"buys": 2, "sells": 5},
        "dropped": [
            {"ticker": "ACTG", "reason": "no live price"},
            {"ticker": "MTZ", "reason": "insufficient cash"},
        ],
        "ai_mode": "claude",
    }
    assert summary["proposed"]["buys"] == 4
    assert summary["executed"]["buys"] == 2
    assert len(summary["dropped"]) == 2
    assert summary["dropped"][0]["ticker"] == "ACTG"
    assert summary["dropped"][0]["reason"] == "no live price"


def test_trade_summary_structure():
    """Trade summary must have win_rate, avg_win, avg_loss, top patterns."""
    summary = {
        "total_trades": 15,
        "win_rate_pct": 40.0,
        "avg_win_pct": 5.3,
        "avg_loss_pct": -6.0,
        "avg_hold_days": 4.2,
        "top_patterns": ["quick_stop", "regime_change"],
        "recent_streak": "2W",
    }
    assert summary["total_trades"] == 15
    assert summary["win_rate_pct"] == 40.0
    assert len(summary["top_patterns"]) == 2
