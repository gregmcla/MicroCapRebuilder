"""Risk and warnings endpoints."""

from fastapi import APIRouter
from api.deps import serialize

from risk_scoreboard import get_risk_scoreboard
from early_warning import get_warnings

router = APIRouter(prefix="/api/{portfolio_id}")


@router.get("/risk")
def risk(portfolio_id: str):
    """Risk scoreboard: overall score, components, recommendations."""
    scoreboard = get_risk_scoreboard(portfolio_id=portfolio_id)
    return serialize(scoreboard)


@router.get("/warnings")
def warnings(portfolio_id: str):
    """Early warnings: regime shifts, losing streaks, concentration alerts."""
    warning_list = get_warnings(portfolio_id=portfolio_id)
    return serialize(warning_list)
