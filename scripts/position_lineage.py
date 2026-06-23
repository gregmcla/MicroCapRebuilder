#!/usr/bin/env python3
"""
Position Lineage — chronological event timeline for any position.

For a given (portfolio_id, ticker), merges every event that touched that
ticker into a single sorted timeline. Sources, all already-existing or
shipped alongside this feature:

  - Decision Trace store (scripts/decision_trace.py)        — AI considered
  - transactions.csv                                         — bought / sold
  - post_mortems.csv (scripts/post_mortem.py)                — exit analysis
  - daily_scores.jsonl (scripts/score_store.py)              — scored
  - watchlist_events.jsonl (scripts/watchlist_events.py)     — entered/left watchlist
  - risk_adjustments.jsonl (scripts/risk_adjustments.py)     — stop/TP changed

Lineage is read-only; never mutates any source. Used by the API endpoint
`api/routes/lineage.py` to power the LineageTab in IntelligenceBrief.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from data_files import get_transactions_file


# ─── Event variants ──────────────────────────────────────────────────────────
# Each gets a `kind` discriminator on serialize. kw_only avoids inheritance
# pain with defaulted base fields.

@dataclass(kw_only=True)
class BaseEvent:
    timestamp: str            # ISO8601, used as sort key
    ticker: str


@dataclass(kw_only=True)
class WatchlistAddedEvent(BaseEvent):
    reason: str = ""          # e.g. "scan:momentum_breakouts", "manual", "shared_universe"
    source: str = ""          # "discovery" / "manual" / "shared"


@dataclass(kw_only=True)
class WatchlistRemovedEvent(BaseEvent):
    reason: str = ""          # "poor_performer" / "bucket_overflow" / "stale_low_score" / "filled"


@dataclass(kw_only=True)
class ScoredEvent(BaseEvent):
    composite: float
    factor_scores: dict       # {price_momentum, earnings_growth, ...}
    score_delta: float = 0.0  # vs prior day


@dataclass(kw_only=True)
class AiConsideredEvent(BaseEvent):
    trace_id: str
    proposal_id: Optional[str] = None
    action_type: Optional[str] = None   # BUY / SELL / TRIM / None
    accepted: Optional[bool] = None     # Claude's accept flag (always true if it reached validate)
    reasoning_excerpt: str = ""         # first 200 chars when available
    # Real outcome of the proposal — cross-referenced with the analyze trace's
    # execute_step. Distinguishes the AI's approval (`accepted`) from what
    # actually happened (`outcome`). Set at lineage-build time, not by the
    # analyze pipeline.
    #   "executed"        — a transaction was written for this proposal_id
    #   "user_rejected"   — user unchecked the proposal in the dashboard
    #   "pipeline_dropped"— execute dropped it (cash / size / phantom / bad data)
    #   "pending"         — analyze cycle hasn't been executed yet
    outcome: Optional[str] = None
    drop_reason: Optional[str] = None   # populated when outcome ∈ {user_rejected, pipeline_dropped}


@dataclass(kw_only=True)
class BuyEvent(BaseEvent):
    transaction_id: str
    proposal_id: Optional[str] = None
    trace_id: Optional[str] = None
    shares: int
    price: float
    stop_loss: float
    take_profit: float
    factor_scores: dict = field(default_factory=dict)
    ai_reasoning_excerpt: str = ""


@dataclass(kw_only=True)
class SellEvent(BaseEvent):
    transaction_id: str
    proposal_id: Optional[str] = None
    trace_id: Optional[str] = None
    shares: int
    price: float
    reason: str = ""                          # STOP_LOSS / TAKE_PROFIT / SIGNAL / MANUAL
    realized_pnl: Optional[float] = None
    realized_pnl_pct: Optional[float] = None
    holding_days: Optional[int] = None
    ai_reasoning_excerpt: str = ""


@dataclass(kw_only=True)
class StopAdjustedEvent(BaseEvent):
    field_name: str           # "stop_loss" / "take_profit"
    old_value: float
    new_value: float
    source: str = ""          # "trailing" / "volatility" / "manual" / "regime" / "preservation"
    trace_id: Optional[str] = None


@dataclass(kw_only=True)
class PostMortemEvent(BaseEvent):
    transaction_id: str
    summary: str = ""
    what_worked: list = field(default_factory=list)
    what_failed: list = field(default_factory=list)
    recommendation: str = ""
    pattern_tags: list = field(default_factory=list)


LineageEvent = Union[
    WatchlistAddedEvent, WatchlistRemovedEvent, ScoredEvent,
    AiConsideredEvent, BuyEvent, SellEvent, StopAdjustedEvent, PostMortemEvent,
]

EVENT_KIND = {
    WatchlistAddedEvent: "watchlist_added",
    WatchlistRemovedEvent: "watchlist_removed",
    ScoredEvent: "scored",
    AiConsideredEvent: "ai_considered",
    BuyEvent: "buy",
    SellEvent: "sell",
    StopAdjustedEvent: "stop_adjusted",
    PostMortemEvent: "post_mortem",
}


def event_to_dict(ev: BaseEvent) -> dict:
    """Serialize with a `kind` discriminator the UI uses to pick a renderer."""
    return {"kind": EVENT_KIND[type(ev)], **asdict(ev)}


# ─── Aggregator ──────────────────────────────────────────────────────────────

def build_lineage(
    portfolio_id: str,
    ticker: str,
    from_date: Optional[str] = None,
    limit: int = 200,
) -> list[BaseEvent]:
    """Merge every source into a chronological event list, newest first.

    Args:
        portfolio_id: which portfolio to read from
        ticker: ticker symbol (case-insensitive; normalized to upper)
        from_date: ISO date string; events strictly older than this are dropped
        limit: max number of events returned

    Returns:
        list[BaseEvent] sorted by timestamp descending (newest first), trimmed to `limit`.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return []

    events: list[BaseEvent] = []
    events.extend(_emit_watchlist_events(portfolio_id, ticker))
    events.extend(_emit_score_events(portfolio_id, ticker))
    events.extend(_emit_ai_considered_events(portfolio_id, ticker))
    events.extend(_emit_buy_sell_events(portfolio_id, ticker))
    events.extend(_emit_post_mortem_events(portfolio_id, ticker))
    events.extend(_emit_risk_adjustment_events(portfolio_id, ticker))

    # Apply from_date filter (drop strictly older)
    if from_date:
        events = [e for e in events if (e.timestamp or "") >= from_date]

    # Sort by timestamp desc, newest first
    events.sort(key=lambda e: e.timestamp or "", reverse=True)

    if limit and len(events) > limit:
        events = events[:limit]
    return events


def build_summary(portfolio_id: str, ticker: str) -> dict:
    """Lightweight summary for hover-cards / overview tiles.

    Returns: {ticker, first_seen, first_bought, last_traded, total_trades,
              total_pnl, current_status}
    """
    ticker = (ticker or "").strip().upper()
    events = build_lineage(portfolio_id, ticker, limit=10_000)

    first_seen = None
    first_bought = None
    last_traded = None
    total_trades = 0
    total_pnl = 0.0
    current_status = "unknown"

    for e in sorted(events, key=lambda x: x.timestamp or ""):
        ts = e.timestamp
        if first_seen is None:
            first_seen = ts
        if isinstance(e, BuyEvent):
            if first_bought is None:
                first_bought = ts
            last_traded = ts
            current_status = "held"
        elif isinstance(e, SellEvent):
            last_traded = ts
            current_status = "closed"
            total_trades += 1
            if e.realized_pnl is not None:
                total_pnl += float(e.realized_pnl)

    return {
        "ticker": ticker,
        "first_seen": first_seen,
        "first_bought": first_bought,
        "last_traded": last_traded,
        "total_trades": total_trades,
        "total_pnl": round(total_pnl, 2),
        "current_status": current_status,
    }


# ─── Per-source readers ──────────────────────────────────────────────────────

def _emit_ai_considered_events(portfolio_id: str, ticker: str) -> list[AiConsideredEvent]:
    """Walk the Decision Trace store: for each trace that mentioned this
    ticker, emit one AiConsideredEvent per ai_allocator_validate entry."""
    from decision_trace import list_by_ticker, load_trace

    out: list[AiConsideredEvent] = []
    try:
        summaries = list_by_ticker(portfolio_id, ticker, limit=200)
    except Exception:
        return out

    for summary in summaries:
        trace_id = summary.get("trace_id")
        if not trace_id:
            continue
        try:
            trace = load_trace(portfolio_id, trace_id)
        except Exception:
            continue

        # Find the ai_allocator_validate step (if present) and pull this
        # ticker's validation. Fall back to a "considered but not validated"
        # event if the ticker was only in the watchlist_scoring step.
        validate_step = None
        scoring_step = None
        for s in trace.steps:
            cls = type(s).__name__
            if cls == "AiAllocatorValidateStep":
                validate_step = s
            elif cls == "WatchlistScoringStep":
                scoring_step = s

        ts = trace.completed_at or trace.started_at

        # Build a lookup of proposal_id → real outcome from the execute step,
        # if this trace has been executed. Used to enrich AiConsideredEvent.
        # No execute step → outcome = "pending".
        outcome_by_pid: dict[str, tuple[str, str]] = {}  # pid -> (outcome, drop_reason)
        exec_step = getattr(trace, "execute_step", None)
        if exec_step is not None:
            for txn in (getattr(exec_step, "transactions_written", None) or []):
                pid = txn.get("proposal_id")
                if pid:
                    outcome_by_pid[pid] = ("executed", "")
            for d in (getattr(exec_step, "drops", None) or []):
                pid = d.get("proposal_id")
                if not pid:
                    continue
                dropped_at = d.get("dropped_at", "") or ""
                if dropped_at == "user_unchecked":
                    outcome_by_pid[pid] = ("user_rejected", d.get("reason", "") or "")
                else:
                    outcome_by_pid[pid] = ("pipeline_dropped", d.get("reason", "") or "")

        emitted_for_ticker = False
        if validate_step is not None:
            for v in (validate_step.validations or []):
                if (v.get("ticker") or "").upper() != ticker:
                    continue
                emitted_for_ticker = True
                pid = v.get("proposal_id")
                if pid and pid in outcome_by_pid:
                    outcome, drop_reason = outcome_by_pid[pid]
                elif exec_step is None:
                    outcome, drop_reason = "pending", ""
                else:
                    # Execute happened but this proposal's pid wasn't touched —
                    # most likely the analysis_result had stale state. Treat as
                    # pipeline_dropped with an unknown reason rather than lying
                    # by omission.
                    outcome, drop_reason = "pipeline_dropped", "not in execute step"
                out.append(AiConsideredEvent(
                    timestamp=ts,
                    ticker=ticker,
                    trace_id=trace_id,
                    proposal_id=pid,
                    action_type=v.get("action_type"),
                    accepted=v.get("accepted"),
                    reasoning_excerpt="",   # full reasoning lives in trace; UI deep-links
                    outcome=outcome,
                    drop_reason=drop_reason or None,
                ))

        if not emitted_for_ticker and scoring_step is not None:
            # Ticker appeared in scoring but didn't make it to validate — still
            # a real "considered" event worth surfacing.
            for c in (scoring_step.candidates or []):
                if (c.get("ticker") or "").upper() != ticker:
                    continue
                out.append(AiConsideredEvent(
                    timestamp=ts,
                    ticker=ticker,
                    trace_id=trace_id,
                    proposal_id=None,
                    action_type=None,
                    accepted=None,
                    reasoning_excerpt="",
                ))
                break

    return out


def _emit_buy_sell_events(portfolio_id: str, ticker: str) -> list[BaseEvent]:
    """Read transactions.csv for this portfolio, emit BuyEvent/SellEvent for
    every row touching the ticker. FIFO-match for realized P&L on sells."""
    tx_path = get_transactions_file(portfolio_id)
    if not tx_path.exists():
        return []
    try:
        df = pd.read_csv(tx_path)
    except Exception:
        return []
    if df.empty or "ticker" not in df.columns:
        return []

    df = df[df["ticker"].astype(str).str.upper() == ticker].copy()
    if df.empty:
        return []
    df = df.sort_values("date")

    # FIFO pair-up for realized P&L + holding_days on sells. We use the FULL
    # transaction history for this ticker (not just sells in the current page)
    # so partial sells don't get mis-attributed.
    lots: list[dict] = []  # FIFO queue of remaining lots: {shares, cost, buy_date}
    events: list[BaseEvent] = []

    for _, row in df.iterrows():
        ts = str(row.get("date", ""))
        action = str(row.get("action", "")).upper()
        shares = int(float(row.get("shares", 0) or 0))
        price = float(row.get("price", 0) or 0)
        txn_id = str(row.get("transaction_id", "") or "")
        rationale = _parse_trade_rationale(row.get("trade_rationale"))
        ai_excerpt = (rationale.get("ai_reasoning") or "")[:200] if rationale else ""

        if action == "BUY":
            lots.append({"shares": shares, "cost": price, "buy_date": ts})
            factor_scores = _parse_factor_scores(row.get("factor_scores"))
            events.append(BuyEvent(
                timestamp=ts,
                ticker=ticker,
                transaction_id=txn_id,
                proposal_id=_str_or_none(row.get("source_proposal_id")),
                trace_id=_str_or_none(row.get("source_trace_id")),
                shares=shares,
                price=round(price, 2),
                stop_loss=float(row.get("stop_loss") or 0),
                take_profit=float(row.get("take_profit") or 0),
                factor_scores=factor_scores,
                ai_reasoning_excerpt=ai_excerpt,
            ))
        elif action == "SELL":
            remaining = shares
            realized = 0.0
            cost_basis = 0.0
            first_buy_date: Optional[str] = None
            while remaining > 0 and lots:
                lot = lots[0]
                take = min(remaining, lot["shares"])
                realized += (price - lot["cost"]) * take
                cost_basis += lot["cost"] * take
                if first_buy_date is None:
                    first_buy_date = lot["buy_date"]
                lot["shares"] -= take
                remaining -= take
                if lot["shares"] == 0:
                    lots.pop(0)
            realized_pct = (realized / cost_basis * 100) if cost_basis > 0 else None
            holding_days = _date_diff_days(first_buy_date, ts) if first_buy_date else None
            events.append(SellEvent(
                timestamp=ts,
                ticker=ticker,
                transaction_id=txn_id,
                proposal_id=_str_or_none(row.get("source_proposal_id")),
                trace_id=_str_or_none(row.get("source_trace_id")),
                shares=shares,
                price=round(price, 2),
                reason=str(row.get("reason", "") or ""),
                realized_pnl=round(realized, 2) if cost_basis > 0 else None,
                realized_pnl_pct=round(realized_pct, 2) if realized_pct is not None else None,
                holding_days=holding_days,
                ai_reasoning_excerpt=ai_excerpt,
            ))

    return events


def _emit_post_mortem_events(portfolio_id: str, ticker: str) -> list[PostMortemEvent]:
    """Read post_mortems.csv for the portfolio, emit one event per row matching ticker."""
    from post_mortem import load_post_mortems

    out: list[PostMortemEvent] = []
    try:
        pms = load_post_mortems(portfolio_id=portfolio_id)
    except Exception:
        return out
    for pm in pms:
        if (pm.ticker or "").upper() != ticker:
            continue
        out.append(PostMortemEvent(
            timestamp=pm.close_date or "",
            ticker=ticker,
            transaction_id=pm.transaction_id or "",
            summary=pm.summary or "",
            what_worked=list(pm.what_worked or []),
            what_failed=list(pm.what_failed or []),
            recommendation=pm.recommendation or "",
            pattern_tags=list(pm.pattern_tags or []),
        ))
    return out


def _emit_score_events(portfolio_id: str, ticker: str) -> list[ScoredEvent]:
    """Read daily_scores.jsonl, emit ScoredEvent per day, deduped to only
    material moves so the timeline isn't drowned in noise."""
    from score_store import ScoreStore

    try:
        store = ScoreStore(portfolio_id=portfolio_id)
        rows = store.get_ticker_history(ticker, days=120)
    except Exception:
        return []

    DEDUP_THRESHOLD = 5.0  # only emit if composite moved >=5pt vs previous emitted point
    out: list[ScoredEvent] = []
    last_emitted_composite: Optional[float] = None
    for i, row in enumerate(rows):
        composite = float(row.get("composite", 0) or 0)
        # Always emit the first score (entry to ranking), the last score, and any
        # ≥5pt move from the previously emitted score.
        is_first = i == 0
        is_last = i == len(rows) - 1
        moved = (
            last_emitted_composite is not None
            and abs(composite - last_emitted_composite) >= DEDUP_THRESHOLD
        )
        if not (is_first or is_last or moved):
            continue
        prev_composite = float(rows[i - 1].get("composite", 0) or 0) if i > 0 else composite
        out.append(ScoredEvent(
            timestamp=str(row.get("date", "")),
            ticker=ticker,
            composite=round(composite, 2),
            factor_scores={
                "price_momentum": row.get("momentum"),
                "earnings_growth": row.get("earnings"),
                "quality": row.get("quality"),
                "volume": row.get("volume"),
                "volatility": row.get("volatility"),
                "value_timing": row.get("value_timing"),
            },
            score_delta=round(composite - prev_composite, 2),
        ))
        last_emitted_composite = composite
    return out


def _emit_watchlist_events(portfolio_id: str, ticker: str) -> list[BaseEvent]:
    """Read watchlist_events.jsonl (shipped in Phase 2). No-op if file absent."""
    path = _data_dir() / "portfolios" / portfolio_id / "watchlist_events.jsonl"
    if not path.exists():
        return []
    out: list[BaseEvent] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if (row.get("ticker") or "").upper() != ticker:
                continue
            kind = row.get("type")
            ts = row.get("ts", "")
            if kind == "added":
                out.append(WatchlistAddedEvent(
                    timestamp=ts, ticker=ticker,
                    reason=row.get("reason", ""), source=row.get("source", ""),
                ))
            elif kind == "removed":
                out.append(WatchlistRemovedEvent(
                    timestamp=ts, ticker=ticker, reason=row.get("reason", ""),
                ))
    except Exception:
        return out
    return out


def _emit_risk_adjustment_events(portfolio_id: str, ticker: str) -> list[StopAdjustedEvent]:
    """Read risk_adjustments.jsonl (shipped in Phase 3). No-op if file absent."""
    path = _data_dir() / "portfolios" / portfolio_id / "risk_adjustments.jsonl"
    if not path.exists():
        return []
    out: list[StopAdjustedEvent] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if (row.get("ticker") or "").upper() != ticker:
                continue
            out.append(StopAdjustedEvent(
                timestamp=row.get("ts", ""),
                ticker=ticker,
                field_name=str(row.get("field", "")),
                old_value=float(row.get("old", 0) or 0),
                new_value=float(row.get("new", 0) or 0),
                source=str(row.get("source", "")),
                trace_id=row.get("trace_id"),
            ))
    except Exception:
        return out
    return out


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _data_dir() -> Path:
    return Path(__file__).parent.parent / "data"


def _str_or_none(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v)
    if not s or s.lower() == "nan":
        return None
    return s


def _parse_trade_rationale(raw) -> dict:
    if raw is None:
        return {}
    s = str(raw)
    if not s or s == "nan":
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


def _parse_factor_scores(raw) -> dict:
    if raw is None:
        return {}
    s = str(raw)
    if not s or s == "nan":
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


def _date_diff_days(start: Optional[str], end: Optional[str]) -> Optional[int]:
    if not start or not end:
        return None
    try:
        d1 = datetime.fromisoformat(start[:19]).date()
        d2 = datetime.fromisoformat(end[:19]).date()
        return (d2 - d1).days
    except Exception:
        return None
