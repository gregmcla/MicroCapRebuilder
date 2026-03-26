"""Parse cron log files into structured dicts for the system logs API."""
import csv
import logging
import re
from pathlib import Path


def parse_scan_execute_log(log_path: Path) -> dict:
    """
    Parse a scan or execute log file (has count summary line).
    Returns: { ran_at, status, ok, failed }
    """
    text = log_path.read_text()
    m = re.search(
        r'\[(\d{2}:\d{2}):\d{2}\] (?:SCAN|EXECUTE) COMPLETE -- (\d+) ok, (\d+) failed',
        text,
    )
    if not m:
        return {"ran_at": None, "status": "failed", "ok": 0, "failed": 0}
    ok = int(m.group(2))
    failed = int(m.group(3))
    return {
        "ran_at": m.group(1),
        "status": "ok" if failed == 0 else "failed",
        "ok": ok,
        "failed": failed,
    }


def parse_update_log(log_path: Path) -> dict:
    """
    Parse an update log file (no count summary — count individual lines).
    Returns: { ran_at, status, ok, failed }
    """
    text = log_path.read_text()
    lines = text.splitlines()
    failed = sum(1 for line in lines if "  FAILED: " in line)
    updating = sum(1 for line in lines if "Updating: " in line)
    ok = max(0, updating - failed)

    m = re.search(r'\[(\d{2}:\d{2}):\d{2}\] UPDATE COMPLETE', text)
    if not m:
        return {"ran_at": None, "status": "failed", "ok": ok, "failed": failed}
    return {
        "ran_at": m.group(1),
        "status": "ok" if failed == 0 else "failed",
        "ok": ok,
        "failed": failed,
    }


def parse_watchdog_log(log_path: Path) -> list[dict]:
    """
    Parse cron/logs/api_watchdog.log.
    Returns list of { date, time, result } for restart outcome lines only.
    """
    if not log_path.exists():
        return []
    results = []
    for line in log_path.read_text().splitlines():
        m = re.match(
            r'\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}):\d{2}\] API restart(ed OK| FAILED)',
            line,
        )
        if m:
            results.append({
                "date": m.group(1),
                "time": m.group(2),
                "result": "ok" if m.group(3) == "ed OK" else "failed",
            })
    return results


def count_trades_for_date(portfolios_dir: Path, date_str: str) -> int:
    """Count BUY+SELL transactions across all portfolios for a given date (YYYY-MM-DD)."""
    total = 0
    for portfolio_dir in sorted(portfolios_dir.iterdir()):
        if not portfolio_dir.is_dir():
            continue
        csv_path = portfolio_dir / "transactions.csv"
        if not csv_path.exists():
            continue
        try:
            with csv_path.open() as f:
                for row in csv.DictReader(f):
                    if row.get("date", "").startswith(date_str):
                        total += 1
        except Exception as e:
            continue
    return total


def _missing_job() -> dict:
    return {"status": "missing", "ok": 0, "failed": 0, "ran_at": None}


def build_day_summary(cron_logs_dir: Path, portfolios_dir: Path, date_str: str) -> dict:
    """Build full day summary for one date. Handles missing files gracefully."""
    date_compact = date_str.replace("-", "")

    def _parse_scan_execute(pattern: str) -> dict:
        files = sorted(cron_logs_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
        if not files:
            return _missing_job()
        try:
            return parse_scan_execute_log(files[-1])
        except Exception as e:
            logging.warning("Failed to parse log %s: %s", cron_logs_dir / pattern, e)
            return {"status": "failed", "ok": 0, "failed": 0, "ran_at": None}

    def _parse_update(log_path: Path) -> dict:
        try:
            return parse_update_log(log_path)
        except Exception as e:
            logging.warning("Failed to parse update log %s: %s", log_path, e)
            return {"status": "failed", "ok": 0, "failed": 0, "ran_at": None}

    scan = _parse_scan_execute(f"scan_{date_compact}_*.log")
    execute = _parse_scan_execute(f"execute_{date_compact}_*.log")

    # Update: may have two files (midday + close) — sort by mtime
    update_files = sorted(
        cron_logs_dir.glob(f"update_{date_compact}_*.log"),
        key=lambda p: p.stat().st_mtime,
    )
    if len(update_files) >= 2:
        update_midday = _parse_update(update_files[0])
        update_close = _parse_update(update_files[1])
    elif len(update_files) == 1:
        update_midday = _parse_update(update_files[0])
        update_close = _missing_job()
    else:
        update_midday = _missing_job()
        update_close = _missing_job()

    # Trade count from transactions CSVs
    trades = count_trades_for_date(portfolios_dir, date_str)
    execute["trades"] = trades

    # Watchdog restarts for this date
    watchdog_events = parse_watchdog_log(cron_logs_dir / "api_watchdog.log")
    day_watchdog = [e for e in watchdog_events if e["date"] == date_str]
    restarts = len(day_watchdog)

    # Build chronological events list
    events = []

    def _add_pipeline_event(job: dict, event_type: str):
        if job["status"] == "missing" or not job.get("ran_at"):
            return
        total = job["ok"] + job["failed"]
        if event_type == "execute":
            t = job.get("trades", 0)
            detail = f"{t} trade{'s' if t != 1 else ''}" if t else "no trades"
        else:
            detail = f"{job['ok']}/{total} ok" if total else "ok"
        events.append({
            "time": job["ran_at"],
            "type": "failed" if job["status"] == "failed" else event_type,
            "detail": detail,
        })

    _add_pipeline_event(scan, "scan")
    _add_pipeline_event(execute, "execute")
    _add_pipeline_event(update_midday, "update")
    _add_pipeline_event(update_close, "update")

    for e in day_watchdog:
        events.append({
            "time": e["time"],
            "type": "api_restart",
            "detail": f"API restarted {'OK' if e['result'] == 'ok' else 'FAILED'}",
        })

    events.sort(key=lambda e: e["time"])

    return {
        "date": date_str,
        "pipeline": {
            "scan": scan,
            "execute": execute,
            "update_midday": update_midday,
            "update_close": update_close,
        },
        "watchdog_restarts": restarts,
        "events": events,
    }
