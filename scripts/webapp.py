#!/usr/bin/env python3
"""
M O M M Y — Autonomous Trading Intelligence

A warm, nurturing command center for your portfolio.
She watches over your investments so you don't have to.

Run with: streamlit run scripts/webapp.py
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
import sys

sys.path.insert(0, str(Path(__file__).parent))

# Load .env BEFORE importing modules that need it
try:
    from dotenv import load_dotenv
    for env_path in [
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
        Path.home() / "MicroCapRebuilder" / ".env",
    ]:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            break
except ImportError:
    pass

from analytics import PortfolioAnalytics
from trade_analyzer import TradeAnalyzer
from market_regime import get_regime_analysis, MarketRegime
from risk_scoreboard import get_risk_scoreboard
from capital_preservation import get_preservation_status
from portfolio_chat import chat as ai_chat, check_setup as check_chat_setup
from portfolio_intelligence import run_intelligence, SAFETY_RAILS
from webapp_helpers import (
    generate_status_sentence,
    calculate_position_progress,
    render_position_progress_bar,
    get_positions_near_stop,
    get_positions_near_target,
    format_pnl,
    format_pct,
)

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"starting_capital": 50000.0}


def is_paper_mode():
    config = load_config()
    return config.get("mode", "live") == "paper"


def set_paper_mode(enabled: bool):
    config = load_config()
    config["mode"] = "paper" if enabled else "live"
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_data_files():
    suffix = "_paper" if is_paper_mode() else ""
    return {
        "positions": DATA_DIR / f"positions{suffix}.csv",
        "transactions": DATA_DIR / f"transactions{suffix}.csv",
        "snapshots": DATA_DIR / f"daily_snapshots{suffix}.csv",
    }


def load_positions():
    files = get_data_files()
    if not files["positions"].exists():
        return pd.DataFrame()
    return pd.read_csv(files["positions"])


def load_transactions():
    files = get_data_files()
    if not files["transactions"].exists():
        return pd.DataFrame()
    return pd.read_csv(files["transactions"])


def load_snapshots():
    files = get_data_files()
    if not files["snapshots"].exists():
        return pd.DataFrame()
    return pd.read_csv(files["snapshots"])


def calculate_cash():
    config = load_config()
    transactions_df = load_transactions()
    if transactions_df.empty:
        return config["starting_capital"]
    buys = transactions_df[transactions_df["action"] == "BUY"]["total_value"].sum()
    sells = transactions_df[transactions_df["action"] == "SELL"]["total_value"].sum()
    return config["starting_capital"] - buys + sells


# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MOMMY",
    page_icon="💚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

paper_mode = is_paper_mode()
mode_class = "paper-mode" if paper_mode else "live-mode"

# ─── Mommy's Design System CSS ────────────────────────────────────────────────
st.markdown(f"""
<div class="{mode_class}">
""", unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

:root {
    --void: #0a0a0f;
    --deep: #12121a;
    --surface: #1a1a24;
    --elevated: #22222e;
    --border-subtle: rgba(255, 255, 255, 0.06);
    --border-visible: rgba(255, 255, 255, 0.12);

    --text-primary: rgba(255, 255, 255, 0.95);
    --text-secondary: rgba(255, 255, 255, 0.70);
    --text-tertiary: rgba(255, 255, 255, 0.45);
    --text-ghost: rgba(255, 255, 255, 0.25);

    --mommy-green: #4ade80;
    --mommy-green-soft: rgba(74, 222, 128, 0.15);
    --mommy-red: #f87171;
    --mommy-red-soft: rgba(248, 113, 113, 0.15);
    --mommy-gold: #fbbf24;
    --mommy-gold-soft: rgba(251, 191, 36, 0.15);
    --mommy-blue: #60a5fa;
    --mommy-blue-soft: rgba(96, 165, 250, 0.12);
}

/* ─── Base ─────────────────────────────────────────────────────────────────── */
.stApp {
    background: var(--void);
    background-image: radial-gradient(ellipse 100% 60% at 50% -10%, rgba(74, 222, 128, 0.03) 0%, transparent 50%);
}

* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

#MainMenu, footer, header, [data-testid="stToolbar"], .stDeployButton {
    display: none !important;
}

.block-container {
    padding: 1.5rem 2rem 3rem 2rem !important;
    max-width: 1200px !important;
}

/* ─── Hero Card (Act 1) ────────────────────────────────────────────────────── */
.hero-card {
    text-align: center;
    padding: 2.5rem 2rem 2rem 2rem;
    position: relative;
    margin-bottom: 0;
}

.hero-card::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
}

.hero-card.calm::before {
    background: radial-gradient(ellipse at center, var(--mommy-blue-soft) 0%, transparent 60%);
}
.hero-card.positive::before {
    background: radial-gradient(ellipse at center, var(--mommy-green-soft) 0%, transparent 60%);
}
.hero-card.attention::before {
    background: radial-gradient(ellipse at center, var(--mommy-gold-soft) 0%, transparent 60%);
}
.hero-card.warning::before {
    background: radial-gradient(ellipse at center, var(--mommy-red-soft) 0%, transparent 60%);
}

.hero-name {
    font-size: 0.7rem;
    letter-spacing: 0.4rem;
    color: var(--text-tertiary);
    text-transform: uppercase;
    margin-bottom: 0.75rem;
}

.hero-equity {
    font-size: 3.5rem;
    font-weight: 300;
    color: var(--text-primary);
    letter-spacing: -0.02em;
    line-height: 1;
    margin-bottom: 0.5rem;
}

.hero-delta {
    font-size: 1rem;
    font-weight: 500;
    padding: 0.35rem 1rem;
    border-radius: 100px;
    display: inline-block;
    margin-bottom: 1.25rem;
}

.hero-delta.positive {
    color: var(--mommy-green);
    background: var(--mommy-green-soft);
}
.hero-delta.negative {
    color: var(--mommy-red);
    background: var(--mommy-red-soft);
}

.hero-status {
    font-size: 0.95rem;
    color: var(--text-secondary);
    font-weight: 400;
    max-width: 400px;
    margin: 0 auto;
    line-height: 1.5;
}

.hero-mode-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    margin-top: 1rem;
    padding: 0.3rem 0.8rem;
    font-size: 0.6rem;
    letter-spacing: 0.1rem;
    text-transform: uppercase;
    border-radius: 2px;
}

.hero-mode-badge.live {
    background: var(--mommy-green-soft);
    color: var(--mommy-green);
}
.hero-mode-badge.paper {
    background: var(--mommy-gold-soft);
    color: var(--mommy-gold);
}

.mode-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
}
.mode-dot.live { background: var(--mommy-green); }
.mode-dot.paper { background: var(--mommy-gold); }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

/* ─── Context Bar (Act 2) ──────────────────────────────────────────────────── */
.context-bar {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    padding: 1rem 0;
    margin: 0 auto 1.5rem auto;
    border-top: 1px solid var(--border-subtle);
    border-bottom: 1px solid var(--border-subtle);
}

.context-chip {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    background: var(--surface);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
}

.context-icon {
    font-size: 1rem;
}

.context-value {
    font-size: 0.95rem;
    font-weight: 500;
    color: var(--text-primary);
}

.context-label {
    font-size: 0.6rem;
    letter-spacing: 0.1rem;
    color: var(--text-tertiary);
    text-transform: uppercase;
    margin-left: 0.25rem;
}

/* ─── Section Headers ──────────────────────────────────────────────────────── */
.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 1.5rem 0 1rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-subtle);
}

.section-title {
    font-size: 0.7rem;
    letter-spacing: 0.15rem;
    color: var(--text-secondary);
    text-transform: uppercase;
}

.section-badge {
    font-size: 0.65rem;
    color: var(--text-tertiary);
    padding: 0.2rem 0.6rem;
    background: var(--deep);
    border-radius: 100px;
}

.section-badge.attention {
    color: var(--mommy-gold);
    background: var(--mommy-gold-soft);
}

.section-badge.positive {
    color: var(--mommy-green);
    background: var(--mommy-green-soft);
}

/* ─── Position Cards ──────────────────────────────────────────────────────── */
.position-card {
    background: var(--surface);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
    transition: border-color 0.2s ease;
}

.position-card:hover {
    border-color: var(--border-visible);
}

.position-card.attention {
    border-left: 3px solid var(--mommy-gold);
}

.position-card.winning {
    border-left: 3px solid var(--mommy-green);
}

.position-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.5rem;
}

.position-ticker {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
}

.position-status {
    font-size: 0.65rem;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.05rem;
}

.position-status.danger {
    background: var(--mommy-red-soft);
    color: var(--mommy-red);
}
.position-status.caution {
    background: var(--mommy-gold-soft);
    color: var(--mommy-gold);
}
.position-status.winning {
    background: var(--mommy-green-soft);
    color: var(--mommy-green);
}
.position-status.near_target {
    background: var(--mommy-green-soft);
    color: var(--mommy-green);
    animation: pulse 1.5s ease-in-out infinite;
}

.position-details {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
}

.position-pnl {
    font-size: 1rem;
    font-weight: 500;
}
.position-pnl.positive { color: var(--mommy-green); }
.position-pnl.negative { color: var(--mommy-red); }

/* ─── Progress Bar ─────────────────────────────────────────────────────────── */
.position-progress-container {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.75rem;
}

.progress-label-left, .progress-label-right {
    font-size: 0.65rem;
    color: var(--text-ghost);
    min-width: 35px;
}
.progress-label-right {
    text-align: right;
}

.progress-track {
    flex: 1;
    height: 4px;
    background: linear-gradient(90deg,
        var(--mommy-red) 0%,
        var(--mommy-red) 12%,
        var(--mommy-gold) 12%,
        var(--mommy-gold) 30%,
        var(--text-ghost) 30%,
        var(--text-ghost) 55%,
        var(--mommy-green) 55%,
        var(--mommy-green) 100%
    );
    border-radius: 2px;
    position: relative;
}

.progress-marker {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 10px;
    height: 10px;
    background: var(--text-primary);
    border: 2px solid var(--void);
    border-radius: 50%;
    box-shadow: 0 0 6px rgba(255, 255, 255, 0.3);
}

.progress-marker.danger { background: var(--mommy-red); }
.progress-marker.caution { background: var(--mommy-gold); }
.progress-marker.winning { background: var(--mommy-green); }
.progress-marker.near_target {
    background: var(--mommy-green);
    box-shadow: 0 0 10px var(--mommy-green);
}

.progress-entry-marker {
    position: absolute;
    top: -3px;
    width: 2px;
    height: 10px;
    background: var(--text-tertiary);
    transform: translateX(-50%);
}

/* ─── Recommendation Cards ─────────────────────────────────────────────────── */
.rec-card {
    background: var(--surface);
    border-radius: 6px;
    padding: 1rem;
    margin-bottom: 0.5rem;
}

.rec-card.buy { border-left: 3px solid var(--mommy-green); }
.rec-card.sell { border-left: 3px solid var(--mommy-red); }
.rec-card.hold { border-left: 3px solid var(--text-ghost); opacity: 0.7; }
.rec-card.blocked { opacity: 0.5; }

.rec-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.4rem;
}

.rec-action {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-primary);
}

.rec-ticker {
    font-size: 0.9rem;
    color: var(--text-secondary);
}

.rec-reason {
    font-size: 0.75rem;
    color: var(--text-tertiary);
    line-height: 1.4;
}

/* ─── Transaction List ─────────────────────────────────────────────────────── */
.tx-row {
    display: flex;
    align-items: center;
    padding: 0.6rem 0;
    border-bottom: 1px solid var(--border-subtle);
}
.tx-row:last-child { border-bottom: none; }

.tx-action {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.05rem;
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    min-width: 35px;
    text-align: center;
}
.tx-action.buy { background: var(--mommy-green-soft); color: var(--mommy-green); }
.tx-action.sell { background: var(--mommy-red-soft); color: var(--mommy-red); }

.tx-ticker {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-left: 0.75rem;
    min-width: 60px;
}

.tx-details {
    font-size: 0.75rem;
    color: var(--text-tertiary);
    flex: 1;
    margin-left: 0.5rem;
}

.tx-date {
    font-size: 0.7rem;
    color: var(--text-ghost);
}

/* ─── Metric Cards ─────────────────────────────────────────────────────────── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
    margin: 1rem 0;
}

.metric-card {
    background: var(--surface);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    padding: 1rem;
    text-align: center;
}

.metric-value {
    font-size: 1.3rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 0.25rem;
}

.metric-value.positive { color: var(--mommy-green); }
.metric-value.negative { color: var(--mommy-red); }

.metric-label {
    font-size: 0.6rem;
    letter-spacing: 0.1rem;
    color: var(--text-tertiary);
    text-transform: uppercase;
}

/* ─── Buttons ──────────────────────────────────────────────────────────────── */
.stButton > button {
    background: var(--surface) !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border-visible) !important;
    border-radius: 6px !important;
    padding: 0.6rem 1.5rem !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.1rem !important;
    text-transform: uppercase !important;
    transition: all 0.2s ease !important;
}

.stButton > button:hover {
    background: var(--elevated) !important;
    border-color: var(--mommy-green) !important;
    color: var(--text-primary) !important;
}

.stButton > button[kind="primary"] {
    background: var(--mommy-green-soft) !important;
    border-color: var(--mommy-green) !important;
    color: var(--mommy-green) !important;
}

.stButton > button[kind="primary"]:hover {
    background: rgba(74, 222, 128, 0.25) !important;
}

/* Paper mode overrides */
.paper-mode .stButton > button:hover {
    border-color: var(--mommy-gold) !important;
}
.paper-mode .stButton > button[kind="primary"] {
    background: var(--mommy-gold-soft) !important;
    border-color: var(--mommy-gold) !important;
    color: var(--mommy-gold) !important;
}

/* ─── Expanders ────────────────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background: var(--surface) !important;
    border-radius: 6px !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.1rem !important;
}

/* ─── Chat Input ───────────────────────────────────────────────────────────── */
.stTextInput > div > div > input {
    background: var(--surface) !important;
    border: 1px solid var(--border-visible) !important;
    border-radius: 6px !important;
    color: var(--text-primary) !important;
}

/* ─── Empty State ──────────────────────────────────────────────────────────── */
.empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-tertiary);
}

.empty-state-text {
    font-size: 0.8rem;
    color: var(--text-tertiary);
}

/* ─── Footer ───────────────────────────────────────────────────────────────── */
.mommy-footer {
    text-align: center;
    padding: 2rem 0 1rem 0;
    margin-top: 2rem;
    border-top: 1px solid var(--border-subtle);
}

.footer-text {
    font-size: 0.55rem;
    letter-spacing: 0.2rem;
    color: var(--text-ghost);
    text-transform: uppercase;
}

/* ─── Scrollbar ────────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--void); }
::-webkit-scrollbar-thumb { background: var(--border-visible); border-radius: 2px; }

/* ─── Responsive ───────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
    .hero-equity { font-size: 2.5rem; }
    .context-bar { gap: 0.4rem; }
    .context-chip { padding: 0.4rem 0.75rem; }
    .metric-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
""", unsafe_allow_html=True)


# ─── Load All Data ────────────────────────────────────────────────────────────
config = load_config()
positions_df = load_positions()
transactions_df = load_transactions()
snapshots_df = load_snapshots()
cash = calculate_cash()

positions_value = positions_df["market_value"].sum() if not positions_df.empty else 0
total_equity = positions_value + cash
starting_capital = config.get("starting_capital", 50000.0)
total_return_pct = ((total_equity - starting_capital) / starting_capital) * 100
num_positions = len(positions_df) if not positions_df.empty else 0
max_positions = config.get("max_positions", 15)
exposure_pct = (positions_value / total_equity * 100) if total_equity > 0 else 0
day_pnl = snapshots_df.iloc[-1].get("day_pnl", 0) if not snapshots_df.empty else 0

# Get additional context
try:
    regime_analysis = get_regime_analysis()
    regime = regime_analysis.regime.value
except:
    regime = "UNKNOWN"

try:
    preservation = get_preservation_status()
    preservation_active = preservation.active
except:
    preservation_active = False

try:
    risk_score = get_risk_scoreboard()
    drawdown_pct = abs(risk_score.components[1].value) if len(risk_score.components) > 1 else 0
except:
    drawdown_pct = 0

# Generate smart status sentence
status_sentence, sentiment = generate_status_sentence(
    positions_df, snapshots_df, day_pnl,
    regime=regime,
    preservation_active=preservation_active,
    drawdown_pct=drawdown_pct
)


# ═══════════════════════════════════════════════════════════════════════════════
# ACT 1: THE HERO STATUS CARD
# ═══════════════════════════════════════════════════════════════════════════════

delta_class = "positive" if total_return_pct >= 0 else "negative"
delta_sign = "+" if total_return_pct >= 0 else ""
mode_text = "PAPER" if paper_mode else "LIVE"
mode_style = "paper" if paper_mode else "live"

st.markdown(f"""
<div class="hero-card {sentiment}">
    <div class="hero-name">M O M M Y</div>
    <div class="hero-equity">${total_equity:,.0f}</div>
    <div class="hero-delta {delta_class}">{delta_sign}{total_return_pct:.1f}% all-time</div>
    <div class="hero-status">{status_sentence}</div>
    <div class="hero-mode-badge {mode_style}">
        <span class="mode-dot {mode_style}"></span>
        {mode_text}
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ACT 2: THE CONTEXT BAR
# ═══════════════════════════════════════════════════════════════════════════════

regime_icons = {"BULL": "🐂", "BEAR": "🐻", "SIDEWAYS": "↔️", "UNKNOWN": "❓"}
regime_icon = regime_icons.get(regime, "❓")
day_sign = "+" if day_pnl >= 0 else ""
day_color = "var(--mommy-green)" if day_pnl >= 0 else "var(--mommy-red)"

st.markdown(f"""
<div class="context-bar">
    <div class="context-chip">
        <span class="context-icon">{regime_icon}</span>
        <span class="context-value">{regime}</span>
        <span class="context-label">Market</span>
    </div>
    <div class="context-chip">
        <span class="context-value">{exposure_pct:.0f}%</span>
        <span class="context-label">Deployed</span>
    </div>
    <div class="context-chip">
        <span class="context-value">{num_positions}</span>
        <span class="context-label">Positions</span>
    </div>
    <div class="context-chip">
        <span class="context-value" style="color: {day_color};">{day_sign}${abs(day_pnl):,.0f}</span>
        <span class="context-label">Today</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ACT 3: THE DETAIL CARDS
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Positions Section ────────────────────────────────────────────────────────
near_stop_positions = get_positions_near_stop(positions_df, threshold_pct=5.0)
near_target_positions = get_positions_near_target(positions_df, threshold_pct=8.0)

badge_text = f"{num_positions} active"
badge_class = ""
if near_stop_positions:
    badge_text = f"{len(near_stop_positions)} need attention"
    badge_class = "attention"
elif near_target_positions:
    badge_text = f"{len(near_target_positions)} near target"
    badge_class = "positive"

st.markdown(f"""
<div class="section-header">
    <span class="section-title">Positions</span>
    <span class="section-badge {badge_class}">{badge_text}</span>
</div>
""", unsafe_allow_html=True)

if not positions_df.empty:
    # Sort: attention items first, then by P&L
    positions_sorted = positions_df.copy()
    positions_sorted['_sort_priority'] = positions_sorted.apply(
        lambda r: 0 if r['ticker'] in [p['ticker'] for p in near_stop_positions] else 1, axis=1
    )
    positions_sorted = positions_sorted.sort_values(['_sort_priority', 'unrealized_pnl_pct'], ascending=[True, False])

    for _, row in positions_sorted.iterrows():
        progress = calculate_position_progress(row)
        zone = progress['zone'] if progress else 'neutral'

        # Card styling based on zone
        card_class = ""
        if zone in ['danger', 'caution']:
            card_class = "attention"
        elif zone in ['winning', 'near_target']:
            card_class = "winning"

        # Status badge
        status_text = ""
        if zone == 'danger':
            status_text = "NEAR STOP"
        elif zone == 'caution':
            status_text = "WATCH"
        elif zone == 'near_target':
            status_text = "NEAR TARGET"
        elif zone == 'winning':
            status_text = "WINNING"

        # P&L formatting
        pnl = row['unrealized_pnl']
        pnl_pct = row['unrealized_pnl_pct']
        pnl_class = "positive" if pnl >= 0 else "negative"
        pnl_sign = "+" if pnl >= 0 else ""

        # Progress bar values
        if progress:
            stop_price = progress['stop_loss']
            target_price = progress['take_profit']
            marker_pct = progress['progress_pct']
            marker_zone = progress['zone']
        else:
            stop_price = 0
            target_price = 0
            marker_pct = 50
            marker_zone = 'neutral'

        # Build HTML as single line to avoid Streamlit parsing issues
        status_html = f'<span class="position-status {zone}">{status_text}</span>' if status_text else ''

        html = f'<div class="position-card {card_class}">'
        html += f'<div class="position-header"><span class="position-ticker">{row["ticker"]}</span>{status_html}</div>'
        html += f'<div class="position-details">{int(row["shares"])} shares @ ${row["avg_cost_basis"]:.2f} → ${row["current_price"]:.2f}</div>'
        html += f'<div class="position-pnl {pnl_class}">{pnl_sign}${abs(pnl):.2f} ({pnl_sign}{pnl_pct:.1f}%)</div>'

        if progress:
            html += f'<div class="position-progress-container">'
            html += f'<span class="progress-label-left">${stop_price:.0f}</span>'
            html += f'<div class="progress-track"><div class="progress-marker {marker_zone}" style="left: {marker_pct}%;"></div></div>'
            html += f'<span class="progress-label-right">${target_price:.0f}</span>'
            html += f'</div>'

        html += '</div>'

        st.markdown(html, unsafe_allow_html=True)

    # Total unrealized P&L
    total_unrealized = positions_df["unrealized_pnl"].sum()
    total_class = "positive" if total_unrealized >= 0 else "negative"
    st.markdown(f'<div style="text-align: right; margin: 1rem 0; padding-top: 0.5rem; border-top: 1px solid var(--border-subtle);"><span style="color: var(--text-tertiary); font-size: 0.7rem; margin-right: 0.75rem;">Unrealized</span><span class="position-pnl {total_class}" style="font-size: 1.1rem;">${total_unrealized:+,.2f}</span></div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="empty-state"><div class="empty-state-text">No positions yet. I\'m watching for opportunities.</div></div>', unsafe_allow_html=True)


# ─── AI Intelligence Section ──────────────────────────────────────────────────
chat_ready, _ = check_chat_setup()

if chat_ready:
    from execute_intelligence import execute_actions

    if "ai_recommendations" not in st.session_state:
        st.session_state.ai_recommendations = None

    actions = st.session_state.ai_recommendations
    action_count = len([a for a in actions if a.get('action') != 'HOLD' and 'error' not in a]) if actions else 0

    rec_badge = f"{action_count} pending" if action_count > 0 else "ready"
    rec_badge_class = "attention" if action_count > 0 else ""

    st.markdown(f"""
    <div class="section-header">
        <span class="section-title">Mommy's Thinking</span>
        <span class="section-badge {rec_badge_class}">{rec_badge}</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("ANALYZE PORTFOLIO", use_container_width=True):
            with st.spinner("Thinking..."):
                try:
                    result = run_intelligence()
                    st.session_state.ai_recommendations = result.get("actions", [])
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        has_executable = False
        if actions:
            has_executable = any(
                a.get("safety_check") == "PASSED" and a.get("action") != "HOLD"
                for a in actions if "error" not in a
            )

        if st.button("EXECUTE", use_container_width=True, disabled=not has_executable, type="primary"):
            with st.spinner("Executing..."):
                try:
                    results = execute_actions(actions)
                    executed = sum(1 for r in results if r.get("result", {}).get("status") == "EXECUTED")
                    st.success(f"Executed {executed} action(s)")
                    st.session_state.ai_recommendations = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Execution error: {e}")

    # Display recommendations
    if actions:
        for action in actions:
            if "error" in action:
                continue

            action_type = action.get("action", "")
            ticker = action.get("ticker", "-")
            reason = action.get("reason", "")
            safety = action.get("safety_check", "")

            if action_type == "HOLD":
                card_class = "hold"
            elif action_type in ["BUY", "ADD"]:
                card_class = "buy"
            elif action_type in ["SELL", "TRIM"]:
                card_class = "sell"
            else:
                card_class = ""

            if safety == "BLOCKED":
                card_class += " blocked"
                blocked_note = f" [BLOCKED: {action.get('block_reason', 'Safety rail')}]"
            else:
                blocked_note = ""

            html = f'<div class="rec-card {card_class}">'
            html += f'<div class="rec-header"><span class="rec-action">{action_type}</span><span class="rec-ticker">{ticker}</span></div>'
            html += f'<div class="rec-reason">{reason}{blocked_note}</div>'
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)


# ─── Recent Activity Section ──────────────────────────────────────────────────
tx_count = len(transactions_df.tail(7)) if not transactions_df.empty else 0

st.markdown(f"""
<div class="section-header">
    <span class="section-title">Recent Activity</span>
    <span class="section-badge">{tx_count} this week</span>
</div>
""", unsafe_allow_html=True)

if not transactions_df.empty:
    recent = transactions_df.tail(6).iloc[::-1]

    for _, tx in recent.iterrows():
        action_class = "buy" if tx["action"] == "BUY" else "sell"
        html = f'<div class="tx-row"><span class="tx-action {action_class}">{tx["action"]}</span><span class="tx-ticker">{tx["ticker"]}</span><span class="tx-details">{int(tx["shares"])} @ ${tx["price"]:.2f}</span><span class="tx-date">{tx["date"]}</span></div>'
        st.markdown(html, unsafe_allow_html=True)
else:
    st.markdown('<div class="empty-state"><div class="empty-state-text">No transactions yet.</div></div>', unsafe_allow_html=True)


# ─── Performance Metrics Section ──────────────────────────────────────────────
with st.expander("Performance & Risk", expanded=False):
    try:
        analytics = PortfolioAnalytics()
        m = analytics.calculate_all_metrics()

        if m and m.days_tracked >= 3:
            # Win Rate
            try:
                analyzer = TradeAnalyzer()
                ts = analyzer.calculate_trade_stats()
                win_rate = ts.win_rate_pct if ts and ts.total_trades > 0 else 0
            except:
                win_rate = 0

            dd_class = "negative" if m.max_drawdown_pct < -5 else ""
            alpha_class = "positive" if m.alpha_pct > 0 else "negative"

            metrics_html = '<div class="metric-grid">'
            metrics_html += f'<div class="metric-card"><div class="metric-value">{m.sharpe_ratio:.2f}</div><div class="metric-label">Sharpe</div></div>'
            metrics_html += f'<div class="metric-card"><div class="metric-value">{win_rate:.0f}%</div><div class="metric-label">Win Rate</div></div>'
            metrics_html += f'<div class="metric-card"><div class="metric-value {dd_class}">{m.max_drawdown_pct:.1f}%</div><div class="metric-label">Max Drawdown</div></div>'
            metrics_html += f'<div class="metric-card"><div class="metric-value {alpha_class}">{m.alpha_pct:+.1f}%</div><div class="metric-label">Alpha</div></div>'
            metrics_html += '</div>'
            st.markdown(metrics_html, unsafe_allow_html=True)
        else:
            st.info("Need more trading history for metrics.")
    except Exception as e:
        st.warning(f"Metrics unavailable: {e}")


# ─── Chat Section ─────────────────────────────────────────────────────────────
with st.expander("Ask Mommy", expanded=False):
    if not chat_ready:
        st.info("Add ANTHROPIC_API_KEY to .env to enable chat.")
    else:
        st.caption("Ask anything about your portfolio.")

        user_question = st.text_input(
            "Question",
            placeholder="Which positions should I watch?",
            label_visibility="collapsed"
        )

        if user_question:
            with st.spinner("Thinking..."):
                response = ai_chat(user_question)

            if response.success:
                st.markdown(f'<div style="background: var(--surface); padding: 1rem; border-radius: 6px; margin-top: 1rem;"><div style="color: var(--text-secondary); font-size: 0.85rem; white-space: pre-wrap;">{response.message}</div></div>', unsafe_allow_html=True)
            else:
                st.error(response.error)


# ─── Actions Bar ──────────────────────────────────────────────────────────────
st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("REFRESH", use_container_width=True):
        st.rerun()

with col2:
    if st.button("RUN DAILY", use_container_width=True, type="primary"):
        with st.spinner("Running..."):
            try:
                project_root = Path(__file__).parent.parent
                result = subprocess.run(
                    ["bash", "run_daily.sh"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=600
                )
                if result.returncode == 0:
                    st.success("Done!")
                    st.rerun()
                else:
                    st.error("Failed")
                    with st.expander("Details"):
                        st.code(result.stderr or result.stdout)
            except Exception as e:
                st.error(f"Error: {e}")

with col3:
    if st.button("DISCOVER", use_container_width=True):
        with st.spinner("Discovering..."):
            try:
                project_root = Path(__file__).parent.parent
                result = subprocess.run(
                    [sys.executable, "scripts/stock_discovery.py"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0:
                    st.success("Done!")
                    with st.expander("Results", expanded=True):
                        st.code(result.stdout[-2000:])
                else:
                    st.error("Failed")
            except Exception as e:
                st.error(f"Error: {e}")


# ─── Settings ─────────────────────────────────────────────────────────────────
with st.expander("Settings", expanded=False):
    col_info, col_toggle = st.columns([3, 1])

    with col_info:
        if paper_mode:
            st.markdown("""
            **Paper Trading** - Simulated trades, no real money.
            """)
        else:
            st.markdown("""
            **Live Trading** - Real portfolio data.
            """)

    with col_toggle:
        if paper_mode:
            if st.button("Go Live", use_container_width=True):
                set_paper_mode(False)
                st.rerun()
        else:
            if st.button("Paper Mode", use_container_width=True):
                set_paper_mode(True)
                st.rerun()

    if paper_mode:
        st.markdown("---")
        paper_files = get_data_files()
        if st.button("Reset Paper Portfolio"):
            for f in paper_files.values():
                if f.exists():
                    f.unlink()
            st.success("Reset!")
            st.rerun()


# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="mommy-footer">
    <div class="footer-text">Mommy's always watching · Data delayed · Not financial advice</div>
</div>
</div>
""", unsafe_allow_html=True)
