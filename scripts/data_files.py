#!/usr/bin/env python3
"""
Shared data file path management with paper trading mode support.

All scripts should import from this module to get the correct file paths
based on whether paper trading mode is enabled.

Supports multi-portfolio mode: pass portfolio_id to resolve paths under
data/portfolios/{id}/ instead of data/. When portfolio_id is None (default),
paths resolve to data/ for backward compatibility.
"""

import json
from pathlib import Path
from typing import Optional

# ─── Base Paths ───────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
PORTFOLIOS_DIR = DATA_DIR / "portfolios"
CONFIG_FILE = DATA_DIR / "config.json"


def _resolve_data_dir(portfolio_id: Optional[str] = None) -> Path:
    """Resolve the data directory for a given portfolio, or the global data dir."""
    if portfolio_id is not None:
        return PORTFOLIOS_DIR / portfolio_id
    return DATA_DIR


def load_config(portfolio_id: Optional[str] = None) -> dict:
    """Load configuration from config.json."""
    config_path = _resolve_data_dir(portfolio_id) / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"starting_capital": 50000.0, "mode": "live"}


def save_config(config: dict, portfolio_id: Optional[str] = None) -> None:
    """Save configuration to config.json."""
    config_path = _resolve_data_dir(portfolio_id) / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def is_paper_mode(portfolio_id: Optional[str] = None) -> bool:
    """Check if system is in paper trading mode."""
    config = load_config(portfolio_id)
    return config.get("mode", "live") == "paper"


def set_paper_mode(enabled: bool, portfolio_id: Optional[str] = None) -> None:
    """Enable or disable paper trading mode."""
    config = load_config(portfolio_id)
    config["mode"] = "paper" if enabled else "live"
    save_config(config, portfolio_id)
    mode = "PAPER" if enabled else "LIVE"
    print(f"📝 Trading mode set to: {mode}")


def get_file_suffix(portfolio_id: Optional[str] = None) -> str:
    """Get the file suffix based on current mode."""
    return "_paper" if is_paper_mode(portfolio_id) else ""


# ─── Data File Paths ──────────────────────────────────────────────────────────
def get_positions_file(portfolio_id: Optional[str] = None) -> Path:
    """Get the positions file path for current mode."""
    suffix = get_file_suffix(portfolio_id)
    return _resolve_data_dir(portfolio_id) / f"positions{suffix}.csv"


def get_transactions_file(portfolio_id: Optional[str] = None) -> Path:
    """Get the transactions file path for current mode."""
    suffix = get_file_suffix(portfolio_id)
    return _resolve_data_dir(portfolio_id) / f"transactions{suffix}.csv"


def get_daily_snapshots_file(portfolio_id: Optional[str] = None) -> Path:
    """Get the daily snapshots file path for current mode."""
    suffix = get_file_suffix(portfolio_id)
    return _resolve_data_dir(portfolio_id) / f"daily_snapshots{suffix}.csv"


# Alias for compatibility
get_snapshots_file = get_daily_snapshots_file


def get_config_file(portfolio_id: Optional[str] = None) -> Path:
    """Get the config file path."""
    return _resolve_data_dir(portfolio_id) / "config.json"


def get_watchlist_file(portfolio_id: Optional[str] = None) -> Path:
    """Get the watchlist file path."""
    return _resolve_data_dir(portfolio_id) / "watchlist.jsonl"


def get_all_data_files(portfolio_id: Optional[str] = None) -> dict:
    """Get all data file paths for current mode."""
    suffix = get_file_suffix(portfolio_id)
    data_dir = _resolve_data_dir(portfolio_id)
    return {
        "positions": data_dir / f"positions{suffix}.csv",
        "transactions": data_dir / f"transactions{suffix}.csv",
        "snapshots": data_dir / f"daily_snapshots{suffix}.csv",
    }


# ─── Convenience Properties ───────────────────────────────────────────────────
# These can be imported directly for simpler usage
POSITIONS_FILE = property(lambda self: get_positions_file())
TRANSACTIONS_FILE = property(lambda self: get_transactions_file())
DAILY_SNAPSHOTS_FILE = property(lambda self: get_daily_snapshots_file())


def get_mode_indicator() -> str:
    """Get a string indicator for the current mode (for logging)."""
    if is_paper_mode():
        return "📝 [PAPER]"
    return "💰 [LIVE]"


def print_mode_status() -> None:
    """Print the current trading mode status."""
    mode = "PAPER TRADING" if is_paper_mode() else "LIVE TRADING"
    indicator = "📝" if is_paper_mode() else "💰"
    print(f"\n{indicator} Mode: {mode}")
    print(f"   Positions: {get_positions_file().name}")
    print(f"   Transactions: {get_transactions_file().name}")
    print(f"   Snapshots: {get_daily_snapshots_file().name}")


if __name__ == "__main__":
    # Show current mode status when run directly
    print_mode_status()
