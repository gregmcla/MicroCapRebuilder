"""Stock discovery/scan endpoints."""

import concurrent.futures
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from api.deps import serialize

from shared_universe import SharedUniverse

router = APIRouter(prefix="/api/{portfolio_id}")

# Top-level (non-portfolio-scoped) discovery routes
global_router = APIRouter(prefix="/api")

# In-memory job store: portfolio_id -> job dict
_scan_jobs: Dict[str, Dict[str, Any]] = {}

SCAN_TIMEOUT_SECONDS = 720  # 12 minutes — covers 3000-ticker cold-cache scans


def _run_scan_job(portfolio_id: str) -> None:
    """Run scan in a background thread and update the job store."""
    from watchlist_manager import update_watchlist

    job = _scan_jobs[portfolio_id]
    start = datetime.now(timezone.utc)

    def _do_scan():
        return update_watchlist(run_discovery=True, portfolio_id=portfolio_id)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_scan)
            try:
                stats = future.result(timeout=SCAN_TIMEOUT_SECONDS)
                elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                if stats and isinstance(stats, dict):
                    stats["elapsed_seconds"] = round(elapsed, 1)
                job["status"] = "complete"
                job["result"] = stats
            except concurrent.futures.TimeoutError:
                job["status"] = "error"
                job["error"] = f"Scan timed out after {SCAN_TIMEOUT_SECONDS}s — try again (cache will be warmer)"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
    finally:
        job["finished_at"] = datetime.now(timezone.utc).isoformat()


@router.post("/scan")
def start_scan(portfolio_id: str):
    """Start a watchlist discovery scan in the background. Returns immediately."""
    existing = _scan_jobs.get(portfolio_id)
    if existing and existing["status"] == "running":
        return {"status": "running", "message": "Scan already in progress"}

    _scan_jobs[portfolio_id] = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
        "error": None,
        "finished_at": None,
    }

    thread = threading.Thread(target=_run_scan_job, args=(portfolio_id,), daemon=True)
    thread.start()

    return {"status": "running", "message": "Scan started"}


@router.get("/watchlist")
def get_watchlist(portfolio_id: str):
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


@router.get("/scan/status")
def get_scan_status(portfolio_id: str):
    """Poll the status of the last scan for this portfolio."""
    job = _scan_jobs.get(portfolio_id)
    if not job:
        return {"status": "idle"}
    return {
        "status": job["status"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "result": job["result"],
        "error": job["error"],
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
