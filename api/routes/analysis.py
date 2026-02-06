"""Analysis and execution endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.deps import serialize

from unified_analysis import run_unified_analysis, execute_approved_actions

router = APIRouter(prefix="/api")

# Store the last analysis result in memory for execute to use
_last_analysis = {"result": None}


@router.post("/analyze")
def analyze():
    """Run unified analysis (dry run). Returns proposed buys/sells with AI review."""
    try:
        result = run_unified_analysis(dry_run=True)
        _last_analysis["result"] = result
        return serialize(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
def execute():
    """Execute approved actions from the last analysis run."""
    if _last_analysis["result"] is None:
        raise HTTPException(status_code=400, detail="No analysis to execute. Run /api/analyze first.")
    try:
        result = execute_approved_actions(_last_analysis["result"])
        _last_analysis["result"] = None
        return serialize(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
