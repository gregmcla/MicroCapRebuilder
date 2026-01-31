#!/usr/bin/env python3
"""
Webapp Helpers - Mommy's Voice & Visual Components

Helper functions for the dashboard including:
- Smart status sentence generation with Mommy's personality
- Position progress bar calculations
- Time-based greetings
- Contextual phrase generation
"""

import random
from datetime import datetime
from typing import Optional
import pandas as pd

# ─── Mommy Voice Phrase Library ───────────────────────────────────────────────

MOMMY_PHRASES = {
    # All-clear states - calm and reassuring
    "all_clear": [
        "Everything's running smoothly.",
        "I've got things under control.",
        "All systems healthy - nothing needs your attention.",
        "Portfolio's humming along nicely.",
        "Looking good. I'm keeping watch.",
    ],

    # Positive states - warm celebration
    "good_day": [
        "Nice day! Up ${amount}.",
        "Looking good today - we're up ${amount}.",
        "Green vibes today. +${amount}.",
        "A good day! Up ${amount}.",
    ],

    # Near stop - protective concern
    "near_stop_single": [
        "Heads up - {ticker} is getting close to its stop.",
        "Keep an eye on {ticker}, it's only {pct:.1f}% from stop.",
        "Watching {ticker} carefully - approaching stop level.",
        "{ticker} needs attention - {pct:.1f}% from stop.",
    ],

    "near_stop_multiple": [
        "{count} positions are approaching stop levels.",
        "A few positions need watching - {count} near their stops.",
        "Heads up on {count} positions getting close to stops.",
    ],

    # Near target - excited but calm
    "near_target": [
        "Good news - {ticker} is approaching target!",
        "{ticker} is only {pct:.1f}% from take-profit.",
        "Almost there! {ticker} nearing target.",
        "{ticker} looking strong - {pct:.1f}% to target.",
    ],

    # Market conditions
    "bear_market": [
        "Markets are choppy. Staying cautious.",
        "Bear conditions - I'm being extra careful.",
        "Rough markets. Playing it safe.",
    ],

    "sideways_market": [
        "Markets are indecisive. Staying patient.",
        "Sideways action today. Waiting for clarity.",
    ],

    # Drawdown states - supportive
    "drawdown_mild": [
        "We're {pct:.1f}% below peak. Staying disciplined.",
        "Small pullback - down {pct:.1f}% from high. Normal.",
    ],

    "drawdown_significant": [
        "Down {pct:.1f}% from peak. Hanging in there.",
        "Rough patch - {pct:.1f}% drawdown. Patience.",
    ],

    # Capital preservation - protective
    "preservation_mode": [
        "Capital preservation mode active. Safety first.",
        "Playing defense right now. Protecting what we have.",
        "Preservation mode on. Being extra careful.",
    ],

    # Bad day - supportive
    "bad_day": [
        "Tough day - down ${amount}. Tomorrow's another day.",
        "Red day, down ${amount}. It happens.",
        "Down ${amount} today. Part of the journey.",
    ],

    # Empty portfolio
    "no_positions": [
        "No positions yet. Ready when you are.",
        "Portfolio is empty. Standing by.",
        "All cash. Waiting for the right opportunities.",
    ],
}


def get_greeting() -> str:
    """Get time-appropriate greeting."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 22:
        return "Good evening"
    else:
        return "Hello"


def get_positions_near_stop(positions_df: pd.DataFrame, threshold_pct: float = 5.0) -> list:
    """
    Get positions within threshold_pct of stop loss.

    Returns list of dicts with ticker, distance_pct, current, stop.
    """
    if positions_df.empty:
        return []

    result = []
    for _, row in positions_df.iterrows():
        stop = row.get('stop_loss', 0)
        current = row.get('current_price', 0)
        if stop and current and stop > 0:
            distance_pct = ((current - stop) / current) * 100
            if 0 < distance_pct <= threshold_pct:
                result.append({
                    'ticker': row['ticker'],
                    'distance_pct': distance_pct,
                    'current': current,
                    'stop': stop
                })
    return sorted(result, key=lambda x: x['distance_pct'])


def get_positions_near_target(positions_df: pd.DataFrame, threshold_pct: float = 8.0) -> list:
    """
    Get positions within threshold_pct of take profit.

    Returns list of dicts with ticker, distance_pct, current, target.
    """
    if positions_df.empty:
        return []

    result = []
    for _, row in positions_df.iterrows():
        target = row.get('take_profit', 0)
        current = row.get('current_price', 0)
        if target and current and target > 0:
            distance_pct = ((target - current) / current) * 100
            if 0 < distance_pct <= threshold_pct:
                result.append({
                    'ticker': row['ticker'],
                    'distance_pct': distance_pct,
                    'current': current,
                    'target': target
                })
    return sorted(result, key=lambda x: x['distance_pct'])


def generate_status_sentence(
    positions_df: pd.DataFrame,
    snapshots_df: pd.DataFrame,
    day_pnl: float,
    regime: Optional[str] = None,
    preservation_active: bool = False,
    drawdown_pct: float = 0,
) -> tuple:
    """
    Generate smart status sentence based on current state.

    Returns: (sentence: str, sentiment: str)
    sentiment is one of: 'calm', 'positive', 'attention', 'warning'
    """

    # Priority 1: Capital preservation mode (highest alert)
    if preservation_active:
        return (
            random.choice(MOMMY_PHRASES["preservation_mode"]),
            "warning"
        )

    # Priority 2: No positions
    if positions_df.empty:
        return (
            random.choice(MOMMY_PHRASES["no_positions"]),
            "calm"
        )

    # Priority 3: Positions very close to stop loss
    near_stop = get_positions_near_stop(positions_df, threshold_pct=3.0)
    if near_stop:
        if len(near_stop) == 1:
            phrase = random.choice(MOMMY_PHRASES["near_stop_single"])
            return (
                phrase.format(ticker=near_stop[0]['ticker'], pct=near_stop[0]['distance_pct']),
                "attention"
            )
        else:
            phrase = random.choice(MOMMY_PHRASES["near_stop_multiple"])
            return (
                phrase.format(count=len(near_stop)),
                "attention"
            )

    # Priority 4: Positions approaching take profit (positive!)
    near_target = get_positions_near_target(positions_df, threshold_pct=5.0)
    if near_target:
        phrase = random.choice(MOMMY_PHRASES["near_target"])
        return (
            phrase.format(ticker=near_target[0]['ticker'], pct=near_target[0]['distance_pct']),
            "positive"
        )

    # Priority 5: Market regime
    if regime == "BEAR":
        return (
            random.choice(MOMMY_PHRASES["bear_market"]),
            "attention"
        )

    # Priority 6: Significant drawdown
    if drawdown_pct >= 10:
        phrase = random.choice(MOMMY_PHRASES["drawdown_significant"])
        return (phrase.format(pct=drawdown_pct), "attention")
    elif drawdown_pct >= 5:
        phrase = random.choice(MOMMY_PHRASES["drawdown_mild"])
        return (phrase.format(pct=drawdown_pct), "calm")

    # Priority 7: Today's performance
    if day_pnl > 50:
        phrase = random.choice(MOMMY_PHRASES["good_day"])
        return (phrase.replace("${amount}", f"${day_pnl:,.0f}"), "positive")
    elif day_pnl < -50:
        phrase = random.choice(MOMMY_PHRASES["bad_day"])
        return (phrase.replace("${amount}", f"${abs(day_pnl):,.0f}"), "attention")

    # Default: All clear
    return (
        random.choice(MOMMY_PHRASES["all_clear"]),
        "calm"
    )


def calculate_position_progress(row: pd.Series) -> Optional[dict]:
    """
    Calculate where current price sits between stop loss and take profit.

    The progress bar shows:
    - 0% = at stop loss (bad)
    - 50% ≈ at entry (neutral)
    - 100% = at take profit (great)

    Returns:
        {
            'progress_pct': 0-100,
            'zone': 'danger' | 'caution' | 'neutral' | 'winning' | 'near_target',
            'stop_distance_pct': float,
            'target_distance_pct': float,
            'current_price': float,
            'stop_loss': float,
            'take_profit': float,
            'entry_price': float
        }
    """
    try:
        current = float(row.get('current_price', 0))
        stop = float(row.get('stop_loss', 0))
        target = float(row.get('take_profit', 0))
        entry = float(row.get('avg_cost_basis', 0))

        if not all([current, stop, target]) or target <= stop:
            return None

        # Calculate progress: 0% = at stop, 100% = at target
        range_total = target - stop
        current_from_stop = current - stop
        progress_pct = (current_from_stop / range_total) * 100
        progress_pct = max(0, min(100, progress_pct))  # Clamp to 0-100

        # Determine zone based on progress
        if progress_pct <= 12:
            zone = 'danger'      # Very close to stop - red alert
        elif progress_pct <= 30:
            zone = 'caution'     # Below entry, needs watching - yellow
        elif progress_pct <= 55:
            zone = 'neutral'     # Around entry - gray
        elif progress_pct <= 85:
            zone = 'winning'     # Solidly profitable - green
        else:
            zone = 'near_target' # Close to take profit - bright green, pulsing

        # Calculate distances as percentages
        stop_distance_pct = ((current - stop) / current) * 100 if current > 0 else 0
        target_distance_pct = ((target - current) / current) * 100 if current > 0 else 0

        return {
            'progress_pct': progress_pct,
            'zone': zone,
            'stop_distance_pct': stop_distance_pct,
            'target_distance_pct': target_distance_pct,
            'current_price': current,
            'stop_loss': stop,
            'take_profit': target,
            'entry_price': entry
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def render_position_progress_bar(progress: Optional[dict]) -> str:
    """Generate HTML for position progress bar."""
    if not progress:
        return ""

    pct = progress['progress_pct']
    zone = progress['zone']
    stop = progress['stop_loss']
    target = progress['take_profit']
    entry = progress.get('entry_price', 0)

    # Calculate entry marker position (if entry is between stop and target)
    entry_marker = ""
    if stop < entry < target:
        entry_pct = ((entry - stop) / (target - stop)) * 100
        entry_marker = f'<div class="progress-entry-marker" style="left: {entry_pct}%;"></div>'

    return f'''
    <div class="position-progress-container">
        <span class="progress-label-left">${stop:.0f}</span>
        <div class="progress-track">
            {entry_marker}
            <div class="progress-marker {zone}" style="left: {pct}%;"></div>
        </div>
        <span class="progress-label-right">${target:.0f}</span>
    </div>
    '''


def get_position_status_text(progress: Optional[dict]) -> str:
    """Get a short status text for a position based on its progress."""
    if not progress:
        return ""

    zone = progress['zone']

    zone_texts = {
        'danger': "Near stop",
        'caution': "Watch",
        'neutral': "",
        'winning': "Winning",
        'near_target': "Near target!"
    }

    return zone_texts.get(zone, "")


def format_pnl(value: float, include_sign: bool = True) -> tuple:
    """
    Format P&L value for display.
    Returns: (formatted_string, css_class)
    """
    if value >= 0:
        sign = "+" if include_sign else ""
        return (f"{sign}${value:,.2f}", "positive")
    else:
        return (f"-${abs(value):,.2f}", "negative")


def format_pct(value: float, include_sign: bool = True) -> tuple:
    """
    Format percentage for display.
    Returns: (formatted_string, css_class)
    """
    if value >= 0:
        sign = "+" if include_sign else ""
        return (f"{sign}{value:.1f}%", "positive")
    else:
        return (f"{value:.1f}%", "negative")
