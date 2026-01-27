#!/usr/bin/env python3
"""
Bloomberg-Style Terminal Dashboard for MicroCapRebuilder.

An elite financial terminal interface for portfolio monitoring.
Run with: streamlit run scripts/webapp.py
"""

import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Add scripts directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from analytics import PortfolioAnalytics
from trade_analyzer import TradeAnalyzer
from market_regime import get_regime_analysis, MarketRegime

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
POSITIONS_FILE = DATA_DIR / "positions.csv"
TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"
DAILY_SNAPSHOTS_FILE = DATA_DIR / "daily_snapshots.csv"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config():
    """Load configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"starting_capital": 50000.0}


def load_positions():
    """Load current positions."""
    if not POSITIONS_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(POSITIONS_FILE)


def load_transactions():
    """Load all transactions."""
    if not TRANSACTIONS_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(TRANSACTIONS_FILE)


def load_snapshots():
    """Load daily snapshots."""
    if not DAILY_SNAPSHOTS_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(DAILY_SNAPSHOTS_FILE)


def calculate_cash():
    """Calculate available cash from transactions."""
    config = load_config()
    transactions_df = load_transactions()

    if transactions_df.empty:
        return config["starting_capital"]

    buys = transactions_df[transactions_df["action"] == "BUY"]["total_value"].sum()
    sells = transactions_df[transactions_df["action"] == "SELL"]["total_value"].sum()

    return config["starting_capital"] - buys + sells


def format_currency(value, decimals=2):
    """Format currency with proper signs."""
    if value >= 0:
        return f"${value:,.{decimals}f}"
    return f"-${abs(value):,.{decimals}f}"


def format_pct(value):
    """Format percentage with color class."""
    return f"{value:+.2f}%"


# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MCR Terminal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Bloomberg Terminal CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
    /* Import terminal font */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    /* Root variables */
    :root {
        --bg-primary: #0a0a0a;
        --bg-secondary: #111111;
        --bg-tertiary: #1a1a1a;
        --border-color: #2a2a2a;
        --text-primary: #e0e0e0;
        --text-secondary: #888888;
        --text-muted: #555555;
        --accent-orange: #ff6600;
        --accent-amber: #ffaa00;
        --accent-yellow: #ffcc00;
        --positive: #00ff88;
        --negative: #ff4444;
        --neutral: #888888;
        --blue: #4488ff;
    }

    /* Main container */
    .stApp {
        background-color: var(--bg-primary) !important;
        font-family: 'JetBrains Mono', 'Consolas', 'Monaco', monospace !important;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* All text monospace */
    * {
        font-family: 'JetBrains Mono', 'Consolas', 'Monaco', monospace !important;
    }

    /* Terminal header bar */
    .terminal-header {
        background: linear-gradient(180deg, #1a1a1a 0%, #0a0a0a 100%);
        border-bottom: 2px solid var(--accent-orange);
        padding: 8px 16px;
        margin: -1rem -1rem 1rem -1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .terminal-title {
        color: var(--accent-orange);
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    .terminal-timestamp {
        color: var(--text-secondary);
        font-size: 0.85rem;
    }

    /* Panel styling */
    .panel {
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 0;
        padding: 12px;
        margin-bottom: 8px;
    }

    .panel-header {
        color: var(--accent-amber);
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 6px;
        margin-bottom: 10px;
    }

    /* Metric display */
    .metric-row {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        border-bottom: 1px dotted var(--border-color);
    }

    .metric-label {
        color: var(--text-secondary);
        font-size: 0.8rem;
    }

    .metric-value {
        color: var(--text-primary);
        font-size: 0.85rem;
        font-weight: 500;
    }

    .metric-value.positive { color: var(--positive); }
    .metric-value.negative { color: var(--negative); }
    .metric-value.accent { color: var(--accent-amber); }

    /* Big number display */
    .big-metric {
        text-align: center;
        padding: 8px;
    }

    .big-metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .big-metric-label {
        font-size: 0.7rem;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .big-metric-delta {
        font-size: 0.9rem;
        margin-top: 2px;
    }

    /* Market regime badge */
    .regime-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 2px;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 1px;
    }

    .regime-bull {
        background-color: rgba(0, 255, 136, 0.15);
        color: var(--positive);
        border: 1px solid var(--positive);
    }

    .regime-bear {
        background-color: rgba(255, 68, 68, 0.15);
        color: var(--negative);
        border: 1px solid var(--negative);
    }

    .regime-sideways {
        background-color: rgba(255, 204, 0, 0.15);
        color: var(--accent-yellow);
        border: 1px solid var(--accent-yellow);
    }

    /* Data table styling */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.8rem;
    }

    .data-table th {
        background-color: var(--bg-tertiary);
        color: var(--accent-amber);
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.7rem;
        letter-spacing: 0.5px;
        padding: 8px 6px;
        text-align: left;
        border-bottom: 2px solid var(--accent-orange);
    }

    .data-table td {
        padding: 6px;
        border-bottom: 1px solid var(--border-color);
        color: var(--text-primary);
    }

    .data-table tr:hover {
        background-color: var(--bg-tertiary);
    }

    .data-table .ticker {
        color: var(--accent-amber);
        font-weight: 600;
    }

    .data-table .positive { color: var(--positive); }
    .data-table .negative { color: var(--negative); }
    .data-table .muted { color: var(--text-muted); }

    /* Ticker tape */
    .ticker-tape {
        background-color: var(--bg-tertiary);
        border-top: 1px solid var(--accent-orange);
        border-bottom: 1px solid var(--accent-orange);
        padding: 6px 12px;
        overflow: hidden;
        white-space: nowrap;
        font-size: 0.75rem;
        margin: 8px 0;
    }

    .ticker-item {
        display: inline-block;
        margin-right: 24px;
    }

    .ticker-symbol {
        color: var(--accent-amber);
        font-weight: 600;
        margin-right: 6px;
    }

    /* Activity log */
    .activity-row {
        display: flex;
        padding: 6px 0;
        border-bottom: 1px solid var(--border-color);
        font-size: 0.8rem;
    }

    .activity-date {
        color: var(--text-muted);
        width: 90px;
    }

    .activity-action {
        width: 50px;
        font-weight: 600;
    }

    .activity-action.buy { color: var(--positive); }
    .activity-action.sell { color: var(--negative); }

    .activity-ticker {
        color: var(--accent-amber);
        width: 70px;
        font-weight: 500;
    }

    .activity-details {
        color: var(--text-secondary);
        flex: 1;
    }

    /* Divider */
    .terminal-divider {
        border: none;
        border-top: 1px solid var(--border-color);
        margin: 16px 0;
    }

    /* Status indicator */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
    }

    .status-dot.live { background-color: var(--positive); }
    .status-dot.stale { background-color: var(--accent-amber); }
    .status-dot.error { background-color: var(--negative); }

    /* Override Streamlit defaults */
    .stMetric {
        background-color: var(--bg-secondary) !important;
    }

    [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
    }

    [data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
    }

    .stDataFrame {
        background-color: var(--bg-secondary) !important;
    }

    /* Chart styling */
    .stPlotlyChart {
        background-color: var(--bg-secondary) !important;
    }

    /* Button styling */
    .stButton > button {
        background-color: var(--bg-tertiary) !important;
        color: var(--accent-orange) !important;
        border: 1px solid var(--accent-orange) !important;
        border-radius: 0 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 600 !important;
        letter-spacing: 1px !important;
        text-transform: uppercase !important;
        font-size: 0.75rem !important;
    }

    .stButton > button:hover {
        background-color: var(--accent-orange) !important;
        color: var(--bg-primary) !important;
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: var(--bg-secondary) !important;
        color: var(--accent-amber) !important;
    }
</style>
""", unsafe_allow_html=True)


# ─── Load Data ────────────────────────────────────────────────────────────────
config = load_config()
positions_df = load_positions()
transactions_df = load_transactions()
snapshots_df = load_snapshots()
cash = calculate_cash()

# Calculate totals
positions_value = positions_df["market_value"].sum() if not positions_df.empty else 0
total_equity = positions_value + cash
starting_capital = config.get("starting_capital", 50000.0)
total_return = total_equity - starting_capital
total_return_pct = ((total_equity - starting_capital) / starting_capital) * 100


# ─── Terminal Header ──────────────────────────────────────────────────────────
st.markdown(f"""
<div class="terminal-header">
    <div class="terminal-title">◆ MICROCAP REBUILDER TERMINAL</div>
    <div class="terminal-timestamp">
        <span class="status-dot live"></span>
        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EST
    </div>
</div>
""", unsafe_allow_html=True)


# ─── Ticker Tape ──────────────────────────────────────────────────────────────
if not positions_df.empty:
    ticker_items = ""
    for _, row in positions_df.iterrows():
        pnl_class = "positive" if row.get("unrealized_pnl_pct", 0) >= 0 else "negative"
        pnl_val = row.get("unrealized_pnl_pct", 0)
        ticker_items += f"""
        <span class="ticker-item">
            <span class="ticker-symbol">{row['ticker']}</span>
            <span class="{pnl_class}">{pnl_val:+.2f}%</span>
        </span>
        """
    st.markdown(f'<div class="ticker-tape">{ticker_items}</div>', unsafe_allow_html=True)


# ─── Main Metrics Row ─────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    pnl_class = "positive" if total_return >= 0 else "negative"
    st.markdown(f"""
    <div class="panel">
        <div class="big-metric">
            <div class="big-metric-label">Total Equity</div>
            <div class="big-metric-value">{format_currency(total_equity, 0)}</div>
            <div class="big-metric-delta {pnl_class}">{format_pct(total_return_pct)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    exposure_pct = (positions_value / total_equity * 100) if total_equity > 0 else 0
    st.markdown(f"""
    <div class="panel">
        <div class="big-metric">
            <div class="big-metric-label">Positions</div>
            <div class="big-metric-value">{format_currency(positions_value, 0)}</div>
            <div class="big-metric-delta" style="color: var(--accent-amber);">{exposure_pct:.1f}% EXPOSURE</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    cash_pct = 100 - exposure_pct
    st.markdown(f"""
    <div class="panel">
        <div class="big-metric">
            <div class="big-metric-label">Cash</div>
            <div class="big-metric-value">{format_currency(cash, 0)}</div>
            <div class="big-metric-delta" style="color: var(--blue);">{cash_pct:.1f}% AVAILABLE</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    num_positions = len(positions_df) if not positions_df.empty else 0
    max_positions = config.get("max_positions", 15)
    st.markdown(f"""
    <div class="panel">
        <div class="big-metric">
            <div class="big-metric-label">Positions</div>
            <div class="big-metric-value">{num_positions}<span style="color: var(--text-muted); font-size: 1rem;">/{max_positions}</span></div>
            <div class="big-metric-delta" style="color: var(--text-secondary);">{max_positions - num_positions} SLOTS OPEN</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    # Day P&L from snapshots
    day_pnl = 0
    day_pnl_pct = 0
    if not snapshots_df.empty and len(snapshots_df) >= 1:
        day_pnl = snapshots_df.iloc[-1].get("day_pnl", 0)
        day_pnl_pct = snapshots_df.iloc[-1].get("day_pnl_pct", 0)

    pnl_class = "positive" if day_pnl >= 0 else "negative"
    st.markdown(f"""
    <div class="panel">
        <div class="big-metric">
            <div class="big-metric-label">Day P&L</div>
            <div class="big-metric-value {pnl_class}">{format_currency(day_pnl, 0)}</div>
            <div class="big-metric-delta {pnl_class}">{format_pct(day_pnl_pct)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Second Row: Regime & Performance & Trade Stats ───────────────────────────
col_regime, col_perf, col_trades = st.columns(3)

with col_regime:
    st.markdown('<div class="panel"><div class="panel-header">◆ MARKET REGIME</div>', unsafe_allow_html=True)

    try:
        regime_analysis = get_regime_analysis()

        regime_class = {
            MarketRegime.BULL: "regime-bull",
            MarketRegime.BEAR: "regime-bear",
            MarketRegime.SIDEWAYS: "regime-sideways",
            MarketRegime.UNKNOWN: "regime-sideways",
        }.get(regime_analysis.regime, "regime-sideways")

        regime_icon = {
            MarketRegime.BULL: "▲",
            MarketRegime.BEAR: "▼",
            MarketRegime.SIDEWAYS: "◆",
            MarketRegime.UNKNOWN: "?",
        }.get(regime_analysis.regime, "?")

        st.markdown(f"""
        <div style="margin-bottom: 12px;">
            <span class="regime-badge {regime_class}">{regime_icon} {regime_analysis.regime.value.upper()}</span>
            <span style="color: var(--text-muted); margin-left: 8px; font-size: 0.8rem;">
                {regime_analysis.regime_strength}
            </span>
        </div>
        <div class="metric-row">
            <span class="metric-label">BENCHMARK</span>
            <span class="metric-value accent">{format_currency(regime_analysis.current_price)}</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">50D SMA</span>
            <span class="metric-value {'positive' if regime_analysis.above_50 else 'negative'}">
                {format_currency(regime_analysis.sma_50)} {'▲' if regime_analysis.above_50 else '▼'}
            </span>
        </div>
        <div class="metric-row">
            <span class="metric-label">200D SMA</span>
            <span class="metric-value {'positive' if regime_analysis.above_200 else 'negative'}">
                {format_currency(regime_analysis.sma_200)} {'▲' if regime_analysis.above_200 else '▼'}
            </span>
        </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f"""
        <div style="color: var(--text-muted);">
            Market data unavailable
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

with col_perf:
    st.markdown('<div class="panel"><div class="panel-header">◆ PERFORMANCE METRICS</div>', unsafe_allow_html=True)

    try:
        analytics = PortfolioAnalytics()
        metrics = analytics.calculate_all_metrics()

        if metrics:
            sharpe_class = "positive" if metrics.sharpe_ratio > 1 else ("negative" if metrics.sharpe_ratio < 0 else "")
            dd_class = "negative" if metrics.max_drawdown_pct < -5 else ""
            return_class = "positive" if metrics.total_return_pct > 0 else "negative"

            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">SHARPE RATIO</span>
                <span class="metric-value {sharpe_class}">{metrics.sharpe_ratio:.2f}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">MAX DRAWDOWN</span>
                <span class="metric-value {dd_class}">{metrics.max_drawdown_pct:.2f}%</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">TOTAL RETURN</span>
                <span class="metric-value {return_class}">{metrics.total_return_pct:+.2f}%</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">DAYS TRACKED</span>
                <span class="metric-value">{metrics.days_tracked}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<span style="color: var(--text-muted);">Insufficient data</span>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown('<span style="color: var(--text-muted);">Collecting data...</span>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

with col_trades:
    st.markdown('<div class="panel"><div class="panel-header">◆ TRADE STATISTICS</div>', unsafe_allow_html=True)

    try:
        analyzer = TradeAnalyzer()
        trade_stats = analyzer.calculate_trade_stats()

        if trade_stats and trade_stats.total_trades > 0:
            wr_class = "positive" if trade_stats.win_rate_pct >= 50 else "negative"
            pf_class = "positive" if trade_stats.profit_factor >= 1 else "negative"
            pnl_class = "positive" if trade_stats.total_realized_pnl >= 0 else "negative"

            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">WIN RATE</span>
                <span class="metric-value {wr_class}">{trade_stats.win_rate_pct:.1f}%</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">PROFIT FACTOR</span>
                <span class="metric-value {pf_class}">{trade_stats.profit_factor:.2f}x</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">AVG WIN / LOSS</span>
                <span class="metric-value">
                    <span class="positive">{trade_stats.avg_win_pct:+.1f}%</span> /
                    <span class="negative">{trade_stats.avg_loss_pct:.1f}%</span>
                </span>
            </div>
            <div class="metric-row">
                <span class="metric-label">REALIZED P&L</span>
                <span class="metric-value {pnl_class}">{format_currency(trade_stats.total_realized_pnl)}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            open_pos = trade_stats.open_positions if trade_stats else num_positions
            st.markdown(f'<span style="color: var(--text-muted);">No closed trades yet ({open_pos} open)</span>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown('<span style="color: var(--text-muted);">Awaiting trades...</span>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─── Positions Table ──────────────────────────────────────────────────────────
st.markdown(f"""
<div class="panel">
    <div class="panel-header">◆ POSITIONS ({num_positions})</div>
""", unsafe_allow_html=True)

if not positions_df.empty:
    table_html = """
    <table class="data-table">
        <thead>
            <tr>
                <th>TICKER</th>
                <th style="text-align: right;">SHARES</th>
                <th style="text-align: right;">AVG COST</th>
                <th style="text-align: right;">CURRENT</th>
                <th style="text-align: right;">MKT VALUE</th>
                <th style="text-align: right;">P&L</th>
                <th style="text-align: right;">P&L %</th>
                <th style="text-align: right;">STOP</th>
                <th style="text-align: right;">TARGET</th>
            </tr>
        </thead>
        <tbody>
    """

    for _, row in positions_df.iterrows():
        pnl = row.get("unrealized_pnl", 0)
        pnl_pct = row.get("unrealized_pnl_pct", 0)
        pnl_class = "positive" if pnl >= 0 else "negative"

        table_html += f"""
        <tr>
            <td class="ticker">{row['ticker']}</td>
            <td style="text-align: right;">{row['shares']:,.0f}</td>
            <td style="text-align: right;">${row['avg_cost_basis']:.2f}</td>
            <td style="text-align: right;">${row['current_price']:.2f}</td>
            <td style="text-align: right;">${row['market_value']:,.2f}</td>
            <td style="text-align: right;" class="{pnl_class}">{format_currency(pnl)}</td>
            <td style="text-align: right;" class="{pnl_class}">{pnl_pct:+.2f}%</td>
            <td style="text-align: right;" class="muted">${row.get('stop_loss', 0):.2f}</td>
            <td style="text-align: right;" class="muted">${row.get('take_profit', 0):.2f}</td>
        </tr>
        """

    table_html += "</tbody></table>"

    # Summary row
    total_unrealized = positions_df["unrealized_pnl"].sum() if "unrealized_pnl" in positions_df.columns else 0
    unrealized_class = "positive" if total_unrealized >= 0 else "negative"

    table_html += f"""
    <div style="text-align: right; padding-top: 8px; border-top: 1px solid var(--border-color); margin-top: 8px;">
        <span style="color: var(--text-secondary);">TOTAL UNREALIZED:</span>
        <span class="{unrealized_class}" style="font-weight: 600; margin-left: 8px;">{format_currency(total_unrealized)}</span>
    </div>
    """

    st.markdown(table_html, unsafe_allow_html=True)
else:
    st.markdown('<span style="color: var(--text-muted);">No positions. Run ./run_daily.sh to start trading.</span>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)


# ─── Recent Activity ──────────────────────────────────────────────────────────
st.markdown("""
<div class="panel">
    <div class="panel-header">◆ RECENT ACTIVITY</div>
""", unsafe_allow_html=True)

if not transactions_df.empty:
    recent = transactions_df.tail(8).iloc[::-1]

    activity_html = ""
    for _, row in recent.iterrows():
        action_class = "buy" if row["action"] == "BUY" else "sell"
        activity_html += f"""
        <div class="activity-row">
            <span class="activity-date">{row['date']}</span>
            <span class="activity-action {action_class}">{row['action']}</span>
            <span class="activity-ticker">{row['ticker']}</span>
            <span class="activity-details">
                {row['shares']:.0f} @ ${row['price']:.2f} = ${row['total_value']:,.2f}
                <span style="color: var(--text-muted); margin-left: 8px;">[{row.get('reason', 'SIGNAL')}]</span>
            </span>
        </div>
        """

    st.markdown(activity_html, unsafe_allow_html=True)
else:
    st.markdown('<span style="color: var(--text-muted);">No transactions recorded.</span>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)


# ─── Equity Chart ─────────────────────────────────────────────────────────────
if not snapshots_df.empty and len(snapshots_df) > 1:
    st.markdown("""
    <div class="panel">
        <div class="panel-header">◆ EQUITY CURVE</div>
    </div>
    """, unsafe_allow_html=True)

    chart_df = snapshots_df[["date", "total_equity"]].copy()
    chart_df["date"] = pd.to_datetime(chart_df["date"])
    chart_df = chart_df.set_index("date")
    chart_df.columns = ["EQUITY"]

    st.line_chart(chart_df, use_container_width=True, color="#ff6600")


# ─── Footer ───────────────────────────────────────────────────────────────────
col_left, col_center, col_right = st.columns([1, 2, 1])

with col_center:
    if st.button("⟳ REFRESH DATA"):
        st.rerun()

st.markdown("""
<div style="text-align: center; padding: 16px; color: var(--text-muted); font-size: 0.7rem; border-top: 1px solid var(--border-color); margin-top: 16px;">
    MICROCAP REBUILDER TERMINAL v2.0 | DATA DELAYED | NOT FINANCIAL ADVICE
</div>
""", unsafe_allow_html=True)
