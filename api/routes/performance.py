"""Performance, analytics, and learning endpoints."""

from fastapi import APIRouter
from api.deps import serialize

from strategy_health import get_strategy_health
from attribution import get_daily_attribution
from analytics import PortfolioAnalytics
from factor_learning import FactorLearner, get_weight_suggestions
from portfolio_state import load_portfolio_state

router = APIRouter(prefix="/api")


@router.get("/performance")
def performance():
    """Strategy health grade, attribution, analytics metrics."""
    health = get_strategy_health()
    attribution = get_daily_attribution()
    metrics = PortfolioAnalytics().calculate_all_metrics()

    return {
        "health": serialize(health),
        "attribution": serialize(attribution),
        "metrics": serialize(metrics),
    }


@router.get("/learning")
def learning():
    """Factor learning summary and weight suggestions."""
    state = load_portfolio_state(fetch_prices=False)
    regime = state.regime.value if state.regime else None

    learner = FactorLearner()
    summary = learner.get_factor_summary()
    suggestions = get_weight_suggestions(regime)

    return {
        "factor_summary": serialize(summary),
        "weight_suggestions": serialize(suggestions),
    }
