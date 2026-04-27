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
