#!/usr/bin/env python3
"""
Layer 3: Portfolio Composition

Enforces diversification limits, detects correlation, triggers rebalancing.
"""

import json
from pathlib import Path
from typing import List, Dict, Set, Optional
from collections import defaultdict

import pandas as pd
import yfinance as yf

from enhanced_structures import (
    BuyProposal, SellProposal, CompositionViolation,
    RebalanceTrigger, UrgencyLevel
)
from portfolio_state import PortfolioState
from sector_mapper import get_sector, load_sector_mapping


DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load configuration."""
    with open(CONFIG_FILE) as f:
        return json.load(f)


class CompositionLayer:
    """Layer 3: Portfolio Composition - Diversification and correlation limits."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize composition layer with configuration."""
        self.config = config or load_config()
        self.layer3_config = self.config.get("enhanced_trading", {}).get("layer3", {})
        self.enabled = self.layer3_config.get("enable_composition", True)

        # Load limits
        self.sector_limit_pct = self.layer3_config.get("sector_limit_pct", 40.0)
        self.correlation_threshold = self.layer3_config.get("correlation_threshold", 0.7)
        self.max_correlated = self.layer3_config.get("max_correlated_positions", 3)
        self.top3_limit_pct = self.layer3_config.get("top3_limit_pct", 45.0)

        # Load sector mapping
        self.sector_mapping = load_sector_mapping()

    def process(
        self,
        state: PortfolioState,
        layer1_output: Dict,
        layer2_output: Dict,
        sector_map: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        Process Layer 3: Filter buys by composition limits, generate rebalancing.

        Args:
            state: Current portfolio state
            layer1_output: Output from Layer 1 (sells)
            layer2_output: Output from Layer 2 (buy proposals)
            sector_map: Optional dict mapping ticker -> sector (from watchlist or AI layer).
                        Used to resolve sectors for proposals without a static mapping.

        Returns:
            dict with:
                - filtered_buys: List[BuyProposal] (approved buys)
                - blocked_buys: List[BuyProposal] (blocked by limits)
                - rebalance_sells: List[SellProposal] (rebalancing actions)
                - violations: List[CompositionViolation]
                - warnings: List[str]
        """
        if not self.enabled:
            return {
                "filtered_buys": layer2_output.get("buy_proposals", []),
                "blocked_buys": [],
                "rebalance_sells": [],
                "violations": [],
                "warnings": []
            }

        buy_proposals = layer2_output.get("buy_proposals", [])

        # Analyze current composition
        current_sectors = self._analyze_sectors(state)
        current_top3_pct = self._calculate_top3_pct(state)

        # Build a running simulation of sector dollar-values so that each
        # successive proposal sees the portfolio *after* all previously approved
        # proposals have been added — not just the original snapshot.
        # Seed with current held-position market values keyed by sector.
        simulated_sector_values: Dict[str, float] = defaultdict(float)
        for sector, pct in current_sectors.items():
            simulated_sector_values[sector] = pct / 100.0 * state.total_equity
        simulated_equity: float = state.total_equity

        # Simulated positions list for top-3 checks (market_value column only needed)
        simulated_positions = state.positions.copy()

        # Filter buy proposals
        filtered_buys = []
        blocked_buys = []
        violations = []
        warnings = []

        for proposal in buy_proposals:
            # Check sector limit using the running simulation state
            sector_ok, sector_violation = self._check_sector_limit(
                proposal, simulated_sector_values, simulated_equity, sector_map
            )
            if not sector_ok:
                blocked_buys.append(proposal)
                violations.append(sector_violation)
                continue

            # Check correlation (skip for now - implement in later iteration)
            # correlation_ok, corr_violation = self._check_correlation(proposal, state)

            # Check top-3 limit using the running simulated positions
            top3_ok, top3_violation = self._check_top3_limit(
                proposal, simulated_positions, simulated_equity
            )
            if not top3_ok:
                blocked_buys.append(proposal)
                violations.append(top3_violation)
                continue

            # Approved — update the running simulation so the next proposal
            # sees this one as already part of the portfolio.
            proposal_sector = self._resolve_sector(proposal.ticker, sector_map)
            simulated_sector_values[proposal_sector] += proposal.total_value
            simulated_equity += proposal.total_value
            new_row = pd.DataFrame([{
                "ticker": proposal.ticker,
                "market_value": proposal.total_value,
                "shares": proposal.shares,
                "current_price": proposal.price,
            }])
            simulated_positions = pd.concat([simulated_positions, new_row], ignore_index=True)

            filtered_buys.append(proposal)

        # Generate warnings for current composition issues
        for sector, pct in current_sectors.items():
            if pct > self.sector_limit_pct:
                warnings.append(f"{sector} sector at {pct:.1f}% (limit {self.sector_limit_pct:.0f}%)")

        if current_top3_pct > self.top3_limit_pct:
            warnings.append(f"Top-3 concentration at {current_top3_pct:.1f}% (limit {self.top3_limit_pct:.0f}%)")

        # Check for rebalancing needs
        rebalance_sells = self._generate_rebalancing_sells(state, current_sectors, current_top3_pct)

        print(f"\n  🏗️  Layer 3: Approved {len(filtered_buys)}/{len(buy_proposals)} buys")
        if blocked_buys:
            print(f"  ⚠️  Blocked {len(blocked_buys)} buys due to composition limits")
        if rebalance_sells:
            print(f"  ⚖️  Generated {len(rebalance_sells)} rebalancing sell(s)")

        return {
            "filtered_buys": filtered_buys,
            "blocked_buys": blocked_buys,
            "rebalance_sells": rebalance_sells,
            "violations": violations,
            "warnings": warnings
        }

    def _analyze_sectors(self, state: PortfolioState) -> Dict[str, float]:
        """
        Analyze sector concentration in current portfolio.

        Returns:
            Dict[sector, percentage_of_portfolio]
        """
        if state.positions.empty:
            return {}

        sector_values = defaultdict(float)

        for _, pos in state.positions.iterrows():
            ticker = pos["ticker"]
            market_value = pos["market_value"]
            sector = get_sector(ticker, self.sector_mapping)
            sector_values[sector] += market_value

        # Convert to percentages
        return {
            sector: (value / state.total_equity * 100)
            for sector, value in sector_values.items()
        }

    def _calculate_top3_pct(self, state: PortfolioState) -> float:
        """Calculate percentage of portfolio in top 3 positions."""
        if state.positions.empty or len(state.positions) < 3:
            return 0.0

        sorted_positions = state.positions.sort_values("market_value", ascending=False)
        top3_value = sorted_positions.head(3)["market_value"].sum()

        return (top3_value / state.total_equity * 100) if state.total_equity > 0 else 0.0

    def _resolve_sector(self, ticker: str, sector_map: Optional[Dict[str, str]] = None) -> str:
        """
        Resolve sector for a ticker, preferring the provided sector_map over
        the static sector_mapping file (which may not have watchlist candidates).
        """
        if sector_map and ticker in sector_map:
            return sector_map[ticker]
        return get_sector(ticker, self.sector_mapping)

    def _check_sector_limit(
        self,
        proposal: BuyProposal,
        simulated_sector_values: Dict[str, float],
        simulated_equity: float,
        sector_map: Optional[Dict[str, str]] = None
    ) -> tuple[bool, Optional[CompositionViolation]]:
        """
        Check if buy would violate sector concentration limit.

        Uses the running simulated portfolio (dollar values + equity) so that
        multiple proposals in the same cycle do not all see the original snapshot.

        Returns:
            (is_ok, violation_or_none)
        """
        sector = self._resolve_sector(proposal.ticker, sector_map)
        current_sector_dollars = simulated_sector_values.get(sector, 0.0)

        # Project what the sector value and total equity would be after this buy
        new_sector_value = current_sector_dollars + proposal.total_value
        new_total_equity = simulated_equity + proposal.total_value
        new_sector_pct = (new_sector_value / new_total_equity * 100) if new_total_equity > 0 else 0.0

        if new_sector_pct > self.sector_limit_pct:
            violation = CompositionViolation(
                ticker=proposal.ticker,
                violation_type="SECTOR",
                current_value=new_sector_pct,
                limit_value=self.sector_limit_pct,
                description=f"{sector} sector would be {new_sector_pct:.1f}% (limit {self.sector_limit_pct:.0f}%)"
            )
            return False, violation

        return True, None

    def _check_top3_limit(
        self,
        proposal: BuyProposal,
        simulated_positions: pd.DataFrame,
        simulated_equity: float,
    ) -> tuple[bool, Optional[CompositionViolation]]:
        """
        Check if buy would violate top-3 concentration limit.

        Uses the running simulated positions DataFrame so that previously approved
        proposals in the same cycle are already reflected in the concentration check.

        Returns:
            (is_ok, violation_or_none)
        """
        # Append proposed position to the current simulation snapshot
        new_row = pd.DataFrame([{
            "ticker": proposal.ticker,
            "market_value": proposal.total_value,
            "shares": proposal.shares,
            "current_price": proposal.price,
        }])
        projected = pd.concat([simulated_positions, new_row], ignore_index=True)

        # Calculate new top-3 against projected equity (includes this buy)
        sorted_positions = projected.sort_values("market_value", ascending=False)
        new_top3_value = sorted_positions.head(3)["market_value"].sum()
        new_total_equity = simulated_equity + proposal.total_value
        new_top3_pct = (new_top3_value / new_total_equity * 100) if new_total_equity > 0 else 0.0

        if new_top3_pct > self.top3_limit_pct:
            violation = CompositionViolation(
                ticker=proposal.ticker,
                violation_type="TOP3",
                current_value=new_top3_pct,
                limit_value=self.top3_limit_pct,
                description=f"Top-3 would be {new_top3_pct:.1f}% (limit {self.top3_limit_pct:.0f}%)"
            )
            return False, violation

        return True, None

    def _generate_rebalancing_sells(
        self,
        state: PortfolioState,
        current_sectors: Dict[str, float],
        current_top3_pct: float
    ) -> List[SellProposal]:
        """
        Generate rebalancing sells for oversized positions.

        Only triggers if:
        - Rebalancing enabled in config
        - Top-3 > limit OR any sector > limit
        - Position is >18% (15% target + 20% drift threshold)
        """
        rebalance_config = self.layer3_config.get("enable_rebalancing", True)
        if not rebalance_config:
            return []

        # Only rebalance if limits violated
        limits_violated = (
            current_top3_pct > self.top3_limit_pct or
            any(pct > self.sector_limit_pct for pct in current_sectors.values())
        )

        if not limits_violated:
            return []

        rebalance_sells = []
        target_pct = self.layer3_config.get("rebalance_target_pct", 15.0)
        trigger_pct = target_pct * (1 + self.layer3_config.get("rebalance_trigger_pct", 20.0) / 100)

        for _, pos in state.positions.iterrows():
            position_pct = (pos["market_value"] / state.total_equity * 100)

            if position_pct > trigger_pct:
                # Calculate trim amount
                target_value = state.total_equity * (target_pct / 100)
                trim_value = pos["market_value"] - target_value
                trim_shares = int(trim_value / pos["current_price"])

                if trim_shares > 0:
                    rebalance_sells.append(SellProposal(
                        ticker=pos["ticker"],
                        shares=trim_shares,
                        current_price=pos["current_price"],
                        reason=f"REBALANCING (position at {position_pct:.1f}%, target {target_pct:.0f}%)",
                        urgency_level=UrgencyLevel.LOW,
                        urgency_score=50
                    ))

        return rebalance_sells
