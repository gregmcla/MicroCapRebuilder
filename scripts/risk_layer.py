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

    def _get_entry_score_from_transactions(self, ticker: str, state: PortfolioState) -> float:
        """Get composite_score from most recent BUY transaction for ticker."""
        if state.transactions.empty:
            return 70.0

        buys = state.transactions[
            (state.transactions["ticker"] == ticker) &
            (state.transactions["action"] == "BUY")
        ].sort_values("date", ascending=False)

        if buys.empty:
            return 70.0  # Fallback for legacy positions

        # Get composite_score from most recent buy
        latest_buy = buys.iloc[0]
        try:
            return float(latest_buy.get("composite_score", 70.0))
        except (ValueError, TypeError):
            return 70.0

    def calculate_dynamic_stops(self, state: PortfolioState) -> Dict[str, StopLevels]:
        """
        Calculate dynamic stop levels for all positions.

        Returns:
            Dict mapping ticker to StopLevels
        """
        if state.positions.empty:
            return {}

        # Score positions to get real ATR values
        tickers = [pos["ticker"] for _, pos in state.positions.iterrows()]
        scorer = StockScorer(regime=state.regime)
        scores = scorer.score_watchlist(tickers)
        score_map = {s.ticker: s for s in scores if s}

        stops = {}

        for _, pos in state.positions.iterrows():
            ticker = pos["ticker"]
            current_price = state.price_cache.get(ticker, pos["current_price"])
            entry_price = pos.get("avg_cost_basis", current_price)
            current_stop = pos.get("stop_loss", 0)

            # Calculate different stop types
            fixed_stop = current_stop if current_stop > 0 else entry_price * 0.92  # 8% default

            trailing_stop = None
            if self.layer1_config.get("enable_trailing_stops", True):
                trailing_stop = self._calculate_trailing_stop(
                    current_price, entry_price, current_stop
                )

            # Get real ATR from scoring
            score_obj = score_map.get(ticker)
            atr_pct = score_obj.atr_pct if score_obj else 2.5

            volatility_stop = None
            if self.layer1_config.get("enable_volatility_stops", True):
                volatility_stop = self._calculate_volatility_stop(
                    current_price, entry_price, atr_pct=atr_pct
                )

            regime_stop = self._calculate_regime_stop(
                entry_price, state.regime
            )

            # Determine best stop to use (most conservative)
            all_stops = [s for s in [fixed_stop, trailing_stop, volatility_stop, regime_stop] if s is not None]
            recommended_stop = max(all_stops) if all_stops else fixed_stop
            stop_type = self._determine_stop_type(
                fixed_stop, trailing_stop, volatility_stop, regime_stop, recommended_stop
            )

            stops[ticker] = StopLevels(
                ticker=ticker,
                current_price=current_price,
                fixed_stop=fixed_stop,
                trailing_stop=trailing_stop,
                volatility_adjusted_stop=volatility_stop,
                regime_adjusted_stop=regime_stop,
                recommended_stop=recommended_stop,
                stop_type=stop_type
            )

        return stops

    def _calculate_trailing_stop(
        self, current_price: float, entry_price: float, current_stop: float
    ) -> Optional[float]:
        """Calculate trailing stop if position is up enough."""
        trigger_pct = self.layer1_config.get("trailing_stop_trigger_pct", 10.0) / 100
        distance_pct = self.layer1_config.get("trailing_stop_distance_pct", 8.0) / 100

        gain_pct = (current_price - entry_price) / entry_price

        if gain_pct >= trigger_pct:
            # Position is up 10%+, trail the stop
            min_stop = entry_price * 1.05  # Never go below entry + 5%
            trailing = current_price * (1 - distance_pct)
            return max(trailing, min_stop, current_stop)

        return None

    def _calculate_volatility_stop(
        self, current_price: float, entry_price: float, atr_pct: float
    ) -> float:
        """Calculate volatility-adjusted stop based on ATR%."""
        high_atr_threshold = self.layer1_config.get("volatility_stop_atr_threshold_high", 5.0)
        low_atr_threshold = self.layer1_config.get("volatility_stop_atr_threshold_low", 2.0)
        high_atr_stop_pct = self.layer1_config.get("volatility_stop_high_atr", 10.0) / 100
        low_atr_stop_pct = self.layer1_config.get("volatility_stop_low_atr", 6.0) / 100

        if atr_pct > high_atr_threshold:
            # High volatility - wider stop
            return entry_price * (1 - high_atr_stop_pct)
        elif atr_pct < low_atr_threshold:
            # Low volatility - tighter stop
            return entry_price * (1 - low_atr_stop_pct)
        else:
            # Normal volatility - standard stop
            return entry_price * 0.92  # 8%

    def _calculate_regime_stop(self, entry_price: float, regime: MarketRegime) -> float:
        """Calculate regime-aware stop."""
        regime_stops = self.layer1_config.get("regime_stops", {
            "BULL": 8.0,
            "SIDEWAYS": 7.0,
            "BEAR": 6.0
        })

        stop_pct = regime_stops.get(regime.value, 8.0) / 100
        return entry_price * (1 - stop_pct)

    def _determine_stop_type(
        self, fixed: float, trailing: Optional[float],
        volatility: Optional[float], regime: float, recommended: float
    ) -> str:
        """Determine which stop type is being used."""
        if trailing and abs(trailing - recommended) < 0.01:
            return "trailing"
        elif volatility and abs(volatility - recommended) < 0.01:
            return "volatility"
        elif abs(regime - recommended) < 0.01:
            return "regime"
        else:
            return "fixed"

    def process(self, state: PortfolioState) -> Dict:
        """
        Process Layer 1: Re-evaluate positions, detect deterioration, update stops.

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

        # Calculate dynamic stops first
        updated_stops = self.calculate_dynamic_stops(state)

        sell_proposals = []
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

            # Use dynamic stop if available
            stop_levels = updated_stops.get(ticker)
            effective_stop = stop_levels.recommended_stop if stop_levels else pos.get("stop_loss", 0)
            take_profit = pos.get("take_profit", 0)

            # Check stop loss (using dynamic stop)
            if effective_stop > 0 and current_price <= effective_stop:
                stop_type_note = f" ({stop_levels.stop_type})" if stop_levels else ""
                sell_proposals.append(SellProposal(
                    ticker=ticker,
                    shares=int(pos["shares"]),
                    current_price=current_price,
                    reason=f"STOP LOSS{stop_type_note} triggered: ${current_price:.2f} <= ${effective_stop:.2f}",
                    urgency_level=UrgencyLevel.EMERGENCY,
                    urgency_score=100,
                    stop_loss=effective_stop,
                    take_profit=take_profit
                ))
                continue

            # Check take profit
            if take_profit > 0 and current_price >= take_profit:
                sell_proposals.append(SellProposal(
                    ticker=ticker,
                    shares=int(pos["shares"]),
                    current_price=current_price,
                    reason=f"TAKE PROFIT triggered: ${current_price:.2f} >= ${take_profit:.2f}",
                    urgency_level=UrgencyLevel.LOW,
                    urgency_score=50,
                    stop_loss=effective_stop,
                    take_profit=take_profit
                ))
                continue

            # Re-evaluation: Check score deterioration (same as before)
            current_score_obj = score_map.get(ticker)
            if not current_score_obj:
                continue

            current_score = current_score_obj.composite_score
            entry_score = self._get_entry_score_from_transactions(ticker, state)

            score_drop = entry_score - current_score

            if score_drop >= self.min_score_drop_sell:
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
                    stop_loss=effective_stop,
                    take_profit=take_profit
                ))

            elif score_drop >= self.min_score_drop_alert:
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
