#!/usr/bin/env python3
"""
Performance Attribution Module for Mommy Bot.

Explains WHY performance happened by attributing returns to:
- Individual factors (momentum, volatility, etc.)
- Market regimes (BULL/SIDEWAYS/BEAR)
- Top/bottom contributing trades

This helps answer: "What drove today's P&L?"
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
from datetime import date, datetime, timedelta

import pandas as pd

from portfolio_state import load_portfolio_state
from data_files import DATA_DIR

# ─── Paths ───
RATIONALES_FILE = DATA_DIR / "trade_rationales.jsonl"


@dataclass
class TradeContribution:
    """Contribution of a single trade to performance."""
    ticker: str
    pnl: float
    pnl_pct: float
    entry_date: str
    factor_scores: Dict[str, float]
    regime_at_entry: str
    is_realized: bool  # True if closed, False if unrealized


@dataclass
class FactorAttribution:
    """Attribution of performance to a single factor."""
    factor: str
    contribution: float  # Dollar amount
    contribution_pct: float  # Percentage of total P&L
    narrative: str  # Human-readable explanation


@dataclass
class PerformanceAttribution:
    """Complete performance attribution for a period."""
    period: str  # daily, weekly, monthly, ytd
    start_date: str
    end_date: str

    # Overall performance
    total_return: float  # Dollar amount
    total_return_pct: float

    # Factor attribution
    attribution_by_factor: Dict[str, float] = field(default_factory=dict)
    factor_details: List[FactorAttribution] = field(default_factory=list)

    # Regime attribution
    attribution_by_regime: Dict[str, float] = field(default_factory=dict)

    # Trade contributions
    top_contributors: List[TradeContribution] = field(default_factory=list)
    bottom_contributors: List[TradeContribution] = field(default_factory=list)

    # Narrative
    narrative: str = ""


class PerformanceAttributor:
    """Calculates performance attribution."""

    FACTOR_NAMES = ["momentum", "volatility", "volume", "relative_strength", "mean_reversion"]

    def __init__(self):
        state = load_portfolio_state(fetch_prices=False)
        self.transactions_df = state.transactions.copy()
        self.positions_df = state.positions.copy()
        self.snapshots_df = state.snapshots.copy()

        # Convert date columns to datetime if needed
        if not self.transactions_df.empty and "date" in self.transactions_df.columns:
            self.transactions_df["date"] = pd.to_datetime(self.transactions_df["date"])
        if not self.snapshots_df.empty and "date" in self.snapshots_df.columns:
            self.snapshots_df["date"] = pd.to_datetime(self.snapshots_df["date"])

    def get_daily_attribution(self, target_date: date = None) -> Optional[PerformanceAttribution]:
        """Get attribution for a single day."""
        if target_date is None:
            target_date = date.today()

        target_str = target_date.isoformat()

        # Get day's P&L from snapshots
        if self.snapshots_df.empty:
            return None

        day_snapshot = self.snapshots_df[
            self.snapshots_df["date"].dt.date == target_date
        ]

        if day_snapshot.empty:
            return None

        day_pnl = day_snapshot.iloc[-1].get("day_pnl", 0)
        day_pnl_pct = day_snapshot.iloc[-1].get("day_pnl_pct", 0)

        # Get trade contributions (realized + unrealized)
        contributions = self._calculate_trade_contributions(target_date)

        # Calculate factor attribution
        factor_attribution = self._calculate_factor_attribution(contributions, day_pnl)

        # Calculate regime attribution
        regime_attribution = self._calculate_regime_attribution(contributions)

        # Sort contributions
        sorted_contributions = sorted(contributions, key=lambda x: x.pnl, reverse=True)
        top_contributors = sorted_contributions[:3] if sorted_contributions else []
        bottom_contributors = sorted_contributions[-3:][::-1] if len(sorted_contributions) >= 3 else []

        # Generate narrative
        narrative = self._generate_narrative(
            day_pnl, day_pnl_pct, factor_attribution, top_contributors, bottom_contributors
        )

        return PerformanceAttribution(
            period="daily",
            start_date=target_str,
            end_date=target_str,
            total_return=day_pnl,
            total_return_pct=day_pnl_pct,
            attribution_by_factor={f.factor: f.contribution for f in factor_attribution},
            factor_details=factor_attribution,
            attribution_by_regime=regime_attribution,
            top_contributors=top_contributors,
            bottom_contributors=bottom_contributors,
            narrative=narrative,
        )

    def _calculate_trade_contributions(self, target_date: date) -> List[TradeContribution]:
        """Calculate P&L contribution from each position."""
        contributions = []

        if self.positions_df.empty:
            return contributions

        # Get unrealized P&L from current positions
        for _, pos in self.positions_df.iterrows():
            ticker = pos["ticker"]
            unrealized_pnl = pos.get("unrealized_pnl", 0)
            unrealized_pnl_pct = pos.get("unrealized_pnl_pct", 0)
            entry_date = pos.get("entry_date", "")

            # Get factor scores from original buy transaction
            factor_scores = {}
            regime_at_entry = ""

            if not self.transactions_df.empty:
                buy_txn = self.transactions_df[
                    (self.transactions_df["ticker"] == ticker) &
                    (self.transactions_df["action"] == "BUY")
                ]
                if not buy_txn.empty:
                    latest_buy = buy_txn.iloc[-1]
                    regime_at_entry = latest_buy.get("regime_at_entry", "")

                    # Parse factor scores JSON
                    factor_scores_str = latest_buy.get("factor_scores", "")
                    if factor_scores_str and isinstance(factor_scores_str, str):
                        try:
                            factor_scores = json.loads(factor_scores_str)
                        except json.JSONDecodeError:
                            pass

            contributions.append(TradeContribution(
                ticker=ticker,
                pnl=unrealized_pnl,
                pnl_pct=unrealized_pnl_pct,
                entry_date=entry_date,
                factor_scores=factor_scores,
                regime_at_entry=regime_at_entry,
                is_realized=False,
            ))

        # Get realized P&L from today's sells
        if not self.transactions_df.empty:
            today_sells = self.transactions_df[
                (self.transactions_df["date"].dt.date == target_date) &
                (self.transactions_df["action"] == "SELL")
            ]

            for _, sell in today_sells.iterrows():
                ticker = sell["ticker"]
                # Find the matching buy to calculate realized P&L
                buys = self.transactions_df[
                    (self.transactions_df["ticker"] == ticker) &
                    (self.transactions_df["action"] == "BUY")
                ]

                if not buys.empty:
                    buy = buys.iloc[-1]
                    buy_price = buy["price"]
                    sell_price = sell["price"]
                    shares = sell["shares"]

                    realized_pnl = (sell_price - buy_price) * shares
                    realized_pnl_pct = ((sell_price - buy_price) / buy_price) * 100

                    factor_scores = {}
                    factor_scores_str = buy.get("factor_scores", "")
                    if factor_scores_str and isinstance(factor_scores_str, str):
                        try:
                            factor_scores = json.loads(factor_scores_str)
                        except json.JSONDecodeError:
                            pass

                    contributions.append(TradeContribution(
                        ticker=ticker,
                        pnl=realized_pnl,
                        pnl_pct=realized_pnl_pct,
                        entry_date=buy.get("date", ""),
                        factor_scores=factor_scores,
                        regime_at_entry=buy.get("regime_at_entry", ""),
                        is_realized=True,
                    ))

        return contributions

    def _calculate_factor_attribution(
        self, contributions: List[TradeContribution], total_pnl: float
    ) -> List[FactorAttribution]:
        """Attribute P&L to factors based on entry factor scores."""
        if not contributions or total_pnl == 0:
            return []

        # Aggregate factor contributions
        factor_totals = {f: 0.0 for f in self.FACTOR_NAMES}
        factor_counts = {f: 0 for f in self.FACTOR_NAMES}

        for contrib in contributions:
            if not contrib.factor_scores:
                continue

            # Weight P&L by factor scores
            total_score = sum(contrib.factor_scores.values())
            if total_score == 0:
                continue

            for factor, score in contrib.factor_scores.items():
                if factor in factor_totals:
                    # Attribute portion of P&L based on factor's contribution to score
                    factor_pnl = contrib.pnl * (score / total_score)
                    factor_totals[factor] += factor_pnl
                    factor_counts[factor] += 1

        # Build factor attribution list
        attributions = []
        for factor in self.FACTOR_NAMES:
            contribution = factor_totals[factor]
            contribution_pct = (contribution / total_pnl * 100) if total_pnl != 0 else 0

            # Generate narrative
            if contribution > 0:
                narrative = f"{factor.replace('_', ' ').title()} contributed positively"
            elif contribution < 0:
                narrative = f"{factor.replace('_', ' ').title()} detracted from performance"
            else:
                narrative = f"{factor.replace('_', ' ').title()} had neutral impact"

            attributions.append(FactorAttribution(
                factor=factor,
                contribution=round(contribution, 2),
                contribution_pct=round(contribution_pct, 1),
                narrative=narrative,
            ))

        # Sort by absolute contribution
        attributions.sort(key=lambda x: abs(x.contribution), reverse=True)
        return attributions

    def _calculate_regime_attribution(
        self, contributions: List[TradeContribution]
    ) -> Dict[str, float]:
        """Attribute P&L to market regimes at entry."""
        regime_pnl = {}

        for contrib in contributions:
            regime = contrib.regime_at_entry or "UNKNOWN"
            if regime not in regime_pnl:
                regime_pnl[regime] = 0.0
            regime_pnl[regime] += contrib.pnl

        return {k: round(v, 2) for k, v in regime_pnl.items()}

    def _generate_narrative(
        self,
        total_pnl: float,
        total_pnl_pct: float,
        factor_attribution: List[FactorAttribution],
        top_contributors: List[TradeContribution],
        bottom_contributors: List[TradeContribution],
    ) -> str:
        """Generate human-readable performance narrative."""
        parts = []

        # Overall performance
        direction = "gained" if total_pnl >= 0 else "lost"
        parts.append(f"Portfolio {direction} ${abs(total_pnl):,.2f} ({total_pnl_pct:+.2f}%)")

        # Top factor
        if factor_attribution:
            top_factor = factor_attribution[0]
            if abs(top_factor.contribution) > 0:
                factor_direction = "driven by" if top_factor.contribution > 0 else "hurt by"
                parts.append(f"{factor_direction} {top_factor.factor.replace('_', ' ')}")

        # Top contributor
        if top_contributors and top_contributors[0].pnl > 0:
            parts.append(f"Top performer: {top_contributors[0].ticker} (+${top_contributors[0].pnl:,.2f})")

        # Bottom contributor
        if bottom_contributors and bottom_contributors[0].pnl < 0:
            parts.append(f"Laggard: {bottom_contributors[0].ticker} (${bottom_contributors[0].pnl:,.2f})")

        return ". ".join(parts) + "." if parts else "No significant activity."


def get_daily_attribution(target_date: date = None) -> Optional[PerformanceAttribution]:
    """Get performance attribution for a day."""
    attributor = PerformanceAttributor()
    return attributor.get_daily_attribution(target_date)


def format_attribution_text(attribution: PerformanceAttribution) -> str:
    """Format attribution as human-readable text."""
    lines = []

    lines.append(f"Performance Attribution: {attribution.period.upper()}")
    lines.append(f"Date: {attribution.start_date}")
    lines.append(f"Total Return: ${attribution.total_return:+,.2f} ({attribution.total_return_pct:+.2f}%)")
    lines.append("")

    if attribution.factor_details:
        lines.append("Factor Attribution:")
        for f in attribution.factor_details:
            sign = "+" if f.contribution >= 0 else ""
            lines.append(f"  {f.factor:<20} {sign}${f.contribution:,.2f} ({f.contribution_pct:+.1f}%)")
        lines.append("")

    if attribution.attribution_by_regime:
        lines.append("Regime Attribution:")
        for regime, pnl in attribution.attribution_by_regime.items():
            sign = "+" if pnl >= 0 else ""
            lines.append(f"  {regime:<10} {sign}${pnl:,.2f}")
        lines.append("")

    if attribution.top_contributors:
        lines.append("Top Contributors:")
        for t in attribution.top_contributors:
            lines.append(f"  {t.ticker}: ${t.pnl:+,.2f} ({t.pnl_pct:+.1f}%)")
        lines.append("")

    if attribution.bottom_contributors:
        lines.append("Bottom Contributors:")
        for b in attribution.bottom_contributors:
            lines.append(f"  {b.ticker}: ${b.pnl:+,.2f} ({b.pnl_pct:+.1f}%)")
        lines.append("")

    lines.append(f"Summary: {attribution.narrative}")

    return "\n".join(lines)


# ─── CLI for Testing ───
if __name__ == "__main__":
    print("\n─── Performance Attribution Demo ───\n")

    attribution = get_daily_attribution()

    if attribution:
        print(format_attribution_text(attribution))
    else:
        print("No attribution data available (need daily snapshots and positions)")
