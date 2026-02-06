"""Risk and warnings endpoints."""

from fastapi import APIRouter
from api.deps import serialize

from risk_scoreboard import get_risk_scoreboard
from early_warning import get_warnings

router = APIRouter(prefix="/api")


@router.get("/risk")
def risk():
    """Risk scoreboard: overall score, components, recommendations."""
    scoreboard = get_risk_scoreboard()
    return serialize(scoreboard)


@router.get("/warnings")
def warnings():
    """Early warnings: regime shifts, losing streaks, concentration alerts."""
    warning_list = get_warnings()
    return serialize(warning_list)
