#!/usr/bin/env python3
"""
Pattern Detection Module for Mommy Bot.

Detects concerning patterns across trades:
- Stop loss clusters (multiple stops in short period)
- Factor reversals (a factor consistently failing)
- Regime mismatches (entries in wrong regime)
- Win/loss streaks

Generates alerts when patterns are detected.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
from datetime import date, datetime, timedelta
from enum import Enum

import pandas as pd

# ─── Paths ───
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"
POST_MORTEMS_FILE = DATA_DIR / "post_mortems.csv"
PATTERN_ALERTS_FILE = DATA_DIR / "pattern_alerts.csv"


class AlertLevel(Enum):
    """Severity levels for pattern alerts."""
    INFO = "INFO"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class PatternAlert:
    """An alert generated from pattern detection."""
    pattern_type: str
    alert_level: str  # INFO, MEDIUM, HIGH, CRITICAL
    title: str
    description: str
    detected_date: str
    details: Dict = field(default_factory=dict)
    recommendation: str = ""
    is_active: bool = True


class PatternDetector:
    """Detects patterns across trading history."""

    # Pattern detection thresholds
    THRESHOLDS = {
        "stop_loss_cluster": {
            "count": 3,
            "days": 5,
            "level": AlertLevel.HIGH,
        },
        "losing_streak": {
            "count": 5,
            "level": AlertLevel.MEDIUM,
        },
        "winning_streak": {
            "count": 5,
            "level": AlertLevel.INFO,
        },
        "factor_failure": {
            "trades": 5,
            "win_rate_threshold": 30,  # Alert if factor's win rate below 30%
            "level": AlertLevel.MEDIUM,
        },
        "regime_mismatch": {
            "count": 3,
            "level": AlertLevel.MEDIUM,
        },
    }

    def __init__(self):
        self.transactions_df = self._load_transactions()
        self.post_mortems_df = self._load_post_mortems()

    def _load_transactions(self) -> pd.DataFrame:
        """Load transactions."""
        if not TRANSACTIONS_FILE.exists():
            return pd.DataFrame()
        df = pd.read_csv(TRANSACTIONS_FILE)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def _load_post_mortems(self) -> pd.DataFrame:
        """Load post-mortems."""
        if not POST_MORTEMS_FILE.exists():
            return pd.DataFrame()
        return pd.read_csv(POST_MORTEMS_FILE)

    def detect_all_patterns(self) -> List[PatternAlert]:
        """Run all pattern detection and return alerts."""
        alerts = []

        alerts.extend(self._detect_stop_loss_cluster())
        alerts.extend(self._detect_streaks())
        alerts.extend(self._detect_factor_failure())
        alerts.extend(self._detect_regime_mismatch())

        return alerts

    def _detect_stop_loss_cluster(self) -> List[PatternAlert]:
        """Detect multiple stop losses in a short period."""
        alerts = []

        if self.transactions_df.empty:
            return alerts

        # Get recent sells with STOP_LOSS reason
        sells = self.transactions_df[
            (self.transactions_df["action"] == "SELL") &
            (self.transactions_df["reason"] == "STOP_LOSS")
        ].copy()

        if sells.empty:
            return alerts

        threshold = self.THRESHOLDS["stop_loss_cluster"]
        lookback_days = threshold["days"]
        min_count = threshold["count"]

        # Look at recent period
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        recent_stops = sells[sells["date"] >= cutoff_date]

        if len(recent_stops) >= min_count:
            tickers = recent_stops["ticker"].tolist()
            alerts.append(PatternAlert(
                pattern_type="stop_loss_cluster",
                alert_level=threshold["level"].value,
                title=f"Stop Loss Cluster Detected",
                description=f"{len(recent_stops)} stop losses triggered in last {lookback_days} days",
                detected_date=date.today().isoformat(),
                details={
                    "tickers": tickers,
                    "count": len(recent_stops),
                    "period_days": lookback_days,
                },
                recommendation="Review market conditions and consider pausing new entries until volatility subsides",
            ))

        return alerts

    def _detect_streaks(self) -> List[PatternAlert]:
        """Detect winning and losing streaks."""
        alerts = []

        if self.post_mortems_df.empty:
            return alerts

        # Sort by date
        df = self.post_mortems_df.sort_values("close_date", ascending=False)

        # Count consecutive wins/losses from most recent
        wins = 0
        losses = 0
        current_streak = None

        for _, row in df.iterrows():
            pnl = row.get("pnl", 0)

            if current_streak is None:
                current_streak = "win" if pnl >= 0 else "loss"

            if pnl >= 0:
                if current_streak == "win":
                    wins += 1
                else:
                    break
            else:
                if current_streak == "loss":
                    losses += 1
                else:
                    break

        # Check for losing streak
        if losses >= self.THRESHOLDS["losing_streak"]["count"]:
            alerts.append(PatternAlert(
                pattern_type="losing_streak",
                alert_level=self.THRESHOLDS["losing_streak"]["level"].value,
                title=f"Losing Streak: {losses} Consecutive Losses",
                description=f"Last {losses} closed trades were losses",
                detected_date=date.today().isoformat(),
                details={"streak_length": losses},
                recommendation="Take a step back - review strategy and consider reducing position sizes",
            ))

        # Check for winning streak (informational)
        if wins >= self.THRESHOLDS["winning_streak"]["count"]:
            alerts.append(PatternAlert(
                pattern_type="winning_streak",
                alert_level=self.THRESHOLDS["winning_streak"]["level"].value,
                title=f"Winning Streak: {wins} Consecutive Wins",
                description=f"Last {wins} closed trades were profitable",
                detected_date=date.today().isoformat(),
                details={"streak_length": wins},
                recommendation="Great performance! Don't get overconfident - maintain risk discipline",
            ))

        return alerts

    def _detect_factor_failure(self) -> List[PatternAlert]:
        """Detect if a factor is consistently failing."""
        alerts = []

        if self.post_mortems_df.empty or len(self.post_mortems_df) < self.THRESHOLDS["factor_failure"]["trades"]:
            return alerts

        # Analyze recent trades
        recent = self.post_mortems_df.tail(self.THRESHOLDS["factor_failure"]["trades"] * 2)

        # This would require factor_scores in post_mortems
        # For now, we'll check pattern_tags for factor-related patterns
        if "pattern_tags" in recent.columns:
            all_tags = []
            for tags_str in recent["pattern_tags"].dropna():
                try:
                    tags = json.loads(tags_str)
                    all_tags.extend(tags)
                except:
                    pass

            # Count momentum reversals
            momentum_reversals = all_tags.count("momentum_reversal")
            if momentum_reversals >= 3:
                alerts.append(PatternAlert(
                    pattern_type="factor_failure",
                    alert_level=self.THRESHOLDS["factor_failure"]["level"].value,
                    title="Momentum Factor Underperforming",
                    description=f"{momentum_reversals} momentum reversals in recent trades",
                    detected_date=date.today().isoformat(),
                    details={"factor": "momentum", "failure_count": momentum_reversals},
                    recommendation="Consider reducing momentum weight or adding confirmation signals",
                ))

        return alerts

    def _detect_regime_mismatch(self) -> List[PatternAlert]:
        """Detect trades where regime changed significantly during hold."""
        alerts = []

        if self.post_mortems_df.empty:
            return alerts

        # Count regime mismatches in recent trades
        if "pattern_tags" in self.post_mortems_df.columns:
            recent = self.post_mortems_df.tail(10)
            regime_changes = 0

            for tags_str in recent["pattern_tags"].dropna():
                try:
                    tags = json.loads(tags_str)
                    if "regime_change" in tags:
                        regime_changes += 1
                except:
                    pass

            if regime_changes >= self.THRESHOLDS["regime_mismatch"]["count"]:
                alerts.append(PatternAlert(
                    pattern_type="regime_mismatch",
                    alert_level=self.THRESHOLDS["regime_mismatch"]["level"].value,
                    title="Frequent Regime Changes During Holds",
                    description=f"{regime_changes} trades affected by regime changes",
                    detected_date=date.today().isoformat(),
                    details={"count": regime_changes},
                    recommendation="Market may be in transition - consider shorter holding periods",
                ))

        return alerts


def save_alerts(alerts: List[PatternAlert]):
    """Save pattern alerts to CSV."""
    if not alerts:
        return

    data = []
    for alert in alerts:
        data.append({
            "pattern_type": alert.pattern_type,
            "alert_level": alert.alert_level,
            "title": alert.title,
            "description": alert.description,
            "detected_date": alert.detected_date,
            "details": json.dumps(alert.details),
            "recommendation": alert.recommendation,
            "is_active": alert.is_active,
        })

    df_new = pd.DataFrame(data)

    if PATTERN_ALERTS_FILE.exists():
        df_existing = pd.read_csv(PATTERN_ALERTS_FILE)
        # Remove duplicates (same pattern_type and date)
        df_existing = df_existing[
            ~((df_existing["pattern_type"].isin(df_new["pattern_type"])) &
              (df_existing["detected_date"].isin(df_new["detected_date"])))
        ]
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new

    df_combined.to_csv(PATTERN_ALERTS_FILE, index=False)


def load_active_alerts() -> List[PatternAlert]:
    """Load active pattern alerts."""
    if not PATTERN_ALERTS_FILE.exists():
        return []

    df = pd.read_csv(PATTERN_ALERTS_FILE)
    df = df[df["is_active"] == True]

    alerts = []
    for _, row in df.iterrows():
        details = {}
        try:
            details = json.loads(row.get("details", "{}"))
        except:
            pass

        alerts.append(PatternAlert(
            pattern_type=row["pattern_type"],
            alert_level=row["alert_level"],
            title=row["title"],
            description=row["description"],
            detected_date=row["detected_date"],
            details=details,
            recommendation=row.get("recommendation", ""),
            is_active=row.get("is_active", True),
        ))

    return alerts


def get_pattern_alerts() -> List[PatternAlert]:
    """Run pattern detection and get current alerts."""
    detector = PatternDetector()
    alerts = detector.detect_all_patterns()

    # Save new alerts
    if alerts:
        save_alerts(alerts)

    return alerts


def format_alert_text(alert: PatternAlert) -> str:
    """Format an alert as readable text."""
    level_emoji = {
        "INFO": "ℹ️",
        "MEDIUM": "⚠️",
        "HIGH": "🔴",
        "CRITICAL": "🚨",
    }
    emoji = level_emoji.get(alert.alert_level, "❓")

    lines = []
    lines.append(f"{emoji} [{alert.alert_level}] {alert.title}")
    lines.append(f"   {alert.description}")
    if alert.recommendation:
        lines.append(f"   → {alert.recommendation}")

    return "\n".join(lines)


# ─── CLI for Testing ───
if __name__ == "__main__":
    print("\n─── Pattern Detection ───\n")

    alerts = get_pattern_alerts()

    if alerts:
        print(f"Found {len(alerts)} pattern(s):\n")
        for alert in alerts:
            print(format_alert_text(alert))
            print()
    else:
        print("No concerning patterns detected.")
        print("(Patterns emerge after trades are closed)")
