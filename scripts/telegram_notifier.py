#!/usr/bin/env python3
"""
Telegram notification sender for GScott trading system.
Send-only module. Does NOT handle incoming callbacks — that's telegram_bot.py.
"""
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

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

log = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
_PENDING_DIR = _PROJECT_ROOT / "data" / "telegram" / "pending"
_PORTFOLIOS_DIR = _PROJECT_ROOT / "data" / "portfolios"


def _fmt_dollar(n: float) -> str:
    sign = "+" if n >= 0 else "-"
    return f"{sign}${abs(int(n)):,}"


def _fmt_pct(n: float) -> str:
    sign = "+" if n >= 0 else "-"
    return f"{sign}{abs(n):.2f}%"


def _send_message(text: str, reply_markup: Optional[dict] = None) -> Optional[int]:
    """POST sendMessage. Returns message_id or None on failure/unconfigured."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return None
    payload: dict = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    url = _TELEGRAM_API.format(token=token, method="sendMessage")
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.ok:
                return resp.json()["result"]["message_id"]
            log.warning("Telegram sendMessage %s: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            log.warning("Telegram sendMessage attempt %d failed: %s", attempt + 1, exc)
        if attempt < 2:
            time.sleep(2 ** attempt)
    return None


def _edit_message(message_id: int, text: str, remove_buttons: bool = True) -> None:
    """Edit an existing message. Optionally clears inline keyboard."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    payload: dict = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if remove_buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": []})
    url = _TELEGRAM_API.format(token=token, method="editMessageText")
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as exc:
        log.warning("Telegram editMessageText failed: %s", exc)
