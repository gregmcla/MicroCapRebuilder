#!/usr/bin/env python3
"""
Post-Mortem Analysis Module for GScott.

Learns from every closed trade by:
- Comparing entry rationale with actual outcome
- Identifying what worked and what failed
- Tagging patterns for future reference
- Generating actionable recommendations

Every closed trade gets a "lesson learned."
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from pathlib import Path
from datetime import date, datetime

import pandas as pd

# ─── Paths ───
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"
RATIONALES_FILE = DATA_DIR / "trade_rationales.jsonl"
POST_MORTEMS_FILE = DATA_DIR / "post_mortems.csv"


@dataclass
class PostMortem:
    """Post-mortem analysis for a closed trade."""
    transaction_id: str  # Links to the SELL transaction
    buy_transaction_id: str  # Links to the original BUY
    ticker: str
    close_date: str

    # Outcome
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    exit_reason: str  # STOP_LOSS, TAKE_PROFIT, MANUAL, SIGNAL
    holding_days: int

    # Entry context
    regime_at_entry: str
    regime_at_exit: str
    composite_score_at_entry: float
    signal_rank_at_entry: int

    # Analysis
    summary: str
    what_worked: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    pattern_tags: List[str] = field(default_factory=list)
    recommendation: str = ""


class PostMortemAnalyzer:
    """Analyzes closed trades and generates post-mortems."""

    # Pattern tags
    PATTERNS = {
        "quick_stop": "Stopped out within 3 days",
        "quick_profit": "Hit take profit within 5 days",
        "regime_change": "Regime changed during holding period",
        "momentum_reversal": "High momentum score but lost money",
        "volatility_spike": "High volatility score but got stopped",
        "low_rank_winner": "Ranked #3+ but still profitable",
        "top_pick_loser": "Ranked #1 but lost money",
        "extended_hold": "Held for 30+ days",
    }

    def __init__(self):
        self.transactions_df = self._load_transactions()
        self.rationales = self._load_rationales()

    def _load_transactions(self) -> pd.DataFrame:
        """Load transactions."""
        if not TRANSACTIONS_FILE.exists():
            return pd.DataFrame()
        df = pd.read_csv(TRANSACTIONS_FILE)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def _load_rationales(self) -> Dict[str, dict]:
        """Load trade rationales indexed by transaction_id."""
        rationales = {}
        if not RATIONALES_FILE.exists():
            return rationales

        with open(RATIONALES_FILE, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        rationales[data.get("transaction_id", "")] = data
                    except json.JSONDecodeError:
                        pass
        return rationales

    def analyze_trade(
        self,
        sell_txn: dict,
        buy_txn: dict,
        current_regime: str = "UNKNOWN",
    ) -> PostMortem:
        """
        Generate post-mortem for a closed trade.

        Args:
            sell_txn: The SELL transaction dict
            buy_txn: The original BUY transaction dict
            current_regime: Current market regime

        Returns:
            PostMortem object with analysis
        """
        ticker = sell_txn["ticker"]
        entry_price = buy_txn["price"]
        exit_price = sell_txn["price"]
        shares = sell_txn["shares"]

        pnl = (exit_price - entry_price) * shares
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100

        # Calculate holding days
        buy_date = pd.to_datetime(buy_txn["date"])
        sell_date = pd.to_datetime(sell_txn["date"])
        holding_days = (sell_date - buy_date).days

        # Get entry context
        regime_at_entry = buy_txn.get("regime_at_entry", "UNKNOWN")
        composite_score = buy_txn.get("composite_score", 0)
        signal_rank = buy_txn.get("signal_rank", 0)

        # Parse factor scores
        factor_scores = {}
        factor_scores_str = buy_txn.get("factor_scores", "")
        if factor_scores_str and isinstance(factor_scores_str, str):
            try:
                factor_scores = json.loads(factor_scores_str)
            except json.JSONDecodeError:
                pass

        exit_reason = sell_txn.get("reason", "MANUAL")

        # Analyze what worked and what failed
        what_worked = []
        what_failed = []
        pattern_tags = []

        # Outcome-based analysis
        if pnl >= 0:
            what_worked.append(f"Trade was profitable: {pnl_pct:+.1f}%")
            if exit_reason == "TAKE_PROFIT":
                what_worked.append("Hit take profit target as planned")
        else:
            what_failed.append(f"Trade lost money: {pnl_pct:.1f}%")
            if exit_reason == "STOP_LOSS":
                what_failed.append("Stop loss triggered - thesis invalidated")

        # Factor-based analysis
        if factor_scores:
            top_factor = max(factor_scores.items(), key=lambda x: x[1])
            if pnl >= 0:
                what_worked.append(f"Strong {top_factor[0]} score ({top_factor[1]:.0f}) contributed to success")
            else:
                what_failed.append(f"High {top_factor[0]} score ({top_factor[1]:.0f}) didn't prevent loss")

        # Holding period analysis
        if holding_days <= 3:
            if pnl < 0:
                pattern_tags.append("quick_stop")
                what_failed.append("Stopped out very quickly - entry timing may be off")
        elif holding_days <= 5 and exit_reason == "TAKE_PROFIT":
            pattern_tags.append("quick_profit")
            what_worked.append("Quick profit - momentum thesis played out fast")
        elif holding_days >= 30:
            pattern_tags.append("extended_hold")

        # Regime analysis
        if regime_at_entry != current_regime and regime_at_entry != "UNKNOWN":
            pattern_tags.append("regime_change")
            if pnl < 0:
                what_failed.append(f"Regime changed from {regime_at_entry} to {current_regime} during hold")

        # Rank analysis
        if signal_rank == 1 and pnl < 0:
            pattern_tags.append("top_pick_loser")
            what_failed.append("Was top-ranked pick but still lost - scoring may need adjustment")
        elif signal_rank >= 3 and pnl >= 0:
            pattern_tags.append("low_rank_winner")
            what_worked.append(f"Ranked #{signal_rank} but still profitable - diversification pays")

        # Factor-specific patterns
        if factor_scores:
            momentum = factor_scores.get("momentum", 0)
            volatility = factor_scores.get("volatility", 0)

            if momentum >= 70 and pnl < 0:
                pattern_tags.append("momentum_reversal")
                what_failed.append("High momentum didn't sustain - possible reversal")

            if volatility >= 70 and exit_reason == "STOP_LOSS":
                pattern_tags.append("volatility_spike")

        # Generate summary
        if pnl >= 0:
            if exit_reason == "TAKE_PROFIT":
                summary = f"Successful trade: {ticker} hit target for {pnl_pct:+.1f}% in {holding_days} days"
            else:
                summary = f"Profitable exit: {ticker} closed at {pnl_pct:+.1f}%"
        else:
            if exit_reason == "STOP_LOSS":
                summary = f"Stop loss: {ticker} lost {abs(pnl_pct):.1f}% in {holding_days} days"
            else:
                summary = f"Loss taken: {ticker} closed at {pnl_pct:.1f}%"

        # Generate recommendation
        recommendation = self._generate_recommendation(
            pnl_pct, exit_reason, pattern_tags, what_failed, factor_scores
        )

        return PostMortem(
            transaction_id=sell_txn.get("transaction_id", ""),
            buy_transaction_id=buy_txn.get("transaction_id", ""),
            ticker=ticker,
            close_date=sell_txn["date"] if isinstance(sell_txn["date"], str) else sell_txn["date"].isoformat(),
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
            exit_reason=exit_reason,
            holding_days=holding_days,
            regime_at_entry=regime_at_entry,
            regime_at_exit=current_regime,
            composite_score_at_entry=composite_score,
            signal_rank_at_entry=signal_rank,
            summary=summary,
            what_worked=what_worked,
            what_failed=what_failed,
            pattern_tags=pattern_tags,
            recommendation=recommendation,
        )

    def _generate_recommendation(
        self,
        pnl_pct: float,
        exit_reason: str,
        pattern_tags: List[str],
        what_failed: List[str],
        factor_scores: Dict[str, float],
    ) -> str:
        """Generate actionable recommendation from analysis."""
        if pnl_pct >= 0:
            if "quick_profit" in pattern_tags:
                return "Consider trailing stops to capture more upside on quick movers"
            return "Continue current strategy - trade executed as planned"

        # Loss-based recommendations
        if "quick_stop" in pattern_tags:
            return "Review entry timing - consider waiting for pullbacks before entry"

        if "momentum_reversal" in pattern_tags:
            return "Add confirmation signals before buying high-momentum stocks"

        if "regime_change" in pattern_tags:
            return "Monitor regime more closely - consider tighter stops during transitions"

        if "top_pick_loser" in pattern_tags:
            return "Review scoring weights - top picks shouldn't consistently lose"

        if exit_reason == "STOP_LOSS":
            return "Stop loss worked as intended - review if stop level was appropriate"

        return "Document lessons and move on - losses are part of trading"


def save_post_mortem(post_mortem: PostMortem):
    """Save post-mortem to CSV file."""
    # Convert to dict for DataFrame
    data = asdict(post_mortem)

    # Convert lists to JSON strings for CSV storage
    data["what_worked"] = json.dumps(data["what_worked"])
    data["what_failed"] = json.dumps(data["what_failed"])
    data["pattern_tags"] = json.dumps(data["pattern_tags"])

    df_new = pd.DataFrame([data])

    if POST_MORTEMS_FILE.exists():
        df_existing = pd.read_csv(POST_MORTEMS_FILE)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new

    df_combined.to_csv(POST_MORTEMS_FILE, index=False)


def load_post_mortems() -> List[PostMortem]:
    """Load all post-mortems from file."""
    if not POST_MORTEMS_FILE.exists():
        return []

    df = pd.read_csv(POST_MORTEMS_FILE)
    post_mortems = []

    for _, row in df.iterrows():
        # Parse JSON strings back to lists
        what_worked = json.loads(row.get("what_worked", "[]"))
        what_failed = json.loads(row.get("what_failed", "[]"))
        pattern_tags = json.loads(row.get("pattern_tags", "[]"))

        pm = PostMortem(
            transaction_id=row["transaction_id"],
            buy_transaction_id=row["buy_transaction_id"],
            ticker=row["ticker"],
            close_date=row["close_date"],
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            pnl=row["pnl"],
            pnl_pct=row["pnl_pct"],
            exit_reason=row["exit_reason"],
            holding_days=row["holding_days"],
            regime_at_entry=row["regime_at_entry"],
            regime_at_exit=row["regime_at_exit"],
            composite_score_at_entry=row["composite_score_at_entry"],
            signal_rank_at_entry=row["signal_rank_at_entry"],
            summary=row["summary"],
            what_worked=what_worked,
            what_failed=what_failed,
            pattern_tags=pattern_tags,
            recommendation=row["recommendation"],
        )
        post_mortems.append(pm)

    return post_mortems


def get_recent_post_mortems(n: int = 5) -> List[PostMortem]:
    """Get the most recent post-mortems."""
    all_pm = load_post_mortems()
    return all_pm[-n:] if all_pm else []


def format_post_mortem_text(pm: PostMortem) -> str:
    """Format a post-mortem as readable text."""
    lines = []
    lines.append(f"Post-Mortem: {pm.ticker}")
    lines.append(f"Date: {pm.close_date}")
    lines.append(f"Result: {pm.pnl_pct:+.1f}% (${pm.pnl:+,.2f})")
    lines.append(f"Exit: {pm.exit_reason} after {pm.holding_days} days")
    lines.append("")
    lines.append(f"Summary: {pm.summary}")
    lines.append("")

    if pm.what_worked:
        lines.append("What Worked:")
        for w in pm.what_worked:
            lines.append(f"  + {w}")
        lines.append("")

    if pm.what_failed:
        lines.append("What Failed:")
        for f in pm.what_failed:
            lines.append(f"  - {f}")
        lines.append("")

    if pm.pattern_tags:
        lines.append(f"Patterns: {', '.join(pm.pattern_tags)}")
        lines.append("")

    lines.append(f"Recommendation: {pm.recommendation}")

    return "\n".join(lines)


# ─── CLI for Testing ───
if __name__ == "__main__":
    print("\n─── Post-Mortem Analysis Demo ───\n")

    # Create a sample post-mortem
    sample_buy = {
        "transaction_id": "buy123",
        "date": "2026-01-20",
        "ticker": "CRDO",
        "price": 100.0,
        "regime_at_entry": "BULL",
        "composite_score": 72.5,
        "signal_rank": 1,
        "factor_scores": json.dumps({
            "price_momentum": 78,
            "earnings_growth": 65,
            "quality": 72,
            "value_timing": 55,
            "volume": 60,
            "volatility": 65
        })
    }

    sample_sell = {
        "transaction_id": "sell456",
        "date": "2026-01-27",
        "ticker": "CRDO",
        "price": 92.0,
        "shares": 10,
        "reason": "STOP_LOSS"
    }

    analyzer = PostMortemAnalyzer()
    pm = analyzer.analyze_trade(sample_sell, sample_buy, current_regime="SIDEWAYS")

    print(format_post_mortem_text(pm))
