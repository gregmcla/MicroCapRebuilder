#!/usr/bin/env python3
"""
Decision Trace — structured per-analyze-cycle record of every branch in the pipeline.

For each /analyze run, we emit a DecisionTrace containing typed step variants
(RegimeDetectionStep, Layer1RiskStep, AiAllocatorCallStep, etc.) that capture
what the pipeline considered, what it rejected and why, and what it produced.

The trace is the substrate for:
  - The DECISIONS dashboard tab (legible reasoning per trade)
  - Decision diffing (why did Claude flip on AVGO between Tuesday and Thursday?)
  - Position lineage (#17), capital allocator attribution (#14), DNA
    visualization (#16), multi-step planning (#20).

Layout on disk (per portfolio):
  data/portfolios/{id}/decisions/{trace_id}.json   — one file per cycle
  data/portfolios/{id}/decisions/.index.jsonl      — append-only summary line per cycle

`save_trace()` is atomic (tmp + replace). `.index.jsonl` append is locked via
fcntl.flock for safe concurrent writes (cron + manual analyze can interleave).
"""

import fcntl
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── Step variants ───────────────────────────────────────────────────────────
# kw_only=True lets subclasses add required fields after BaseStep's defaulted
# `error` field without ordering pain. Each step is self-describing.

@dataclass(kw_only=True)
class BaseStep:
    step_name: str
    started_at: str           # ISO8601
    duration_ms: int
    error: Optional[str] = None


@dataclass(kw_only=True)
class RegimeDetectionStep(BaseStep):
    benchmark_symbol: str
    regime: str               # "BULL" / "BEAR" / "SIDEWAYS"
    sma_50: float
    sma_200: float
    position_size_factor: float
    cache_hit: bool


@dataclass(kw_only=True)
class Layer1RiskStep(BaseStep):
    positions_reviewed: int
    flagged: list             # [{ticker, reason, score_drop, ...}]
    not_flagged: list         # ticker list


@dataclass(kw_only=True)
class WatchlistScoringStep(BaseStep):
    total_scored: int
    threshold_applied: float
    top_n_selected: int
    candidates: list          # [{ticker, score, factor_scores, score_delta}, ...]


@dataclass(kw_only=True)
class AiAllocatorPromptStep(BaseStep):
    blocks_included: list     # ["macro", "observations", "factor_scores", ...]
    prompt_char_count: int
    prompt_text: str          # inline (~30KB)
    candidate_count: int
    held_count: int


@dataclass(kw_only=True)
class AiAllocatorCallStep(BaseStep):
    model: str
    response_char_count: int
    response_token_count: Optional[int]
    finish_reason: str
    raw_response: str          # inline


@dataclass(kw_only=True)
class AiAllocatorParseStep(BaseStep):
    cleanup_applied: list      # ["stripped_markdown", "removed_trailing_commas", ...]
    parsed_buys: list
    parsed_sells: list
    parsed_trims: list
    parse_error: Optional[str] = None


@dataclass(kw_only=True)
class AiAllocatorValidateStep(BaseStep):
    validations: list          # [{proposal_id, ticker, action_type, accepted, modifications, rejection_reason}]


@dataclass(kw_only=True)
class ResultAssembleStep(BaseStep):
    mode_filter: str
    approved_count: int
    modified_count: int
    vetoed_count: int
    micro_position_dropped: list


@dataclass(kw_only=True)
class ExecuteStep(BaseStep):
    proposal_ids_processed: list
    transactions_written: list # [{proposal_id, transaction_id, ticker, action, shares, price}]
    drops: list                # [{proposal_id, ticker, reason, dropped_at}]


# ─── Discriminator registry ──────────────────────────────────────────────────
# Used during JSON (de)serialization since asdict() loses the runtime class.

STEP_REGISTRY: dict[str, type[BaseStep]] = {
    "regime_detection": RegimeDetectionStep,
    "layer1_risk": Layer1RiskStep,
    "watchlist_scoring": WatchlistScoringStep,
    "ai_allocator_prompt": AiAllocatorPromptStep,
    "ai_allocator_call": AiAllocatorCallStep,
    "ai_allocator_parse": AiAllocatorParseStep,
    "ai_allocator_validate": AiAllocatorValidateStep,
    "result_assemble": ResultAssembleStep,
    "execute": ExecuteStep,
}

# Reverse lookup: class → discriminator key
_CLASS_TO_KEY = {cls: key for key, cls in STEP_REGISTRY.items()}


def _step_type_key(step: BaseStep) -> str:
    return _CLASS_TO_KEY[type(step)]


# ─── Trace container ─────────────────────────────────────────────────────────

@dataclass
class DecisionTrace:
    trace_id: str
    portfolio_id: str
    portfolio_name: str
    analyze_mode: str         # "full" / "buys_only" / "sells_only"
    branch: str               # "ai_driven" (the only live branch; "mechanical" reserved)
    started_at: str
    completed_at: str = ""
    duration_ms: int = 0
    steps: list = field(default_factory=list)
    final_summary: dict = field(default_factory=dict)
    config_snapshot: dict = field(default_factory=dict)
    execute_step: Optional[ExecuteStep] = None
    _start_time: float = field(default=0.0, repr=False)

    def add_step(self, step: BaseStep) -> None:
        self.steps.append(step)

    def finalize(self) -> None:
        if self._start_time:
            self.duration_ms = int((time.time() - self._start_time) * 1000)
        self.completed_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Serialize with step_type discriminators."""
        out = {
            "trace_id": self.trace_id,
            "portfolio_id": self.portfolio_id,
            "portfolio_name": self.portfolio_name,
            "analyze_mode": self.analyze_mode,
            "branch": self.branch,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "final_summary": self.final_summary,
            "config_snapshot": self.config_snapshot,
            "steps": [
                {**asdict(s), "step_type": _step_type_key(s)}
                for s in self.steps
            ],
            "execute_step": (
                {**asdict(self.execute_step), "step_type": "execute"}
                if self.execute_step
                else None
            ),
        }
        return out


def new_trace(
    portfolio_id: str,
    portfolio_name: str,
    mode: str,
    branch: str,
    config: dict,
) -> DecisionTrace:
    """Construct a fresh trace; call save_trace() at end of analyze."""
    now = datetime.now()
    trace_id = f"{portfolio_id}_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    return DecisionTrace(
        trace_id=trace_id,
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        analyze_mode=mode,
        branch=branch,
        started_at=now.isoformat(),
        config_snapshot=_sanitize_config(config),
        _start_time=time.time(),
    )


def _sanitize_config(config: dict) -> dict:
    """Strip secrets from config snapshot (api keys etc.)."""
    out = json.loads(json.dumps(config, default=str))  # deep copy + JSON-safe
    dp = out.get("data_provider", {})
    if "alpha_vantage_api_key" in dp:
        dp["alpha_vantage_api_key"] = "***"
    return out


# ─── Persistence ─────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent / "data" / "portfolios"


def _decisions_dir(portfolio_id: str) -> Path:
    d = _DATA_DIR / portfolio_id / "decisions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_trace(trace: DecisionTrace) -> Path:
    """Atomic write of trace JSON + append to index. Returns the trace file path."""
    trace.finalize()
    out_dir = _decisions_dir(trace.portfolio_id)
    out_path = out_dir / f"{trace.trace_id}.json"
    tmp_path = out_path.with_suffix(".json.tmp")

    with tmp_path.open("w") as f:
        json.dump(trace.to_dict(), f, indent=2, default=str)
    tmp_path.replace(out_path)

    _append_index(out_dir, trace)
    return out_path


def _append_index(out_dir: Path, trace: DecisionTrace) -> None:
    """Append summary line to .index.jsonl. fcntl-locked for concurrent safety."""
    summary = _index_line(trace)
    index_path = out_dir / ".index.jsonl"
    with index_path.open("a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(summary, default=str) + "\n")
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _index_line(trace: DecisionTrace) -> dict:
    """Build the one-line index summary. Includes proposal_ids and tickers
    so search-by-proposal and search-by-ticker are O(scan_index) not
    O(scan_all_trace_files)."""
    tickers: set[str] = set()
    proposal_ids: list[str] = []

    for s in trace.steps:
        if isinstance(s, WatchlistScoringStep):
            for c in s.candidates:
                t = c.get("ticker")
                if t:
                    tickers.add(t)
        elif isinstance(s, AiAllocatorValidateStep):
            for v in s.validations:
                if v.get("ticker"):
                    tickers.add(v["ticker"])
                if v.get("proposal_id"):
                    proposal_ids.append(v["proposal_id"])
        elif isinstance(s, Layer1RiskStep):
            for f_ in s.flagged:
                if f_.get("ticker"):
                    tickers.add(f_["ticker"])

    if trace.execute_step:
        for txn in trace.execute_step.transactions_written:
            if txn.get("ticker"):
                tickers.add(txn["ticker"])
            if txn.get("proposal_id") and txn["proposal_id"] not in proposal_ids:
                proposal_ids.append(txn["proposal_id"])

    summary = trace.final_summary or {}
    return {
        "trace_id": trace.trace_id,
        "timestamp": trace.started_at,
        "mode": trace.analyze_mode,
        "branch": trace.branch,
        "approved": summary.get("approved", 0),
        "modified": summary.get("modified", 0),
        "vetoed": summary.get("vetoed", 0),
        "tickers": sorted(tickers),
        "proposal_ids": proposal_ids,
    }


# ─── Reads ───────────────────────────────────────────────────────────────────

def load_trace(portfolio_id: str, trace_id: str) -> DecisionTrace:
    """Reconstruct a DecisionTrace from disk."""
    path = _decisions_dir(portfolio_id) / f"{trace_id}.json"
    with path.open() as f:
        data = json.load(f)
    return _trace_from_dict(data)


def _step_from_dict(d: dict) -> BaseStep:
    d = dict(d)  # shallow copy so caller's data isn't mutated
    step_type = d.pop("step_type")
    cls = STEP_REGISTRY[step_type]
    return cls(**d)


def _trace_from_dict(data: dict) -> DecisionTrace:
    steps_data = data.pop("steps", [])
    execute_data = data.pop("execute_step", None)
    trace = DecisionTrace(**data, _start_time=0.0)
    trace.steps = [_step_from_dict(s) for s in steps_data]
    if execute_data:
        trace.execute_step = _step_from_dict(execute_data)
    return trace


def list_recent(portfolio_id: str, limit: int = 20) -> list[dict]:
    """Tail of .index.jsonl, newest first."""
    index_path = _decisions_dir(portfolio_id) / ".index.jsonl"
    if not index_path.exists():
        return []
    lines = [l for l in index_path.read_text().strip().split("\n") if l]
    out = [json.loads(l) for l in lines[-limit:]]
    return list(reversed(out))


def find_trace_id_by_proposal(portfolio_id: str, proposal_id: str) -> Optional[str]:
    """Return the trace_id of the trace whose proposals include `proposal_id`.
    Index scan: O(N) on lines but skips full trace file loads."""
    index_path = _decisions_dir(portfolio_id) / ".index.jsonl"
    if not index_path.exists():
        return None
    # Reverse scan — newer traces typically queried more often
    for line in reversed([l for l in index_path.read_text().strip().split("\n") if l]):
        try:
            summary = json.loads(line)
        except json.JSONDecodeError:
            continue
        if proposal_id in (summary.get("proposal_ids") or []):
            return summary["trace_id"]
    return None


def attach_execute_step(
    portfolio_id: str,
    trace_id: str,
    step: ExecuteStep,
) -> bool:
    """Load an existing trace, set its execute_step, and atomically rewrite.

    Returns True on success, False if the trace file is missing (e.g. cron's
    .last_analysis.json was created before tracing landed). Non-fatal — execute
    proceeds even if attachment fails.
    """
    path = _decisions_dir(portfolio_id) / f"{trace_id}.json"
    if not path.exists():
        return False
    with path.open() as f:
        data = json.load(f)
    data["execute_step"] = {**asdict(step), "step_type": "execute"}

    tmp_path = path.with_suffix(".json.tmp")
    with tmp_path.open("w") as f:
        json.dump(data, f, indent=2, default=str)
    tmp_path.replace(path)
    return True


def list_by_ticker(portfolio_id: str, ticker: str, limit: int = 50) -> list[dict]:
    """All trace summaries that touched `ticker`. Newest first."""
    index_path = _decisions_dir(portfolio_id) / ".index.jsonl"
    if not index_path.exists():
        return []
    out = []
    for line in reversed([l for l in index_path.read_text().strip().split("\n") if l]):
        try:
            summary = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ticker in (summary.get("tickers") or []):
            out.append(summary)
            if len(out) >= limit:
                break
    return out
