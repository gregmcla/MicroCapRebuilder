# Telegram Bot Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Telegram bot that sends scan summaries, position snapshots, and analysis proposals with APPROVE/REJECT buttons — all trades require explicit confirmation before execution.

**Architecture:** A lightweight `telegram_notifier.py` module (uses `requests`, called by cron scripts) handles outbound messages. A separate long-running `telegram_bot.py` process (uses `python-telegram-bot` v20, async long polling) handles incoming button taps and calls the local FastAPI execute endpoint on APPROVE. Pending approvals are tracked as JSON files in `data/telegram/pending/`.

**Tech Stack:** `python-telegram-bot==20.*`, `requests` (already installed), FastAPI (already running), asyncio

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `scripts/telegram_notifier.py` | Send-only: build messages, POST to Telegram Bot API, write pending files |
| Create | `scripts/telegram_bot.py` | Long-running bot: callback handler, expiry loop, execute-on-approve |
| Create | `cron/analyze.sh` | Cron: call analyze API per portfolio, then send proposals |
| Modify | `cron/scan.sh` | Add scan summary notification after scan loop |
| Modify | `cron/update.sh` | Add portfolio snapshot notification after update loop |
| Modify | `cron/api_watchdog.sh` | Add bot process health check + restart |
| Modify | `api/routes/discovery.py` | Send single-portfolio scan notification after dashboard SCAN completes |
| Modify | `.gitignore` | Add `data/telegram/` |
| Modify | `crontab` | Swap `execute.sh` → `analyze.sh` at 9:35 AM |
| Create | `scripts/tests/test_telegram_notifier.py` | Unit tests for message builders and pending file logic |

---

## Task 1: Install dependency and configure environment

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Install python-telegram-bot**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
pip install "python-telegram-bot[job-queue]==20.*"
pip freeze | grep telegram
```

Expected output includes: `python-telegram-bot==20.x.x`

- [ ] **Step 2: Add data/telegram/ to .gitignore**

Add this line to `.gitignore` (after the `data/pipeline_status/` line):

```
data/telegram/
```

- [ ] **Step 3: Create data/telegram/pending/ directory with a .gitkeep**

```bash
mkdir -p data/telegram/pending
touch data/telegram/pending/.gitkeep
```

- [ ] **Step 4: Document required .env variables**

Add these three lines to `.env` (with your actual values):

```
TELEGRAM_BOT_TOKEN=<token from @BotFather>
TELEGRAM_CHAT_ID=<your numeric chat ID>
TELEGRAM_APPROVAL_TIMEOUT_MINUTES=60
```

To get your chat ID: message your bot once, then run:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool | grep '"id"' | head -5
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore data/telegram/pending/.gitkeep
git commit -m "chore: add python-telegram-bot dep, gitignore data/telegram/"
```

---

## Task 2: `scripts/telegram_notifier.py` — core helpers

**Files:**
- Create: `scripts/telegram_notifier.py`

- [ ] **Step 1: Write failing tests for core helpers**

Create `scripts/tests/test_telegram_notifier.py`:

```python
"""Tests for telegram_notifier message builders and helpers."""
import sys
import json
import os
import tempfile
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_fmt_dollar_positive():
    from telegram_notifier import _fmt_dollar
    assert _fmt_dollar(14800) == "+$14,800"


def test_fmt_dollar_negative():
    from telegram_notifier import _fmt_dollar
    assert _fmt_dollar(-2300) == "-$2,300"


def test_fmt_dollar_zero():
    from telegram_notifier import _fmt_dollar
    assert _fmt_dollar(0) == "+$0"


def test_fmt_pct_positive():
    from telegram_notifier import _fmt_pct
    assert _fmt_pct(1.23) == "+1.23%"


def test_fmt_pct_negative():
    from telegram_notifier import _fmt_pct
    assert _fmt_pct(-0.82) == "-0.82%"


def test_send_message_skips_when_no_token(monkeypatch):
    """send_message returns None silently when TELEGRAM_BOT_TOKEN is unset."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    from telegram_notifier import _send_message
    result = _send_message("test")
    assert result is None


def test_send_message_returns_message_id_on_success(monkeypatch):
    """_send_message returns message_id from Telegram response."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"result": {"message_id": 42}}
    with patch("requests.post", return_value=mock_resp):
        from telegram_notifier import _send_message
        result = _send_message("hello")
        assert result == 42
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
python3 -m pytest scripts/tests/test_telegram_notifier.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'telegram_notifier'`

- [ ] **Step 3: Create `scripts/telegram_notifier.py` with core helpers**

```python
#!/usr/bin/env python3
"""
Telegram notification sender for GScott trading system.

Send-only module. Call from cron scripts or API routes.
Does NOT handle incoming callbacks — that's telegram_bot.py.

Usage (CLI):
    python3 scripts/telegram_notifier.py scan-summary --ok "max gov-infra" --failed ""
    python3 scripts/telegram_notifier.py proposals --portfolio max
    python3 scripts/telegram_notifier.py update-snapshot --ok "max gov-infra"
    python3 scripts/telegram_notifier.py single-scan --portfolio max
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

# ── Path setup (allow import from scripts/ when called from project root) ────
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ── Load .env ─────────────────────────────────────────────────────────────────
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


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt_dollar(n: float) -> str:
    sign = "+" if n >= 0 else "-"
    return f"{sign}${abs(int(n)):,}"


def _fmt_pct(n: float) -> str:
    sign = "+" if n >= 0 else "-"
    return f"{sign}{abs(n):.2f}%"


# ── Low-level Telegram HTTP ───────────────────────────────────────────────────

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
```

- [ ] **Step 4: Run tests — core helpers should pass**

```bash
python3 -m pytest scripts/tests/test_telegram_notifier.py -v 2>&1 | head -30
```

Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/telegram_notifier.py scripts/tests/test_telegram_notifier.py
git commit -m "feat: telegram_notifier core helpers and send primitives"
```

---

## Task 3: `telegram_notifier.py` — portfolio stats helper

**Files:**
- Modify: `scripts/telegram_notifier.py`
- Modify: `scripts/tests/test_telegram_notifier.py`

- [ ] **Step 1: Write failing tests for portfolio stats**

Append to `scripts/tests/test_telegram_notifier.py`:

```python
def test_get_new_tickers_today(tmp_path):
    """_get_new_tickers_today returns tickers added today."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    watchlist = [
        {"ticker": "NVDA", "added_date": today, "status": "ACTIVE"},
        {"ticker": "AMD", "added_date": today, "status": "ACTIVE"},
        {"ticker": "INTC", "added_date": yesterday, "status": "ACTIVE"},
        {"ticker": "OLD", "added_date": today, "status": "STALE"},
    ]
    wl_file = tmp_path / "watchlist.jsonl"
    wl_file.write_text("\n".join(json.dumps(e) for e in watchlist))

    from telegram_notifier import _get_new_tickers_today
    result = _get_new_tickers_today(wl_file)
    assert set(result) == {"NVDA", "AMD"}


def test_get_new_tickers_today_empty_file(tmp_path):
    """Returns empty list when watchlist file does not exist."""
    from telegram_notifier import _get_new_tickers_today
    result = _get_new_tickers_today(tmp_path / "missing.jsonl")
    assert result == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
python3 -m pytest scripts/tests/test_telegram_notifier.py::test_get_new_tickers_today -v
```

Expected: `ImportError` — `_get_new_tickers_today` not defined yet.

- [ ] **Step 3: Add `_get_new_tickers_today` and `_get_portfolio_stats` to `telegram_notifier.py`**

Append after `_edit_message` in `scripts/telegram_notifier.py`:

```python
# ── Portfolio data helpers ────────────────────────────────────────────────────

def _get_new_tickers_today(watchlist_file: Path) -> list:
    """Return tickers added today from a watchlist.jsonl file."""
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
    """
    Load portfolio state and return stats dict for notifications.

    Returns:
        {equity, positions_count, total_return_pct, total_return_dollars,
         intraday_pct, intraday_dollars, watchlist_size}
        or None on failure.
    """
    try:
        from portfolio_state import load_portfolio_state
        state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)

        starting_capital = state.config.get("starting_capital", 0) or 0
        equity = state.total_equity

        # Total return vs starting capital
        total_return_dollars = equity - starting_capital
        total_return_pct = (total_return_dollars / starting_capital * 100) if starting_capital > 0 else 0.0

        # Intraday change: sum of position-level day_change (dollars)
        intraday_dollars = 0.0
        if not state.positions.empty and "day_change" in state.positions.columns:
            intraday_dollars = float(state.positions["day_change"].sum())
        prev_equity = equity - intraday_dollars
        intraday_pct = (intraday_dollars / prev_equity * 100) if prev_equity > 0 else 0.0

        # Watchlist size
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
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest scripts/tests/test_telegram_notifier.py -v 2>&1 | tail -15
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/telegram_notifier.py scripts/tests/test_telegram_notifier.py
git commit -m "feat: telegram_notifier portfolio stats and new-ticker helpers"
```

---

## Task 4: `telegram_notifier.py` — scan summary

**Files:**
- Modify: `scripts/telegram_notifier.py`
- Modify: `scripts/tests/test_telegram_notifier.py`

- [ ] **Step 1: Write failing tests for scan summary**

Append to `scripts/tests/test_telegram_notifier.py`:

```python
def test_build_scan_message_contains_portfolio_names():
    """Scan summary includes each portfolio name."""
    from telegram_notifier import _build_scan_message
    stats_map = {
        "max": {
            "equity": 1_240_000, "positions_count": 8,
            "total_return_pct": 12.3, "total_return_dollars": 136_000,
            "intraday_pct": 0.82, "intraday_dollars": 10_100,
            "watchlist_size": 47, "new_tickers": ["NVDA", "AMD", "INTC"],
        },
        "gov-infra": {
            "equity": 284_000, "positions_count": 5,
            "total_return_pct": 4.1, "total_return_dollars": 11_000,
            "intraday_pct": -0.3, "intraday_dollars": -850,
            "watchlist_size": 38, "new_tickers": ["GD"],
        },
    }
    msg = _build_scan_message(stats_map, failed=[], elapsed_seconds=134)
    assert "MAX" in msg
    assert "GOV-INFRA" in msg
    assert "NVDA" in msg
    assert "+0.82%" in msg
    assert "2m 14s" in msg


def test_build_scan_message_no_new_tickers():
    """Shows 'no change' when no new tickers."""
    from telegram_notifier import _build_scan_message
    stats_map = {
        "max": {
            "equity": 1_000_000, "positions_count": 5,
            "total_return_pct": 0.0, "total_return_dollars": 0,
            "intraday_pct": 0.0, "intraday_dollars": 0,
            "watchlist_size": 40, "new_tickers": [],
        },
    }
    msg = _build_scan_message(stats_map, failed=[], elapsed_seconds=60)
    assert "no change" in msg


def test_build_scan_message_failed_portfolio():
    """Failed portfolios show warning in message."""
    from telegram_notifier import _build_scan_message
    msg = _build_scan_message({}, failed=["bad-portfolio"], elapsed_seconds=10)
    assert "bad-portfolio" in msg
    assert "failed" in msg.lower()
```

- [ ] **Step 2: Run to confirm failures**

```bash
python3 -m pytest scripts/tests/test_telegram_notifier.py::test_build_scan_message_contains_portfolio_names -v
```

Expected: `ImportError` — `_build_scan_message` not defined.

- [ ] **Step 3: Add `_build_scan_message` and `send_scan_summary` to `telegram_notifier.py`**

Append to `scripts/telegram_notifier.py`:

```python
# ── Scan summary ──────────────────────────────────────────────────────────────

def _build_scan_message(
    stats_map: dict,
    failed: list,
    elapsed_seconds: float,
) -> str:
    """Build consolidated scan summary message text."""
    now = datetime.now()
    dow = now.strftime("%a")
    ts = now.strftime("%b %-d, %-I:%M %p")
    lines = [f"Scan Complete — {dow} {ts}", ""]

    for portfolio_id, s in stats_map.items():
        new = s.get("new_tickers", [])
        new_str = f"  +{len(new)} new  " + " · ".join(new[:5]) if new else "  no change"
        watchlist_str = f"Watchlist: {s['watchlist_size']}{new_str}"
        equity_str = f"${s['equity']:,.0f} equity"
        total_str = f"total {_fmt_pct(s['total_return_pct'])} ({_fmt_dollar(s['total_return_dollars'])})"
        intraday_str = f"Today: {_fmt_pct(s['intraday_pct'])} ({_fmt_dollar(s['intraday_dollars'])}) vs yesterday's close"
        lines += [
            portfolio_id.upper(),
            f"  {watchlist_str}",
            f"  {s['positions_count']} positions · {equity_str} · {total_str}",
            f"  {intraday_str}",
            "",
        ]

    for pid in failed:
        lines += [f"{pid.upper()}  ⚠️ scan failed", ""]

    mins = int(elapsed_seconds // 60)
    secs = int(elapsed_seconds % 60)
    elapsed_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
    total_count = len(stats_map) + len(failed)
    lines.append(f"{total_count} portfolio{'s' if total_count != 1 else ''} · {elapsed_str}")
    return "\n".join(lines).strip()


def send_scan_summary(ok_portfolios: list, failed_portfolios: list) -> None:
    """Fetch stats for each portfolio and send consolidated scan message."""
    import time as _time
    start = _time.monotonic()

    stats_map: dict = {}
    for pid in ok_portfolios:
        s = _get_portfolio_stats(pid)
        if s:
            wl_file = _PORTFOLIOS_DIR / pid / "watchlist.jsonl"
            s["new_tickers"] = _get_new_tickers_today(wl_file)
            stats_map[pid] = s

    elapsed = _time.monotonic() - start
    text = _build_scan_message(stats_map, failed=failed_portfolios, elapsed_seconds=elapsed)
    _send_message(text)


def send_single_portfolio_scan(portfolio_id: str, scan_stats: Optional[dict] = None) -> None:
    """Send scan notification for a single portfolio (dashboard-triggered scans)."""
    s = _get_portfolio_stats(portfolio_id)
    if not s:
        return
    wl_file = _PORTFOLIOS_DIR / portfolio_id / "watchlist.jsonl"
    s["new_tickers"] = _get_new_tickers_today(wl_file)
    stats_map = {portfolio_id: s}
    text = _build_scan_message(stats_map, failed=[], elapsed_seconds=0)
    _send_message(text)
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest scripts/tests/test_telegram_notifier.py -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/telegram_notifier.py scripts/tests/test_telegram_notifier.py
git commit -m "feat: telegram_notifier scan summary builder"
```

---

## Task 5: `telegram_notifier.py` — analysis proposals

**Files:**
- Modify: `scripts/telegram_notifier.py`
- Modify: `scripts/tests/test_telegram_notifier.py`

- [ ] **Step 1: Write failing tests for proposals**

Append to `scripts/tests/test_telegram_notifier.py`:

```python
def test_build_proposals_message_buy():
    """Proposal message includes BUY ticker with score and reasoning."""
    from telegram_notifier import _build_proposals_message
    approved = [
        {
            "original": {
                "action_type": "BUY",
                "ticker": "NVDA",
                "total_value": 2500.0,
                "quant_score": 78.0,
                "reason": "SIGNAL",
            },
            "ai_reasoning": "breakout momentum",
            "decision": "APPROVE",
        }
    ]
    msg = _build_proposals_message(
        portfolio_id="max",
        approved=approved,
        sell_enrichment={},
        cash_after=142500,
        regime="BULL",
        ai_mode="claude",
        intraday_pct=0.82,
        intraday_dollars=10100,
        expires_at=datetime(2026, 4, 28, 10, 35),
    )
    assert "NVDA" in msg
    assert "$2,500" in msg
    assert "78" in msg
    assert "BUYS (1)" in msg


def test_build_proposals_message_sell_enrichment():
    """Proposal message includes days_held and return for sells."""
    from telegram_notifier import _build_proposals_message
    approved = [
        {
            "original": {
                "action_type": "SELL",
                "ticker": "INTC",
                "shares": 50,
                "price": 66.78,
                "reason": "STOP_LOSS",
            },
            "ai_reasoning": "stop triggered",
            "decision": "APPROVE",
        }
    ]
    sell_enrichment = {
        "INTC": {"days_held": 14, "return_pct": -8.2, "return_dollars": -1240}
    }
    msg = _build_proposals_message(
        portfolio_id="max",
        approved=approved,
        sell_enrichment=sell_enrichment,
        cash_after=142500,
        regime="BULL",
        ai_mode="claude",
        intraday_pct=0.82,
        intraday_dollars=10100,
        expires_at=datetime(2026, 4, 28, 10, 35),
    )
    assert "INTC" in msg
    assert "14d" in msg
    assert "-8.20%" in msg


def test_write_and_read_pending_file(tmp_path):
    """Pending file is written correctly and can be read back."""
    import importlib
    import telegram_notifier as tn
    # Override pending dir to tmp
    original = tn._PENDING_DIR
    tn._PENDING_DIR = tmp_path

    expires = datetime(2026, 4, 28, 10, 35, tzinfo=timezone.utc)
    tn._write_pending("max", message_id=99, expires_at=expires)

    pending_file = tmp_path / "max.json"
    assert pending_file.exists()
    data = json.loads(pending_file.read_text())
    assert data["portfolio_id"] == "max"
    assert data["message_id"] == 99

    tn._PENDING_DIR = original


def test_is_expired_true():
    """_is_expired returns True when expires_at is in the past."""
    from telegram_notifier import _is_expired
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    assert _is_expired({"expires_at": past}) is True


def test_is_expired_false():
    """_is_expired returns False when expires_at is in the future."""
    from telegram_notifier import _is_expired
    future = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    assert _is_expired({"expires_at": future}) is False
```

- [ ] **Step 2: Run to confirm failures**

```bash
python3 -m pytest scripts/tests/test_telegram_notifier.py::test_build_proposals_message_buy -v
```

Expected: `ImportError` — `_build_proposals_message` not defined.

- [ ] **Step 3: Add proposals functions to `telegram_notifier.py`**

Append to `scripts/telegram_notifier.py`:

```python
# ── Analysis proposals ────────────────────────────────────────────────────────

def _get_sell_enrichment(state, ticker: str) -> dict:
    """Return days_held, return_pct, return_dollars for a held position."""
    try:
        if state.positions.empty:
            return {}
        row = state.positions[state.positions["ticker"] == ticker]
        if row.empty:
            return {}
        r = row.iloc[0]
        entry_date = r.get("entry_date", "")
        avg_cost = float(r.get("avg_cost_basis", 0) or 0)
        current_price = float(r.get("current_price", 0) or 0)
        shares = float(r.get("shares", 0) or 0)

        days_held = 0
        if entry_date:
            try:
                from datetime import date as _date
                d = _date.fromisoformat(str(entry_date)[:10])
                days_held = (_date.today() - d).days
            except Exception:
                pass

        return_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0
        return_dollars = (current_price - avg_cost) * shares

        return {
            "days_held": days_held,
            "return_pct": return_pct,
            "return_dollars": return_dollars,
        }
    except Exception:
        return {}


def _build_proposals_message(
    portfolio_id: str,
    approved: list,
    sell_enrichment: dict,
    cash_after: float,
    regime: str,
    ai_mode: str,
    intraday_pct: float,
    intraday_dollars: float,
    expires_at: datetime,
) -> str:
    """Build per-portfolio analysis proposal message text."""
    buys = [a for a in approved if a.get("original", {}).get("action_type") == "BUY"]
    sells = [a for a in approved if a.get("original", {}).get("action_type") == "SELL"]

    now_str = datetime.now().strftime("%-I:%M %p")
    expires_str = expires_at.strftime("%-I:%M %p")
    mode_str = "AI mode" if ai_mode == "claude" else "mechanical"

    lines = [
        f"{portfolio_id.upper()} · {regime} · {mode_str}",
        f"Analyzed {now_str} · expires {expires_str}",
        "",
    ]

    if buys:
        lines.append(f"BUYS ({len(buys)})")
        for a in buys:
            orig = a["original"]
            ticker = orig.get("ticker", "?")
            value = orig.get("total_value", 0) or 0
            score = orig.get("quant_score", 0) or 0
            reasoning = (a.get("ai_reasoning") or orig.get("reason", ""))[:60]
            lines.append(f"  {ticker:<8} ${value:,.0f}   score {score:.0f}   {reasoning}")
        lines.append("")

    if sells:
        lines.append(f"SELLS ({len(len(sells))})")
        for a in sells:
            orig = a["original"]
            ticker = orig.get("ticker", "?")
            reason = orig.get("reason", "SIGNAL").replace("_", " ").lower()
            enr = sell_enrichment.get(ticker, {})
            days = enr.get("days_held", 0)
            ret_pct = enr.get("return_pct", 0.0)
            ret_dollars = enr.get("return_dollars", 0.0)
            hold_str = f"held {days}d" if days else ""
            ret_str = f"{_fmt_pct(ret_pct)} ({_fmt_dollar(ret_dollars)})"
            suffix = f"   {hold_str} · {ret_str}" if hold_str else f"   {ret_str}"
            lines.append(f"  {ticker:<8} 100%   {reason}{suffix}")
        lines.append("")

    lines.append(f"Cash after: ${cash_after:,.0f}")
    intraday_str = f"Today: {_fmt_pct(intraday_pct)} ({_fmt_dollar(intraday_dollars)}) vs yesterday's close"
    lines.append(intraday_str)

    return "\n".join(lines).strip()


def _write_pending(portfolio_id: str, message_id: int, expires_at: datetime) -> None:
    """Write pending approval state file."""
    _PENDING_DIR.mkdir(parents=True, exist_ok=True)
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    data = {
        "portfolio_id": portfolio_id,
        "message_id": message_id,
        "chat_id": chat_id,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    (_PENDING_DIR / f"{portfolio_id}.json").write_text(json.dumps(data))


def _is_expired(pending: dict) -> bool:
    """Return True if the pending approval has passed its expires_at."""
    try:
        expires = datetime.fromisoformat(pending["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires
    except Exception:
        return True


def send_analysis_proposals(portfolio_id: str) -> None:
    """
    Read .last_analysis.json for portfolio_id, build proposal message,
    send with APPROVE/REJECT buttons, write pending file.
    Sends nothing if there are no approved actions.
    """
    analysis_file = _PORTFOLIOS_DIR / portfolio_id / ".last_analysis.json"
    if not analysis_file.exists():
        log.warning("No analysis file for %s", portfolio_id)
        return

    with open(analysis_file) as f:
        result = json.load(f)

    approved = result.get("approved", [])
    if not approved:
        return

    # Sell enrichment (days held + return)
    try:
        from portfolio_state import load_portfolio_state
        state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)
        sell_enrichment = {}
        for a in approved:
            orig = a.get("original", {})
            if orig.get("action_type") == "SELL":
                ticker = orig.get("ticker", "")
                if ticker:
                    sell_enrichment[ticker] = _get_sell_enrichment(state, ticker)

        intraday_dollars = 0.0
        if not state.positions.empty and "day_change" in state.positions.columns:
            intraday_dollars = float(state.positions["day_change"].sum())
        prev_equity = state.total_equity - intraday_dollars
        intraday_pct = (intraday_dollars / prev_equity * 100) if prev_equity > 0 else 0.0
        cash_after = state.cash
    except Exception as exc:
        log.warning("Could not load state for enrichment: %s", exc)
        sell_enrichment = {}
        intraday_pct = 0.0
        intraday_dollars = 0.0
        cash_after = 0.0

    timeout_minutes = int(os.getenv("TELEGRAM_APPROVAL_TIMEOUT_MINUTES", "60"))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)

    text = _build_proposals_message(
        portfolio_id=portfolio_id,
        approved=approved,
        sell_enrichment=sell_enrichment,
        cash_after=cash_after,
        regime=result.get("regime", "UNKNOWN"),
        ai_mode=result.get("ai_mode", "unknown"),
        intraday_pct=intraday_pct,
        intraday_dollars=intraday_dollars,
        expires_at=expires_at,
    )

    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ APPROVE", "callback_data": f"approve:{portfolio_id}"},
            {"text": "❌ REJECT", "callback_data": f"reject:{portfolio_id}"},
        ]]
    }

    message_id = _send_message(text, reply_markup=reply_markup)
    if message_id:
        _write_pending(portfolio_id, message_id, expires_at)
```

- [ ] **Step 4: Fix the typo in sells count line**

Find this line in the function just added:
```python
        lines.append(f"SELLS ({len(len(sells))})")
```

Replace with:
```python
        lines.append(f"SELLS ({len(sells)})")
```

- [ ] **Step 5: Run tests**

```bash
python3 -m pytest scripts/tests/test_telegram_notifier.py -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/telegram_notifier.py scripts/tests/test_telegram_notifier.py
git commit -m "feat: telegram_notifier analysis proposals with pending file"
```

---

## Task 6: `telegram_notifier.py` — update snapshot + CLI

**Files:**
- Modify: `scripts/telegram_notifier.py`

- [ ] **Step 1: Write failing test for update snapshot**

Append to `scripts/tests/test_telegram_notifier.py`:

```python
def test_build_update_snapshot_message():
    """Update snapshot message includes equity and intraday for each portfolio."""
    from telegram_notifier import _build_update_snapshot_message
    stats_map = {
        "max": {
            "equity": 1_240_000, "positions_count": 8,
            "total_return_pct": 12.3, "total_return_dollars": 136_000,
            "intraday_pct": 1.2, "intraday_dollars": 14_800,
        },
    }
    msg = _build_update_snapshot_message(stats_map, failed=[], label="4:15 PM update")
    assert "MAX" in msg
    assert "+1.20%" in msg
    assert "4:15 PM update" in msg
```

- [ ] **Step 2: Run to confirm failure**

```bash
python3 -m pytest scripts/tests/test_telegram_notifier.py::test_build_update_snapshot_message -v
```

- [ ] **Step 3: Add update snapshot and CLI to `telegram_notifier.py`**

Append to `scripts/telegram_notifier.py`:

```python
# ── Update snapshot ───────────────────────────────────────────────────────────

def _build_update_snapshot_message(stats_map: dict, failed: list, label: str) -> str:
    """Build portfolio update snapshot message text."""
    now_str = datetime.now().strftime("%-I:%M %p")
    dow = datetime.now().strftime("%a %b %-d")
    lines = [f"Portfolio Update — {dow}, {now_str}", ""]

    for portfolio_id, s in stats_map.items():
        equity_str = f"${s['equity']:,.0f} equity"
        total_str = f"total {_fmt_pct(s['total_return_pct'])} ({_fmt_dollar(s['total_return_dollars'])})"
        intraday_str = f"Today: {_fmt_pct(s['intraday_pct'])} ({_fmt_dollar(s['intraday_dollars'])}) vs yesterday's close"
        lines += [
            portfolio_id.upper(),
            f"  {s['positions_count']} positions · {equity_str} · {total_str}",
            f"  {intraday_str}",
            "",
        ]

    for pid in failed:
        lines += [f"{pid.upper()}  ⚠️ update failed", ""]

    total_count = len(stats_map) + len(failed)
    lines.append(f"{total_count} portfolio{'s' if total_count != 1 else ''} · {label}")
    return "\n".join(lines).strip()


def send_update_snapshot(ok_portfolios: list, failed_portfolios: list) -> None:
    """Fetch stats for each portfolio and send update snapshot message."""
    stats_map: dict = {}
    for pid in ok_portfolios:
        s = _get_portfolio_stats(pid)
        if s:
            stats_map[pid] = s

    label = datetime.now().strftime("%-I:%M %p update")
    text = _build_update_snapshot_message(stats_map, failed=failed_portfolios, label=label)
    _send_message(text)


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="GScott Telegram Notifier")
    sub = parser.add_subparsers(dest="command", required=True)

    # scan-summary
    p_scan = sub.add_parser("scan-summary")
    p_scan.add_argument("--ok", default="", help="Space-separated list of OK portfolio IDs")
    p_scan.add_argument("--failed", default="", help="Space-separated list of failed portfolio IDs")

    # proposals
    p_proposals = sub.add_parser("proposals")
    p_proposals.add_argument("--portfolio", required=True)

    # update-snapshot
    p_update = sub.add_parser("update-snapshot")
    p_update.add_argument("--ok", default="")
    p_update.add_argument("--failed", default="")

    # single-scan (dashboard-triggered)
    p_single = sub.add_parser("single-scan")
    p_single.add_argument("--portfolio", required=True)

    args = parser.parse_args()

    if args.command == "scan-summary":
        ok = [p for p in args.ok.split() if p]
        failed = [p for p in args.failed.split() if p]
        send_scan_summary(ok, failed)

    elif args.command == "proposals":
        send_analysis_proposals(args.portfolio)

    elif args.command == "update-snapshot":
        ok = [p for p in args.ok.split() if p]
        failed = [p for p in args.failed.split() if p]
        send_update_snapshot(ok, failed)

    elif args.command == "single-scan":
        send_single_portfolio_scan(args.portfolio)
```

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest scripts/tests/test_telegram_notifier.py -v 2>&1 | tail -25
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/telegram_notifier.py scripts/tests/test_telegram_notifier.py
git commit -m "feat: telegram_notifier update snapshot and CLI entrypoint"
```

---

## Task 7: `scripts/telegram_bot.py`

**Files:**
- Create: `scripts/telegram_bot.py`

- [ ] **Step 1: Create `scripts/telegram_bot.py`**

```python
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

# ── Path + env ────────────────────────────────────────────────────────────────
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


# ── Pending file helpers ──────────────────────────────────────────────────────

def _load_pending(portfolio_id: str) -> dict | None:
    f = _PENDING_DIR / f"{portfolio_id}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except Exception:
        return None


def _delete_pending(portfolio_id: str) -> None:
    (_PENDING_DIR / f"{portfolio_id}.json").unlink(missing_ok=True)


def _is_expired(pending: dict) -> bool:
    try:
        expires = datetime.fromisoformat(pending["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires
    except Exception:
        return True


def _all_pending() -> list[dict]:
    _PENDING_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for f in _PENDING_DIR.glob("*.json"):
        if f.name == ".gitkeep":
            continue
        try:
            results.append(json.loads(f.read_text()))
        except Exception:
            pass
    return results


# ── Telegram edit helper (sync, for use in expiry loop) ──────────────────────

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
        log.warning("edit_message_sync failed: %s", exc)


# ── Callback handler ──────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if ":" not in data:
        return

    action, portfolio_id = data.split(":", 1)

    if action == "reject":
        _delete_pending(portfolio_id)
        await query.edit_message_text(f"{portfolio_id.upper()} · ❌ Rejected")
        log.info("REJECT received for %s", portfolio_id)
        return

    if action != "approve":
        return

    # ── APPROVE ──────────────────────────────────────────────────────────────
    pending = _load_pending(portfolio_id)
    if pending is None:
        await query.edit_message_text(f"{portfolio_id.upper()} · ⏱ Already expired or rejected")
        return

    if _is_expired(pending):
        _delete_pending(portfolio_id)
        await query.edit_message_text(f"{portfolio_id.upper()} · ⏱ Expired — no trades fired")
        return

    # Delete pending file BEFORE executing to prevent double-execute on re-tap
    _delete_pending(portfolio_id)

    await query.edit_message_text(f"{portfolio_id.upper()} · ⏳ Executing...")
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
                f"{portfolio_id.upper()} · ✅ Executed — {trade_str} at {now_str}"
            )
            log.info("Execute OK for %s: %s", portfolio_id, trade_str)
        else:
            log.error("Execute failed for %s: HTTP %s %s", portfolio_id, resp.status_code, resp.text[:200])
            await query.edit_message_text(
                f"{portfolio_id.upper()} · ❌ Execute failed (HTTP {resp.status_code}) — check logs"
            )
    except Exception as exc:
        log.error("Execute exception for %s: %s", portfolio_id, exc)
        await query.edit_message_text(
            f"{portfolio_id.upper()} · ❌ Execute failed — check logs"
        )


# ── Expiry background task ────────────────────────────────────────────────────

async def _expiry_loop() -> None:
    """Check for expired pending approvals every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        for pending in _all_pending():
            if _is_expired(pending):
                pid = pending.get("portfolio_id", "")
                mid = pending.get("message_id")
                chat_id = pending.get("chat_id", os.getenv("TELEGRAM_CHAT_ID", ""))
                log.info("Expiring pending approval for %s (message_id=%s)", pid, mid)
                if mid and chat_id:
                    _edit_message_sync(mid, chat_id, f"{pid.upper()} · ⏱ Expired — no trades fired")
                _delete_pending(pid)


async def _post_init(application: Application) -> None:
    asyncio.create_task(_expiry_loop())
    log.info("GScott Telegram Bot started. Expiry loop active.")


# ── Main ──────────────────────────────────────────────────────────────────────

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
```

- [ ] **Step 2: Smoke-test the bot (dry run — no Telegram connection)**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
python3 -c "import telegram_bot; print('import ok')" 2>&1
```

Expected: `import ok` (no errors)

- [ ] **Step 3: Verify bot starts with a real token (if configured)**

If `.env` has `TELEGRAM_BOT_TOKEN` set:
```bash
timeout 5 python3 scripts/telegram_bot.py 2>&1 || true
```

Expected output includes `Starting long polling...` before timeout. If `TELEGRAM_BOT_TOKEN not set`, that's fine — will test once token is configured.

- [ ] **Step 4: Commit**

```bash
git add scripts/telegram_bot.py
git commit -m "feat: telegram_bot long-polling process with APPROVE/REJECT handler"
```

---

## Task 8: Modify `cron/scan.sh`

**Files:**
- Modify: `cron/scan.sh`

- [ ] **Step 1: Update `cron/scan.sh` to collect per-portfolio results and send notification**

Replace the existing `cron/scan.sh` with:

```bash
#!/usr/bin/env bash
# Pre-market discovery scan — refreshes all active portfolio watchlists
# Scheduled: 6:30 AM ET, Monday–Friday via crontab
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/scan_$(date +%Y%m%d)_$$.log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=========================================="
log "PRE-MARKET SCAN START"
log "=========================================="

cd "$DIR"
source .venv/bin/activate
export DISABLE_SOCIAL=true

if [ -f .env ]; then
    set -a; source .env; set +a
fi

PORTFOLIOS=$(python3 scripts/list_portfolios.py 2>>"$LOG")
if [ -z "$PORTFOLIOS" ]; then
    log "ERROR: list_portfolios.py returned no portfolios -- aborting"
    exit 1
fi

COUNT=0
FAILED=0
PORTFOLIOS_OK=""
PORTFOLIOS_FAILED=""

for PORTFOLIO in $PORTFOLIOS; do
    log "Scanning: $PORTFOLIO"
    if python3 scripts/watchlist_manager.py --update --portfolio "$PORTFOLIO" >> "$LOG" 2>&1; then
        log "  ok: $PORTFOLIO"
        COUNT=$((COUNT + 1))
        PORTFOLIOS_OK="$PORTFOLIOS_OK $PORTFOLIO"
    else
        log "  FAILED: $PORTFOLIO (continuing)"
        FAILED=$((FAILED + 1))
        PORTFOLIOS_FAILED="$PORTFOLIOS_FAILED $PORTFOLIO"
    fi
done

log "=========================================="
log "SCAN COMPLETE -- $COUNT ok, $FAILED failed"
log "=========================================="

# Send Telegram scan summary (non-fatal)
PORTFOLIOS_OK="${PORTFOLIOS_OK# }"
PORTFOLIOS_FAILED="${PORTFOLIOS_FAILED# }"
python3 scripts/telegram_notifier.py scan-summary \
    --ok "$PORTFOLIOS_OK" \
    --failed "$PORTFOLIOS_FAILED" >> "$LOG" 2>&1 || true
```

- [ ] **Step 2: Verify script is executable**

```bash
chmod +x /Users/gregmclaughlin/MicroCapRebuilder/cron/scan.sh
bash -n /Users/gregmclaughlin/MicroCapRebuilder/cron/scan.sh
```

Expected: no output (syntax OK).

- [ ] **Step 3: Commit**

```bash
git add cron/scan.sh
git commit -m "feat: scan.sh sends Telegram summary after scan loop"
```

---

## Task 9: Create `cron/analyze.sh`

**Files:**
- Create: `cron/analyze.sh`

This script replaces `execute.sh` in the cron schedule. It calls the analyze API endpoint (which writes `.last_analysis.json`), then sends proposal messages. It does NOT execute trades.

- [ ] **Step 1: Create `cron/analyze.sh`**

```bash
#!/usr/bin/env bash
# Market-open analyze — AI allocation dry run, sends Telegram proposals for approval
# Scheduled: 9:35 AM ET, Monday–Friday via crontab
# Execution is triggered by user tapping APPROVE in Telegram, not this script.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/analyze_$(date +%Y%m%d)_$$.log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# Belt-and-suspenders: skip weekends
DOW=$(date +%u)
if [ "$DOW" -ge 6 ]; then
    log "Weekend detected -- skipping"
    exit 0
fi

log "=========================================="
log "MARKET-OPEN ANALYZE START"
log "=========================================="

cd "$DIR"
source .venv/bin/activate
export DISABLE_SOCIAL=true

if [ -f .env ]; then
    set -a; source .env; set +a
fi

PORTFOLIOS=$(python3 scripts/list_portfolios.py 2>>"$LOG")
if [ -z "$PORTFOLIOS" ]; then
    log "ERROR: list_portfolios.py returned no portfolios -- aborting"
    exit 1
fi

COUNT=0
FAILED=0

for PORTFOLIO in $PORTFOLIOS; do
    log "Analyzing: $PORTFOLIO"

    # Call the analyze API endpoint — writes .last_analysis.json, returns HTTP 200 on success
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "http://localhost:8001/api/$PORTFOLIO/analyze" \
        --max-time 300 2>>"$LOG")

    if [ "$HTTP_STATUS" -eq 200 ] 2>/dev/null; then
        log "  analysis ok: $PORTFOLIO (HTTP $HTTP_STATUS)"
        COUNT=$((COUNT + 1))
        # Send Telegram proposal message (non-fatal — if no proposals, sends nothing)
        python3 scripts/telegram_notifier.py proposals \
            --portfolio "$PORTFOLIO" >> "$LOG" 2>&1 || true
    else
        log "  FAILED: $PORTFOLIO (HTTP $HTTP_STATUS)"
        FAILED=$((FAILED + 1))
    fi
done

log "=========================================="
log "ANALYZE COMPLETE -- $COUNT ok, $FAILED failed"
log "=========================================="
```

- [ ] **Step 2: Make executable and validate syntax**

```bash
chmod +x /Users/gregmclaughlin/MicroCapRebuilder/cron/analyze.sh
bash -n /Users/gregmclaughlin/MicroCapRebuilder/cron/analyze.sh
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add cron/analyze.sh
git commit -m "feat: analyze.sh dry-run analysis + Telegram proposals (no auto-execute)"
```

---

## Task 10: Modify `cron/update.sh`

**Files:**
- Modify: `cron/update.sh`

- [ ] **Step 1: Update `cron/update.sh` to collect results and send snapshot**

Replace the existing `cron/update.sh` with:

```bash
#!/usr/bin/env bash
# Position update + factor learning — runs at noon and post-close
# Scheduled: 12:00 PM ET and 4:15 PM ET, Monday–Friday via crontab
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/update_$(date +%Y%m%d)_$$.log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=========================================="
log "POSITION UPDATE START"
log "=========================================="

cd "$DIR"
source .venv/bin/activate
export DISABLE_SOCIAL=true

if [ -f .env ]; then
    set -a; source .env; set +a
fi

PORTFOLIOS=$(python3 scripts/list_portfolios.py 2>>"$LOG")
if [ -z "$PORTFOLIOS" ]; then
    log "ERROR: list_portfolios.py returned no portfolios -- aborting"
    exit 1
fi

PORTFOLIOS_OK=""
PORTFOLIOS_FAILED=""

for PORTFOLIO in $PORTFOLIOS; do
    log "Updating: $PORTFOLIO"
    if python3 scripts/update_positions.py --portfolio "$PORTFOLIO" >> "$LOG" 2>&1; then
        PORTFOLIOS_OK="$PORTFOLIOS_OK $PORTFOLIO"
        python3 scripts/factor_learning.py --portfolio "$PORTFOLIO" >> "$LOG" 2>&1 || true
    else
        log "  FAILED: update_positions for $PORTFOLIO"
        PORTFOLIOS_FAILED="$PORTFOLIOS_FAILED $PORTFOLIO"
    fi
done

log "=========================================="
log "UPDATE COMPLETE"
log "=========================================="

# Send Telegram portfolio snapshot (non-fatal)
PORTFOLIOS_OK="${PORTFOLIOS_OK# }"
PORTFOLIOS_FAILED="${PORTFOLIOS_FAILED# }"
python3 scripts/telegram_notifier.py update-snapshot \
    --ok "$PORTFOLIOS_OK" \
    --failed "$PORTFOLIOS_FAILED" >> "$LOG" 2>&1 || true
```

- [ ] **Step 2: Validate**

```bash
chmod +x /Users/gregmclaughlin/MicroCapRebuilder/cron/update.sh
bash -n /Users/gregmclaughlin/MicroCapRebuilder/cron/update.sh
```

- [ ] **Step 3: Commit**

```bash
git add cron/update.sh
git commit -m "feat: update.sh sends Telegram portfolio snapshot after update"
```

---

## Task 11: Extend `cron/api_watchdog.sh` to monitor the bot

**Files:**
- Modify: `cron/api_watchdog.sh`

- [ ] **Step 1: Add bot process check to `cron/api_watchdog.sh`**

Append these lines just before the final `fi` of the existing watchdog (after the API restart check):

```bash
# ── Telegram bot watchdog ─────────────────────────────────────────────────────
BOT_LOG="$DIR/cron/logs/telegram_bot.log"

if ! pgrep -f "telegram_bot.py" > /dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Telegram bot down -- restarting..." >> "$LOG"

    cd "$DIR"
    source .venv/bin/activate
    if [ -f .env ]; then
        set -a; source .env; set +a
    fi

    nohup python3 scripts/telegram_bot.py >> "$BOT_LOG" 2>&1 &
    sleep 5

    if pgrep -f "telegram_bot.py" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Telegram bot restarted OK" >> "$LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Telegram bot restart FAILED" >> "$LOG"
    fi
fi
```

The full modified `cron/api_watchdog.sh` should look like this:

```bash
#!/usr/bin/env bash
# API health check + Telegram bot watchdog
# Scheduled: every 15 minutes via crontab

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$DIR/cron/logs/api_watchdog.log"
mkdir -p "$(dirname "$LOG")"

HEALTH=$(curl -s --max-time 5 http://localhost:8001/api/health 2>/dev/null || echo "")

if [[ "$HEALTH" == *'"status":"ok"'* ]]; then
    :
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] API down -- restarting..." >> "$LOG"

    cd "$DIR"
    source .venv/bin/activate

    if [ -f .env ]; then
        set -a; source .env; set +a
    fi

    pkill -f "uvicorn api.main:app" 2>/dev/null || true
    sleep 1

    DISABLE_SOCIAL=true nohup uvicorn api.main:app --host 0.0.0.0 --port 8001 \
        >> "$LOG" 2>&1 &

    sleep 8
    HEALTH=$(curl -s --max-time 5 http://localhost:8001/api/health 2>/dev/null || echo "")
    if [[ "$HEALTH" == *'"status":"ok"'* ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] API restarted OK" >> "$LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] API restart FAILED" >> "$LOG"
    fi
fi

# ── Telegram bot watchdog ─────────────────────────────────────────────────────
BOT_LOG="$DIR/cron/logs/telegram_bot.log"

if ! pgrep -f "telegram_bot.py" > /dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Telegram bot down -- restarting..." >> "$LOG"

    cd "$DIR"
    source .venv/bin/activate
    if [ -f .env ]; then
        set -a; source .env; set +a
    fi

    nohup python3 scripts/telegram_bot.py >> "$BOT_LOG" 2>&1 &
    sleep 5

    if pgrep -f "telegram_bot.py" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Telegram bot restarted OK" >> "$LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Telegram bot restart FAILED" >> "$LOG"
    fi
fi
```

- [ ] **Step 2: Validate syntax**

```bash
bash -n /Users/gregmclaughlin/MicroCapRebuilder/cron/api_watchdog.sh
```

- [ ] **Step 3: Commit**

```bash
git add cron/api_watchdog.sh
git commit -m "feat: api_watchdog.sh monitors and restarts telegram_bot.py"
```

---

## Task 12: `api/routes/discovery.py` — send notification after dashboard scan

**Files:**
- Modify: `api/routes/discovery.py`

The dashboard SCAN button hits `POST /api/{portfolio_id}/scan`. The scan runs in a background thread (`_run_scan_job`). After it completes successfully, send a single-portfolio Telegram notification.

- [ ] **Step 1: Add notification call to `_run_scan_job` in `api/routes/discovery.py`**

Find the block in `_run_scan_job` that sets `job["status"] = "complete"`:

```python
                job["status"] = "complete"
                job["result"] = stats
```

Add the notification call immediately after:

```python
                job["status"] = "complete"
                job["result"] = stats

                # Send Telegram notification (non-fatal — dashboard scans are single-portfolio)
                try:
                    from telegram_notifier import send_single_portfolio_scan
                    send_single_portfolio_scan(portfolio_id, stats)
                except Exception:
                    pass
```

- [ ] **Step 2: Restart the API and verify no import errors**

```bash
curl -s http://localhost:8001/api/health
```

Expected: `{"status":"ok"}`

If the API is not running:
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && \
DISABLE_SOCIAL=true uvicorn api.main:app --host 0.0.0.0 --port 8001 &
sleep 3 && curl -s http://localhost:8001/api/health
```

- [ ] **Step 3: Commit**

```bash
git add api/routes/discovery.py
git commit -m "feat: discovery.py sends Telegram notification after dashboard scan"
```

---

## Task 13: Update crontab to add analyze.sh

**Files:**
- Modify: crontab (via `crontab -e` or direct edit)

- [ ] **Step 1: View current crontab**

```bash
crontab -l
```

You will see the paused entries. The current 9:35 AM execute line is:
```
# PAUSED 2026-04-03: 35 9 * * 1-5 /Users/gregmclaughlin/MicroCapRebuilder/cron/execute.sh
```

- [ ] **Step 2: Add analyze.sh entry (keep execute.sh commented)**

Run:
```bash
(crontab -l; echo "# Market-open analyze + Telegram proposals (9:35 AM ET, Mon-Fri)") | crontab -
(crontab -l; echo "# PAUSED: 35 9 * * 1-5 /Users/gregmclaughlin/MicroCapRebuilder/cron/analyze.sh") | crontab -
```

Or open with `EDITOR=nano crontab -e` and add after the existing execute.sh comment:
```
# Market-open analyze + Telegram proposals (9:35 AM ET, Mon-Fri)
# PAUSED: 35 9 * * 1-5 /Users/gregmclaughlin/MicroCapRebuilder/cron/analyze.sh
```

The cron remains paused until you explicitly re-enable it. When you're ready to re-enable, uncomment the scan, analyze, and update lines (remove `# PAUSED:` prefix).

- [ ] **Step 3: Verify crontab looks right**

```bash
crontab -l
```

Expected: analyze.sh entry present, all trading crons still commented out.

- [ ] **Step 4: Commit crontab backup**

```bash
crontab -l > /Users/gregmclaughlin/MicroCapRebuilder/cron/crontab_backup_$(date +%Y%m%d).txt
git add cron/crontab_backup_*.txt
git commit -m "chore: update crontab backup with analyze.sh entry"
```

---

## Task 14: Manual smoke test

Once `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set in `.env`:

- [ ] **Step 1: Start the bot manually**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate && source .env
python3 scripts/telegram_bot.py &
BOT_PID=$!
sleep 3
echo "Bot PID: $BOT_PID"
```

- [ ] **Step 2: Send a test scan summary**

```bash
python3 scripts/telegram_notifier.py scan-summary --ok "max" --failed ""
```

Expected: Telegram message arrives with MAX stats.

- [ ] **Step 3: Send a test analysis proposal (requires a prior analyze run)**

First trigger an analyze via the API:
```bash
curl -s -X POST http://localhost:8001/api/max/analyze > /dev/null
python3 scripts/telegram_notifier.py proposals --portfolio max
```

Expected: Telegram message arrives with MAX proposals and APPROVE/REJECT buttons. If no proposals, nothing is sent (correct behavior).

- [ ] **Step 4: Send a test update snapshot**

```bash
python3 scripts/telegram_notifier.py update-snapshot --ok "max" --failed ""
```

Expected: Telegram snapshot message arrives.

- [ ] **Step 5: Test APPROVE flow (paper mode — safe)**

If proposals were sent in Step 3, tap APPROVE in Telegram. Expected sequence:
1. Message edits to `MAX · ⏳ Executing...`
2. Within 30–90s, message edits to `MAX · ✅ Executed — N buys/sells at HH:MM`

- [ ] **Step 6: Stop the bot and verify watchdog would restart it**

```bash
kill $BOT_PID
pgrep -f telegram_bot.py  # should be empty
bash /Users/gregmclaughlin/MicroCapRebuilder/cron/api_watchdog.sh
sleep 6
pgrep -f telegram_bot.py  # should be non-empty
```

- [ ] **Step 7: Final commit**

```bash
git add -u
git commit -m "feat: Telegram bot notifications complete — scan/analyze/update + APPROVE/REJECT"
git push
```

---

## Self-Review Checklist

**Spec requirement coverage:**

| Requirement | Task |
|-------------|------|
| Scan → summary notification | Tasks 4, 8 |
| Analysis → proposals with APPROVE/REJECT | Tasks 5, 9 |
| Update → snapshot notification | Tasks 6, 10 |
| All trades require confirmation | Task 7 (bot never auto-executes) |
| REJECT = silent skip | Task 7 (`handle_callback`) |
| 60-min expiry | Tasks 5 (`_write_pending`), 7 (`_expiry_loop`) |
| Bot monitors via watchdog | Task 11 |
| Dashboard SCAN sends notification | Task 12 |
| Intraday delta in all messages | Tasks 3, 4, 6 |
| Sell enrichment (days held + return) | Task 5 (`_get_sell_enrichment`) |
| data/telegram/ gitignored | Task 1 |
| Fresh prices on execute | Task 7 (calls `/execute` endpoint which re-runs analysis) |
| Error handling / non-fatal | All cron tasks use `|| true`; bot has try/except around all external calls |
