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
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

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

    log.info("Starting long polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
