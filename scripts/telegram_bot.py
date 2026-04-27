#!/usr/bin/env python3
"""
GScott Telegram Bot — long-running async process.

Handles APPROVE/REJECT callback queries from analysis proposal messages.
On APPROVE: calls the local FastAPI execute endpoint with fresh prices.
On REJECT: edits message to rejected state, cleans up pending file.
Background task checks for expired pending approvals every 60s.

Start: python3 scripts/telegram_bot.py
Monitor: checked by cron/api_watchdog.sh every 15 min
Logs: cron/logs/telegram_bot.log
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from dotenv import load_dotenv
    for _env in [_PROJECT_ROOT / ".env", Path.cwd() / ".env"]:
        if _env.exists():
            load_dotenv(_env, override=True)
            break
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_PENDING_DIR = _PROJECT_ROOT / "data" / "telegram" / "pending"
_API_BASE = os.getenv("GSCOTT_API_URL", "http://localhost:8001")


# ---------------------------------------------------------------------------
# Pending file helpers
# ---------------------------------------------------------------------------

def _load_pending(portfolio_id: str) -> dict | None:
    f = _PENDING_DIR / f"{portfolio_id}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except Exception as exc:
        log.warning("Could not read pending file for %s: %s", portfolio_id, exc)
        return None


def _delete_pending(portfolio_id: str) -> None:
    (_PENDING_DIR / f"{portfolio_id}.json").unlink(missing_ok=True)


def _is_expired(pending: dict) -> bool:
    try:
        expires = datetime.fromisoformat(pending["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires
    except Exception as exc:
        log.warning("Could not parse expires_at from pending record: %s", exc)
        return True


def _all_pending() -> list[dict]:
    _PENDING_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for f in _PENDING_DIR.glob("*.json"):
        if f.name == ".gitkeep":
            continue
        try:
            results.append(json.loads(f.read_text()))
        except Exception as exc:
            log.warning("Could not read pending file %s: %s", f.name, exc)
    return results


# ---------------------------------------------------------------------------
# Telegram edit helper (sync, for use in expiry loop)
# ---------------------------------------------------------------------------

def _edit_message_sync(message_id: int, chat_id: str, text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": json.dumps({"inline_keyboard": []}),
            },
            timeout=10,
        )
    except Exception as exc:
        log.warning("_edit_message_sync failed: %s", exc)


# ---------------------------------------------------------------------------
# Callback handler
# ---------------------------------------------------------------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if ":" not in data:
        return

    action, portfolio_id = data.split(":", 1)

    if action == "reject":
        _delete_pending(portfolio_id)
        await query.edit_message_text(f"📊 {portfolio_id.upper()} · ❌ Rejected")
        log.info("REJECT received for %s", portfolio_id)
        return

    if action != "approve":
        return

    # APPROVE
    pending = _load_pending(portfolio_id)
    if pending is None:
        await query.edit_message_text(f"📊 {portfolio_id.upper()} · ⏱ Already expired or rejected")
        return

    if _is_expired(pending):
        _delete_pending(portfolio_id)
        await query.edit_message_text(f"📊 {portfolio_id.upper()} · ⏱ Expired — no trades fired")
        return

    # Delete pending BEFORE executing to prevent double-execute on re-tap
    _delete_pending(portfolio_id)

    await query.edit_message_text(f"📊 {portfolio_id.upper()} · ⏳ Executing...")
    log.info("APPROVE received for %s — calling execute endpoint", portfolio_id)

    try:
        resp = requests.post(
            f"{_API_BASE}/api/{portfolio_id}/execute",
            timeout=300,
        )
        if resp.status_code == 200:
            data_resp = resp.json()
            executed = data_resp.get("executed", {})
            buys = executed.get("buys", 0)
            sells = executed.get("sells", 0)
            now_str = datetime.now().strftime("%-I:%M %p")
            parts = []
            if buys:
                parts.append(f"{buys} buy{'s' if buys != 1 else ''}")
            if sells:
                parts.append(f"{sells} sell{'s' if sells != 1 else ''}")
            trade_str = " · ".join(parts) if parts else "0 trades"
            await query.edit_message_text(
                f"📊 {portfolio_id.upper()} · ✅ Executed — {trade_str} at {now_str}"
            )
            log.info("Execute OK for %s: %s", portfolio_id, trade_str)
        else:
            log.error(
                "Execute failed for %s: HTTP %s %s",
                portfolio_id, resp.status_code, resp.text[:200],
            )
            await query.edit_message_text(
                f"📊 {portfolio_id.upper()} · ❌ Execute failed (HTTP {resp.status_code}) — check logs"
            )
    except Exception as exc:
        log.error("Execute exception for %s: %s", portfolio_id, exc)
        await query.edit_message_text(
            f"📊 {portfolio_id.upper()} · ❌ Execute failed — check logs"
        )


# ---------------------------------------------------------------------------
# /status command
# ---------------------------------------------------------------------------

def _fmt_pnl(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.1f}%"


def _fmt_day(val: float) -> str:
    arrow = "↑" if val >= 0 else "↓"
    sign = "+" if val >= 0 else ""
    return f"{arrow}{sign}{val:.1f}%"


def _build_portfolio_status(portfolio_id: str, state: dict) -> str:
    name = portfolio_id.upper()
    positions = state.get("positions", [])
    cash = state.get("cash", 0) or 0
    pos_value = sum(p.get("market_value", 0) or 0 for p in positions)
    total = pos_value + cash
    day_pnl = sum(p.get("day_change", 0) or 0 for p in positions)
    day_sign = "+" if day_pnl >= 0 else ""

    header = (
        f"📊 {name}\n"
        f"Total ${total:,.0f}  {day_sign}${day_pnl:,.0f} today  |  {len(positions)} pos\n"
    )

    if not positions:
        return header + "  (no open positions)\n"

    # Sort by market value descending
    sorted_pos = sorted(positions, key=lambda p: p.get("market_value", 0) or 0, reverse=True)

    lines = ["```"]
    lines.append(f"{'TICKER':<7} {'PRICE':>8} {'P&L%':>7} {'TODAY':>7}")
    lines.append("─" * 33)
    for p in sorted_pos:
        ticker = (p.get("ticker") or "")[:6]
        price = p.get("current_price") or 0
        pnl_pct = p.get("unrealized_pnl_pct") or 0
        day_pct = p.get("day_change_pct") or 0
        lines.append(
            f"{ticker:<7} ${price:>7.2f} {_fmt_pnl(pnl_pct):>7} {_fmt_day(day_pct):>7}"
        )
    lines.append("```")
    lines.append(f"Cash ${cash:,.0f}")

    return header + "\n".join(lines)


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Fetching live positions...")

    try:
        resp = requests.get(f"{_API_BASE}/api/portfolios", timeout=10)
        portfolios = resp.json().get("portfolios", [])
        portfolio_ids = [p["id"] for p in portfolios]
    except Exception as exc:
        await msg.edit_text(f"❌ Could not fetch portfolios: {exc}")
        return

    first = True
    for pid in portfolio_ids:
        try:
            state_resp = requests.get(f"{_API_BASE}/api/{pid}/state", timeout=30)
            state = state_resp.json()
        except Exception as exc:
            log.warning("Could not fetch state for %s: %s", pid, exc)
            continue

        text = _build_portfolio_status(pid, state)
        if first:
            await msg.edit_text(text, parse_mode="Markdown")
            first = False
        else:
            await update.message.reply_text(text, parse_mode="Markdown")

    if first:
        await msg.edit_text("No portfolio data available.")


# ---------------------------------------------------------------------------
# Expiry background task
# ---------------------------------------------------------------------------

async def _expiry_loop() -> None:
    while True:
        await asyncio.sleep(60)
        for pending in _all_pending():
            if _is_expired(pending):
                pid = pending.get("portfolio_id", "")
                mid = pending.get("message_id")
                chat_id = pending.get("chat_id", os.getenv("TELEGRAM_CHAT_ID", ""))
                log.info("Expiring pending approval for %s (message_id=%s)", pid, mid)
                if mid and chat_id:
                    _edit_message_sync(
                        mid, chat_id,
                        f"📊 {pid.upper()} · ⏱ Expired — no trades fired",
                    )
                _delete_pending(pid)


async def _post_init(application: Application) -> None:
    asyncio.create_task(_expiry_loop())
    log.info("GScott Telegram Bot started. Expiry loop active.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        log.error("TELEGRAM_BOT_TOKEN not set — exiting")
        sys.exit(1)

    application = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .build()
    )
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(CommandHandler("status", handle_status))

    log.info("Starting long polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
