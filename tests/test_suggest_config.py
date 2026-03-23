"""Tests for suggest_config_for_dna()."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from strategy_generator import suggest_config_for_dna


def _mock_claude_response(content: str):
    """Build a mock Anthropic message response."""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=content)]
    return mock_resp


def test_suggest_config_returns_expected_fields():
    fake_response = json.dumps({
        "name": "Defense Tech Portfolio",
        "universe": "midcap",
        "etfs": ["ITA", "FITE", "ROBO"],
        "stop_loss_pct": 7.0,
        "risk_per_trade_pct": 8.0,
        "max_position_pct": 12.0,
    })
    with patch("strategy_generator.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(fake_response)

        result = suggest_config_for_dna("defense tech thesis", 1_000_000)

    assert result["name"] == "Defense Tech Portfolio"
    assert result["universe"] == "midcap"
    assert result["etfs"] == ["ITA", "FITE", "ROBO"]
    assert result["stop_loss_pct"] == 7.0


def test_suggest_config_falls_back_to_allcap_for_invalid_universe():
    fake_response = json.dumps({
        "name": "Test Portfolio",
        "universe": "mega-cap",
        "etfs": ["SPY"],
        "stop_loss_pct": 7.0,
        "risk_per_trade_pct": 8.0,
        "max_position_pct": 12.0,
    })
    with patch("strategy_generator.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(fake_response)

        result = suggest_config_for_dna("test", 1_000_000)

    assert result["universe"] == "allcap"


def test_suggest_config_handles_markdown_wrapped_json():
    fake_response = '```json\n{"name": "Test", "universe": "allcap", "etfs": ["SPY"], "stop_loss_pct": 7.0, "risk_per_trade_pct": 8.0, "max_position_pct": 12.0}\n```'
    with patch("strategy_generator.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(fake_response)

        result = suggest_config_for_dna("test", 1_000_000)

    assert result["name"] == "Test"


def test_suggest_config_raises_on_missing_api_key():
    with patch("strategy_generator.get_api_key", return_value=None):
        try:
            suggest_config_for_dna("test", 1_000_000)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "API key" in str(e)
