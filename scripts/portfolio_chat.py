#!/usr/bin/env python3
"""
Portfolio Chat - AI-powered portfolio analysis assistant.

Uses Claude to answer questions about the portfolio, suggest trades,
and provide insights based on current positions and market conditions.
"""

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import pandas as pd

# Load environment vgscottbles - try multiple paths
def _load_env():
    """Try multiple paths to find and load .env file."""
    try:
        from dotenv import load_dotenv

        # List of paths to try
        paths_to_try = [
            Path(__file__).resolve().parent.parent / ".env",  # scripts/../.env
            Path.cwd() / ".env",  # Current working directory
            Path.home() / "MicroCapRebuilder" / ".env",  # Home directory
            Path("/home/user/MicroCapRebuilder/.env"),  # Absolute fallback
        ]

        for env_path in paths_to_try:
            if env_path.exists():
                load_dotenv(env_path, override=True)
                return str(env_path)

        # Last resort: try default load_dotenv
        load_dotenv(override=True)
        return "default"
    except ImportError:
        return None

_loaded_from = _load_env()

from portfolio_state import load_portfolio_state


@dataclass
class ChatResponse:
    """Response from the portfolio chat."""
    message: str
    success: bool
    error: Optional[str] = None


def get_api_key() -> Optional[str]:
    """Get Anthropic API key from environment."""
    return os.environ.get("ANTHROPIC_API_KEY")


def get_portfolio_context() -> str:
    """Build context about current portfolio state for the AI."""
    state = load_portfolio_state(fetch_prices=False)
    mode = "PAPER TRADING" if state.paper_mode else "LIVE TRADING"

    context_parts = [
        f"# Portfolio Status ({mode})",
        f"Date: {date.today().isoformat()}",
        f"Starting Capital: ${state.config.get('starting_capital', 50000):,.2f}",
        "",
    ]

    # Positions
    if not state.positions.empty:
        total_value = state.positions["market_value"].sum()
        total_pnl = state.positions["unrealized_pnl"].sum()

        context_parts.append("## Current Positions")
        context_parts.append(f"Total Positions: {len(state.positions)}")
        context_parts.append(f"Total Value: ${total_value:,.2f}")
        context_parts.append(f"Unrealized P&L: ${total_pnl:+,.2f}")
        context_parts.append("")
        context_parts.append("| Ticker | Shares | Avg Cost | Current | P&L | P&L % | Stop | Target |")
        context_parts.append("|--------|--------|----------|---------|-----|-------|------|--------|")

        for _, row in state.positions.iterrows():
            context_parts.append(
                f"| {row['ticker']} | {int(row['shares'])} | "
                f"${row['avg_cost_basis']:.2f} | ${row['current_price']:.2f} | "
                f"${row['unrealized_pnl']:+.2f} | {row['unrealized_pnl_pct']:+.1f}% | "
                f"${row.get('stop_loss', 0):.2f} | ${row.get('take_profit', 0):.2f} |"
            )
        context_parts.append("")
    else:
        context_parts.append("## Current Positions")
        context_parts.append("No active positions.")
        context_parts.append("")

    # Cash
    context_parts.append(f"## Cash Available: ${state.cash:,.2f}")
    context_parts.append("")

    # Recent transactions
    if not state.transactions.empty:
        recent = state.transactions.tail(10)
        context_parts.append("## Recent Transactions (last 10)")
        context_parts.append("| Date | Action | Ticker | Shares | Price | Reason |")
        context_parts.append("|------|--------|--------|--------|-------|--------|")
        for _, row in recent.iloc[::-1].iterrows():
            context_parts.append(
                f"| {row['date']} | {row['action']} | {row['ticker']} | "
                f"{int(row['shares'])} | ${row['price']:.2f} | {row.get('reason', '')} |"
            )
        context_parts.append("")

    # Daily performance
    if not state.snapshots.empty:
        latest = state.snapshots.iloc[-1]
        context_parts.append("## Today's Performance")
        context_parts.append(f"Total Equity: ${latest['total_equity']:,.2f}")
        context_parts.append(f"Day P&L: ${latest.get('day_pnl', 0):+,.2f} ({latest.get('day_pnl_pct', 0):+.2f}%)")
        context_parts.append("")

        # Calculate overall return
        starting = state.config.get("starting_capital", 50000)
        total_return = ((latest['total_equity'] - starting) / starting) * 100
        context_parts.append(f"Total Return: {total_return:+.2f}%")
        context_parts.append("")

    # Risk parameters
    context_parts.append("## Risk Parameters")
    context_parts.append(f"Stop Loss: {state.config.get('default_stop_loss_pct', 8)}%")
    context_parts.append(f"Take Profit: {state.config.get('default_take_profit_pct', 20)}%")
    context_parts.append(f"Max Positions: {state.config.get('max_positions', 15)}")
    context_parts.append(f"Risk Per Trade: {state.config.get('risk_per_trade_pct', 10)}%")

    return "\n".join(context_parts)


def get_system_prompt() -> str:
    """Get the system prompt for the portfolio assistant."""
    return """You are GScott's AI assistant - a helpful trading intelligence embedded in an autonomous portfolio management system.

Your role is to:
1. Analyze the portfolio and answer questions about positions, performance, and risk
2. Identify stocks that may need attention (approaching stops, weak performers, etc.)
3. Suggest potential actions based on the data (but always note you're not giving financial advice)
4. Explain trading decisions and portfolio metrics in plain language
5. Be concise and actionable - this is a command center, not a lecture hall

Style guidelines:
- Be direct and concise
- Use bullet points for lists
- Highlight important numbers with context
- If suggesting sells or concerns, explain WHY
- Always remind that these are observations, not financial advice

When analyzing positions:
- Flag positions that are close to stop loss (within 3%)
- Flag positions that are close to take profit (within 5%)
- Note any positions with unusually large gains or losses
- Consider position concentration (any single position > 15% of portfolio)

You have access to the current portfolio data which will be provided with each question."""


def chat(user_message: str) -> ChatResponse:
    """Send a message to the portfolio assistant and get a response."""
    api_key = get_api_key()

    if not api_key:
        return ChatResponse(
            message="",
            success=False,
            error="No Anthropic API key found. Add ANTHROPIC_API_KEY to your .env file."
        )

    try:
        import anthropic
    except ImportError:
        return ChatResponse(
            message="",
            success=False,
            error="anthropic package not installed. Run: pip install anthropic"
        )

    # Build context
    portfolio_context = get_portfolio_context()

    try:
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=get_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": f"""Here is the current portfolio data:

{portfolio_context}

---

User question: {user_message}"""
                }
            ]
        )

        return ChatResponse(
            message=response.content[0].text,
            success=True
        )

    except anthropic.APIError as e:
        return ChatResponse(
            message="",
            success=False,
            error=f"API error: {str(e)}"
        )
    except Exception as e:
        return ChatResponse(
            message="",
            success=False,
            error=f"Error: {str(e)}"
        )


def check_setup() -> tuple[bool, str]:
    """Check if chat is properly configured."""
    # Re-load env in case it wasn't loaded at import time
    loaded_from = _load_env()

    api_key = get_api_key()

    if not api_key:
        # Provide helpful error message
        expected_path = Path(__file__).resolve().parent.parent / ".env"
        return False, f"No ANTHROPIC_API_KEY found. Add it to: {expected_path}"

    try:
        import anthropic
        return True, "Ready"
    except ImportError:
        return False, "anthropic package not installed"


# Quick test
if __name__ == "__main__":
    ready, status = check_setup()
    print(f"Chat status: {status}")

    if ready:
        print("\nPortfolio context:")
        print(get_portfolio_context())

        print("\n" + "─" * 50)
        response = chat("Give me a quick summary of my portfolio health.")
        if response.success:
            print(response.message)
        else:
            print(f"Error: {response.error}")
