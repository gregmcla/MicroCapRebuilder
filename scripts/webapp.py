#!/usr/bin/env python3
"""
Mommy Bot - Bloomberg-Style Terminal Dashboard.
Run with: streamlit run scripts/webapp.py
"""

import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
import sys

sys.path.insert(0, str(Path(__file__).parent))

from analytics import PortfolioAnalytics
from trade_analyzer import TradeAnalyzer
from market_regime import get_regime_analysis, MarketRegime

# ─── Ticker URLs ──────────────────────────────────────────────────────────────
TICKER_URLS = {
    "RIOT": "https://www.riotplatforms.com/",
    "SMR": "https://www.nuscalepower.com/",
    "TDW": "https://www.teradyne.com/",
    "BELFB": "https://www.belfuse.com/",
    "AVAV": "https://www.avinc.com/",
    "MGY": "https://www.magnoliaoilgas.com/",
    "GOLF": "https://www.callawaygolf.com/",
    "BTU": "https://www.peabodyenergy.com/",
    "TEX": "https://www.terex.com/",
    "CAKE": "https://www.thecheesecakefactory.com/",
    "AXSM": "https://www.axsome.com/",
    "CRC": "https://www.calresources.com/",
    "LMND": "https://www.lemonade.com/",
    "PFSI": "https://www.pfsinvestments.com/",
    "EAT": "https://www.brinker.com/",
}

def get_ticker_link(ticker):
    """Return markdown hyperlink for ticker if URL exists, otherwise plain text."""
    url = TICKER_URLS.get(ticker)
    if url:
        return f"[{ticker}]({url})"
    return ticker

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
POSITIONS_FILE = DATA_DIR / "positions.csv"
TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"
DAILY_SNAPSHOTS_FILE = DATA_DIR / "daily_snapshots.csv"
CONFIG_FILE = DATA_DIR / "config.json"


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"starting_capital": 50000.0}


def load_positions():
    if not POSITIONS_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(POSITIONS_FILE)


def load_transactions():
    if not TRANSACTIONS_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(TRANSACTIONS_FILE)


def load_snapshots():
    if not DAILY_SNAPSHOTS_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(DAILY_SNAPSHOTS_FILE)


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
    page_title="Mommy Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
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
    --positive: #00ff88;
    --negative: #ff4444;
    --blue: #4488ff;
}
.stApp { background-color: var(--bg-primary) !important; }
#MainMenu, footer, header { visibility: hidden; }
* { font-family: 'JetBrains Mono', 'Consolas', monospace !important; }
.block-container { padding-top: 1rem !important; }
[data-testid="stMetric"] { background-color: var(--bg-secondary); border: 1px solid var(--border-color); padding: 10px; }
[data-testid="stMetricLabel"] { color: var(--accent-amber) !important; font-size: 0.7rem !important; }
[data-testid="stMetricValue"] { color: var(--text-primary) !important; font-size: 1.4rem !important; font-weight: 700 !important; }
[data-testid="stMetricDelta"] > div { font-size: 0.8rem !important; }
.stButton > button { background-color: var(--bg-tertiary) !important; color: var(--accent-orange) !important; border: 1px solid var(--accent-orange) !important; border-radius: 0 !important; font-weight: 600 !important; }
.stButton > button:hover { background-color: var(--accent-orange) !important; color: var(--bg-primary) !important; }
div[data-testid="stDataFrame"] > div { background-color: var(--bg-secondary) !important; }
</style>""", unsafe_allow_html=True)


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


# ─── Header ───────────────────────────────────────────────────────────────────
h1, h2 = st.columns([3, 1])
with h1:
    st.markdown(f"## :orange[◆ MOMMY BOT]")
with h2:
    st.markdown(f"<p style='text-align:right; color:#888; padding-top:12px;'>🟢 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EST</p>", unsafe_allow_html=True)


# ─── Ticker Tape ──────────────────────────────────────────────────────────────
if not positions_df.empty:
    tape = []
    for _, r in positions_df.iterrows():
        ticker = r['ticker']
        pnl = r.get("unrealized_pnl_pct", 0)
        pnl_color = "#00ff88" if pnl >= 0 else "#ff4444"
        url = TICKER_URLS.get(ticker)
        if url:
            ticker_html = f'<a href="{url}" target="_blank" style="color:#ffaa00;font-weight:bold;text-decoration:none;">{ticker}</a>'
        else:
            ticker_html = f'<span style="color:#ffaa00;font-weight:bold;">{ticker}</span>'
        tape.append(f'{ticker_html} <span style="color:{pnl_color}">{pnl:+.2f}%</span>')
    st.markdown(" &nbsp;&nbsp;&nbsp; ".join(tape), unsafe_allow_html=True)
    st.divider()


# ─── Main Metrics ─────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("TOTAL EQUITY", f"${total_equity:,.0f}", f"{total_return_pct:+.2f}%")
with c2:
    st.metric("POSITIONS VALUE", f"${positions_value:,.0f}", f"{exposure_pct:.1f}% exposure")
with c3:
    st.metric("CASH", f"${cash:,.0f}", f"{100-exposure_pct:.1f}% available")
with c4:
    st.metric("POSITIONS", f"{num_positions} / {max_positions}", f"{max_positions - num_positions} slots open")
with c5:
    day_pnl = snapshots_df.iloc[-1].get("day_pnl", 0) if not snapshots_df.empty else 0
    day_pct = snapshots_df.iloc[-1].get("day_pnl_pct", 0) if not snapshots_df.empty else 0
    st.metric("DAY P&L", f"${day_pnl:,.0f}", f"{day_pct:+.2f}%")


st.markdown("")


# ─── Three Panels ─────────────────────────────────────────────────────────────
col_regime, col_perf, col_trades = st.columns(3)

with col_regime:
    st.markdown("#### :orange[◆ MARKET REGIME]")
    try:
        ra = get_regime_analysis()
        regime_emoji = {"BULL": "🟢 ▲ BULL", "BEAR": "🔴 ▼ BEAR", "SIDEWAYS": "🟡 ◆ SIDEWAYS"}.get(ra.regime.value.upper(), "⚪ UNKNOWN")
        st.markdown(f"**{regime_emoji}**")
        st.markdown(f"**Benchmark:** :orange[${ra.current_price:,.2f}]")
        a50 = "🟢" if ra.above_50 else "🔴"
        a200 = "🟢" if ra.above_200 else "🔴"
        st.markdown(f"**50D SMA:** {a50} ${ra.sma_50:,.2f}")
        st.markdown(f"**200D SMA:** {a200} ${ra.sma_200:,.2f}")
    except:
        st.markdown("_Market data unavailable_")

with col_perf:
    st.markdown("#### :orange[◆ PERFORMANCE]")
    try:
        analytics = PortfolioAnalytics()
        m = analytics.calculate_all_metrics()
        if m:
            st.markdown(f"**Sharpe Ratio:** {m.sharpe_ratio:.2f}")
            st.markdown(f"**Max Drawdown:** {m.max_drawdown_pct:.2f}%")
            st.markdown(f"**Total Return:** {m.total_return_pct:+.2f}%")
            st.markdown(f"**Days Tracked:** {m.days_tracked}")
        else:
            st.markdown("_Insufficient data_")
    except:
        st.markdown("_Collecting data..._")

with col_trades:
    st.markdown("#### :orange[◆ TRADE STATS]")
    try:
        analyzer = TradeAnalyzer()
        ts = analyzer.calculate_trade_stats()
        if ts and ts.total_trades > 0:
            st.markdown(f"**Win Rate:** {ts.win_rate_pct:.1f}%")
            st.markdown(f"**Profit Factor:** {ts.profit_factor:.2f}x")
            st.markdown(f"**Avg Win/Loss:** +{ts.avg_win_pct:.1f}% / {ts.avg_loss_pct:.1f}%")
            st.markdown(f"**Realized P&L:** ${ts.total_realized_pnl:,.2f}")
        else:
            st.markdown(f"_No closed trades yet ({num_positions} open)_")
    except:
        st.markdown("_Awaiting trades..._")


st.markdown("")
st.divider()


# ─── Positions Table ──────────────────────────────────────────────────────────
st.markdown(f"#### :orange[◆ POSITIONS ({num_positions})]")

if not positions_df.empty:
    display_df = positions_df[["ticker", "shares", "avg_cost_basis", "current_price", "market_value", "unrealized_pnl", "unrealized_pnl_pct", "stop_loss", "take_profit"]].copy()
    display_df.columns = ["TICKER", "SHARES", "AVG COST", "CURRENT", "MKT VALUE", "P&L $", "P&L %", "STOP", "TARGET"]
    display_df["AVG COST"] = display_df["AVG COST"].apply(lambda x: f"${x:.2f}")
    display_df["CURRENT"] = display_df["CURRENT"].apply(lambda x: f"${x:.2f}")
    display_df["MKT VALUE"] = display_df["MKT VALUE"].apply(lambda x: f"${x:,.2f}")
    display_df["P&L $"] = display_df["P&L $"].apply(lambda x: f"${x:+,.2f}")
    display_df["P&L %"] = display_df["P&L %"].apply(lambda x: f"{x:+.2f}%")
    display_df["STOP"] = display_df["STOP"].apply(lambda x: f"${x:.2f}")
    display_df["TARGET"] = display_df["TARGET"].apply(lambda x: f"${x:.2f}")
    display_df["SHARES"] = display_df["SHARES"].astype(int)

    # Build clickable ticker links row
    ticker_links = []
    for t in positions_df["ticker"].tolist():
        url = TICKER_URLS.get(t, f"https://finance.yahoo.com/quote/{t}")
        ticker_links.append(f'<a href="{url}" target="_blank" style="color:#ffaa00;text-decoration:none;margin-right:16px;">{t}</a>')
    st.markdown("**Quick Links:** " + " ".join(ticker_links), unsafe_allow_html=True)

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    total_unrealized = positions_df["unrealized_pnl"].sum()
    color = "green" if total_unrealized >= 0 else "red"
    st.markdown(f"**Total Unrealized P&L:** :{color}[${total_unrealized:+,.2f}]")
else:
    st.markdown("_No positions. Run ./run_daily.sh to start trading._")


st.markdown("")


# ─── Recent Activity ──────────────────────────────────────────────────────────
st.markdown("#### :orange[◆ RECENT ACTIVITY]")

if not transactions_df.empty:
    recent = transactions_df.tail(8).iloc[::-1][["date", "action", "ticker", "shares", "price", "total_value", "reason"]].copy()

    # Build clickable ticker links for recent transactions
    recent_tickers = recent["ticker"].unique().tolist()
    recent_links = []
    for t in recent_tickers:
        url = TICKER_URLS.get(t, f"https://finance.yahoo.com/quote/{t}")
        recent_links.append(f'<a href="{url}" target="_blank" style="color:#ffaa00;text-decoration:none;margin-right:16px;">{t}</a>')
    st.markdown("**Quick Links:** " + " ".join(recent_links), unsafe_allow_html=True)

    recent.columns = ["DATE", "ACTION", "TICKER", "SHARES", "PRICE", "VALUE", "REASON"]
    recent["SHARES"] = recent["SHARES"].astype(int)
    recent["PRICE"] = recent["PRICE"].apply(lambda x: f"${x:.2f}")
    recent["VALUE"] = recent["VALUE"].apply(lambda x: f"${x:,.2f}")
    st.dataframe(recent, use_container_width=True, hide_index=True)
else:
    st.markdown("_No transactions recorded._")


st.markdown("")


# ─── Equity Chart ─────────────────────────────────────────────────────────────
if not snapshots_df.empty and len(snapshots_df) > 1:
    st.markdown("#### :orange[◆ EQUITY CURVE]")
    chart_df = snapshots_df[["date", "total_equity"]].copy()
    chart_df["date"] = pd.to_datetime(chart_df["date"])
    chart_df = chart_df.set_index("date")
    chart_df.columns = ["EQUITY"]
    st.line_chart(chart_df, use_container_width=True, color="#ff6600")


# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("")
col_l, col_c, col_r = st.columns([1, 1, 1])
with col_c:
    if st.button("⟳ REFRESH DATA", use_container_width=True):
        st.rerun()

st.markdown("<p style='text-align:center; color:#555; font-size:0.7rem; margin-top:24px;'>MOMMY BOT v3.0 | DATA DELAYED | NOT FINANCIAL ADVICE</p>", unsafe_allow_html=True)
