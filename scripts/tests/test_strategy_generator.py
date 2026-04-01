import json
import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# Ensure scripts dir is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy_generator import suggest_config_for_dna


def test_suggest_config_returns_curated_tickers():
    """AI config suggestion should include curated_tickers list."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "name": "Healthcare Growth",
        "universe": "allcap",
        "etfs": ["XLV", "XBI"],
        "stop_loss_pct": 8.0,
        "take_profit_pct": 30.0,
        "risk_per_trade_pct": 10.0,
        "max_position_pct": 15.0,
        "max_positions": 10,
        "reentry_guard": {"stop_loss_cooldown_days": 7, "lookback_days": 30, "meaningful_change_threshold_pts": 10},
        "curated_tickers": [
            {"ticker": "UNH", "sector": "Healthcare", "rationale": "Largest managed care"},
            {"ticker": "ISRG", "sector": "Healthcare", "rationale": "Surgical robotics leader"},
            {"ticker": "VEEV", "sector": "Healthcare", "rationale": "Cloud software for life sciences"},
        ]
    }))]

    with patch("strategy_generator.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        with patch("strategy_generator.get_api_key", return_value="test-key"):
            result = suggest_config_for_dna("diversified healthcare", 100000)

    assert "curated_tickers" in result
    assert len(result["curated_tickers"]) >= 3
    assert result["curated_tickers"][0]["ticker"] == "UNH"
    assert "sector" in result["curated_tickers"][0]
    assert "rationale" in result["curated_tickers"][0]


def test_suggest_config_works_without_curated_tickers():
    """Backward compat: if AI omits curated_tickers, result has empty list."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "name": "Test",
        "universe": "allcap",
        "etfs": ["SPY"],
        "stop_loss_pct": 7.0,
        "take_profit_pct": 20.0,
        "risk_per_trade_pct": 8.0,
        "max_position_pct": 12.0,
        "max_positions": 10,
    }))]

    with patch("strategy_generator.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        with patch("strategy_generator.get_api_key", return_value="test-key"):
            result = suggest_config_for_dna("generic strategy", 100000)

    assert result["curated_tickers"] == []
