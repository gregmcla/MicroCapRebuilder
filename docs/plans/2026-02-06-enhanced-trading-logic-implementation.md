# Enhanced Trading Logic Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform MicroCapRebuilder from a basic mechanical trading system into an intelligent, adaptive portfolio manager with 4-layer decision architecture (Risk, Opportunity, Portfolio, Execution) and fast learning system.

**Architecture:** Sequential layer processing - each layer takes actions from previous layer, applies intelligence, outputs modified actions. Layer 1 (Risk) re-evaluates positions and manages dynamic stops. Layer 2 (Opportunity) scores candidates with conviction-based sizing. Layer 3 (Portfolio) enforces diversification limits. Layer 4 (Execution) sequences trades strategically. Learning system tracks patterns and calibrates after every 5 trades.

**Tech Stack:** Python 3, pandas, yfinance, existing PortfolioState architecture, config-driven layer toggles

---

## Phase 1: Foundation - Data Structures & Configuration

### Task 1.1: Add Enhanced Trading Configuration

**Files:**
- Modify: `data/config.json`

**Step 1: Add enhanced_trading configuration section**

Add to `data/config.json`:

```json
{
  "enhanced_trading": {
    "enable_layers": true,
    "layer1": {
      "enable_reeval": true,
      "aggressiveness": "moderate",
      "min_score_drop_for_alert": 20,
      "min_score_drop_for_sell": 30,
      "enable_trailing_stops": true,
      "enable_volatility_stops": true,
      "trailing_stop_trigger_pct": 10.0,
      "trailing_stop_distance_pct": 8.0,
      "volatility_stop_high_atr": 10.0,
      "volatility_stop_low_atr": 6.0,
      "volatility_stop_atr_threshold_high": 5.0,
      "volatility_stop_atr_threshold_low": 2.0,
      "regime_stops": {
        "BULL": 8.0,
        "SIDEWAYS": 7.0,
        "BEAR": 6.0
      }
    },
    "layer2": {
      "enable_conviction": true,
      "min_conviction": 60,
      "enable_pattern_detection": true,
      "conviction_multiplier_max": 2.0,
      "conviction_thresholds": {
        "exceptional": 90,
        "strong": 80,
        "good": 70,
        "acceptable": 60
      },
      "conviction_multipliers": {
        "exceptional": 2.0,
        "strong": 1.5,
        "good": 1.0,
        "acceptable": 0.75
      },
      "conviction_adjustments": {
        "multiple_confirmations": 0.3,
        "breakout_pattern": 0.2,
        "fresh_high": 0.2,
        "regime_alignment": 0.2,
        "low_volatility": 0.1
      },
      "position_sizing": {
        "high_conviction_pct": 12.0,
        "medium_conviction_pct": 8.0,
        "low_conviction_pct": 5.0
      }
    },
    "layer3": {
      "enable_composition": true,
      "sector_limit_pct": 40.0,
      "correlation_threshold": 0.7,
      "max_correlated_positions": 3,
      "top3_limit_pct": 45.0,
      "correlation_lookback_days": 60,
      "enable_rebalancing": true,
      "rebalance_trigger_pct": 20.0,
      "rebalance_target_pct": 15.0
    },
    "layer4": {
      "enable_sequencing": true,
      "priorities": {
        "emergency_sell": 100,
        "deteriorating_sell_high": 90,
        "deteriorating_sell_medium": 70,
        "quality_degradation_sell": 60,
        "rebalancing_sell": 50,
        "high_conviction_buy": 85,
        "medium_conviction_buy": 65,
        "low_conviction_buy": 45
      }
    }
  },
  "learning": {
    "fast_pattern_learning": {
      "enabled": true,
      "min_trades_for_pattern": 5,
      "pattern_confidence_threshold": 0.6
    },
    "conviction_calibration": {
      "enabled": true,
      "recalibrate_every_n_trades": 10,
      "adjustment_step_pct": 10.0
    },
    "stop_optimization": {
      "enabled": true,
      "track_trailing_vs_fixed": true,
      "track_volatility_adjusted": true
    },
    "auto_tuning": {
      "enabled": true,
      "poor_performance_threshold": 0.5,
      "high_volatility_threshold": 3.0,
      "adjustment_magnitude": 5.0
    }
  }
}
```

**Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('data/config.json'))"`
Expected: No errors

**Step 3: Commit**

```bash
git add data/config.json
git commit -m "feat(config): add enhanced trading layer configuration

- Layer 1: Risk management (re-eval, dynamic stops)
- Layer 2: Opportunity (conviction, patterns, sizing)
- Layer 3: Portfolio composition (correlation, limits)
- Layer 4: Execution sequencing (priorities)
- Fast learning system configuration"
```

### Task 1.2: Create Enhanced Data Structures

**Files:**
- Create: `scripts/enhanced_structures.py`

**Step 1: Write data structures for layer outputs**

Create `scripts/enhanced_structures.py`:

```python
#!/usr/bin/env python3
"""
Enhanced data structures for 4-layer trading system.

Defines dataclasses for:
- Sell proposals with urgency scoring
- Buy proposals with conviction scoring
- Pattern signals
- Portfolio constraints
- Execution priorities
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class UrgencyLevel(Enum):
    """Urgency levels for sell signals."""
    EMERGENCY = "EMERGENCY"  # 90-100: Stop loss hit
    HIGH = "HIGH"  # 70-89: Pattern break + deterioration
    MEDIUM = "MEDIUM"  # 50-69: Score drop significant
    LOW = "LOW"  # <50: Monitoring only


class ConvictionLevel(Enum):
    """Conviction levels for buy signals."""
    EXCEPTIONAL = "EXCEPTIONAL"  # 90+
    STRONG = "STRONG"  # 80-89
    GOOD = "GOOD"  # 70-79
    ACCEPTABLE = "ACCEPTABLE"  # 60-69


class PatternType(Enum):
    """Entry/exit pattern types."""
    BREAKOUT = "BREAKOUT"
    PULLBACK = "PULLBACK"
    MOMENTUM_SURGE = "MOMENTUM_SURGE"
    REGIME_CATALYST = "REGIME_CATALYST"
    DETERIORATION = "DETERIORATION"
    VOLUME_DISTRIBUTION = "VOLUME_DISTRIBUTION"
    SUPPORT_BREAK = "SUPPORT_BREAK"


@dataclass
class PatternSignal:
    """Detected technical pattern."""
    pattern_type: PatternType
    confidence: float  # 0-100
    description: str
    detected_at_price: float


@dataclass
class DeteriorationSignal:
    """Position deterioration detection."""
    ticker: str
    entry_score: float
    current_score: float
    score_drop: float
    patterns_detected: List[PatternSignal] = field(default_factory=list)
    urgency_score: int = 0  # 0-100


@dataclass
class SellProposal:
    """Sell proposal from Layer 1."""
    ticker: str
    shares: int
    current_price: float
    reason: str
    urgency_level: UrgencyLevel
    urgency_score: int  # 0-100
    deterioration: Optional[DeteriorationSignal] = None
    stop_loss: float = 0.0
    take_profit: float = 0.0


@dataclass
class ConvictionScore:
    """Conviction scoring for buy candidates."""
    ticker: str
    composite_score: float  # Base 6-factor score
    conviction_multiplier: float  # 0.5-2.0
    final_conviction: float  # composite * multiplier (capped at 100)
    conviction_level: ConvictionLevel
    patterns_detected: List[PatternSignal] = field(default_factory=list)
    factors: Dict[str, float] = field(default_factory=dict)


@dataclass
class BuyProposal:
    """Buy proposal from Layer 2."""
    ticker: str
    shares: int
    price: float
    conviction_score: ConvictionScore
    position_size_pct: float  # % of portfolio
    stop_loss: float
    take_profit: float
    opportunity_score: int  # 0-100 (for Layer 4 prioritization)


@dataclass
class PortfolioConstraint:
    """Portfolio composition constraint violation."""
    constraint_type: str  # "sector_limit", "correlation_cluster", "position_overgrowth"
    severity: str  # "VETO", "REDUCE", "WARNING"
    description: str
    affected_ticker: str
    suggested_action: Optional[str] = None


@dataclass
class PrioritizedAction:
    """Action with execution priority."""
    action_type: str  # "BUY" or "SELL"
    ticker: str
    shares: int
    price: float
    priority_score: int  # 0-100 (higher = execute first)
    reason: str
    stop_loss: float = 0.0
    take_profit: float = 0.0
    # Link back to original proposal
    original_proposal: Optional[object] = None


@dataclass
class ExecutionPlan:
    """Final sequenced execution plan."""
    sequenced_actions: List[PrioritizedAction]
    initial_cash: float
    final_cash_estimate: float
    skipped_actions: List[Dict] = field(default_factory=list)
    execution_notes: List[str] = field(default_factory=list)


@dataclass
class StopLevels:
    """Dynamic stop loss levels for a position."""
    ticker: str
    current_price: float
    fixed_stop: float
    trailing_stop: Optional[float] = None
    volatility_adjusted_stop: Optional[float] = None
    regime_adjusted_stop: Optional[float] = None
    recommended_stop: float = 0.0  # Best stop to use
    stop_type: str = "fixed"  # "fixed", "trailing", "volatility", "regime"
```

**Step 2: Verify imports work**

Run: `python3 -c "import sys; sys.path.insert(0, 'scripts'); from enhanced_structures import *; print('OK')"`
Expected: "OK"

**Step 3: Commit**

```bash
git add scripts/enhanced_structures.py
git commit -m "feat(core): add enhanced data structures for 4-layer system

- Dataclasses for sell/buy proposals with scoring
- Pattern signal detection structures
- Portfolio constraint tracking
- Execution prioritization structures
- Stop level management structures"
```

---

## Phase 2: Layer 1 - Risk Management

### Task 2.1: Position Re-Evaluation

**Files:**
- Create: `scripts/risk_layer.py`

**Step 1: Create risk_layer.py with position re-evaluation**

Create `scripts/risk_layer.py`:

```python
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
```

**Step 2: Test basic import and instantiation**

Run: `python3 -c "import sys; sys.path.insert(0, 'scripts'); from risk_layer import RiskLayer; r = RiskLayer(); print('OK')"`
Expected: "OK"

**Step 3: Commit**

```bash
git add scripts/risk_layer.py
git commit -m "feat(layer1): add position re-evaluation logic

- Re-scores all current positions
- Detects score deterioration (20+ point drop alert, 30+ sell)
- Checks existing stop/target triggers
- Returns sell proposals with urgency scoring"
```

### Task 2.2: Dynamic Stop Loss Management

**Files:**
- Modify: `scripts/risk_layer.py`

**Step 1: Add dynamic stop calculation methods**

Add to `RiskLayer` class in `scripts/risk_layer.py`:

```python
    def calculate_dynamic_stops(self, state: PortfolioState) -> Dict[str, StopLevels]:
        """
        Calculate dynamic stop levels for all positions.

        Returns:
            Dict mapping ticker to StopLevels
        """
        if state.positions.empty:
            return {}

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

            volatility_stop = None
            if self.layer1_config.get("enable_volatility_stops", True):
                # Get ATR from score if available
                volatility_stop = self._calculate_volatility_stop(
                    current_price, entry_price, atr_pct=2.5  # TODO: Get real ATR
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
```

**Step 2: Update process() to use dynamic stops**

Replace the `process()` method to integrate dynamic stops:

```python
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
            entry_score = 70.0  # TODO: Load from transaction

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
```

**Step 3: Test dynamic stop calculation**

Run:
```python
python3 << 'EOF'
import sys
sys.path.insert(0, 'scripts')
from risk_layer import RiskLayer
from portfolio_state import load_portfolio_state

state = load_portfolio_state(fetch_prices=False)
layer = RiskLayer()
result = layer.process(state)
print(f"Sell proposals: {len(result['sell_proposals'])}")
print(f"Updated stops: {len(result['updated_stops'])}")
print("OK")
EOF
```

Expected: Prints counts and "OK"

**Step 4: Commit**

```bash
git add scripts/risk_layer.py
git commit -m "feat(layer1): add dynamic stop loss management

- Trailing stops (trigger at +10%, trail at -8%)
- Volatility-adjusted stops (wider for high ATR)
- Regime-aware stops (tighter in bear markets)
- Recommends most conservative stop across all types"
```

---

## Phase 3: Layer 2 - Opportunity Management

### Task 3.1: Conviction Scoring

**Files:**
- Create: `scripts/opportunity_layer.py`

**Step 1: Create opportunity_layer.py with conviction scoring**

Create `scripts/opportunity_layer.py`:

```python
#!/usr/bin/env python3
"""
Layer 2: Opportunity Management

Scores candidates with conviction levels, detects entry patterns,
sizes positions by conviction and volatility.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional

from enhanced_structures import (
    BuyProposal, ConvictionScore, ConvictionLevel,
    PatternSignal, PatternType
)
from stock_scorer import StockScorer, StockScore
from portfolio_state import PortfolioState, load_watchlist
from market_regime import MarketRegime, get_position_size_multiplier


DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load configuration."""
    with open(CONFIG_FILE) as f:
        return json.load(f)


class OpportunityLayer:
    """Layer 2: Opportunity Management - Conviction scoring and pattern detection."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize opportunity layer with configuration."""
        self.config = config or load_config()
        self.layer2_config = self.config.get("enhanced_trading", {}).get("layer2", {})
        self.enabled = self.layer2_config.get("enable_conviction", True)
        self.min_conviction = self.layer2_config.get("min_conviction", 60)

    def process(self, state: PortfolioState, risk_layer_output: Dict) -> Dict:
        """
        Process Layer 2: Score candidates with conviction, detect patterns.

        Args:
            state: Current portfolio state
            risk_layer_output: Output from Layer 1 (for context)

        Returns:
            dict with:
                - buy_proposals: List[BuyProposal]
                - conviction_scores: Dict[ticker, ConvictionScore]
        """
        if not self.enabled:
            return {
                "buy_proposals": [],
                "conviction_scores": {}
            }

        # Check if we can buy
        if state.regime == MarketRegime.BEAR:
            print("  ⚠️  Bear market - Layer 2 skipping new buys")
            return {"buy_proposals": [], "conviction_scores": {}}

        if state.num_positions >= self.config.get("max_positions", 15):
            print(f"  ⚠️  At max positions ({state.num_positions}) - Layer 2 skipping")
            return {"buy_proposals": [], "conviction_scores": {}}

        # Load and score watchlist
        watchlist = load_watchlist()
        current_tickers = set(state.positions["ticker"].tolist()) if not state.positions.empty else set()
        candidates = [t for t in watchlist if t not in current_tickers]

        if not candidates:
            return {"buy_proposals": [], "conviction_scores": {}}

        scorer = StockScorer(regime=state.regime)
        scored_results = scorer.score_watchlist(candidates)

        # Calculate conviction for each candidate
        conviction_scores = {}
        for stock_score in scored_results:
            if not stock_score:
                continue

            conviction = self.calculate_conviction(stock_score, state.regime)
            if conviction.final_conviction >= self.min_conviction:
                conviction_scores[stock_score.ticker] = conviction

        # Generate buy proposals
        buy_proposals = self._generate_buy_proposals(
            conviction_scores, state
        )

        return {
            "buy_proposals": buy_proposals,
            "conviction_scores": conviction_scores
        }

    def calculate_conviction(
        self, stock_score: StockScore, regime: MarketRegime
    ) -> ConvictionScore:
        """
        Calculate conviction score with multipliers.

        Args:
            stock_score: Base stock score from 6-factor model
            regime: Current market regime

        Returns:
            ConvictionScore with multiplier applied
        """
        composite = stock_score.composite_score

        # Base multiplier from score
        thresholds = self.layer2_config.get("conviction_thresholds", {})
        multipliers = self.layer2_config.get("conviction_multipliers", {})

        if composite >= thresholds.get("exceptional", 90):
            base_multiplier = multipliers.get("exceptional", 2.0)
            level = ConvictionLevel.EXCEPTIONAL
        elif composite >= thresholds.get("strong", 80):
            base_multiplier = multipliers.get("strong", 1.5)
            level = ConvictionLevel.STRONG
        elif composite >= thresholds.get("good", 70):
            base_multiplier = multipliers.get("good", 1.0)
            level = ConvictionLevel.GOOD
        else:
            base_multiplier = multipliers.get("acceptable", 0.75)
            level = ConvictionLevel.ACCEPTABLE

        # Adjustments
        adjustments = self.layer2_config.get("conviction_adjustments", {})
        multiplier = base_multiplier

        # Multiple confirmations (momentum + volume + RS all strong)
        if self._check_multiple_confirmations(stock_score):
            multiplier += adjustments.get("multiple_confirmations", 0.3)

        # Pattern detection
        patterns = self._detect_entry_patterns(stock_score)
        if patterns:
            for pattern in patterns:
                if pattern.pattern_type == PatternType.BREAKOUT:
                    multiplier += adjustments.get("breakout_pattern", 0.2)
                elif pattern.pattern_type == PatternType.MOMENTUM_SURGE:
                    multiplier += adjustments.get("fresh_high", 0.2)

        # Regime alignment
        if self._check_regime_alignment(stock_score, regime):
            multiplier += adjustments.get("regime_alignment", 0.2)

        # Low volatility
        if stock_score.atr_pct < 2.0:
            multiplier += adjustments.get("low_volatility", 0.1)

        # Cap multiplier
        max_multiplier = self.layer2_config.get("conviction_multiplier_max", 2.0)
        multiplier = min(multiplier, max_multiplier)

        # Calculate final conviction
        final_conviction = min(100, composite * multiplier)

        return ConvictionScore(
            ticker=stock_score.ticker,
            composite_score=composite,
            conviction_multiplier=multiplier,
            final_conviction=final_conviction,
            conviction_level=level,
            patterns_detected=patterns,
            factors={
                "momentum": stock_score.momentum_score,
                "volatility": stock_score.volatility_score,
                "volume": stock_score.volume_score,
                "relative_strength": stock_score.relative_strength_score,
                "mean_reversion": stock_score.mean_reversion_score,
                "rsi": stock_score.rsi_score,
            }
        )

    def _check_multiple_confirmations(self, stock_score: StockScore) -> bool:
        """Check if momentum + volume + RS all strong."""
        return (
            stock_score.momentum_score >= 70 and
            stock_score.volume_score >= 70 and
            stock_score.relative_strength_score >= 70
        )

    def _detect_entry_patterns(self, stock_score: StockScore) -> List[PatternSignal]:
        """Detect entry patterns (breakout, momentum surge, etc.)."""
        patterns = []

        # Breakout: Fresh 20-day high + high volume
        # TODO: Implement actual pattern detection with price history
        # For now, use proxy signals from stock_score metadata
        if stock_score.momentum_20d > 10 and stock_score.volume_score > 75:
            patterns.append(PatternSignal(
                pattern_type=PatternType.BREAKOUT,
                confidence=80,
                description="20-day momentum surge with high volume",
                detected_at_price=stock_score.current_price
            ))

        # Momentum surge: Strong momentum alignment
        if stock_score.momentum_alignment == "ALIGNED":
            patterns.append(PatternSignal(
                pattern_type=PatternType.MOMENTUM_SURGE,
                confidence=75,
                description="Multi-timeframe momentum alignment",
                detected_at_price=stock_score.current_price
            ))

        return patterns

    def _check_regime_alignment(self, stock_score: StockScore, regime: MarketRegime) -> bool:
        """Check if stock aligns with market regime."""
        if regime == MarketRegime.BULL:
            # Bull market: Want high momentum stocks
            return stock_score.momentum_score >= 70
        elif regime == MarketRegime.SIDEWAYS:
            # Sideways: Want mean reversion plays
            return stock_score.mean_reversion_score >= 70
        else:
            # Bear: Want defensive (low vol, high quality)
            return stock_score.volatility_score >= 70

    def _generate_buy_proposals(
        self, conviction_scores: Dict[str, ConvictionScore], state: PortfolioState
    ) -> List[BuyProposal]:
        """Generate buy proposals with conviction-based position sizing."""
        proposals = []

        # Sort by final conviction
        sorted_convictions = sorted(
            conviction_scores.values(),
            key=lambda x: x.final_conviction,
            reverse=True
        )

        # Position sizing config
        sizing = self.layer2_config.get("position_sizing", {})
        high_conviction_pct = sizing.get("high_conviction_pct", 12.0) / 100
        medium_conviction_pct = sizing.get("medium_conviction_pct", 8.0) / 100
        low_conviction_pct = sizing.get("low_conviction_pct", 5.0) / 100

        # Regime multiplier
        position_multiplier = get_position_size_multiplier(state.regime)

        # Calculate position sizes
        slots_available = self.config.get("max_positions", 15) - state.num_positions
        remaining_cash = state.cash

        for conviction in sorted_convictions[:slots_available]:
            # Determine position size by conviction
            if conviction.final_conviction >= 80:
                size_pct = high_conviction_pct
            elif conviction.final_conviction >= 70:
                size_pct = medium_conviction_pct
            else:
                size_pct = low_conviction_pct

            # Apply regime multiplier and cap at max
            size_pct = min(size_pct * position_multiplier, self.config.get("max_position_pct", 15.0) / 100)
            position_value = min(state.total_equity * size_pct, remaining_cash)

            price = conviction.ticker  # TODO: Get actual price
            # For now, skip actual pricing - will integrate in next task

        return proposals
```

**Step 2: Test conviction scoring**

Run:
```python
python3 << 'EOF'
import sys
sys.path.insert(0, 'scripts')
from opportunity_layer import OpportunityLayer
from portfolio_state import load_portfolio_state

state = load_portfolio_state(fetch_prices=False)
layer = OpportunityLayer()
result = layer.process(state, {})
print(f"Buy proposals: {len(result['buy_proposals'])}")
print(f"Conviction scores: {len(result['conviction_scores'])}")
print("OK")
EOF
```

Expected: Prints counts and "OK"

**Step 3: Commit**

```bash
git add scripts/opportunity_layer.py
git commit -m "feat(layer2): add conviction scoring system

- Base multiplier from composite score (0.75x-2.0x)
- Adjustments for confirmations, patterns, regime alignment
- Conviction levels (EXCEPTIONAL, STRONG, GOOD, ACCEPTABLE)
- Entry pattern detection (breakout, momentum surge)
- Conviction-based position sizing (5-15% of portfolio)"
```

---

## Incremental Implementation Approach

This plan documents Phases 1-2 (Foundation + Layer 1: Risk Management) in complete detail. Remaining phases will be planned incrementally after we:

1. **Implement and test Phase 1-2** (config + data structures + risk layer)
2. **Integrate Layer 1 with unified_analysis.py** and test with real portfolio
3. **Learn from results** - Does position re-evaluation work? Are dynamic stops effective?
4. **Plan Phase 3-4** (Layers 2-3) based on learnings
5. **Repeat** - build, test, learn, plan next phase

**Remaining Phases (to be detailed later):**
- **Phase 3**: Layer 2 completion (pattern detection, position sizing, buy proposals)
- **Phase 4**: Layer 3 (correlation analysis, sector limits, portfolio constraints)
- **Phase 5**: Layer 4 (execution sequencing, priority scoring, cash tracking)
- **Phase 6**: Integration (refactor unified_analysis.py to orchestrate all 4 layers)
- **Phase 7**: Learning system (pattern learning, conviction calibration, auto-tuning)
- **Phase 8**: Testing & validation (parallel paper trading, metrics, dashboard integration)

**Why incremental?**
- Faster time to results (see if Layer 1 helps before building Layers 2-4)
- Learn from real implementation (adapt design based on what works)
- Avoid over-planning (60+ tasks planned upfront likely to change)
- More agile iteration (build → test → learn → adapt)

**Current scope:** Phases 1-2 (8 tasks) - Foundation + Risk Management Layer