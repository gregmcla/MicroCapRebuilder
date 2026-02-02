#!/usr/bin/env python3
"""
Reusable Components for Mommy Bot Dashboard.

Provides modular UI components following the design system:
- Hero Metrics Ribbon with sparklines
- Position Cards with progress bars
- Portfolio Treemap
- Mommy Companion Sidebar
- Enhanced Equity Curve

Usage:
    from webapp_components import (
        render_metrics_ribbon,
        render_position_cards,
        render_mommy_sidebar,
    )
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from webapp_styles import COLORS, inject_styles
from avatar_svg import get_avatar_svg, AvatarState as AvatarStateType
from avatar_states import AvatarState, determine_avatar_state_simple


# ─── Sparkline Generation ─────────────────────────────────────────────────────

def generate_sparkline_svg(values: List[float], width: int = 100, height: int = 24, color: str = None) -> str:
    """
    Generate an inline SVG sparkline.

    Args:
        values: List of numeric values
        width: SVG width in pixels
        height: SVG height in pixels
        color: Line color (defaults to accent teal)

    Returns:
        SVG string
    """
    if not values or len(values) < 2:
        return ""

    color = color or COLORS["accent_teal"]

    # Normalize values to fit in height
    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val if max_val != min_val else 1

    # Calculate points
    points = []
    for i, val in enumerate(values):
        x = (i / (len(values) - 1)) * width
        y = height - ((val - min_val) / val_range) * height * 0.8 - height * 0.1
        points.append(f"{x:.1f},{y:.1f}")

    points_str = " ".join(points)

    # Determine if trending up or down
    is_up = values[-1] >= values[0]
    line_color = COLORS["success"] if is_up else COLORS["danger"]

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
        <polyline
            points="{points_str}"
            fill="none"
            stroke="{line_color}"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
        />
    </svg>'''

    return svg


# ─── Metrics Ribbon ───────────────────────────────────────────────────────────

def render_metrics_ribbon(
    total_equity: float,
    day_pnl: float,
    day_pnl_pct: float,
    cash: float,
    regime: str,
    equity_history: List[float] = None,
    pnl_history: List[float] = None,
    cash_history: List[float] = None
):
    """
    Render the hero metrics ribbon with 4 key metrics and sparklines.
    """
    # Generate sparklines
    equity_sparkline = generate_sparkline_svg(equity_history or [])
    pnl_sparkline = generate_sparkline_svg(pnl_history or [])
    cash_sparkline = generate_sparkline_svg(cash_history or [])

    # Format values
    equity_str = f"${total_equity:,.2f}"
    pnl_sign = "+" if day_pnl >= 0 else ""
    pnl_str = f"{pnl_sign}${day_pnl:,.2f}"
    pnl_pct_str = f"({pnl_sign}{day_pnl_pct:.2f}%)"
    cash_str = f"${cash:,.2f}"

    # Regime emoji
    regime_display = {
        "BULL": ("BULL", "bull"),
        "BEAR": ("BEAR", "bear"),
        "SIDEWAYS": ("SIDEWAYS", "sideways")
    }.get(regime, ("--", ""))

    pnl_class = "positive" if day_pnl >= 0 else "negative"

    html = '<div class="metrics-ribbon">'

    # Total Equity
    html += '<div class="metric-hero">'
    html += f'<div class="metric-value">{equity_str}</div>'
    html += '<div class="metric-label">Total Equity</div>'
    if equity_sparkline:
        html += f'<div class="metric-sparkline">{equity_sparkline}</div>'
    html += '</div>'

    # Day P&L
    html += '<div class="metric-hero">'
    html += f'<div class="metric-value {pnl_class}">{pnl_str}</div>'
    html += f'<div class="metric-label">Today {pnl_pct_str}</div>'
    if pnl_sparkline:
        html += f'<div class="metric-sparkline">{pnl_sparkline}</div>'
    html += '</div>'

    # Cash
    html += '<div class="metric-hero">'
    html += f'<div class="metric-value">{cash_str}</div>'
    html += '<div class="metric-label">Cash Available</div>'
    if cash_sparkline:
        html += f'<div class="metric-sparkline">{cash_sparkline}</div>'
    html += '</div>'

    # Regime
    html += '<div class="metric-hero">'
    html += f'<div class="metric-value">{regime_display[0]}</div>'
    html += '<div class="metric-label">Market Regime</div>'
    html += '</div>'

    html += '</div>'

    st.markdown(html, unsafe_allow_html=True)


# ─── Position Cards ───────────────────────────────────────────────────────────

def calculate_position_progress(current: float, stop: float, target: float) -> float:
    """Calculate position progress as percentage between stop and target."""
    if target == stop:
        return 50.0

    progress = (current - stop) / (target - stop) * 100
    return max(0, min(100, progress))


def render_position_cards(positions_df: pd.DataFrame, cols_per_row: int = 3):
    """
    Render positions as cards instead of a table.

    Args:
        positions_df: DataFrame with position data
        cols_per_row: Number of cards per row
    """
    if positions_df.empty:
        st.info("No open positions")
        return

    st.markdown('<div class="position-grid">', unsafe_allow_html=True)

    cards_html = ""
    for _, pos in positions_df.iterrows():
        ticker = pos.get("ticker", "???")
        pnl = pos.get("unrealized_pnl", 0)
        pnl_pct = pos.get("unrealized_pnl_pct", 0)
        current_price = pos.get("current_price", 0)
        stop_loss = pos.get("stop_loss", current_price * 0.92)
        take_profit = pos.get("take_profit", current_price * 1.20)

        # Calculate progress
        progress = calculate_position_progress(current_price, stop_loss, take_profit)

        # Check proximity to stop/target
        near_stop = progress < 15
        near_target = progress > 85

        pnl_class = "positive" if pnl >= 0 else "negative"
        pnl_sign = "+" if pnl >= 0 else ""
        card_class = "near-stop" if near_stop else ("near-target" if near_target else "")

        cards_html += f'<div class="position-card {card_class}">'
        cards_html += f'<div class="position-symbol">{ticker}</div>'
        cards_html += f'<div class="position-pnl {pnl_class}">{pnl_sign}${abs(pnl):,.2f} ({pnl_sign}{pnl_pct:.1f}%)</div>'
        cards_html += '<div class="position-progress">'
        cards_html += '<div class="position-progress-track"></div>'
        cards_html += f'<div class="position-progress-marker" style="left: {progress:.1f}%"></div>'
        cards_html += '</div>'
        cards_html += '<div class="position-labels">'
        cards_html += f'<span>Stop ${stop_loss:.2f}</span>'
        cards_html += f'<span>${current_price:.2f}</span>'
        cards_html += f'<span>Target ${take_profit:.2f}</span>'
        cards_html += '</div>'
        cards_html += '</div>'

    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)


# ─── Portfolio Treemap ────────────────────────────────────────────────────────

def render_portfolio_treemap(positions_df: pd.DataFrame):
    """
    Render portfolio composition as a treemap (replaces donut chart).
    """
    if not PLOTLY_AVAILABLE:
        st.warning("Plotly not available for treemap")
        return

    if positions_df.empty:
        st.info("No positions for treemap")
        return

    # Prepare data
    df = positions_df.copy()

    # Add sector if missing
    if "sector" not in df.columns:
        df["sector"] = "Unknown"

    # Ensure required columns
    if "market_value" not in df.columns:
        df["market_value"] = df.get("current_price", 0) * df.get("shares", 0)

    if "unrealized_pnl_pct" not in df.columns:
        df["unrealized_pnl_pct"] = 0

    # Create treemap
    fig = px.treemap(
        df,
        path=["sector", "ticker"],
        values="market_value",
        color="unrealized_pnl_pct",
        color_continuous_scale=[
            [0, COLORS["danger"]],
            [0.5, COLORS["text_muted"]],
            [1, COLORS["success"]]
        ],
        color_continuous_midpoint=0,
        hover_data=["market_value", "unrealized_pnl_pct"]
    )

    fig.update_layout(
        margin=dict(t=0, l=0, r=0, b=0),
        paper_bgcolor=COLORS["bg_primary"],
        font_color=COLORS["text_primary"],
        height=300,
        coloraxis_showscale=False
    )

    fig.update_traces(
        textfont=dict(color=COLORS["text_primary"]),
        hovertemplate="<b>%{label}</b><br>Value: $%{value:,.2f}<br>P&L: %{color:.1f}%<extra></extra>"
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─── Enhanced Equity Curve ────────────────────────────────────────────────────

def render_equity_curve(snapshots_df: pd.DataFrame, height: int = 300):
    """
    Render equity curve with gradient fill.
    """
    if not PLOTLY_AVAILABLE:
        st.warning("Plotly not available for equity curve")
        return

    if snapshots_df.empty:
        st.info("No data for equity curve")
        return

    df = snapshots_df.copy()

    # Ensure we have required columns
    date_col = "date" if "date" in df.columns else df.columns[0]
    equity_col = "total_equity" if "total_equity" in df.columns else df.columns[1]

    fig = go.Figure()

    # Add gradient fill area
    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=df[equity_col],
        fill='tozeroy',
        fillcolor='rgba(79, 209, 197, 0.15)',
        line=dict(color=COLORS["accent_teal"], width=2),
        mode='lines',
        name='Equity'
    ))

    # Add starting capital line if we can determine it
    if len(df) > 0:
        start_equity = df[equity_col].iloc[0]
        fig.add_hline(
            y=start_equity,
            line_dash="dash",
            line_color=COLORS["text_muted"],
            annotation_text="Start",
            annotation_position="left"
        )

    fig.update_layout(
        paper_bgcolor=COLORS["bg_primary"],
        plot_bgcolor=COLORS["bg_primary"],
        font_color=COLORS["text_secondary"],
        height=height,
        margin=dict(t=20, l=60, r=20, b=40),
        xaxis=dict(
            gridcolor=COLORS["border"],
            showgrid=True,
            zeroline=False
        ),
        yaxis=dict(
            gridcolor=COLORS["border"],
            showgrid=True,
            zeroline=False,
            tickformat="$,.0f"
        ),
        showlegend=False,
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─── Mommy Companion Sidebar ──────────────────────────────────────────────────

import random

def get_time_greeting() -> str:
    """Get a time-appropriate greeting with personality."""
    hour = datetime.now().hour

    morning = [
        "Good morning, sweetie!",
        "Morning! Let's see what we've got.",
        "Rise and shine!",
    ]
    afternoon = [
        "Good afternoon!",
        "Hey there!",
        "Afternoon check-in time.",
    ]
    evening = [
        "Evening, love.",
        "Good evening!",
        "Hey sweetie.",
    ]
    night = [
        "Burning the midnight oil?",
        "Late night trading thoughts?",
        "Can't sleep?",
    ]

    if 5 <= hour < 12:
        return random.choice(morning)
    elif 12 <= hour < 17:
        return random.choice(afternoon)
    elif 17 <= hour < 22:
        return random.choice(evening)
    else:
        return random.choice(night)


def get_mommy_greeting(
    day_pnl: float = 0,
    positions_near_stop: int = 0,
    positions_near_target: int = 0,
    regime: str = "UNKNOWN",
    drawdown_pct: float = 0
) -> str:
    """Generate a context-aware greeting from Mommy with personality."""

    # Time-based greeting
    base = get_time_greeting()
    parts = [base]

    # Priority 1: Positions near stop (concern)
    if positions_near_stop >= 2:
        parts.append(f"We've got {positions_near_stop} positions getting too close to stops. Let's pay attention.")
    elif positions_near_stop == 1:
        parts.append("One position is making me nervous - keep an eye out.")

    # Priority 2: Positions near target (celebration)
    elif positions_near_target >= 2:
        parts.append(f"Look at us! {positions_near_target} positions approaching targets.")
    elif positions_near_target == 1:
        parts.append("One of our positions is almost at the finish line!")

    # Priority 3: Day performance
    elif day_pnl > 500:
        parts.append("What a day! We're killing it.")
    elif day_pnl > 100:
        parts.append("Looking good today. I like what I see.")
    elif day_pnl > 0:
        parts.append("We're in the green. Steady as she goes.")
    elif day_pnl < -500:
        parts.append("Rough day, I won't lie. But we'll bounce back.")
    elif day_pnl < -100:
        parts.append("A bit of red today. Nothing we can't handle.")
    elif day_pnl < 0:
        parts.append("Slight dip. No need to panic.")

    # Priority 4: Market regime
    elif regime == "BEAR":
        parts.append("The bears are out. Playing it safe.")
    elif regime == "SIDEWAYS":
        parts.append("Markets are choppy. Patience is key.")
    else:
        # Default - encouraging
        encouraging = [
            "I've got my eyes on everything.",
            "All systems normal.",
            "Smooth sailing so far.",
            "Let's make some money.",
        ]
        parts.append(random.choice(encouraging))

    return " ".join(parts)


def render_mommy_sidebar(
    day_pnl: float = 0,
    insights: List[str] = None,
    positions_near_stop: int = 0,
    positions_near_target: int = 0,
    regime: str = "UNKNOWN",
    drawdown_pct: float = 0
):
    """
    Render the Mommy companion sidebar with dynamic avatar.

    The avatar expression changes based on portfolio state:
    - neutral: Default calm look
    - pleased: When things are going well
    - concerned: When positions need attention
    - skeptical: In uncertain market conditions
    """
    # Determine avatar state
    avatar_state = determine_avatar_state_simple(
        day_pnl=day_pnl,
        positions_near_stop=positions_near_stop,
        positions_near_target=positions_near_target,
        regime=regime,
        drawdown_pct=drawdown_pct
    )

    # Get greeting with context
    greeting = get_mommy_greeting(
        day_pnl=day_pnl,
        positions_near_stop=positions_near_stop,
        positions_near_target=positions_near_target,
        regime=regime,
        drawdown_pct=drawdown_pct
    )
    insights = insights or []

    # Get SVG avatar for current state
    avatar_svg = get_avatar_svg(avatar_state.value, size=80)

    html = '<div class="mommy-sidebar">'

    # Avatar with breathing animation
    html += '<div class="mommy-avatar-container">'
    html += avatar_svg
    html += '</div>'

    # Greeting bubble
    html += f'<div class="mommy-greeting">"{greeting}"</div>'

    # Recent insights
    if insights:
        html += '<div class="mommy-insights">'
        html += '<div class="mommy-insights-title">Recent Insights</div>'
        for insight in insights[:5]:
            html += f'<div class="mommy-insight">{insight}</div>'
        html += '</div>'

    html += '</div>'

    st.markdown(html, unsafe_allow_html=True)


# ─── Command Zone ─────────────────────────────────────────────────────────────

def render_command_zone(is_live: bool = True):
    """
    Render the floating command pill bar.

    Note: This renders the visual shell. Actual buttons are rendered
    by Streamlit separately due to interactivity requirements.
    """
    status_class = "live" if is_live else "paper"
    status_text = "LIVE" if is_live else "PAPER"

    html = '<div class="command-zone">'
    html += '<div class="command-pill">'
    html += f'<span class="status-dot {status_class}"></span>'
    html += f'<span style="color: var(--text-primary); font-weight: 600; margin-right: 16px;">{status_text}</span>'
    # Buttons are rendered by Streamlit
    html += '</div>'
    html += '</div>'

    st.markdown(html, unsafe_allow_html=True)


# ─── Top Bar ──────────────────────────────────────────────────────────────────

def render_top_bar(is_live: bool = True):
    """Render the minimal top bar with logo and status."""
    status_class = "live" if is_live else "paper"

    html = '<div class="mommy-topbar">'
    html += '<div class="mommy-logo">'
    html += '<div class="mommy-logo-icon">M</div>'
    html += '<span>MOMMY</span>'
    html += '</div>'
    html += '<div style="display: flex; align-items: center; gap: 12px;">'
    html += f'<span class="status-dot {status_class}"></span>'
    html += '<span style="color: var(--text-secondary); font-size: 12px;">Connected</span>'
    html += '</div>'
    html += '</div>'

    st.markdown(html, unsafe_allow_html=True)


# ─── Section Header ───────────────────────────────────────────────────────────

def render_section_header(title: str, badge: str = None):
    """Render a section header with optional badge."""
    html = '<div class="section-head">'
    html += f'<span class="section-title">{title}</span>'
    if badge:
        html += f'<span class="mommy-card-badge">{badge}</span>'
    html += '</div>'

    st.markdown(html, unsafe_allow_html=True)


# ─── Card Wrapper ─────────────────────────────────────────────────────────────

def card_start(title: str = None, badge: str = None) -> None:
    """Start a card container."""
    html = '<div class="mommy-card">'
    if title:
        html += '<div class="mommy-card-header">'
        html += f'<span class="mommy-card-title">{title}</span>'
        if badge:
            html += f'<span class="mommy-card-badge">{badge}</span>'
        html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def card_end() -> None:
    """End a card container."""
    st.markdown('</div>', unsafe_allow_html=True)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test components
    print("Mommy Bot Components")
    print("=" * 50)

    # Test sparkline
    test_values = [100, 105, 103, 110, 115, 112, 120]
    svg = generate_sparkline_svg(test_values)
    print(f"\nSparkline SVG length: {len(svg)} chars")

    # Test greeting
    greeting = get_mommy_greeting(day_pnl=150, positions_near_target=2)
    print(f"\nSample greeting: {greeting}")
