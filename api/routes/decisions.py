"""Decision Trace endpoints — read-only access to per-analyze-cycle traces."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import serialize, validate_portfolio_id

from decision_trace import (
    list_recent,
    list_by_ticker,
    find_trace_id_by_proposal,
    load_trace,
)


router = APIRouter(prefix="/api/{portfolio_id}/decisions")


def _trace_path(portfolio_id: str, trace_id: str) -> Path:
    base = Path(__file__).parent.parent.parent / "data" / "portfolios" / portfolio_id / "decisions"
    return base / f"{trace_id}.json"


@router.get("/recent")
def get_recent_decisions(
    portfolio_id: str = Depends(validate_portfolio_id),
    limit: int = Query(default=20, ge=1, le=200),
):
    """List recent trace summaries — newest first. Backed by .index.jsonl tail."""
    return {"traces": list_recent(portfolio_id, limit=limit)}


@router.get("/by_ticker/{ticker}")
def get_decisions_by_ticker(
    ticker: str,
    portfolio_id: str = Depends(validate_portfolio_id),
    limit: int = Query(default=50, ge=1, le=200),
):
    """All trace summaries that touched `ticker`. Newest first."""
    return {"traces": list_by_ticker(portfolio_id, ticker.upper(), limit=limit)}


@router.get("/by_proposal/{proposal_id}")
def get_decision_by_proposal(
    proposal_id: str,
    portfolio_id: str = Depends(validate_portfolio_id),
):
    """Resolve a proposal_id to its containing trace_id (then GET /{trace_id})."""
    trace_id = find_trace_id_by_proposal(portfolio_id, proposal_id)
    if not trace_id:
        raise HTTPException(status_code=404, detail=f"No trace contains proposal_id {proposal_id}")
    return {"proposal_id": proposal_id, "trace_id": trace_id}


@router.get("/diff")
def diff_decisions(
    portfolio_id: str = Depends(validate_portfolio_id),
    a: str = Query(..., description="Trace ID A"),
    b: str = Query(..., description="Trace ID B"),
):
    """Structural diff between two traces — step-level deltas (regime change,
    score deltas, prompt-block additions, validation flips)."""
    pa = _trace_path(portfolio_id, a)
    pb = _trace_path(portfolio_id, b)
    if not pa.exists():
        raise HTTPException(status_code=404, detail=f"Trace {a} not found")
    if not pb.exists():
        raise HTTPException(status_code=404, detail=f"Trace {b} not found")
    with pa.open() as f:
        ta = json.load(f)
    with pb.open() as f:
        tb = json.load(f)
    return _diff_traces(ta, tb)


@router.get("/{trace_id}")
def get_decision_trace(
    trace_id: str,
    portfolio_id: str = Depends(validate_portfolio_id),
):
    """Full trace JSON for a given trace_id."""
    path = _trace_path(portfolio_id, trace_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    with path.open() as f:
        data = json.load(f)
    return data


# ─── Diff implementation ─────────────────────────────────────────────────────

def _diff_traces(a: dict, b: dict) -> dict:
    """Step-by-step diff between two trace dicts.

    For each step type that appears in either trace, compute structural deltas.
    Designed for readability over completeness — surfaces the things that matter
    most when answering "why did the system flip on this trade?"
    """
    out: dict = {
        "trace_a": {"trace_id": a.get("trace_id"), "timestamp": a.get("started_at")},
        "trace_b": {"trace_id": b.get("trace_id"), "timestamp": b.get("started_at")},
        "deltas": [],
    }

    steps_a = {s.get("step_type"): s for s in (a.get("steps") or [])}
    steps_b = {s.get("step_type"): s for s in (b.get("steps") or [])}
    all_step_types = sorted(set(steps_a) | set(steps_b))

    for step_type in all_step_types:
        sa = steps_a.get(step_type)
        sb = steps_b.get(step_type)
        if sa is None:
            out["deltas"].append({"step_type": step_type, "kind": "added_in_b", "summary": "Step appeared in B"})
            continue
        if sb is None:
            out["deltas"].append({"step_type": step_type, "kind": "removed_in_b", "summary": "Step disappeared in B"})
            continue

        if step_type == "regime_detection":
            if sa.get("regime") != sb.get("regime"):
                out["deltas"].append({
                    "step_type": step_type, "kind": "value_changed",
                    "field": "regime", "from": sa.get("regime"), "to": sb.get("regime"),
                })
            for f in ("sma_50", "sma_200", "position_size_factor"):
                if sa.get(f) != sb.get(f):
                    out["deltas"].append({
                        "step_type": step_type, "kind": "value_changed",
                        "field": f, "from": sa.get(f), "to": sb.get(f),
                    })

        elif step_type == "layer1_risk":
            fa = {x["ticker"] for x in (sa.get("flagged") or [])}
            fb = {x["ticker"] for x in (sb.get("flagged") or [])}
            for t in sorted(fb - fa):
                out["deltas"].append({"step_type": step_type, "kind": "newly_flagged", "ticker": t})
            for t in sorted(fa - fb):
                out["deltas"].append({"step_type": step_type, "kind": "unflagged", "ticker": t})

        elif step_type == "watchlist_scoring":
            sa_scores = {c["ticker"]: c.get("score") for c in (sa.get("candidates") or [])}
            sb_scores = {c["ticker"]: c.get("score") for c in (sb.get("candidates") or [])}
            for ticker in sorted(set(sa_scores) | set(sb_scores)):
                va, vb = sa_scores.get(ticker), sb_scores.get(ticker)
                if va is None:
                    out["deltas"].append({"step_type": step_type, "kind": "candidate_added", "ticker": ticker, "score_b": vb})
                elif vb is None:
                    out["deltas"].append({"step_type": step_type, "kind": "candidate_dropped", "ticker": ticker, "score_a": va})
                elif abs((va or 0) - (vb or 0)) >= 5.0:
                    out["deltas"].append({"step_type": step_type, "kind": "score_changed",
                                          "ticker": ticker, "from": va, "to": vb})

        elif step_type == "ai_allocator_prompt":
            ba = set(sa.get("blocks_included") or [])
            bb = set(sb.get("blocks_included") or [])
            for blk in sorted(bb - ba):
                out["deltas"].append({"step_type": step_type, "kind": "prompt_block_added", "block": blk})
            for blk in sorted(ba - bb):
                out["deltas"].append({"step_type": step_type, "kind": "prompt_block_removed", "block": blk})
            if sa.get("candidate_count") != sb.get("candidate_count"):
                out["deltas"].append({"step_type": step_type, "kind": "candidate_count_changed",
                                      "from": sa.get("candidate_count"), "to": sb.get("candidate_count")})

        elif step_type == "ai_allocator_validate":
            va_tickers = {v["ticker"] for v in (sa.get("validations") or [])}
            vb_tickers = {v["ticker"] for v in (sb.get("validations") or [])}
            for t in sorted(vb_tickers - va_tickers):
                out["deltas"].append({"step_type": step_type, "kind": "newly_validated", "ticker": t})
            for t in sorted(va_tickers - vb_tickers):
                out["deltas"].append({"step_type": step_type, "kind": "no_longer_validated", "ticker": t})

        elif step_type == "result_assemble":
            for f in ("approved_count", "modified_count", "vetoed_count"):
                if sa.get(f) != sb.get(f):
                    out["deltas"].append({"step_type": step_type, "kind": "count_changed",
                                          "field": f, "from": sa.get(f), "to": sb.get(f)})

    # Execute step diff
    ea, eb = a.get("execute_step"), b.get("execute_step")
    if ea is None and eb is not None:
        out["deltas"].append({"step_type": "execute", "kind": "appeared_in_b"})
    elif ea is not None and eb is None:
        out["deltas"].append({"step_type": "execute", "kind": "disappeared_in_b"})
    elif ea and eb:
        if len(ea.get("transactions_written") or []) != len(eb.get("transactions_written") or []):
            out["deltas"].append({"step_type": "execute", "kind": "tx_count_changed",
                                  "from": len(ea.get("transactions_written") or []),
                                  "to": len(eb.get("transactions_written") or [])})

    return out
