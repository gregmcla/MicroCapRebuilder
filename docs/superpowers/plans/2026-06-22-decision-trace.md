# Plan: Decision Trace (Feature #9)

**Status:** awaiting Greg approval
**Author:** Claude
**Date:** 2026-06-22

---

## Goal

Make every `/analyze` cycle's decision path *legible and queryable*. Right now `run_unified_analysis()` produces a flat result blob — the inputs, branch points, and rejected alternatives along the way are lost. With Decision Trace, every analyze cycle emits a structured tree of decisions that can be loaded, diff'd, and replayed.

This is the substrate that enables Features #14 (capital allocator — needs decision attribution), #16 (DNA visualizer — needs measured behavior), #17 (position lineage — IS a query against trace store), and #20 (multi-step planning — same data model, future-tense).

---

## What "Decision Trace" actually is

A single accumulator object (`DecisionTrace`) threaded through `run_unified_analysis`. At every branch point in the pipeline, code calls `trace.step("name")` as a context manager and records:

- inputs received
- candidates considered (e.g. all 200 scored tickers)
- candidates passed (the top 8 that survived)
- candidates rejected (with per-ticker reason)
- outputs produced
- duration
- model / prompt metadata (for AI calls)
- nested sub-decisions

At end of analyze, the trace is serialized to `data/portfolios/{id}/decisions/{trace_id}.json` alongside the existing `.last_analysis.json`.

A new dashboard tab loads any trace and renders it as an expandable tree. Click any final buy/sell → walk the tree backwards to see the exact path.

---

## Schema

```python
# scripts/decision_trace.py

@dataclass
class DecisionStep:
    step: str                       # "layer1_risk", "ai_allocator_validate", etc.
    started_at: str                 # ISO8601
    duration_ms: int
    inputs: dict                    # what entered
    outputs: dict                   # what left
    candidates_considered: list = field(default_factory=list)
    candidates_passed: list = field(default_factory=list)
    candidates_rejected: list = field(default_factory=list)  # [{ticker, reason, ...}]
    children: list["DecisionStep"] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # model, prompt_hash, etc.
    error: Optional[str] = None

@dataclass
class DecisionTrace:
    trace_id: str                   # "max_20260622_161345_a1b2"
    portfolio_id: str
    analyze_mode: str               # full / buys_only / sells_only
    branch: str                     # "ai_driven" / "mechanical"
    started_at: str
    completed_at: str
    duration_ms: int
    steps: list[DecisionStep]
    final_summary: dict             # mirrors result["summary"]
    config_snapshot: dict           # subset of config — DNA + scoring weights at decision time
```

Storage: one JSON file per trace, ~5–50KB. Gitignored. Retention: keep last 100 per portfolio, prune older on write.

---

## Decision points to instrument

### AI-driven path (priority — covers MAX, defense-tech, max2, max-b, asymmetric-catalyst-hunters, etc. — most live activity)

| Step | Source location | What gets captured |
|---|---|---|
| `regime_detection` | `portfolio_state.py:_get_cached_regime_analysis` | Benchmark, regime label, SMA50/200, position_size_factor |
| `layer1_risk` | `unified_analysis.py:581 _run_layer1_risk` | Positions reviewed, which flagged (stop-loss, score deterioration, momentum fade, etc.), per-ticker reason |
| `watchlist_scoring` | watchlist read + score store query | All scored tickers, top N selected for AI prompt, score deltas |
| `ai_allocator_prompt_build` | `ai_allocator.py:205 _build_allocation_prompt` | Which context blocks included (macro, observations, factor_scores, recent_trades, sector_overlap, reentry_guard, regime_block), prompt size |
| `ai_allocator_call` | `ai_allocator.py:allocate` | Model, prompt char count, response duration, raw response text, response token count, finish reason |
| `ai_allocator_parse` | `ai_allocator.py:961 _parse_json` | JSON cleanup applied, parsed buy/sell/trim list |
| `ai_allocator_validate` | `ai_allocator.py:685 _validate_allocation` | Per-action: original → final, share cap reasons, phantom-sell rejections, max_positions truncations |
| `result_assemble` | `_assemble_analysis_result` | Approve/modify/veto split, mode enforcement, micro-position filter rejections |

### Mechanical path (lower priority — fewer portfolios, can ship in phase 3)

| Step | Source |
|---|---|
| `regime_detection` | (same as above) |
| `layer1_risk` | (same as above) |
| `enhanced_layers_step2` | `_run_enhanced_layers_step2` — OpportunityLayer + CompositionLayer |
| `fallback_scoring_step2` | `_run_fallback_scoring_step2` |
| `layer4_sequencing` | ExecutionSequencer.process |
| `warning_severity_reduction` | inline in `run_unified_analysis` |
| `ai_review` | `ai_review.review_proposed_actions` — per-action APPROVE/MODIFY/VETO with Claude reasoning |
| `result_assemble` | (same as above) |

---

## API surface

| Endpoint | Returns |
|---|---|
| `GET /api/{portfolio_id}/decisions/recent?limit=20` | List of recent trace IDs with summary (timestamp, mode, branch, approve/modify/veto counts) |
| `GET /api/{portfolio_id}/decisions/{trace_id}` | Full trace JSON |
| `GET /api/{portfolio_id}/decisions/by_ticker/{ticker}` | All traces that touched a ticker (sets up Feature #17) |
| `GET /api/{portfolio_id}/decisions/diff?trace_a={id}&trace_b={id}` | Structural diff (phase 6) |

---

## UI

**New tab** in IntelligenceBrief: "DECISIONS" (slots between FACTORS and TRADES).

**MVP (phase 5):**
- Left: list of recent traces (last 20), each showing date / mode / approve count / veto count
- Right: expandable tree view of selected trace
- Click any final action (approve/modify/veto) → highlight the path through the tree that produced it

**Phase 6 (post-MVP):**
- Filter list by date range, by ticker (search box)
- Diff mode: select two traces side-by-side, structural diff highlights what flipped

---

## Build phases & sizing

| Phase | Work | Days | Ship-able value |
|---|---|---|---|
| 1 | `scripts/decision_trace.py` substrate + storage + `_trace` kwarg threading | 2 | None alone |
| 2 | Instrument AI-driven path (8 steps) | 2 | **All live AI-driven portfolios become legible** ✅ |
| 3 | Instrument mechanical path (7 steps) | 1.5 | Covers remaining portfolios |
| 4 | API endpoints + atomic write + prune | 1 | Backend complete |
| 5 | DecisionsTab UI MVP (tree view) | 1.5 | **Greg can navigate decisions in the dashboard** ✅ |
| 6 | Diff view + ticker search | 1 | "Why did Claude flip on AVGO?" answered in 2 clicks |

**Minimum viable ship:** Phases 1 + 2 + 4 + 5 = **~6 days.** Mechanical path and diff view can land in a follow-up.

---

## Risks and how I'll handle them

1. **Mutation in the pipeline.** Several decision functions mutate `proposed_actions` in place. Tracing might capture odd intermediate state.
   → Snapshot inputs and outputs at the boundary of each wrapped block. Don't try to capture intra-step mutations.

2. **Prompt bloat.** ai_allocator's prompt is ~30KB. Storing it verbatim in every trace = 30KB × 100 traces × 35 portfolios = ~100MB.
   → Store the *structure* (which blocks included + sizes) inline. Store full prompt text in a sidecar file `decisions/{trace_id}.prompt.txt` only when explicitly requested.

3. **Test suite expects exact dict shapes.** 327 backend tests reference result fields.
   → Tracing is purely additive. `run_unified_analysis` returns the SAME dict as before; the trace is written as a side effect to disk. No change to the function's return type. Tests stay green.

4. **Disk growth.** Without pruning, ~50KB × N analyze cycles × 35 portfolios fills up.
   → Prune on write: when count > 100, delete oldest by mtime. Configurable via env var.

5. **AI-driven branch returns early.** `run_unified_analysis` short-circuits into `_run_ai_driven_analysis` at line 861. Need to thread the trace into that function.
   → Pass `_trace` as a kwarg. Use a no-op `NullTrace` when not provided so existing callers don't have to change.

6. **Existing cron pipeline.** `cron/analyze.sh` calls the analyze endpoint. Don't want to slow down cron.
   → Tracing overhead is <50ms per analyze cycle (measured by the wrapping context-manager pattern). Writing the JSON file is async-able if it ever becomes a concern. Initial measurement post-Phase-2 will confirm.

---

## Out of scope (for this phase)

- **Tracing the execute pipeline** (`execute_approved_actions`). It has its own decision points (phantom sells, cash math, atomic writes). Worth tracing eventually but separate scope; doubles the work.
- **Multi-portfolio trace correlation** (cross-portfolio "what tickers did multiple portfolios reject and why?"). Belongs to Feature #15 (convergence) not #9.
- **Trace replay simulation** ("rerun this trace with weights X instead of Y"). That's Feature #1 territory (genetic portfolios).
- **Decision quality model** ("of all traces, what reasoning patterns correlate with outcomes?"). That's the *next* feature on the chain — needs 3+ months of accumulated traces first.

---

## Approval needed

Before I touch code, I need a green light on:

1. **Scope of MVP** — Phases 1 + 2 + 4 + 5 only? Or include Phase 3 (mechanical path) and ship the whole thing in one go?
2. **Storage location** — `data/portfolios/{id}/decisions/{trace_id}.json` — same dir as positions.csv etc., gitignored alongside them. OK?
3. **Retention** — keep last 100 per portfolio by default. OK?
4. **UI placement** — new tab in IntelligenceBrief (alongside FACTORS / RISK / TRADES). Or somewhere else?
5. **Prompt body persistence** — sidecar file (only on request) vs always-inline vs never-stored. I lean sidecar. OK?

Once approved I start with `scripts/decision_trace.py` (the substrate). Estimated first ship: 4-6 days.
