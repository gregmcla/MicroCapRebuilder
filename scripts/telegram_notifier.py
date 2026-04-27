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


# ---------------------------------------------------------------------------
# Portfolio stats helpers
# ---------------------------------------------------------------------------

def _get_new_tickers_today(watchlist_file: Path) -> list:
    if not watchlist_file.exists():
        return []
    today = date.today().isoformat()
    result = []
    try:
        with open(watchlist_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("added_date", "") == today and entry.get("status", "ACTIVE") == "ACTIVE":
                    result.append(entry["ticker"])
    except Exception as exc:
        log.warning("Error reading watchlist %s: %s", watchlist_file, exc)
    return result


def _get_portfolio_stats(portfolio_id: str) -> Optional[dict]:
    """Load portfolio state and return stats dict for notifications."""
    try:
        from portfolio_state import load_portfolio_state
        state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)
        starting_capital = state.config.get("starting_capital", 0) or 0
        equity = state.total_equity
        total_return_dollars = equity - starting_capital
        total_return_pct = (total_return_dollars / starting_capital * 100) if starting_capital > 0 else 0.0
        intraday_dollars = 0.0
        if not state.positions.empty and "day_change" in state.positions.columns:
            intraday_dollars = float(state.positions["day_change"].sum())
        prev_equity = equity - intraday_dollars
        intraday_pct = (intraday_dollars / prev_equity * 100) if prev_equity > 0 else 0.0
        wl_file = _PORTFOLIOS_DIR / portfolio_id / "watchlist.jsonl"
        watchlist_size = 0
        if wl_file.exists():
            with open(wl_file) as f:
                watchlist_size = sum(
                    1 for line in f
                    if line.strip() and json.loads(line).get("status", "ACTIVE") == "ACTIVE"
                )
        return {
            "equity": equity,
            "positions_count": state.num_positions,
            "total_return_pct": total_return_pct,
            "total_return_dollars": total_return_dollars,
            "intraday_pct": intraday_pct,
            "intraday_dollars": intraday_dollars,
            "watchlist_size": watchlist_size,
        }
    except Exception as exc:
        log.warning("Failed to get stats for %s: %s", portfolio_id, exc)
        return None
