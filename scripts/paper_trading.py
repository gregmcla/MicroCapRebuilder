#!/usr/bin/env python3
"""
Paper Trading Module for GScott.

Provides paper trading functionality to test strategies without real money.
In paper mode:
- All trades are simulated (not executed with real broker)
- Separate data files are used (transactions_paper.csv, etc.)
- All output is clearly marked as [PAPER]
- Simulated slippage and fill delays can be configured

Usage:
    python scripts/paper_trading.py --enable      # Enable paper mode
    python scripts/paper_trading.py --disable     # Switch to live mode
    python scripts/paper_trading.py --status      # Show current mode
    python scripts/paper_trading.py --reset       # Reset paper portfolio
"""

import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# ─── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config():
    """Load configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config):
    """Save configuration."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def is_paper_mode():
    """Check if paper trading is enabled."""
    config = load_config()
    return config.get("paper_trading", {}).get("enabled", False)


def get_data_suffix():
    """Get the suffix for data files in paper mode."""
    config = load_config()
    if config.get("paper_trading", {}).get("enabled", False):
        return config.get("paper_trading", {}).get("paper_data_suffix", "_paper")
    return ""


def get_data_file(base_name: str) -> Path:
    """
    Get the appropriate data file path based on trading mode.

    In paper mode, returns files like 'transactions_paper.csv'
    In live mode, returns files like 'transactions.csv'
    """
    suffix = get_data_suffix()

    # Parse the base name
    if "." in base_name:
        name, ext = base_name.rsplit(".", 1)
        return DATA_DIR / f"{name}{suffix}.{ext}"
    else:
        return DATA_DIR / f"{base_name}{suffix}"


def get_mode_prefix():
    """Get the prefix for log output based on mode."""
    if is_paper_mode():
        return "📝 [PAPER] "
    return ""


def enable_paper_mode():
    """Enable paper trading mode."""
    config = load_config()

    if "paper_trading" not in config:
        config["paper_trading"] = {
            "enabled": False,
            "simulated_fill_delay_pct": 0.1,
            "simulated_slippage_pct": 0.05,
            "paper_data_suffix": "_paper"
        }

    config["paper_trading"]["enabled"] = True
    config["mode"] = "paper"
    save_config(config)

    print("✅ Paper trading mode ENABLED")
    print("")
    print("   All trades will now be simulated.")
    print("   Data will be saved to separate files with '_paper' suffix.")
    print("")
    print("   Paper files:")
    print(f"   - {get_data_file('transactions.csv')}")
    print(f"   - {get_data_file('positions.csv')}")
    print(f"   - {get_data_file('daily_snapshots.csv')}")
    print("")
    print("   Run './run_daily.sh' to start paper trading.")


def disable_paper_mode():
    """Disable paper trading mode (switch to live)."""
    config = load_config()

    if "paper_trading" in config:
        config["paper_trading"]["enabled"] = False

    config["mode"] = "live"
    save_config(config)

    print("✅ Paper trading mode DISABLED")
    print("")
    print("   ⚠️  WARNING: You are now in LIVE mode!")
    print("   All trades will be recorded to production files.")
    print("")
    print("   Make sure this is intentional before running the daily workflow.")


def show_status():
    """Show current trading mode status."""
    config = load_config()
    paper_config = config.get("paper_trading", {})
    is_paper = paper_config.get("enabled", False)

    print("\n─── Trading Mode Status ───\n")

    if is_paper:
        print("   Mode: 📝 PAPER TRADING")
        print("   Status: Simulated trades only")
        print("")
        print("   Settings:")
        print(f"   - Simulated slippage: {paper_config.get('simulated_slippage_pct', 0.05):.2%}")
        print(f"   - Fill delay factor: {paper_config.get('simulated_fill_delay_pct', 0.1):.2%}")
        print("")

        # Check paper files
        paper_transactions = get_data_file("transactions.csv")
        paper_positions = get_data_file("positions.csv")
        paper_snapshots = get_data_file("daily_snapshots.csv")

        print("   Paper data files:")
        print(f"   - Transactions: {'✓ exists' if paper_transactions.exists() else '✗ not created'}")
        print(f"   - Positions: {'✓ exists' if paper_positions.exists() else '✗ not created'}")
        print(f"   - Snapshots: {'✓ exists' if paper_snapshots.exists() else '✗ not created'}")

        # Show paper portfolio summary if available
        if paper_positions.exists():
            import pandas as pd
            try:
                positions_df = pd.read_csv(paper_positions)
                if not positions_df.empty:
                    print("")
                    print(f"   Paper Portfolio:")
                    print(f"   - Positions: {len(positions_df)}")
                    total_value = positions_df["market_value"].sum()
                    print(f"   - Total value: ${total_value:,.2f}")
            except Exception as e:
                print(f"Warning: failed to read paper positions: {e}")
    else:
        print("   Mode: 🔴 LIVE TRADING")
        print("   Status: Real trades will be recorded")
        print("")
        print("   ⚠️  All operations affect production data!")
        print("")
        print("   To switch to paper mode:")
        print("   python scripts/paper_trading.py --enable")

    print("")


def reset_paper_portfolio():
    """Reset the paper trading portfolio to starting capital."""
    config = load_config()

    if not config.get("paper_trading", {}).get("enabled", False):
        print("❌ Paper trading is not enabled")
        print("   Enable it first: python scripts/paper_trading.py --enable")
        return

    # Confirm with user
    print("⚠️  This will DELETE all paper trading data:")
    print(f"   - {get_data_file('transactions.csv')}")
    print(f"   - {get_data_file('positions.csv')}")
    print(f"   - {get_data_file('daily_snapshots.csv')}")
    print("")

    confirm = input("Type 'RESET' to confirm: ")
    if confirm != "RESET":
        print("Cancelled.")
        return

    # Delete paper files
    for filename in ["transactions.csv", "positions.csv", "daily_snapshots.csv",
                     "post_mortems.csv", "factor_performance.csv", "pattern_alerts.csv"]:
        paper_file = get_data_file(filename)
        if paper_file.exists():
            paper_file.unlink()
            print(f"   Deleted: {paper_file.name}")

    print("")
    print("✅ Paper portfolio reset!")
    print(f"   Starting capital: ${config.get('starting_capital', 50000):,.2f}")
    print("   Run './run_daily.sh' to start fresh.")


def simulate_slippage(price: float, is_buy: bool) -> float:
    """
    Simulate price slippage for paper trades.

    Buys execute slightly higher, sells slightly lower.
    """
    config = load_config()
    slippage_pct = config.get("paper_trading", {}).get("simulated_slippage_pct", 0.05) / 100

    if is_buy:
        # Buy at slightly higher price
        return price * (1 + slippage_pct)
    else:
        # Sell at slightly lower price
        return price * (1 - slippage_pct)


def log_paper_trade(action: str, ticker: str, shares: int, price: float, **kwargs):
    """Log a paper trade with clear marking."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = shares * price

    print(f"📝 [PAPER] {action} {shares} {ticker} @ ${price:.2f} = ${total:,.2f}")

    # Additional details
    if kwargs.get("reason"):
        print(f"         Reason: {kwargs['reason']}")
    if kwargs.get("stop_loss"):
        print(f"         Stop: ${kwargs['stop_loss']:.2f} | Target: ${kwargs.get('take_profit', 0):.2f}")


# ─── Data File Path Utilities ────────────────────────────────────────────────
# These are imported by other modules to get the correct file paths

TRANSACTIONS_FILE = property(lambda self: get_data_file("transactions.csv"))
POSITIONS_FILE = property(lambda self: get_data_file("positions.csv"))
DAILY_SNAPSHOTS_FILE = property(lambda self: get_data_file("daily_snapshots.csv"))


def main():
    parser = argparse.ArgumentParser(
        description="Manage paper trading mode for GScott"
    )

    parser.add_argument(
        "--enable", action="store_true",
        help="Enable paper trading mode"
    )
    parser.add_argument(
        "--disable", action="store_true",
        help="Disable paper trading (switch to live)"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show current trading mode"
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Reset paper portfolio to starting capital"
    )

    args = parser.parse_args()

    if args.enable:
        enable_paper_mode()
    elif args.disable:
        disable_paper_mode()
    elif args.reset:
        reset_paper_portfolio()
    else:
        # Default to status
        show_status()


if __name__ == "__main__":
    main()
