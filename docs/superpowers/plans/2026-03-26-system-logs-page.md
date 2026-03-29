# System Logs Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LOGS page in the GScott dashboard showing daily pipeline health (scan/execute/update status), an event timeline, and a Claude-generated daily narrative — all accessible via a LOGS button in the TopBar.

**Architecture:** Pure read-only feature — a Python log parser reads `cron/logs/` files and transactions CSVs, a FastAPI route serves structured JSON, and a React full-page component renders it. A separate narrative endpoint calls Claude with daily context (trades, P&L, factor learning) and caches the response 10 minutes. Navigation uses the existing Zustand `setPortfolio("logs")` pattern.

**Tech Stack:** Python 3 / FastAPI / pathlib, React 19 / TanStack Query / Tailwind v4, Zustand, Anthropic SDK (already installed).

---

## Context for the implementer

This is MicroCapRebuilder (GScott), a paper trading system. The project root is `/Users/gregmclaughlin/MicroCapRebuilder`. Python lives in `.venv/`. The dashboard is a Vite + React 19 + Tailwind v4 SPA.

**Navigation pattern:** `activePortfolioId` in Zustand store drives what renders. `"overview"` → OverviewPage. Any other string → portfolio detail. We're adding `"logs"` → LogsPage. The `setPortfolio(id)` method on `usePortfolioStore` is how navigation works.

**Cron log files** live in `cron/logs/`. Format:
- `scan_YYYYMMDD_PID.log` / `execute_YYYYMMDD_PID.log` — have `COMPLETE -- X ok, Y failed` summary lines
- `update_YYYYMMDD_PID.log` — no summary line, must count `Updating:` and `FAILED:` lines
- `api_watchdog.log` — persistent log with `[YYYY-MM-DD HH:MM:SS]` timestamps

**Key imports for the backend:**
```python
# At top of any script in scripts/
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
# But system.py is in api/routes/, so:
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
```

**Test style in this project:** pytest, simple functions, `Path` for files. See `tests/test_cron_scripts.py` for examples.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/log_parser.py` | Create | Parse cron log files into structured dicts |
| `api/routes/system.py` | Create | `GET /api/system/logs` and `GET /api/system/narrative` |
| `api/main.py` | Modify | Register system router |
| `tests/test_log_parser.py` | Create | 9 tests for parser functions |
| `tests/fixtures/cron_logs/` | Create | Fixture log files for tests |
| `dashboard/src/lib/types.ts` | Modify | Add 5 new TypeScript interfaces |
| `dashboard/src/lib/api.ts` | Modify | Add `getSystemLogs()` and `generateNarrative()` |
| `dashboard/src/hooks/useSystemLogs.ts` | Create | `useSystemLogs()` and `useSystemNarrative()` hooks |
| `dashboard/src/hooks/usePortfolioState.ts` | Modify | Extend `enabled` guard to exclude `"logs"` |
| `dashboard/src/components/LogsPage.tsx` | Create | Full-page view (narrative + grid + timeline) |
| `dashboard/src/App.tsx` | Modify | Add `"logs"` routing case, fix query guards |
| `dashboard/src/components/TopBar.tsx` | Modify | Add LOGS button |

---

## Task 1: Log parser + tests (TDD)

**Files:**
- Create: `tests/fixtures/cron_logs/scan_20260326_12345.log`
- Create: `tests/fixtures/cron_logs/execute_20260326_12345.log`
- Create: `tests/fixtures/cron_logs/update_20260326_12345.log`
- Create: `tests/fixtures/cron_logs/api_watchdog.log`
- Create: `tests/fixtures/portfolios/microcap/transactions.csv`
- Create: `tests/test_log_parser.py`
- Create: `scripts/log_parser.py`

- [ ] **Step 1: Create fixture files**

Create `tests/fixtures/cron_logs/scan_20260326_12345.log`:
```
[06:31:02] ==========================================
[06:31:02] PRE-MARKET SCAN START
[06:31:02] ==========================================
[06:31:03] Scanning: microcap
[06:31:05]   ok: microcap
[06:31:05] Scanning: max
[06:31:07]   ok: max
[06:31:07] Scanning: boomers
[06:31:09]   FAILED: boomers (continuing)
[06:31:09] ==========================================
[06:31:09] SCAN COMPLETE -- 2 ok, 1 failed
[06:31:09] ==========================================
```

Create `tests/fixtures/cron_logs/execute_20260326_12345.log`:
```
[09:36:14] ==========================================
[09:36:14] MARKET-OPEN EXECUTE START
[09:36:14] ==========================================
[09:36:15] Executing: microcap
[09:36:45]   ok: microcap
[09:36:45] Executing: max
[09:37:20]   ok: max
[09:37:20] ==========================================
[09:37:20] EXECUTE COMPLETE -- 2 ok, 0 failed
[09:37:20] ==========================================
```

Create `tests/fixtures/cron_logs/update_20260326_12345.log`:
```
[12:01:33] ==========================================
[12:01:33] POSITION UPDATE START
[12:01:33] ==========================================
[12:01:33] Updating: microcap
[12:01:35] Updating: max
[12:01:36]   FAILED: update_positions for max
[12:01:36] ==========================================
[12:01:36] UPDATE COMPLETE
[12:01:36] ==========================================
```

Create `tests/fixtures/cron_logs/api_watchdog.log`:
```
[2026-03-26 10:14:00] API down -- restarting...
[2026-03-26 10:14:08] API restarted OK
[2026-03-26 14:30:00] API down -- restarting...
[2026-03-26 14:30:08] API restart FAILED
[2026-03-25 08:00:01] API down -- restarting...
[2026-03-25 08:00:09] API restarted OK
```

Create `tests/fixtures/portfolios/microcap/transactions.csv`:
```
transaction_id,date,ticker,action,shares,price,total_value,stop_loss,take_profit,reason,factor_scores,regime_at_entry,composite_score,signal_rank,trade_rationale
abc123,2026-03-26T09:37:00,AAPL,BUY,10,150.00,1500.00,135.00,180.00,SIGNAL,,,,,
def456,2026-03-26T09:37:01,MSFT,SELL,5,300.00,1500.00,,,TAKE_PROFIT,,,,,
ghi789,2026-03-25T09:37:00,GOOG,BUY,2,200.00,400.00,,,SIGNAL,,,,,
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_log_parser.py`:

```python
"""Tests for scripts/log_parser.py — parse cron log files into structured data."""
import csv
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "cron_logs"
PORTFOLIOS_FIXTURES = Path(__file__).parent / "fixtures" / "portfolios"

# Import from scripts/
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
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
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
pytest tests/test_log_parser.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'log_parser'`

- [ ] **Step 4: Implement log_parser.py**

Create `scripts/log_parser.py`:

```python
"""Parse cron log files into structured dicts for the system logs API."""
import csv
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
        except Exception:
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
        except Exception:
            return {"status": "failed", "ok": 0, "failed": 0, "ran_at": None}

    def _parse_update(log_path: Path) -> dict:
        try:
            return parse_update_log(log_path)
        except Exception:
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
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
pytest tests/test_log_parser.py -v
```

Expected:
```
tests/test_log_parser.py::test_parse_scan_execute_log_ok PASSED
tests/test_log_parser.py::test_parse_scan_execute_log_with_failures PASSED
tests/test_log_parser.py::test_parse_scan_execute_log_truncated PASSED
tests/test_log_parser.py::test_parse_update_log_counts_lines PASSED
tests/test_log_parser.py::test_parse_update_log_missing_complete PASSED
tests/test_log_parser.py::test_parse_watchdog_log PASSED
tests/test_log_parser.py::test_count_trades_for_date PASSED
tests/test_log_parser.py::test_count_trades_for_date_different_day PASSED
tests/test_log_parser.py::test_build_day_summary_missing_logs PASSED
9 passed
```

- [ ] **Step 6: Commit**

```bash
git add scripts/log_parser.py tests/test_log_parser.py tests/fixtures/
git commit -m "feat: add cron log parser with tests"
```

---

## Task 2: Backend API route

**Files:**
- Create: `api/routes/system.py`
- Modify: `api/main.py`

- [ ] **Step 1: Write failing endpoint test**

Add to `tests/test_log_parser.py` (append at the bottom):

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_log_parser.py::test_api_system_logs_endpoint -v
```

Expected: `ModuleNotFoundError: No module named 'api.routes.system'`

- [ ] **Step 3: Implement system.py**

Create `api/routes/system.py`:

```python
"""System health and logs endpoints."""
import csv
import sys
from datetime import date as _date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from log_parser import build_day_summary

router = APIRouter()

CRON_LOGS_DIR = Path(__file__).parent.parent.parent / "cron" / "logs"
PORTFOLIOS_DIR = Path(__file__).parent.parent.parent / "data" / "portfolios"

_MISSING_JOB = {"status": "missing", "ok": 0, "failed": 0, "ran_at": None}

def _empty_day(date_str: str) -> dict:
    return {
        "date": date_str,
        "pipeline": {
            "scan": dict(_MISSING_JOB),
            "execute": {**_MISSING_JOB, "trades": 0},
            "update_midday": dict(_MISSING_JOB),
            "update_close": dict(_MISSING_JOB),
        },
        "watchdog_restarts": 0,
        "events": [],
    }


@router.get("/api/system/logs")
def get_system_logs():
    """Return last 30 days of pipeline activity, newest first."""
    if not CRON_LOGS_DIR.exists():
        return {"days": [_empty_day(str(_date.today() - timedelta(days=i))) for i in range(30)]}

    days = []
    today = _date.today()
    for i in range(30):
        date_str = str(today - timedelta(days=i))
        try:
            day = build_day_summary(CRON_LOGS_DIR, PORTFOLIOS_DIR, date_str)
        except Exception:
            day = _empty_day(date_str)
        days.append(day)
    return {"days": days}


# In-memory narrative cache: {date_str: {"result": response_dict, "cached_at": datetime}}
_narrative_cache: dict[str, dict] = {}
_NARRATIVE_CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_trades_for_date(date_str: str) -> list[dict]:
    """Get trade details across all portfolios for a given date."""
    trades = []
    if not PORTFOLIOS_DIR.exists():
        return trades
    for portfolio_dir in sorted(PORTFOLIOS_DIR.iterdir()):
        if not portfolio_dir.is_dir():
            continue
        csv_path = portfolio_dir / "transactions.csv"
        if not csv_path.exists():
            continue
        try:
            with csv_path.open() as f:
                for row in csv.DictReader(f):
                    if row.get("date", "").startswith(date_str):
                        trades.append({
                            "portfolio": portfolio_dir.name,
                            "ticker": row.get("ticker", ""),
                            "action": row.get("action", ""),
                            "price": row.get("price", ""),
                            "reason": row.get("reason", ""),
                        })
        except Exception:
            continue
    return trades


def _get_pnl_snapshots(date_str: str) -> list[dict]:
    """Get P&L snapshot for each portfolio on a given date."""
    snapshots = []
    if not PORTFOLIOS_DIR.exists():
        return snapshots
    for portfolio_dir in sorted(PORTFOLIOS_DIR.iterdir()):
        if not portfolio_dir.is_dir():
            continue
        csv_path = portfolio_dir / "daily_snapshots.csv"
        if not csv_path.exists():
            continue
        try:
            with csv_path.open() as f:
                for row in csv.DictReader(f):
                    if row.get("date", "") == date_str:
                        snapshots.append({
                            "portfolio": portfolio_dir.name,
                            "total_equity": row.get("total_equity", ""),
                            "day_pnl": row.get("day_pnl", ""),
                            "day_pnl_pct": row.get("day_pnl_pct", ""),
                        })
        except Exception:
            continue
    return snapshots


def _build_narrative_prompt(
    date_str: str,
    day_summary: dict,
    trades: list[dict],
    pnl_snapshots: list[dict],
) -> str:
    pipeline = day_summary.get("pipeline", {})

    def _job_line(job: dict, label: str) -> str:
        if job.get("status") == "missing":
            return f"  {label}: did not run"
        ok = job.get("ok", 0)
        failed = job.get("failed", 0)
        trades_note = f", {job.get('trades', 0)} trades" if "trades" in job else ""
        status = "✓" if job.get("status") == "ok" else "✗"
        return f"  {label}: {status} {ok}/{ok+failed} portfolios ok{trades_note}"

    pipeline_lines = "\n".join([
        _job_line(pipeline.get("scan", {}), "SCAN (6:30 AM)"),
        _job_line(pipeline.get("execute", {}), "EXECUTE (9:35 AM)"),
        _job_line(pipeline.get("update_midday", {}), "UPDATE MIDDAY (12:00 PM)"),
        _job_line(pipeline.get("update_close", {}), "UPDATE CLOSE (4:15 PM)"),
        f"  API watchdog restarts: {day_summary.get('watchdog_restarts', 0)}",
    ])

    trade_lines = ""
    if trades:
        trade_lines = "\n".join(
            f"  {t['action']} {t['ticker']} in [{t['portfolio']}] @ ${t['price']} — reason: {t['reason']}"
            for t in trades
        )
    else:
        trade_lines = "  No trades today."

    pnl_lines = ""
    if pnl_snapshots:
        pnl_lines = "\n".join(
            f"  {s['portfolio']}: equity=${s['total_equity']}, day P&L=${s['day_pnl']} ({s['day_pnl_pct']}%)"
            for s in pnl_snapshots
        )
    else:
        pnl_lines = "  No P&L data available."

    return f"""You are the GScott trading system's daily analyst. Write a concise daily briefing for {date_str}.

## Pipeline Status
{pipeline_lines}

## Today's Trades
{trade_lines}

## Portfolio P&L
{pnl_lines}

---

Write a daily briefing covering:
1. What happened operationally — did the pipeline run cleanly, any issues?
2. Why trades were made — synthesize from the ticker/reason data above
3. Patterns emerging across portfolios today
4. Anything notable — failures, unusual activity, watchdog restarts

Be concise — 3–5 short paragraphs. Use plain text (no markdown headers). Write in second person ("your portfolios").
""".strip()


@router.get("/api/system/narrative")
def get_system_narrative(date: Optional[str] = None, regenerate: bool = False):
    """Generate (or return cached) Claude narrative for a given date.

    Query params:
      date: YYYY-MM-DD (defaults to today)
      regenerate: true to bypass 10-minute in-memory cache
    """
    from schema import CLAUDE_MODEL

    target_date = date or str(_date.today())

    if not regenerate and target_date in _narrative_cache:
        entry = _narrative_cache[target_date]
        age = (datetime.now() - entry["cached_at"]).total_seconds()
        if age < _NARRATIVE_CACHE_TTL_SECONDS:
            cached = dict(entry["result"])
            cached["cached"] = True
            return cached

    try:
        day_summary = build_day_summary(CRON_LOGS_DIR, PORTFOLIOS_DIR, target_date)
    except Exception:
        day_summary = _empty_day(target_date)

    trades = _get_trades_for_date(target_date)
    pnl_snapshots = _get_pnl_snapshots(target_date)
    prompt = _build_narrative_prompt(target_date, day_summary, trades, pnl_snapshots)

    try:
        import anthropic
        client = anthropic.Anthropic(timeout=60.0)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        narrative = message.content[0].text
    except Exception as e:
        return {
            "date": target_date,
            "narrative": None,
            "generated_at": datetime.now().isoformat(),
            "cached": False,
            "error": "narrative unavailable",
        }

    result = {
        "date": target_date,
        "narrative": narrative,
        "generated_at": datetime.now().isoformat(),
        "cached": False,
    }
    _narrative_cache[target_date] = {"result": result, "cached_at": datetime.now()}
    return result
```

- [ ] **Step 4: Register router in main.py**

Open `api/main.py`. After the existing router imports and before the `app.include_router()` calls, add:

```python
from api.routes import system as system_routes
```

Then add this line among the `app.include_router()` calls — add it **before** the portfolio-scoped routes (after market routes is fine):

```python
app.include_router(system_routes.router)
```

The full router block in `main.py` should look like:
```python
app.include_router(portfolios_routes.router)
app.include_router(state_routes.router)
app.include_router(risk_routes.router)
app.include_router(performance_routes.router)
app.include_router(analysis_routes.router)
app.include_router(market_routes.router)
app.include_router(controls_routes.router)
app.include_router(discovery_routes.router)
app.include_router(system_routes.router)   # ← add this
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
pytest tests/test_log_parser.py -v
```

Expected: all 10 tests pass.

- [ ] **Step 6: Smoke test the live endpoint**

```bash
curl -s http://localhost:8001/api/system/logs | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['days']), 'days'); print(d['days'][0])"
```

Expected: `30 days` followed by today's day object with all pipeline fields.

(API must be running. If not: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && DISABLE_SOCIAL=true nohup uvicorn api.main:app --host 0.0.0.0 --port 8001 > /tmp/mcr_api.log 2>&1 &` then wait 4s.)

- [ ] **Step 7: Commit**

```bash
git add api/routes/system.py api/main.py tests/test_log_parser.py
git commit -m "feat: add system logs and narrative API endpoints"
```

---

## Task 3: TypeScript types + API client

**Files:**
- Modify: `dashboard/src/lib/types.ts`
- Modify: `dashboard/src/lib/api.ts`

- [ ] **Step 1: Add TypeScript types to types.ts**

Open `dashboard/src/lib/types.ts`. Append at the end of the file:

```typescript
// ── System Logs ──────────────────────────────────────────────────────────────

export interface PipelineJob {
  status: "ok" | "failed" | "missing";
  ok: number;
  failed: number;
  ran_at: string | null;   // "HH:MM" or null if missing
  trades?: number;         // execute job only
}

export interface LogEvent {
  time: string;            // "HH:MM"
  type: "scan" | "execute" | "update" | "api_restart" | "failed";
  detail: string;
}

export interface DayLog {
  date: string;            // "YYYY-MM-DD"
  pipeline: {
    scan: PipelineJob;
    execute: PipelineJob;
    update_midday: PipelineJob;
    update_close: PipelineJob;
  };
  watchdog_restarts: number;
  events: LogEvent[];
}

export interface SystemLogsResponse {
  days: DayLog[];
}

export interface NarrativeResponse {
  date: string;
  narrative: string | null;
  generated_at: string;
  cached: boolean;
  error?: string;
}
```

- [ ] **Step 2: Add methods to api.ts**

Open `dashboard/src/lib/api.ts`. Find the market endpoints section (near lines 116–118) and add these two methods to the `api` object, after the existing market methods:

```typescript
  // System logs
  getSystemLogs: (): Promise<SystemLogsResponse> =>
    get<SystemLogsResponse>("/api/system/logs"),

  generateNarrative: (logDate?: string, regenerate?: boolean): Promise<NarrativeResponse> => {
    const params = new URLSearchParams();
    if (logDate) params.set("date", logDate);
    if (regenerate) params.set("regenerate", "true");
    const qs = params.toString();
    return get<NarrativeResponse>(`/api/system/narrative${qs ? `?${qs}` : ""}`);
  },
```

Make sure to add the new types to the import from `./types` at the top of `api.ts`:
```typescript
import type {
  // ... existing imports ...
  SystemLogsResponse,
  NarrativeResponse,
} from "./types";
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -20
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/lib/types.ts dashboard/src/lib/api.ts
git commit -m "feat: add system logs TypeScript types and API client methods"
```

---

## Task 4: React hooks + usePortfolioState guard fix

**Files:**
- Create: `dashboard/src/hooks/useSystemLogs.ts`
- Modify: `dashboard/src/hooks/usePortfolioState.ts`

- [ ] **Step 1: Create useSystemLogs.ts**

Create `dashboard/src/hooks/useSystemLogs.ts`:

```typescript
/** TanStack Query hooks for system logs and Claude narrative. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { SystemLogsResponse, NarrativeResponse } from "../lib/types";

export function useSystemLogs() {
  return useQuery<SystemLogsResponse>({
    queryKey: ["system-logs"],
    queryFn: () => api.getSystemLogs(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useSystemNarrative(logDate?: string) {
  return useQuery<NarrativeResponse>({
    queryKey: ["system-narrative", logDate],
    queryFn: () => api.generateNarrative(logDate),
    staleTime: 10 * 60 * 1000,  // 10 min — matches server cache
    retry: false,               // don't retry Claude failures
  });
}

export function useRegenerateNarrative() {
  const queryClient = useQueryClient();
  // Calls with regenerate=true so the server bypasses its 10-min cache,
  // then writes the result directly into the query cache.
  return async (logDate?: string) => {
    const result = await api.generateNarrative(logDate, true);
    queryClient.setQueryData(["system-narrative", logDate], result);
  };
}
```

- [ ] **Step 2: Fix usePortfolioState.ts guard**

Open `dashboard/src/hooks/usePortfolioState.ts`. The current `enabled` line is:
```typescript
    enabled: portfolioId !== "overview",
```

Change it to:
```typescript
    enabled: portfolioId !== "overview" && portfolioId !== "logs",
```

Only this one line changes. The `usePortfolioRefresh` hook does not need changing (it's already `enabled: false`).

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -10
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/hooks/useSystemLogs.ts dashboard/src/hooks/usePortfolioState.ts
git commit -m "feat: add useSystemLogs hook and fix portfolio state guard for logs route"
```

---

## Task 5: LogsPage component

**Files:**
- Create: `dashboard/src/components/LogsPage.tsx`

- [ ] **Step 1: Create LogsPage.tsx**

Create `dashboard/src/components/LogsPage.tsx`:

```tsx
/**
 * LogsPage — system health + pipeline status + Claude daily briefing.
 * Activated when activePortfolioId === "logs".
 */

import { useState } from "react";
import { useSystemLogs, useSystemNarrative, useRegenerateNarrative } from "../hooks/useSystemLogs";
import type { DayLog, PipelineJob, LogEvent } from "../lib/types";

// ── Badge colours ─────────────────────────────────────────────────────────────

const EVENT_BADGE: Record<LogEvent["type"], string> = {
  scan:        "bg-blue-900/60 text-blue-300 border border-blue-700/40",
  execute:     "bg-green-900/60 text-green-300 border border-green-700/40",
  update:      "bg-teal-900/60 text-teal-300 border border-teal-700/40",
  api_restart: "bg-amber-900/60 text-amber-300 border border-amber-700/40",
  failed:      "bg-red-900/60 text-red-400 border border-red-700/40",
};

const EVENT_LABEL: Record<LogEvent["type"], string> = {
  scan:        "SCAN",
  execute:     "EXECUTE",
  update:      "UPDATE",
  api_restart: "RESTART",
  failed:      "FAILED",
};

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusCell({ job }: { job: PipelineJob }) {
  if (job.status === "missing") {
    return <span className="text-zinc-600 font-mono text-xs">—</span>;
  }
  const total = job.ok + job.failed;
  if (job.status === "failed" && total === 0) {
    return <span className="text-red-400 font-mono text-xs">✗</span>;
  }
  const hasFailures = job.failed > 0;
  const color = hasFailures ? "text-amber-400" : "text-green-400";
  const icon = hasFailures ? "⚠" : "✓";
  return (
    <span className={`${color} font-mono text-xs`}>
      {icon} {job.ok}/{total}
    </span>
  );
}

function WatchdogCell({ restarts }: { restarts: number }) {
  if (restarts === 0) {
    return <span className="text-zinc-600 font-mono text-xs">0</span>;
  }
  return (
    <span className="text-amber-400 font-mono text-xs">
      ⚡ {restarts}
    </span>
  );
}

function NarrativeSection() {
  const { data, isLoading } = useSystemNarrative();
  const regenerate = useRegenerateNarrative();

  return (
    <section className="mb-8 border border-zinc-800 rounded-lg p-5 bg-zinc-900/40">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-mono tracking-widest text-zinc-500 uppercase">
          Today's Briefing
        </h2>
        <button
          onClick={() => regenerate()}
          className="text-xs text-zinc-600 hover:text-zinc-300 transition-colors font-mono"
        >
          Regenerate ↺
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {[100, 90, 95, 80].map((w, i) => (
            <div key={i} className="h-3 bg-zinc-800 rounded" style={{ width: `${w}%` }} />
          ))}
        </div>
      ) : data?.narrative ? (
        <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap font-mono">
          {data.narrative}
        </p>
      ) : (
        <p className="text-sm text-zinc-600 italic">
          {data?.error
            ? "Narrative unavailable — Claude call failed."
            : "No briefing yet. Check back after the first cron run."}
        </p>
      )}
    </section>
  );
}

function PipelineGrid({ days }: { days: DayLog[] }) {
  const today = new Date().toISOString().slice(0, 10);
  const visible = days.slice(0, 14);

  return (
    <section className="mb-8">
      <h2 className="text-xs font-mono tracking-widest text-zinc-500 uppercase mb-3">
        Pipeline Status
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono border-collapse">
          <thead>
            <tr className="text-zinc-600 border-b border-zinc-800">
              <th className="text-left py-2 pr-6 font-normal">DATE</th>
              <th className="text-center py-2 px-3 font-normal">SCAN 6:30</th>
              <th className="text-center py-2 px-3 font-normal">EXECUTE 9:35</th>
              <th className="text-center py-2 px-3 font-normal">UPDATE 12:00</th>
              <th className="text-center py-2 px-3 font-normal">UPDATE 4:15</th>
              <th className="text-center py-2 px-3 font-normal">WATCHDOG</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((day) => {
              const isToday = day.date === today;
              return (
                <tr
                  key={day.date}
                  className={`border-b border-zinc-800/50 ${isToday ? "bg-zinc-800/30" : ""}`}
                >
                  <td className={`py-2 pr-6 ${isToday ? "text-zinc-300" : "text-zinc-500"}`}>
                    {day.date}
                  </td>
                  <td className="py-2 px-3 text-center">
                    <StatusCell job={day.pipeline.scan} />
                  </td>
                  <td className="py-2 px-3 text-center">
                    <StatusCell job={day.pipeline.execute} />
                  </td>
                  <td className="py-2 px-3 text-center">
                    <StatusCell job={day.pipeline.update_midday} />
                  </td>
                  <td className="py-2 px-3 text-center">
                    <StatusCell job={day.pipeline.update_close} />
                  </td>
                  <td className="py-2 px-3 text-center">
                    <WatchdogCell restarts={day.watchdog_restarts} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TimelineDay({ day, defaultOpen }: { day: DayLog; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const label = new Date(day.date + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric",
  });

  return (
    <div className="border-b border-zinc-800/50">
      <button
        className="w-full flex items-center gap-2 py-2 text-xs font-mono text-zinc-500 hover:text-zinc-300 transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        <span>{open ? "▼" : "▶"}</span>
        <span>{label}</span>
        {day.events.length > 0 && (
          <span className="text-zinc-700">({day.events.length} events)</span>
        )}
      </button>

      {open && (
        <div className="pb-3 space-y-1.5 pl-4">
          {day.events.length === 0 ? (
            <p className="text-xs text-zinc-700 font-mono">No events recorded.</p>
          ) : (
            day.events.map((evt, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className="text-zinc-600 font-mono text-xs w-10 shrink-0">{evt.time}</span>
                <span className={`text-xs font-mono px-1.5 py-0.5 rounded shrink-0 ${EVENT_BADGE[evt.type]}`}>
                  {EVENT_LABEL[evt.type]}
                </span>
                <span className="text-zinc-400 font-mono text-xs">{evt.detail}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function EventTimeline({ days }: { days: DayLog[] }) {
  return (
    <section>
      <h2 className="text-xs font-mono tracking-widest text-zinc-500 uppercase mb-3">
        Event Timeline
      </h2>
      <div>
        {days.map((day, i) => (
          <TimelineDay key={day.date} day={day} defaultOpen={i === 0} />
        ))}
      </div>
    </section>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function LogsPage() {
  const { data, isLoading } = useSystemLogs();
  const updatedAt = new Date().toLocaleTimeString("en-US", {
    hour: "numeric", minute: "2-digit",
  });

  return (
    <main className="flex-1 overflow-y-auto p-6 min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xs font-mono tracking-widest text-zinc-400 uppercase">
          System Logs
        </h1>
        <span className="text-xs font-mono text-zinc-600">
          last updated {updatedAt}
        </span>
      </div>

      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-6 bg-zinc-800 rounded w-full" />
          ))}
        </div>
      ) : !data || data.days.every((d) => d.events.length === 0 && d.watchdog_restarts === 0) ? (
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <p className="text-zinc-500 font-mono text-sm mb-1">No logs yet</p>
          <p className="text-zinc-700 font-mono text-xs">
            Pipeline activity will appear here after the first cron run (6:30 AM tomorrow).
          </p>
        </div>
      ) : (
        <>
          <NarrativeSection />
          <PipelineGrid days={data.days} />
          <EventTimeline days={data.days} />
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -10
```

Expected: no errors referencing LogsPage.tsx.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/LogsPage.tsx
git commit -m "feat: add LogsPage component with narrative, pipeline grid, and timeline"
```

---

## Task 6: App.tsx + TopBar.tsx wiring

**Files:**
- Modify: `dashboard/src/App.tsx`
- Modify: `dashboard/src/components/TopBar.tsx`

- [ ] **Step 1: Update App.tsx**

Open `dashboard/src/App.tsx`.

**Change 1:** Add import at the top with the other page imports:
```tsx
import LogsPage from "./components/LogsPage";
```

**Change 2:** Find line 62 (the `isOverview` declaration):
```tsx
const isOverview = portfolioId === "overview";
```
Add a new line immediately after it:
```tsx
const isLogs = portfolioId === "logs";
```

**Change 3:** Find the `activeMatrixPortfolio` useMemo (around line 71). Its first line is:
```tsx
if (isOverview || !portfolioId) return null;
```
Change it to:
```tsx
if (isOverview || isLogs || !portfolioId) return null;
```

**Change 4:** Find the two `useQuery` calls that have `enabled: !isOverview && !!portfolioId` (around lines 90–100). Change **both** of them:
```tsx
// BEFORE:
enabled: !isOverview && !!portfolioId,

// AFTER:
enabled: !isOverview && !isLogs && !!portfolioId,
```

**Change 5:** Find the conditional render block (around line 110). Currently:
```tsx
{isOverview ? (
  <main className="flex-1 flex flex-col overflow-hidden min-w-0">
    <OverviewPage />
  </main>
) : (
  <div className="flex-1 flex flex-col overflow-hidden min-w-0">
    ...portfolio detail...
  </div>
)}
```
Change to:
```tsx
{isLogs ? (
  <main className="flex-1 flex flex-col overflow-hidden min-w-0">
    <LogsPage />
  </main>
) : isOverview ? (
  <main className="flex-1 flex flex-col overflow-hidden min-w-0">
    <OverviewPage />
  </main>
) : (
  <div className="flex-1 flex flex-col overflow-hidden min-w-0">
    ...portfolio detail (unchanged)...
  </div>
)}
```

- [ ] **Step 2: Add LOGS button to TopBar.tsx**

Open `dashboard/src/components/TopBar.tsx`.

**Add import** at the top:
```tsx
import { usePortfolioStore } from "../lib/store";
```
(Skip this if it's already imported — check the existing imports.)

**Find the right section** of the TopBar (around lines 319–335). It contains the EmergencyClose and ModeToggle components. The structure looks like:
```tsx
{/* right */}
<div className="flex items-center gap-2">
  {/* stale alerts, price failures, loading spinner */}
  <EmergencyClose ... />
  <ModeToggle ... />
</div>
```

**Add the LOGS button** immediately before `<EmergencyClose`:
```tsx
<LogsButton />
```

**Add the LogsButton component** near the top of the file, after the existing sub-components (around line 240, before the main `TopBar` function):

```tsx
function LogsButton() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const isActive = portfolioId === "logs";

  return (
    <button
      onClick={() => setPortfolio(isActive ? "overview" : "logs")}
      className={`${BTN_H} px-3 rounded font-mono text-xs tracking-wider transition-colors ${
        isActive
          ? "bg-zinc-700 text-zinc-200"
          : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
      }`}
    >
      LOGS
    </button>
  );
}
```

Note: `BTN_H` is already defined in TopBar.tsx (line 18) as a height class. Use it for consistency.

Clicking LOGS when already on the logs page navigates back to overview.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -10
```

Expected: no errors.

- [ ] **Step 4: End-to-end smoke test**

Ensure the API is running (check with `curl -s http://localhost:8001/api/health`). Then open the dashboard at `http://localhost:5173`.

Verify:
1. LOGS button appears in the TopBar between VIX and CLOSE ALL
2. Clicking LOGS renders the LogsPage (shows "SYSTEM LOGS" header)
3. Pipeline grid shows 14 rows with `—` for all jobs (no logs yet)
4. Timeline shows empty state message
5. Narrative section shows "No briefing yet" or loads a narrative
6. Clicking LOGS again navigates back to overview
7. Switching to a portfolio via PortfolioSwitcher works normally
8. No console errors about invalid API calls to `/api/logs/state`

- [ ] **Step 5: Commit and push**

```bash
git add dashboard/src/App.tsx dashboard/src/components/TopBar.tsx
git commit -m "feat: wire LogsPage into App routing and TopBar navigation"
git push
```

Restart API to pick up backend changes:
```bash
pkill -f "uvicorn api.main:app" 2>/dev/null; sleep 1
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate
DISABLE_SOCIAL=true nohup uvicorn api.main:app --host 0.0.0.0 --port 8001 > /tmp/mcr_api.log 2>&1 &
sleep 4 && curl -s http://localhost:8001/api/health
```
