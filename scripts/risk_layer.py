#!/usr/bin/env python3
"""
Layer 1: Risk Management

Re-evaluates ALL current positions, detects deterioration,
manages dynamic stops, proposes sells based on urgency.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd

from enhanced_structures import (
    SellProposal, DeteriorationSignal, UrgencyLevel,
    PatternSignal, PatternType, StopLevels
)
from stock_scorer import StockScorer
from portfolio_state import PortfolioState
from market_regime import MarketRegime


DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load configuration."""
    with open(CONFIG_FILE) as f:
        return json.load(f)


class RiskLayer:
    """Layer 1: Risk Management - Position re-evaluation and dynamic stops."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize risk layer with configuration."""
        self.config = config or load_config()
        self.layer1_config = self.config.get("enhanced_trading", {}).get("layer1", {})
        self.enabled = self.layer1_config.get("enable_reeval", True)
        self.min_score_drop_alert = self.layer1_config.get("min_score_drop_for_alert", 20)
        self.min_score_drop_sell = self.layer1_config.get("min_score_drop_for_sell", 30)

    def process(self, state: PortfolioState) -> Dict:
        """
        Process Layer 1: Re-evaluate positions, detect deterioration.

        Returns:
            dict with:
                - sell_proposals: List[SellProposal]
                - updated_stops: Dict[ticker, StopLevels]
                - deterioration_alerts: List[DeteriorationSignal]
        """
        if not self.enabled:
            return {
                "sell_proposals": [],
                "updated_stops": {},
                "deterioration_alerts": []
            }

        sell_proposals = []
        updated_stops = {}
        deterioration_alerts = []

        if state.positions.empty:
            return {
                "sell_proposals": sell_proposals,
                "updated_stops": updated_stops,
                "deterioration_alerts": deterioration_alerts
            }

        # Re-score all positions
        tickers = state.positions["ticker"].tolist()
        scorer = StockScorer(regime=state.regime)
        current_scores = scorer.score_watchlist(tickers)
        score_map = {s.ticker: s for s in current_scores if s}

        for _, pos in state.positions.iterrows():
            ticker = pos["ticker"]
            current_price = state.price_cache.get(ticker, pos["current_price"])

            # Check stop loss / take profit (existing logic)
            stop_loss = pos.get("stop_loss", 0)
            take_profit = pos.get("take_profit", 0)

            if stop_loss > 0 and current_price <= stop_loss:
                sell_proposals.append(SellProposal(
                    ticker=ticker,
                    shares=int(pos["shares"]),
                    current_price=current_price,
                    reason=f"STOP LOSS triggered: ${current_price:.2f} <= ${stop_loss:.2f}",
                    urgency_level=UrgencyLevel.EMERGENCY,
                    urgency_score=100,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                ))
                continue

            if take_profit > 0 and current_price >= take_profit:
                sell_proposals.append(SellProposal(
                    ticker=ticker,
                    shares=int(pos["shares"]),
                    current_price=current_price,
                    reason=f"TAKE PROFIT triggered: ${current_price:.2f} >= ${take_profit:.2f}",
                    urgency_level=UrgencyLevel.LOW,
                    urgency_score=50,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                ))
                continue

            # Re-evaluation: Check score deterioration
            current_score_obj = score_map.get(ticker)
            if not current_score_obj:
                continue

            current_score = current_score_obj.composite_score

            # Try to get entry score from transactions
            # For now, use a placeholder - we'll enhance this later
            entry_score = 70.0  # TODO: Load from transaction factor_scores

            score_drop = entry_score - current_score

            if score_drop >= self.min_score_drop_sell:
                # Significant deterioration - propose sell
                deterioration = DeteriorationSignal(
                    ticker=ticker,
                    entry_score=entry_score,
                    current_score=current_score,
                    score_drop=score_drop,
                    urgency_score=min(100, int(50 + score_drop))
                )
                deterioration_alerts.append(deterioration)

                sell_proposals.append(SellProposal(
                    ticker=ticker,
                    shares=int(pos["shares"]),
                    current_price=current_price,
                    reason=f"QUALITY DEGRADATION: Score dropped {score_drop:.0f} points ({entry_score:.0f} → {current_score:.0f})",
                    urgency_level=UrgencyLevel.HIGH if score_drop >= 40 else UrgencyLevel.MEDIUM,
                    urgency_score=min(100, int(50 + score_drop)),
                    deterioration=deterioration,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                ))

            elif score_drop >= self.min_score_drop_alert:
                # Alert but don't sell yet
                deterioration = DeteriorationSignal(
                    ticker=ticker,
                    entry_score=entry_score,
                    current_score=current_score,
                    score_drop=score_drop,
                    urgency_score=min(100, int(30 + score_drop))
                )
                deterioration_alerts.append(deterioration)

        return {
            "sell_proposals": sell_proposals,
            "updated_stops": updated_stops,
            "deterioration_alerts": deterioration_alerts
        }
