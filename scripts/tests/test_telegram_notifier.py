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


# Task 3: portfolio stats helpers

def test_get_new_tickers_today(tmp_path):
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
    from telegram_notifier import _get_new_tickers_today
    result = _get_new_tickers_today(tmp_path / "missing.jsonl")
    assert result == []


# Task 4: scan summary

def test_build_scan_message_contains_portfolio_names():
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
    from telegram_notifier import _build_scan_message
    msg = _build_scan_message({}, failed=["bad-portfolio"], elapsed_seconds=10)
    assert "bad-portfolio" in msg
    assert "failed" in msg.lower()


# Task 5: analysis proposals

def test_build_proposals_message_buy():
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
    import importlib
    import telegram_notifier as tn
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
    from telegram_notifier import _is_expired
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    assert _is_expired({"expires_at": past}) is True


def test_is_expired_false():
    from telegram_notifier import _is_expired
    future = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    assert _is_expired({"expires_at": future}) is False


# Task 6: update snapshot

def test_build_update_snapshot_message():
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
