"""Risk and warnings endpoints."""

from fastapi import APIRouter
from api.deps import serialize

from risk_scoreboard import get_risk_scoreboard
from early_warning import get_warnings
from portfolio_state import load_portfolio_state

router = APIRouter(prefix="/api/{portfolio_id}")


@router.get("/risk")
def risk(portfolio_id: str):
    """Risk scoreboard: overall score, components, recommendations."""
    # Load state for this portfolio so backing functions use correct data
    _state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    scoreboard = get_risk_scoreboard()
    return serialize(scoreboard)


@router.get("/warnings")
def warnings(portfolio_id: str):
    """Early warnings: regime shifts, losing streaks, concentration alerts."""
    _state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    warning_list = get_warnings()
    return serialize(warning_list)
