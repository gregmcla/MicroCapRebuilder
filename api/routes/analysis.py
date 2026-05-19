"""Analysis and execution endpoints."""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from api.deps import serialize, validate_portfolio_id

from unified_analysis import run_unified_analysis, execute_approved_actions


class ExecuteRequest(BaseModel):
    selected_tickers: Optional[list[str]] = None

router = APIRouter(prefix="/api/{portfolio_id}")

_PORTFOLIOS_DIR = Path(__file__).parent.parent.parent / "data" / "portfolios"

_VALID_MODES = {"full", "buys_only", "sells_only"}


def _analysis_file(portfolio_id: str, mode: str = "full") -> Path:
    """Resolve the slot file path for a given mode."""
    base = _PORTFOLIOS_DIR / portfolio_id
    if mode == "full":
        return base / ".last_analysis.json"
    if mode == "buys_only":
        return base / ".last_analysis.buys.json"
    if mode == "sells_only":
        return base / ".last_analysis.sells.json"
    raise ValueError(f"invalid mode: {mode}")


def _executing_file(portfolio_id: str, mode: str = "full") -> Path:
    """Resolve the per-mode executing lock path."""
    base = _PORTFOLIOS_DIR / portfolio_id
    if mode == "full":
        return base / ".executing.json"
    if mode == "buys_only":
        return base / ".executing.buys.json"
    if mode == "sells_only":
        return base / ".executing.sells.json"
    raise ValueError(f"invalid mode: {mode}")


def _validate_mode(mode: str) -> str:
    if mode not in _VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid mode '{mode}' (allowed: {sorted(_VALID_MODES)})",
        )
    return mode


@router.post("/analyze")
def analyze(
    portfolio_id: str = Depends(validate_portfolio_id),
    mode: str = Query(default="full"),
):
    """Run unified analysis (dry run). Mode controls scope and slot file."""
    mode = _validate_mode(mode)
    try:
        result = run_unified_analysis(dry_run=True, portfolio_id=portfolio_id, mode=mode)
        analysis_file = _analysis_file(portfolio_id, mode)
        serialized = serialize(result)
        # Atomic write: tmp + replace prevents corruption if process is killed mid-write.
        # A subsequent /execute reading a partial JSON would 500 or act on garbage.
        tmp_file = analysis_file.with_name(analysis_file.name + ".tmp")
        try:
            with open(tmp_file, "w") as f:
                json.dump(serialized, f)
            tmp_file.replace(analysis_file)
        except Exception:
            tmp_file.unlink(missing_ok=True)
            raise
        return serialized
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
def execute(
    portfolio_id: str = Depends(validate_portfolio_id),
    mode: str = Query(default="full"),
    body: Optional[ExecuteRequest] = Body(None),
):
    """Execute approved actions from the last analysis run for the given mode."""
    mode = _validate_mode(mode)
    analysis_file = _analysis_file(portfolio_id, mode)
    if not analysis_file.exists():
        raise HTTPException(
            status_code=400,
            detail=f"No analysis to execute for mode={mode}. Run analyze first.",
        )

    # Concurrency guard: atomically claim the analysis by renaming it.
    # Only one caller wins; concurrent /execute hits get 409. On exception,
    # we rename back so the user can retry. Each mode has its own lock file.
    executing_file = _executing_file(portfolio_id, mode)
    try:
        analysis_file.rename(executing_file)
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="Already executing or no analysis available.")

    try:
        with open(executing_file) as f:
            last_analysis = json.load(f)

        # Cherry-pick filter: only execute the tickers the user selected.
        # Only applies when the caller sends selected_tickers (buys/sells-only modes).
        if body and body.selected_tickers is not None:
            selected = set(body.selected_tickers)
            last_analysis["approved"] = [
                a for a in last_analysis.get("approved", [])
                if a.get("original", {}).get("ticker") in selected
            ]
            last_analysis["modified"] = [
                a for a in last_analysis.get("modified", [])
                if a.get("original", {}).get("ticker") in selected
            ]

        result = execute_approved_actions(last_analysis, portfolio_id=portfolio_id)
        executing_file.unlink(missing_ok=True)
        return serialize(result)
    except Exception as e:
        # Restore the analysis file so the user can retry after fixing the issue
        try:
            executing_file.rename(analysis_file)
        except Exception as restore_exc:
            # Couldn't restore — leave the executing file in place for manual recovery
            print(f"[execute] Could not restore analysis file after failure: {restore_exc}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))
