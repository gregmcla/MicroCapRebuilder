#!/usr/bin/env python3
"""
Avatar State Manager for Mommy Bot

Determines which avatar expression to display based on portfolio conditions.
Integrates with the dashboard to show contextually appropriate expressions.

States:
- NEUTRAL: Default calm, confident look
- PLEASED: Warm smile when things are going well
- CONCERNED: Alert expression when positions need attention
- SKEPTICAL: Raised eyebrow in uncertain market conditions
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


class AvatarState(Enum):
    """Avatar expression states."""
    NEUTRAL = "neutral"
    PLEASED = "pleased"
    CONCERNED = "concerned"
    SKEPTICAL = "skeptical"


@dataclass
class AvatarContext:
    """Context data for determining avatar state."""
    day_pnl: float = 0.0
    day_pnl_pct: float = 0.0
    total_return_pct: float = 0.0
    positions_near_stop: int = 0
    positions_near_target: int = 0
    regime: str = "UNKNOWN"
    drawdown_pct: float = 0.0
    num_positions: int = 0
    win_rate: float = 0.0
    consecutive_losses: int = 0
    consecutive_wins: int = 0


def determine_avatar_state(context: AvatarContext) -> AvatarState:
    """
    Determine the appropriate avatar expression based on portfolio state.

    Priority order (highest to lowest):
    1. CONCERNED - Risk situations that need attention
    2. PLEASED - Positive situations worth celebrating
    3. SKEPTICAL - Uncertain/cautious situations
    4. NEUTRAL - Default state

    Args:
        context: AvatarContext with portfolio metrics

    Returns:
        AvatarState enum value
    """

    # ─── CONCERNED triggers (highest priority) ───────────────────────────────
    # These are situations that need the user's attention

    # Multiple positions near stop loss
    if context.positions_near_stop >= 2:
        return AvatarState.CONCERNED

    # Significant drawdown
    if context.drawdown_pct > 10:
        return AvatarState.CONCERNED

    # Bad day (down more than 2%)
    if context.day_pnl_pct < -2.0:
        return AvatarState.CONCERNED

    # Losing streak
    if context.consecutive_losses >= 3:
        return AvatarState.CONCERNED

    # ─── PLEASED triggers ────────────────────────────────────────────────────
    # Celebrate the wins!

    # Positions approaching targets
    if context.positions_near_target >= 2:
        return AvatarState.PLEASED

    # Great day (up more than 2%)
    if context.day_pnl_pct > 2.0:
        return AvatarState.PLEASED

    # Good absolute P&L
    if context.day_pnl > 500:
        return AvatarState.PLEASED

    # Winning streak
    if context.consecutive_wins >= 3:
        return AvatarState.PLEASED

    # Strong overall performance
    if context.total_return_pct > 10 and context.win_rate > 60:
        return AvatarState.PLEASED

    # ─── SKEPTICAL triggers ──────────────────────────────────────────────────
    # Uncertain or cautious situations

    # Bear market
    if context.regime == "BEAR":
        return AvatarState.SKEPTICAL

    # Sideways/choppy market
    if context.regime == "SIDEWAYS":
        return AvatarState.SKEPTICAL

    # One position near stop (not critical but worth noting)
    if context.positions_near_stop == 1:
        return AvatarState.SKEPTICAL

    # Moderate drawdown
    if context.drawdown_pct > 5:
        return AvatarState.SKEPTICAL

    # Low win rate
    if context.win_rate > 0 and context.win_rate < 40:
        return AvatarState.SKEPTICAL

    # ─── NEUTRAL (default) ───────────────────────────────────────────────────
    return AvatarState.NEUTRAL


def determine_avatar_state_simple(
    day_pnl: float = 0.0,
    positions_near_stop: int = 0,
    positions_near_target: int = 0,
    regime: str = "UNKNOWN",
    drawdown_pct: float = 0.0
) -> AvatarState:
    """
    Simplified version for quick state determination.

    Args:
        day_pnl: Today's P&L in dollars
        positions_near_stop: Count of positions within 5% of stop loss
        positions_near_target: Count of positions within 10% of take profit
        regime: Market regime (BULL, BEAR, SIDEWAYS)
        drawdown_pct: Current drawdown percentage

    Returns:
        AvatarState enum value
    """
    context = AvatarContext(
        day_pnl=day_pnl,
        positions_near_stop=positions_near_stop,
        positions_near_target=positions_near_target,
        regime=regime,
        drawdown_pct=drawdown_pct
    )
    return determine_avatar_state(context)


def get_state_description(state: AvatarState) -> str:
    """Get a human-readable description of what the avatar state means."""
    descriptions = {
        AvatarState.NEUTRAL: "All systems normal. Mommy is calmly watching over your portfolio.",
        AvatarState.PLEASED: "Things are looking good! Mommy is happy with your progress.",
        AvatarState.CONCERNED: "Heads up - some positions need attention. Mommy is keeping a close eye.",
        AvatarState.SKEPTICAL: "Market conditions are uncertain. Mommy suggests caution.",
    }
    return descriptions.get(state, descriptions[AvatarState.NEUTRAL])


def get_state_color(state: AvatarState) -> str:
    """Get the accent color associated with avatar state."""
    colors = {
        AvatarState.NEUTRAL: "#4FD1C5",   # Teal
        AvatarState.PLEASED: "#48BB78",   # Green
        AvatarState.CONCERNED: "#F56565", # Red
        AvatarState.SKEPTICAL: "#ED8936", # Orange
    }
    return colors.get(state, colors[AvatarState.NEUTRAL])


# ─── Test ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Avatar State Manager")
    print("=" * 50)

    # Test cases
    test_cases = [
        ("Default state", AvatarContext()),
        ("Great day", AvatarContext(day_pnl=1000, day_pnl_pct=3.5)),
        ("Near targets", AvatarContext(positions_near_target=3)),
        ("Near stops", AvatarContext(positions_near_stop=2)),
        ("Bear market", AvatarContext(regime="BEAR")),
        ("Big drawdown", AvatarContext(drawdown_pct=12)),
        ("Losing streak", AvatarContext(consecutive_losses=4)),
        ("Winning streak", AvatarContext(consecutive_wins=5, win_rate=70)),
    ]

    for name, context in test_cases:
        state = determine_avatar_state(context)
        print(f"\n{name}:")
        print(f"  State: {state.value}")
        print(f"  Description: {get_state_description(state)}")
