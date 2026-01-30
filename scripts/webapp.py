#!/usr/bin/env python3
"""
Mommy Bot - Bloomberg-Style Terminal Dashboard.
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


# ─── Capital Preservation Banner ─────────────────────────────────────────────
try:
    preservation = get_preservation_status()
    if preservation.active:
        st.markdown("""
        <div style="background-color:#8B0000; border:2px solid #FF4444; padding:10px; margin:10px 0; border-radius:4px;">
            <span style="color:#FFFFFF; font-weight:bold;">🛡️ CAPITAL PRESERVATION MODE ACTIVE</span>
        </div>
        """, unsafe_allow_html=True)
        with st.expander("View Details", expanded=False):
            st.markdown("**Trigger Reasons:**")
            for reason in preservation.trigger_reasons:
                st.markdown(f"- {reason}")
            st.markdown("**Actions:**")
            for action in preservation.actions_taken:
                st.markdown(f"- {action.name}: {action.description}")
            st.markdown("**Exit Conditions:**")
            for condition in preservation.exit_conditions:
                st.markdown(f"- {condition}")
except Exception:
    pass


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


# ─── Four Panels ─────────────────────────────────────────────────────────────
col_regime, col_risk, col_perf, col_trades = st.columns(4)

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

with col_risk:
    st.markdown("#### :orange[◆ RISK SCORE]")
    try:
        risk = get_risk_scoreboard()
        # Color code based on risk level
        risk_colors = {"LOW": "🟢", "MODERATE": "🟡", "ELEVATED": "🟠", "HIGH": "🔴", "CRITICAL": "⚫"}
        risk_icon = risk_colors.get(risk.risk_level, "⚪")
        st.markdown(f"**{risk_icon} {risk.overall_score:.0f}/100 ({risk.risk_level})**")
        # Show component summary
        for c in risk.components[:3]:  # Top 3 components
            status_icon = "✓" if c.status == "OK" else ("⚠" if c.status == "WARNING" else "✗")
            st.markdown(f"**{c.name}:** {status_icon} {c.score:.0f}")
        if risk.recommended_actions:
            st.caption(risk.recommended_actions[0][:50] + "..." if len(risk.recommended_actions[0]) > 50 else risk.recommended_actions[0])
    except Exception as e:
        st.markdown("_Calculating risk..._")

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


# ─── Risk Assessment Detail ──────────────────────────────────────────────────
st.markdown("#### :orange[◆ RISK ASSESSMENT]")
try:
    risk = get_risk_scoreboard()

    # Risk meter row
    r1, r2, r3 = st.columns([1, 2, 1])
    with r1:
        risk_colors = {"LOW": "green", "MODERATE": "orange", "ELEVATED": "orange", "HIGH": "red", "CRITICAL": "red"}
        st.metric("RISK SCORE", f"{risk.overall_score:.0f}/100", risk.risk_level)
    with r2:
        st.markdown(f"**Assessment:** {risk.narrative}")
    with r3:
        pass

    # Component breakdown
    st.markdown("**Component Scores:**")
    comp_cols = st.columns(5)
    for i, c in enumerate(risk.components):
        with comp_cols[i]:
            status_color = "green" if c.status == "OK" else ("orange" if c.status == "WARNING" else "red")
            st.markdown(f":{status_color}[**{c.name}**]")
            st.markdown(f"{c.score:.0f}/100")

    # Recommendations
    if risk.recommended_actions:
        st.markdown("**Recommendations:**")
        for rec in risk.recommended_actions[:3]:
            st.markdown(f"- {rec}")

except Exception as e:
    st.markdown("_Risk assessment loading..._")

st.markdown("")


# ─── Performance Attribution ─────────────────────────────────────────────────
st.markdown("#### :orange[◆ WHY TODAY HAPPENED]")
try:
    attribution = get_daily_attribution()
    if attribution and (attribution.total_return != 0 or attribution.top_contributors):
        # Summary row
        a1, a2, a3 = st.columns([1, 2, 1])
        with a1:
            pnl_color = "green" if attribution.total_return >= 0 else "red"
            st.metric("DAY P&L", f"${attribution.total_return:+,.2f}", f"{attribution.total_return_pct:+.2f}%")
        with a2:
            st.markdown(f"**{attribution.narrative}**")
        with a3:
            pass

        # Factor attribution
        if attribution.factor_details:
            st.markdown("**Factor Attribution:**")
            factor_cols = st.columns(5)
            for i, f in enumerate(attribution.factor_details[:5]):
                with factor_cols[i]:
                    f_color = "green" if f.contribution >= 0 else "red"
                    st.markdown(f":{f_color}[**{f.factor.replace('_', ' ').title()}**]")
                    st.markdown(f"${f.contribution:+,.0f}")

        # Top/bottom contributors
        if attribution.top_contributors or attribution.bottom_contributors:
            st.markdown("")
            tc1, tc2 = st.columns(2)
            with tc1:
                if attribution.top_contributors:
                    st.markdown("**Top Contributors:**")
                    for t in attribution.top_contributors[:3]:
                        t_color = "green" if t.pnl >= 0 else "red"
                        st.markdown(f"- {t.ticker}: :{t_color}[${t.pnl:+,.2f}] ({t.pnl_pct:+.1f}%)")
            with tc2:
                if attribution.bottom_contributors and attribution.bottom_contributors[0].pnl < 0:
                    st.markdown("**Bottom Contributors:**")
                    for b in attribution.bottom_contributors[:3]:
                        b_color = "green" if b.pnl >= 0 else "red"
                        st.markdown(f"- {b.ticker}: :{b_color}[${b.pnl:+,.2f}] ({b.pnl_pct:+.1f}%)")
    else:
        st.markdown("_No performance data for attribution yet_")
except Exception as e:
    st.markdown("_Attribution loading..._")

st.markdown("")


# ─── Pattern Alerts & Learning ───────────────────────────────────────────────
col_alerts, col_pm = st.columns(2)

with col_alerts:
    st.markdown("#### :orange[◆ PATTERN ALERTS]")
    try:
        alerts = get_pattern_alerts()
        if alerts:
            for alert in alerts[:3]:
                level_colors = {"INFO": "blue", "MEDIUM": "orange", "HIGH": "red", "CRITICAL": "red"}
                level_icons = {"INFO": "ℹ️", "MEDIUM": "⚠️", "HIGH": "🔴", "CRITICAL": "🚨"}
                color = level_colors.get(alert.alert_level, "gray")
                icon = level_icons.get(alert.alert_level, "❓")
                st.markdown(f"{icon} :{color}[**{alert.title}**]")
                st.caption(alert.description)
                if alert.recommendation:
                    st.markdown(f"_→ {alert.recommendation}_")
        else:
            st.markdown("_No concerning patterns detected_")
    except Exception:
        st.markdown("_Pattern detection loading..._")

with col_pm:
    st.markdown("#### :orange[◆ RECENT LESSONS]")
    try:
        post_mortems = get_recent_post_mortems(3)
        if post_mortems:
            for pm in reversed(post_mortems):
                pm_color = "green" if pm.pnl >= 0 else "red"
                st.markdown(f"**{pm.ticker}** :{pm_color}[{pm.pnl_pct:+.1f}%] - {pm.exit_reason}")
                st.caption(pm.summary)
                if pm.recommendation:
                    st.markdown(f"_→ {pm.recommendation}_")
        else:
            st.markdown("_No closed trades yet - lessons appear after sells_")
    except Exception:
        st.markdown("_Post-mortems loading..._")

st.markdown("")


# ─── Factor Learning ─────────────────────────────────────────────────────────
st.markdown("#### :orange[◆ FACTOR LEARNING]")
try:
    learner = FactorLearner()
    factor_summary = learner.get_factor_summary()

    if factor_summary["status"] == "ok" and factor_summary["factors"]:
        # Factor performance grid
        fc1, fc2, fc3, fc4, fc5 = st.columns(5)
        factor_cols = [fc1, fc2, fc3, fc4, fc5]

        for i, f in enumerate(factor_summary["factors"][:5]):
            with factor_cols[i]:
                # Trend icons
                trend_icon = {"improving": "▲", "stable": "─", "declining": "▼"}.get(f["trend"], "?")
                trend_color = "green" if f["trend"] == "improving" else ("red" if f["trend"] == "declining" else "orange")

                # Win rate coloring
                wr_color = "green" if f["win_rate"] >= 55 else ("red" if f["win_rate"] < 45 else "orange")

                st.markdown(f"**{f['factor'].replace('_', ' ').title()}**")
                st.markdown(f":{wr_color}[{f['win_rate']:.0f}%] win rate")
                st.markdown(f":{trend_color}[{trend_icon}] {f['trend']}")
                contrib_color = "green" if f["total_contribution"] >= 0 else "red"
                st.markdown(f":{contrib_color}[${f['total_contribution']:+,.0f}]")

        # Weight suggestions
        suggestions = get_weight_suggestions()
        if suggestions:
            st.markdown("")
            st.markdown("**Suggested Weight Adjustments:**")
            for s in suggestions[:3]:
                conf_color = "green" if s.confidence == "HIGH" else ("orange" if s.confidence == "MEDIUM" else "gray")
                change_color = "green" if s.change_pct > 0 else "red"
                st.markdown(
                    f"- **{s.factor.replace('_', ' ').title()}**: "
                    f"{s.current_weight:.0%} → {s.suggested_weight:.0%} "
                    f"(:{change_color}[{s.change_pct:+.1f}%]) "
                    f":{conf_color}[[{s.confidence}]]"
                )
    else:
        st.markdown("_Need more closed trades to analyze factor performance_")
        st.caption("Factor learning becomes active after trades are closed with post-mortems")
except Exception as e:
    st.markdown("_Factor learning loading..._")

st.markdown("")
st.divider()


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

with col_l:
    if st.button("⟳ REFRESH", use_container_width=True):
        st.rerun()

with col_c:
    if st.button("▶ RUN DAILY", use_container_width=True, type="primary"):
        with st.spinner("Running daily workflow... (this may take a few minutes)"):
            try:
                # Get project root directory
                project_root = Path(__file__).parent.parent
                result = subprocess.run(
                    ["bash", "run_daily.sh"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout
                )
                if result.returncode == 0:
                    st.success("Daily run complete!")
                    st.code(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout, language="text")
                    st.rerun()
                else:
                    st.error("Daily run failed!")
                    st.code(result.stderr[-1000:] if result.stderr else result.stdout[-1000:], language="text")
            except subprocess.TimeoutExpired:
                st.error("Daily run timed out (>10 minutes)")
            except Exception as e:
                st.error(f"Error: {e}")

with col_r:
    if st.button("🔍 DISCOVER", use_container_width=True):
        with st.spinner("Discovering new stocks..."):
            try:
                project_root = Path(__file__).parent.parent
                result = subprocess.run(
                    ["python", "scripts/stock_discovery.py"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                if result.returncode == 0:
                    st.success("Discovery complete!")
                    st.code(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout, language="text")
                else:
                    st.error("Discovery failed!")
                    st.code(result.stderr[-1000:] if result.stderr else "No error output", language="text")
            except subprocess.TimeoutExpired:
                st.error("Discovery timed out (>5 minutes)")
            except Exception as e:
                st.error(f"Error: {e}")

st.markdown("<p style='text-align:center; color:#555; font-size:0.7rem; margin-top:24px;'>MOMMY BOT v3.0 | DATA DELAYED | NOT FINANCIAL ADVICE</p>", unsafe_allow_html=True)
