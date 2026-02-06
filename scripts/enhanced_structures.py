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
