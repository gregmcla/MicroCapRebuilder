"""Portfolio Intelligence Brief endpoints — aggregate data, AI audit, and chat."""

import json
import logging
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from api.deps import serialize

from portfolio_state import load_portfolio_state
from strategy_health import get_strategy_health
from analytics import PortfolioAnalytics
from factor_learning import FactorLearner, get_weight_suggestions
from risk_scoreboard import get_risk_scoreboard
from early_warning import get_warnings

router = APIRouter(prefix="/api/{portfolio_id}")

DATA_DIR = Path(__file__).parent.parent.parent / "data"

# ── Audit brief cache — keyed by portfolio_id, expires every 10 min ──────────
_audit_cache: dict[str, dict] = {}
_AUDIT_CACHE_TTL = 600  # seconds


def _safe_float(v, default=0.0):
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return default


def _compute_sector_breakdown(positions) -> dict:
    """Return {sector: {count, value, pct}} from a positions DataFrame."""
    if positions is None or len(positions) == 0:
        return {}
    total_value = _safe_float(positions["market_value"].sum()) if "market_value" in positions.columns else 0.0
    breakdown: dict[str, dict] = {}
    for _, row in positions.iterrows():
        sector = str(row.get("sector", "Unknown") or "Unknown")
        val = _safe_float(row.get("market_value", 0))
        if sector not in breakdown:
            breakdown[sector] = {"count": 0, "value": 0.0, "pct": 0.0}
        breakdown[sector]["count"] += 1
        breakdown[sector]["value"] += val
    if total_value > 0:
        for s in breakdown:
            breakdown[s]["pct"] = round(breakdown[s]["value"] / total_value * 100, 1)
    return breakdown


def _compute_avg_hold_days(transactions) -> float:
    """Compute average days held across completed trades (buy → sell pairs)."""
    if transactions is None or transactions.empty:
        return 0.0
    buys: dict[str, list] = {}
    hold_days: list[float] = []
    for _, tx in transactions.sort_values("date").iterrows():
        ticker = str(tx.get("ticker", ""))
        action = str(tx.get("action", ""))
        tx_date = str(tx.get("date", ""))[:10]
        if action == "BUY":
            buys.setdefault(ticker, []).append(tx_date)
        elif action == "SELL" and ticker in buys and buys[ticker]:
            buy_date = buys[ticker].pop(0)
            try:
                delta = (datetime.fromisoformat(tx_date) - datetime.fromisoformat(buy_date)).days
                hold_days.append(max(0, delta))
            except Exception:
                pass
    return round(sum(hold_days) / len(hold_days), 1) if hold_days else 0.0


def _most_traded_tickers(transactions, top_n: int = 8) -> list[dict]:
    if transactions is None or transactions.empty:
        return []
    counts: dict[str, int] = {}
    for _, tx in transactions.iterrows():
        ticker = str(tx.get("ticker", ""))
        if ticker:
            counts[ticker] = counts.get(ticker, 0) + 1
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"ticker": t, "count": c} for t, c in sorted_items[:top_n]]


def _factor_deltas(config: dict, learning_factors: list) -> dict[str, float]:
    """Compute current_weight - default_weight per factor."""
    defaults = config.get("scoring", {}).get("default_weights", {})
    deltas: dict[str, float] = {}
    for entry in learning_factors:
        factor = entry.get("factor", "")
        # The "current" weight isn't stored explicitly in learning data;
        # use default weights as baseline and show 0 delta until factor learning fires
        deltas[factor] = 0.0
    for factor, weight in defaults.items():
        deltas[factor] = deltas.get(factor, 0.0)
    return deltas


def _positions_near_stop(positions, threshold_pct: float = 5.0) -> list[str]:
    """Return tickers where (current_price - stop_loss) / current_price < threshold."""
    near: list[str] = []
    if positions is None or len(positions) == 0:
        return near
    for _, row in positions.iterrows():
        price = _safe_float(row.get("current_price", 0))
        stop = _safe_float(row.get("stop_loss", 0))
        if price > 0 and stop > 0:
            dist_pct = (price - stop) / price * 100
            if dist_pct < threshold_pct:
                near.append(str(row.get("ticker", "")))
    return near


def _avg_position_age(positions) -> float:
    if positions is None or len(positions) == 0:
        return 0.0
    today = date.today()
    ages: list[float] = []
    for _, row in positions.iterrows():
        entry = str(row.get("entry_date", ""))[:10]
        try:
            delta = (today - datetime.fromisoformat(entry).date()).days
            ages.append(max(0, delta))
        except Exception:
            pass
    return round(sum(ages) / len(ages), 1) if ages else 0.0


def _build_audit_context(portfolio_id: str) -> str:
    """Assemble a rich text context block for the AI audit prompt."""
    try:
        state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
        config = state.config or {}

        # Strategy DNA
        dna = config.get("strategy_dna", "") or config.get("strategy", {}).get("ai_prompt", "") or ""
        portfolio_name = config.get("name", portfolio_id)
        universe = config.get("universe_preset", config.get("universe", {}).get("preset", "unknown"))

        # Performance
        try:
            metrics = PortfolioAnalytics(portfolio_id=portfolio_id).calculate_all_metrics()
            sharpe = _safe_float(getattr(metrics, "sharpe_ratio", 0))
            max_dd = _safe_float(getattr(metrics, "max_drawdown_pct", 0))
            total_return = _safe_float(getattr(metrics, "total_return_pct", 0))
            cagr = _safe_float(getattr(metrics, "cagr_pct", 0))
        except Exception:
            sharpe, max_dd, total_return, cagr = 0.0, 0.0, 0.0, 0.0

        # Strategy health
        try:
            health = get_strategy_health(portfolio_id=portfolio_id)
            grade = health.grade
            diagnosis = health.diagnosis
            struggling = health.what_struggling
            recommendations = health.recommendations
        except Exception:
            grade, diagnosis, struggling, recommendations = "?", "", [], []

        # Risk
        try:
            risk = get_risk_scoreboard(portfolio_id=portfolio_id)
            risk_score = risk.overall_score
            risk_level = risk.risk_level
        except Exception:
            risk_score, risk_level = 0, "unknown"

        # Warnings
        try:
            warnings = get_warnings(portfolio_id=portfolio_id)
            active_warnings = [f"[{w.severity.upper()}] {w.title}: {w.description}" for w in warnings[:5]]
        except Exception:
            active_warnings = []

        # Trade stats
        txns = state.transactions
        avg_hold = _compute_avg_hold_days(txns)
        most_traded = _most_traded_tickers(txns, top_n=5)

        # Position composition
        positions = state.positions
        sector_breakdown = _compute_sector_breakdown(positions)
        near_stop = _positions_near_stop(positions)
        num_positions = state.num_positions
        cash_pct = round((state.cash / state.total_equity * 100) if state.total_equity > 0 else 0, 1)
        deployed_pct = round(100 - cash_pct, 1)

        # Factor learning
        try:
            learner = FactorLearner(portfolio_id=portfolio_id)
            factor_summary = learner.get_factor_summary()
            factor_factors = factor_summary.factors if hasattr(factor_summary, "factors") else []
            factor_lines = "\n".join(
                f"  {f.factor}: win_rate={f.win_rate:.0%}, trend={f.trend}, trades={f.total_trades}"
                for f in factor_factors
            ) or "  No factor data yet (need more trades)"
        except Exception:
            factor_lines = "  No factor data yet"

        # Config key params
        stop_pct = config.get("default_stop_loss_pct", "?")
        target_pct = config.get("default_take_profit_pct", "?")
        risk_per_trade = config.get("risk_per_trade_pct", "?")
        max_pos = config.get("max_positions", "?")
        max_pos_pct = config.get("max_position_pct", "?")

        # Sector concentration
        sector_lines = "\n".join(
            f"  {s}: {v['count']} positions, {v['pct']:.1f}% of portfolio"
            for s, v in sorted(sector_breakdown.items(), key=lambda x: x[1]["pct"], reverse=True)
        ) or "  No positions"

        context = f"""PORTFOLIO: {portfolio_name} (id: {portfolio_id})
UNIVERSE: {universe}
STRATEGY DNA: {dna or "Not set"}

CONFIGURATION:
  Stop loss: {stop_pct}% | Take profit: {target_pct}% | Risk/trade: {risk_per_trade}%
  Max positions: {max_pos} | Max position size: {max_pos_pct}%

PERFORMANCE:
  Total return: {total_return:+.2f}% | CAGR: {cagr:.2f}%
  Sharpe ratio: {sharpe:.2f} | Max drawdown: {max_dd:.2f}%
  Strategy grade: {grade} | Diagnosis: {diagnosis}

CURRENT PORTFOLIO:
  {num_positions} positions | {deployed_pct}% deployed | {cash_pct}% cash
  Avg position age: {_avg_position_age(positions):.1f} days
  Positions near stop loss: {near_stop or "none"}

SECTOR BREAKDOWN:
{sector_lines}

TRADE STATISTICS:
  Avg hold time: {avg_hold:.1f} days
  Most traded: {", ".join(f"{t['ticker']}({t['count']})" for t in most_traded) or "none yet"}

FACTOR INTELLIGENCE:
{factor_lines}

ACTIVE RISK WARNINGS ({len(active_warnings)}):
{chr(10).join(active_warnings) or "  None"}
  Overall risk score: {risk_score}/100 ({risk_level})

STRATEGY HEALTH:
  What's struggling: {"; ".join(struggling) or "nothing flagged"}
  Recommendations: {"; ".join(recommendations[:3]) or "none"}
""".strip()

        return context

    except Exception as e:
        logging.warning("[intelligence] context build failed for %s: %s", portfolio_id, e)
        return f"Portfolio: {portfolio_id}\n(Context build error: {e})"


def _build_audit_prompt(context: str) -> str:
    return f"""You are GScott, an expert portfolio analyst with deep quantitative finance knowledge. You have been asked to conduct a thorough Portfolio Audit Brief for the following portfolio.

{context}

---

Write a Portfolio Audit Brief covering these areas:

1. **DNA vs Reality**: Is the portfolio actually executing its stated strategy DNA? Identify any behavioral drift — sectors, position sizes, hold times, or trading patterns that deviate from what the DNA prescribes.

2. **What's Working**: Which factors, sectors, or trade patterns are generating the most value? Be specific with numbers where available.

3. **What's Not Working**: Where is the portfolio losing its edge? Flag any persistent problems — factors with poor win rates, sectors dragging returns, positions held too long, or risk config that seems miscalibrated.

4. **Risk Posture**: Given the current regime, sector concentration, and positions near stop, is the portfolio appropriately positioned? What's the biggest unacknowledged risk?

5. **Actionable Observations**: 2-3 concrete things worth acting on now — whether that's tightening a stop, rotating a sector, adjusting a factor weight, or reconsidering the DNA itself.

Be direct, analytical, and specific. Use numbers. Don't pad. Write in second person ("your portfolio"). 4–6 paragraphs total.
""".strip()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/intelligence-brief")
def get_intelligence_brief(portfolio_id: str):
    """Aggregate endpoint: combines performance, learning, risk, warnings, composition."""
    try:
        state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
        config = state.config or {}
    except Exception as e:
        return {"error": str(e)}

    # Performance + health
    try:
        health = get_strategy_health(portfolio_id=portfolio_id)
        health_data = serialize(health)
    except Exception as e:
        health_data = {"error": str(e)}

    try:
        metrics = PortfolioAnalytics(portfolio_id=portfolio_id).calculate_all_metrics()
        metrics_data = serialize(metrics)
    except Exception as e:
        metrics_data = None

    # Learning
    try:
        learner = FactorLearner(portfolio_id=portfolio_id)
        factor_summary = serialize(learner.get_factor_summary())
        weight_suggestions = serialize(get_weight_suggestions(
            state.regime.value if state.regime else None,
            portfolio_id=portfolio_id
        ))
    except Exception:
        factor_summary = {"status": "no_data", "factors": [], "total_analyzed_trades": 0, "last_updated": ""}
        weight_suggestions = []

    # Factor deltas vs defaults
    default_weights = config.get("scoring", {}).get("default_weights", {})
    factor_deltas = {k: 0.0 for k in default_weights}

    # Risk
    try:
        risk_data = serialize(get_risk_scoreboard(portfolio_id=portfolio_id))
    except Exception as e:
        risk_data = {"error": str(e)}

    try:
        warnings_data = serialize(get_warnings(portfolio_id=portfolio_id))
    except Exception as e:
        warnings_data = []

    # Computed composition stats
    positions = state.positions
    sector_breakdown = _compute_sector_breakdown(positions)

    top3_concentration_pct = 0.0
    if positions is not None and len(positions) > 0 and "market_value" in positions.columns:
        total_eq = state.total_equity or 1
        top3_val = float(positions.nlargest(3, "market_value")["market_value"].sum())
        top3_concentration_pct = round(top3_val / total_eq * 100, 1)

    return {
        "health": health_data,
        "metrics": metrics_data,
        "factor_summary": factor_summary,
        "weight_suggestions": weight_suggestions,
        "factor_deltas": factor_deltas,
        "risk": risk_data,
        "warnings": warnings_data,
        "sector_breakdown": sector_breakdown,
        "top3_concentration_pct": top3_concentration_pct,
        "positions_near_stop": _positions_near_stop(positions),
        "avg_position_age_days": _avg_position_age(positions),
        "avg_hold_days": _compute_avg_hold_days(state.transactions),
        "most_traded_tickers": _most_traded_tickers(state.transactions),
        "config": config,
        # quick-access fields
        "total_return_pct": _safe_float(metrics_data.get("total_return_pct") if metrics_data else 0.0),
        "regime": state.regime.value if state.regime else None,
        "regime_analysis": serialize(state.regime_analysis) if state.regime_analysis else None,
        "cash_pct": round((state.cash / state.total_equity * 100) if state.total_equity > 0 else 0, 1),
        "deployed_pct": round((state.positions_value / state.total_equity * 100) if state.total_equity > 0 else 0, 1),
        "num_positions": state.num_positions,
        "snapshots": [
            {
                "date": str(row.get("date", "")),
                "total_equity": _safe_float(row.get("total_equity", 0)),
                "day_pnl_pct": _safe_float(row.get("day_pnl_pct", 0)),
            }
            for _, row in state.snapshots.iterrows()
        ] if state.snapshots is not None and len(state.snapshots) > 0 else [],
    }


@router.get("/intelligence-brief/audit")
def get_audit_brief(portfolio_id: str, regenerate: bool = False):
    """AI-generated Portfolio Audit Brief. Cached 10 min per portfolio."""
    from schema import CLAUDE_MODEL

    cache_key = portfolio_id
    if not regenerate and cache_key in _audit_cache:
        entry = _audit_cache[cache_key]
        age = (datetime.now() - entry["cached_at"]).total_seconds()
        if age < _AUDIT_CACHE_TTL:
            result = dict(entry["result"])
            result["cached"] = True
            return result

    context = _build_audit_context(portfolio_id)
    prompt = _build_audit_prompt(context)

    try:
        import anthropic
        client = anthropic.Anthropic(timeout=90.0)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        brief_text = message.content[0].text
    except Exception as e:
        logging.warning("[intelligence] audit brief failed for %s: %s", portfolio_id, e)
        return {
            "brief": None,
            "generated_at": datetime.now().isoformat(),
            "cached": False,
            "error": "AI audit unavailable — check API key",
        }

    result = {
        "brief": brief_text,
        "generated_at": datetime.now().isoformat(),
        "cached": False,
        "error": None,
    }
    _audit_cache[cache_key] = {"result": result, "cached_at": datetime.now()}
    return result


class ChatRequest(BaseModel):
    messages: list[dict]  # [{role: "user"|"assistant", content: str}]


@router.post("/intelligence-chat")
def intelligence_chat(portfolio_id: str, req: ChatRequest):
    """Chat with portfolio context injected as system prompt."""
    from schema import CLAUDE_MODEL

    context = _build_audit_context(portfolio_id)

    system_prompt = f"""You are GScott, an expert portfolio analyst and trading system co-pilot. You have deep knowledge of quantitative finance, portfolio management, and trading strategy execution.

The user is asking you questions about their portfolio. Here is the full portfolio context:

{context}

---

Answer their questions directly and analytically. Be specific — use the numbers above. When you don't have data for something, say so. You can also suggest what data would be needed to answer. Keep answers concise and actionable. Don't pad responses with disclaimers. Write as if you're a PM reviewing their own book.
""".strip()

    # Cap history at 20 messages to avoid runaway costs
    messages = req.messages[-20:]

    try:
        import anthropic
        client = anthropic.Anthropic(timeout=60.0)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )
        reply = message.content[0].text
    except Exception as e:
        logging.warning("[intelligence] chat failed for %s: %s", portfolio_id, e)
        return {"reply": "Chat unavailable right now. Check API key and try again.", "error": str(e)}

    return {"reply": reply, "error": None}
