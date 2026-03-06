import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from portfolio_registry import UNIVERSE_PRESETS


def test_total_watchlist_slots_in_presets():
    assert UNIVERSE_PRESETS["smallcap"]["total_watchlist_slots"] == 150
    assert UNIVERSE_PRESETS["midcap"]["total_watchlist_slots"] == 180
    assert UNIVERSE_PRESETS["largecap"]["total_watchlist_slots"] == 200
    assert UNIVERSE_PRESETS["allcap"]["total_watchlist_slots"] == 250
    # microcap stays flat — no bucketing, no slot count needed
    assert "total_watchlist_slots" not in UNIVERSE_PRESETS["microcap"]


def test_create_portfolio_accepts_sector_weights():
    """create_portfolio() signature must accept sector_weights param."""
    import inspect
    from portfolio_registry import create_portfolio
    sig = inspect.signature(create_portfolio)
    assert "sector_weights" in sig.parameters
