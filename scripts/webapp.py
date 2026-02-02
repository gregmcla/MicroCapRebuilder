#!/usr/bin/env python3
"""
M O M M Y — Autonomous Trading Intelligence

A warm, nurturing command center for your portfolio.
Implements the design consultant's vision with deep navy + soft teal palette.

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
from strategy_health import get_strategy_health
from strategy_pivot import analyze_pivot, apply_recommended_pivot

# Import new design system
from webapp_styles import inject_styles, COLORS
from webapp_components import (
    render_metrics_ribbon,
    render_position_cards,
    render_portfolio_treemap,
    render_equity_curve,
    render_mommy_sidebar,
    render_top_bar,
    render_section_header,
    card_start,
    card_end,
    generate_sparkline_svg,
    get_mommy_greeting,
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

    files = get_data_files()
    df_new = pd.DataFrame(transactions)

    if files["transactions"].exists():
        df_existing = pd.read_csv(files["transactions"])
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new

    df_combined.to_csv(files["transactions"], index=False)
    pd.DataFrame(columns=positions_df.columns).to_csv(files["positions"], index=False)

    return len(transactions), f"Closed {len(transactions)} positions"


# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MOMMY",
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
if "show_close_all_confirm" not in st.session_state:
    st.session_state.show_close_all_confirm = False
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if "chart_timeframe" not in st.session_state:
    st.session_state.chart_timeframe = "1M"
if "pivot_analysis" not in st.session_state:
    st.session_state.pivot_analysis = None
if "show_pivot_apply_confirm" not in st.session_state:
    st.session_state.show_pivot_apply_confirm = False
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "cards"

# ─── Inject New Design System CSS ─────────────────────────────────────────────
st.markdown(inject_styles(), unsafe_allow_html=True)

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

# Get positions near stop/target
near_stop = get_positions_near_stop(positions_df, threshold_pct=5.0)
near_target = get_positions_near_target(positions_df, threshold_pct=8.0)

# Prepare equity history for sparklines
equity_history = snapshots_df["total_equity"].tolist()[-20:] if not snapshots_df.empty else []
pnl_history = snapshots_df["day_pnl"].tolist()[-20:] if not snapshots_df.empty and "day_pnl" in snapshots_df.columns else []
cash_history = snapshots_df["cash"].tolist()[-20:] if not snapshots_df.empty and "cash" in snapshots_df.columns else []


# ═══════════════════════════════════════════════════════════════════════════════
# TOP BAR (Minimal header with logo and status)
# ═══════════════════════════════════════════════════════════════════════════════
col_logo, col_status, col_mode = st.columns([2, 1, 1])

with col_logo:
    logo_html = '<div style="display: flex; align-items: center; gap: 12px; padding: 8px 0;">'
    logo_html += '<div style="width: 40px; height: 40px; background: linear-gradient(135deg, #4FD1C5 0%, #38B2AC 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: 700; color: #0A1628; font-family: Georgia, serif;">M</div>'
    logo_html += '<span style="font-family: Georgia, serif; font-size: 24px; font-weight: 600; color: #F7FAFC;">MOMMY</span>'
    logo_html += '</div>'
    st.markdown(logo_html, unsafe_allow_html=True)

with col_status:
    status_color = COLORS["success"] if chat_ready else COLORS["danger"]
    status_text = "Connected" if chat_ready else "Disconnected"
    status_html = f'<div style="display: flex; align-items: center; gap: 8px; justify-content: flex-end; padding-top: 16px;">'
    status_html += f'<span style="width: 10px; height: 10px; border-radius: 50%; background: {status_color}; box-shadow: 0 0 8px {status_color};"></span>'
    status_html += f'<span style="color: {COLORS["text_secondary"]}; font-size: 12px;">{status_text}</span>'
    status_html += '</div>'
    st.markdown(status_html, unsafe_allow_html=True)

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
# COMMAND ZONE (Floating pill bar with primary actions)
# ═══════════════════════════════════════════════════════════════════════════════
analysis = st.session_state.unified_analysis
has_executable = analysis.get("summary", {}).get("can_execute", False) if analysis else False

col_analyze, col_execute, col_pivot, col_discover, col_update, col_refresh = st.columns(6)

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

with col_pivot:
    if st.button("PIVOT", use_container_width=True, key="pivot_top"):
        with st.spinner("Analyzing strategy..."):
            try:
                pivot_result = analyze_pivot()
                st.session_state.pivot_analysis = pivot_result
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

with col_discover:
    if st.button("DISCOVER", use_container_width=True, key="discover_top"):
        with st.spinner("Discovering new candidates..."):
            try:
                project_root = Path(__file__).parent.parent
                result = subprocess.run([sys.executable, "scripts/watchlist_manager.py", "--update"], cwd=project_root, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    st.success("Discovery complete!")
                    if result.stdout:
                        st.code(result.stdout[-1500:], language=None)
                else:
                    st.warning("Discovery had issues")
                    if result.stderr:
                        st.code(result.stderr[-500:], language=None)
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


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTE CONFIRMATION DIALOG
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.show_execute_confirm and analysis:
    approved = analysis.get("approved", [])
    modified = analysis.get("modified", [])
    executable = approved + modified

    if executable:
        confirm_html = f'<div style="background: {COLORS["bg_card"]}; border: 2px solid {COLORS["warning"]}; border-radius: 12px; padding: 20px; margin: 16px 0;">'
        confirm_html += f'<div style="font-weight: 600; color: {COLORS["warning"]}; margin-bottom: 12px;">Confirm Execution</div>'
        confirm_html += f'<div style="color: {COLORS["text_secondary"]}; font-size: 14px;">The following trades will be executed:</div>'
        confirm_html += '</div>'
        st.markdown(confirm_html, unsafe_allow_html=True)

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
# HERO METRICS RIBBON
# ═══════════════════════════════════════════════════════════════════════════════
render_metrics_ribbon(
    total_equity=total_equity,
    day_pnl=day_pnl,
    day_pnl_pct=day_pnl_pct,
    cash=cash,
    regime=regime,
    equity_history=equity_history,
    pnl_history=pnl_history,
    cash_history=cash_history
)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT AREA + MOMMY SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
main_col, sidebar_col = st.columns([3, 1])

with sidebar_col:
    # Mommy Companion Sidebar
    insights = []
    if not transactions_df.empty:
        transactions_df['date'] = pd.to_datetime(transactions_df['date'])
        recent_sells = transactions_df[(transactions_df['action'] == 'SELL') & (transactions_df['date'] >= pd.Timestamp.now() - pd.Timedelta(days=7))]
        for _, sell in recent_sells.head(3).iterrows():
            reason = sell.get('reason', '')
            ticker = sell['ticker']
            if reason == 'STOP_LOSS':
                insights.append(f"{ticker} stopped out")
            elif reason == 'TAKE_PROFIT':
                insights.append(f"{ticker} hit target!")

    for pos in near_stop[:2]:
        insights.append(f"{pos['ticker']} near stop")
    for pos in near_target[:2]:
        insights.append(f"{pos['ticker']} approaching target")

    render_mommy_sidebar(
        day_pnl=day_pnl,
        insights=insights,
        positions_near_stop=len(near_stop),
        positions_near_target=len(near_target),
        regime=regime,
        drawdown_pct=max_drawdown
    )

    # Chat input in sidebar
    if chat_ready:
        st.markdown(f'<div style="margin-top: 20px; padding-top: 16px; border-top: 1px solid {COLORS["border"]};">', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size: 12px; color: {COLORS["text_secondary"]}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Ask Me Anything</div>', unsafe_allow_html=True)

        # Quick-action chips
        import random
        QUICK_QUESTIONS = [
            ("Portfolio Health", "Give me a quick health check on my portfolio"),
            ("Positions at Risk", "Which positions are closest to their stop losses?"),
            ("Near Targets", "Which positions are approaching their targets?"),
            ("Today's Summary", "Summarize how my portfolio did today"),
        ]

        chips_html = '<div class="quick-chips">'
        for label, _ in QUICK_QUESTIONS:
            chips_html += f'<span class="quick-chip">{label}</span>'
        chips_html += '</div>'
        st.markdown(chips_html, unsafe_allow_html=True)

        # Rotating placeholder suggestions
        PLACEHOLDERS = [
            "How's my portfolio doing?",
            "Any positions I should worry about?",
            "What should I watch today?",
            "How's my diversification?",
            "Summarize my risk exposure",
        ]
        placeholder = random.choice(PLACEHOLDERS)

        with st.form(key="mommy_chat_form", clear_on_submit=True):
            user_question = st.text_input("chat_input", placeholder=placeholder, label_visibility="collapsed")
            submitted = st.form_submit_button("Ask", use_container_width=True)

        if submitted and user_question:
            with st.spinner("Mommy is thinking..."):
                response = ai_chat(user_question)
            if response.success:
                st.markdown(f'<div class="mommy-response" style="background: rgba(79,209,197,0.1); border-left: 3px solid {COLORS["accent_teal"]}; padding: 12px; border-radius: 8px; font-style: italic; color: {COLORS["text_primary"]};">"{response.message}"</div>', unsafe_allow_html=True)
            else:
                st.error(response.error)

        st.markdown('</div>', unsafe_allow_html=True)


with main_col:
    # ═══════════════════════════════════════════════════════════════════════════
    # STRATEGY HEALTH & PIVOT ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    pivot_analysis = st.session_state.pivot_analysis

    if pivot_analysis:
        health = pivot_analysis.health
        grade_first = health.grade[0].upper()

        grade_colors = {'A': COLORS["success"], 'B': '#68D391', 'C': COLORS["warning"], 'D': '#F6AD55', 'F': COLORS["danger"]}
        grade_color = grade_colors.get(grade_first, COLORS["warning"])

        health_html = f'<div class="health-card">'
        health_html += '<div class="health-header">'
        health_html += f'<div><span class="health-grade" style="color: {grade_color};">{health.grade}</span>'
        health_html += f'<div style="font-size: 14px; color: {COLORS["text_secondary"]};">{health.score:.0f}/100 - {health.grade_description}</div></div>'
        if pivot_analysis.should_pivot:
            urgency_colors = {'low': COLORS["success"], 'medium': COLORS["warning"], 'high': COLORS["danger"]}
            urg_color = urgency_colors.get(pivot_analysis.urgency, COLORS["warning"])
            health_html += f'<span class="pivot-urgency" style="background: rgba({urg_color}, 0.2); color: {urg_color};">PIVOT {pivot_analysis.urgency.upper()}</span>'
        health_html += '</div>'

        health_html += '<div style="display: flex; flex-direction: column; gap: 12px;">'
        for c in health.components:
            fill_color = COLORS["success"] if c.score >= 70 else COLORS["warning"] if c.score >= 50 else COLORS["danger"]
            health_html += f'<div class="health-component">'
            health_html += f'<span class="health-label">{c.name}</span>'
            health_html += f'<div class="health-bar"><div class="health-fill" style="width:{c.score}%; background: {fill_color};"></div></div>'
            health_html += f'<span class="health-value">{c.score:.0f}</span>'
            health_html += '</div>'
        health_html += '</div>'

        health_html += f'<div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid {COLORS["border"]}; font-size: 14px; color: {COLORS["text_secondary"]}; line-height: 1.6;">{health.diagnosis}</div>'
        health_html += '</div>'
        st.markdown(health_html, unsafe_allow_html=True)

        if pivot_analysis.should_pivot or pivot_analysis.diagnosis_working or pivot_analysis.diagnosis_failing:
            pivot_html = '<div class="pivot-card">'
            pivot_html += f'<div class="pivot-mommy">"{pivot_analysis.mommy_says}"</div>'

            if pivot_analysis.diagnosis_working:
                pivot_html += '<div class="pivot-section">'
                pivot_html += '<div class="pivot-section-title">What\'s Working</div>'
                for item in pivot_analysis.diagnosis_working[:4]:
                    pivot_html += f'<div class="pivot-item working">{item.description}</div>'
                pivot_html += '</div>'

            if pivot_analysis.diagnosis_failing:
                pivot_html += '<div class="pivot-section">'
                pivot_html += '<div class="pivot-section-title">What\'s Struggling</div>'
                for item in pivot_analysis.diagnosis_failing[:4]:
                    pivot_html += f'<div class="pivot-item failing">{item.description}</div>'
                pivot_html += '</div>'

            pivot_html += '</div>'
            st.markdown(pivot_html, unsafe_allow_html=True)

            if pivot_analysis.pivots:
                render_section_header("Pivot Options")

                for pivot in pivot_analysis.pivots[:3]:
                    is_recommended = pivot == pivot_analysis.recommended_pivot
                    rec_class = "recommended" if is_recommended else ""
                    border_color = COLORS["accent_teal"] if is_recommended else COLORS["border"]

                    rec_html = f'<div class="pivot-recommendation" style="border-color: {border_color};">'
                    rec_html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
                    rec_html += f'<span class="pivot-rec-name">{pivot.name}</span>'
                    if is_recommended:
                        rec_html += f'<span class="pivot-rec-badge">RECOMMENDED</span>'
                    rec_html += '</div>'
                    rec_html += f'<div style="font-size: 14px; color: {COLORS["text_secondary"]}; margin-bottom: 8px;">{pivot.description}</div>'
                    rec_html += f'<div style="font-size: 12px; color: {COLORS["text_muted"]};">Confidence: {pivot.confidence*100:.0f}% | Risk: {pivot.risk_change}</div>'
                    rec_html += '</div>'
                    st.markdown(rec_html, unsafe_allow_html=True)

                if pivot_analysis.recommended_pivot:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"APPLY: {pivot_analysis.recommended_pivot.name}", type="primary", key="apply_pivot"):
                            try:
                                success = apply_recommended_pivot(pivot_analysis)
                                if success:
                                    st.success(f"Applied {pivot_analysis.recommended_pivot.name} successfully!")
                                    st.session_state.pivot_analysis = None
                                    st.rerun()
                                else:
                                    st.error("Failed to apply pivot")
                            except Exception as e:
                                st.error(f"Error: {e}")
                    with col2:
                        if st.button("DISMISS", key="dismiss_pivot"):
                            st.session_state.pivot_analysis = None
                            st.rerun()

    # ═══════════════════════════════════════════════════════════════════════════
    # POSITIONS SECTION
    # ═══════════════════════════════════════════════════════════════════════════
    winners = len(positions_df[positions_df['unrealized_pnl'] > 0]) if not positions_df.empty else 0
    losers = len(positions_df[positions_df['unrealized_pnl'] <= 0]) if not positions_df.empty else 0

    render_section_header("Positions", f"{winners}W / {losers}L")

    if not positions_df.empty:
        # View toggle
        view_col1, view_col2, view_col3 = st.columns([1, 1, 4])
        with view_col1:
            if st.button("Cards", key="view_cards", type="primary" if st.session_state.view_mode == "cards" else "secondary"):
                st.session_state.view_mode = "cards"
                st.rerun()
        with view_col2:
            if st.button("Table", key="view_table", type="primary" if st.session_state.view_mode == "table" else "secondary"):
                st.session_state.view_mode = "table"
                st.rerun()

        if st.session_state.view_mode == "cards":
            render_position_cards(positions_df)
        else:
            # Table view
            near_stop_tickers = {p['ticker'] for p in near_stop}
            near_target_tickers = {p['ticker'] for p in near_target}

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

                try:
                    entry_date = row.get('entry_date', '')
                    days_held = (datetime.now() - pd.to_datetime(entry_date)).days
                except:
                    days_held = 0

                port_weight = (market_value / total_equity) * 100 if total_equity > 0 else 0
                progress = calculate_position_progress(row)
                prog_pct = progress['progress_pct'] if progress else 50

                if ticker in near_stop_tickers:
                    row_bg = f"rgba(245,101,101,0.08)"
                elif pnl >= 0:
                    row_bg = f"rgba(72,187,120,0.05)"
                else:
                    row_bg = f"rgba(245,101,101,0.03)"

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
                rows_html += f'<td style="color: {COLORS["text_muted"]}; font-size: 12px;">{days_held}d</td>'
                rows_html += f'<td style="color: {COLORS["text_muted"]}; font-size: 12px;">${stop_loss:.0f}</td>'
                rows_html += f'<td style="color: {COLORS["text_muted"]}; font-size: 12px;">${take_profit:.0f}</td>'
                rows_html += f'<td><div style="width: 60px; height: 6px; background: {COLORS["bg_hover"]}; border-radius: 3px;"><div style="width: {prog_pct}%; height: 100%; background: {prog_color}; border-radius: 3px;"></div></div></td>'
                rows_html += '</tr>'

            table_html = f'<table style="width: 100%; border-collapse: collapse; font-size: 14px;">'
            table_html += f'<thead><tr style="border-bottom: 1px solid {COLORS["border"]};">'
            for h in ['Ticker', 'Shares', 'Entry', 'Current', 'Value', 'P&L', '%', 'Weight', 'Days', 'Stop', 'Target', 'Progress']:
                table_html += f'<th style="text-align: left; padding: 10px 8px; font-size: 11px; font-weight: 500; color: {COLORS["text_muted"]}; text-transform: uppercase; letter-spacing: 0.5px;">{h}</th>'
            table_html += '</tr></thead>'
            table_html += f'<tbody>{rows_html}</tbody></table>'
            st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info("No open positions")

    # ═══════════════════════════════════════════════════════════════════════════
    # PORTFOLIO COMPOSITION (Treemap)
    # ═══════════════════════════════════════════════════════════════════════════
    if not positions_df.empty and num_positions > 1:
        render_section_header("Portfolio Composition")
        render_portfolio_treemap(positions_df)

    # ═══════════════════════════════════════════════════════════════════════════
    # EQUITY CURVE
    # ═══════════════════════════════════════════════════════════════════════════
    if not snapshots_df.empty:
        render_section_header("Equity Curve")

        timeframes = ["1W", "1M", "3M", "YTD", "ALL"]
        cols = st.columns(len(timeframes))
        for i, tf in enumerate(timeframes):
            with cols[i]:
                if st.button(tf, key=f"tf_{tf}", use_container_width=True, type="primary" if st.session_state.chart_timeframe == tf else "secondary"):
                    st.session_state.chart_timeframe = tf
                    st.rerun()

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
            render_equity_curve(chart_df)

    # ═══════════════════════════════════════════════════════════════════════════
    # RECENT ACTIVITY
    # ═══════════════════════════════════════════════════════════════════════════
    render_section_header("Recent Activity")

    if not transactions_df.empty:
        recent = transactions_df.tail(8).iloc[::-1]

        for _, tx in recent.iterrows():
            action = tx["action"]
            ticker = tx["ticker"]
            shares = int(tx["shares"])
            price = tx["price"]
            total_val = tx.get("total_value", shares * price)
            date_str = str(tx["date"])
            reason = tx.get("reason", "")

            badge_color = COLORS["success"] if action == "BUY" else COLORS["danger"]
            badge_bg = f"rgba(72,187,120,0.15)" if action == "BUY" else f"rgba(245,101,101,0.15)"

            reason_html = ""
            if action == "SELL" and reason in ["STOP_LOSS", "TAKE_PROFIT"]:
                reason_text = "(Stop)" if reason == "STOP_LOSS" else "(Target)"
                reason_color = COLORS["danger"] if reason == "STOP_LOSS" else COLORS["success"]
                reason_html = f'<span style="color: {reason_color}; font-size: 12px; margin-left: 8px;">{reason_text}</span>'

            tx_html = f'<div style="display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid {COLORS["border"]}; gap: 12px;">'
            tx_html += f'<span style="background: {badge_bg}; color: {badge_color}; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 4px; min-width: 40px; text-align: center;">{action}</span>'
            tx_html += f'<span style="font-weight: 500; color: {COLORS["text_primary"]}; min-width: 50px;">{ticker}</span>'
            tx_html += f'<span style="color: {COLORS["text_secondary"]}; font-size: 13px; flex: 1;">{shares} @ ${price:.2f} = ${total_val:,.0f}{reason_html}</span>'
            tx_html += f'<span style="color: {COLORS["text_muted"]}; font-size: 12px;">{date_str}</span>'
            tx_html += '</div>'
            st.markdown(tx_html, unsafe_allow_html=True)
    else:
        st.info("No transactions yet")

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYSIS RESULTS
    # ═══════════════════════════════════════════════════════════════════════════
    if analysis:
        render_section_header("Analysis Results")
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
            decision_icon = "check" if decision == ReviewDecision.APPROVE else "edit" if decision == ReviewDecision.MODIFY else "x"
            blocked_opacity = "0.5" if decision == ReviewDecision.VETO else "1"
            conf_pct = int(confidence * 100)

            mods_html = ""
            if decision == ReviewDecision.MODIFY:
                mods = []
                if r.modified_shares and r.modified_shares != shares:
                    mods.append(f"shares: {shares} -> {r.modified_shares}")
                if r.modified_stop and r.modified_stop != action.stop_loss:
                    mods.append(f"stop: ${action.stop_loss:.0f} -> ${r.modified_stop:.0f}")
                if r.modified_target and r.modified_target != action.take_profit:
                    mods.append(f"target: ${action.take_profit:.0f} -> ${r.modified_target:.0f}")
                if mods:
                    mods_html = f'<div style="font-size: 12px; color: {COLORS["warning"]}; margin-top: 6px;">Modified: {", ".join(mods)}</div>'

            card_html = f'<div style="background: {COLORS["bg_card"]}; border: 1px solid {COLORS["border"]}; border-radius: 12px; padding: 16px; margin-bottom: 12px; opacity: {blocked_opacity};">'
            card_html += f'<div style="display: flex; justify-content: space-between; align-items: center;">'
            card_html += f'<div><span style="font-weight: 600; color: {action_color};">{action_type}</span> <span style="font-weight: 500; color: {COLORS["text_primary"]};">{ticker}</span> <span style="color: {COLORS["text_secondary"]}; font-size: 13px;">{shares} shares @ ${price:.2f}</span></div>'
            card_html += f'<div style="font-size: 13px; color: {decision_color}; font-weight: 500;">{decision}</div>'
            card_html += '</div>'
            card_html += f'<div style="display: flex; gap: 20px; margin-top: 8px; font-size: 12px; color: {COLORS["text_muted"]};">'
            card_html += f'<span>Quant Score: <strong style="color: {COLORS["text_primary"]};">{quant_score:.0f}</strong>/100</span>'
            card_html += f'<span>Confidence: <strong style="color: {COLORS["text_primary"]};">{conf_pct}%</strong></span>'
            card_html += '</div>'
            card_html += f'<div style="font-size: 13px; color: {COLORS["text_secondary"]}; margin-top: 10px;"><strong>Quant:</strong> {quant_reason}</div>'
            card_html += f'<div style="font-size: 13px; color: {COLORS["text_secondary"]}; margin-top: 6px;"><strong>AI Review:</strong> {ai_reason}</div>'
            card_html += mods_html
            card_html += '</div>'
            st.markdown(card_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# RISK METRICS ROW (Secondary metrics)
# ═══════════════════════════════════════════════════════════════════════════════
render_section_header("Risk Metrics")

metrics_html = f'<div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px;">'

def metric_card(label, value, color=None):
    val_color = color or COLORS["text_primary"]
    return f'<div style="background: {COLORS["bg_card"]}; border: 1px solid {COLORS["border"]}; border-radius: 12px; padding: 16px; text-align: center;"><div style="font-size: 11px; color: {COLORS["text_muted"]}; text-transform: uppercase; letter-spacing: 0.5px;">{label}</div><div style="font-size: 20px; font-weight: 600; color: {val_color}; margin-top: 4px;">{value}</div></div>'

sharpe_color = COLORS["success"] if sharpe_ratio > 1 else COLORS["warning"] if sharpe_ratio > 0 else COLORS["danger"]
dd_color = COLORS["success"] if max_drawdown < 5 else COLORS["warning"] if max_drawdown < 10 else COLORS["danger"]
wr_color = COLORS["success"] if win_rate > 50 else COLORS["warning"] if win_rate > 40 else COLORS["danger"]
pf_color = COLORS["success"] if profit_factor > 1.5 else COLORS["warning"] if profit_factor > 1 else COLORS["danger"]

metrics_html += metric_card("Sharpe Ratio", f"{sharpe_ratio:.2f}", sharpe_color)
metrics_html += metric_card("Max Drawdown", f"{max_drawdown:.1f}%", dd_color)
metrics_html += metric_card("Win Rate", f"{win_rate:.0f}%", wr_color)
metrics_html += metric_card("Profit Factor", f"{profit_factor:.2f}", pf_color)
avg_win_loss = f"${avg_win:.0f} / ${abs(avg_loss):.0f}" if avg_loss != 0 else "N/A"
metrics_html += metric_card("Avg Win/Loss", avg_win_loss)

metrics_html += '</div>'
st.markdown(metrics_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TRADE HISTORY (Collapsible)
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("Trade History / Journal", expanded=False):
    if not transactions_df.empty:
        sells = transactions_df[transactions_df['action'] == 'SELL'].copy()
        if not sells.empty:
            sells = sells.sort_values('date', ascending=False)

            for _, tx in sells.head(15).iterrows():
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
        st.info("No trade history")


# ═══════════════════════════════════════════════════════════════════════════════
# EMERGENCY CONTROLS (Collapsible)
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("Emergency Controls", expanded=False):
    st.markdown(f'<div style="color: {COLORS["danger"]}; font-size: 12px; margin-bottom: 12px;">Use with caution. These actions cannot be undone.</div>', unsafe_allow_html=True)

    if st.button("CLOSE ALL POSITIONS", key="close_all_btn"):
        st.session_state.show_close_all_confirm = True

    if st.session_state.show_close_all_confirm:
        st.warning("This will close ALL open positions at market price. Are you sure?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("YES, CLOSE ALL", type="primary", key="confirm_close"):
                count, msg = close_all_positions()
                if count > 0:
                    st.success(f"Closed {count} positions")
                else:
                    st.info(msg)
                st.session_state.show_close_all_confirm = False
                st.rerun()
        with col2:
            if st.button("CANCEL", key="cancel_close"):
                st.session_state.show_close_all_confirm = False
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
mode_indicator = "PAPER MODE" if paper_mode else "LIVE"
footer_html = f'<div style="text-align: center; padding: 32px 0 16px; font-size: 11px; color: {COLORS["text_muted"]}; letter-spacing: 1px; text-transform: uppercase; border-top: 1px solid {COLORS["border"]}; margin-top: 32px;">'
footer_html += f'{mode_indicator} | Unified Analysis (Quant + AI) | Not Financial Advice'
footer_html += '</div>'
st.markdown(footer_html, unsafe_allow_html=True)
