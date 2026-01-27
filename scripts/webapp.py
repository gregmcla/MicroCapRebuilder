#!/usr/bin/env python3
"""
Streamlit Web Dashboard for MicroCapRebuilder.

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


# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MicroCapRebuilder",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #1e1e1e;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    .big-number {
        font-size: 2.5rem;
        font-weight: bold;
    }
    .positive { color: #00ff88; }
    .negative { color: #ff4444; }
    .neutral { color: #888888; }
</style>
""", unsafe_allow_html=True)


# ─── Header ───────────────────────────────────────────────────────────────────
st.title("📈 MicroCapRebuilder Dashboard")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Refresh button
if st.button("🔄 Refresh Data"):
    st.rerun()

st.divider()


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
total_return_pct = ((total_equity - starting_capital) / starting_capital) * 100


# ─── Top Row: Key Metrics ─────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="💰 Total Equity",
        value=f"${total_equity:,.2f}",
        delta=f"{total_return_pct:+.2f}%" if total_return_pct != 0 else None,
    )

with col2:
    exposure_pct = (positions_value / total_equity * 100) if total_equity > 0 else 0
    st.metric(
        label="📊 Positions Value",
        value=f"${positions_value:,.2f}",
        delta=f"{exposure_pct:.1f}% exposed",
    )

with col3:
    st.metric(
        label="💵 Cash Available",
        value=f"${cash:,.2f}",
        delta=f"{100 - exposure_pct:.1f}% of portfolio",
    )

with col4:
    num_positions = len(positions_df) if not positions_df.empty else 0
    max_positions = config.get("max_positions", 15)
    st.metric(
        label="📋 Positions",
        value=f"{num_positions} / {max_positions}",
        delta=f"{max_positions - num_positions} slots open",
    )

st.divider()


# ─── Second Row: Market Regime & Performance ──────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🌍 Market Regime")

    try:
        regime_analysis = get_regime_analysis()

        regime_colors = {
            MarketRegime.BULL: "🟢",
            MarketRegime.BEAR: "🔴",
            MarketRegime.SIDEWAYS: "🟡",
            MarketRegime.UNKNOWN: "⚪",
        }

        regime_emoji = regime_colors.get(regime_analysis.regime, "⚪")

        regime_col1, regime_col2 = st.columns(2)

        with regime_col1:
            st.markdown(f"### {regime_emoji} {regime_analysis.regime.value}")
            st.caption(f"Strength: {regime_analysis.regime_strength}")

        with regime_col2:
            st.metric("Benchmark", f"${regime_analysis.current_price:,.2f}")
            st.caption(f"50-day SMA: {'above' if regime_analysis.above_50 else 'below'}")
            st.caption(f"200-day SMA: {'above' if regime_analysis.above_200 else 'below'}")

    except Exception as e:
        st.warning(f"Could not fetch market regime: {e}")

with col_right:
    st.subheader("📊 Performance Metrics")

    try:
        analytics = PortfolioAnalytics()
        metrics = analytics.calculate_all_metrics()

        if metrics:
            perf_col1, perf_col2 = st.columns(2)

            with perf_col1:
                st.metric("Sharpe Ratio", f"{metrics.sharpe_ratio:.2f}")
                st.metric("Max Drawdown", f"{metrics.max_drawdown_pct:.2f}%")

            with perf_col2:
                st.metric("Total Return", f"{metrics.total_return_pct:+.2f}%")
                st.metric("Days Tracked", f"{metrics.days_tracked}")
        else:
            st.info("Insufficient data for metrics")

    except Exception as e:
        st.info("Run for a few days to see performance metrics")

st.divider()


# ─── Third Row: Trade Statistics ──────────────────────────────────────────────
st.subheader("📈 Trade Statistics")

try:
    analyzer = TradeAnalyzer()
    trade_stats = analyzer.calculate_trade_stats()

    if trade_stats and trade_stats.total_trades > 0:
        stat_cols = st.columns(6)

        with stat_cols[0]:
            st.metric("Total Trades", trade_stats.total_trades)
        with stat_cols[1]:
            st.metric("Win Rate", f"{trade_stats.win_rate_pct:.1f}%")
        with stat_cols[2]:
            st.metric("Profit Factor", f"{trade_stats.profit_factor:.2f}x")
        with stat_cols[3]:
            st.metric("Avg Win", f"{trade_stats.avg_win_pct:+.2f}%")
        with stat_cols[4]:
            st.metric("Avg Loss", f"{trade_stats.avg_loss_pct:.2f}%")
        with stat_cols[5]:
            color = "normal" if trade_stats.total_realized_pnl >= 0 else "inverse"
            st.metric("Realized P&L", f"${trade_stats.total_realized_pnl:+,.2f}", delta_color=color)
    else:
        st.info(f"No completed trades yet. Open positions: {trade_stats.open_positions if trade_stats else num_positions}")

except Exception as e:
    st.info("Trade statistics will appear after completed trades")

st.divider()


# ─── Positions Table ──────────────────────────────────────────────────────────
st.subheader("📋 Current Positions")

if not positions_df.empty:
    # Format for display
    display_df = positions_df.copy()

    # Select and rename columns
    columns_to_show = ["ticker", "shares", "avg_cost_basis", "current_price",
                       "market_value", "unrealized_pnl", "unrealized_pnl_pct",
                       "stop_loss", "take_profit"]

    available_cols = [c for c in columns_to_show if c in display_df.columns]
    display_df = display_df[available_cols]

    # Rename for display
    column_names = {
        "ticker": "Ticker",
        "shares": "Shares",
        "avg_cost_basis": "Avg Cost",
        "current_price": "Current",
        "market_value": "Value",
        "unrealized_pnl": "P&L ($)",
        "unrealized_pnl_pct": "P&L (%)",
        "stop_loss": "Stop Loss",
        "take_profit": "Take Profit",
    }
    display_df = display_df.rename(columns=column_names)

    # Style the dataframe
    def color_pnl(val):
        if pd.isna(val):
            return ""
        try:
            val = float(val)
            if val > 0:
                return "color: #00ff88"
            elif val < 0:
                return "color: #ff4444"
        except:
            pass
        return ""

    styled_df = display_df.style.applymap(
        color_pnl,
        subset=["P&L ($)", "P&L (%)"] if "P&L ($)" in display_df.columns else []
    ).format({
        "Avg Cost": "${:.2f}",
        "Current": "${:.2f}",
        "Value": "${:,.2f}",
        "P&L ($)": "${:+,.2f}",
        "P&L (%)": "{:+.2f}%",
        "Stop Loss": "${:.2f}",
        "Take Profit": "${:.2f}",
    }, na_rep="-")

    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # Summary stats below table
    total_unrealized = positions_df["unrealized_pnl"].sum() if "unrealized_pnl" in positions_df.columns else 0
    st.caption(f"**Total Unrealized P&L:** ${total_unrealized:+,.2f}")

else:
    st.info("No positions yet. Run `./run_daily.sh` to start trading.")

st.divider()


# ─── Recent Transactions ──────────────────────────────────────────────────────
st.subheader("📜 Recent Transactions")

if not transactions_df.empty:
    recent = transactions_df.tail(10).iloc[::-1]  # Last 10, reversed

    display_txn = recent[["date", "action", "ticker", "shares", "price", "total_value", "reason"]].copy()
    display_txn.columns = ["Date", "Action", "Ticker", "Shares", "Price", "Value", "Reason"]

    def color_action(val):
        if val == "BUY":
            return "color: #00ff88"
        elif val == "SELL":
            return "color: #ff4444"
        return ""

    styled_txn = display_txn.style.applymap(color_action, subset=["Action"]).format({
        "Price": "${:.2f}",
        "Value": "${:,.2f}",
    })

    st.dataframe(styled_txn, use_container_width=True, hide_index=True)
else:
    st.info("No transactions yet.")

st.divider()


# ─── Equity Chart ─────────────────────────────────────────────────────────────
st.subheader("📈 Equity Curve")

if not snapshots_df.empty and len(snapshots_df) > 1:
    chart_df = snapshots_df[["date", "total_equity"]].copy()
    chart_df["date"] = pd.to_datetime(chart_df["date"])
    chart_df = chart_df.set_index("date")

    st.line_chart(chart_df, use_container_width=True)
else:
    st.info("Equity chart will appear after a few days of trading.")


# ─── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.caption("MicroCapRebuilder | Run `./run_daily.sh` to update data | Refresh page to see changes")
