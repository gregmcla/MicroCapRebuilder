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
# Warm, direct, occasionally teasing - always in command

MOMMY_PHRASES = {
    # All-clear states - calm, confident, a touch playful
    "all_clear": [
        "All quiet on the western front. Go enjoy your coffee.",
        "Nothing's on fire. I'll holler if that changes.",
        "Smooth sailing, sweetie. Mommy's got this.",
        "Portfolio's humming along nicely. Just the way I like it.",
        "Looking good out there. I'm keeping watch.",
        "Everything's in order. You can breathe.",
        "Steady as she goes. Nothing needs your attention right now.",
    ],

    # Positive states - warm celebration with personality
    "good_day": [
        "Look at us! Up ${amount} today.",
        "Nice work, sweetie. We're up ${amount}.",
        "Green across the board - +${amount}. Love to see it.",
        "What a day! Up ${amount}. Pat yourself on the back.",
        "The market's being kind today. +${amount}.",
        "Well well, up ${amount}. Someone's having a good day.",
    ],

    # Near stop - protective concern with personality
    "near_stop_single": [
        "Heads up - {ticker} is getting a little too close to the edge for my taste.",
        "Keep an eye on {ticker}, sweetie. Only {pct:.1f}% from stop.",
        "I don't love where {ticker} is sitting. {pct:.1f}% from stop.",
        "{ticker} is making me nervous - watching it like a hawk.",
        "Fair warning: {ticker} is {pct:.1f}% from stop. Don't say I didn't tell you.",
    ],

    "near_stop_multiple": [
        "{count} positions are getting uncomfortably close to stops. Let's pay attention.",
        "Sweetie, we've got {count} positions in the danger zone. Stay sharp.",
        "Mommy's a bit concerned - {count} positions near their stops.",
        "Red alert on {count} positions. Time to focus.",
    ],

    # Near target - excited, proud
    "near_target": [
        "Look at you! {ticker} is almost at the finish line.",
        "{ticker} is knocking on the door - only {pct:.1f}% from target!",
        "Get ready to celebrate - {ticker} is {pct:.1f}% from take-profit.",
        "Almost there, sweetie! {ticker} nearing target.",
        "{ticker} is looking gorgeous right now. {pct:.1f}% to payday.",
        "Time to start thinking about taking some chips off {ticker}.",
    ],

    # Market conditions - direct and knowing
    "bear_market": [
        "The bears are out, sweetie. We're playing defense.",
        "Rough neighborhood out there. Keeping positions tight.",
        "Bear market vibes. Not the time for heroics.",
        "Markets are in a mood. Staying cautious.",
    ],

    "sideways_market": [
        "Markets can't make up their mind. Patience.",
        "Choppy waters today. Waiting for clarity.",
        "Sideways action. Not my favorite, but we adapt.",
        "The market's being indecisive. That's fine - so are we.",
    ],

    # Drawdown states - supportive but real
    "drawdown_mild": [
        "We're {pct:.1f}% off the highs. Nothing to panic about.",
        "Small pullback - down {pct:.1f}%. Part of the game.",
        "Down {pct:.1f}% from peak. Staying disciplined.",
        "Little setback at {pct:.1f}% drawdown. We've seen worse.",
    ],

    "drawdown_significant": [
        "Okay, {pct:.1f}% drawdown is getting my attention. Tightening up.",
        "Down {pct:.1f}% from peak. Hang in there with me.",
        "Not gonna sugarcoat it - {pct:.1f}% drawdown. But we'll get through.",
        "Rough patch. {pct:.1f}% down. Let's be smart about this.",
    ],

    # Capital preservation - protective mama bear
    "preservation_mode": [
        "Preservation mode is on. We're protecting what we've got.",
        "Safety first, sweetie. I've put up the shields.",
        "Time to play defense. Capital preservation active.",
        "I've switched to mama bear mode. No unnecessary risks.",
    ],

    # Bad day - supportive, not dismissive
    "bad_day": [
        "Tough day - down ${amount}. Tomorrow's a fresh start.",
        "Red day, down ${amount}. It happens to the best of us.",
        "Down ${amount} today. Not fun, but not the end of the world.",
        "Ouch - ${amount} in the red. Let's shake it off.",
        "Market giveth, market taketh. Down ${amount} today.",
    ],

    # Empty portfolio
    "no_positions": [
        "All cash, sitting pretty. Ready when you are.",
        "No positions yet. Just say the word.",
        "Portfolio's empty. Waiting for the right dance partner.",
        "Fully liquid. Let's find some opportunities.",
    ],

    # Great day - proud mama
    "great_day": [
        "Now THIS is a day! Up ${amount}. I'm so proud.",
        "Killing it! +${amount}. You should be smiling.",
        "What a beauty - up ${amount}. Let's keep this energy.",
        "Chef's kiss. Up ${amount} today.",
    ],

    # Winning streak - celebratory
    "winning_streak": [
        "{count} wins in a row! Don't let it go to your head, sweetie.",
        "We're on a roll - {count} consecutive wins. Stay humble.",
        "Hot streak! {count} wins. Let's keep the momentum.",
    ],

    # Losing streak - tough love
    "losing_streak": [
        "{count} losses in a row. Let's regroup and refocus.",
        "Rough stretch - {count} consecutive stops hit. We'll bounce back.",
        "Not our week. {count} losses. Time to tighten up.",
    ],

    # Teasing - for when user checks too often
    "teasing": [
        "Back already? The market doesn't move that fast, sweetie.",
        "Checking again? I promise I'll tell you if something happens.",
        "You know I've got this, right? Go take a walk.",
        "The portfolio's fine. You're the one I'm worried about.",
        "Third check this hour? Someone's anxious today.",
    ],

    # Position-specific callouts
    "position_callout": [
        "Keep an eye on {ticker} - it's been moving.",
        "{ticker} is doing its thing. Looking healthy.",
        "Watching {ticker} closely today.",
    ],
}


def get_greeting() -> str:
    """Get time-appropriate greeting with personality."""
    hour = datetime.now().hour

    morning_greetings = [
        "Good morning, sweetie!",
        "Morning! Let's see what we've got.",
        "Rise and shine! Ready to make some money?",
        "Good morning! Coffee first, then charts.",
    ]

    afternoon_greetings = [
        "Good afternoon!",
        "Afternoon check-in time.",
        "Hey there! How's the day treating you?",
        "Back for a midday peek?",
    ]

    evening_greetings = [
        "Evening, love. Let's see what the market left on our doorstep.",
        "Good evening! Time for the daily wrap-up.",
        "Evening check-in. Let's see how we did.",
        "Hey sweetie. Let's review the day.",
    ]

    night_greetings = [
        "Burning the midnight oil?",
        "Late night trading thoughts?",
        "Can't sleep without checking the portfolio?",
        "Night owl mode activated.",
    ]

    if 5 <= hour < 12:
        return random.choice(morning_greetings)
    elif 12 <= hour < 17:
        return random.choice(afternoon_greetings)
    elif 17 <= hour < 22:
        return random.choice(evening_greetings)
    else:
        return random.choice(night_greetings)


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
