#!/usr/bin/env python3
"""
M O M M Y — Autonomous Trading Intelligence

Single scrollable page for daily check-ins.
All key information renders on one page — scroll, don't click tabs.

Sections:
- Metrics strip: equity, P&L, cash, regime
- Alerts: stale prices, near-stop, near-target positions
- Positions: full positions list with card/table toggle
- Analysis: ANALYZE/EXECUTE flow with results
- Recent Activity: last trades (expandable)
- Learning Insights: factor performance (collapsed by default)

GScott Chat lives in a persistent right sidebar.

Run with: streamlit run scripts/webapp.py
"""

import json
import subprocess
import random
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
from strategy_health import get_strategy_health
from strategy_pivot import analyze_pivot, apply_recommended_pivot
from factor_learning import FactorLearner, get_weight_suggestions

# Import design system
from webapp_styles import inject_styles, COLORS
from webapp_components import (
    render_position_cards,
    render_portfolio_treemap,
    render_equity_curve,
    render_section_header,
    generate_sparkline_svg,
    get_gscott_greeting,
)
from avatar_svg import get_avatar_svg
from avatar_states import determine_avatar_state_simple

# ─── Data Layer (via portfolio_state) ─────────────────────────────────────────
from portfolio_state import load_portfolio_state, save_transactions_batch, remove_position, save_positions
from data_files import (
    load_config as _load_config, save_config as _save_config,
    is_paper_mode, set_paper_mode, DATA_DIR, CONFIG_FILE,
    get_positions_file,
)


def get_trade_stats(transactions_df):
    """Calculate detailed trade statistics."""
    if transactions_df.empty:
        return {}

    sells = transactions_df[transactions_df['action'] == 'SELL'].copy()
    if sells.empty:
        return {}

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
    except Exception:
        pass

    return stats


def close_all_positions():
    """Emergency close all positions - creates SELL transactions for each position."""
    import uuid
    from datetime import date as dt_date

    state = load_portfolio_state(fetch_prices=False)
    if state.positions.empty:
        return 0, "No positions to close"

    transactions = []
    for _, pos in state.positions.iterrows():
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

    # Save transactions and clear positions
    state = save_transactions_batch(state, transactions)
    for _, pos in state.positions.iterrows():
        state = remove_position(state, pos['ticker'])
    save_positions(state)

    return len(transactions), f"Closed {len(transactions)} positions"


# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GScott",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="collapsed",
)

paper_mode = is_paper_mode()

# Initialize session state
if "unified_analysis" not in st.session_state:
    st.session_state.unified_analysis = None
if "show_execute_confirm" not in st.session_state:
    st.session_state.show_execute_confirm = False
if "show_emergency_modal" not in st.session_state:
    st.session_state.show_emergency_modal = False
if "show_close_all_confirm" not in st.session_state:
    st.session_state.show_close_all_confirm = False
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if "pivot_analysis" not in st.session_state:
    st.session_state.pivot_analysis = None
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "cards"
if "gscott_chat_response" not in st.session_state:
    st.session_state.gscott_chat_response = None
if "sidebar_collapsed" not in st.session_state:
    st.session_state.sidebar_collapsed = False

# ─── Inject CSS ───────────────────────────────────────────────────────────────
st.markdown(inject_styles(), unsafe_allow_html=True)

# ─── Load All Data (single portfolio_state call) ─────────────────────────────
_state = load_portfolio_state(fetch_prices=False)
config = _state.config
positions_df = _state.positions
transactions_df = _state.transactions
snapshots_df = _state.snapshots
cash = _state.cash
positions_value = _state.positions_value
total_equity = _state.total_equity
num_positions = _state.num_positions
regime = _state.regime.value
regime_analysis = _state.regime_analysis
stale_alerts = _state.stale_alerts

starting_capital = config.get("starting_capital", 50000.0)
total_return = total_equity - starting_capital
total_return_pct = (total_return / starting_capital) * 100
day_pnl = snapshots_df.iloc[-1].get("day_pnl", 0) if not snapshots_df.empty else 0
day_pnl_pct = snapshots_df.iloc[-1].get("day_pnl_pct", 0) if not snapshots_df.empty else 0

# Get analytics
try:
    analytics = PortfolioAnalytics()
    metrics = analytics.calculate_metrics()
    sharpe_ratio = metrics.get('sharpe_ratio', 0) if metrics else 0
    max_drawdown = metrics.get('max_drawdown_pct', 0) if metrics else 0
    sortino_ratio = metrics.get('sortino_ratio', 0) if metrics else 0
except Exception:
    sharpe_ratio = max_drawdown = sortino_ratio = 0

# Get trade stats
trade_stats = get_trade_stats(transactions_df)
win_rate = trade_stats.get('win_rate', 0)
profit_factor = trade_stats.get('profit_factor', 0)
avg_win = trade_stats.get('avg_win', 0)
avg_loss = trade_stats.get('avg_loss', 0)

# Check API status
chat_ready, chat_error = check_chat_setup()

# Get positions near stop/target
near_stop = get_positions_near_stop(positions_df, threshold_pct=5.0)
near_target = get_positions_near_target(positions_df, threshold_pct=8.0)

# Prepare history for sparklines
equity_history = snapshots_df["total_equity"].tolist()[-20:] if not snapshots_df.empty else []
pnl_history = snapshots_df["day_pnl"].tolist()[-20:] if not snapshots_df.empty and "day_pnl" in snapshots_df.columns else []


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER BAR (Logo + Controls)
# ═══════════════════════════════════════════════════════════════════════════════
col_logo, col_spacer, col_controls = st.columns([1.5, 3, 1.5])

with col_logo:
    logo_html = '<div style="display: flex; align-items: center; gap: 12px; padding: 4px 0;">'
    logo_html += '<div style="width: 36px; height: 36px; background: linear-gradient(135deg, #4FD1C5 0%, #38B2AC 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; color: #0A1628; font-family: Georgia, serif;">M</div>'
    logo_html += '<span style="font-family: Georgia, serif; font-size: 20px; font-weight: 600; color: #F7FAFC;">GScott</span>'
    logo_html += '</div>'
    st.markdown(logo_html, unsafe_allow_html=True)

with col_controls:
    ctrl_cols = st.columns([1, 1, 1])

    # Status dot
    with ctrl_cols[0]:
        status_color = COLORS["success"] if chat_ready else COLORS["danger"]
        status_html = f'<div style="display: flex; align-items: center; gap: 6px; padding-top: 8px;">'
        status_html += f'<span style="width: 8px; height: 8px; border-radius: 50%; background: {status_color}; box-shadow: 0 0 6px {status_color};"></span>'
        status_html += '</div>'
        st.markdown(status_html, unsafe_allow_html=True)

    # Mode toggle
    with ctrl_cols[1]:
        mode_label = "PAPER" if paper_mode else "LIVE"
        mode_color = COLORS["warning"] if paper_mode else COLORS["success"]
        if st.button(mode_label, key="mode_toggle", use_container_width=True):
            set_paper_mode(not paper_mode)
            st.rerun()

    # Emergency button
    with ctrl_cols[2]:
        if st.button("⚠️", key="emergency_btn"):
            st.session_state.show_emergency_modal = True


# ═══════════════════════════════════════════════════════════════════════════════
# COMPACT METRICS STRIP
# ═══════════════════════════════════════════════════════════════════════════════
strip_html = '<div class="metrics-strip">'

# Total Equity
strip_html += '<div class="strip-metric">'
strip_html += f'<span class="strip-metric-value">${total_equity:,.0f}</span>'
strip_html += '<span class="strip-metric-label">Equity</span>'
strip_html += '</div>'

strip_html += '<div class="strip-divider"></div>'

# Day P&L
pnl_class = "positive" if day_pnl >= 0 else "negative"
pnl_sign = "+" if day_pnl >= 0 else ""
strip_html += '<div class="strip-metric">'
strip_html += f'<span class="strip-metric-value {pnl_class}">{pnl_sign}${abs(day_pnl):,.0f}</span>'
strip_html += '<span class="strip-metric-label">Today</span>'
strip_html += '</div>'

strip_html += '<div class="strip-divider"></div>'

# Total Return (Overall P&L)
return_class = "positive" if total_return >= 0 else "negative"
return_sign = "+" if total_return >= 0 else ""
strip_html += '<div class="strip-metric">'
strip_html += f'<span class="strip-metric-value {return_class}">{return_sign}${abs(total_return):,.0f} ({return_sign}{abs(total_return_pct):.1f}%)</span>'
strip_html += '<span class="strip-metric-label">Total P&L</span>'
strip_html += '</div>'

strip_html += '<div class="strip-divider"></div>'

# Cash
strip_html += '<div class="strip-metric">'
strip_html += f'<span class="strip-metric-value">${cash:,.0f}</span>'
strip_html += '<span class="strip-metric-label">Cash</span>'
strip_html += '</div>'

strip_html += '<div class="strip-divider"></div>'

# Regime
regime_class = "bull" if regime == "BULL" else "bear" if regime == "BEAR" else "sideways"
regime_icon = "🐂" if regime == "BULL" else "🐻" if regime == "BEAR" else "↔️"
strip_html += f'<span class="regime-badge {regime_class}">{regime_icon} {regime}</span>'

strip_html += '</div>'
st.markdown(strip_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EMERGENCY MODAL
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.show_emergency_modal:
    st.markdown(f'<div style="background: {COLORS["bg_card"]}; border: 2px solid {COLORS["danger"]}; border-radius: 12px; padding: 24px; margin: 16px 0;">', unsafe_allow_html=True)
    st.markdown(f'<div style="font-family: Georgia, serif; font-size: 18px; font-weight: 600; color: {COLORS["danger"]}; margin-bottom: 16px;">⚠️ Emergency Controls</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color: {COLORS["text_secondary"]}; font-size: 14px; margin-bottom: 16px;">Use with caution. These actions cannot be undone.</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("🔴 CLOSE ALL", key="close_all_btn", type="primary"):
            st.session_state.show_close_all_confirm = True

    with col2:
        if st.button("Cancel", key="cancel_emergency"):
            st.session_state.show_emergency_modal = False
            st.session_state.show_close_all_confirm = False
            st.rerun()

    if st.session_state.show_close_all_confirm:
        st.warning("This will close ALL open positions at market price. Are you sure?")
        conf_col1, conf_col2 = st.columns(2)
        with conf_col1:
            if st.button("YES, CLOSE ALL", type="primary", key="confirm_close"):
                count, msg = close_all_positions()
                if count > 0:
                    st.success(f"Closed {count} positions")
                else:
                    st.info(msg)
                st.session_state.show_emergency_modal = False
                st.session_state.show_close_all_confirm = False
                st.rerun()
        with conf_col2:
            if st.button("NO, CANCEL", key="cancel_close"):
                st.session_state.show_close_all_confirm = False
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT AREA + GScott SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
main_col, sidebar_col = st.columns([3, 1])

# ─── GScott SIDEBAR (Persistent) ───────────────────────────────────────────────
with sidebar_col:
    # Determine avatar state
    avatar_state = determine_avatar_state_simple(
        day_pnl=day_pnl,
        positions_near_stop=len(near_stop),
        positions_near_target=len(near_target),
        regime=regime,
        drawdown_pct=max_drawdown
    )

    # Get greeting
    greeting = get_gscott_greeting(
        day_pnl=day_pnl,
        positions_near_stop=len(near_stop),
        positions_near_target=len(near_target),
        regime=regime,
        drawdown_pct=max_drawdown
    )

    # Avatar
    avatar_svg = get_avatar_svg(avatar_state.value, size=80)
    st.markdown('<div class="gscott-avatar-container">' + avatar_svg + '</div>', unsafe_allow_html=True)

    # Greeting
    st.markdown(f'<div class="gscott-greeting">"{greeting}"</div>', unsafe_allow_html=True)

    # Recent Insights
    insights = []
    if not transactions_df.empty:
        transactions_df['date'] = pd.to_datetime(transactions_df['date'])
        recent_sells = transactions_df[(transactions_df['action'] == 'SELL') & (transactions_df['date'] >= pd.Timestamp.now() - pd.Timedelta(days=7))]
        for _, sell in recent_sells.head(2).iterrows():
            reason = sell.get('reason', '')
            ticker = sell['ticker']
            if reason == 'STOP_LOSS':
                insights.append(f"⛔ {ticker} stopped out")
            elif reason == 'TAKE_PROFIT':
                insights.append(f"✅ {ticker} hit target!")

    for pos in near_stop[:2]:
        insights.append(f"⚠️ {pos['ticker']} near stop")
    for pos in near_target[:2]:
        insights.append(f"🎯 {pos['ticker']} near target")

    if insights:
        insights_html = f'<div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid {COLORS["border"]};">'
        insights_html += f'<div style="font-size: 11px; color: {COLORS["text_muted"]}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Recent Insights</div>'
        for insight in insights[:5]:
            insights_html += f'<div style="font-size: 13px; color: {COLORS["text_secondary"]}; padding: 4px 0;">{insight}</div>'
        insights_html += '</div>'
        st.markdown(insights_html, unsafe_allow_html=True)

    # Chat input
    if chat_ready:
        st.markdown(f'<div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid {COLORS["border"]};">', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size: 11px; color: {COLORS["text_muted"]}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Ask Me Anything</div>', unsafe_allow_html=True)

        # Quick chips
        QUICK_QUESTIONS = [
            ("Health", "Give me a quick health check on my portfolio"),
            ("Risk", "Which positions are closest to their stop losses?"),
            ("Targets", "Which positions are approaching their targets?"),
        ]
        chips_html = '<div class="quick-chips">'
        for label, _ in QUICK_QUESTIONS:
            chips_html += f'<span class="quick-chip">{label}</span>'
        chips_html += '</div>'
        st.markdown(chips_html, unsafe_allow_html=True)

        PLACEHOLDERS = ["How's my portfolio?", "Any worries?", "What should I watch?"]
        placeholder = random.choice(PLACEHOLDERS)

        with st.form(key="gscott_chat_form", clear_on_submit=True):
            user_question = st.text_input("chat", placeholder=placeholder, label_visibility="collapsed")
            submitted = st.form_submit_button("Ask", use_container_width=True)

        if submitted and user_question:
            with st.spinner("Thinking..."):
                response = ai_chat(user_question)
            if response.success:
                st.session_state.gscott_chat_response = response.message
            else:
                st.session_state.gscott_chat_response = None
                st.error(response.error)

        # Display response outside the submit block so it persists
        if st.session_state.gscott_chat_response:
            st.markdown(f'<div style="background: rgba(79,209,197,0.1); border-left: 3px solid {COLORS["accent_teal"]}; padding: 10px; border-radius: 8px; margin-top: 10px; font-size: 13px; font-style: italic; color: {COLORS["text_primary"]};">"{st.session_state.gscott_chat_response}"</div>', unsafe_allow_html=True)
            if st.button("Clear", key="clear_chat", use_container_width=True):
                st.session_state.gscott_chat_response = None
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)


# ─── MAIN CONTENT (Single Scrollable Page) ──────────────────────────────────
with main_col:

    # ═══════════════════════════════════════════════════════════════════════════
    # ALERTS (stale prices, near-stop, near-target)
    # ═══════════════════════════════════════════════════════════════════════════
    has_alerts = stale_alerts or near_stop or near_target
    if has_alerts:
        render_section_header("Alerts")

        for ticker, days in stale_alerts.items():
            alert_html = f'<div class="alert-card danger">'
            alert_html += f'<span class="alert-icon">📡</span>'
            alert_html += f'<span class="alert-text"><strong>{ticker}</strong> price stale for {days} consecutive days — may be delisted</span>'
            alert_html += '</div>'
            st.markdown(alert_html, unsafe_allow_html=True)

        for pos in near_stop[:3]:
            alert_html = f'<div class="alert-card danger">'
            alert_html += f'<span class="alert-icon">⚠️</span>'
            alert_html += f'<span class="alert-text"><strong>{pos["ticker"]}</strong> is only {pos["distance_pct"]:.1f}% from stop loss</span>'
            alert_html += '</div>'
            st.markdown(alert_html, unsafe_allow_html=True)

        for pos in near_target[:3]:
            alert_html = f'<div class="alert-card success">'
            alert_html += f'<span class="alert-icon">🎯</span>'
            alert_html += f'<span class="alert-text"><strong>{pos["ticker"]}</strong> is {pos["distance_pct"]:.1f}% from target</span>'
            alert_html += '</div>'
            st.markdown(alert_html, unsafe_allow_html=True)


    # ═══════════════════════════════════════════════════════════════════════════
    # POSITIONS
    # ═══════════════════════════════════════════════════════════════════════════
    winners = len(positions_df[positions_df['unrealized_pnl'] > 0]) if not positions_df.empty else 0
    losers = len(positions_df[positions_df['unrealized_pnl'] <= 0]) if not positions_df.empty else 0

    # Action bar
    action_col1, action_col2, action_col3, action_col4 = st.columns([1, 1, 1, 3])

    with action_col1:
        if st.button("🔄 REFRESH", key="refresh_positions", use_container_width=True):
            st.rerun()

    with action_col2:
        if st.button("📊 UPDATE", key="update_positions", use_container_width=True):
            with st.spinner("Updating prices..."):
                try:
                    project_root = Path(__file__).parent.parent
                    result = subprocess.run([sys.executable, "scripts/update_positions.py"], cwd=project_root, capture_output=True, text=True, timeout=120)
                    if result.returncode == 0:
                        st.success("Updated!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with action_col3:
        view_toggle = st.selectbox("View", ["Cards", "Table"], label_visibility="collapsed", key="pos_view_toggle")
        if view_toggle == "Cards":
            st.session_state.view_mode = "cards"
        else:
            st.session_state.view_mode = "table"

    render_section_header("Positions", f"{winners}W / {losers}L")

    if not positions_df.empty:
        if st.session_state.view_mode == "cards":
            render_position_cards(positions_df)
        else:
            # Table view
            near_stop_tickers = {p['ticker'] for p in near_stop}
            near_target_tickers = {p['ticker'] for p in near_target}

            positions_sorted = positions_df.copy()
            positions_sorted['_priority'] = positions_sorted['ticker'].apply(
                lambda t: 0 if t in near_stop_tickers else (1 if t in near_target_tickers else 2)
            )
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

                port_weight = (market_value / total_equity) * 100 if total_equity > 0 else 0
                progress = calculate_position_progress(row)
                prog_pct = progress['progress_pct'] if progress else 50

                if ticker in near_stop_tickers:
                    row_bg = "rgba(245,101,101,0.08)"
                elif pnl >= 0:
                    row_bg = "rgba(72,187,120,0.05)"
                else:
                    row_bg = "rgba(245,101,101,0.03)"

                pnl_color = COLORS["success"] if pnl >= 0 else COLORS["danger"]
                pnl_sign = "+" if pnl >= 0 else ""
                prog_color = COLORS["danger"] if prog_pct < 25 else COLORS["warning"] if prog_pct < 50 else COLORS["text_muted"] if prog_pct < 75 else COLORS["success"]

                rows_html += f'<tr style="background: {row_bg};">'
                rows_html += f'<td style="font-weight: 600; color: {COLORS["text_primary"]};">{ticker}</td>'
                rows_html += f'<td style="color: {COLORS["text_secondary"]};">{shares}</td>'
                rows_html += f'<td style="color: {COLORS["text_secondary"]};">${entry_price:.2f}</td>'
                rows_html += f'<td style="color: {COLORS["text_secondary"]};">${current_price:.2f}</td>'
                rows_html += f'<td style="color: {COLORS["text_secondary"]};">${market_value:,.0f}</td>'
                rows_html += f'<td style="color: {pnl_color};">{pnl_sign}${abs(pnl):,.0f}</td>'
                rows_html += f'<td style="color: {pnl_color};">{pnl_sign}{pnl_pct:.1f}%</td>'
                rows_html += f'<td style="color: {COLORS["text_muted"]}; font-size: 12px;">{port_weight:.1f}%</td>'
                rows_html += f'<td style="color: {COLORS["text_muted"]}; font-size: 12px;">${stop_loss:.0f}</td>'
                rows_html += f'<td style="color: {COLORS["text_muted"]}; font-size: 12px;">${take_profit:.0f}</td>'
                rows_html += f'<td><div style="width: 60px; height: 6px; background: {COLORS["bg_hover"]}; border-radius: 3px;"><div style="width: {prog_pct}%; height: 100%; background: {prog_color}; border-radius: 3px;"></div></div></td>'
                rows_html += '</tr>'

            table_html = '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">'
            table_html += f'<thead><tr style="border-bottom: 1px solid {COLORS["border"]};">'
            for h in ['Ticker', 'Shares', 'Entry', 'Current', 'Value', 'P&L', '%', 'Weight', 'Stop', 'Target', 'Progress']:
                table_html += f'<th style="text-align: left; padding: 8px 6px; font-size: 10px; font-weight: 500; color: {COLORS["text_muted"]}; text-transform: uppercase;">{h}</th>'
            table_html += '</tr></thead>'
            table_html += f'<tbody>{rows_html}</tbody></table>'
            st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info("No open positions")


    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYSIS & ACTIONS
    # ═══════════════════════════════════════════════════════════════════════════
    render_section_header("Analysis & Actions")

    action_col1, action_col2, action_col3 = st.columns([1, 1, 4])

    analysis = st.session_state.unified_analysis
    has_executable = analysis.get("summary", {}).get("can_execute", False) if analysis else False

    with action_col1:
        if st.button("🔍 ANALYZE", key="analyze_btn", type="primary", use_container_width=True):
            with st.spinner("Running analysis..."):
                try:
                    result = run_unified_analysis(dry_run=True)
                    st.session_state.unified_analysis = result
                    st.session_state.show_execute_confirm = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with action_col2:
        if st.button("▶️ EXECUTE", key="execute_btn", disabled=not has_executable, use_container_width=True):
            st.session_state.show_execute_confirm = True

    # Execute confirmation
    if st.session_state.show_execute_confirm and analysis:
        approved = analysis.get("approved", [])
        modified = analysis.get("modified", [])
        executable = approved + modified

        if executable:
            st.markdown(f'<div style="background: {COLORS["bg_card"]}; border: 2px solid {COLORS["warning"]}; border-radius: 12px; padding: 20px; margin: 16px 0;">', unsafe_allow_html=True)
            st.markdown(f'<div style="font-weight: 600; color: {COLORS["warning"]}; margin-bottom: 12px;">Confirm Execution</div>', unsafe_allow_html=True)

            for r in executable:
                action = r.original
                shares = r.modified_shares or action.shares
                mod_note = " (modified)" if r.decision == ReviewDecision.MODIFY else ""
                st.markdown(f"- **{action.action_type}** {action.ticker}: {shares} shares @ ${action.price:.2f}{mod_note}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("EXECUTE NOW", type="primary", key="exec_confirm"):
                    with st.spinner("Executing..."):
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

            st.markdown('</div>', unsafe_allow_html=True)

    # Analysis Results
    if analysis:
        summary = analysis.get("summary", {})

        summary_html = f'<div style="display: flex; gap: 24px; margin: 12px 0; font-size: 14px;">'
        summary_html += f'<span style="color: {COLORS["text_muted"]};">Proposed: <strong style="color: {COLORS["text_primary"]};">{summary.get("total_proposed", 0)}</strong></span>'
        summary_html += f'<span style="color: {COLORS["success"]};">Approved: <strong>{summary.get("approved", 0)}</strong></span>'
        summary_html += f'<span style="color: {COLORS["warning"]};">Modified: <strong>{summary.get("modified", 0)}</strong></span>'
        summary_html += f'<span style="color: {COLORS["danger"]};">Vetoed: <strong>{summary.get("vetoed", 0)}</strong></span>'
        summary_html += '</div>'
        st.markdown(summary_html, unsafe_allow_html=True)

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

            action_color = COLORS["success"] if action_type == "BUY" else COLORS["danger"]
            decision_color = COLORS["success"] if decision == ReviewDecision.APPROVE else COLORS["warning"] if decision == ReviewDecision.MODIFY else COLORS["danger"]
            blocked_opacity = "0.5" if decision == ReviewDecision.VETO else "1"
            conf_pct = int(confidence * 100)

            card_html = f'<div style="background: {COLORS["bg_card"]}; border: 1px solid {COLORS["border"]}; border-radius: 12px; padding: 16px; margin-bottom: 12px; opacity: {blocked_opacity};">'
            card_html += f'<div style="display: flex; justify-content: space-between; align-items: center;">'
            card_html += f'<div><span style="font-weight: 600; color: {action_color};">{action_type}</span> <span style="font-weight: 500; color: {COLORS["text_primary"]};">{ticker}</span> <span style="color: {COLORS["text_secondary"]}; font-size: 13px;">{shares} @ ${price:.2f}</span></div>'
            card_html += f'<div style="font-size: 13px; color: {decision_color}; font-weight: 500;">{decision}</div>'
            card_html += '</div>'
            card_html += f'<div style="font-size: 12px; color: {COLORS["text_muted"]}; margin-top: 6px;">Quant: {quant_score:.0f}/100 | Confidence: {conf_pct}%</div>'
            card_html += f'<div style="font-size: 13px; color: {COLORS["text_secondary"]}; margin-top: 8px;">{ai_reason}</div>'
            card_html += '</div>'
            st.markdown(card_html, unsafe_allow_html=True)

    # Portfolio Composition
    if not positions_df.empty and num_positions > 1:
        render_section_header("Portfolio Composition")
        render_portfolio_treemap(positions_df)

    # Risk Metrics
    render_section_header("Risk Metrics")

    metrics_html = '<div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px;">'

    def metric_card(label, value, color=None):
        val_color = color or COLORS["text_primary"]
        return f'<div style="background: {COLORS["bg_card"]}; border: 1px solid {COLORS["border"]}; border-radius: 10px; padding: 14px; text-align: center;"><div style="font-size: 10px; color: {COLORS["text_muted"]}; text-transform: uppercase; letter-spacing: 0.5px;">{label}</div><div style="font-size: 18px; font-weight: 600; color: {val_color}; margin-top: 4px;">{value}</div></div>'

    sharpe_color = COLORS["success"] if sharpe_ratio > 1 else COLORS["warning"] if sharpe_ratio > 0 else COLORS["danger"]
    dd_color = COLORS["success"] if max_drawdown < 5 else COLORS["warning"] if max_drawdown < 10 else COLORS["danger"]
    wr_color = COLORS["success"] if win_rate > 50 else COLORS["warning"] if win_rate > 40 else COLORS["danger"]
    pf_color = COLORS["success"] if profit_factor > 1.5 else COLORS["warning"] if profit_factor > 1 else COLORS["danger"]

    metrics_html += metric_card("Sharpe", f"{sharpe_ratio:.2f}", sharpe_color)
    metrics_html += metric_card("Max DD", f"{max_drawdown:.1f}%", dd_color)
    metrics_html += metric_card("Win Rate", f"{win_rate:.0f}%", wr_color)
    metrics_html += metric_card("Profit Factor", f"{profit_factor:.2f}", pf_color)
    avg_win_loss = f"${avg_win:.0f}/${abs(avg_loss):.0f}" if avg_loss != 0 else "N/A"
    metrics_html += metric_card("Avg W/L", avg_win_loss)

    metrics_html += '</div>'
    st.markdown(metrics_html, unsafe_allow_html=True)

    # Diversification
    if not positions_df.empty:
        render_section_header("Diversification")

        largest_pos = positions_df.nlargest(1, 'market_value')['market_value'].iloc[0] if not positions_df.empty else 0
        largest_pct = (largest_pos / total_equity) * 100 if total_equity > 0 else 0
        top3_pct = (positions_df.nlargest(3, 'market_value')['market_value'].sum() / total_equity) * 100 if total_equity > 0 else 0
        cash_pct = (cash / total_equity) * 100 if total_equity > 0 else 0

        div_html = '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;">'
        div_html += metric_card("Largest Position", f"{largest_pct:.1f}%")
        div_html += metric_card("Top 3 Concentration", f"{top3_pct:.1f}%")
        div_html += metric_card("Cash Reserve", f"{cash_pct:.1f}%")
        div_html += metric_card("Position Count", f"{num_positions}")
        div_html += '</div>'
        st.markdown(div_html, unsafe_allow_html=True)


    # ═══════════════════════════════════════════════════════════════════════════
    # RECENT ACTIVITY (expandable)
    # ═══════════════════════════════════════════════════════════════════════════
    with st.expander("Recent Activity", expanded=True):
        if not transactions_df.empty:
            all_tx = transactions_df.sort_values('date', ascending=False)

            for _, tx in all_tx.head(20).iterrows():
                action = tx["action"]
                ticker = tx["ticker"]
                shares = int(tx["shares"])
                price = tx["price"]
                total_val = tx.get("total_value", shares * price)
                date_str = str(tx["date"])
                reason = tx.get("reason", "")

                badge_color = COLORS["success"] if action == "BUY" else COLORS["danger"]
                badge_bg = "rgba(72,187,120,0.15)" if action == "BUY" else "rgba(245,101,101,0.15)"

                reason_html = ""
                if action == "SELL" and reason in ["STOP_LOSS", "TAKE_PROFIT"]:
                    reason_text = "(Stop)" if reason == "STOP_LOSS" else "(Target)"
                    reason_color = COLORS["danger"] if reason == "STOP_LOSS" else COLORS["success"]
                    reason_html = f'<span style="color: {reason_color}; font-size: 11px; margin-left: 6px;">{reason_text}</span>'

                tx_html = f'<div style="display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid {COLORS["border"]}; gap: 12px;">'
                tx_html += f'<span style="background: {badge_bg}; color: {badge_color}; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 4px; min-width: 40px; text-align: center;">{action}</span>'
                tx_html += f'<span style="font-weight: 500; color: {COLORS["text_primary"]}; min-width: 50px;">{ticker}</span>'
                tx_html += f'<span style="color: {COLORS["text_secondary"]}; font-size: 13px; flex: 1;">{shares} @ ${price:.2f} = ${total_val:,.0f}{reason_html}</span>'
                tx_html += f'<span style="color: {COLORS["text_muted"]}; font-size: 12px;">{date_str}</span>'
                tx_html += '</div>'
                st.markdown(tx_html, unsafe_allow_html=True)

            # Trade History / Journal
            with st.expander("Trade History / Journal", expanded=False):
                sells = transactions_df[transactions_df['action'] == 'SELL'].copy()
                if not sells.empty:
                    sells = sells.sort_values('date', ascending=False)

                    for _, tx in sells.head(20).iterrows():
                        ticker = tx['ticker']
                        date_str = str(tx['date'])
                        shares = int(tx['shares'])
                        price = tx['price']
                        reason = tx.get('reason', 'MANUAL')
                        total_val = tx.get('total_value', shares * price)

                        reason_color = COLORS["danger"] if reason == "STOP_LOSS" else COLORS["success"] if reason == "TAKE_PROFIT" else COLORS["text_secondary"]

                        hist_html = f'<div style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid {COLORS["border"]}; gap: 16px; font-size: 13px;">'
                        hist_html += f'<span style="color: {COLORS["text_muted"]}; min-width: 80px;">{date_str}</span>'
                        hist_html += f'<span style="font-weight: 500; color: {COLORS["text_primary"]}; min-width: 50px;">{ticker}</span>'
                        hist_html += f'<span style="color: {COLORS["text_secondary"]};">{shares} @ ${price:.2f}</span>'
                        hist_html += f'<span style="color: {COLORS["text_secondary"]};">${total_val:,.0f}</span>'
                        hist_html += f'<span style="color: {reason_color};">{reason}</span>'
                        hist_html += '</div>'
                        st.markdown(hist_html, unsafe_allow_html=True)
                else:
                    st.info("No closed trades yet")
        else:
            st.info("No transactions yet")


    # ═══════════════════════════════════════════════════════════════════════════
    # LEARNING INSIGHTS (collapsed by default)
    # ═══════════════════════════════════════════════════════════════════════════
    with st.expander("Learning Insights", expanded=False):
        try:
            learner = FactorLearner()
            summary = learner.get_factor_summary()
            if summary.get("status") == "ok" and summary.get("factors"):
                st.markdown(f'<div style="font-size: 13px; color: {COLORS["text_secondary"]}; margin-bottom: 12px;">Trades Analyzed: {summary.get("total_analyzed_trades", 0)}</div>', unsafe_allow_html=True)

                # Factor performance table
                header_html = f'<div style="display: grid; grid-template-columns: 2fr 1fr 1.5fr 1fr; gap: 8px; padding: 8px 0; border-bottom: 1px solid {COLORS["border"]}; font-size: 10px; color: {COLORS["text_muted"]}; text-transform: uppercase; letter-spacing: 0.5px;">'
                header_html += '<span>Factor</span><span style="text-align: right;">Win Rate</span><span style="text-align: right;">Contribution</span><span style="text-align: right;">Trend</span>'
                header_html += '</div>'
                st.markdown(header_html, unsafe_allow_html=True)

                for f in summary["factors"]:
                    name = f["factor"].replace("_", " ").title()
                    wr = f["win_rate"]
                    contrib = f["total_contribution"]
                    trend = f["trend"]
                    wr_color = COLORS["success"] if wr >= 50 else COLORS["danger"]
                    contrib_color = COLORS["success"] if contrib >= 0 else COLORS["danger"]
                    contrib_sign = "+" if contrib >= 0 else ""

                    row_html = f'<div style="display: grid; grid-template-columns: 2fr 1fr 1.5fr 1fr; gap: 8px; padding: 8px 0; border-bottom: 1px solid {COLORS["border"]}; font-size: 13px;">'
                    row_html += f'<span style="color: {COLORS["text_primary"]};">{name}</span>'
                    row_html += f'<span style="text-align: right; color: {wr_color};">{wr:.0f}%</span>'
                    row_html += f'<span style="text-align: right; color: {contrib_color};">{contrib_sign}${abs(contrib):,.0f}</span>'
                    row_html += f'<span style="text-align: right; color: {COLORS["text_muted"]};">{trend}</span>'
                    row_html += '</div>'
                    st.markdown(row_html, unsafe_allow_html=True)

                # Weight adjustment suggestions
                suggestions = get_weight_suggestions(regime)
                if suggestions:
                    st.markdown(f'<div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid {COLORS["border"]};">', unsafe_allow_html=True)
                    st.markdown(f'<div style="font-size: 11px; color: {COLORS["text_muted"]}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Suggested Adjustments</div>', unsafe_allow_html=True)
                    for s in suggestions[:3]:
                        name = s.factor.replace("_", " ").title()
                        change_color = COLORS["success"] if s.change_pct > 0 else COLORS["danger"]
                        sug_html = f'<div style="font-size: 13px; color: {COLORS["text_secondary"]}; padding: 4px 0;">'
                        sug_html += f'{name}: {s.current_weight:.0%} → {s.suggested_weight:.0%} '
                        sug_html += f'<span style="color: {change_color};">({s.change_pct:+.1f}%)</span> '
                        sug_html += f'<span style="color: {COLORS["text_muted"]};">[{s.confidence}]</span>'
                        sug_html += '</div>'
                        st.markdown(sug_html, unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("Insufficient closed trades for factor analysis")
        except Exception:
            st.info("Learning analysis unavailable")


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
mode_indicator = "PAPER MODE" if paper_mode else "LIVE"
footer_html = f'<div style="text-align: center; padding: 24px 0 16px; font-size: 10px; color: {COLORS["text_muted"]}; letter-spacing: 1px; text-transform: uppercase; border-top: 1px solid {COLORS["border"]}; margin-top: 32px;">'
footer_html += f'{mode_indicator} | Single Page Dashboard | Not Financial Advice'
footer_html += '</div>'
st.markdown(footer_html, unsafe_allow_html=True)
