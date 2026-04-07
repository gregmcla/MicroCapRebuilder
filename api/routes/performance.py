"""Performance, analytics, and learning endpoints."""

from fastapi import APIRouter
from api.deps import serialize

from strategy_health import get_strategy_health
from attribution import get_daily_attribution
from analytics import PortfolioAnalytics
from factor_learning import FactorLearner, get_weight_suggestions
from generate_report import generate_report

router = APIRouter(prefix="/api/{portfolio_id}")


@router.get("/performance")
def performance(portfolio_id: str):
    """Strategy health grade, attribution, analytics metrics."""
    health = get_strategy_health(portfolio_id=portfolio_id)
    attribution = get_daily_attribution()
    metrics = PortfolioAnalytics(portfolio_id=portfolio_id).calculate_all_metrics()

    return {
        "health": serialize(health),
        "attribution": serialize(attribution),
        "metrics": serialize(metrics),
    }


@router.get("/report")
def daily_report(portfolio_id: str):
    """Generate and return the daily text report."""
    text = generate_report(portfolio_id=portfolio_id)
    return {"text": text}


@router.get("/learning")
def learning(portfolio_id: str):
    """Factor learning summary and weight suggestions."""
    from portfolio_state import load_portfolio_state
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    regime = state.regime.value if state.regime else None

    learner = FactorLearner(portfolio_id=portfolio_id)
    summary = learner.get_factor_summary()
    suggestions = get_weight_suggestions(regime, portfolio_id=portfolio_id)

    return {
        "factor_summary": serialize(summary),
        "weight_suggestions": serialize(suggestions),
    }
