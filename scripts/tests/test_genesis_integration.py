#!/usr/bin/env python3
"""Integration test: POST /api/portfolios with curated_tickers flows to curated_universe.json."""
import json
import sys
from pathlib import Path
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure project root is on sys.path so `api` and `scripts` packages resolve
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # project root
sys.path.insert(0, str(Path(__file__).parent.parent))         # scripts/


def test_create_portfolio_api_saves_curated_universe(tmp_path):
    """POST /api/portfolios with ai_config.curated_tickers writes curated_universe.json."""
    from api.main import app

    with patch("portfolio_registry.PORTFOLIOS_DIR", tmp_path), \
         patch("portfolio_registry.REGISTRY_FILE", tmp_path / "portfolios.json"), \
         patch("portfolio_registry.load_registry", return_value={"portfolios": {}, "default_portfolio": None}), \
         patch("portfolio_registry.save_registry"), \
         patch("api.routes.portfolios._trigger_scan"):  # avoid background yfinance/watchlist calls

        client = TestClient(app)
        payload = {
            "id": "test-health-api",
            "name": "Healthcare Growth",
            "universe": "allcap",
            "starting_capital": 100000,
            "ai_driven": True,
            "strategy_dna": "diversified healthcare",
            "ai_config": {
                "stop_loss_pct": 8.0,
                "risk_per_trade_pct": 10.0,
                "max_position_pct": 15.0,
                "curated_tickers": [
                    {"ticker": "UNH", "sector": "Healthcare", "rationale": "Managed care"},
                    {"ticker": "ISRG", "sector": "Healthcare", "rationale": "Surgical robotics"},
                    {"ticker": "VEEV", "sector": "Technology", "rationale": "Life sciences cloud"},
                ],
            },
        }

        response = client.post("/api/portfolios", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    curated_path = tmp_path / "test-health-api" / "curated_universe.json"
    assert curated_path.exists(), "curated_universe.json was not created"
    curated = json.loads(curated_path.read_text())

    assert "UNH" in curated["Healthcare"]["tier_1_core"]
    assert "ISRG" in curated["Healthcare"]["tier_1_core"]
    assert "VEEV" in curated["Technology"]["tier_1_core"]
