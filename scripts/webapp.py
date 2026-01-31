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
import numpy as np
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
from webapp_helpers import (
    generate_status_sentence,
    calculate_position_progress,
    get_positions_near_stop,
    get_positions_near_target,
)
from unified_analysis import run_unified_analysis, execute_approved_actions
from ai_review import ReviewDecision

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


def get_trade_stats(transactions_df):
    """Calculate detailed trade statistics."""
    if transactions_df.empty:
        return {}

    sells = transactions_df[transactions_df['action'] == 'SELL'].copy()
    if sells.empty:
        return {}

    # Calculate P&L for each sell by matching with buys
    stats = {
        'total_trades': len(sells),
        'winning_trades': 0,
        'losing_trades': 0,
        'total_pnl': 0,
        'avg_win': 0,
        'avg_loss': 0,
        'largest_win': 0,
        'largest_loss': 0,
        'profit_factor': 0,
    }

    try:
        analyzer = TradeAnalyzer()
        analysis = analyzer.analyze()
        if analysis:
            stats['winning_trades'] = analysis.get('winning_trades', 0)
            stats['losing_trades'] = analysis.get('losing_trades', 0)
            stats['total_pnl'] = analysis.get('total_realized_pnl', 0)
            stats['avg_win'] = analysis.get('avg_win', 0)
            stats['avg_loss'] = analysis.get('avg_loss', 0)
            stats['largest_win'] = analysis.get('best_trade_pnl', 0)
            stats['largest_loss'] = analysis.get('worst_trade_pnl', 0)
            stats['profit_factor'] = analysis.get('profit_factor', 0)
            stats['win_rate'] = analysis.get('win_rate', 0)
    except:
        pass

    return stats


def close_all_positions():
    """Emergency close all positions - creates SELL transactions for each position."""
    import uuid
    from datetime import date as dt_date
    from schema import TRANSACTION_COLUMNS, Action, Reason

    positions_df = load_positions()
    if positions_df.empty:
        return 0, "No positions to close"

    transactions = []
    for _, pos in positions_df.iterrows():
        tx = {
            "transaction_id": str(uuid.uuid4())[:8],
            "date": dt_date.today().isoformat(),
            "ticker": pos['ticker'],
            "action": "SELL",
            "shares": pos['shares'],
            "price": pos['current_price'],
            "total_value": round(pos['shares'] * pos['current_price'], 2),
            "stop_loss": "",
            "take_profit": "",
            "reason": "MANUAL",
            "regime_at_entry": "",
            "composite_score": "",
            "factor_scores": "",
            "signal_rank": "",
        }
        transactions.append(tx)

    # Append to transactions file
    files = get_data_files()
    df_new = pd.DataFrame(transactions)

    if files["transactions"].exists():
        df_existing = pd.read_csv(files["transactions"])
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new

    df_combined.to_csv(files["transactions"], index=False)

    # Clear positions file
    pd.DataFrame(columns=positions_df.columns).to_csv(files["positions"], index=False)

    return len(transactions), f"Closed {len(transactions)} positions"


# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MOMMY",
    page_icon="💚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

paper_mode = is_paper_mode()

# Initialize session state
if "unified_analysis" not in st.session_state:
    st.session_state.unified_analysis = None
if "show_execute_confirm" not in st.session_state:
    st.session_state.show_execute_confirm = False
if "show_close_all_confirm" not in st.session_state:
    st.session_state.show_close_all_confirm = False
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if "chart_timeframe" not in st.session_state:
    st.session_state.chart_timeframe = "1M"

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
.block-container { padding: 1rem 2rem 2rem 2rem !important; max-width: 1200px !important; }

/* Header bar */
.header-bar { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; margin-bottom: 1rem; border-bottom: 1px solid var(--border); }
.header-title { font-size: 1.1rem; font-weight: 600; color: var(--text); letter-spacing: 0.1em; }

/* Summary cards */
.summary-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.75rem; margin-bottom: 1rem; }
.summary-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 0.875rem 1rem; position: relative; }
.summary-label { font-size: 0.6rem; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.2rem; }
.summary-value { font-size: 1.3rem; font-weight: 500; color: var(--text); }
.summary-value.green { color: var(--green); }
.summary-value.red { color: var(--red); }
.summary-sub { font-size: 0.7rem; color: var(--text-dim); margin-top: 0.2rem; }
.sparkline { position: absolute; bottom: 8px; right: 10px; width: 50px; height: 20px; }

/* Risk metrics row */
.metrics-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.75rem; margin-bottom: 1rem; }
.metric-card { background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 0.6rem 0.8rem; text-align: center; }
.metric-label { font-size: 0.55rem; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.05em; }
.metric-value { font-size: 1rem; font-weight: 600; color: var(--text); margin-top: 0.15rem; }
.metric-value.good { color: var(--green); }
.metric-value.warn { color: var(--gold); }
.metric-value.bad { color: var(--red); }

/* Insight box */
.insight-box { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 0.875rem 1rem; margin-bottom: 1rem; border-left: 3px solid var(--text-faint); }
.insight-box.insight-good { border-left-color: var(--green); }
.insight-box.insight-warn { border-left-color: var(--gold); }
.insight-box.insight-alert { border-left-color: var(--red); }
.insight-status { font-size: 0.9rem; color: var(--text); margin-bottom: 0.4rem; }
.insight-items { display: flex; flex-wrap: wrap; gap: 0.75rem; }
.insight-item { display: flex; align-items: center; gap: 0.35rem; font-size: 0.7rem; color: var(--text-dim); }
.insight-dot { width: 5px; height: 5px; border-radius: 50%; }
.dot-good { background: var(--green); }
.dot-warn { background: var(--gold); }
.dot-neutral { background: var(--text-faint); }

/* Section headers */
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 1.25rem 0 0.6rem 0; padding-bottom: 0.4rem; border-bottom: 1px solid var(--border); }
.section-title { font-size: 0.7rem; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.1em; }
.section-badge { font-size: 0.6rem; color: var(--text-faint); }

/* Status bar */
.status-bar { display: flex; gap: 1rem; align-items: center; font-size: 0.65rem; color: var(--text-faint); padding: 0.4rem 0; margin-bottom: 0.5rem; }
.status-item { display: flex; align-items: center; gap: 0.3rem; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; }
.status-dot.green { background: var(--green); }
.status-dot.yellow { background: var(--gold); }
.status-dot.red { background: var(--red); }

/* Positions table */
.pos-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.pos-table th { text-align: left; padding: 0.45rem 0.6rem; font-size: 0.6rem; font-weight: 500; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border); cursor: pointer; }
.pos-table th:hover { color: var(--text-dim); }
.pos-table td { padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
.pos-table tr:hover { background: var(--card); }
.pos-table tr.row-win { background: rgba(34,197,94,0.04); }
.pos-table tr.row-lose { background: rgba(239,68,68,0.04); }
.pos-table tr.row-alert { background: rgba(234,179,8,0.06); }

.col-ticker { font-weight: 600; color: var(--text); }
.col-dim { color: var(--text-dim); }
.col-small { font-size: 0.7rem; color: var(--text-faint); }
.pnl-up { color: var(--green); }
.pnl-down { color: var(--red); }

.mini-bar { width: 60px; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
.mini-fill { height: 100%; border-radius: 2px; }

/* Tooltip */
.tooltip { position: relative; cursor: help; border-bottom: 1px dotted var(--text-faint); }
.tooltip:hover::after { content: attr(data-tip); position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); background: #222; color: var(--text); padding: 0.4rem 0.6rem; border-radius: 4px; font-size: 0.65rem; white-space: nowrap; z-index: 100; }

/* Transaction list */
.tx-item { display: flex; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid var(--border); gap: 0.75rem; font-size: 0.8rem; }
.tx-badge { font-size: 0.55rem; font-weight: 600; padding: 0.15rem 0.4rem; border-radius: 3px; min-width: 28px; text-align: center; }
.tx-badge.buy { background: var(--green-bg); color: var(--green); }
.tx-badge.sell { background: var(--red-bg); color: var(--red); }
.tx-ticker { font-weight: 500; color: var(--text); min-width: 45px; }
.tx-detail { color: var(--text-dim); font-size: 0.75rem; flex: 1; }
.tx-pnl { font-weight: 500; min-width: 60px; text-align: right; }
.tx-date { color: var(--text-faint); font-size: 0.7rem; }

/* AI recommendation cards */
.ai-card { background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 0.75rem; margin-bottom: 0.5rem; }
.ai-card.blocked { opacity: 0.5; }
.ai-action { font-weight: 600; font-size: 0.85rem; }
.ai-action.buy { color: var(--green); }
.ai-action.sell { color: var(--red); }
.ai-action.hold { color: var(--text-dim); }
.ai-ticker { font-weight: 500; color: var(--text); }
.ai-reason { font-size: 0.75rem; color: var(--text-dim); margin-top: 0.3rem; }
.ai-confidence { font-size: 0.65rem; color: var(--text-faint); margin-top: 0.2rem; }

/* Confirmation modal */
.confirm-box { background: var(--card); border: 2px solid var(--gold); border-radius: 8px; padding: 1rem; margin: 0.5rem 0; }
.confirm-title { font-weight: 600; color: var(--gold); margin-bottom: 0.5rem; }
.confirm-list { font-size: 0.8rem; color: var(--text-dim); }

/* Emergency button */
.emergency-btn { background: transparent !important; color: var(--red) !important; border: 1px solid var(--red) !important; font-size: 0.6rem !important; padding: 0.3rem 0.6rem !important; opacity: 0.6; }
.emergency-btn:hover { opacity: 1 !important; background: var(--red-bg) !important; }

/* Buttons */
.stButton > button { background: var(--card) !important; color: var(--text-dim) !important; border: 1px solid var(--border) !important; border-radius: 6px !important; font-size: 0.65rem !important; letter-spacing: 0.05em !important; text-transform: uppercase !important; }
.stButton > button:hover { background: var(--card-hover) !important; border-color: var(--green) !important; color: var(--text) !important; }
.stButton > button[kind="primary"] { background: var(--green-bg) !important; border-color: var(--green) !important; color: var(--green) !important; }

/* Chart container */
.chart-container { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
.chart-controls { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
.chart-btn { padding: 0.25rem 0.6rem; font-size: 0.65rem; border: 1px solid var(--border); border-radius: 4px; background: transparent; color: var(--text-dim); cursor: pointer; }
.chart-btn.active { background: var(--green-bg); border-color: var(--green); color: var(--green); }

/* Mommy Chat */
.mommy-chat { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1rem; margin-bottom: 1rem; }
.mommy-chat-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; }
.mommy-avatar { width: 32px; height: 32px; background: linear-gradient(135deg, #22c55e, #16a34a); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.9rem; }
.mommy-name { font-weight: 600; color: var(--text); font-size: 0.85rem; }
.mommy-status { font-size: 0.65rem; color: var(--green); }
.mommy-input-row { display: flex; gap: 0.5rem; }
.mommy-response { background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.2); border-radius: 8px; padding: 0.875rem; margin-top: 0.75rem; font-size: 0.85rem; color: var(--text); line-height: 1.5; }
.mommy-response::before { content: '"'; font-size: 1.5rem; color: var(--green); opacity: 0.5; margin-right: 0.25rem; }

/* Footer */
.footer { text-align: center; padding: 1.5rem 0 1rem 0; font-size: 0.55rem; color: var(--text-faint); letter-spacing: 0.1em; text-transform: uppercase; border-top: 1px solid var(--border); margin-top: 1.5rem; }

/* Responsive */
@media (max-width: 768px) {
    .summary-grid { grid-template-columns: repeat(2, 1fr); }
    .metrics-grid { grid-template-columns: repeat(3, 1fr); }
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

# Calculate additional metrics
total_invested = positions_df["market_value"].sum() if not positions_df.empty else 0
buying_power = cash

# Get analytics
try:
    analytics = PortfolioAnalytics()
    metrics = analytics.calculate_metrics()
    sharpe_ratio = metrics.get('sharpe_ratio', 0) if metrics else 0
    max_drawdown = metrics.get('max_drawdown_pct', 0) if metrics else 0
    sortino_ratio = metrics.get('sortino_ratio', 0) if metrics else 0
except:
    sharpe_ratio = max_drawdown = sortino_ratio = 0

# Get trade stats
trade_stats = get_trade_stats(transactions_df)
win_rate = trade_stats.get('win_rate', 0)
profit_factor = trade_stats.get('profit_factor', 0)
avg_win = trade_stats.get('avg_win', 0)
avg_loss = trade_stats.get('avg_loss', 0)

# Get regime
try:
    regime_analysis = get_regime_analysis()
    regime = regime_analysis.regime.value
except:
    regime = "UNKNOWN"

# Check API status
chat_ready, chat_error = check_chat_setup()
api_status = "green" if chat_ready else "red"
last_refresh = st.session_state.last_refresh.strftime("%H:%M:%S")


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS BAR
# ═══════════════════════════════════════════════════════════════════════════════
status_html = f'<div class="status-bar"><span class="status-item"><span class="status-dot {api_status}"></span>API {"Connected" if chat_ready else "Disconnected"}</span><span class="status-item">Last refresh: {last_refresh}</span><span class="status-item">Regime: {regime}</span></div>'
st.markdown(status_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER BAR WITH MODE TOGGLE AND EMERGENCY CONTROLS
# ═══════════════════════════════════════════════════════════════════════════════
col_title, col_emergency, col_mode = st.columns([2, 1, 1])

with col_title:
    st.markdown('<div class="header-title">M O M M Y</div>', unsafe_allow_html=True)

with col_emergency:
    if st.button("CLOSE ALL", key="close_all_btn", help="Emergency: Close all positions"):
        st.session_state.show_close_all_confirm = True

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

# Emergency confirmation dialog
if st.session_state.show_close_all_confirm:
    st.markdown('<div class="confirm-box"><div class="confirm-title">Confirm Close All Positions</div><div class="confirm-list">This will close ALL open positions at market price. This action cannot be undone.</div></div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("YES, CLOSE ALL", type="primary"):
            count, msg = close_all_positions()
            if count > 0:
                st.success(f"Closed {count} positions")
            else:
                st.info(msg)
            st.session_state.show_close_all_confirm = False
            st.rerun()
    with col2:
        if st.button("CANCEL"):
            st.session_state.show_close_all_confirm = False
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PRIMARY ACTIONS BAR (Top of page for easy access)
# ═══════════════════════════════════════════════════════════════════════════════
analysis = st.session_state.unified_analysis
has_executable = analysis.get("summary", {}).get("can_execute", False) if analysis else False

col_analyze, col_execute, col_discover, col_update, col_refresh = st.columns(5)

with col_analyze:
    if st.button("ANALYZE", use_container_width=True, type="primary", key="analyze_top"):
        with st.spinner("Running unified analysis..."):
            try:
                result = run_unified_analysis(dry_run=True)
                st.session_state.unified_analysis = result
                st.session_state.show_execute_confirm = False
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

with col_execute:
    if st.button("EXECUTE", use_container_width=True, disabled=not has_executable, key="execute_top"):
        st.session_state.show_execute_confirm = True

with col_discover:
    if st.button("DISCOVER", use_container_width=True, key="discover_top"):
        with st.spinner("Discovering..."):
            try:
                project_root = Path(__file__).parent.parent
                result = subprocess.run([sys.executable, "scripts/watchlist_manager.py", "--update"], cwd=project_root, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    st.success("Discovery complete!")
                else:
                    st.warning("Discovery skipped")
            except Exception as e:
                st.error(f"Error: {e}")

with col_update:
    if st.button("UPDATE", use_container_width=True, key="update_top"):
        with st.spinner("Updating prices..."):
            try:
                project_root = Path(__file__).parent.parent
                result = subprocess.run([sys.executable, "scripts/update_positions.py"], cwd=project_root, capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    st.success("Prices updated!")
                    st.rerun()
                else:
                    st.error("Update failed")
            except Exception as e:
                st.error(f"Error: {e}")

with col_refresh:
    if st.button("REFRESH", use_container_width=True, key="refresh_top"):
        st.session_state.last_refresh = datetime.now()
        st.rerun()

# Execute confirmation dialog (shown inline when triggered)
if st.session_state.show_execute_confirm and analysis:
    approved = analysis.get("approved", [])
    modified = analysis.get("modified", [])
    executable = approved + modified

    if executable:
        st.markdown('<div class="confirm-box"><div class="confirm-title">Confirm Execution</div><div class="confirm-list">The following trades will be executed:</div></div>', unsafe_allow_html=True)

        for r in executable:
            action = r.original
            shares = r.modified_shares or action.shares
            mod_note = " (modified)" if r.decision == ReviewDecision.MODIFY else ""
            st.markdown(f"- **{action.action_type}** {action.ticker}: {shares} shares @ ${action.price:.2f}{mod_note}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("EXECUTE NOW", type="primary", key="exec_confirm"):
                with st.spinner("Executing approved actions..."):
                    try:
                        result = execute_approved_actions(analysis)
                        executed = result.get("executed", 0)
                        st.success(f"Executed {executed} action(s)")
                        st.session_state.unified_analysis = None
                        st.session_state.show_execute_confirm = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col2:
            if st.button("CANCEL", key="exec_cancel"):
                st.session_state.show_execute_confirm = False
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY CARDS (Enhanced with 5 cards)
# ═══════════════════════════════════════════════════════════════════════════════
total_class = "green" if total_return >= 0 else "red"
day_class = "green" if day_pnl >= 0 else "red"
total_sign = "+" if total_return >= 0 else ""
day_sign = "+" if day_pnl >= 0 else ""

total_unrealized = positions_df["unrealized_pnl"].sum() if not positions_df.empty else 0
unrealized_class = "green" if total_unrealized >= 0 else "red"
unrealized_sign = "+" if total_unrealized >= 0 else ""

card1 = f'<div class="summary-card"><div class="summary-label">Total Equity</div><div class="summary-value">${total_equity:,.0f}</div><div class="summary-sub">{total_sign}{total_return_pct:.1f}% all-time</div></div>'
card2 = f'<div class="summary-card"><div class="summary-label">Today</div><div class="summary-value {day_class}">{day_sign}${abs(day_pnl):,.0f}</div><div class="summary-sub">{day_sign}{day_pnl_pct:.2f}%</div></div>'
card3 = f'<div class="summary-card"><div class="summary-label">Unrealized P&L</div><div class="summary-value {unrealized_class}">{unrealized_sign}${abs(total_unrealized):,.0f}</div><div class="summary-sub">{num_positions} positions</div></div>'
card4 = f'<div class="summary-card"><div class="summary-label">Cash / Buying Power</div><div class="summary-value">${cash:,.0f}</div><div class="summary-sub">{(cash/total_equity*100):.0f}% available</div></div>'
card5 = f'<div class="summary-card"><div class="summary-label">Invested</div><div class="summary-value">${total_invested:,.0f}</div><div class="summary-sub">{(total_invested/total_equity*100):.0f}% deployed</div></div>'
summary_html = f'<div class="summary-grid">{card1}{card2}{card3}{card4}{card5}</div>'
st.markdown(summary_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# RISK METRICS ROW
# ═══════════════════════════════════════════════════════════════════════════════
sharpe_class = "good" if sharpe_ratio > 1 else "warn" if sharpe_ratio > 0 else "bad"
dd_class = "good" if max_drawdown < 5 else "warn" if max_drawdown < 10 else "bad"
wr_class = "good" if win_rate > 50 else "warn" if win_rate > 40 else "bad"
pf_class = "good" if profit_factor > 1.5 else "warn" if profit_factor > 1 else "bad"

m1 = f'<div class="metric-card"><div class="metric-label" title="Risk-adjusted return measure">Sharpe Ratio</div><div class="metric-value {sharpe_class}">{sharpe_ratio:.2f}</div></div>'
m2 = f'<div class="metric-card"><div class="metric-label" title="Largest peak-to-trough decline">Max Drawdown</div><div class="metric-value {dd_class}">{max_drawdown:.1f}%</div></div>'
m3 = f'<div class="metric-card"><div class="metric-label" title="Percentage of winning trades">Win Rate</div><div class="metric-value {wr_class}">{win_rate:.0f}%</div></div>'
m4 = f'<div class="metric-card"><div class="metric-label" title="Gross profits / gross losses">Profit Factor</div><div class="metric-value {pf_class}">{profit_factor:.2f}</div></div>'
avg_win_loss = f"${avg_win:.0f} / ${abs(avg_loss):.0f}" if avg_loss != 0 else "N/A"
m5 = f'<div class="metric-card"><div class="metric-label" title="Average winning trade vs losing trade">Avg Win/Loss</div><div class="metric-value">{avg_win_loss}</div></div>'
metrics_html = f'<div class="metrics-grid">{m1}{m2}{m3}{m4}{m5}</div>'
st.markdown(metrics_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MOMMY CHAT (Top of page, nicer styling)
# ═══════════════════════════════════════════════════════════════════════════════
if chat_ready:
    chat_header = '<div class="mommy-chat-header"><div class="mommy-avatar">M</div><div><div class="mommy-name">Ask Mommy</div><div class="mommy-status">Online</div></div></div>'
    st.markdown(f'<div class="mommy-chat">{chat_header}', unsafe_allow_html=True)

    user_question = st.text_input("chat_input", placeholder="What should I know about my portfolio today?", label_visibility="collapsed", key="mommy_chat_top")

    if user_question:
        with st.spinner("Mommy is thinking..."):
            response = ai_chat(user_question)
        if response.success:
            # Make the response sound more like Mommy
            mommy_response = response.message
            st.markdown(f'<div class="mommy-response">{mommy_response}</div>', unsafe_allow_html=True)
        else:
            st.error(response.error)

    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EQUITY CURVE CHART
# ═══════════════════════════════════════════════════════════════════════════════
if not snapshots_df.empty:
    st.markdown('<div class="section-head"><span class="section-title">Equity Curve</span></div>', unsafe_allow_html=True)

    # Timeframe selector
    timeframes = ["1W", "1M", "3M", "YTD", "ALL"]
    cols = st.columns(len(timeframes))
    for i, tf in enumerate(timeframes):
        with cols[i]:
            if st.button(tf, key=f"tf_{tf}", use_container_width=True,
                        type="primary" if st.session_state.chart_timeframe == tf else "secondary"):
                st.session_state.chart_timeframe = tf
                st.rerun()

    # Filter data by timeframe
    chart_df = snapshots_df.copy()
    chart_df['date'] = pd.to_datetime(chart_df['date'])

    now = pd.Timestamp.now()
    if st.session_state.chart_timeframe == "1W":
        chart_df = chart_df[chart_df['date'] >= now - pd.Timedelta(days=7)]
    elif st.session_state.chart_timeframe == "1M":
        chart_df = chart_df[chart_df['date'] >= now - pd.Timedelta(days=30)]
    elif st.session_state.chart_timeframe == "3M":
        chart_df = chart_df[chart_df['date'] >= now - pd.Timedelta(days=90)]
    elif st.session_state.chart_timeframe == "YTD":
        chart_df = chart_df[chart_df['date'] >= pd.Timestamp(now.year, 1, 1)]

    if not chart_df.empty:
        chart_df = chart_df.set_index('date')
        st.line_chart(chart_df['total_equity'], use_container_width=True, height=200)


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS INSIGHT
# ═══════════════════════════════════════════════════════════════════════════════
near_stop = get_positions_near_stop(positions_df, threshold_pct=5.0)
near_target = get_positions_near_target(positions_df, threshold_pct=8.0)

if not snapshots_df.empty:
    peak_equity = snapshots_df['total_equity'].max()
    current_drawdown = ((peak_equity - total_equity) / peak_equity) * 100 if peak_equity > 0 else 0
else:
    current_drawdown = 0

try:
    preservation = get_preservation_status()
    preservation_active = preservation.get('preservation_mode', False)
except:
    preservation_active = False

status_sentence, sentiment = generate_status_sentence(
    positions_df, snapshots_df, day_pnl,
    regime=regime, preservation_active=preservation_active, drawdown_pct=current_drawdown
)

insights = []
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
    # Count unique tickers bought, not total transactions
    unique_new_positions = recent_buys['ticker'].nunique() if not recent_buys.empty else 0
    if unique_new_positions > 0:
        insights.append(('neutral', f'{unique_new_positions} new position{"s" if unique_new_positions > 1 else ""} opened'))

if near_stop:
    for pos in near_stop[:2]:
        insights.append(('warn', f'{pos["ticker"]} {pos["distance_pct"]:.0f}% from stop'))
if near_target:
    for pos in near_target[:2]:
        insights.append(('good', f'{pos["ticker"]} {pos["distance_pct"]:.0f}% from target'))

sentiment_class = {'calm': 'insight-calm', 'positive': 'insight-good', 'attention': 'insight-warn', 'warning': 'insight-alert'}.get(sentiment, 'insight-calm')
insight_items = "".join([f'<span class="insight-item"><span class="insight-dot dot-{t}"></span>{txt}</span>' for t, txt in insights[:4]])
insight_html = f'<div class="insight-box {sentiment_class}"><div class="insight-status">{status_sentence}</div>'
if insight_items:
    insight_html += f'<div class="insight-items">{insight_items}</div>'
insight_html += '</div>'
st.markdown(insight_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# POSITIONS TABLE (Enhanced)
# ═══════════════════════════════════════════════════════════════════════════════
near_stop_tickers = {p['ticker'] for p in near_stop}
near_target_tickers = {p['ticker'] for p in near_target}

if not positions_df.empty:
    winners = len(positions_df[positions_df['unrealized_pnl'] > 0])
    losers = len(positions_df[positions_df['unrealized_pnl'] <= 0])
else:
    winners = losers = 0

st.markdown(f'<div class="section-head"><span class="section-title">Positions</span><span class="section-badge">{winners}W / {losers}L · {num_positions} open</span></div>', unsafe_allow_html=True)

if not positions_df.empty:
    positions_sorted = positions_df.copy()
    positions_sorted['_priority'] = positions_sorted['ticker'].apply(lambda t: 0 if t in near_stop_tickers else (1 if t in near_target_tickers else 2))
    positions_sorted = positions_sorted.sort_values(['_priority', 'unrealized_pnl_pct'], ascending=[True, False])

    rows_html = ""
    for _, row in positions_sorted.iterrows():
        ticker = row['ticker']
        shares = int(row.get('shares', 0))
        entry_price = row['avg_cost_basis']
        current_price = row['current_price']
        market_value = row['market_value']
        pnl = row['unrealized_pnl']
        pnl_pct = row['unrealized_pnl_pct']
        stop_loss = row.get('stop_loss', entry_price * 0.92)
        take_profit = row.get('take_profit', entry_price * 1.20)
        entry_date = row.get('entry_date', '')

        # Days held
        try:
            days_held = (datetime.now() - pd.to_datetime(entry_date)).days
        except:
            days_held = 0

        # Portfolio weight
        port_weight = (market_value / total_equity) * 100 if total_equity > 0 else 0

        # Progress
        progress = calculate_position_progress(row)
        prog_pct = progress['progress_pct'] if progress else 50

        # Row styling
        if ticker in near_stop_tickers:
            row_class = "row-alert"
        elif pnl >= 0:
            row_class = "row-win"
        else:
            row_class = "row-lose"

        pnl_class = "pnl-up" if pnl >= 0 else "pnl-down"
        pnl_sign = "+" if pnl >= 0 else ""

        bar_color = "var(--red)" if prog_pct < 25 else "var(--gold)" if prog_pct < 50 else "#666" if prog_pct < 75 else "var(--green)"

        rows_html += f'<tr class="{row_class}"><td class="col-ticker">{ticker}</td><td class="col-dim">{shares}</td><td class="col-dim">${entry_price:.2f}</td><td class="col-dim">${current_price:.2f}</td><td class="col-dim">${market_value:,.0f}</td><td class="{pnl_class}">{pnl_sign}${abs(pnl):,.0f}</td><td class="{pnl_class}">{pnl_sign}{pnl_pct:.1f}%</td><td class="col-small">{port_weight:.1f}%</td><td class="col-small">{days_held}d</td><td class="col-small">${stop_loss:.0f}</td><td class="col-small">${take_profit:.0f}</td><td><div class="mini-bar"><div class="mini-fill" style="width:{prog_pct}%;background:{bar_color}"></div></div></td></tr>'

    header = '<tr><th>Ticker</th><th>Shares</th><th>Entry</th><th>Current</th><th>Value</th><th>P&L</th><th>%</th><th>Weight</th><th>Days</th><th>Stop</th><th>Target</th><th title="Position between stop loss (0%) and take profit (100%)">Progress</th></tr>'
    table_html = f'<table class="pos-table"><thead>{header}</thead><tbody>{rows_html}</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
else:
    st.markdown('<div style="text-align:center; padding: 1.5rem; color: var(--text-faint);">No positions yet</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO COMPOSITION
# ═══════════════════════════════════════════════════════════════════════════════
if not positions_df.empty and num_positions > 0:
    st.markdown('<div class="section-head"><span class="section-title">Portfolio Composition</span></div>', unsafe_allow_html=True)

    col_chart, col_metrics = st.columns([2, 1])

    with col_chart:
        # Create pie chart data
        chart_data = positions_df[['ticker', 'market_value']].copy()
        chart_data = chart_data.sort_values('market_value', ascending=False)

        # Add cash as a slice
        cash_row = pd.DataFrame({'ticker': ['Cash'], 'market_value': [cash]})
        chart_data = pd.concat([chart_data, cash_row], ignore_index=True)

        # Calculate percentages
        chart_data['percentage'] = (chart_data['market_value'] / total_equity * 100).round(1)

        # Use plotly for donut chart
        try:
            import plotly.graph_objects as go

            colors = ['#22c55e', '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#06b6d4', '#84cc16', '#f43f5e', '#6366f1', '#14b8a6']
            # Add gray for cash
            chart_colors = colors[:len(chart_data)-1] + ['#374151']

            fig = go.Figure(data=[go.Pie(
                labels=chart_data['ticker'],
                values=chart_data['market_value'],
                hole=0.6,
                textinfo='label+percent',
                textposition='outside',
                marker=dict(colors=chart_colors[:len(chart_data)]),
                textfont=dict(size=11, color='rgba(255,255,255,0.8)'),
            )])

            fig.update_layout(
                showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=20, b=20, l=20, r=20),
                height=250,
                annotations=[dict(
                    text=f'${total_equity:,.0f}',
                    x=0.5, y=0.5,
                    font=dict(size=16, color='rgba(255,255,255,0.9)'),
                    showarrow=False
                )]
            )

            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        except ImportError:
            # Fallback to simple bar if plotly not available
            st.bar_chart(chart_data.set_index('ticker')['market_value'], height=200)

    with col_metrics:
        # Diversification metrics
        if len(positions_df) > 0:
            weights = positions_df['market_value'] / total_equity
            # Herfindahl-Hirschman Index (lower is more diversified)
            hhi = (weights ** 2).sum()
            # Effective number of positions (1/HHI)
            effective_n = 1 / hhi if hhi > 0 else 0
            # Largest position weight
            max_weight = weights.max() * 100
            # Concentration (top 3)
            top3_weight = weights.nlargest(3).sum() * 100 if len(weights) >= 3 else weights.sum() * 100

            # Diversification health score (0-100)
            # Good: effective_n close to actual n, max_weight < 15%, top3 < 50%
            div_score = min(100, (effective_n / num_positions) * 50 + (1 - max_weight/30) * 25 + (1 - top3_weight/75) * 25)
            div_score = max(0, div_score)

            if div_score >= 70:
                div_status = "Good"
                div_color = "var(--green)"
            elif div_score >= 40:
                div_status = "Moderate"
                div_color = "var(--gold)"
            else:
                div_status = "Concentrated"
                div_color = "var(--red)"

            metrics_html = f'''
            <div style="font-size: 0.75rem; color: var(--text-dim);">
                <div style="margin-bottom: 0.75rem;">
                    <div style="font-size: 0.6rem; color: var(--text-faint); text-transform: uppercase;">Diversification</div>
                    <div style="font-size: 1.1rem; font-weight: 600; color: {div_color};">{div_status}</div>
                </div>
                <div style="margin-bottom: 0.5rem;">
                    <span style="color: var(--text-faint);">Largest Position:</span> {max_weight:.1f}%
                </div>
                <div style="margin-bottom: 0.5rem;">
                    <span style="color: var(--text-faint);">Top 3 Concentration:</span> {top3_weight:.1f}%
                </div>
                <div style="margin-bottom: 0.5rem;">
                    <span style="color: var(--text-faint);">Cash Reserve:</span> {(cash/total_equity*100):.1f}%
                </div>
                <div>
                    <span style="color: var(--text-faint);">Positions:</span> {num_positions}
                </div>
            </div>
            '''
            st.markdown(metrics_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# RECENT ACTIVITY (Enhanced)
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-head"><span class="section-title">Recent Activity</span></div>', unsafe_allow_html=True)

if not transactions_df.empty:
    recent = transactions_df.tail(10).iloc[::-1]

    for _, tx in recent.iterrows():
        action = tx["action"]
        badge_class = "buy" if action == "BUY" else "sell"
        ticker = tx["ticker"]
        shares = int(tx["shares"])
        price = tx["price"]
        total_val = tx.get("total_value", shares * price)
        date_str = str(tx["date"])
        reason = tx.get("reason", "")

        # For sells, show P&L if available
        pnl_html = ""
        if action == "SELL" and reason in ["STOP_LOSS", "TAKE_PROFIT"]:
            reason_text = " (Stop)" if reason == "STOP_LOSS" else " (Target)"
            pnl_html = f'<span class="tx-detail" style="color: var(--{"red" if reason == "STOP_LOSS" else "green"})">{reason_text}</span>'

        html = f'<div class="tx-item"><span class="tx-badge {badge_class}">{action}</span><span class="tx-ticker">{ticker}</span><span class="tx-detail">{shares} @ ${price:.2f} = ${total_val:,.0f}</span>{pnl_html}<span class="tx-date">{date_str}</span></div>'
        st.markdown(html, unsafe_allow_html=True)
else:
    st.markdown('<div style="text-align:center; padding: 1.5rem; color: var(--text-faint);">No transactions yet</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS RESULTS (Shows when analysis is run from top buttons)
# ═══════════════════════════════════════════════════════════════════════════════
if analysis:
    st.markdown('<div class="section-head"><span class="section-title">Analysis Results</span></div>', unsafe_allow_html=True)
    summary = analysis.get("summary", {})
    st.markdown(f'''
    <div style="display:flex; gap:1rem; margin:0.75rem 0; font-size:0.75rem;">
        <span style="color:var(--text-faint);">Proposed: <strong style="color:var(--text)">{summary.get("total_proposed", 0)}</strong></span>
        <span style="color:var(--green);">Approved: <strong>{summary.get("approved", 0)}</strong></span>
        <span style="color:var(--gold);">Modified: <strong>{summary.get("modified", 0)}</strong></span>
        <span style="color:var(--red);">Vetoed: <strong>{summary.get("vetoed", 0)}</strong></span>
    </div>
    ''', unsafe_allow_html=True)

    # Show reviewed actions
    reviewed = analysis.get("reviewed_actions", [])
    for r in reviewed:
        action = r.original
        decision = r.decision
        ai_reason = r.ai_reasoning
        confidence = r.confidence

        action_type = action.action_type
        ticker = action.ticker
        shares = action.shares
        price = action.price
        quant_score = action.quant_score
        quant_reason = action.reason

        # Determine styling
        action_class = "buy" if action_type == "BUY" else "sell"
        decision_color = "var(--green)" if decision == ReviewDecision.APPROVE else "var(--gold)" if decision == ReviewDecision.MODIFY else "var(--red)"
        decision_icon = "✅" if decision == ReviewDecision.APPROVE else "🔧" if decision == ReviewDecision.MODIFY else "❌"
        blocked_class = " blocked" if decision == ReviewDecision.VETO else ""
        conf_pct = int(confidence * 100)

        # Show modified values if any
        mods_text = ""
        if decision == ReviewDecision.MODIFY:
            mods = []
            if r.modified_shares and r.modified_shares != shares:
                mods.append(f"shares: {shares}→{r.modified_shares}")
            if r.modified_stop and r.modified_stop != action.stop_loss:
                mods.append(f"stop: ${action.stop_loss:.0f}→${r.modified_stop:.0f}")
            if r.modified_target and r.modified_target != action.take_profit:
                mods.append(f"target: ${action.take_profit:.0f}→${r.modified_target:.0f}")
            if mods:
                mods_text = f'<div style="font-size:0.7rem; color:var(--gold); margin-top:0.2rem;">Modified: {", ".join(mods)}</div>'

        # Build card HTML as single line to avoid Streamlit rendering issues
        card_html = f'<div class="ai-card{blocked_class}">'
        card_html += f'<div style="display:flex; justify-content:space-between; align-items:center;">'
        card_html += f'<div><span class="ai-action {action_class}">{action_type}</span> <span class="ai-ticker">{ticker}</span> <span style="color:var(--text-dim); font-size:0.75rem;">{shares} shares @ ${price:.2f}</span></div>'
        card_html += f'<div style="font-size:0.75rem; color:{decision_color};">{decision_icon} {decision}</div>'
        card_html += '</div>'
        card_html += f'<div style="display:flex; gap:1rem; margin-top:0.4rem; font-size:0.7rem; color:var(--text-faint);">'
        card_html += f'<span>Quant Score: <strong style="color:var(--text)">{quant_score:.0f}</strong>/100</span>'
        card_html += f'<span>Confidence: <strong style="color:var(--text)">{conf_pct}%</strong></span>'
        card_html += '</div>'
        card_html += f'<div class="ai-reason"><strong>Quant:</strong> {quant_reason}</div>'
        card_html += f'<div class="ai-reason"><strong>AI Review:</strong> {ai_reason}</div>'
        card_html += mods_text
        card_html += '</div>'
        st.markdown(card_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TRADE HISTORY (Collapsible)
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("Trade History / Journal", expanded=False):
    if not transactions_df.empty:
        sells = transactions_df[transactions_df['action'] == 'SELL'].copy()
        if not sells.empty:
            sells = sells.sort_values('date', ascending=False)

            history_rows = ""
            for _, tx in sells.head(20).iterrows():
                ticker = tx['ticker']
                date_str = str(tx['date'])
                shares = int(tx['shares'])
                price = tx['price']
                reason = tx.get('reason', 'MANUAL')
                total_val = tx.get('total_value', shares * price)

                reason_color = "var(--red)" if reason == "STOP_LOSS" else "var(--green)" if reason == "TAKE_PROFIT" else "var(--text-dim)"

                history_rows += f'<tr><td>{date_str}</td><td class="col-ticker">{ticker}</td><td>SELL</td><td>{shares}</td><td>${price:.2f}</td><td>${total_val:,.0f}</td><td style="color:{reason_color}">{reason}</td></tr>'

            history_html = f'<table class="pos-table"><thead><tr><th>Date</th><th>Ticker</th><th>Side</th><th>Shares</th><th>Price</th><th>Total</th><th>Reason</th></tr></thead><tbody>{history_rows}</tbody></table>'
            st.markdown(history_html, unsafe_allow_html=True)
        else:
            st.info("No closed trades yet")
    else:
        st.info("No trade history")


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
mode_indicator = "PAPER MODE" if paper_mode else "LIVE"
st.markdown(f'<div class="footer">{mode_indicator} · Unified Analysis (Quant + AI) · Not Financial Advice</div>', unsafe_allow_html=True)
