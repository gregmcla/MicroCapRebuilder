#!/usr/bin/env python3
"""
Centralized schema definitions for GScott.
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
    "trade_rationale",  # JSON: {ai_decision, ai_confidence, ai_reasoning, quant_reason, regime, top_factors}
    # Decision Trace linkage (Feature #9)
    "source_proposal_id",  # 8-char hex; matches ProposedAction.proposal_id from the analyze cycle that produced this trade
    "source_trace_id",     # full trace_id (portfolio_yyyymmdd_HHMMSS_xxxx); permits direct trace lookup from a transaction row
    # DNA Genome catalyst-hunting signals (Feature #16); empty on legacy rows until backfilled
    "heat_at_entry",          # social sentiment classification at buy time: COLD/WARM/HOT/SPIKING
    "market_cap_at_entry_m",  # market cap in $M at buy time (for micro/small-cap detection)
]

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
    "day_change",       # Total dollar change today (position-level, not per-share)
    "day_change_pct",   # Percent change today
    "price_high",       # Highest price since entry — used for trailing stops
    "sector",           # GICS sector (backfilled at scan time); on-disk since before this constant
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

# ─── Action Types ─────────────────────────────────────────────────────────────
class Action:
    BUY = "BUY"
    SELL = "SELL"
    TRIM = "TRIM"           # Partial sell (intelligence-driven)
    ADD = "ADD"             # Add to existing position


# ─── Trade Reasons ────────────────────────────────────────────────────────────
class Reason:
    SIGNAL = "SIGNAL"           # Normal buy/sell from strategy
    STOP_LOSS = "STOP_LOSS"     # Triggered stop loss
    TAKE_PROFIT = "TAKE_PROFIT" # Triggered take profit
    MANUAL = "MANUAL"           # Manual intervention
    MIGRATION = "MIGRATION"     # Imported from legacy data
    INTELLIGENCE = "INTELLIGENCE"  # AI portfolio intelligence decision
    TRIM_PROFIT = "TRIM_PROFIT"    # Partial profit taking
    REBALANCE = "REBALANCE"        # Portfolio rebalancing
    LIQUIDITY_DROP = "LIQUIDITY_DROP"  # Volume collapsed vs 3-month avg
    STAGNATION = "STAGNATION"          # Held >45 days with <±5% movement


# ─── AI Model ─────────────────────────────────────────────────────────────────
# Used by ai_allocator + ai_review — money-critical paths only.
# Non-critical paths (screener, reflection, intelligence, narrative) use Sonnet 4.6 directly.
CLAUDE_MODEL = "claude-opus-4-8"

# Default reasoning effort for the money-critical paths (ai_allocator + ai_review).
# Opus 4.x reasons via adaptive thinking + output_config.effort (a level, not a token
# budget): low | medium | high | xhigh | max. Reasoning is ON by default on these two
# paths — buy/sell allocation and the risk-veto review are exactly where a reasoning
# pass catches structured errors (e.g. the +5.6% "stop triggered" hallucination).
# Per-portfolio override via the `ai_effort` config field; set it to "" to disable
# thinking for that portfolio. Dial this one constant down to "medium" to cut
# per-cycle latency/cost across all portfolios at once.
DEFAULT_AI_EFFORT = "high"

# ─── Model Experiment ─────────────────────────────────────────────────────────
# Experiment concluded 2026-05-21. Opus 4.8 adopted as primary 2026-06-29.
MODEL_EXPERIMENT = {
    "baseline_model": "claude-opus-4-6",
    "challenger_model": "claude-opus-4-7",
    "switch_date": "2026-04-23",
    "end_date": "2026-05-21",
}
