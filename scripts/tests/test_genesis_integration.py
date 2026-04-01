#!/usr/bin/env python3
"""Integration test: suggest-config -> create portfolio -> curated universe exists."""
import json
import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_full_genesis_flow(tmp_path):
    """End-to-end: AI returns curated_tickers -> create_portfolio saves them -> universe_provider loads them."""
    ai_result = {
        "name": "Healthcare Growth",
        "universe": "allcap",
        "etfs": ["XLV", "XBI"],
        "stop_loss_pct": 8.0,
        "take_profit_pct": 30.0,
        "risk_per_trade_pct": 10.0,
        "max_position_pct": 15.0,
        "max_positions": 10,
        "reentry_guard": {
            "enabled": True,
            "stop_loss_cooldown_days": 7,
            "lookback_days": 30,
            "meaningful_change_threshold_pts": 10,
        },
        "curated_tickers": [
            {"ticker": "UNH", "sector": "Healthcare", "rationale": "Managed care leader"},
            {"ticker": "ISRG", "sector": "Healthcare", "rationale": "Surgical robotics"},
            {"ticker": "VEEV", "sector": "Technology", "rationale": "Life sciences cloud"},
        ],
    }

    with patch("portfolio_registry.PORTFOLIOS_DIR", tmp_path), \
         patch("portfolio_registry.REGISTRY_FILE", tmp_path / "portfolios.json"), \
         patch("portfolio_registry.load_registry", return_value={"portfolios": {}, "default_portfolio": None}), \
         patch("portfolio_registry.save_registry"):

        from portfolio_registry import create_portfolio
        create_portfolio(
            portfolio_id="health-test",
            name="Healthcare Growth",
            universe="allcap",
            starting_capital=100000,
            ai_config=ai_result,
            ai_driven=True,
            strategy_dna="diversified healthcare",
        )

    curated_path = tmp_path / "health-test" / "curated_universe.json"
    assert curated_path.exists()
    curated = json.loads(curated_path.read_text())
    assert "UNH" in curated["Healthcare"]["tier_1_core"]
    assert "VEEV" in curated["Technology"]["tier_1_core"]
