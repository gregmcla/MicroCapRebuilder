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

import httpx
import requests  # used only by sync expiry-loop helper _edit_message_sync
from telegram import BotCommand, Update
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
        # Async http so the asyncio event loop stays responsive — REJECT taps,
        # /status commands, and the expiry loop continue working while execute runs.
        async with httpx.AsyncClient(timeout=300.0) as http:
            resp = await http.post(f"{_API_BASE}/api/{portfolio_id}/execute")
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

def _fmt_dollars(val: float) -> str:
    sign = "+" if val >= 0 else "-"
    abs_val = abs(val)
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{sign}${abs_val / 1_000:.1f}k"
    return f"{sign}${abs_val:.0f}"


def _fmt_pct(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.1f}%"


def _fmt_day(val: float, dollars: float) -> str:
    arrow = "↑" if val >= 0 else "↓"
    return f"{arrow}{_fmt_dollars(dollars)} {_fmt_pct(val)}"


def _build_portfolio_status(portfolio_id: str, state: dict) -> str:
    name = portfolio_id.upper()
    positions = state.get("positions", [])
    cash = state.get("cash", 0) or 0
    pos_value = sum(p.get("market_value", 0) or 0 for p in positions)
    total = pos_value + cash
    day_pnl = sum(p.get("day_change", 0) or 0 for p in positions)
    header = (
        f"📊 {name}\n"
        f"Total ${total:,.0f}  {_fmt_dollars(day_pnl)} today  |  {len(positions)} pos\n"
    )

    if not positions:
        return header + "  (no open positions)\n"

    # Sort by market value descending
    sorted_pos = sorted(positions, key=lambda p: p.get("market_value", 0) or 0, reverse=True)

    lines = ["```"]
    lines.append(f"{'TICKER':<7} {'PRICE':>8}  {'P&L':>13}  {'TODAY':>13}")
    lines.append("─" * 46)
    for p in sorted_pos:
        ticker = (p.get("ticker") or "")[:6]
        price = p.get("current_price") or 0
        pnl_pct = p.get("unrealized_pnl_pct") or 0
        pnl_dollars = p.get("unrealized_pnl") or 0
        day_pct = p.get("day_change_pct") or 0
        day_dollars = p.get("day_change") or 0
        pnl_str = f"{_fmt_dollars(pnl_dollars)} {_fmt_pct(pnl_pct)}"
        day_str = _fmt_day(day_pct, day_dollars)
        lines.append(
            f"{ticker:<7} ${price:>7.2f}  {pnl_str:>13}  {day_str:>13}"
        )
    lines.append("```")
    lines.append(f"Cash ${cash:,.0f}")

    return header + "\n".join(lines)


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Fetching live positions...")

    # One AsyncClient for all calls — connection reuse + non-blocking event loop
    async with httpx.AsyncClient(timeout=60.0) as http:
        try:
            resp = await http.get(f"{_API_BASE}/api/portfolios", timeout=10.0)
            portfolios = resp.json().get("portfolios", [])
            portfolio_ids = [p["id"] for p in portfolios]
        except Exception as exc:
            await msg.edit_text(f"❌ Could not fetch portfolios: {exc}")
            return

        first = True
        for pid in portfolio_ids:
            try:
                state_resp = await http.get(f"{_API_BASE}/api/{pid}/state/refresh")
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
# /scan and /analyze commands (single portfolio at a time)
# ---------------------------------------------------------------------------

async def _fetch_portfolio_ids(http: httpx.AsyncClient) -> list[str]:
    resp = await http.get(f"{_API_BASE}/api/portfolios", timeout=10.0)
    portfolios = resp.json().get("portfolios", [])
    return [p["id"] for p in portfolios]


def _match_portfolio(requested: str, ids: list[str]) -> str | None:
    """Case-insensitive match of a user-typed name against known portfolio ids."""
    req = requested.strip().lower()
    for pid in ids:
        if pid.lower() == req:
            return pid
    return None


async def _resolve_arg(update: Update, http: httpx.AsyncClient, args: list[str], cmd: str) -> str | None:
    """Resolve the portfolio argument. Replies with usage/error and returns None on failure."""
    try:
        ids = await _fetch_portfolio_ids(http)
    except Exception as exc:
        await update.message.reply_text(f"❌ Could not fetch portfolios: {exc}")
        return None
    listing = ", ".join(sorted(ids)) or "(none)"
    if not args:
        await update.message.reply_text(f"Usage: /{cmd} <portfolio>\nPortfolios: {listing}")
        return None
    pid = _match_portfolio(args[0], ids)
    if pid is None:
        await update.message.reply_text(f"❓ Unknown portfolio '{args[0]}'.\nPortfolios: {listing}")
        return None
    return pid


async def handle_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with httpx.AsyncClient(timeout=60.0) as http:
        pid = await _resolve_arg(update, http, context.args, "scan")
        if pid is None:
            return

        msg = await update.message.reply_text(f"⏳ Scanning {pid.upper()}…")
        try:
            resp = await http.post(f"{_API_BASE}/api/{pid}/scan")
            data = resp.json()
        except Exception as exc:
            await msg.edit_text(f"📊 {pid.upper()} · ❌ Scan failed to start: {exc}")
            return

        if data.get("message") == "Scan already in progress":
            await msg.edit_text(
                f"📊 {pid.upper()} · 🔄 A scan is already running — its summary will arrive when it finishes"
            )
            return

        log.info("SCAN started for %s — polling status", pid)
        # Poll until complete/error. The scan API itself sends the detailed
        # watchlist summary on completion, so we just track status here.
        deadline = asyncio.get_event_loop().time() + 780  # > SCAN_TIMEOUT_SECONDS (720)
        while True:
            await asyncio.sleep(5)
            try:
                sresp = await http.get(f"{_API_BASE}/api/{pid}/scan/status")
                status = sresp.json()
            except Exception as exc:
                log.warning("Scan status poll failed for %s: %s", pid, exc)
                if asyncio.get_event_loop().time() > deadline:
                    await msg.edit_text(f"📊 {pid.upper()} · ⏱ Lost track of scan — check back shortly")
                    return
                continue

            st = status.get("status")
            if st == "complete":
                await msg.edit_text(f"📊 {pid.upper()} · ✅ Scan complete — summary below")
                log.info("Scan complete for %s", pid)
                return
            if st == "error":
                err = status.get("error", "unknown error")
                await msg.edit_text(f"📊 {pid.upper()} · ❌ Scan failed — {err}")
                log.error("Scan error for %s: %s", pid, err)
                return
            if asyncio.get_event_loop().time() > deadline:
                await msg.edit_text(f"📊 {pid.upper()} · ⏱ Scan still running — check back shortly")
                return


async def handle_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with httpx.AsyncClient(timeout=300.0) as http:
        pid = await _resolve_arg(update, http, context.args, "analyze")
        if pid is None:
            return

        msg = await update.message.reply_text(
            f"⏳ Analyzing {pid.upper()}… (this can take a minute or two)"
        )
        log.info("ANALYZE started for %s", pid)
        try:
            resp = await http.post(f"{_API_BASE}/api/{pid}/analyze")
        except Exception as exc:
            await msg.edit_text(f"📊 {pid.upper()} · ❌ Analysis failed: {exc}")
            log.error("Analyze exception for %s: %s", pid, exc)
            return

        if resp.status_code != 200:
            await msg.edit_text(
                f"📊 {pid.upper()} · ❌ Analysis failed (HTTP {resp.status_code}) — check logs"
            )
            log.error("Analyze failed for %s: HTTP %s %s", pid, resp.status_code, resp.text[:200])
            return

        approved = (resp.json().get("approved") or [])

    if not approved:
        await msg.edit_text(f"📊 {pid.upper()} · ✅ Analysis complete — no actions proposed")
        log.info("Analyze complete for %s — no actions", pid)
        return

    # send_analysis_proposals is synchronous (uses requests) and sends the
    # proposals message with APPROVE/REJECT buttons + writes the pending file,
    # which handle_callback already acts on. Run it off the event loop.
    try:
        from telegram_notifier import send_analysis_proposals
        await asyncio.to_thread(send_analysis_proposals, pid)
        n = len(approved)
        await msg.edit_text(
            f"📊 {pid.upper()} · ✅ Analysis complete — {n} proposal{'s' if n != 1 else ''} below"
        )
        log.info("Analyze complete for %s — %d proposals sent", pid, n)
    except Exception as exc:
        log.error("send_analysis_proposals failed for %s: %s", pid, exc)
        await msg.edit_text(
            f"📊 {pid.upper()} · ⚠️ Analysis done but could not send proposals — check logs"
        )


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
    try:
        await application.bot.set_my_commands([
            BotCommand("status", "Overview of all portfolios"),
            BotCommand("scan", "Scan a portfolio for new candidates — /scan <portfolio>"),
            BotCommand("analyze", "Analyze a portfolio for trades — /analyze <portfolio>"),
        ])
    except Exception as exc:
        log.warning("Could not set bot command menu: %s", exc)
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
    application.add_handler(CommandHandler("scan", handle_scan))
    application.add_handler(CommandHandler("analyze", handle_analyze))

    log.info("Starting long polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
