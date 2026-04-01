import json
import sys
from pathlib import Path
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared_universe import SharedUniverse, SharedScanResult


def test_write_and_read_scan_results(tmp_path):
    """Scan results written by one portfolio can be read by another."""
    cache = SharedUniverse(cache_dir=tmp_path)
    now = datetime.now().isoformat()

    cache.write_results("portfolio-a", [
        SharedScanResult("AAPL", 75.0, "momentum_breakouts", "Technology", "portfolio-a", now, {"price_momentum": 85}),
        SharedScanResult("UNH", 68.0, "sector_leaders", "Healthcare", "portfolio-a", now, {}),
    ])

    results = cache.read_results(max_age_hours=24)
    tickers = {r.ticker for r in results}
    assert "AAPL" in tickers
    assert "UNH" in tickers


def test_stale_results_filtered_by_age(tmp_path):
    """Results older than max_age_hours are excluded."""
    cache = SharedUniverse(cache_dir=tmp_path)
    old_time = (datetime.now() - timedelta(hours=25)).isoformat()

    cache.write_results("portfolio-a", [
        SharedScanResult("OLD", 50.0, "volume_anomalies", "Energy", "portfolio-a", old_time, {}),
    ])

    assert cache.read_results(max_age_hours=24) == []


def test_cross_portfolio_convergence(tmp_path):
    """Tickers found by multiple portfolios are flagged."""
    cache = SharedUniverse(cache_dir=tmp_path)
    now = datetime.now().isoformat()

    cache.write_results("portfolio-a", [
        SharedScanResult("XOM", 70.0, "momentum_breakouts", "Energy", "portfolio-a", now, {}),
    ])
    cache.write_results("portfolio-b", [
        SharedScanResult("XOM", 72.0, "sector_leaders", "Energy", "portfolio-b", now, {}),
    ])

    convergent = cache.get_convergent_tickers(min_portfolios=2)
    assert "XOM" in convergent
    assert convergent["XOM"]["portfolio_count"] >= 2


def test_get_best_score(tmp_path):
    """get_best_score returns highest composite_score for a ticker."""
    cache = SharedUniverse(cache_dir=tmp_path)
    now = datetime.now().isoformat()

    cache.write_results("portfolio-a", [
        SharedScanResult("MSFT", 60.0, "momentum_breakouts", "Technology", "portfolio-a", now, {}),
    ])
    cache.write_results("portfolio-b", [
        SharedScanResult("MSFT", 75.0, "sector_leaders", "Technology", "portfolio-b", now, {}),
    ])

    assert cache.get_best_score("MSFT") >= 75.0
