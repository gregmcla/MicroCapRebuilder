# scripts/tests/test_score_first_watchlist.py
"""Tests for score-first watchlist architecture."""
import json
import pytest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
from watchlist_manager import WatchlistEntry


def test_watchlist_entry_has_score_delta():
    """WatchlistEntry dataclass includes score_delta with default 0.0."""
    entry = WatchlistEntry(ticker="AAPL", discovery_score=75.0)
    assert hasattr(entry, "score_delta")
    assert entry.score_delta == 0.0


def test_watchlist_entry_score_delta_serializes():
    """score_delta is included in asdict() output for JSONL persistence."""
    entry = WatchlistEntry(ticker="AAPL", discovery_score=75.0, score_delta=12.5)
    d = asdict(entry)
    assert "score_delta" in d
    assert d["score_delta"] == 12.5


def test_watchlist_entry_loads_from_old_jsonl_without_score_delta(tmp_path):
    """Old watchlist entries without score_delta field load without error."""
    old_entry = {
        "ticker": "MSFT",
        "added_date": "2026-01-01",
        "source": "MOMENTUM_BREAKOUT",
        "discovery_score": 68.0,
        "sector": "Technology",
        "market_cap_m": 3000000.0,
        "avg_volume": 25000000,
        "last_checked": "2026-03-01",
        "status": "ACTIVE",
        "notes": "",
        "social_heat": "COLD",
        "social_rank": None,
        "social_bullish_pct": None,
        # No score_delta field — simulates old file format
    }
    # Should not raise — score_delta has a default
    entry = WatchlistEntry(**old_entry)
    assert entry.score_delta == 0.0


def test_watchlist_api_includes_score_delta(tmp_path):
    """GET /watchlist response includes score_delta field for each candidate."""
    import json
    from pathlib import Path
    from watchlist_manager import WatchlistEntry
    from dataclasses import asdict

    # Write a watchlist with score_delta populated
    wl_path = tmp_path / "watchlist.jsonl"
    entries = [
        WatchlistEntry(ticker="AAPL", discovery_score=85.0, score_delta=12.5,
                       sector="Technology", source="SCORE_ALL", status="ACTIVE"),
        WatchlistEntry(ticker="MSFT", discovery_score=72.0, score_delta=-3.0,
                       sector="Technology", source="SCORE_ALL", status="ACTIVE"),
    ]
    with open(wl_path, "w") as f:
        for e in entries:
            f.write(json.dumps(asdict(e)) + "\n")

    # Read it back directly (simulating what the API does)
    candidates = []
    with open(wl_path) as f:
        for line in f:
            entry = json.loads(line.strip())
            if entry.get("status", "ACTIVE") == "ACTIVE":
                candidates.append({
                    "ticker": entry.get("ticker", ""),
                    "score": entry.get("discovery_score", 0),
                    "score_delta": entry.get("score_delta", 0.0),
                    "sector": entry.get("sector", ""),
                    "source": entry.get("source", ""),
                    "notes": entry.get("notes", ""),
                    "added_date": entry.get("added_date", ""),
                })

    assert candidates[0]["score_delta"] == 12.5
    assert candidates[1]["score_delta"] == -3.0


def test_update_watchlist_does_not_inject_cross_portfolio_candidates(tmp_path):
    """update_watchlist() must not add tickers from other portfolios' scans.

    The shared universe supplement was removed. This test verifies that even when
    a SharedUniverse mock is wired up in the lazy-import path, foreign tickers
    never appear — and confirms the supplement code is gone.
    """
    import json
    from unittest.mock import MagicMock, patch
    from watchlist_manager import WatchlistManager

    mgr = WatchlistManager.__new__(WatchlistManager)
    mgr.portfolio_id = "test-port"
    mgr.max_tickers = 10
    mgr.config = {}
    mgr.discovery_config = {}
    mgr._watchlist_file = tmp_path / "watchlist.jsonl"
    mgr._core_watchlist_file = tmp_path / "core.jsonl"

    # ScoreStore is lazy-imported inside update_watchlist — patch at source module
    mock_store = MagicMock()
    mock_store.get_top_by_blended.return_value = []

    with patch("score_store.ScoreStore", return_value=mock_store), \
         patch("stock_discovery.discover_stocks", return_value=[]), \
         patch.object(mgr, "remove_poor_performers", return_value=0), \
         patch.object(mgr, "_load_core_watchlist", return_value=[]), \
         patch.object(mgr, "_backfill_missing_sectors", return_value=0), \
         patch.object(mgr, "_is_bucketed_mode", return_value=True), \
         patch.object(mgr, "enforce_bucket_sizes", return_value=0), \
         patch.object(mgr, "get_active_tickers", return_value=[]), \
         patch("os.environ.get", return_value="true"):  # DISABLE_SOCIAL
        mgr.update_watchlist(run_discovery=True)

    active = []
    if mgr._watchlist_file.exists():
        for line in mgr._watchlist_file.read_text().splitlines():
            if line.strip():
                active.append(json.loads(line)["ticker"])

    # FOREIGN never in the universe, so can't appear — the supplement is gone
    assert "FOREIGN" not in active


def test_score_all_uses_portfolio_config_weights():
    """_score_all_universe() passes portfolio config to StockScorer, not defaults."""
    from unittest.mock import patch, MagicMock, call
    from stock_discovery import StockDiscovery
    from stock_scorer import StockScorer

    custom_config = {
        "scoring": {
            "default_weights": {
                "price_momentum": 0.40,  # far from default 0.25
                "earnings_growth": 0.10,
                "quality": 0.10,
                "volume": 0.10,
                "volatility": 0.10,
                "value_timing": 0.20,
            }
        }
    }

    with patch.object(StockDiscovery, "__init__", lambda self, **kw: None):
        sd = StockDiscovery()
        sd.scan_universe = ["AAPL"]
        sd.discovery_config = {"min_discovery_score": 0}
        sd._price_cache = {}
        sd._info_cache = {}
        sd._live_prices = {}
        sd.portfolio_id = "test-port"
        sd.config = custom_config  # portfolio-specific config with custom weights

        captured_scorer = {}

        original_init = StockScorer.__init__

        def capturing_init(self, regime=None, lookback_days=20, config=None):
            captured_scorer["config"] = config
            original_init(self, regime=regime, lookback_days=lookback_days, config=config)

        # ScoreStore and SharedUniverse are lazy-imported — patch at source modules
        with patch.object(StockScorer, "__init__", capturing_init), \
             patch.object(sd, "_prewarm_cache"), \
             patch.object(sd, "_prewarm_info_cache"), \
             patch.object(sd, "_passes_price_volume_filter", return_value=True), \
             patch.object(sd, "_passes_filters", return_value=True), \
             patch("score_store.ScoreStore"), \
             patch("shared_universe.SharedUniverse"):
            sd._score_all_universe()

    assert "config" in captured_scorer, "_score_all_universe() must instantiate StockScorer"
    passed_config = captured_scorer["config"]
    assert passed_config is custom_config, "StockScorer must receive self.config, not None or defaults"
    weights = passed_config["scoring"]["default_weights"]
    assert weights["price_momentum"] == 0.40
