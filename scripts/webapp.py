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

/* Section headers */
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 1.5rem 0 0.75rem 0; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }
.section-title { font-size: 0.75rem; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.1em; }
.section-badge { font-size: 0.65rem; color: var(--text-faint); }

/* Position cards - NEW DESIGN */
.pos-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 0.75rem; }
.pos-card:hover { background: var(--card-hover); }
.pos-card.alert { border-left: 3px solid var(--gold); }
.pos-card.winner { border-left: 3px solid var(--green); }

.pos-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem; }
.pos-ticker { font-size: 1.25rem; font-weight: 600; color: var(--text); }
.pos-pnl { text-align: right; }
.pos-pnl-value { font-size: 1.1rem; font-weight: 600; }
.pos-pnl-value.green { color: var(--green); }
.pos-pnl-value.red { color: var(--red); }
.pos-pnl-pct { font-size: 0.8rem; color: var(--text-dim); }

.pos-meta { display: flex; gap: 2rem; margin-bottom: 0.75rem; font-size: 0.8rem; color: var(--text-dim); }
.pos-meta-item { display: flex; flex-direction: column; }
.pos-meta-label { font-size: 0.6rem; color: var(--text-faint); text-transform: uppercase; margin-bottom: 0.1rem; }
.pos-meta-value { color: var(--text); }

.pos-bar-container { margin: 0.75rem 0; }
.pos-bar-labels { display: flex; justify-content: space-between; font-size: 0.65rem; color: var(--text-faint); margin-bottom: 0.3rem; }
.pos-bar { height: 6px; background: linear-gradient(90deg, var(--red) 0%, var(--red) 20%, var(--gold) 20%, var(--gold) 40%, #444 40%, #444 60%, var(--green) 60%, var(--green) 100%); border-radius: 3px; position: relative; }
.pos-bar-marker { position: absolute; top: 50%; transform: translate(-50%, -50%); width: 14px; height: 14px; background: white; border: 2px solid var(--bg); border-radius: 50%; box-shadow: 0 0 8px rgba(255,255,255,0.4); }
.pos-bar-entry { position: absolute; top: -2px; height: 10px; width: 2px; background: var(--text-faint); transform: translateX(-50%); }

.pos-stops { display: flex; justify-content: space-between; font-size: 0.75rem; margin-top: 0.5rem; }
.pos-stop { color: var(--red); }
.pos-target { color: var(--green); }

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

summary_html = f'''
<div class="summary-grid">
    <div class="summary-card">
        <div class="summary-label">Total Equity</div>
        <div class="summary-value">${total_equity:,.0f}</div>
        <div class="summary-sub">{total_sign}{total_return_pct:.1f}% all-time</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">Today</div>
        <div class="summary-value {day_class}">{day_sign}${abs(day_pnl):,.0f}</div>
        <div class="summary-sub">{day_sign}{day_pnl_pct:.2f}%</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">Unrealized P&L</div>
        <div class="summary-value {unrealized_class}">{unrealized_sign}${abs(total_unrealized):,.0f}</div>
        <div class="summary-sub">{num_positions} positions</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">Cash</div>
        <div class="summary-value">${cash:,.0f}</div>
        <div class="summary-sub">{(cash/total_equity*100):.0f}% reserve</div>
    </div>
</div>
'''
st.markdown(summary_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# POSITIONS
# ═══════════════════════════════════════════════════════════════════════════════
near_stop = get_positions_near_stop(positions_df, threshold_pct=5.0)
near_target = get_positions_near_target(positions_df, threshold_pct=8.0)

alert_count = len(near_stop)
badge_text = f"{alert_count} need attention" if alert_count > 0 else f"{num_positions} positions"

st.markdown(f'<div class="section-head"><span class="section-title">Positions</span><span class="section-badge">{badge_text}</span></div>', unsafe_allow_html=True)

if not positions_df.empty:
    # Sort by attention priority then by P&L
    positions_sorted = positions_df.copy()
    near_stop_tickers = [p['ticker'] for p in near_stop]
    positions_sorted['_priority'] = positions_sorted['ticker'].apply(lambda t: 0 if t in near_stop_tickers else 1)
    positions_sorted = positions_sorted.sort_values(['_priority', 'unrealized_pnl_pct'], ascending=[True, False])

    for _, row in positions_sorted.iterrows():
        ticker = row['ticker']
        shares = int(row['shares'])
        entry_price = row['avg_cost_basis']
        current_price = row['current_price']
        market_value = row['market_value']
        pnl = row['unrealized_pnl']
        pnl_pct = row['unrealized_pnl_pct']
        stop_loss = row.get('stop_loss', entry_price * 0.92)
        take_profit = row.get('take_profit', entry_price * 1.20)
        entry_date = row.get('entry_date', '')

        # Calculate days held
        try:
            entry_dt = pd.to_datetime(entry_date)
            days_held = (datetime.now() - entry_dt).days
        except:
            days_held = 0

        # Progress calculation
        progress = calculate_position_progress(row)
        if progress:
            marker_pct = progress['progress_pct']
            zone = progress['zone']
        else:
            marker_pct = 50
            zone = 'neutral'

        # Entry marker position
        if stop_loss < entry_price < take_profit:
            entry_marker_pct = ((entry_price - stop_loss) / (take_profit - stop_loss)) * 100
        else:
            entry_marker_pct = 50

        # Card styling
        card_class = ""
        if zone in ['danger', 'caution']:
            card_class = "alert"
        elif zone in ['winning', 'near_target']:
            card_class = "winner"

        # P&L styling
        pnl_class = "green" if pnl >= 0 else "red"
        pnl_sign = "+" if pnl >= 0 else ""

        # Distance to stop/target
        stop_dist = ((current_price - stop_loss) / current_price) * 100
        target_dist = ((take_profit - current_price) / current_price) * 100

        # Position % of portfolio
        port_pct = (market_value / total_equity) * 100 if total_equity > 0 else 0

        html = f'''
        <div class="pos-card {card_class}">
            <div class="pos-top">
                <div>
                    <span class="pos-ticker">{ticker}</span>
                </div>
                <div class="pos-pnl">
                    <div class="pos-pnl-value {pnl_class}">{pnl_sign}${abs(pnl):,.2f}</div>
                    <div class="pos-pnl-pct">{pnl_sign}{pnl_pct:.1f}%</div>
                </div>
            </div>

            <div class="pos-meta">
                <div class="pos-meta-item">
                    <span class="pos-meta-label">Shares</span>
                    <span class="pos-meta-value">{shares}</span>
                </div>
                <div class="pos-meta-item">
                    <span class="pos-meta-label">Value</span>
                    <span class="pos-meta-value">${market_value:,.0f}</span>
                </div>
                <div class="pos-meta-item">
                    <span class="pos-meta-label">% Portfolio</span>
                    <span class="pos-meta-value">{port_pct:.1f}%</span>
                </div>
                <div class="pos-meta-item">
                    <span class="pos-meta-label">Entry</span>
                    <span class="pos-meta-value">${entry_price:.2f}</span>
                </div>
                <div class="pos-meta-item">
                    <span class="pos-meta-label">Current</span>
                    <span class="pos-meta-value">${current_price:.2f}</span>
                </div>
                <div class="pos-meta-item">
                    <span class="pos-meta-label">Days Held</span>
                    <span class="pos-meta-value">{days_held}</span>
                </div>
            </div>

            <div class="pos-bar-container">
                <div class="pos-bar-labels">
                    <span>Stop ${stop_loss:.0f} ({stop_dist:.0f}% away)</span>
                    <span>Target ${take_profit:.0f} ({target_dist:.0f}% away)</span>
                </div>
                <div class="pos-bar">
                    <div class="pos-bar-entry" style="left: {entry_marker_pct}%;"></div>
                    <div class="pos-bar-marker" style="left: {marker_pct}%;"></div>
                </div>
            </div>
        </div>
        '''
        st.markdown(html, unsafe_allow_html=True)

else:
    st.markdown('<div style="text-align:center; padding: 3rem; color: var(--text-faint);">No positions yet</div>', unsafe_allow_html=True)


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

        html = f'''
        <div class="tx-item">
            <span class="tx-badge {badge_class}">{action}</span>
            <span class="tx-ticker">{ticker}</span>
            <span class="tx-detail">{shares} shares @ ${price:.2f}</span>
            <span class="tx-date">{date}</span>
        </div>
        '''
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
