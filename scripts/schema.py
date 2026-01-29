#!/usr/bin/env python3
"""
Centralized schema definitions for Mommy Bot.
All scripts should import from here to ensure consistency.
"""

# ─── Transaction Ledger Schema ────────────────────────────────────────────────
# Unified record of all BUY and SELL transactions
TRANSACTION_COLUMNS = [
    "transaction_id",   # UUID for unique identification
    "date",             # ISO date (YYYY-MM-DD)
    "ticker",           # Stock symbol
    "action",           # BUY or SELL
    "shares",           # Number of shares
    "price",            # Execution price per share
    "total_value",      # shares * price
    "stop_loss",        # Stop loss price (set at entry for buys)
    "take_profit",      # Take profit price (set at entry for buys)
    "reason",           # SIGNAL, STOP_LOSS, TAKE_PROFIT, MANUAL
    # Explainability columns (Phase 4)
    "regime_at_entry",  # BULL/BEAR/SIDEWAYS - market regime when trade was made
    "composite_score",  # Overall score at entry (0-100)
    "factor_scores",    # JSON: {momentum: 65, volatility: 72, ...}
    "signal_rank",      # Rank among candidates (1=top pick)
]

# Columns required for backward compatibility (original transactions without explainability)
TRANSACTION_COLUMNS_BASIC = TRANSACTION_COLUMNS[:10]  # First 10 columns

# ─── Current Positions Schema ─────────────────────────────────────────────────
# Derived from transactions - represents current holdings
POSITION_COLUMNS = [
    "ticker",
    "shares",
    "avg_cost_basis",   # Weighted average purchase price
    "current_price",
    "market_value",     # shares * current_price
    "unrealized_pnl",   # market_value - (shares * avg_cost_basis)
    "unrealized_pnl_pct",
    "stop_loss",        # Current stop loss level
    "take_profit",      # Current take profit level
    "entry_date",       # Date of first purchase
]

# ─── Daily Snapshots Schema ───────────────────────────────────────────────────
# Daily portfolio state for equity curve tracking
DAILY_SNAPSHOT_COLUMNS = [
    "date",
    "cash",
    "positions_value",
    "total_equity",
    "day_pnl",
    "day_pnl_pct",
    "benchmark_value",  # For comparison (e.g., ^RUT)
]

# ─── Legacy Column Mappings ───────────────────────────────────────────────────
# Maps old column names to new standardized names
LEGACY_COLUMN_MAP = {
    "Cash Balance": "cash",
    "Cash": "cash",
    "Total Equity": "total_equity",
    "Equity": "total_equity",
    "Total Value": "market_value",
    "Value": "market_value",
    "Shares Bought": "shares",
    "Buy Price": "price",
    "Cost Basis": "avg_cost_basis",
    "Current Price": "current_price",
    "PnL": "unrealized_pnl",
}

# ─── Action Types ─────────────────────────────────────────────────────────────
class Action:
    BUY = "BUY"
    SELL = "SELL"

# ─── Trade Reasons ────────────────────────────────────────────────────────────
class Reason:
    SIGNAL = "SIGNAL"           # Normal buy/sell from strategy
    STOP_LOSS = "STOP_LOSS"     # Triggered stop loss
    TAKE_PROFIT = "TAKE_PROFIT" # Triggered take profit
    MANUAL = "MANUAL"           # Manual intervention
    MIGRATION = "MIGRATION"     # Imported from legacy data
