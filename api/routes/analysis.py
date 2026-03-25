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
        with open(analysis_file, "w") as f:
            json.dump(result, f, default=str)
        return serialize(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
def execute(portfolio_id: str):
    """Execute approved actions from the last analysis run."""
    analysis_file = _analysis_file(portfolio_id)
    if not analysis_file.exists():
        raise HTTPException(status_code=400, detail="No analysis to execute. Run analyze first.")
    try:
        with open(analysis_file) as f:
            last_analysis = json.load(f)
        result = execute_approved_actions(last_analysis, portfolio_id=portfolio_id)
        analysis_file.unlink(missing_ok=True)
        return serialize(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
