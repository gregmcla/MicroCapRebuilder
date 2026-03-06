import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from stock_discovery import StockDiscovery, DiscoveredStock
from datetime import date


def _make_candidate(ticker: str, sector: str, score: float) -> DiscoveredStock:
    return DiscoveredStock(
        ticker=ticker, source="MOMENTUM_BREAKOUT", discovery_score=score,
        sector=sector, market_cap_m=1000.0, avg_volume=500000,
        current_price=50.0, momentum_20d=5.0, rsi_14=55.0,
        volume_ratio=1.5, near_52wk_high_pct=95.0,
        discovered_date=date.today().isoformat(), notes="",
    )


def _make_discovery() -> StockDiscovery:
    d = object.__new__(StockDiscovery)
    return d


def test_select_by_buckets_respects_slot_limits():
    discovery = _make_discovery()
    candidates = [
        _make_candidate("AAPL", "Technology", 90),
        _make_candidate("MSFT", "Technology", 85),
        _make_candidate("GOOG", "Technology", 80),  # should be cut
        _make_candidate("JNJ", "Healthcare", 88),
        _make_candidate("PFE", "Healthcare", 75),
    ]
    result = discovery._select_by_buckets(candidates, {"Technology": 50, "Healthcare": 50}, total_slots=4)
    tickers = {r.ticker for r in result}
    assert "AAPL" in tickers   # top Tech
    assert "MSFT" in tickers   # 2nd Tech
    assert "GOOG" not in tickers  # 3rd Tech, cut
    assert "JNJ" in tickers   # top Healthcare
    assert "PFE" in tickers   # 2nd Healthcare


def test_select_by_buckets_proportional_weighting():
    discovery = _make_discovery()
    candidates = [_make_candidate(f"T{i}", "Technology", 90 - i) for i in range(10)]
    candidates += [_make_candidate(f"H{i}", "Healthcare", 80 - i) for i in range(4)]
    # Tech 75%, Healthcare 25% → 9 Tech slots, 3 Healthcare slots out of 12
    result = discovery._select_by_buckets(
        candidates, {"Technology": 75, "Healthcare": 25}, total_slots=12
    )
    tech_count = sum(1 for r in result if r.sector == "Technology")
    health_count = sum(1 for r in result if r.sector == "Healthcare")
    assert tech_count == 9
    assert health_count == 3


def test_select_by_buckets_leaves_empty_slots_when_sector_sparse():
    discovery = _make_discovery()
    candidates = [
        _make_candidate("AAPL", "Technology", 90),
        # Healthcare has 0 candidates
    ]
    result = discovery._select_by_buckets(
        candidates, {"Technology": 50, "Healthcare": 50}, total_slots=10
    )
    # Only 1 Tech candidate fills 1 slot; Healthcare stays empty
    assert len(result) == 1
    assert result[0].ticker == "AAPL"


def test_select_by_buckets_fuzzy_sector_match():
    """yfinance returns 'Communication Services'; sector_weights key is 'Communication'."""
    discovery = _make_discovery()
    candidates = [_make_candidate("META", "Communication Services", 85)]
    result = discovery._select_by_buckets(
        candidates, {"Communication": 100}, total_slots=5
    )
    assert len(result) == 1
    assert result[0].ticker == "META"
