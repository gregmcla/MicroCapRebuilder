#!/usr/bin/env python3
"""
Portfolio Intelligence Engine

The autonomous brain of Mommy. Analyzes the portfolio holistically
and generates actionable decisions with reasoning.

This module:
1. Loads current portfolio state
2. Fetches market conditions
3. Analyzes correlations, concentrations, exposures
4. Reviews what's working vs what's not
5. Considers cash position vs opportunity set
6. Generates recommendations with reasoning
7. Executes through safety rails
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd
import numpy as np

# Load environment
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
except ImportError:
    pass

from data_files import (
    get_positions_file, get_transactions_file, get_snapshots_file,
    get_config_file, get_watchlist_file, is_paper_mode
)

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
LOGS_DIR = SCRIPT_DIR.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# ─── Safety Rails Configuration ───────────────────────────────────────────────
SAFETY_RAILS = {
    "max_position_pct": 20.0,       # No single position > 20% of portfolio
    "min_cash_pct": 10.0,           # Always keep 10% cash
    "max_daily_sells": 3,           # Max 3 sell actions per day
    "max_daily_buys": 2,            # Max 2 buy actions per day
    "max_daily_turnover_pct": 30.0, # Max 30% of portfolio traded per day
    "max_sector_pct": 40.0,         # No sector > 40% of portfolio
    "max_correlation": 0.85,        # No two positions correlated > 0.85
    "daily_loss_halt_pct": 5.0,     # Stop trading if down 5% in a day
}

# ─── Action Types ─────────────────────────────────────────────────────────────
class ActionType:
    BUY = "BUY"
    SELL = "SELL"
    TRIM = "TRIM"           # Partial sell
    ADD = "ADD"             # Add to existing position
    ADJUST_STOP = "ADJUST_STOP"
    ADJUST_TARGET = "ADJUST_TARGET"
    HOLD = "HOLD"           # Explicit decision to do nothing


def load_config() -> dict:
    """Load configuration."""
    config_file = get_config_file()
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    return {"starting_capital": 50000.0}


def load_positions() -> pd.DataFrame:
    """Load current positions."""
    pos_file = get_positions_file()
    if not pos_file.exists():
        return pd.DataFrame()
    return pd.read_csv(pos_file)


def load_transactions() -> pd.DataFrame:
    """Load transaction history."""
    tx_file = get_transactions_file()
    if not tx_file.exists():
        return pd.DataFrame()
    return pd.read_csv(tx_file)


def load_snapshots() -> pd.DataFrame:
    """Load daily snapshots."""
    snap_file = get_snapshots_file()
    if not snap_file.exists():
        return pd.DataFrame()
    return pd.read_csv(snap_file)


def load_watchlist() -> pd.DataFrame:
    """Load watchlist."""
    wl_file = get_watchlist_file()
    if not wl_file.exists():
        return pd.DataFrame()

    records = []
    with open(wl_file) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return pd.DataFrame(records)


def calculate_cash(config: dict, transactions: pd.DataFrame) -> float:
    """Calculate current cash from transactions."""
    starting = config.get("starting_capital", 50000.0)
    if transactions.empty:
        return starting

    cash = starting
    for _, tx in transactions.iterrows():
        if tx["action"] == "BUY":
            cash -= tx["total_value"]
        elif tx["action"] == "SELL":
            cash += tx["total_value"]
    return cash


def get_market_regime() -> dict:
    """Get current market regime and conditions."""
    try:
        from market_regime import get_regime_analysis
        regime = get_regime_analysis()
        return {
            "regime": regime.get("regime", "UNKNOWN"),
            "position_multiplier": regime.get("position_multiplier", 0.5),
            "spy_above_50d": regime.get("above_50d_sma", False),
            "spy_above_200d": regime.get("above_200d_sma", False),
        }
    except Exception as e:
        return {"regime": "UNKNOWN", "error": str(e)}


def get_correlation_matrix(positions: pd.DataFrame, days: int = 60) -> Optional[pd.DataFrame]:
    """Calculate correlation matrix for current positions."""
    if positions.empty or len(positions) < 2:
        return None

    try:
        import yfinance as yf
        tickers = positions["ticker"].tolist()
        end = datetime.now()
        start = end - timedelta(days=days)

        data = yf.download(tickers, start=start, end=end, progress=False)["Close"]
        if data.empty:
            return None

        returns = data.pct_change().dropna()
        return returns.corr()
    except Exception:
        return None


def get_sector_exposure(positions: pd.DataFrame) -> dict:
    """Get sector exposure from positions."""
    # For now, return placeholder - could integrate with yfinance sector data
    return {"Unknown": 100.0}


def analyze_recent_performance(transactions: pd.DataFrame, days: int = 30) -> dict:
    """Analyze recent trading performance."""
    if transactions.empty:
        return {"trades": 0}

    # Filter to recent sells (completed trades)
    recent = transactions[transactions["action"] == "SELL"].copy()
    if "date" in recent.columns:
        recent["date"] = pd.to_datetime(recent["date"])
        cutoff = datetime.now() - timedelta(days=days)
        recent = recent[recent["date"] >= cutoff]

    if recent.empty:
        return {"trades": 0}

    # Calculate basic stats
    wins = recent[recent.get("realized_pnl", 0) > 0] if "realized_pnl" in recent.columns else pd.DataFrame()
    losses = recent[recent.get("realized_pnl", 0) < 0] if "realized_pnl" in recent.columns else pd.DataFrame()

    return {
        "trades": len(recent),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(recent) if len(recent) > 0 else 0,
    }


def build_portfolio_context(
    positions: pd.DataFrame,
    transactions: pd.DataFrame,
    snapshots: pd.DataFrame,
    watchlist: pd.DataFrame,
    config: dict,
) -> dict:
    """Build comprehensive portfolio context for AI analysis."""

    cash = calculate_cash(config, transactions)
    positions_value = positions["market_value"].sum() if not positions.empty and "market_value" in positions.columns else 0
    total_equity = cash + positions_value

    # Position details
    position_details = []
    if not positions.empty:
        for _, pos in positions.iterrows():
            position_details.append({
                "ticker": pos.get("ticker", ""),
                "shares": pos.get("shares", 0),
                "avg_cost": pos.get("avg_cost_basis", 0),
                "current_price": pos.get("current_price", 0),
                "market_value": pos.get("market_value", 0),
                "unrealized_pnl": pos.get("unrealized_pnl", 0),
                "unrealized_pnl_pct": pos.get("unrealized_pnl_pct", 0),
                "stop_loss": pos.get("stop_loss", 0),
                "take_profit": pos.get("take_profit", 0),
                "pct_of_portfolio": (pos.get("market_value", 0) / total_equity * 100) if total_equity > 0 else 0,
            })

    # Recent transactions
    recent_tx = []
    if not transactions.empty:
        recent = transactions.tail(10)
        for _, tx in recent.iterrows():
            recent_tx.append({
                "date": str(tx.get("date", "")),
                "ticker": tx.get("ticker", ""),
                "action": tx.get("action", ""),
                "shares": tx.get("shares", 0),
                "price": tx.get("price", 0),
                "reason": tx.get("reason", ""),
            })

    # Performance
    performance = analyze_recent_performance(transactions)

    # Market conditions
    market = get_market_regime()

    # Top watchlist candidates (if scored)
    watchlist_candidates = []
    if not watchlist.empty and "score" in watchlist.columns:
        top = watchlist.nlargest(5, "score")
        for _, w in top.iterrows():
            watchlist_candidates.append({
                "ticker": w.get("ticker", ""),
                "score": w.get("score", 0),
            })
    elif not watchlist.empty:
        # Just list tickers
        watchlist_candidates = [{"ticker": t} for t in watchlist["ticker"].head(10).tolist()]

    return {
        "timestamp": datetime.now().isoformat(),
        "mode": "PAPER" if is_paper_mode() else "LIVE",
        "portfolio": {
            "total_equity": round(total_equity, 2),
            "cash": round(cash, 2),
            "cash_pct": round(cash / total_equity * 100, 2) if total_equity > 0 else 100,
            "positions_value": round(positions_value, 2),
            "num_positions": len(positions),
            "positions": position_details,
        },
        "market": market,
        "performance": performance,
        "watchlist_candidates": watchlist_candidates,
        "config": {
            "max_positions": config.get("max_positions", 15),
            "risk_per_trade_pct": config.get("risk_per_trade_pct", 10),
            "default_stop_loss_pct": config.get("default_stop_loss_pct", 8),
            "default_take_profit_pct": config.get("default_take_profit_pct", 20),
        },
        "safety_rails": SAFETY_RAILS,
    }


def get_ai_recommendations(context: dict) -> list[dict]:
    """Send portfolio context to Claude and get recommendations."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return [{"error": "No ANTHROPIC_API_KEY configured"}]

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        return [{"error": "anthropic package not installed"}]

    system_prompt = """You are Mommy, an autonomous portfolio intelligence system for microcap stocks.

Your job is to analyze the portfolio holistically and generate specific, actionable recommendations.

You have these action types available:
- BUY: Open a new position (specify ticker and dollar amount)
- SELL: Close an entire position (specify ticker)
- TRIM: Reduce a position by a percentage (specify ticker and percent to sell)
- ADD: Increase an existing position (specify ticker and dollar amount)
- ADJUST_STOP: Move stop loss (specify ticker and new stop price)
- ADJUST_TARGET: Move take profit (specify ticker and new target price)
- HOLD: Explicit decision to make no changes (with reasoning)

Rules:
1. Be decisive but prudent - this is real money
2. Always provide clear reasoning for each action
3. Consider correlations and concentration risk
4. Respect the safety rails provided
5. In BEAR markets, be defensive (trim winners, raise stops, hold cash)
6. In BULL markets, be opportunistic (deploy cash, let winners run)
7. Take partial profits on big winners (>25% gain)
8. Cut losers before they hit stop loss if thesis is broken
9. Don't overtrade - only recommend actions with clear edge

Respond with a JSON array of actions. Each action should have:
- action: The action type
- ticker: The stock symbol
- amount: Dollar amount (for BUY/ADD) OR
- percent: Percentage (for TRIM) OR
- price: New price level (for ADJUST_STOP/ADJUST_TARGET)
- reason: Clear explanation of why

Example response:
```json
[
  {"action": "TRIM", "ticker": "CRDO", "percent": 50, "reason": "Position is 22% of portfolio at +35% gain. Taking partial profits to reduce concentration."},
  {"action": "ADJUST_STOP", "ticker": "ACME", "price": 45.50, "reason": "Stock up 18%, raising stop to protect gains."},
  {"action": "HOLD", "ticker": null, "reason": "Market regime uncertain, maintaining current positions."}
]
```

If no actions are warranted, return a single HOLD action with reasoning."""

    user_prompt = f"""Analyze this portfolio and provide your recommendations:

```json
{json.dumps(context, indent=2)}
```

What actions should we take today? Respond with a JSON array of actions."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        # Parse response
        content = response.content[0].text

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        actions = json.loads(content.strip())
        return actions

    except json.JSONDecodeError as e:
        return [{"error": f"Failed to parse AI response: {e}", "raw": content}]
    except Exception as e:
        return [{"error": f"AI request failed: {e}"}]


def apply_safety_rails(actions: list[dict], context: dict) -> list[dict]:
    """Filter actions through safety rails."""

    filtered = []
    buy_count = 0
    sell_count = 0
    turnover = 0
    total_equity = context["portfolio"]["total_equity"]

    for action in actions:
        if "error" in action:
            filtered.append(action)
            continue

        action_type = action.get("action", "")
        ticker = action.get("ticker")
        blocked = False
        block_reason = ""

        # Count buys/sells
        if action_type == "BUY":
            buy_count += 1
            if buy_count > SAFETY_RAILS["max_daily_buys"]:
                blocked = True
                block_reason = f"Exceeded max daily buys ({SAFETY_RAILS['max_daily_buys']})"

        if action_type in ["SELL", "TRIM"]:
            sell_count += 1
            if sell_count > SAFETY_RAILS["max_daily_sells"]:
                blocked = True
                block_reason = f"Exceeded max daily sells ({SAFETY_RAILS['max_daily_sells']})"

        # Check position size for buys/adds
        if action_type in ["BUY", "ADD"] and not blocked:
            amount = action.get("amount", 0)
            # Find existing position value
            existing = 0
            for pos in context["portfolio"]["positions"]:
                if pos["ticker"] == ticker:
                    existing = pos["market_value"]
                    break

            new_value = existing + amount
            new_pct = (new_value / total_equity * 100) if total_equity > 0 else 0

            if new_pct > SAFETY_RAILS["max_position_pct"]:
                blocked = True
                block_reason = f"Would exceed max position size ({SAFETY_RAILS['max_position_pct']}%)"

        # Check min cash for buys
        if action_type in ["BUY", "ADD"] and not blocked:
            amount = action.get("amount", 0)
            new_cash = context["portfolio"]["cash"] - amount
            new_cash_pct = (new_cash / total_equity * 100) if total_equity > 0 else 0

            if new_cash_pct < SAFETY_RAILS["min_cash_pct"]:
                blocked = True
                block_reason = f"Would breach min cash reserve ({SAFETY_RAILS['min_cash_pct']}%)"

        # Add safety check result to action
        action["safety_check"] = "BLOCKED" if blocked else "PASSED"
        if blocked:
            action["block_reason"] = block_reason

        filtered.append(action)

    return filtered


def log_decision(context: dict, actions: list[dict]):
    """Log the AI decision with full context."""

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOGS_DIR / f"intelligence_{timestamp}.json"

    log_entry = {
        "timestamp": timestamp,
        "context_summary": {
            "total_equity": context["portfolio"]["total_equity"],
            "cash": context["portfolio"]["cash"],
            "num_positions": context["portfolio"]["num_positions"],
            "market_regime": context["market"].get("regime", "UNKNOWN"),
        },
        "actions": actions,
    }

    with open(log_file, "w") as f:
        json.dump(log_entry, f, indent=2)

    # Also append to daily log
    daily_log = LOGS_DIR / f"intelligence_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with open(daily_log, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    return log_file


def run_intelligence() -> dict:
    """Main entry point: analyze portfolio and generate recommendations."""

    print("🧠 Mommy is thinking...")
    print()

    # Load all data
    config = load_config()
    positions = load_positions()
    transactions = load_transactions()
    snapshots = load_snapshots()
    watchlist = load_watchlist()

    # Build context
    print("📊 Loading portfolio state...")
    context = build_portfolio_context(positions, transactions, snapshots, watchlist, config)

    print(f"   Equity: ${context['portfolio']['total_equity']:,.2f}")
    print(f"   Cash: ${context['portfolio']['cash']:,.2f} ({context['portfolio']['cash_pct']:.1f}%)")
    print(f"   Positions: {context['portfolio']['num_positions']}")
    print(f"   Market Regime: {context['market'].get('regime', 'UNKNOWN')}")
    print()

    # Get AI recommendations
    print("🤖 Analyzing and generating recommendations...")
    actions = get_ai_recommendations(context)

    # Apply safety rails
    print("🛡️  Applying safety rails...")
    actions = apply_safety_rails(actions, context)

    # Log decision
    log_file = log_decision(context, actions)
    print(f"📝 Decision logged to {log_file.name}")
    print()

    # Display recommendations
    print("=" * 60)
    print("📋 RECOMMENDATIONS")
    print("=" * 60)

    for action in actions:
        if "error" in action:
            print(f"❌ Error: {action['error']}")
            continue

        status = "✓" if action.get("safety_check") == "PASSED" else "✗ BLOCKED"
        action_type = action.get("action", "?")
        ticker = action.get("ticker", "-")
        reason = action.get("reason", "")

        if action_type == "HOLD":
            print(f"{status} HOLD: {reason}")
        elif action_type == "TRIM":
            pct = action.get("percent", 0)
            print(f"{status} TRIM {ticker} by {pct}%: {reason}")
        elif action_type in ["BUY", "ADD"]:
            amt = action.get("amount", 0)
            print(f"{status} {action_type} ${amt:,.0f} of {ticker}: {reason}")
        elif action_type == "SELL":
            print(f"{status} SELL {ticker}: {reason}")
        elif action_type in ["ADJUST_STOP", "ADJUST_TARGET"]:
            price = action.get("price", 0)
            print(f"{status} {action_type} {ticker} to ${price:.2f}: {reason}")

        if action.get("safety_check") == "BLOCKED":
            print(f"   ⚠️  {action.get('block_reason', 'Unknown reason')}")

        print()

    return {
        "context": context,
        "actions": actions,
        "log_file": str(log_file),
    }


if __name__ == "__main__":
    result = run_intelligence()
