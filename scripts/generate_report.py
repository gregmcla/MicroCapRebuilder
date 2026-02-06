#!/usr/bin/env python3
"""
Daily Report Generator for Mommy Bot.

Generates a comprehensive text report with:
- Portfolio summary
- Today's activity
- Performance metrics
- Current positions
- Recent trade history

Usage: python scripts/generate_report.py

Output: reports/daily_report.txt
"""

from datetime import date
from pathlib import Path

import pandas as pd

from analytics import PortfolioAnalytics
from trade_analyzer import TradeAnalyzer
from risk_scoreboard import get_risk_scoreboard
from attribution import get_daily_attribution
from portfolio_state import load_portfolio_state

# ─── Paths ────────────────────────────────────────────────────────────────────
REPORTS_DIR = Path(__file__).parent.parent / "reports"


def get_today_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Filter transactions for today."""
    today = date.today().isoformat()
    return df[df["date"] == today] if not df.empty and "date" in df.columns else pd.DataFrame()


def generate_report() -> str:
    """Generate the daily report text."""
    # Load portfolio state
    state = load_portfolio_state(fetch_prices=False)

    # Extract what we need
    config = state.config
    positions_df = state.positions
    transactions_df = state.transactions
    snapshots_df = state.snapshots
    cash = state.cash
    positions_value = state.positions_value
    total_equity = state.total_equity

    today = date.today().isoformat()
    starting_capital = config.get("starting_capital", 5000.0)
    total_return = ((total_equity - starting_capital) / starting_capital) * 100

    # Get analytics
    analytics = PortfolioAnalytics()
    risk_metrics = analytics.calculate_all_metrics()

    # Get trade stats
    trade_analyzer = TradeAnalyzer()
    trade_stats = trade_analyzer.calculate_trade_stats()

    # Today's activity
    today_txns = get_today_transactions(transactions_df)
    today_buys = today_txns[today_txns["action"] == "BUY"] if not today_txns.empty else pd.DataFrame()
    today_sells = today_txns[today_txns["action"] == "SELL"] if not today_txns.empty else pd.DataFrame()

    # Build report
    lines = []
    lines.append("=" * 60)
    lines.append(f"  MOMMY BOT - DAILY REPORT: {today}")
    lines.append("=" * 60)
    lines.append("")

    # Portfolio Summary
    lines.append("PORTFOLIO SUMMARY")
    lines.append("-" * 40)
    lines.append(f"Total Equity:     ${total_equity:>12,.2f} ({total_return:+.2f}% all-time)")
    lines.append(f"Positions Value:  ${positions_value:>12,.2f} ({positions_value/total_equity*100 if total_equity else 0:.1f}%)")
    lines.append(f"Cash:             ${cash:>12,.2f} ({cash/total_equity*100 if total_equity else 0:.1f}%)")
    lines.append(f"Starting Capital: ${starting_capital:>12,.2f}")
    lines.append("")

    # Today's Activity
    lines.append("TODAY'S ACTIVITY")
    lines.append("-" * 40)
    if today_txns.empty:
        lines.append("  No transactions today")
    else:
        buy_value = today_buys["total_value"].sum() if not today_buys.empty else 0
        sell_value = today_sells["total_value"].sum() if not today_sells.empty else 0
        lines.append(f"Buys:   {len(today_buys):>3} trades  ${buy_value:>10,.2f}")
        lines.append(f"Sells:  {len(today_sells):>3} trades  ${sell_value:>10,.2f}")
    lines.append("")

    # Risk Assessment
    lines.append("RISK ASSESSMENT")
    lines.append("-" * 40)
    try:
        risk = get_risk_scoreboard()
        lines.append(f"Overall Risk Score: {risk.overall_score:.0f}/100 ({risk.risk_level})")
        for c in risk.components:
            status_icon = "✓" if c.status == "OK" else ("⚠" if c.status == "WARNING" else "✗")
            lines.append(f"  {c.name:<15} {c.score:>5.0f}/100 {status_icon}")
        lines.append("")
        lines.append(f"Assessment: {risk.narrative}")
        if risk.recommended_actions:
            lines.append("")
            lines.append("Recommendations:")
            for rec in risk.recommended_actions[:3]:
                lines.append(f"  - {rec}")
    except Exception as e:
        lines.append("  Risk calculation unavailable")
    lines.append("")

    # Performance Attribution (Why Today Happened)
    lines.append("WHY TODAY HAPPENED")
    lines.append("-" * 40)
    try:
        attribution = get_daily_attribution()
        if attribution and (attribution.total_return != 0 or attribution.top_contributors):
            lines.append(f"Day P&L: ${attribution.total_return:+,.2f} ({attribution.total_return_pct:+.2f}%)")
            lines.append("")

            if attribution.factor_details:
                lines.append("Factor Attribution:")
                for f in attribution.factor_details[:5]:
                    sign = "+" if f.contribution >= 0 else ""
                    lines.append(f"  {f.factor:<18} {sign}${f.contribution:>8,.2f}")
                lines.append("")

            if attribution.top_contributors:
                top = attribution.top_contributors[0]
                lines.append(f"Top Contributor:  {top.ticker} ${top.pnl:+,.2f} ({top.pnl_pct:+.1f}%)")

            if attribution.bottom_contributors and attribution.bottom_contributors[0].pnl < 0:
                bottom = attribution.bottom_contributors[0]
                lines.append(f"Bottom:           {bottom.ticker} ${bottom.pnl:+,.2f} ({bottom.pnl_pct:+.1f}%)")

            if attribution.narrative:
                lines.append("")
                lines.append(f"Summary: {attribution.narrative}")
        else:
            lines.append("  No performance data for attribution")
    except Exception as e:
        lines.append("  Attribution calculation unavailable")
    lines.append("")

    # Risk Metrics
    lines.append("PERFORMANCE METRICS")
    lines.append("-" * 40)
    if risk_metrics:
        lines.append(f"Sharpe Ratio:     {risk_metrics.sharpe_ratio:>8.2f}")
        lines.append(f"Sortino Ratio:    {risk_metrics.sortino_ratio:>8.2f}")
        lines.append(f"Max Drawdown:     {risk_metrics.max_drawdown_pct:>7.2f}%")
        lines.append(f"Current Drawdown: {risk_metrics.current_drawdown_pct:>7.2f}%")
        lines.append(f"Annual Volatility:{risk_metrics.volatility_annual:>7.2f}%")
    else:
        lines.append("  Insufficient data for metrics")
    lines.append("")

    # Trade Statistics
    lines.append("TRADE STATISTICS")
    lines.append("-" * 40)
    if trade_stats and trade_stats.total_trades > 0:
        lines.append(f"Total Trades:     {trade_stats.total_trades:>8}")
        lines.append(f"Win Rate:         {trade_stats.win_rate_pct:>7.1f}%")
        lines.append(f"Profit Factor:    {trade_stats.profit_factor:>8.2f}x")
        lines.append(f"Avg Win:          {trade_stats.avg_win_pct:>+7.2f}%")
        lines.append(f"Avg Loss:         {trade_stats.avg_loss_pct:>+7.2f}%")
        lines.append(f"Realized P&L:     ${trade_stats.total_realized_pnl:>+10,.2f}")
    else:
        lines.append(f"  No completed trades yet")
        lines.append(f"  Open positions: {trade_stats.open_positions if trade_stats else len(positions_df)}")
    lines.append("")

    # Current Positions
    lines.append("CURRENT POSITIONS")
    lines.append("-" * 40)
    if positions_df.empty:
        lines.append("  No positions")
    else:
        # Header
        lines.append(f"{'Ticker':<8} {'Shares':>6} {'Cost':>10} {'Current':>10} {'P&L':>10} {'Stop':>8} {'Target':>8}")
        lines.append("-" * 70)

        for _, pos in positions_df.iterrows():
            ticker = pos["ticker"]
            shares = int(pos["shares"])
            cost = pos["avg_cost_basis"]
            current = pos["current_price"]
            pnl_pct = pos["unrealized_pnl_pct"]
            stop = pos.get("stop_loss", "")
            target = pos.get("take_profit", "")

            stop_str = f"${float(stop):.0f}" if stop and str(stop).replace('.','').isdigit() else "-"
            target_str = f"${float(target):.0f}" if target and str(target).replace('.','').isdigit() else "-"

            lines.append(
                f"{ticker:<8} {shares:>6} ${cost:>8.2f} ${current:>8.2f} {pnl_pct:>+8.1f}% {stop_str:>8} {target_str:>8}"
            )
    lines.append("")

    # Recent Trades
    lines.append("RECENT TRADES (Last 5)")
    lines.append("-" * 40)
    if transactions_df.empty:
        lines.append("  No trades yet")
    else:
        recent = transactions_df.tail(5).iloc[::-1]  # Reverse for most recent first
        for _, txn in recent.iterrows():
            action_emoji = "+" if txn["action"] == "BUY" else "-"
            reason = f" ({txn['reason']})" if txn.get("reason") and txn["action"] == "SELL" else ""
            lines.append(
                f"  {txn['date']}  {action_emoji}{txn['action']:<5} {txn['ticker']:<6} "
                f"{int(txn['shares']):>4} @ ${txn['price']:>8.2f}{reason}"
            )
    lines.append("")

    # Footer
    lines.append("=" * 60)
    lines.append(f"  Report generated: {date.today().isoformat()}")
    lines.append("=" * 60)

    return "\n".join(lines)


def save_report(content: str):
    """Save report to file."""
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / "daily_report.txt"
    with open(report_path, "w") as f:
        f.write(content)
    return report_path


def main():
    print("\n─── Generating Daily Report ───\n")

    content = generate_report()

    # Print to console
    print(content)

    # Save to file
    path = save_report(content)
    print(f"\n✅ Report saved to: {path}")


if __name__ == "__main__":
    main()
