#!/usr/bin/env python3
"""
Shared data file path management with paper trading mode support.

All scripts should import from this module to get the correct file paths
based on whether paper trading mode is enabled.
"""

import json
from pathlib import Path

# ─── Base Paths ───────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load configuration from config.json."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"starting_capital": 50000.0, "mode": "live"}


def save_config(config: dict) -> None:
    """Save configuration to config.json."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def is_paper_mode() -> bool:
    """Check if system is in paper trading mode."""
    config = load_config()
    return config.get("mode", "live") == "paper"


def set_paper_mode(enabled: bool) -> None:
    """Enable or disable paper trading mode."""
    config = load_config()
    config["mode"] = "paper" if enabled else "live"
    save_config(config)
    mode = "PAPER" if enabled else "LIVE"
    print(f"📝 Trading mode set to: {mode}")


def get_file_suffix() -> str:
    """Get the file suffix based on current mode."""
    return "_paper" if is_paper_mode() else ""


# ─── Data File Paths ──────────────────────────────────────────────────────────
def get_positions_file() -> Path:
    """Get the positions file path for current mode."""
    suffix = get_file_suffix()
    return DATA_DIR / f"positions{suffix}.csv"


def get_transactions_file() -> Path:
    """Get the transactions file path for current mode."""
    suffix = get_file_suffix()
    return DATA_DIR / f"transactions{suffix}.csv"


def get_daily_snapshots_file() -> Path:
    """Get the daily snapshots file path for current mode."""
    suffix = get_file_suffix()
    return DATA_DIR / f"daily_snapshots{suffix}.csv"


def get_all_data_files() -> dict:
    """Get all data file paths for current mode."""
    suffix = get_file_suffix()
    return {
        "positions": DATA_DIR / f"positions{suffix}.csv",
        "transactions": DATA_DIR / f"transactions{suffix}.csv",
        "snapshots": DATA_DIR / f"daily_snapshots{suffix}.csv",
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
