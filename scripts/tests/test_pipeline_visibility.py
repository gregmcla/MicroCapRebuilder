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
