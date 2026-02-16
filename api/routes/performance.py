"""Performance, analytics, and learning endpoints."""

from fastapi import APIRouter
from api.deps import serialize

from strategy_health import get_strategy_health
from attribution import get_daily_attribution
from analytics import PortfolioAnalytics
from factor_learning import FactorLearner, get_weight_suggestions
from portfolio_state import load_portfolio_state

router = APIRouter(prefix="/api/{portfolio_id}")


@router.get("/performance")
def performance(portfolio_id: str):
    """Strategy health grade, attribution, analytics metrics."""
    _state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    health = get_strategy_health()
    attribution = get_daily_attribution()
    metrics = PortfolioAnalytics().calculate_all_metrics()

    return {
        "health": serialize(health),
        "attribution": serialize(attribution),
        "metrics": serialize(metrics),
    }


@router.get("/learning")
def learning(portfolio_id: str):
    """Factor learning summary and weight suggestions."""
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    regime = state.regime.value if state.regime else None

    learner = FactorLearner(portfolio_id=portfolio_id)
    summary = learner.get_factor_summary()
    suggestions = get_weight_suggestions(regime, portfolio_id=portfolio_id)

    return {
        "factor_summary": serialize(summary),
        "weight_suggestions": serialize(suggestions),
    }
