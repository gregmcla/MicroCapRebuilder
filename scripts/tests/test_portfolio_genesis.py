import json
import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_create_portfolio_saves_curated_tickers(tmp_path):
    """When ai_config includes curated_tickers, they're saved to portfolio dir."""
    # Write a base config.json that create_portfolio clones
    base_config = Path(__file__).parent.parent.parent / "data" / "config.json"

    with patch("portfolio_registry.PORTFOLIOS_DIR", tmp_path), \
         patch("portfolio_registry.REGISTRY_FILE", tmp_path / "portfolios.json"), \
         patch("portfolio_registry.load_registry", return_value={"portfolios": {}, "default_portfolio": None}), \
         patch("portfolio_registry.save_registry"):

        from portfolio_registry import create_portfolio

        ai_config = {
            "stop_loss_pct": 8.0,
            "risk_per_trade_pct": 10.0,
            "max_position_pct": 15.0,
            "curated_tickers": [
                {"ticker": "UNH", "sector": "Healthcare", "rationale": "Managed care leader"},
                {"ticker": "ISRG", "sector": "Healthcare", "rationale": "Surgical robotics"},
                {"ticker": "VEEV", "sector": "Technology", "rationale": "Life sciences cloud"},
            ]
        }

        create_portfolio(
            portfolio_id="test-health",
            name="Test Healthcare",
            universe="allcap",
            starting_capital=100000,
            ai_config=ai_config,
            ai_driven=True,
            strategy_dna="diversified healthcare",
        )

    curated_path = tmp_path / "test-health" / "curated_universe.json"
    assert curated_path.exists(), "curated_universe.json was not created"
    curated = json.loads(curated_path.read_text())
    assert "Healthcare" in curated
    assert "UNH" in curated["Healthcare"]["tier_1_core"]
    assert "ISRG" in curated["Healthcare"]["tier_1_core"]
    assert "Technology" in curated
    assert "VEEV" in curated["Technology"]["tier_1_core"]


def test_create_portfolio_without_curated_tickers(tmp_path):
    """create_portfolio without curated_tickers does not create curated file."""
    with patch("portfolio_registry.PORTFOLIOS_DIR", tmp_path), \
         patch("portfolio_registry.REGISTRY_FILE", tmp_path / "portfolios.json"), \
         patch("portfolio_registry.load_registry", return_value={"portfolios": {}, "default_portfolio": None}), \
         patch("portfolio_registry.save_registry"):

        from portfolio_registry import create_portfolio

        create_portfolio(
            portfolio_id="test-plain",
            name="Test Plain",
            universe="allcap",
            starting_capital=100000,
        )

    curated_path = tmp_path / "test-plain" / "curated_universe.json"
    assert not curated_path.exists(), "curated_universe.json should NOT be created without curated_tickers"
