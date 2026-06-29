"""Stock discovery/scan endpoints."""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from api.deps import serialize, validate_portfolio_id

from shared_universe import SharedUniverse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/{portfolio_id}")

# Top-level (non-portfolio-scoped) discovery routes
global_router = APIRouter(prefix="/api")

# In-memory job store: portfolio_id -> job dict
# Lock protects the dict against the request thread + background scan thread
# both mutating job state without coordination.
_scan_jobs: Dict[str, Dict[str, Any]] = {}
_scan_jobs_lock = threading.Lock()

# Serialize actual discovery execution across portfolios. Concurrent multi-hundred
# -ticker scans stampede Yahoo into throttling, which used to cascade every
# per-ticker call into its 5-60s timeout and blow the budget. Running one scan at
# a time (override with SCAN_CONCURRENCY) keeps the rate budget sane; scans are now
# ~10-15s each so queuing is cheap.
_scan_semaphore = threading.Semaphore(int(os.environ.get("SCAN_CONCURRENCY", "1")))
# Don't let a queued scan wait behind a wedged one forever.
_SEM_ACQUIRE_TIMEOUT = 900


def _run_scan_job(portfolio_id: str) -> None:
    """Run scan in a background thread and update the job store."""
    from watchlist_manager import update_watchlist

    with _scan_jobs_lock:
        job = _scan_jobs[portfolio_id]
    start = datetime.now(timezone.utc)

    # Gate on the global scan semaphore so portfolios don't stampede Yahoo.
    acquired = _scan_semaphore.acquire(timeout=_SEM_ACQUIRE_TIMEOUT)
    if not acquired:
        with _scan_jobs_lock:
            job["status"] = "error"
            job["error"] = "Timed out waiting for another scan to finish"
            job["finished_at"] = datetime.now(timezone.utc).isoformat()
        return

    try:
        stats = update_watchlist(run_discovery=True, portfolio_id=portfolio_id)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        if stats and isinstance(stats, dict):
            stats["elapsed_seconds"] = round(elapsed, 1)
        with _scan_jobs_lock:
            job["status"] = "complete"
            job["result"] = stats

        # Send Telegram notification (non-fatal — dashboard scans are single-portfolio)
        try:
            from telegram_notifier import send_single_portfolio_scan
            send_single_portfolio_scan(portfolio_id)
        except Exception as e:
            logger.warning("scan telegram notify failed for %s: %s", portfolio_id, e)
    except Exception as e:
        logger.warning("scan failed for %s: %s", portfolio_id, e)
        with _scan_jobs_lock:
            job["status"] = "error"
            job["error"] = str(e)
    finally:
        _scan_semaphore.release()
        with _scan_jobs_lock:
            job["finished_at"] = datetime.now(timezone.utc).isoformat()


@router.post("/scan")
def start_scan(portfolio_id: str = Depends(validate_portfolio_id)):
    """Start a watchlist discovery scan in the background. Returns immediately."""
    # Lock scope: just the check-and-create. Lock is released BEFORE the scan
    # thread starts so the scan itself runs without holding it.
    with _scan_jobs_lock:
        existing = _scan_jobs.get(portfolio_id)
        if existing and existing.get("status") == "running":
            return {"status": "running", "message": "Scan already in progress"}
        # Refuse a duplicate while a prior scan's thread is still alive (e.g. it was
        # marked errored/timed-out but hasn't actually stopped) — two scans of one
        # portfolio would double the Yahoo load and race their final saves.
        prior = existing.get("thread") if existing else None
        if prior is not None and prior.is_alive():
            return {"status": "running", "message": "Previous scan still finishing"}

        job = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
            "error": None,
            "finished_at": None,
            "thread": None,
        }
        _scan_jobs[portfolio_id] = job

    thread = threading.Thread(target=_run_scan_job, args=(portfolio_id,), daemon=True)
    with _scan_jobs_lock:
        job["thread"] = thread
    thread.start()

    return {"status": "running", "message": "Scan started"}


@router.get("/watchlist")
def get_watchlist(portfolio_id: str = Depends(validate_portfolio_id)):
    """Return active watchlist candidates, sorted by blended rank (score + 0.3*delta) desc."""
    data_dir = Path(__file__).parent.parent.parent / "data" / "portfolios" / portfolio_id
    wl_path = data_dir / "watchlist.jsonl"
    if not wl_path.exists():
        return {"candidates": [], "total": 0}

    candidates = []
    with open(wl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("status", "ACTIVE") == "ACTIVE":
                    score = entry.get("discovery_score", 0) or 0
                    delta = entry.get("score_delta", 0.0) or 0.0
                    candidates.append({
                        "ticker": entry.get("ticker", ""),
                        "score": score,
                        "score_delta": delta,
                        "blended": round(score + 0.3 * delta, 2),
                        "sector": entry.get("sector", ""),
                        "source": entry.get("source", ""),
                        "notes": entry.get("notes", ""),
                        "added_date": entry.get("added_date", ""),
                    })
            except Exception:
                continue

    # Sort by blended rank (score + 0.3 * delta), descending
    candidates.sort(key=lambda x: x["blended"], reverse=True)
    return {"candidates": candidates, "total": len(candidates)}


def _watchlist_last_scanned(portfolio_id: str) -> str | None:
    """Return ISO timestamp of the last completed scan, from watchlist.jsonl mtime."""
    try:
        wl = Path(__file__).parent.parent.parent / "data" / "portfolios" / portfolio_id / "watchlist.jsonl"
        if wl.exists():
            import time as _time
            mtime = wl.stat().st_mtime
            return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except Exception:
        pass
    return None


@router.get("/scan/status")
def get_scan_status(portfolio_id: str = Depends(validate_portfolio_id)):
    """Poll the status of the last scan for this portfolio."""
    last_scanned = _watchlist_last_scanned(portfolio_id)
    with _scan_jobs_lock:
        job = _scan_jobs.get(portfolio_id)
        if not job:
            return {"status": "idle", "last_scanned": last_scanned}
        # Snapshot the dict under the lock so the response is internally consistent
        return {
            "status": job["status"],
            "started_at": job["started_at"],
            "finished_at": job["finished_at"],
            "result": job["result"],
            "error": job["error"],
            "last_scanned": last_scanned,
        }


@global_router.get("/convergent-signals")
def get_convergent_signals(
    min_portfolios: int = Query(default=2, ge=1, description="Minimum number of portfolios that must have discovered the ticker"),
):
    """Get tickers discovered by multiple portfolios (cross-portfolio convergence signal)."""
    try:
        shared = SharedUniverse()
        convergent = shared.get_convergent_tickers(min_portfolios=min_portfolios)

        # Sort by portfolio_count (most convergent first), then by score
        sorted_signals = sorted(
            convergent.items(),
            key=lambda x: (x[1]["portfolio_count"], x[1]["best_score"]),
            reverse=True,
        )

        return serialize({
            "convergent_tickers": [
                {"ticker": ticker, **data}
                for ticker, data in sorted_signals
            ],
            "total": len(sorted_signals),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
