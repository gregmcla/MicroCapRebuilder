#!/usr/bin/env python3
"""
M O M M Y — Autonomous Trading Intelligence

A warm, nurturing command center for your portfolio.
Run with: streamlit run scripts/webapp.py
"""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import streamlit as st
import sys

sys.path.insert(0, str(Path(__file__).parent))

# Load .env BEFORE importing modules
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
    get_positions_near_stop,
    get_positions_near_target,
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

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
    --bg: #0a0a0f;
    --card: #13131a;
    --card-hover: #1a1a24;
    --border: rgba(255,255,255,0.08);
    --text: rgba(255,255,255,0.92);
    --text-dim: rgba(255,255,255,0.6);
    --text-faint: rgba(255,255,255,0.35);
    --green: #22c55e;
    --green-bg: rgba(34,197,94,0.12);
    --red: #ef4444;
    --red-bg: rgba(239,68,68,0.12);
    --gold: #eab308;
    --gold-bg: rgba(234,179,8,0.12);
    --blue: #3b82f6;
}

.stApp { background: var(--bg); }
#MainMenu, footer, header, [data-testid="stToolbar"], .stDeployButton { display: none !important; }
.block-container { padding: 1rem 2rem 2rem 2rem !important; max-width: 1100px !important; }

/* Header bar */
.header-bar { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; margin-bottom: 1rem; border-bottom: 1px solid var(--border); }
.header-title { font-size: 1.1rem; font-weight: 600; color: var(--text); letter-spacing: 0.1em; }
.header-mode { display: flex; align-items: center; gap: 0.5rem; }
.mode-btn { padding: 0.4rem 1rem; font-size: 0.7rem; border-radius: 4px; border: 1px solid var(--border); background: transparent; color: var(--text-dim); cursor: pointer; text-transform: uppercase; letter-spacing: 0.05em; }
.mode-btn.active { background: var(--green-bg); border-color: var(--green); color: var(--green); }
.mode-btn.paper.active { background: var(--gold-bg); border-color: var(--gold); color: var(--gold); }

/* Summary cards */
.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
.summary-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.25rem; }
.summary-label { font-size: 0.65rem; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.25rem; }
.summary-value { font-size: 1.5rem; font-weight: 500; color: var(--text); }
.summary-value.green { color: var(--green); }
.summary-value.red { color: var(--red); }
.summary-sub { font-size: 0.75rem; color: var(--text-dim); margin-top: 0.25rem; }

/* Insight box */
.insight-box { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; border-left: 3px solid var(--text-faint); }
.insight-box.insight-good { border-left-color: var(--green); }
.insight-box.insight-warn { border-left-color: var(--gold); }
.insight-box.insight-alert { border-left-color: var(--red); }
.insight-status { font-size: 0.95rem; color: var(--text); margin-bottom: 0.5rem; }
.insight-items { display: flex; flex-wrap: wrap; gap: 1rem; }
.insight-item { display: flex; align-items: center; gap: 0.4rem; font-size: 0.75rem; color: var(--text-dim); }
.insight-dot { width: 6px; height: 6px; border-radius: 50%; }
.dot-good { background: var(--green); }
.dot-warn { background: var(--gold); }
.dot-neutral { background: var(--text-faint); }

/* Section headers */
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 1.5rem 0 0.75rem 0; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }
.section-title { font-size: 0.75rem; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.1em; }
.section-badge { font-size: 0.65rem; color: var(--text-faint); }

/* Positions quick stats */
.pos-stats { display: flex; gap: 0.75rem; align-items: center; font-size: 0.75rem; color: var(--text-dim); margin-bottom: 0.75rem; padding: 0.5rem 0; }
.stat-item { display: flex; gap: 0.25rem; }
.stat-sep { color: var(--text-faint); }
.stat-win { color: var(--green); }
.stat-lose { color: var(--red); }

/* Positions table - compact */
.pos-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.pos-table th { text-align: left; padding: 0.5rem 0.75rem; font-size: 0.65rem; font-weight: 500; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border); }
.pos-table td { padding: 0.65rem 0.75rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
.pos-table tr:hover { background: var(--card); }
.pos-table tr.row-alert { background: rgba(234,179,8,0.06); }
.pos-table tr.row-alert:hover { background: rgba(234,179,8,0.1); }
.pos-table tr.row-target { background: rgba(34,197,94,0.06); }
.pos-table tr.row-down { }

.col-ticker { font-weight: 600; color: var(--text); min-width: 60px; }
.col-value { color: var(--text-dim); min-width: 70px; }
.col-pnl { font-weight: 500; min-width: 70px; }
.col-pct { min-width: 55px; }
.col-bar { min-width: 100px; }
.col-status { min-width: 50px; text-align: right; }

.pnl-up { color: var(--green); }
.pnl-down { color: var(--red); }

.status-warn { font-size: 0.65rem; font-weight: 600; color: var(--gold); text-transform: uppercase; letter-spacing: 0.03em; }
.status-good { font-size: 0.65rem; font-weight: 600; color: var(--green); text-transform: uppercase; letter-spacing: 0.03em; }

/* Mini progress bar in table */
.mini-bar { width: 100%; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
.mini-fill { height: 100%; border-radius: 2px; transition: width 0.3s ease; }

/* Transaction list */
.tx-item { display: flex; align-items: center; padding: 0.6rem 0; border-bottom: 1px solid var(--border); gap: 1rem; }
.tx-item:last-child { border-bottom: none; }
.tx-badge { font-size: 0.6rem; font-weight: 600; padding: 0.2rem 0.5rem; border-radius: 3px; min-width: 32px; text-align: center; }
.tx-badge.buy { background: var(--green-bg); color: var(--green); }
.tx-badge.sell { background: var(--red-bg); color: var(--red); }
.tx-ticker { font-weight: 500; color: var(--text); min-width: 50px; }
.tx-detail { color: var(--text-dim); font-size: 0.8rem; flex: 1; }
.tx-date { color: var(--text-faint); font-size: 0.75rem; }

/* Buttons */
.stButton > button { background: var(--card) !important; color: var(--text-dim) !important; border: 1px solid var(--border) !important; border-radius: 6px !important; font-size: 0.7rem !important; letter-spacing: 0.05em !important; text-transform: uppercase !important; }
.stButton > button:hover { background: var(--card-hover) !important; border-color: var(--green) !important; color: var(--text) !important; }
.stButton > button[kind="primary"] { background: var(--green-bg) !important; border-color: var(--green) !important; color: var(--green) !important; }

/* Checkbox styling */
.stCheckbox label { color: var(--text-dim) !important; font-size: 0.75rem !important; }

/* Footer */
.footer { text-align: center; padding: 2rem 0 1rem 0; font-size: 0.6rem; color: var(--text-faint); letter-spacing: 0.1em; text-transform: uppercase; border-top: 1px solid var(--border); margin-top: 2rem; }

/* Responsive */
@media (max-width: 768px) {
    .summary-grid { grid-template-columns: repeat(2, 1fr); }
    .pos-meta { flex-wrap: wrap; gap: 1rem; }
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
total_return = total_equity - starting_capital
total_return_pct = (total_return / starting_capital) * 100
num_positions = len(positions_df) if not positions_df.empty else 0
day_pnl = snapshots_df.iloc[-1].get("day_pnl", 0) if not snapshots_df.empty else 0
day_pnl_pct = snapshots_df.iloc[-1].get("day_pnl_pct", 0) if not snapshots_df.empty else 0

# Get regime
try:
    regime_analysis = get_regime_analysis()
    regime = regime_analysis.regime.value
except:
    regime = "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER BAR WITH MODE TOGGLE
# ═══════════════════════════════════════════════════════════════════════════════
col_title, col_mode = st.columns([3, 1])

with col_title:
    st.markdown('<div class="header-title">M O M M Y</div>', unsafe_allow_html=True)

with col_mode:
    mode_col1, mode_col2 = st.columns(2)
    with mode_col1:
        if st.button("LIVE", use_container_width=True, type="primary" if not paper_mode else "secondary"):
            if paper_mode:
                set_paper_mode(False)
                st.rerun()
    with mode_col2:
        if st.button("PAPER", use_container_width=True, type="primary" if paper_mode else "secondary"):
            if not paper_mode:
                set_paper_mode(True)
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY CARDS
# ═══════════════════════════════════════════════════════════════════════════════
total_class = "green" if total_return >= 0 else "red"
day_class = "green" if day_pnl >= 0 else "red"
total_sign = "+" if total_return >= 0 else ""
day_sign = "+" if day_pnl >= 0 else ""

# Calculate total unrealized P&L
total_unrealized = positions_df["unrealized_pnl"].sum() if not positions_df.empty else 0
unrealized_class = "green" if total_unrealized >= 0 else "red"
unrealized_sign = "+" if total_unrealized >= 0 else ""

# Build summary cards as single-line HTML
card1 = f'<div class="summary-card"><div class="summary-label">Total Equity</div><div class="summary-value">${total_equity:,.0f}</div><div class="summary-sub">{total_sign}{total_return_pct:.1f}% all-time</div></div>'
card2 = f'<div class="summary-card"><div class="summary-label">Today</div><div class="summary-value {day_class}">{day_sign}${abs(day_pnl):,.0f}</div><div class="summary-sub">{day_sign}{day_pnl_pct:.2f}%</div></div>'
card3 = f'<div class="summary-card"><div class="summary-label">Unrealized P&L</div><div class="summary-value {unrealized_class}">{unrealized_sign}${abs(total_unrealized):,.0f}</div><div class="summary-sub">{num_positions} positions</div></div>'
card4 = f'<div class="summary-card"><div class="summary-label">Cash</div><div class="summary-value">${cash:,.0f}</div><div class="summary-sub">{(cash/total_equity*100):.0f}% reserve</div></div>'
summary_html = f'<div class="summary-grid">{card1}{card2}{card3}{card4}</div>'
st.markdown(summary_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS INSIGHT - What's happening right now
# ═══════════════════════════════════════════════════════════════════════════════
# Get current drawdown
if not snapshots_df.empty:
    peak_equity = snapshots_df['total_equity'].max()
    current_drawdown = ((peak_equity - total_equity) / peak_equity) * 100 if peak_equity > 0 else 0
else:
    current_drawdown = 0

# Check preservation status
try:
    preservation = get_preservation_status()
    preservation_active = preservation.get('preservation_mode', False)
except:
    preservation_active = False

# Generate smart status
status_sentence, sentiment = generate_status_sentence(
    positions_df, snapshots_df, day_pnl,
    regime=regime, preservation_active=preservation_active, drawdown_pct=current_drawdown
)

# Build insight items
insights = []

# Recent sells (last 7 days)
if not transactions_df.empty:
    transactions_df['date'] = pd.to_datetime(transactions_df['date'])
    recent_sells = transactions_df[(transactions_df['action'] == 'SELL') & (transactions_df['date'] >= pd.Timestamp.now() - pd.Timedelta(days=7))]
    recent_buys = transactions_df[(transactions_df['action'] == 'BUY') & (transactions_df['date'] >= pd.Timestamp.now() - pd.Timedelta(days=7))]

    for _, sell in recent_sells.iterrows():
        reason = sell.get('reason', '')
        ticker = sell['ticker']
        if reason == 'STOP_LOSS':
            insights.append(('warn', f'{ticker} stopped out'))
        elif reason == 'TAKE_PROFIT':
            insights.append(('good', f'{ticker} hit target'))
        else:
            insights.append(('neutral', f'Sold {ticker}'))

    if len(recent_buys) > 0:
        insights.append(('neutral', f'{len(recent_buys)} new position{"s" if len(recent_buys) > 1 else ""} opened'))

# Positions near levels
if near_stop:
    for pos in near_stop[:2]:
        insights.append(('warn', f'{pos["ticker"]} {pos["distance_pct"]:.0f}% from stop'))

if near_target:
    for pos in near_target[:2]:
        insights.append(('good', f'{pos["ticker"]} {pos["distance_pct"]:.0f}% from target'))

# Build insight HTML
sentiment_class = {'calm': 'insight-calm', 'positive': 'insight-good', 'attention': 'insight-warn', 'warning': 'insight-alert'}.get(sentiment, 'insight-calm')

insight_items = ""
for item_type, text in insights[:4]:
    dot_class = f'dot-{item_type}'
    insight_items += f'<span class="insight-item"><span class="insight-dot {dot_class}"></span>{text}</span>'

insight_html = f'<div class="insight-box {sentiment_class}"><div class="insight-status">{status_sentence}</div>'
if insight_items:
    insight_html += f'<div class="insight-items">{insight_items}</div>'
insight_html += '</div>'
st.markdown(insight_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# POSITIONS - Compact Table Design
# ═══════════════════════════════════════════════════════════════════════════════
near_stop = get_positions_near_stop(positions_df, threshold_pct=5.0)
near_target = get_positions_near_target(positions_df, threshold_pct=8.0)
near_stop_tickers = {p['ticker'] for p in near_stop}
near_target_tickers = {p['ticker'] for p in near_target}

# Count winners/losers
if not positions_df.empty:
    winners = len(positions_df[positions_df['unrealized_pnl'] > 0])
    losers = len(positions_df[positions_df['unrealized_pnl'] <= 0])
    best_pct = positions_df['unrealized_pnl_pct'].max()
    worst_pct = positions_df['unrealized_pnl_pct'].min()
else:
    winners = losers = 0
    best_pct = worst_pct = 0

# Quick stats line
stats_html = f'<div class="pos-stats"><span class="stat-item"><span class="stat-win">{winners}W</span> / <span class="stat-lose">{losers}L</span></span><span class="stat-sep">|</span><span class="stat-item">Best: <span class="stat-win">+{best_pct:.0f}%</span></span><span class="stat-sep">|</span><span class="stat-item">Worst: <span class="stat-lose">{worst_pct:.0f}%</span></span></div>'

st.markdown(f'<div class="section-head"><span class="section-title">Positions</span><span class="section-badge">{num_positions} open</span></div>', unsafe_allow_html=True)

if not positions_df.empty:
    st.markdown(stats_html, unsafe_allow_html=True)

    # Sort: alerts first, then by P&L %
    positions_sorted = positions_df.copy()
    positions_sorted['_priority'] = positions_sorted['ticker'].apply(lambda t: 0 if t in near_stop_tickers else (1 if t in near_target_tickers else 2))
    positions_sorted = positions_sorted.sort_values(['_priority', 'unrealized_pnl_pct'], ascending=[True, False])

    # Build table rows
    rows_html = ""
    for _, row in positions_sorted.iterrows():
        ticker = row['ticker']
        pnl = row['unrealized_pnl']
        pnl_pct = row['unrealized_pnl_pct']
        market_value = row['market_value']
        current_price = row['current_price']
        entry_price = row['avg_cost_basis']
        stop_loss = row.get('stop_loss', entry_price * 0.92)
        take_profit = row.get('take_profit', entry_price * 1.20)

        # Progress bar calculation
        progress = calculate_position_progress(row)
        prog_pct = progress['progress_pct'] if progress else 50
        zone = progress['zone'] if progress else 'neutral'

        # Status indicator
        if ticker in near_stop_tickers:
            status = "WATCH"
            status_class = "status-warn"
            row_class = "row-alert"
        elif ticker in near_target_tickers:
            status = "TARGET"
            status_class = "status-good"
            row_class = "row-target"
        elif pnl >= 0:
            status = ""
            status_class = ""
            row_class = ""
        else:
            status = ""
            status_class = ""
            row_class = "row-down"

        # P&L formatting
        pnl_class = "pnl-up" if pnl >= 0 else "pnl-down"
        pnl_sign = "+" if pnl >= 0 else ""

        # Progress bar color
        if prog_pct < 25:
            bar_color = "var(--red)"
        elif prog_pct < 50:
            bar_color = "var(--gold)"
        elif prog_pct < 75:
            bar_color = "#666"
        else:
            bar_color = "var(--green)"

        # Build compact row
        rows_html += f'<tr class="{row_class}"><td class="col-ticker">{ticker}</td><td class="col-value">${market_value:,.0f}</td><td class="col-pnl {pnl_class}">{pnl_sign}${abs(pnl):,.0f}</td><td class="col-pct {pnl_class}">{pnl_sign}{pnl_pct:.1f}%</td><td class="col-bar"><div class="mini-bar"><div class="mini-fill" style="width:{prog_pct}%;background:{bar_color}"></div></div></td><td class="col-status"><span class="{status_class}">{status}</span></td></tr>'

    table_html = f'<table class="pos-table"><thead><tr><th>Ticker</th><th>Value</th><th>P&L</th><th>%</th><th>Progress</th><th></th></tr></thead><tbody>{rows_html}</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)

else:
    st.markdown('<div style="text-align:center; padding: 2rem; color: var(--text-faint);">No positions yet</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# RECENT ACTIVITY
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-head"><span class="section-title">Recent Activity</span></div>', unsafe_allow_html=True)

if not transactions_df.empty:
    recent = transactions_df.tail(8).iloc[::-1]

    for _, tx in recent.iterrows():
        action = tx["action"]
        badge_class = "buy" if action == "BUY" else "sell"
        ticker = tx["ticker"]
        shares = int(tx["shares"])
        price = tx["price"]
        date = tx["date"]
        html = f'<div class="tx-item"><span class="tx-badge {badge_class}">{action}</span><span class="tx-ticker">{ticker}</span><span class="tx-detail">{shares} @ ${price:.2f}</span><span class="tx-date">{date}</span></div>'
        st.markdown(html, unsafe_allow_html=True)
else:
    st.markdown('<div style="text-align:center; padding: 2rem; color: var(--text-faint);">No transactions yet</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# AI INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════
chat_ready, _ = check_chat_setup()

if chat_ready:
    from execute_intelligence import execute_actions

    st.markdown('<div class="section-head"><span class="section-title">AI Intelligence</span></div>', unsafe_allow_html=True)

    if "ai_recommendations" not in st.session_state:
        st.session_state.ai_recommendations = None

    actions = st.session_state.ai_recommendations

    col1, col2 = st.columns(2)
    with col1:
        if st.button("ANALYZE PORTFOLIO", use_container_width=True):
            with st.spinner("Analyzing..."):
                try:
                    result = run_intelligence()
                    st.session_state.ai_recommendations = result.get("actions", [])
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        has_executable = False
        if actions:
            has_executable = any(a.get("safety_check") == "PASSED" and a.get("action") != "HOLD" for a in actions if "error" not in a)

        if st.button("EXECUTE", use_container_width=True, disabled=not has_executable, type="primary"):
            with st.spinner("Executing..."):
                try:
                    results = execute_actions(actions)
                    executed = sum(1 for r in results if r.get("result", {}).get("status") == "EXECUTED")
                    st.success(f"Executed {executed} action(s)")
                    st.session_state.ai_recommendations = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    if actions:
        for action in actions:
            if "error" in action:
                continue
            action_type = action.get("action", "")
            ticker = action.get("ticker", "-")
            reason = action.get("reason", "")
            safety = action.get("safety_check", "")

            color = "#22c55e" if action_type in ["BUY", "ADD"] else "#ef4444" if action_type in ["SELL", "TRIM"] else "#666"
            blocked = " (BLOCKED)" if safety == "BLOCKED" else ""

            st.markdown(f'<div style="padding: 0.5rem; border-left: 3px solid {color}; margin: 0.5rem 0; background: var(--card);"><strong>{action_type}</strong> {ticker}{blocked}<br><span style="font-size: 0.8rem; color: var(--text-dim);">{reason}</span></div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════
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
                result = subprocess.run(["bash", "run_daily.sh"], cwd=project_root, capture_output=True, text=True, timeout=600)
                if result.returncode == 0:
                    st.success("Done!")
                    st.rerun()
                else:
                    st.error("Failed")
                    st.code(result.stderr or result.stdout)
            except Exception as e:
                st.error(f"Error: {e}")

with col3:
    if st.button("DISCOVER", use_container_width=True):
        with st.spinner("Discovering..."):
            try:
                project_root = Path(__file__).parent.parent
                result = subprocess.run([sys.executable, "scripts/stock_discovery.py"], cwd=project_root, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    st.success("Done!")
                    st.code(result.stdout[-2000:])
                else:
                    st.error("Failed")
            except Exception as e:
                st.error(f"Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT
# ═══════════════════════════════════════════════════════════════════════════════
if chat_ready:
    st.markdown('<div class="section-head"><span class="section-title">Ask Mommy</span></div>', unsafe_allow_html=True)

    user_question = st.text_input("Question", placeholder="Which positions should I watch?", label_visibility="collapsed")

    if user_question:
        with st.spinner("Thinking..."):
            response = ai_chat(user_question)
        if response.success:
            st.markdown(f'<div style="background: var(--card); padding: 1rem; border-radius: 6px; margin-top: 0.5rem; color: var(--text-dim); font-size: 0.85rem; white-space: pre-wrap;">{response.message}</div>', unsafe_allow_html=True)
        else:
            st.error(response.error)


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
mode_indicator = "PAPER MODE" if paper_mode else "LIVE"
st.markdown(f'<div class="footer">{mode_indicator} · Data Delayed · Not Financial Advice</div>', unsafe_allow_html=True)
