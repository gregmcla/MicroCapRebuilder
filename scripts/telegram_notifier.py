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


# ---------------------------------------------------------------------------
# Scan summary
# ---------------------------------------------------------------------------

def _build_scan_message(stats_map: dict, failed: list, elapsed_seconds: float) -> str:
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
        lines += [f"{pid.upper()} ({pid})  ⚠️ scan failed", ""]
    mins = int(elapsed_seconds // 60)
    secs = int(elapsed_seconds % 60)
    elapsed_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
    total_count = len(stats_map) + len(failed)
    lines.append(f"{total_count} portfolio{'s' if total_count != 1 else ''} · {elapsed_str}")
    return "\n".join(lines).strip()


def send_scan_summary(ok_portfolios: list, failed_portfolios: list) -> None:
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
    s = _get_portfolio_stats(portfolio_id)
    if not s:
        return
    wl_file = _PORTFOLIOS_DIR / portfolio_id / "watchlist.jsonl"
    s["new_tickers"] = _get_new_tickers_today(wl_file)
    stats_map = {portfolio_id: s}
    text = _build_scan_message(stats_map, failed=[], elapsed_seconds=0)
    _send_message(text)


# ---------------------------------------------------------------------------
# Analysis proposals
# ---------------------------------------------------------------------------

def _get_sell_enrichment(state, ticker: str) -> dict:
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
        return {"days_held": days_held, "return_pct": return_pct, "return_dollars": return_dollars}
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
        lines.append(f"SELLS ({len(sells)})")
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
    lines.append(f"Today: {_fmt_pct(intraday_pct)} ({_fmt_dollar(intraday_dollars)}) vs yesterday's close")
    return "\n".join(lines).strip()


def _write_pending(portfolio_id: str, message_id: int, expires_at: datetime) -> None:
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
    try:
        expires = datetime.fromisoformat(pending["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires
    except Exception:
        return True


def send_analysis_proposals(portfolio_id: str) -> None:
    analysis_file = _PORTFOLIOS_DIR / portfolio_id / ".last_analysis.json"
    if not analysis_file.exists():
        log.warning("No analysis file for %s", portfolio_id)
        return
    with open(analysis_file) as f:
        result = json.load(f)
    approved = result.get("approved", [])
    if not approved:
        return
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


# ---------------------------------------------------------------------------
# Update snapshot + CLI
# ---------------------------------------------------------------------------

def _build_update_snapshot_message(stats_map: dict, failed: list, label: str) -> str:
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
    stats_map: dict = {}
    for pid in ok_portfolios:
        s = _get_portfolio_stats(pid)
        if s:
            stats_map[pid] = s
    label = datetime.now().strftime("%-I:%M %p update")
    text = _build_update_snapshot_message(stats_map, failed=failed_portfolios, label=label)
    _send_message(text)


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description="GScott Telegram Notifier")
    sub = parser.add_subparsers(dest="command", required=True)
    p_scan = sub.add_parser("scan-summary")
    p_scan.add_argument("--ok", default="")
    p_scan.add_argument("--failed", default="")
    p_proposals = sub.add_parser("proposals")
    p_proposals.add_argument("--portfolio", required=True)
    p_update = sub.add_parser("update-snapshot")
    p_update.add_argument("--ok", default="")
    p_update.add_argument("--failed", default="")
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
