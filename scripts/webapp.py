#!/usr/bin/env python3
"""
M O M M Y — Autonomous Trading Intelligence

A cinematic command center interface for monitoring
a living system that operates quietly and continuously.

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

from analytics import PortfolioAnalytics
from trade_analyzer import TradeAnalyzer
from market_regime import get_regime_analysis, MarketRegime
from risk_scoreboard import get_risk_scoreboard
from capital_preservation import get_preservation_status
from attribution import get_daily_attribution
from pattern_detector import get_pattern_alerts
from post_mortem import get_recent_post_mortems
from factor_learning import FactorLearner, get_weight_suggestions
from portfolio_chat import chat as ai_chat, check_setup as check_chat_setup

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"starting_capital": 50000.0}


def is_paper_mode():
    """Check if system is in paper trading mode."""
    config = load_config()
    return config.get("mode", "live") == "paper"


def set_paper_mode(enabled: bool):
    """Toggle paper trading mode."""
    config = load_config()
    config["mode"] = "paper" if enabled else "live"
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_data_files():
    """Get the correct data files based on current mode."""
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
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Check Mode ──────────────────────────────────────────────────────────────
paper_mode = is_paper_mode()
mode_class = "paper-mode" if paper_mode else "live-mode"

# ─── Cinematic CSS ───────────────────────────────────────────────────────────
st.markdown(f"""
<div class="{mode_class}">
""", unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500&display=swap');

:root {
    --void: #000000;
    --abyss: #08080c;
    --deep: #0c0c12;
    --surface: #161620;
    --elevated: #1e1e2a;
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-visible: rgba(255, 255, 255, 0.15);
    --text-primary: rgba(255, 255, 255, 1);
    --text-secondary: rgba(255, 255, 255, 0.75);
    --text-tertiary: rgba(255, 255, 255, 0.50);
    --text-ghost: rgba(255, 255, 255, 0.30);
    --pulse-cyan: #00d4ff;
    --pulse-gold: #ffd700;
    --pulse-positive: #00ff9d;
    --pulse-negative: #ff3366;
    --pulse-warning: #ffaa00;
    --glow-cyan: rgba(0, 212, 255, 0.20);
    --glow-gold: rgba(255, 215, 0, 0.15);
}

/* ─── Base Reset ─────────────────────────────────────────────────────────── */
.stApp {
    background: var(--void);
    background-image:
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0, 212, 255, 0.03) 0%, transparent 50%),
        radial-gradient(ellipse 60% 40% at 50% 120%, rgba(255, 215, 0, 0.02) 0%, transparent 40%);
    min-height: 100vh;
}

* {
    font-family: 'Space Grotesk', -apple-system, sans-serif !important;
}

code, pre, [data-testid="stCode"] * {
    font-family: 'JetBrains Mono', monospace !important;
}

#MainMenu, footer, header, [data-testid="stToolbar"], .stDeployButton {
    display: none !important;
}

.block-container {
    padding: 2rem 3rem 4rem 3rem !important;
    max-width: 1600px !important;
}

/* ─── The Identity ───────────────────────────────────────────────────────── */
.system-identity {
    text-align: center;
    padding: 3rem 0 2rem 0;
    position: relative;
}

.system-identity::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 200px;
    height: 200px;
    background: radial-gradient(circle, var(--glow-cyan) 0%, transparent 70%);
    opacity: 0.5;
    pointer-events: none;
}

.system-name {
    font-size: 2.5rem;
    font-weight: 300;
    letter-spacing: 1.2rem;
    color: var(--text-primary);
    margin: 0;
    position: relative;
    text-transform: uppercase;
}

.system-status {
    font-size: 0.8rem;
    letter-spacing: 0.3rem;
    color: var(--text-secondary);
    margin-top: 0.8rem;
    text-transform: uppercase;
}

.system-pulse {
    display: inline-block;
    width: 6px;
    height: 6px;
    background: var(--pulse-cyan);
    border-radius: 50%;
    margin-right: 12px;
    animation: pulse 3s ease-in-out infinite;
    box-shadow: 0 0 12px var(--pulse-cyan);
}

@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.8); }
}

/* ─── The Mind (Central Focus) ───────────────────────────────────────────── */
.mind-container {
    text-align: center;
    padding: 4rem 2rem;
    margin: 2rem auto;
    max-width: 600px;
    position: relative;
}

.mind-container::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at center, var(--glow-cyan) 0%, transparent 60%);
    opacity: 0.1;
    pointer-events: none;
}

.mind-value {
    font-size: 5rem;
    font-weight: 300;
    color: var(--text-primary);
    letter-spacing: -0.02em;
    line-height: 1;
    margin-bottom: 0.5rem;
}

.mind-label {
    font-size: 0.75rem;
    letter-spacing: 0.4rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    margin-bottom: 2rem;
}

.mind-delta {
    font-size: 1.2rem;
    font-weight: 400;
    padding: 0.5rem 1.5rem;
    border-radius: 100px;
    display: inline-block;
}

.mind-delta.positive {
    color: var(--pulse-positive);
    background: rgba(0, 255, 157, 0.08);
}

.mind-delta.negative {
    color: var(--pulse-negative);
    background: rgba(255, 51, 102, 0.08);
}

/* ─── Secondary Metrics ──────────────────────────────────────────────────── */
.metrics-row {
    display: flex;
    justify-content: center;
    gap: 4rem;
    padding: 2rem 0;
    margin: 1rem 0 3rem 0;
    border-top: 1px solid var(--border-subtle);
    border-bottom: 1px solid var(--border-subtle);
}

.metric-item {
    text-align: center;
}

.metric-value {
    font-size: 1.6rem;
    font-weight: 400;
    color: var(--text-primary);
    margin-bottom: 0.3rem;
}

.metric-label {
    font-size: 0.7rem;
    letter-spacing: 0.2rem;
    color: var(--text-secondary);
    text-transform: uppercase;
}

/* ─── Signal Panels ──────────────────────────────────────────────────────── */
.signal-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.5rem;
    margin: 2rem 0;
}

.signal-panel {
    background: linear-gradient(180deg, var(--surface) 0%, var(--abyss) 100%);
    border: 1px solid var(--border-subtle);
    padding: 1.5rem;
    position: relative;
    overflow: hidden;
}

.signal-panel::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border-visible), transparent);
}

.signal-title {
    font-size: 0.7rem;
    letter-spacing: 0.15rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    margin-bottom: 1rem;
}

.signal-value {
    font-size: 1.8rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 0.3rem;
}

.signal-detail {
    font-size: 0.75rem;
    color: var(--text-secondary);
}

/* ─── Regime Indicator ───────────────────────────────────────────────────── */
.regime-indicator {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 1.2rem;
    background: var(--surface);
    border: 1px solid var(--border-visible);
}

.regime-indicator.bull {
    border-color: rgba(0, 255, 157, 0.2);
}

.regime-indicator.bear {
    border-color: rgba(255, 51, 102, 0.2);
}

.regime-indicator.sideways {
    border-color: rgba(255, 170, 0, 0.2);
}

.regime-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.regime-dot.bull { background: var(--pulse-positive); box-shadow: 0 0 8px var(--pulse-positive); }
.regime-dot.bear { background: var(--pulse-negative); box-shadow: 0 0 8px var(--pulse-negative); }
.regime-dot.sideways { background: var(--pulse-warning); box-shadow: 0 0 8px var(--pulse-warning); }

.regime-text {
    font-size: 0.7rem;
    letter-spacing: 0.15rem;
    color: var(--text-secondary);
    text-transform: uppercase;
}

/* ─── Data Tables ────────────────────────────────────────────────────────── */
.data-section {
    margin: 3rem 0;
}

.section-header {
    font-size: 0.75rem;
    letter-spacing: 0.2rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    margin-bottom: 1.5rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-visible);
}

[data-testid="stDataFrame"] {
    background: transparent !important;
}

[data-testid="stDataFrame"] > div {
    background: var(--surface) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 0 !important;
}

/* ─── Streamlit Overrides ────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: transparent;
    padding: 0;
}

[data-testid="stMetricLabel"] {
    font-size: 0.6rem !important;
    letter-spacing: 0.2rem !important;
    color: var(--text-tertiary) !important;
    text-transform: uppercase !important;
}

[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 400 !important;
    color: var(--text-primary) !important;
}

/* Buttons */
.stButton > button {
    background: transparent !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border-visible) !important;
    border-radius: 0 !important;
    padding: 0.75rem 2rem !important;
    font-size: 0.65rem !important;
    letter-spacing: 0.2rem !important;
    text-transform: uppercase !important;
    transition: all 0.3s ease !important;
}

.stButton > button:hover {
    background: var(--surface) !important;
    border-color: var(--pulse-cyan) !important;
    color: var(--text-primary) !important;
    box-shadow: 0 0 20px rgba(0, 212, 255, 0.1) !important;
}

.stButton > button[kind="primary"] {
    background: transparent !important;
    border-color: var(--pulse-cyan) !important;
    color: var(--pulse-cyan) !important;
}

.stButton > button[kind="primary"]:hover {
    background: rgba(0, 212, 255, 0.1) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 1px solid var(--border-subtle);
    gap: 0;
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-tertiary) !important;
    font-size: 0.65rem !important;
    letter-spacing: 0.15rem !important;
    text-transform: uppercase !important;
    padding: 1rem 2rem !important;
    border-bottom: 2px solid transparent !important;
}

.stTabs [aria-selected="true"] {
    color: var(--text-primary) !important;
    border-bottom-color: var(--pulse-cyan) !important;
}

/* Charts */
[data-testid="stVegaLiteChart"] {
    background: transparent !important;
}

/* Dividers */
hr {
    border-color: var(--border-subtle) !important;
    margin: 2rem 0 !important;
}

/* Info/Warning boxes */
.stAlert {
    background: var(--surface) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 0 !important;
    color: var(--text-secondary) !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: var(--surface) !important;
    border: 1px solid var(--border-subtle) !important;
    color: var(--text-secondary) !important;
}

/* ─── Risk Meter ─────────────────────────────────────────────────────────── */
.risk-meter {
    width: 100%;
    height: 2px;
    background: var(--border-subtle);
    margin: 1rem 0;
    position: relative;
}

.risk-meter-fill {
    height: 100%;
    transition: width 0.5s ease;
}

.risk-low { background: var(--pulse-positive); box-shadow: 0 0 8px var(--pulse-positive); }
.risk-moderate { background: var(--pulse-warning); box-shadow: 0 0 8px var(--pulse-warning); }
.risk-high { background: var(--pulse-negative); box-shadow: 0 0 8px var(--pulse-negative); }

/* ─── Alert Banner ───────────────────────────────────────────────────────── */
.alert-banner {
    background: linear-gradient(90deg, rgba(255, 51, 102, 0.1) 0%, transparent 100%);
    border-left: 2px solid var(--pulse-negative);
    padding: 1rem 1.5rem;
    margin: 1rem 0;
}

.alert-title {
    font-size: 0.65rem;
    letter-spacing: 0.2rem;
    color: var(--pulse-negative);
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}

.alert-detail {
    font-size: 0.8rem;
    color: var(--text-secondary);
}

/* ─── Position Row ───────────────────────────────────────────────────────── */
.position-row {
    display: flex;
    align-items: center;
    padding: 1rem 0;
    border-bottom: 1px solid var(--border-subtle);
}

.position-row:last-child {
    border-bottom: none;
}

.position-ticker {
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-primary);
    width: 80px;
}

.position-detail {
    flex: 1;
    font-size: 0.75rem;
    color: var(--text-secondary);
}

.position-pnl {
    font-size: 0.85rem;
    font-weight: 500;
}

.position-pnl.positive { color: var(--pulse-positive); }
.position-pnl.negative { color: var(--pulse-negative); }

/* ─── Footer ─────────────────────────────────────────────────────────────── */
.footer {
    text-align: center;
    padding: 4rem 0 2rem 0;
    margin-top: 4rem;
    border-top: 1px solid var(--border-subtle);
}

.footer-text {
    font-size: 0.55rem;
    letter-spacing: 0.3rem;
    color: var(--text-ghost);
    text-transform: uppercase;
}

/* ─── Scrollbar ──────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--void); }
::-webkit-scrollbar-thumb { background: var(--border-visible); }
::-webkit-scrollbar-thumb:hover { background: var(--text-tertiary); }

/* ─── Mode Badge ─────────────────────────────────────────────────────────── */
.mode-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 1rem;
    font-size: 0.65rem;
    letter-spacing: 0.15rem;
    text-transform: uppercase;
    border-radius: 2px;
    margin-top: 1rem;
}

.mode-badge.live {
    background: rgba(0, 255, 157, 0.1);
    border: 1px solid rgba(0, 255, 157, 0.3);
    color: var(--pulse-positive);
}

.mode-badge.paper {
    background: rgba(255, 215, 0, 0.1);
    border: 1px solid rgba(255, 215, 0, 0.3);
    color: var(--pulse-gold);
}

.mode-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
}

.mode-dot.live {
    background: var(--pulse-positive);
    box-shadow: 0 0 8px var(--pulse-positive);
}

.mode-dot.paper {
    background: var(--pulse-gold);
    box-shadow: 0 0 8px var(--pulse-gold);
}

/* Paper mode accent override */
.paper-mode .system-pulse {
    background: var(--pulse-gold) !important;
    box-shadow: 0 0 12px var(--pulse-gold) !important;
}

.paper-mode .system-identity::before {
    background: radial-gradient(circle, var(--glow-gold) 0%, transparent 70%) !important;
}

.paper-mode .mind-container::before {
    background: radial-gradient(ellipse at center, var(--glow-gold) 0%, transparent 60%) !important;
}

.paper-mode .stTabs [aria-selected="true"] {
    border-bottom-color: var(--pulse-gold) !important;
}

.paper-mode .stButton > button:hover {
    border-color: var(--pulse-gold) !important;
    box-shadow: 0 0 20px rgba(255, 215, 0, 0.1) !important;
}

.paper-mode .stButton > button[kind="primary"] {
    border-color: var(--pulse-gold) !important;
    color: var(--pulse-gold) !important;
}

.paper-mode .stButton > button[kind="primary"]:hover {
    background: rgba(255, 215, 0, 0.1) !important;
}

/* ─── Settings Panel ─────────────────────────────────────────────────────── */
.settings-panel {
    background: var(--surface);
    border: 1px solid var(--border-subtle);
    padding: 1.5rem;
    margin: 1rem 0;
}

.settings-title {
    font-size: 0.7rem;
    letter-spacing: 0.15rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    margin-bottom: 1rem;
}

.settings-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--border-subtle);
}

.settings-row:last-child {
    border-bottom: none;
}

.settings-label {
    font-size: 0.8rem;
    color: var(--text-secondary);
}

.settings-value {
    font-size: 0.8rem;
    color: var(--text-primary);
}
</style>
""", unsafe_allow_html=True)


# ─── Load Data ────────────────────────────────────────────────────────────────
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
day_pct = snapshots_df.iloc[-1].get("day_pnl_pct", 0) if not snapshots_df.empty else 0


# ─── The Identity ─────────────────────────────────────────────────────────────
mode_text = "PAPER" if paper_mode else "LIVE"
mode_style = "paper" if paper_mode else "live"

st.markdown(f"""
<div class="system-identity">
    <h1 class="system-name">M O M M Y</h1>
    <div class="system-status">
        <span class="system-pulse"></span>
        Autonomous Trading Intelligence · {datetime.now().strftime('%Y.%m.%d')}
    </div>
    <div class="mode-badge {mode_style}">
        <span class="mode-dot {mode_style}"></span>
        {mode_text} MODE
    </div>
</div>
""", unsafe_allow_html=True)


# ─── Capital Preservation Alert ──────────────────────────────────────────────
try:
    preservation = get_preservation_status()
    if preservation.active:
        st.markdown("""
        <div class="alert-banner">
            <div class="alert-title">Capital Preservation Active</div>
            <div class="alert-detail">Position sizing reduced · New entries restricted</div>
        </div>
        """, unsafe_allow_html=True)
except:
    pass


# ─── The Mind (Central Focus) ────────────────────────────────────────────────
delta_class = "positive" if total_return_pct >= 0 else "negative"
delta_sign = "+" if total_return_pct >= 0 else ""

st.markdown(f"""
<div class="mind-container">
    <div class="mind-value">${total_equity:,.0f}</div>
    <div class="mind-label">Total Equity</div>
    <div class="mind-delta {delta_class}">{delta_sign}{total_return_pct:.2f}% all-time</div>
</div>
""", unsafe_allow_html=True)


# ─── Secondary Metrics ───────────────────────────────────────────────────────
day_sign = "+" if day_pnl >= 0 else ""
st.markdown(f"""
<div class="metrics-row">
    <div class="metric-item">
        <div class="metric-value">${positions_value:,.0f}</div>
        <div class="metric-label">Deployed</div>
    </div>
    <div class="metric-item">
        <div class="metric-value">${cash:,.0f}</div>
        <div class="metric-label">Reserve</div>
    </div>
    <div class="metric-item">
        <div class="metric-value">{num_positions}</div>
        <div class="metric-label">Positions</div>
    </div>
    <div class="metric-item">
        <div class="metric-value">{day_sign}${abs(day_pnl):,.0f}</div>
        <div class="metric-label">Today</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ─── Signal Panels ───────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    try:
        ra = get_regime_analysis()
        regime_class = ra.regime.value.lower()
        regime_text = ra.regime.value.upper()
        st.markdown(f"""
        <div class="signal-panel">
            <div class="signal-title">Market Regime</div>
            <div class="regime-indicator {regime_class}">
                <span class="regime-dot {regime_class}"></span>
                <span class="regime-text">{regime_text}</span>
            </div>
            <div class="signal-detail" style="margin-top: 1rem;">
                Benchmark ${ra.current_price:,.2f}
            </div>
        </div>
        """, unsafe_allow_html=True)
    except:
        st.markdown("""
        <div class="signal-panel">
            <div class="signal-title">Market Regime</div>
            <div class="signal-value">—</div>
        </div>
        """, unsafe_allow_html=True)

with col2:
    try:
        risk = get_risk_scoreboard()
        risk_class = "risk-low" if risk.overall_score >= 70 else ("risk-high" if risk.overall_score < 40 else "risk-moderate")
        st.markdown(f"""
        <div class="signal-panel">
            <div class="signal-title">Risk Assessment</div>
            <div class="signal-value">{risk.overall_score:.0f}</div>
            <div class="risk-meter">
                <div class="risk-meter-fill {risk_class}" style="width: {risk.overall_score}%;"></div>
            </div>
            <div class="signal-detail">{risk.risk_level}</div>
        </div>
        """, unsafe_allow_html=True)
    except:
        st.markdown("""
        <div class="signal-panel">
            <div class="signal-title">Risk Assessment</div>
            <div class="signal-value">—</div>
        </div>
        """, unsafe_allow_html=True)

with col3:
    try:
        analytics = PortfolioAnalytics()
        m = analytics.calculate_all_metrics()
        sharpe = m.sharpe_ratio if m else 0
        st.markdown(f"""
        <div class="signal-panel">
            <div class="signal-title">Sharpe Ratio</div>
            <div class="signal-value">{sharpe:.2f}</div>
            <div class="signal-detail">Risk-adjusted return</div>
        </div>
        """, unsafe_allow_html=True)
    except:
        st.markdown("""
        <div class="signal-panel">
            <div class="signal-title">Sharpe Ratio</div>
            <div class="signal-value">—</div>
        </div>
        """, unsafe_allow_html=True)

with col4:
    try:
        analyzer = TradeAnalyzer()
        ts = analyzer.calculate_trade_stats()
        win_rate = ts.win_rate_pct if ts and ts.total_trades > 0 else 0
        st.markdown(f"""
        <div class="signal-panel">
            <div class="signal-title">Win Rate</div>
            <div class="signal-value">{win_rate:.0f}%</div>
            <div class="signal-detail">{ts.total_trades if ts else 0} closed trades</div>
        </div>
        """, unsafe_allow_html=True)
    except:
        st.markdown("""
        <div class="signal-panel">
            <div class="signal-title">Win Rate</div>
            <div class="signal-value">—</div>
        </div>
        """, unsafe_allow_html=True)


# ─── Tabs ────────────────────────────────────────────────────────────────────
st.markdown("")
tab_positions, tab_activity, tab_intelligence, tab_chat = st.tabs([
    "POSITIONS", "ACTIVITY", "INTELLIGENCE", "CHAT"
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: POSITIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_positions:
    if not positions_df.empty:
        st.markdown('<div class="section-header">Current Holdings</div>', unsafe_allow_html=True)

        for _, row in positions_df.iterrows():
            pnl_class = "positive" if row["unrealized_pnl"] >= 0 else "negative"
            pnl_sign = "+" if row["unrealized_pnl"] >= 0 else ""
            st.markdown(f"""
            <div class="position-row">
                <div class="position-ticker">{row['ticker']}</div>
                <div class="position-detail">
                    {int(row['shares'])} shares · ${row['avg_cost_basis']:.2f} avg · ${row['current_price']:.2f} current
                </div>
                <div class="position-pnl {pnl_class}">
                    {pnl_sign}${row['unrealized_pnl']:.2f} ({pnl_sign}{row['unrealized_pnl_pct']:.1f}%)
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Summary
        total_unrealized = positions_df["unrealized_pnl"].sum()
        pnl_class = "positive" if total_unrealized >= 0 else "negative"
        st.markdown(f"""
        <div style="text-align: right; margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--border-subtle);">
            <span style="color: var(--text-tertiary); font-size: 0.65rem; letter-spacing: 0.15rem; text-transform: uppercase; margin-right: 1rem;">Unrealized P&L</span>
            <span class="position-pnl {pnl_class}" style="font-size: 1.2rem;">${total_unrealized:+,.2f}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align: center; padding: 4rem 0; color: var(--text-tertiary);">
            <div style="font-size: 0.7rem; letter-spacing: 0.2rem; text-transform: uppercase;">No Active Positions</div>
            <div style="font-size: 0.8rem; margin-top: 0.5rem; color: var(--text-ghost);">System awaiting entry signals</div>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: ACTIVITY
# ═══════════════════════════════════════════════════════════════════════════════
with tab_activity:
    # Equity Curve
    if not snapshots_df.empty and len(snapshots_df) > 1:
        st.markdown('<div class="section-header">Equity Curve</div>', unsafe_allow_html=True)
        chart_df = snapshots_df[["date", "total_equity"]].copy()
        chart_df["date"] = pd.to_datetime(chart_df["date"])
        chart_df = chart_df.set_index("date")
        chart_df.columns = ["EQUITY"]
        st.line_chart(chart_df, use_container_width=True, color="#00d4ff")

    # Recent Transactions
    st.markdown('<div class="section-header">Recent Transactions</div>', unsafe_allow_html=True)
    if not transactions_df.empty:
        recent = transactions_df.tail(8).iloc[::-1][["date", "action", "ticker", "shares", "price", "reason"]].copy()
        recent.columns = ["DATE", "ACTION", "TICKER", "SHARES", "PRICE", "REASON"]
        recent["SHARES"] = recent["SHARES"].astype(int)
        recent["PRICE"] = recent["PRICE"].apply(lambda x: f"${x:.2f}")
        st.dataframe(recent, use_container_width=True, hide_index=True)
    else:
        st.markdown("""
        <div style="text-align: center; padding: 3rem 0; color: var(--text-tertiary);">
            <div style="font-size: 0.7rem; letter-spacing: 0.2rem; text-transform: uppercase;">No Transaction History</div>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_intelligence:
    col_left, col_right = st.columns(2)

    with col_left:
        # Pattern Detection
        st.markdown('<div class="section-header">Pattern Detection</div>', unsafe_allow_html=True)
        try:
            alerts = get_pattern_alerts()
            if alerts:
                for alert in alerts[:3]:
                    level_colors = {"INFO": "var(--text-secondary)", "MEDIUM": "var(--pulse-warning)", "HIGH": "var(--pulse-negative)", "CRITICAL": "var(--pulse-negative)"}
                    color = level_colors.get(alert.alert_level, "var(--text-secondary)")
                    st.markdown(f"""
                    <div style="margin-bottom: 1rem; padding-left: 1rem; border-left: 2px solid {color};">
                        <div style="font-size: 0.8rem; color: var(--text-primary);">{alert.title}</div>
                        <div style="font-size: 0.7rem; color: var(--text-tertiary); margin-top: 0.3rem;">{alert.description}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown('<div style="color: var(--text-tertiary); font-size: 0.75rem;">No patterns detected</div>', unsafe_allow_html=True)
        except:
            st.markdown('<div style="color: var(--text-tertiary); font-size: 0.75rem;">Pattern analysis initializing</div>', unsafe_allow_html=True)

        # Recent Lessons
        st.markdown('<div class="section-header" style="margin-top: 2rem;">Learning Archive</div>', unsafe_allow_html=True)
        try:
            post_mortems = get_recent_post_mortems(3)
            if post_mortems:
                for pm in reversed(post_mortems):
                    pnl_color = "var(--pulse-positive)" if pm.pnl >= 0 else "var(--pulse-negative)"
                    st.markdown(f"""
                    <div style="margin-bottom: 1rem;">
                        <div style="font-size: 0.8rem;">
                            <span style="color: var(--text-primary);">{pm.ticker}</span>
                            <span style="color: {pnl_color}; margin-left: 0.5rem;">{pm.pnl_pct:+.1f}%</span>
                            <span style="color: var(--text-tertiary); margin-left: 0.5rem;">{pm.exit_reason}</span>
                        </div>
                        <div style="font-size: 0.7rem; color: var(--text-tertiary); margin-top: 0.3rem;">{pm.summary}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown('<div style="color: var(--text-tertiary); font-size: 0.75rem;">Awaiting completed trades</div>', unsafe_allow_html=True)
        except:
            st.markdown('<div style="color: var(--text-tertiary); font-size: 0.75rem;">Learning system initializing</div>', unsafe_allow_html=True)

    with col_right:
        # Factor Performance
        st.markdown('<div class="section-header">Factor Intelligence</div>', unsafe_allow_html=True)
        try:
            learner = FactorLearner()
            factor_summary = learner.get_factor_summary()

            if factor_summary["status"] == "ok" and factor_summary["factors"]:
                for f in factor_summary["factors"][:5]:
                    trend_colors = {"improving": "var(--pulse-positive)", "stable": "var(--text-tertiary)", "declining": "var(--pulse-negative)"}
                    trend_color = trend_colors.get(f["trend"], "var(--text-tertiary)")
                    wr_color = "var(--pulse-positive)" if f["win_rate"] >= 55 else ("var(--pulse-negative)" if f["win_rate"] < 45 else "var(--text-secondary)")

                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; border-bottom: 1px solid var(--border-subtle);">
                        <span style="color: var(--text-secondary); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1rem;">{f['factor'].replace('_', ' ')}</span>
                        <span style="color: {wr_color}; font-size: 0.85rem;">{f['win_rate']:.0f}%</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown('<div style="color: var(--text-tertiary); font-size: 0.75rem;">Insufficient data for analysis</div>', unsafe_allow_html=True)
        except:
            st.markdown('<div style="color: var(--text-tertiary); font-size: 0.75rem;">Factor analysis initializing</div>', unsafe_allow_html=True)

        # Attribution
        st.markdown('<div class="section-header" style="margin-top: 2rem;">Attribution</div>', unsafe_allow_html=True)
        try:
            attribution = get_daily_attribution()
            if attribution and attribution.top_contributors:
                for t in attribution.top_contributors[:3]:
                    pnl_color = "var(--pulse-positive)" if t.pnl >= 0 else "var(--pulse-negative)"
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; padding: 0.5rem 0;">
                        <span style="color: var(--text-secondary); font-size: 0.8rem;">{t.ticker}</span>
                        <span style="color: {pnl_color}; font-size: 0.8rem;">${t.pnl:+,.0f}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown('<div style="color: var(--text-tertiary); font-size: 0.75rem;">No attribution data</div>', unsafe_allow_html=True)
        except:
            st.markdown('<div style="color: var(--text-tertiary); font-size: 0.75rem;">Attribution loading</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: CHAT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown('<div class="section-header">Ask MOMMY</div>', unsafe_allow_html=True)

    # Check if chat is configured
    chat_ready, chat_status = check_chat_setup()

    if not chat_ready:
        st.markdown(f"""
        <div style="background: var(--surface); border: 1px solid var(--border-subtle); padding: 1.5rem; margin: 1rem 0;">
            <div style="color: var(--pulse-warning); font-size: 0.8rem; margin-bottom: 0.5rem;">Setup Required</div>
            <div style="color: var(--text-secondary); font-size: 0.75rem;">
                {chat_status}<br><br>
                To enable AI chat:<br>
                1. Add <code>ANTHROPIC_API_KEY=your-key-here</code> to your .env file<br>
                2. Run <code>pip install anthropic</code><br>
                3. Refresh the page
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Sample questions
        st.markdown("""
        <div style="color: var(--text-tertiary); font-size: 0.7rem; margin-bottom: 1rem;">
            Try asking: "Which positions should I be worried about?" or "Summarize my portfolio health"
        </div>
        """, unsafe_allow_html=True)

        # Chat input
        user_question = st.text_input(
            "Ask a question about your portfolio",
            placeholder="e.g., Which stocks are close to their stop loss?",
            label_visibility="collapsed"
        )

        if user_question:
            with st.spinner("Thinking..."):
                response = ai_chat(user_question)

            if response.success:
                st.markdown(f"""
                <div style="background: var(--surface); border: 1px solid var(--border-subtle); padding: 1.5rem; margin: 1rem 0;">
                    <div style="color: var(--text-secondary); font-size: 0.8rem; white-space: pre-wrap;">{response.message}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error(response.error)

        # Quick action buttons
        st.markdown("---")
        st.markdown('<div style="color: var(--text-tertiary); font-size: 0.65rem; letter-spacing: 0.1rem; text-transform: uppercase; margin-bottom: 0.75rem;">Quick Questions</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Portfolio Health Check", use_container_width=True):
                with st.spinner("Analyzing..."):
                    response = ai_chat("Give me a quick health check of my portfolio. What's going well and what needs attention?")
                if response.success:
                    st.markdown(f"""
                    <div style="background: var(--surface); border: 1px solid var(--border-subtle); padding: 1.5rem; margin: 1rem 0;">
                        <div style="color: var(--text-secondary); font-size: 0.8rem; white-space: pre-wrap;">{response.message}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error(response.error)

        with col2:
            if st.button("Positions to Watch", use_container_width=True):
                with st.spinner("Scanning..."):
                    response = ai_chat("Which positions are approaching their stop loss or take profit levels? Any that need immediate attention?")
                if response.success:
                    st.markdown(f"""
                    <div style="background: var(--surface); border: 1px solid var(--border-subtle); padding: 1.5rem; margin: 1rem 0;">
                        <div style="color: var(--text-secondary); font-size: 0.8rem; white-space: pre-wrap;">{response.message}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error(response.error)


# ─── Actions ─────────────────────────────────────────────────────────────────
st.markdown("")
st.markdown("---")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if st.button("REFRESH", use_container_width=True):
        st.rerun()

with col2:
    if st.button("EXECUTE DAILY", use_container_width=True, type="primary"):
        with st.spinner(""):
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
                    st.success("Execution complete")
                    with st.expander("Output"):
                        st.code(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                    st.rerun()
                else:
                    st.error("Execution failed")
                    st.code(result.stderr[-1000:] if result.stderr else result.stdout[-1000:])
            except subprocess.TimeoutExpired:
                st.error("Timeout exceeded")
            except Exception as e:
                st.error(f"Error: {e}")

with col3:
    if st.button("DISCOVER", use_container_width=True):
        with st.spinner(""):
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
                    st.success("Discovery complete")
                    with st.expander("Results", expanded=True):
                        st.code(result.stdout[-2000:])
                else:
                    st.error("Discovery failed")
                    with st.expander("Error details"):
                        st.code(result.stderr or result.stdout)
            except Exception as e:
                st.error(f"Discovery error: {e}")


# ─── Settings ─────────────────────────────────────────────────────────────────
with st.expander("SETTINGS", expanded=False):
    st.markdown('<div class="settings-title">Trading Mode</div>', unsafe_allow_html=True)

    col_info, col_toggle = st.columns([3, 1])

    with col_info:
        if paper_mode:
            st.markdown("""
            <div style="font-size: 0.8rem; color: var(--text-secondary);">
                <strong style="color: var(--pulse-gold);">Paper Trading Active</strong><br>
                <span style="color: var(--text-tertiary);">Simulated trades using separate data files. No real money at risk.</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="font-size: 0.8rem; color: var(--text-secondary);">
                <strong style="color: var(--pulse-positive);">Live Trading Active</strong><br>
                <span style="color: var(--text-tertiary);">Using real portfolio data. All trades are tracked.</span>
            </div>
            """, unsafe_allow_html=True)

    with col_toggle:
        if paper_mode:
            if st.button("GO LIVE", use_container_width=True, type="primary"):
                set_paper_mode(False)
                st.rerun()
        else:
            if st.button("PAPER MODE", use_container_width=True):
                set_paper_mode(True)
                st.rerun()

    # Paper trading stats if in paper mode
    if paper_mode:
        st.markdown("---")
        st.markdown('<div class="settings-title">Paper Portfolio</div>', unsafe_allow_html=True)

        paper_files = get_data_files()
        paper_transactions = paper_files["transactions"]
        paper_positions = paper_files["positions"]

        if paper_positions.exists():
            paper_pos_df = pd.read_csv(paper_positions)
            paper_pos_count = len(paper_pos_df)
        else:
            paper_pos_count = 0

        if paper_transactions.exists():
            paper_tx_df = pd.read_csv(paper_transactions)
            paper_tx_count = len(paper_tx_df)
        else:
            paper_tx_count = 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Positions", paper_pos_count)
        with col2:
            st.metric("Transactions", paper_tx_count)
        with col3:
            if st.button("RESET PAPER", use_container_width=True):
                # Clear paper trading files
                for f in paper_files.values():
                    if f.exists():
                        f.unlink()
                st.success("Paper portfolio reset")
                st.rerun()


# ─── Footer ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    <div class="footer-text">Autonomous Trading Intelligence · Data Delayed · Not Financial Advice</div>
</div>
</div>
""", unsafe_allow_html=True)
