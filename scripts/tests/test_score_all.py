import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_score_all_method_exists():
    """StockDiscovery must have a _score_all_universe method."""
    from stock_discovery import StockDiscovery
    assert hasattr(StockDiscovery, '_score_all_universe'), "_score_all_universe method is missing"


def test_run_all_scans_routes_to_score_all_for_small_universe():
    """run_all_scans should call _score_all_universe when universe < 500 tickers."""
    from stock_discovery import StockDiscovery

    with patch.object(StockDiscovery, '__init__', lambda self, **kw: None):
        sd = StockDiscovery()
        sd.scan_universe = [f"TICK{i}" for i in range(100)]  # small universe
        sd.discovery_config = {}
        sd._price_cache = {}
        sd._info_cache = {}
        sd._live_prices = {}
        sd.portfolio_id = "test"

        with patch.object(sd, '_score_all_universe', return_value=[]) as mock_score_all, \
             patch.object(sd, '_prewarm_cache'), \
             patch.object(sd, '_prewarm_info_cache'):
            sd.run_all_scans()
            mock_score_all.assert_called_once()


def test_run_all_scans_uses_normal_path_for_large_universe():
    """run_all_scans should NOT call _score_all_universe when universe >= 500 tickers."""
    from stock_discovery import StockDiscovery

    with patch.object(StockDiscovery, '__init__', lambda self, **kw: None):
        sd = StockDiscovery()
        sd.scan_universe = [f"TICK{i}" for i in range(600)]  # large universe
        sd.discovery_config = {}
        sd._price_cache = {}
        sd._info_cache = {}
        sd._live_prices = {}
        sd.portfolio_id = "test"

        with patch.object(sd, '_score_all_universe', return_value=[]) as mock_score_all, \
             patch.object(sd, '_prewarm_cache'), \
             patch.object(sd, '_prewarm_info_cache'), \
             patch.object(sd, '_passes_price_volume_filter', return_value=False):
            sd.run_all_scans()
            mock_score_all.assert_not_called()
