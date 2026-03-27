#!/usr/bin/env python3
"""
One-time migration script to convert legacy data files to new schema.

Migrates:
- trade_log.csv -> transactions.csv (with UUIDs, dates, deduplication)
- portfolio.csv + portfolio_update.csv -> positions.csv + daily_snapshots.csv

Run once: python scripts/migrate_data.py
"""

import json
import shutil
import uuid
from datetime import date
from pathlib import Path

import pandas as pd

from schema import (
    TRANSACTION_COLUMNS,
    POSITION_COLUMNS,
    DAILY_SNAPSHOT_COLUMNS,
    Action,
    Reason,
)

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
BACKUP_DIR = Path(__file__).parent.parent / "backup" / "pre-migration"

# Legacy files
LEGACY_TRADE_LOG = DATA_DIR / "trade_log.csv"
LEGACY_PORTFOLIO = DATA_DIR / "portfolio.csv"
LEGACY_PORTFOLIO_UPDATE = DATA_DIR / "portfolio_update.csv"

# New files
TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"
POSITIONS_FILE = DATA_DIR / "positions.csv"
DAILY_SNAPSHOTS_FILE = DATA_DIR / "daily_snapshots.csv"
CONFIG_FILE = DATA_DIR / "config.json"


def backup_legacy_files():
    """Backup all legacy data files before migration."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    for f in [LEGACY_TRADE_LOG, LEGACY_PORTFOLIO, LEGACY_PORTFOLIO_UPDATE]:
        if f.exists():
            dest = BACKUP_DIR / f.name
            shutil.copy2(f, dest)
            print(f"  Backed up {f.name}")

    print(f"✅ Backups saved to {BACKUP_DIR}")


def load_config():
    """Load configuration for starting capital."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"starting_capital": 5000.0}


def migrate_trade_log():
    """
    Convert trade_log.csv to transactions.csv.
    - Add UUIDs
    - Add dates (infer from file or use today)
    - Deduplicate repeated entries
    - Set action=BUY for all (legacy has no sells)
    """
    if not LEGACY_TRADE_LOG.exists():
        print("  No trade_log.csv found, creating empty transactions.csv")
        df = pd.DataFrame(columns=TRANSACTION_COLUMNS)
        df.to_csv(TRANSACTIONS_FILE, index=False)
        return df

    df = pd.read_csv(LEGACY_TRADE_LOG)
    print(f"  Loaded {len(df)} rows from trade_log.csv")

    # Deduplicate - trade_log has 5x repeated entries
    # Group by ticker, shares, price and keep first occurrence
    before_count = len(df)
    df = df.drop_duplicates(subset=["Ticker", "Shares Bought", "Buy Price"], keep="first")
    after_count = len(df)
    if before_count != after_count:
        print(f"  Deduplicated: {before_count} -> {after_count} rows")

    # Build new transactions dataframe
    transactions = []
    today = date.today().isoformat()

    for _, row in df.iterrows():
        ticker = row["Ticker"]
        shares = int(row["Shares Bought"])
        price = float(row["Buy Price"])

        transactions.append({
            "transaction_id": str(uuid.uuid4())[:8],
            "date": today,  # Legacy didn't track dates
            "ticker": ticker,
            "action": Action.BUY,
            "shares": shares,
            "price": round(price, 2),
            "total_value": round(shares * price, 2),
            "stop_loss": "",  # Will be set by risk manager in future
            "take_profit": "",
            "reason": Reason.MIGRATION,
        })

    df_new = pd.DataFrame(transactions, columns=TRANSACTION_COLUMNS)
    df_new.to_csv(TRANSACTIONS_FILE, index=False)
    print(f"✅ Created transactions.csv with {len(df_new)} transactions")
    return df_new


def migrate_positions(transactions_df):
    """
    Build positions.csv from transactions.
    Aggregate all BUY transactions by ticker (no sells in legacy data).
    """
    config = load_config()

    if transactions_df.empty:
        print("  No transactions, creating empty positions.csv")
        df = pd.DataFrame(columns=POSITION_COLUMNS)
        df.to_csv(POSITIONS_FILE, index=False)
        return df, config["starting_capital"]

    # Aggregate by ticker
    positions = []
    total_cost = 0

    grouped = transactions_df.groupby("ticker")
    for ticker, group in grouped:
        total_shares = group["shares"].sum()
        total_value = group["total_value"].sum()
        avg_cost = total_value / total_shares if total_shares > 0 else 0
        entry_date = group["date"].min()

        positions.append({
            "ticker": ticker,
            "shares": int(total_shares),
            "avg_cost_basis": round(avg_cost, 2),
            "current_price": round(avg_cost, 2),  # Will be updated by update_positions.py
            "market_value": round(total_value, 2),
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "stop_loss": "",
            "take_profit": "",
            "entry_date": entry_date,
        })
        total_cost += total_value

    df_pos = pd.DataFrame(positions, columns=POSITION_COLUMNS)
    df_pos.to_csv(POSITIONS_FILE, index=False)

    cash = config["starting_capital"] - total_cost
    print(f"✅ Created positions.csv with {len(df_pos)} positions")
    print(f"   Total invested: ${total_cost:,.2f}, Cash remaining: ${cash:,.2f}")

    return df_pos, cash


def create_initial_snapshot(positions_df, cash):
    """Create initial daily snapshot."""
    today = date.today().isoformat()
    positions_value = positions_df["market_value"].sum() if not positions_df.empty else 0
    total_equity = positions_value + cash

    snapshot = {
        "date": today,
        "cash": round(cash, 2),
        "positions_value": round(positions_value, 2),
        "total_equity": round(total_equity, 2),
        "day_pnl": 0.0,
        "day_pnl_pct": 0.0,
        "benchmark_value": "",
    }

    df = pd.DataFrame([snapshot], columns=DAILY_SNAPSHOT_COLUMNS)
    df.to_csv(DAILY_SNAPSHOTS_FILE, index=False)
    print(f"✅ Created daily_snapshots.csv with initial equity: ${total_equity:,.2f}")


def main():
    print("\n" + "=" * 60)
    print("MicroCapRebuilder Data Migration")
    print("=" * 60 + "\n")

    # Step 1: Backup
    print("Step 1: Backing up legacy files...")
    backup_legacy_files()
    print()

    # Step 2: Migrate trade log to transactions
    print("Step 2: Migrating trade_log.csv -> transactions.csv...")
    transactions_df = migrate_trade_log()
    print()

    # Step 3: Build positions from transactions
    print("Step 3: Building positions.csv from transactions...")
    positions_df, cash = migrate_positions(transactions_df)
    print()

    # Step 4: Create initial daily snapshot
    print("Step 4: Creating initial daily snapshot...")
    create_initial_snapshot(positions_df, cash)
    print()

    print("=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print("\nNew data files created:")
    print(f"  - {TRANSACTIONS_FILE}")
    print(f"  - {POSITIONS_FILE}")
    print(f"  - {DAILY_SNAPSHOTS_FILE}")
    print(f"\nLegacy files backed up to: {BACKUP_DIR}")
    print("\n⚠️  Run 'scripts/update_positions.py' to fetch current prices.")


if __name__ == "__main__":
    main()
