import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from watchlist_manager import WatchlistManager


def _make_manager(sector_weights=None, total_slots=100):
    m = object.__new__(WatchlistManager)
    m.sector_weights = sector_weights or {}
    m.total_watchlist_slots = total_slots
    m.max_tickers = 150
    return m


def test_is_bucketed_mode_with_weights():
    m = _make_manager({"Technology": 60, "Healthcare": 40})
    assert m._is_bucketed_mode() is True


def test_is_bucketed_mode_without_weights():
    m = _make_manager()
    assert m._is_bucketed_mode() is False


def test_compute_bucket_sizes_proportional():
    m = _make_manager({"Technology": 60, "Healthcare": 40}, total_slots=100)
    sizes = m._compute_bucket_sizes()
    assert sizes["Technology"] == 60
    assert sizes["Healthcare"] == 40
    assert sum(sizes.values()) == 100


def test_compute_bucket_sizes_rounding_sums_correctly():
    # 3 sectors with odd total — rounding must still sum to total_slots
    m = _make_manager({"Technology": 33, "Healthcare": 33, "Industrials": 34}, total_slots=100)
    sizes = m._compute_bucket_sizes()
    assert sum(sizes.values()) == 100


def test_compute_bucket_sizes_unequal_weights():
    m = _make_manager({"Technology": 75, "Healthcare": 25}, total_slots=200)
    sizes = m._compute_bucket_sizes()
    assert sizes["Technology"] == 150
    assert sizes["Healthcare"] == 50
    assert sum(sizes.values()) == 200
