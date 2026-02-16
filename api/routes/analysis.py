"""Analysis and execution endpoints."""

from fastapi import APIRouter, HTTPException
from api.deps import serialize

from unified_analysis import run_unified_analysis, execute_approved_actions

router = APIRouter(prefix="/api/{portfolio_id}")

# Store the last analysis result per portfolio
_last_analysis: dict[str, dict] = {}


@router.post("/analyze")
def analyze(portfolio_id: str):
    """Run unified analysis (dry run). Returns proposed buys/sells with AI review."""
    try:
        result = run_unified_analysis(dry_run=True, portfolio_id=portfolio_id)
        _last_analysis[portfolio_id] = result
        return serialize(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
def execute(portfolio_id: str):
    """Execute approved actions from the last analysis run."""
    if portfolio_id not in _last_analysis or _last_analysis[portfolio_id] is None:
        raise HTTPException(status_code=400, detail="No analysis to execute. Run analyze first.")
    try:
        result = execute_approved_actions(_last_analysis[portfolio_id], portfolio_id=portfolio_id)
        _last_analysis[portfolio_id] = None
        return serialize(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
