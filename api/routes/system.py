"""System health and logs endpoints."""
import csv
import logging
from datetime import date as _date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

from log_parser import build_day_summary

router = APIRouter(prefix="/api/system")

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


@router.get("/pipeline-health")
def pipeline_health():
    """Return latest pipeline execution status for all portfolios."""
    import json
    status_dir = Path(__file__).parent.parent.parent / "data" / "pipeline_status"
    if not status_dir.exists():
        return {"portfolios": [], "anomalies": []}

    results = []
    anomalies = []
    for f in sorted(status_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            results.append(data)
            # Check for anomalies
            if data.get("ai_mode") == "mechanical_fallback":
                anomalies.append(f"{data['portfolio_id']}: Claude fallback activated")
            if data.get("executed", {}).get("buys", 0) == 0 and data.get("proposed", {}).get("buys", 0) > 0:
                anomalies.append(f"{data['portfolio_id']}: all buys dropped")
        except Exception:
            pass

    return {"portfolios": results, "anomalies": anomalies}


@router.get("/logs")
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
        except Exception as e:
            logging.warning("Failed to build day summary for %s: %s", date_str, e)
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
        except Exception as e:
            logging.warning("Failed to read transactions for %s: %s", portfolio_dir.name, e)
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
        except Exception as e:
            logging.warning("Failed to read snapshots for %s: %s", portfolio_dir.name, e)
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


@router.get("/narrative")
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
    except Exception as e:
        logging.warning("Failed to build day summary for narrative %s: %s", target_date, e)
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
        logging.warning("Claude narrative call failed for %s: %s", target_date, e)
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
