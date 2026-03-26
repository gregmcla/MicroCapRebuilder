"""Tests for scripts/log_parser.py — parse cron log files into structured data."""
import csv
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "cron_logs"
PORTFOLIOS_FIXTURES = Path(__file__).parent / "fixtures" / "portfolios"

# Import from scripts/
from log_parser import (
    parse_scan_execute_log,
    parse_update_log,
    parse_watchdog_log,
    count_trades_for_date,
    build_day_summary,
)


def test_parse_scan_execute_log_ok():
    """Execute log with all ok → status ok, correct counts."""
    result = parse_scan_execute_log(FIXTURES / "execute_20260326_12345.log")
    assert result["status"] == "ok"
    assert result["ok"] == 2
    assert result["failed"] == 0
    assert result["ran_at"] == "09:37"


def test_parse_scan_execute_log_with_failures():
    """Scan log with some failures → status failed, correct counts."""
    result = parse_scan_execute_log(FIXTURES / "scan_20260326_12345.log")
    assert result["status"] == "failed"
    assert result["ok"] == 2
    assert result["failed"] == 1
    assert result["ran_at"] == "06:31"


def test_parse_scan_execute_log_truncated(tmp_path):
    """Log without COMPLETE line (truncated) → status failed."""
    log = tmp_path / "scan_20260326_99999.log"
    log.write_text("[06:30:00] PRE-MARKET SCAN START\n[06:30:01] Scanning: microcap\n")
    result = parse_scan_execute_log(log)
    assert result["status"] == "failed"
    assert result["ran_at"] is None


def test_parse_update_log_counts_lines():
    """Update log (no summary) → counts Updating/FAILED lines correctly."""
    result = parse_update_log(FIXTURES / "update_20260326_12345.log")
    assert result["ok"] == 1    # microcap succeeded, max failed → 2 Updating - 1 FAILED = 1
    assert result["failed"] == 1
    assert result["status"] == "failed"
    assert result["ran_at"] == "12:01"


def test_parse_update_log_missing_complete(tmp_path):
    """Update log without COMPLETE line → status failed."""
    log = tmp_path / "update_20260326_99999.log"
    log.write_text("[12:00:00] POSITION UPDATE START\n[12:00:01] Updating: microcap\n")
    result = parse_update_log(log)
    assert result["status"] == "failed"
    assert result["ran_at"] is None


def test_parse_watchdog_log():
    """Watchdog log → correct list of restart events with date/time/result."""
    results = parse_watchdog_log(FIXTURES / "api_watchdog.log")
    assert len(results) == 3  # 2 on 03-26, 1 on 03-25 (only restarted OK/FAILED lines)
    mar26 = [r for r in results if r["date"] == "2026-03-26"]
    assert len(mar26) == 2
    assert mar26[0] == {"date": "2026-03-26", "time": "10:14", "result": "ok"}
    assert mar26[1] == {"date": "2026-03-26", "time": "14:30", "result": "failed"}


def test_count_trades_for_date():
    """Count trades for a specific date across all fixture portfolios."""
    count = count_trades_for_date(PORTFOLIOS_FIXTURES, "2026-03-26")
    assert count == 2  # AAPL buy + MSFT sell on 2026-03-26


def test_count_trades_for_date_different_day():
    """Trades on a different date are not counted."""
    count = count_trades_for_date(PORTFOLIOS_FIXTURES, "2026-03-25")
    assert count == 1  # only GOOG buy on 2026-03-25


def test_build_day_summary_missing_logs(tmp_path):
    """Day with no log files → all statuses missing, empty events."""
    empty_portfolios = tmp_path / "portfolios"
    empty_portfolios.mkdir()
    result = build_day_summary(tmp_path, empty_portfolios, "2026-03-26")
    assert result["date"] == "2026-03-26"
    assert result["pipeline"]["scan"]["status"] == "missing"
    assert result["pipeline"]["execute"]["status"] == "missing"
    assert result["pipeline"]["update_midday"]["status"] == "missing"
    assert result["pipeline"]["update_close"]["status"] == "missing"
    assert result["watchdog_restarts"] == 0
    assert result["events"] == []


def test_api_system_logs_endpoint(monkeypatch):
    """GET /api/system/logs returns a list of day objects."""
    from fastapi.testclient import TestClient
    import api.main as main_module

    # Point the route at our fixture directories
    import api.routes.system as system_module
    monkeypatch.setattr(system_module, "CRON_LOGS_DIR", FIXTURES)
    monkeypatch.setattr(system_module, "PORTFOLIOS_DIR", PORTFOLIOS_FIXTURES)

    client = TestClient(main_module.app)
    response = client.get("/api/system/logs")
    assert response.status_code == 200
    data = response.json()
    assert "days" in data
    assert isinstance(data["days"], list)
    assert len(data["days"]) == 30
    # Today or recent date should have real data from fixtures if date matches
    # But regardless, every entry must have the required shape
    for day in data["days"]:
        assert "date" in day
        assert "pipeline" in day
        assert "watchdog_restarts" in day
        assert "events" in day
