"""Analysis and execution endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from api.deps import serialize

from unified_analysis import run_unified_analysis, execute_approved_actions

router = APIRouter(prefix="/api/{portfolio_id}")

_PORTFOLIOS_DIR = Path(__file__).parent.parent.parent / "data" / "portfolios"


def _analysis_file(portfolio_id: str) -> Path:
    return _PORTFOLIOS_DIR / portfolio_id / ".last_analysis.json"


@router.post("/analyze")
def analyze(portfolio_id: str):
    """Run unified analysis (dry run). Returns proposed buys/sells with AI review."""
    try:
        result = run_unified_analysis(dry_run=True, portfolio_id=portfolio_id)
        analysis_file = _analysis_file(portfolio_id)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
def execute(portfolio_id: str):
    """Execute approved actions from the last analysis run."""
    analysis_file = _analysis_file(portfolio_id)
    if not analysis_file.exists():
        raise HTTPException(status_code=400, detail="No analysis to execute. Run analyze first.")

    # Concurrency guard: atomically claim the analysis by renaming it.
    # Only one caller wins; concurrent /execute hits get 409. On exception,
    # we rename back so the user can retry.
    executing_file = analysis_file.with_name(".executing.json")
    try:
        analysis_file.rename(executing_file)
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="Already executing or no analysis available.")

    try:
        with open(executing_file) as f:
            last_analysis = json.load(f)
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
        raise HTTPException(status_code=500, detail=str(e))
