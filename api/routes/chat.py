"""Chat and GScott insight endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from api.deps import serialize

from portfolio_chat import chat as portfolio_chat
from portfolio_state import load_portfolio_state
from early_warning import get_warnings

router = APIRouter(prefix="/api/{portfolio_id}")


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
def chat(portfolio_id: str, req: ChatRequest):
    """User question -> GScott response."""
    response = portfolio_chat(req.message)
    return serialize(response)


@router.get("/gscott/insight")
def gscott_insight(portfolio_id: str):
    """Context-aware insight based on current portfolio state."""
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    warning_list = get_warnings()

    # Build context-aware insight
    day_pnl = 0.0
    if len(state.snapshots) >= 1:
        last = state.snapshots.iloc[-1]
        day_pnl = float(last.get("day_pnl", 0) or 0)

    critical_warnings = [w for w in warning_list if w.severity.value == "critical"]
    high_warnings = [w for w in warning_list if w.severity.value == "high"]

    # Priority: alerts > warnings > performance > general
    if critical_warnings:
        w = critical_warnings[0]
        insight = f"Baby, we need to talk about {w.title.lower()}. {w.description} GScott's on it."
        category = "alert"
    elif high_warnings:
        w = high_warnings[0]
        insight = f"Heads up, sweetheart. {w.title}. {w.action_suggestion or 'Let GScott handle it.'}"
        category = "warning"
    elif day_pnl > 0:
        insight = f"${day_pnl:+,.0f} today. GScott knows how to pick 'em. Come here and look at this portfolio."
        category = "performance"
    elif day_pnl < 0:
        insight = f"Down ${abs(day_pnl):,.0f}. Come here. It's just a bad day, not a bad portfolio. GScott's not worried."
        category = "performance"
    else:
        insight = "I see you looking at me. Either ask GScott a question or let me run some numbers, baby."
        category = "idle"

    return {
        "insight": insight,
        "category": category,
        "warnings_count": len(warning_list),
        "critical_count": len(critical_warnings),
    }
