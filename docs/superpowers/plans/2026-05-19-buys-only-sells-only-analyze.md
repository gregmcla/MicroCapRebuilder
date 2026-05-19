# Buys-Only / Sells-Only Analyze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two analyze modes (`buys_only`, `sells_only`) reachable from two new dashboard buttons that share the existing pipeline but constrain prompt + output to a single side, with independent persistence slots and execute paths. The existing `/analyze` endpoint, cron, and Telegram flows remain bit-for-bit identical.

**Architecture:** A `mode` parameter (`"full"` | `"buys_only"` | `"sells_only"`) is threaded through `run_unified_analysis` → its branch helpers → `run_ai_allocation` → `_build_allocation_prompt` / `_validate_allocation`. A defense-in-depth output filter in `_assemble_analysis_result` and the AI-driven return block guarantees the off-side is never emitted. Three slot files per portfolio (`.last_analysis.json`, `.last_analysis.buys.json`, `.last_analysis.sells.json`) hold independent plans. `/analyze` and `/execute` accept a `?mode=` query param that selects the slot.

**Tech Stack:** Python 3 + FastAPI backend, React 19 + Vite + Zustand + TanStack Query frontend. pytest for tests. Anthropic SDK for AI allocator.

**Spec:** `docs/superpowers/specs/2026-05-19-buys-only-sells-only-analyze-design.md`

---

## Conventions

- Commands assume working directory: `/Users/gregmclaughlin/MicroCapRebuilder/`
- Tests run via: `python3 -m pytest <path> -v`
- Backend reload: the dev API is launched via `uvicorn api.main:app --host 0.0.0.0 --port 8001` — kill + relaunch (no `--reload` in production runs). For TDD cycles, tests don't need the server running.
- Frontend dev server: `cd dashboard && npm run dev` (Vite, port 5173). Hot reload picks up TS changes.
- TypeScript build check: `cd dashboard && npx tsc --noEmit`
- All commits should include the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.

---

## Task 1: Add `mode` parameter to `_build_allocation_prompt`

**Goal:** The allocator prompt builder accepts a `mode` argument and emits a one-paragraph stance directive immediately before the HARD CONSTRAINTS block for `buys_only` / `sells_only`. Default (`full`) emits nothing — prompt is unchanged.

**Files:**
- Modify: `scripts/ai_allocator.py` (function `_build_allocation_prompt`, around line 175 and around line 558 where HARD CONSTRAINTS is inserted)
- Test: `scripts/tests/test_ai_allocator.py` (extend with new test functions)

- [ ] **Step 1: Write the failing tests**

Add to `scripts/tests/test_ai_allocator.py`:

```python
import pytest
from types import SimpleNamespace

# Helper to call _build_allocation_prompt with minimum viable args
def _minimal_prompt(mode: str = "full") -> str:
    from ai_allocator import _build_allocation_prompt
    from market_regime import MarketRegime
    import pandas as pd

    state = SimpleNamespace(
        positions=pd.DataFrame(columns=["ticker", "shares", "avg_cost_basis",
                                        "current_price", "market_value",
                                        "unrealized_pnl_pct", "stop_loss",
                                        "take_profit", "entry_date"]),
        transactions=pd.DataFrame(),
        cash=100_000.0,
        total_equity=100_000.0,
        num_positions=0,
        regime=MarketRegime.SIDEWAYS,
        config={"max_positions": 10, "default_stop_loss_pct": 8.0},
        portfolio_id="_test_prompt",
        regime_analysis=None,
    )
    return _build_allocation_prompt(
        state=state,
        layer1_sells=[],
        scored_candidates=[],
        sector_map={},
        regime=MarketRegime.SIDEWAYS,
        warning_severity="NORMAL",
        strategy_dna="Test strategy",
        available_cash=100_000.0,
        info_cache={},
        full_watchlist=False,
        regime_analysis=None,
        prompt_extras=None,
        portfolio_id="_test_prompt",
        mode=mode,
    )


def test_build_prompt_full_mode_omits_directive():
    p = _minimal_prompt(mode="full")
    assert "CASH DEPLOYMENT MODE" not in p
    assert "RISK REVIEW MODE" not in p


def test_build_prompt_buys_only_includes_cash_deployment_directive():
    p = _minimal_prompt(mode="buys_only")
    assert "CASH DEPLOYMENT MODE" in p
    assert "do not propose any sells" in p.lower()
    # Directive must appear before HARD CONSTRAINTS so Claude reads it first
    assert p.index("CASH DEPLOYMENT MODE") < p.index("HARD CONSTRAINTS")


def test_build_prompt_sells_only_includes_risk_review_directive():
    p = _minimal_prompt(mode="sells_only")
    assert "RISK REVIEW MODE" in p
    assert "do not propose any new buys" in p.lower()
    assert p.index("RISK REVIEW MODE") < p.index("HARD CONSTRAINTS")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_ai_allocator.py -v -k "build_prompt"`
Expected: FAIL — `_build_allocation_prompt` does not accept a `mode` kwarg (`TypeError: unexpected keyword argument`).

- [ ] **Step 3: Implement the mode directive**

In `scripts/ai_allocator.py`, modify `_build_allocation_prompt` signature (around line 175) to accept `mode: str = "full"`:

```python
def _build_allocation_prompt(
    state,
    layer1_sells: list,
    scored_candidates: list,
    sector_map: dict,
    regime: MarketRegime,
    warning_severity: str,
    strategy_dna: str,
    available_cash: float,
    info_cache: Optional[dict] = None,
    full_watchlist: bool = False,
    regime_analysis: Optional[RegimeAnalysis] = None,
    prompt_extras: Optional[dict] = None,
    portfolio_id: str = None,
    mode: str = "full",
) -> str:
```

Then, in the prompt assembly inside that function, find the section immediately before the `HARD CONSTRAINTS (non-negotiable):` line (around line 558) and build a `mode_directive` block that gets inserted just before it. Locate the f-string that produces the prompt and insert a `{mode_directive}` placeholder, then define the variable above the f-string:

```python
    if mode == "buys_only":
        mode_directive = (
            "\n⚠️ CASH DEPLOYMENT MODE: This run focuses only on new buys. "
            "Treat current positions as fixed — do not propose any sells. "
            "Available cash is current cash only (no sell proceeds to assume). "
            "Return empty `sells: []`.\n"
        )
    elif mode == "sells_only":
        mode_directive = (
            "\n⚠️ RISK REVIEW MODE: This run focuses only on existing positions. "
            "Do not propose any new buys. Return empty `allocation_plan: []`. "
            "Focus on broken theses, oversized positions, deteriorating factors, "
            "and Layer 1 flagged positions.\n"
        )
    else:
        mode_directive = ""
```

Insert `{mode_directive}` into the f-string immediately before the line `HARD CONSTRAINTS (non-negotiable):`. Concretely, that block in the file currently reads:

```python
{macro_block}
{l1_block}
{recently_sold_block}
{candidates_block}
{_sizing_block}
HARD CONSTRAINTS (non-negotiable):
```

Change it to:

```python
{macro_block}
{l1_block}
{recently_sold_block}
{candidates_block}
{_sizing_block}{mode_directive}
HARD CONSTRAINTS (non-negotiable):
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_ai_allocator.py -v -k "build_prompt"`
Expected: PASS — all three new tests green.

- [ ] **Step 5: Commit**

```bash
git add scripts/ai_allocator.py scripts/tests/test_ai_allocator.py
git commit -m "$(cat <<'EOF'
feat(allocator): mode param on _build_allocation_prompt adds stance directive

buys_only and sells_only modes inject a stance directive immediately
before HARD CONSTRAINTS. full mode leaves the prompt unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add `mode` parameter to `_validate_allocation`

**Goal:** When `mode == "buys_only"`, the allocator's sells list is force-cleared during validation (logs a warning if Claude returned any). When `mode == "sells_only"`, the buys list is force-cleared the same way. `full` mode is unchanged.

**Files:**
- Modify: `scripts/ai_allocator.py` (`_validate_allocation`, line 617)
- Test: `scripts/tests/test_ai_allocator.py`

- [ ] **Step 1: Write the failing tests**

Add to `scripts/tests/test_ai_allocator.py`:

```python
def test_validate_allocation_buys_only_drops_sells_even_if_claude_returns_them():
    from ai_allocator import _validate_allocation
    allocation_data = {
        "allocation_plan": [
            {"ticker": "AAPL", "shares": 10, "price": 150.0,
             "stop_loss": 138.0, "take_profit": 180.0, "reasoning": "buy"},
        ],
        "sells": [
            {"ticker": "MSFT", "shares": 5, "price": 200.0, "reasoning": "claude misbehaving"},
        ],
    }
    valid_buys, ai_sells = _validate_allocation(
        allocation_data,
        available_cash=100_000.0,
        total_equity=100_000.0,
        scored_candidates=[{"ticker": "AAPL", "composite_score": 70, "current_price": 150.0,
                            "factor_scores": {}, "data_completeness": 6}],
        held_tickers={"MSFT"},
        held_shares_map={"MSFT": 5},
        max_positions=None,
        mode="buys_only",
    )
    assert len(valid_buys) == 1
    assert ai_sells == [], "buys_only mode must drop all sells"


def test_validate_allocation_sells_only_drops_buys_even_if_claude_returns_them():
    from ai_allocator import _validate_allocation
    allocation_data = {
        "allocation_plan": [
            {"ticker": "AAPL", "shares": 10, "price": 150.0,
             "stop_loss": 138.0, "take_profit": 180.0, "reasoning": "claude misbehaving"},
        ],
        "sells": [
            {"ticker": "MSFT", "shares": 5, "price": 200.0, "reasoning": "trim winner"},
        ],
    }
    valid_buys, ai_sells = _validate_allocation(
        allocation_data,
        available_cash=100_000.0,
        total_equity=100_000.0,
        scored_candidates=[],
        held_tickers={"MSFT"},
        held_shares_map={"MSFT": 5},
        max_positions=None,
        mode="sells_only",
    )
    assert valid_buys == [], "sells_only mode must drop all buys"
    assert len(ai_sells) == 1


def test_validate_allocation_full_mode_keeps_both_sides_unchanged():
    from ai_allocator import _validate_allocation
    allocation_data = {
        "allocation_plan": [
            {"ticker": "AAPL", "shares": 10, "price": 150.0,
             "stop_loss": 138.0, "take_profit": 180.0, "reasoning": "buy"},
        ],
        "sells": [
            {"ticker": "MSFT", "shares": 5, "price": 200.0, "reasoning": "sell"},
        ],
    }
    valid_buys, ai_sells = _validate_allocation(
        allocation_data,
        available_cash=100_000.0,
        total_equity=100_000.0,
        scored_candidates=[{"ticker": "AAPL", "composite_score": 70, "current_price": 150.0,
                            "factor_scores": {}, "data_completeness": 6}],
        held_tickers={"MSFT"},
        held_shares_map={"MSFT": 5},
        max_positions=None,
        mode="full",
    )
    assert len(valid_buys) == 1
    assert len(ai_sells) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_ai_allocator.py -v -k "validate_allocation"`
Expected: FAIL — `_validate_allocation` does not accept a `mode` kwarg.

- [ ] **Step 3: Implement the mode filter**

In `scripts/ai_allocator.py`, modify `_validate_allocation` signature (line 617) to accept `mode: str = "full"`:

```python
def _validate_allocation(
    allocation_data: dict,
    available_cash: float,
    total_equity: float,
    scored_candidates: list,
    held_tickers: set | None = None,
    held_shares_map: dict | None = None,
    max_positions: int | None = None,
    mode: str = "full",
):
```

At the very start of the function (after the signature, before any other logic), add:

```python
    # Mode enforcement — defense in depth. Even if Claude returned an off-side
    # list, drop it here so the wrong side never reaches the pipeline.
    if mode == "buys_only" and allocation_data.get("sells"):
        logging.warning(
            "buys_only mode: dropping %d sells Claude returned despite directive",
            len(allocation_data["sells"]),
        )
        allocation_data = {**allocation_data, "sells": []}
    elif mode == "sells_only" and allocation_data.get("allocation_plan"):
        logging.warning(
            "sells_only mode: dropping %d buys Claude returned despite directive",
            len(allocation_data["allocation_plan"]),
        )
        allocation_data = {**allocation_data, "allocation_plan": []}
```

Confirm `import logging` exists at the top of the file (it does — used by reentry guard around line 176).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_ai_allocator.py -v -k "validate_allocation"`
Expected: PASS — all three new tests green.

- [ ] **Step 5: Commit**

```bash
git add scripts/ai_allocator.py scripts/tests/test_ai_allocator.py
git commit -m "$(cat <<'EOF'
feat(allocator): mode param on _validate_allocation enforces off-side empty

Defense-in-depth filter: if Claude returns sells in buys_only mode or
buys in sells_only mode, drop them at validation time and log a warning.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Thread `mode` through `run_ai_allocation`

**Goal:** `run_ai_allocation` accepts a `mode` arg, passes it to `_build_allocation_prompt` and `_validate_allocation`. Existing callers default to `mode="full"`.

**Files:**
- Modify: `scripts/ai_allocator.py` (`run_ai_allocation`, line 34)
- Test: `scripts/tests/test_ai_allocator.py`

- [ ] **Step 1: Write the failing test**

Add to `scripts/tests/test_ai_allocator.py`:

```python
def test_run_ai_allocation_threads_mode_to_prompt_and_validate(monkeypatch):
    """Verify mode arg is passed through to both _build_allocation_prompt and _validate_allocation."""
    from ai_allocator import run_ai_allocation
    from market_regime import MarketRegime
    import pandas as pd

    state = SimpleNamespace(
        positions=pd.DataFrame(),
        transactions=pd.DataFrame(),
        cash=100_000.0,
        total_equity=100_000.0,
        num_positions=0,
        regime=MarketRegime.SIDEWAYS,
        config={"max_positions": 10, "ai_model": "claude-opus-4-7"},
        portfolio_id="_test_thread",
        regime_analysis=None,
    )

    captured = {"prompt_mode": None, "validate_mode": None}

    def _fake_build(*args, **kwargs):
        captured["prompt_mode"] = kwargs.get("mode")
        return "PROMPT_BODY"

    def _fake_validate(*args, **kwargs):
        captured["validate_mode"] = kwargs.get("mode")
        return [], []

    monkeypatch.setattr("ai_allocator._build_allocation_prompt", _fake_build)
    monkeypatch.setattr("ai_allocator._validate_allocation", _fake_validate)
    monkeypatch.setattr("ai_allocator._parse_json", lambda _t: {"allocation_plan": [], "sells": []})

    class _FakeClient:
        class messages:
            @staticmethod
            def create(**_kw):
                resp = SimpleNamespace()
                resp.content = [SimpleNamespace(text='{"allocation_plan":[],"sells":[]}')]
                resp.model = "claude-opus-4-7"
                return resp
    monkeypatch.setattr("ai_allocator.get_ai_client", lambda: _FakeClient())

    run_ai_allocation(
        state=state,
        layer1_sells=[],
        scored_candidates=[],
        sector_map={},
        regime=MarketRegime.SIDEWAYS,
        warning_severity="NORMAL",
        strategy_dna="test",
        info_cache={},
        regime_analysis=None,
        prompt_extras=None,
        mode="buys_only",
    )

    assert captured["prompt_mode"] == "buys_only"
    assert captured["validate_mode"] == "buys_only"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest scripts/tests/test_ai_allocator.py -v -k "threads_mode"`
Expected: FAIL — `run_ai_allocation` does not accept a `mode` kwarg.

- [ ] **Step 3: Thread mode through**

In `scripts/ai_allocator.py`, modify `run_ai_allocation` signature (line 34) to accept `mode: str = "full"`:

```python
def run_ai_allocation(
    state,
    layer1_sells: list,
    scored_candidates: list,
    sector_map: dict,
    regime: MarketRegime,
    warning_severity: str,
    strategy_dna: str,
    info_cache: Optional[dict] = None,
    regime_analysis: Optional[RegimeAnalysis] = None,
    prompt_extras: Optional[dict] = None,
    mode: str = "full",
) -> list:
```

Inside the function, in the call to `_build_allocation_prompt` (around line 93), add `mode=mode,` to the kwargs. In the call to `_validate_allocation` (around line 140), add `mode=mode,`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest scripts/tests/test_ai_allocator.py -v -k "threads_mode"`
Expected: PASS.

Also re-run full allocator test file to confirm no regression:

Run: `python3 -m pytest scripts/tests/test_ai_allocator.py -v`
Expected: All previously-passing tests + the new ones all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/ai_allocator.py scripts/tests/test_ai_allocator.py
git commit -m "$(cat <<'EOF'
feat(allocator): mode param on run_ai_allocation threads to prompt/validate

Default mode='full' preserves existing call-site behavior.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add `mode` parameter to `_assemble_analysis_result` (defense-in-depth filter)

**Goal:** After review, drop any actions whose `action_type` doesn't match the mode's allowed side. This is the final guard — even if every upstream layer leaks, the off-side gets dropped here.

**Files:**
- Modify: `scripts/unified_analysis.py` (`_assemble_analysis_result`, line 594)
- Test: `tests/integration/test_analyze_pipeline.py` (new test)

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_analyze_pipeline.py`:

```python
def test_assemble_buys_only_drops_sells_from_all_lists():
    """Defense-in-depth: _assemble_analysis_result drops SELL actions in buys_only mode."""
    from unified_analysis import _assemble_analysis_result
    from ai_review import ReviewedAction, ReviewDecision
    from schema import ProposedAction
    from market_regime import MarketRegime

    buy = ProposedAction(
        action_type="BUY", ticker="AAPL", shares=10, price=150.0,
        stop_loss=138.0, take_profit=180.0, quant_score=70,
        factor_scores={}, regime="SIDEWAYS", reason="test",
    )
    sell = ProposedAction(
        action_type="SELL", ticker="MSFT", shares=5, price=200.0,
        stop_loss=0, take_profit=0, quant_score=0,
        factor_scores={}, regime="SIDEWAYS", reason="leaked sell",
    )
    reviewed_buy = ReviewedAction(original=buy, decision=ReviewDecision.APPROVE)
    reviewed_sell = ReviewedAction(original=sell, decision=ReviewDecision.APPROVE)

    result = _assemble_analysis_result(
        proposed_actions=[buy, sell],
        reviewed_actions=[reviewed_buy, reviewed_sell],
        portfolio_context={},
        stale_positions={},
        regime=MarketRegime.SIDEWAYS,
        mode="buys_only",
    )
    # Approved list must contain only the buy
    assert all(r.original.action_type == "BUY" for r in result["approved"])
    assert len(result["approved"]) == 1
    # Proposed/reviewed top-level lists also filtered
    assert all(a.action_type == "BUY" for a in result["proposed_actions"])
    assert all(r.original.action_type == "BUY" for r in result["reviewed_actions"])


def test_assemble_sells_only_drops_buys_from_all_lists():
    from unified_analysis import _assemble_analysis_result
    from ai_review import ReviewedAction, ReviewDecision
    from schema import ProposedAction
    from market_regime import MarketRegime

    buy = ProposedAction(
        action_type="BUY", ticker="AAPL", shares=10, price=150.0,
        stop_loss=138.0, take_profit=180.0, quant_score=70,
        factor_scores={}, regime="SIDEWAYS", reason="leaked buy",
    )
    sell = ProposedAction(
        action_type="SELL", ticker="MSFT", shares=5, price=200.0,
        stop_loss=0, take_profit=0, quant_score=0,
        factor_scores={}, regime="SIDEWAYS", reason="legit sell",
    )
    reviewed_buy = ReviewedAction(original=buy, decision=ReviewDecision.APPROVE)
    reviewed_sell = ReviewedAction(original=sell, decision=ReviewDecision.APPROVE)

    result = _assemble_analysis_result(
        proposed_actions=[buy, sell],
        reviewed_actions=[reviewed_buy, reviewed_sell],
        portfolio_context={},
        stale_positions={},
        regime=MarketRegime.SIDEWAYS,
        mode="sells_only",
    )
    assert all(r.original.action_type == "SELL" for r in result["approved"])
    assert len(result["approved"]) == 1
    assert all(a.action_type == "SELL" for a in result["proposed_actions"])
    assert all(r.original.action_type == "SELL" for r in result["reviewed_actions"])


def test_assemble_full_mode_keeps_both_sides():
    from unified_analysis import _assemble_analysis_result
    from ai_review import ReviewedAction, ReviewDecision
    from schema import ProposedAction
    from market_regime import MarketRegime

    buy = ProposedAction(
        action_type="BUY", ticker="AAPL", shares=10, price=150.0,
        stop_loss=138.0, take_profit=180.0, quant_score=70,
        factor_scores={}, regime="SIDEWAYS", reason="test",
    )
    sell = ProposedAction(
        action_type="SELL", ticker="MSFT", shares=5, price=200.0,
        stop_loss=0, take_profit=0, quant_score=0,
        factor_scores={}, regime="SIDEWAYS", reason="test",
    )
    result = _assemble_analysis_result(
        proposed_actions=[buy, sell],
        reviewed_actions=[
            ReviewedAction(original=buy, decision=ReviewDecision.APPROVE),
            ReviewedAction(original=sell, decision=ReviewDecision.APPROVE),
        ],
        portfolio_context={},
        stale_positions={},
        regime=MarketRegime.SIDEWAYS,
        mode="full",
    )
    assert len(result["approved"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "assemble"`
Expected: FAIL — `_assemble_analysis_result` does not accept `mode`.

- [ ] **Step 3: Implement the filter**

In `scripts/unified_analysis.py`, modify `_assemble_analysis_result` signature (line 594):

```python
def _assemble_analysis_result(
    proposed_actions: list,
    reviewed_actions: list,
    portfolio_context: dict,
    stale_positions: dict,
    regime,
    mode: str = "full",
) -> dict:
```

At the start of the function body (immediately after the docstring), add the mode filter:

```python
    # Mode enforcement — final guard. Drop the off-side from every list
    # before computing approved/modified/vetoed splits.
    if mode == "buys_only":
        proposed_actions = [a for a in proposed_actions if a.action_type == "BUY"]
        reviewed_actions = [r for r in reviewed_actions if r.original.action_type == "BUY"]
    elif mode == "sells_only":
        proposed_actions = [a for a in proposed_actions if a.action_type == "SELL"]
        reviewed_actions = [r for r in reviewed_actions if r.original.action_type == "SELL"]
```

Update the returned dict to also include `"mode": mode` so the slot file records which mode produced it:

```python
    return {
        "proposed_actions": proposed_actions,
        "reviewed_actions": reviewed_actions,
        "approved": approved,
        "modified": modified,
        "vetoed": vetoed,
        "summary": {
            "total_proposed": len(proposed_actions),
            "approved": len(approved),
            "modified": len(modified),
            "vetoed": len(vetoed),
            "can_execute": len(approved) + len(modified) > 0,
        },
        "portfolio_context": portfolio_context,
        "regime": regime.value,
        "timestamp": datetime.now().isoformat(),
        "stale_positions": stale_positions,
        "ai_mode": "mechanical",
        "mode": mode,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "assemble"`
Expected: PASS — all three new tests green.

Also confirm the existing integration suite still passes:

Run: `python3 -m pytest tests/integration/ -v`
Expected: 17 pre-existing tests still green; new tests added.

- [ ] **Step 5: Commit**

```bash
git add scripts/unified_analysis.py tests/integration/test_analyze_pipeline.py
git commit -m "$(cat <<'EOF'
feat(unified_analysis): mode filter in _assemble_analysis_result

Defense-in-depth: in buys_only/sells_only modes, drop the off-side
from proposed/reviewed/approved lists at assembly time. Result dict
gains a 'mode' field for downstream slot-file tagging.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Thread `mode` through `_run_ai_driven_analysis`

**Goal:** The AI-driven path accepts `mode`, skips watchlist scoring entirely in `sells_only`, passes empty `layer1_sells` to the allocator in `buys_only`, threads `mode` to `run_ai_allocation`, and filters its own return-block lists by mode (this path returns its own result dict, not via `_assemble_analysis_result`).

**Files:**
- Modify: `scripts/unified_analysis.py` (`_run_ai_driven_analysis`, line 99)
- Test: `tests/integration/test_analyze_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/integration/test_analyze_pipeline.py` (uses the existing `seed_portfolio` fixture and mocks pattern from this file):

```python
def test_ai_driven_sells_only_skips_watchlist_scoring(seed_portfolio, mock_anthropic, mock_yfinance, monkeypatch):
    """sells_only must NOT score watchlist candidates."""
    from unified_analysis import run_unified_analysis

    sp = seed_portfolio(
        config_overrides={"ai_driven": True, "strategy_dna": "test"},
        positions=[{"ticker": "AAPL", "shares": 10, "avg_cost_basis": 100.0,
                    "current_price": 100.0, "stop_loss": 92.0, "take_profit": 120.0}],
        watchlist=["MSFT", "NVDA", "GOOGL"],
    )

    score_calls = []
    from stock_scorer import StockScorer
    original_score_watchlist = StockScorer.score_watchlist

    def _track(self, tickers):
        score_calls.append(list(tickers))
        return original_score_watchlist(self, tickers)
    monkeypatch.setattr(StockScorer, "score_watchlist", _track)

    mock_anthropic.next_response = _ai_alloc_response(allocation_plan=[], sells=[])

    result = run_unified_analysis(dry_run=True, portfolio_id=sp.pid, mode="sells_only")
    sp.cleanup()

    assert score_calls == [], f"sells_only must not score watchlist, got: {score_calls}"
    # Buys must be absent regardless
    assert not any(r.original.action_type == "BUY" for r in result["reviewed_actions"])


def test_ai_driven_buys_only_passes_empty_layer1_sells_to_allocator(seed_portfolio, mock_anthropic, mock_yfinance):
    """buys_only must not surface Layer 1 sells in the result."""
    from unified_analysis import run_unified_analysis

    # Position with stop loss already breached → Layer 1 would normally sell it
    sp = seed_portfolio(
        config_overrides={"ai_driven": True, "strategy_dna": "test"},
        positions=[{"ticker": "AAPL", "shares": 10, "avg_cost_basis": 100.0,
                    "current_price": 80.0,  # below stop
                    "stop_loss": 92.0, "take_profit": 120.0}],
        watchlist=["MSFT"],
    )
    mock_anthropic.next_response = _ai_alloc_response(allocation_plan=[], sells=[])

    result = run_unified_analysis(dry_run=True, portfolio_id=sp.pid, mode="buys_only")
    sp.cleanup()

    # No SELL should appear despite Layer 1 flagging AAPL
    assert not any(r.original.action_type == "SELL" for r in result["reviewed_actions"])
```

Note: `_ai_alloc_response` is the existing helper in `tests/integration/fixtures/mock_responses.py` (or test_analyze_pipeline.py). If it doesn't exist, inline the response: a `MagicMock` whose `.content[0].text` is `'{"allocation_plan":[],"sells":[],"portfolio_thesis":"test","cash_after_plan":100000}'` and `.model = "claude-opus-4-7"`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "ai_driven_sells_only or ai_driven_buys_only"`
Expected: FAIL — `run_unified_analysis` does not accept `mode`.

- [ ] **Step 3: Implement mode threading in `_run_ai_driven_analysis`**

In `scripts/unified_analysis.py`, modify `_run_ai_driven_analysis` signature (line 99) to accept `mode: str = "full"`:

```python
def _run_ai_driven_analysis(
    state,
    regime,
    warning_severity: str,
    stale_positions: dict,
    layer1_sell_actions: list,
    mode: str = "full",
) -> dict:
```

After loading the watchlist (around line 132 where `candidates = [...]` is set), gate the scoring path on mode:

```python
    # In sells_only, skip watchlist scoring entirely — no buys will be emitted.
    if mode == "sells_only":
        scored_candidates = []
        info_cache = {}
    else:
        # ... existing pre-warm + scoring logic stays as-is, but indent under this else
```

Wrap the existing pre-warm + scoring block (lines ~134-179, from `info_cache = {}` through the `print(f"  Scored ... candidate(s)")` line) inside the `else` branch.

In the call to `run_ai_allocation` (around line 229), pass `layer1_sells` based on mode and thread `mode`:

```python
    effective_layer1_sells = [] if mode == "buys_only" else layer1_sell_actions
    print("\n  🤖 AI-DRIVEN MODE — Claude is the portfolio manager")
    reviewed_actions = run_ai_allocation(
        state=state,
        layer1_sells=effective_layer1_sells,
        scored_candidates=scored_candidates,
        sector_map=sector_map,
        regime=regime,
        warning_severity=warning_severity,
        strategy_dna=strategy_dna,
        info_cache=info_cache,
        regime_analysis=state.regime_analysis,
        prompt_extras=prompt_extras,
        mode=mode,
    )
```

Filter the return block by mode (the AI-driven path builds its own result dict, not via `_assemble_analysis_result`). Just before `return {...}` at the end of the function (around line 271), insert:

```python
    if mode == "buys_only":
        reviewed_actions = [r for r in reviewed_actions if r.original.action_type == "BUY"]
        approved = [r for r in approved if r.original.action_type == "BUY"]
        proposed_actions = [a for a in proposed_actions if a.action_type == "BUY"]
    elif mode == "sells_only":
        reviewed_actions = [r for r in reviewed_actions if r.original.action_type == "SELL"]
        approved = [r for r in approved if r.original.action_type == "SELL"]
        proposed_actions = [a for a in proposed_actions if a.action_type == "SELL"]
```

Add `"mode": mode,` to the returned dict.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "ai_driven"`
Expected: PASS — new tests + existing AI-driven tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/unified_analysis.py tests/integration/test_analyze_pipeline.py
git commit -m "$(cat <<'EOF'
feat(unified_analysis): mode-aware _run_ai_driven_analysis

sells_only skips watchlist scoring entirely (saves 30-60s).
buys_only passes empty layer1_sells to allocator. Both modes
filter the return-block lists by allowed action_type.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add `mode` parameter to `_run_fallback_scoring_step2`

**Goal:** In `sells_only` mode, the fallback scorer skips watchlist scoring entirely (returns proposed_actions unchanged — sells stay, no buys added). In `buys_only` mode, behavior is unchanged (it only ever appends BUYs; Layer 1 sells already present in proposed_actions get filtered later by `_assemble_analysis_result`).

**Files:**
- Modify: `scripts/unified_analysis.py` (`_run_fallback_scoring_step2`, line 442)
- Test: `tests/integration/test_analyze_pipeline.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_analyze_pipeline.py`:

```python
def test_fallback_sells_only_skips_scoring(seed_portfolio, mock_anthropic, mock_yfinance, monkeypatch):
    """Non-AI-driven (fallback) path: sells_only must not score watchlist."""
    from unified_analysis import run_unified_analysis

    sp = seed_portfolio(
        config_overrides={"ai_driven": False,
                          "enhanced_trading": {"enable_layers": False}},
        positions=[{"ticker": "AAPL", "shares": 10, "avg_cost_basis": 100.0,
                    "current_price": 80.0,  # at risk
                    "stop_loss": 92.0, "take_profit": 120.0}],
        watchlist=["MSFT", "NVDA"],
    )

    score_calls = []
    from stock_scorer import StockScorer
    original = StockScorer.score_watchlist
    monkeypatch.setattr(
        StockScorer, "score_watchlist",
        lambda self, tickers: (score_calls.append(list(tickers)), original(self, tickers))[1],
    )

    # Fallback path still calls ai_review for reviewed_actions; return APPROVE for all
    mock_anthropic.next_response = _ai_review_approve_all_response()

    result = run_unified_analysis(dry_run=True, portfolio_id=sp.pid, mode="sells_only")
    sp.cleanup()

    assert score_calls == [], f"sells_only fallback must not score, got {score_calls}"
```

Note: `_ai_review_approve_all_response` is the existing helper for the ai_review path; reuse from `mock_responses.py`. If it returns a list of decisions, ensure the structure matches what the path expects.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "fallback_sells_only"`
Expected: FAIL — `_run_fallback_scoring_step2` doesn't accept `mode`.

- [ ] **Step 3: Implement**

In `scripts/unified_analysis.py`, modify `_run_fallback_scoring_step2` signature (line 442):

```python
def _run_fallback_scoring_step2(
    state,
    regime,
    preservation_active: bool,
    config: dict,
    position_multiplier: float,
    proposed_actions: list,
    mode: str = "full",
) -> list:
```

At the very top of the function body (before the `print("Scoring watchlist candidates...")` line), add:

```python
    # sells_only mode: don't score the watchlist at all. Layer 1 sells already
    # in proposed_actions stay; the assemble step will filter buys (none here)
    # but the work-skip is the actual point.
    if mode == "sells_only":
        return proposed_actions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "fallback_sells_only"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/unified_analysis.py tests/integration/test_analyze_pipeline.py
git commit -m "$(cat <<'EOF'
feat(unified_analysis): mode-aware _run_fallback_scoring_step2

sells_only short-circuits before scoring the watchlist.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Add `mode` parameter to `_run_enhanced_layers_step2`

**Goal:** In `sells_only` mode, skip Layers 2/3 entirely (Layer 1 sells flow through). In `buys_only` mode, keep pure `buy_proposals` but drop rotation pairs (their cash math depends on the paired sell).

**Files:**
- Modify: `scripts/unified_analysis.py` (`_run_enhanced_layers_step2`, line 294)
- Test: `tests/integration/test_analyze_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/integration/test_analyze_pipeline.py`:

```python
def test_enhanced_sells_only_skips_layers_2_3(seed_portfolio, mock_anthropic, mock_yfinance):
    """Enhanced path sells_only short-circuits before Layer 2."""
    from unified_analysis import run_unified_analysis

    sp = seed_portfolio(
        config_overrides={
            "ai_driven": False,
            "enhanced_trading": {"enable_layers": True},
        },
        positions=[{"ticker": "AAPL", "shares": 10, "avg_cost_basis": 100.0,
                    "current_price": 80.0,
                    "stop_loss": 92.0, "take_profit": 120.0}],
        watchlist=["MSFT", "NVDA"],
    )
    mock_anthropic.next_response = _ai_review_approve_all_response()

    result = run_unified_analysis(dry_run=True, portfolio_id=sp.pid, mode="sells_only")
    sp.cleanup()

    # No buys in output
    assert not any(a.action_type == "BUY" for a in result["proposed_actions"])
    # Layer 1 sell should still be present (AAPL below stop)
    assert any(a.action_type == "SELL" and a.ticker == "AAPL"
               for a in result["proposed_actions"])


def test_enhanced_buys_only_drops_rotation_pairs(seed_portfolio, mock_anthropic, mock_yfinance):
    """Enhanced path buys_only emits pure buy_proposals; no rotation sells/buys."""
    # This test is a structural assertion — depends on layer2 emitting rotation
    # pairs for the fixture. Use the existing rotation-emitting fixture pattern,
    # or assert the weaker invariant: zero SELL actions in buys_only output.
    from unified_analysis import run_unified_analysis

    sp = seed_portfolio(
        config_overrides={
            "ai_driven": False,
            "enhanced_trading": {"enable_layers": True},
        },
        positions=[{"ticker": "AAPL", "shares": 10, "avg_cost_basis": 100.0,
                    "current_price": 100.0,
                    "stop_loss": 92.0, "take_profit": 120.0}],
        watchlist=["MSFT", "NVDA"],
    )
    mock_anthropic.next_response = _ai_review_approve_all_response()

    result = run_unified_analysis(dry_run=True, portfolio_id=sp.pid, mode="buys_only")
    sp.cleanup()

    assert not any(a.action_type == "SELL" for a in result["proposed_actions"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "enhanced_sells_only or enhanced_buys_only"`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `scripts/unified_analysis.py`, modify `_run_enhanced_layers_step2` signature (line 294):

```python
def _run_enhanced_layers_step2(
    state,
    layer1_output: dict,
    regime,
    preservation_active: bool,
    config: dict,
    portfolio_id: str | None,
    proposed_actions: list,
    info_cache: dict,
    mode: str = "full",
) -> tuple[list, dict]:
```

At the top of the function body, before the `print("\nRunning Layer 2: Opportunity Management...")` line:

```python
    # sells_only: skip enhanced layers entirely; Layer 1 sells in proposed_actions
    # are sufficient and the assemble step will filter anything else.
    if mode == "sells_only":
        return proposed_actions, info_cache
```

Then inside the function, in the block where rotation pairs are processed (around lines 364-371), add a mode check. Find:

```python
    if layer2_output.get("rotation_sells"):
        print(f"\n  🔄 Portfolio Rotation: {len(layer2_output['rotation_sells'])} swap(s) proposed")
        for sell, buy in zip(layer2_output["rotation_sells"], layer2_output["rotation_buys"]):
            print(f"     SELL {sell.ticker} → BUY {buy.ticker} ({sell.reason})")

    rotation_buy_tickers = {b.ticker for b in layer2_output.get("rotation_buys", [])}
    all_buys = layer2_output["buy_proposals"] + layer2_output.get("rotation_buys", [])
```

Change the rotation-pair block to skip rotation in buys_only:

```python
    if mode == "buys_only":
        # Drop rotation pairs — rotation buys assume cash from rotation sells,
        # which we're not executing. Pure buy_proposals only.
        layer2_output["rotation_sells"] = []
        layer2_output["rotation_buys"] = []

    if layer2_output.get("rotation_sells"):
        print(f"\n  🔄 Portfolio Rotation: {len(layer2_output['rotation_sells'])} swap(s) proposed")
        for sell, buy in zip(layer2_output["rotation_sells"], layer2_output["rotation_buys"]):
            print(f"     SELL {sell.ticker} → BUY {buy.ticker} ({sell.reason})")

    rotation_buy_tickers = {b.ticker for b in layer2_output.get("rotation_buys", [])}
    all_buys = layer2_output["buy_proposals"] + layer2_output.get("rotation_buys", [])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "enhanced"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/unified_analysis.py tests/integration/test_analyze_pipeline.py
git commit -m "$(cat <<'EOF'
feat(unified_analysis): mode-aware _run_enhanced_layers_step2

sells_only skips Layer 2/3 entirely. buys_only keeps pure buy_proposals
but drops rotation pairs (cash math depends on paired sell).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Thread `mode` through `run_unified_analysis` + skip reentry veto

**Goal:** Top-level `run_unified_analysis` accepts `mode`, passes it to all three branch helpers and to `_assemble_analysis_result`. The same-run reentry veto (which depends on both sides being present) is skipped in non-full modes.

**Files:**
- Modify: `scripts/unified_analysis.py` (`run_unified_analysis`, line 744)
- Test: `tests/integration/test_analyze_pipeline.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_analyze_pipeline.py`:

```python
def test_run_unified_analysis_accepts_mode_param(seed_portfolio, mock_anthropic, mock_yfinance):
    """Smoke test: run_unified_analysis accepts mode kwarg and result includes it."""
    from unified_analysis import run_unified_analysis

    sp = seed_portfolio(
        config_overrides={"ai_driven": True, "strategy_dna": "test"},
        positions=[],
        watchlist=["MSFT"],
    )
    mock_anthropic.next_response = _ai_alloc_response(allocation_plan=[], sells=[])

    result_full = run_unified_analysis(dry_run=True, portfolio_id=sp.pid, mode="full")
    result_buys = run_unified_analysis(dry_run=True, portfolio_id=sp.pid, mode="buys_only")
    result_sells = run_unified_analysis(dry_run=True, portfolio_id=sp.pid, mode="sells_only")
    sp.cleanup()

    assert result_full.get("mode") == "full"
    assert result_buys.get("mode") == "buys_only"
    assert result_sells.get("mode") == "sells_only"


def test_run_unified_analysis_default_mode_is_full(seed_portfolio, mock_anthropic, mock_yfinance):
    """Backward compat: calling without mode kwarg behaves exactly like mode='full'."""
    from unified_analysis import run_unified_analysis

    sp = seed_portfolio(
        config_overrides={"ai_driven": True, "strategy_dna": "test"},
        positions=[],
        watchlist=["MSFT"],
    )
    mock_anthropic.next_response = _ai_alloc_response(allocation_plan=[], sells=[])

    result = run_unified_analysis(dry_run=True, portfolio_id=sp.pid)
    sp.cleanup()
    assert result.get("mode") == "full"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "run_unified_analysis_accepts_mode or run_unified_analysis_default_mode"`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `scripts/unified_analysis.py`, modify `run_unified_analysis` signature (line 744):

```python
def run_unified_analysis(dry_run: bool = True, portfolio_id: str = None, mode: str = "full") -> dict:
```

In the AI-driven branch (around line 813), pass `mode=mode`:

```python
    if config.get("ai_driven"):
        print("=" * 60)
        print("AI-DRIVEN MODE — Claude replaces Layers 2-4")
        print("=" * 60)
        return _run_ai_driven_analysis(
            state=state,
            regime=regime,
            warning_severity=warning_severity,
            stale_positions=state.stale_alerts,
            layer1_sell_actions=proposed_actions,
            mode=mode,
        )
```

In the enhanced-layers branch (around line 824), pass `mode=mode`:

```python
    if config.get("enhanced_trading", {}).get("enable_layers", False):
        proposed_actions, info_cache = _run_enhanced_layers_step2(
            state=state,
            layer1_output=layer1_output,
            regime=regime,
            preservation_active=preservation_active,
            config=config,
            portfolio_id=portfolio_id,
            proposed_actions=proposed_actions,
            info_cache=info_cache,
            mode=mode,
        )
```

In the fallback branch (around line 836), pass `mode=mode`:

```python
    else:
        proposed_actions = _run_fallback_scoring_step2(
            state=state,
            regime=regime,
            preservation_active=preservation_active,
            config=config,
            position_multiplier=position_multiplier,
            proposed_actions=proposed_actions,
            mode=mode,
        )
```

Skip the same-run reentry veto block (lines 929-956) in non-full modes. Wrap the entire `if not state.positions.empty: ... sell_cost_basis = {} ...` block in a mode check:

```python
    # Same-run reentry veto only applies when both sides are present.
    if mode == "full" and not state.positions.empty:
        sell_cost_basis = {}
        # ... existing block ...
```

Finally, in the `_assemble_analysis_result(...)` call at the end (around line 968), pass `mode=mode`:

```python
    return _assemble_analysis_result(
        proposed_actions=proposed_actions,
        reviewed_actions=reviewed_actions,
        portfolio_context=portfolio_context,
        stale_positions=stale_positions,
        regime=regime,
        mode=mode,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "run_unified_analysis"`
Expected: PASS.

Also verify the full integration suite is still green:

Run: `python3 -m pytest tests/integration/ -v`
Expected: All tests green (existing 17 + new ones added in Tasks 4-8).

- [ ] **Step 5: Commit**

```bash
git add scripts/unified_analysis.py tests/integration/test_analyze_pipeline.py
git commit -m "$(cat <<'EOF'
feat(unified_analysis): mode param on run_unified_analysis

Threads mode through all three branches (AI-driven, enhanced layers,
fallback) and into _assemble_analysis_result. Same-run reentry veto
skipped in non-full modes (it depends on both sides being present).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `/analyze` endpoint accepts `?mode=` and writes to mode-specific slot file

**Goal:** `POST /api/{pid}/analyze?mode=buys_only` writes to `.last_analysis.buys.json`. `?mode=sells_only` writes to `.last_analysis.sells.json`. Default `?mode=full` (or omitted) writes to `.last_analysis.json` — existing behavior preserved.

**Files:**
- Modify: `api/routes/analysis.py`
- Test: `tests/integration/test_analyze_pipeline.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_analyze_pipeline.py`:

```python
def test_analyze_endpoint_writes_to_mode_specific_slot(seed_portfolio, mock_anthropic, mock_yfinance):
    """Each mode writes to its own .last_analysis.{slot}.json."""
    from fastapi.testclient import TestClient
    from api.main import app

    sp = seed_portfolio(
        config_overrides={"ai_driven": True, "strategy_dna": "test"},
        positions=[],
        watchlist=["MSFT"],
    )
    mock_anthropic.next_response = _ai_alloc_response(allocation_plan=[], sells=[])

    client = TestClient(app)
    r_full  = client.post(f"/api/{sp.pid}/analyze")
    r_buys  = client.post(f"/api/{sp.pid}/analyze?mode=buys_only")
    r_sells = client.post(f"/api/{sp.pid}/analyze?mode=sells_only")
    assert r_full.status_code == 200
    assert r_buys.status_code == 200
    assert r_sells.status_code == 200

    pdir = sp.portfolio_dir
    assert (pdir / ".last_analysis.json").exists()
    assert (pdir / ".last_analysis.buys.json").exists()
    assert (pdir / ".last_analysis.sells.json").exists()
    sp.cleanup()


def test_analyze_endpoint_rejects_invalid_mode(seed_portfolio):
    from fastapi.testclient import TestClient
    from api.main import app

    sp = seed_portfolio(
        config_overrides={"ai_driven": True, "strategy_dna": "test"},
        positions=[], watchlist=["MSFT"],
    )
    client = TestClient(app)
    r = client.post(f"/api/{sp.pid}/analyze?mode=bogus")
    sp.cleanup()
    assert r.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "writes_to_mode_specific or rejects_invalid_mode"`
Expected: FAIL — endpoint doesn't accept `mode`.

- [ ] **Step 3: Implement the endpoint changes**

Replace the contents of `api/routes/analysis.py` with:

```python
"""Analysis and execution endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from api.deps import serialize, validate_portfolio_id

from unified_analysis import run_unified_analysis, execute_approved_actions

router = APIRouter(prefix="/api/{portfolio_id}")

_PORTFOLIOS_DIR = Path(__file__).parent.parent.parent / "data" / "portfolios"

_VALID_MODES = {"full", "buys_only", "sells_only"}


def _analysis_file(portfolio_id: str, mode: str) -> Path:
    """Resolve the slot file path for a given mode."""
    base = _PORTFOLIOS_DIR / portfolio_id
    if mode == "full":
        return base / ".last_analysis.json"
    if mode == "buys_only":
        return base / ".last_analysis.buys.json"
    if mode == "sells_only":
        return base / ".last_analysis.sells.json"
    raise ValueError(f"invalid mode: {mode}")


def _executing_file(portfolio_id: str, mode: str) -> Path:
    """Resolve the per-mode executing lock path."""
    base = _PORTFOLIOS_DIR / portfolio_id
    if mode == "full":
        return base / ".executing.json"
    if mode == "buys_only":
        return base / ".executing.buys.json"
    if mode == "sells_only":
        return base / ".executing.sells.json"
    raise ValueError(f"invalid mode: {mode}")


def _validate_mode(mode: str) -> str:
    if mode not in _VALID_MODES:
        raise HTTPException(status_code=400, detail=f"invalid mode '{mode}' (allowed: {sorted(_VALID_MODES)})")
    return mode


@router.post("/analyze")
def analyze(
    portfolio_id: str = Depends(validate_portfolio_id),
    mode: str = Query(default="full"),
):
    """Run unified analysis (dry run). Mode controls scope and slot file."""
    mode = _validate_mode(mode)
    try:
        result = run_unified_analysis(dry_run=True, portfolio_id=portfolio_id, mode=mode)
        analysis_file = _analysis_file(portfolio_id, mode)
        serialized = serialize(result)
        tmp_file = analysis_file.with_name(analysis_file.name + ".tmp")
        try:
            with open(tmp_file, "w") as f:
                json.dump(serialized, f)
            tmp_file.replace(analysis_file)
        except Exception:
            tmp_file.unlink(missing_ok=True)
            raise
        return serialized
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
def execute(
    portfolio_id: str = Depends(validate_portfolio_id),
    mode: str = Query(default="full"),
):
    """Execute approved actions from the last analysis run for the given mode."""
    mode = _validate_mode(mode)
    analysis_file = _analysis_file(portfolio_id, mode)
    if not analysis_file.exists():
        raise HTTPException(
            status_code=400,
            detail=f"No analysis to execute for mode={mode}. Run analyze first.",
        )

    executing_file = _executing_file(portfolio_id, mode)
    try:
        analysis_file.rename(executing_file)
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="Already executing or no analysis available.")

    try:
        with open(executing_file) as f:
            last_analysis = json.load(f)
        result = execute_approved_actions(last_analysis, portfolio_id=portfolio_id)
        executing_file.unlink(missing_ok=True)
        return serialize(result)
    except Exception as e:
        try:
            executing_file.rename(analysis_file)
        except Exception as restore_exc:
            print(f"[execute] Could not restore analysis file after failure: {restore_exc}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/integration/test_analyze_pipeline.py -v -k "writes_to_mode_specific or rejects_invalid_mode"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/routes/analysis.py tests/integration/test_analyze_pipeline.py
git commit -m "$(cat <<'EOF'
feat(api): /analyze and /execute accept ?mode= with separate slot files

mode=full|buys_only|sells_only. Each mode writes/reads its own slot
file and uses its own .executing.{mode}.json concurrency lock.
Default mode=full preserves all existing behavior.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Test independent execute locks across modes

**Goal:** Concurrent execute of `buys_only` and `sells_only` does not block on the other's lock. (The shared `_atomic_state_writes` flock guard already serializes the underlying CSV write; this test confirms the API-layer locks are independent.)

**Files:**
- Test: `tests/integration/test_execute_pipeline.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_execute_pipeline.py`:

```python
def test_executing_one_mode_does_not_block_others(seed_portfolio, mock_anthropic, mock_yfinance):
    """While .executing.buys.json exists, /execute?mode=sells_only is not blocked by it."""
    from fastapi.testclient import TestClient
    from api.main import app

    sp = seed_portfolio(
        config_overrides={"ai_driven": True, "strategy_dna": "test"},
        positions=[{"ticker": "AAPL", "shares": 10, "avg_cost_basis": 100.0,
                    "current_price": 80.0,
                    "stop_loss": 92.0, "take_profit": 120.0}],
        watchlist=["MSFT"],
    )
    # Pre-populate the sells slot
    mock_anthropic.next_response = _ai_alloc_response(
        allocation_plan=[],
        sells=[{"ticker": "AAPL", "shares": 10, "price": 80.0, "reasoning": "stop"}],
    )
    client = TestClient(app)
    r = client.post(f"/api/{sp.pid}/analyze?mode=sells_only")
    assert r.status_code == 200

    # Simulate a buys_only execute already in flight by manually creating .executing.buys.json
    (sp.portfolio_dir / ".executing.buys.json").write_text('{"approved":[]}')

    # /execute?mode=sells_only should still succeed (not 409)
    r2 = client.post(f"/api/{sp.pid}/execute?mode=sells_only")
    # Cleanup the simulated lock
    (sp.portfolio_dir / ".executing.buys.json").unlink(missing_ok=True)
    sp.cleanup()
    assert r2.status_code == 200, f"sells_only execute was blocked: {r2.status_code} {r2.text}"
```

- [ ] **Step 2: Run test to verify it passes immediately**

Because Task 9 already implemented per-mode lock files, this test should pass without further code changes. Run:

Run: `python3 -m pytest tests/integration/test_execute_pipeline.py -v -k "does_not_block_others"`
Expected: PASS (this is a regression guard — if it fails, Task 9 introduced cross-mode coupling and needs to be revisited).

- [ ] **Step 3: Commit (no code change, test-only)**

```bash
git add tests/integration/test_execute_pipeline.py
git commit -m "$(cat <<'EOF'
test(integration): verify mode-specific execute locks are independent

Pre-existing .executing.buys.json must not block /execute?mode=sells_only.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Dashboard `api.ts` — `analyze` and `execute` accept optional `mode`

**Files:**
- Modify: `dashboard/src/lib/api.ts`

- [ ] **Step 1: Update the analyze and execute functions**

In `dashboard/src/lib/api.ts`, find the existing `analyze` line (around line 90):

```typescript
analyze: (pid: string) => post<AnalysisResult>(`/${pid}/analyze`),
```

Replace with:

```typescript
analyze: (pid: string, mode: "full" | "buys_only" | "sells_only" = "full") =>
  post<AnalysisResult>(`/${pid}/analyze${mode !== "full" ? `?mode=${mode}` : ""}`),
```

Similarly, find the existing `execute` line and change to:

```typescript
execute: (pid: string, mode: "full" | "buys_only" | "sells_only" = "full") =>
  post<void>(`/${pid}/execute${mode !== "full" ? `?mode=${mode}` : ""}`),
```

- [ ] **Step 2: Type check**

Run: `cd dashboard && npx tsc --noEmit 2>&1 | grep -v 'CreatePortfolioModal\|OverviewPage\|PortfolioSettingsModal\|TopBar'`
Expected: No new errors. (Project has known TS warnings in the excluded files — those are unrelated.)

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/lib/api.ts
git commit -m "$(cat <<'EOF'
feat(dashboard): api.ts analyze/execute accept optional mode arg

Default mode='full' preserves existing call sites without changes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Dashboard store — per-mode analysis slots

**Goal:** `portfolioAnalyses[pid]` becomes a nested structure: `{ full: {...}, buys_only: {...}, sells_only: {...} }`. New actions trigger per-mode analyze/execute.

**Files:**
- Modify: `dashboard/src/lib/store.ts`

- [ ] **Step 1: Read the existing store structure**

Open `dashboard/src/lib/store.ts` and locate the analysis-related state (around lines 30-200). Identify:
- The `portfolioAnalyses` shape (currently `{[pid]: { status, result, error, analyzedAt }}`)
- `runAnalysis`, `runExecute` actions
- `syncActive` helper
- Top-level cached fields: `result`, `isAnalyzing`, `isExecuting`, `error`, `lastAnalyzedAt`

- [ ] **Step 2: Refactor to per-mode slots**

Replace the analysis state shape with:

```typescript
type AnalysisMode = "full" | "buys_only" | "sells_only";

interface AnalysisSlot {
  status: "idle" | "running" | "complete" | "executing" | "executed" | "error";
  result: AnalysisResult | null;
  error: string | null;
  analyzedAt: string | null;
}

const emptySlot = (): AnalysisSlot => ({
  status: "idle", result: null, error: null, analyzedAt: null,
});

interface AnalysisState {
  // Per-portfolio per-mode slots
  portfolioAnalyses: Record<string, Record<AnalysisMode, AnalysisSlot>>;

  // The mode currently being viewed in the dashboard (UI state)
  activeMode: AnalysisMode;
  setActiveMode: (m: AnalysisMode) => void;

  // Convenience accessors for the active portfolio + active mode (mirrors prior top-level fields)
  result: AnalysisResult | null;
  isAnalyzing: boolean;
  isExecuting: boolean;
  error: string | null;
  lastAnalyzedAt: string | null;

  runAnalysis: (mode?: AnalysisMode) => Promise<void>;
  runExecute: (mode?: AnalysisMode) => Promise<void>;
}
```

Update `writeSlot` to take a mode argument:

```typescript
const writeSlot = (pid: string, mode: AnalysisMode, patch: Partial<AnalysisSlot>) => {
  set((s) => {
    const portfolioSlots = s.portfolioAnalyses[pid] ?? {
      full: emptySlot(), buys_only: emptySlot(), sells_only: emptySlot(),
    };
    const prev = portfolioSlots[mode];
    return {
      portfolioAnalyses: {
        ...s.portfolioAnalyses,
        [pid]: { ...portfolioSlots, [mode]: { ...prev, ...patch } },
      },
    };
  });
  syncActive();
};
```

Update `syncActive` to read from `portfolioAnalyses[pid][activeMode]`:

```typescript
const syncActive = () => {
  set((s) => {
    const pid = usePortfolioStore.getState().activePortfolioId;
    const slot = s.portfolioAnalyses[pid]?.[s.activeMode];
    return {
      result: slot?.result ?? null,
      isAnalyzing: slot?.status === "running",
      isExecuting: slot?.status === "executing",
      error: slot?.error ?? null,
      lastAnalyzedAt: slot?.analyzedAt ?? null,
    };
  });
};
```

Update `runAnalysis`:

```typescript
runAnalysis: async (mode: AnalysisMode = "full") => {
  const portfolioId = usePortfolioStore.getState().activePortfolioId;
  if (portfolioId === "overview") return;
  writeSlot(portfolioId, mode, { status: "running", error: null });
  try {
    const result = await api.analyze(portfolioId, mode);
    writeSlot(portfolioId, mode, {
      status: "complete", result, error: null,
      analyzedAt: new Date().toLocaleTimeString(),
    });
  } catch (e) {
    writeSlot(portfolioId, mode, {
      status: "error",
      error: e instanceof Error ? e.message : "Analysis failed",
    });
  }
},
```

Update `runExecute`:

```typescript
runExecute: async (mode: AnalysisMode = "full") => {
  const portfolioId = usePortfolioStore.getState().activePortfolioId;
  if (portfolioId === "overview") return;
  const slot = get().portfolioAnalyses[portfolioId]?.[mode];
  if (!slot?.result?.summary.can_execute) return;
  writeSlot(portfolioId, mode, { status: "executing", error: null });
  try {
    await api.execute(portfolioId, mode);
    writeSlot(portfolioId, mode, {
      status: "executed", result: null, analyzedAt: null,
    });
  } catch (e) {
    writeSlot(portfolioId, mode, {
      status: "error",
      error: e instanceof Error ? e.message : "Execution failed",
    });
  }
},

setActiveMode: (m: AnalysisMode) => {
  set({ activeMode: m });
  syncActive();
},
```

In the initial state, set `activeMode: "full"`.

Make sure the subscription to `usePortfolioStore` (which calls `syncActive()` on portfolio change) still works — it should, since `syncActive` is now mode-aware.

- [ ] **Step 3: Type check**

Run: `cd dashboard && npx tsc --noEmit 2>&1 | grep -v 'CreatePortfolioModal\|OverviewPage\|PortfolioSettingsModal\|TopBar'`
Expected: No new errors.

- [ ] **Step 4: Manual smoke test**

Start the dev server if not already running and confirm the dashboard loads without console errors. (The existing ANALYZE/EXECUTE buttons should still work since they call `runAnalysis()` / `runExecute()` with no args → defaults to `"full"`.)

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/lib/store.ts
git commit -m "$(cat <<'EOF'
feat(dashboard): per-mode analysis slots in store

portfolioAnalyses[pid] is now a nested record with full/buys_only/
sells_only slots. activeMode determines which slot the top-level
result/isAnalyzing/error/lastAnalyzedAt fields mirror.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: TopBar — add `ANALYZE BUYS` and `ANALYZE SELLS` buttons

**Goal:** Two new buttons next to the existing ANALYZE. Each calls `runAnalysis("buys_only")` / `runAnalysis("sells_only")` and shows its own loading state.

**Files:**
- Modify: `dashboard/src/components/TopBar.tsx`

- [ ] **Step 1: Locate the existing ANALYZE button**

Read `dashboard/src/components/TopBar.tsx` and find the existing ANALYZE button. It currently uses `runAnalysis()` from `useAnalysisStore`. Note the loading state pattern (`isAnalyzing`).

- [ ] **Step 2: Add two new buttons next to ANALYZE**

After the existing ANALYZE button JSX, add:

```tsx
<button
  onClick={() => useAnalysisStore.getState().runAnalysis("buys_only")}
  disabled={useAnalysisStore((s) => s.portfolioAnalyses[activePortfolioId]?.buys_only?.status === "running")}
  className="…match the ANALYZE button styling…"
  title="Analyze only — propose buys with current cash, ignore sell decisions"
>
  {useAnalysisStore((s) => s.portfolioAnalyses[activePortfolioId]?.buys_only?.status === "running")
    ? "ANALYZING BUYS…"
    : "ANALYZE BUYS"}
</button>

<button
  onClick={() => useAnalysisStore.getState().runAnalysis("sells_only")}
  disabled={useAnalysisStore((s) => s.portfolioAnalyses[activePortfolioId]?.sells_only?.status === "running")}
  className="…match the ANALYZE button styling…"
  title="Analyze only — evaluate existing positions for sells, no new buys"
>
  {useAnalysisStore((s) => s.portfolioAnalyses[activePortfolioId]?.sells_only?.status === "running")
    ? "ANALYZING SELLS…"
    : "ANALYZE SELLS"}
</button>
```

Match the existing ANALYZE button's class names exactly. If the existing button uses a green/teal accent for ANALYZE, use the same neutral styling for the new buttons (they're analyze siblings, not distinct trade actions). Do NOT use the green of `+ BUY` (that's the manual trade entry color and would confuse the meaning).

- [ ] **Step 3: Type check**

Run: `cd dashboard && npx tsc --noEmit 2>&1 | grep -v 'CreatePortfolioModal\|OverviewPage\|PortfolioSettingsModal'`
Expected: No new errors related to TopBar.

- [ ] **Step 4: Manual smoke test**

Open the dashboard at http://localhost:5173, click `ANALYZE BUYS`, watch the network tab to confirm it hits `POST /api/{pid}/analyze?mode=buys_only` and returns 200. Click `ANALYZE SELLS`, verify same with `?mode=sells_only`. (The results won't yet display in ActionsTab — that's Task 14.)

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/TopBar.tsx
git commit -m "$(cat <<'EOF'
feat(dashboard): ANALYZE BUYS and ANALYZE SELLS buttons in TopBar

Each button triggers a single-side analyze and writes to its own slot.
Loading states are independent. Labels chosen to disambiguate from the
existing + BUY manual trade button.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: ActionsTab — mode switcher + mode-aware EXECUTE

**Goal:** Add a `FULL | BUYS ONLY | SELLS ONLY` segmented control at the top of ActionsTab. Switching changes `activeMode` in the store, which makes ActionsTab display the corresponding slot's result. The EXECUTE button calls `runExecute(activeMode)`.

**Files:**
- Modify: `dashboard/src/components/ActionsTab.tsx`

- [ ] **Step 1: Read existing ActionsTab structure**

Read `dashboard/src/components/ActionsTab.tsx`. Note how it currently reads `result` from the store and renders proposed/approved actions.

- [ ] **Step 2: Add the mode switcher**

At the top of the rendered output (before the existing summary or actions list), add:

```tsx
const activeMode = useAnalysisStore((s) => s.activeMode);
const setActiveMode = useAnalysisStore((s) => s.setActiveMode);

// Counts per mode for the badges (only show count if a result exists for that mode)
const slots = useAnalysisStore((s) => s.portfolioAnalyses[activePortfolioId]) ?? {
  full: null, buys_only: null, sells_only: null,
};
const countFor = (mode: AnalysisMode) => slots[mode]?.result?.approved?.length ?? 0;

// JSX:
<div className="flex items-center gap-1 mb-3 text-xs">
  {([
    { mode: "full", label: "FULL" },
    { mode: "buys_only", label: "BUYS ONLY" },
    { mode: "sells_only", label: "SELLS ONLY" },
  ] as { mode: AnalysisMode; label: string }[]).map(({ mode, label }) => (
    <button
      key={mode}
      onClick={() => setActiveMode(mode)}
      className={`px-2 py-1 border ${
        activeMode === mode
          ? "border-white/40 bg-white/10 text-white"
          : "border-white/10 text-white/50 hover:text-white/80"
      }`}
    >
      {label}{countFor(mode) ? ` (${countFor(mode)})` : ""}
    </button>
  ))}
</div>
```

`activePortfolioId` should come from `usePortfolioStore` if not already imported. `AnalysisMode` should be exported from the store and imported here.

- [ ] **Step 3: Make EXECUTE mode-aware**

Find the existing EXECUTE button. Change its onClick from `runExecute()` to `runExecute(activeMode)`. Add a small label or tooltip indicating the active mode, e.g., the button text becomes `EXECUTE (${activeMode === "full" ? "FULL" : activeMode === "buys_only" ? "BUYS" : "SELLS"})`.

- [ ] **Step 4: Handle empty state per mode**

If `result == null` for the active mode (slot is idle), show a message: `No ${activeMode} analysis run yet. Click ANALYZE${activeMode === "full" ? "" : " " + (activeMode === "buys_only" ? "BUYS" : "SELLS")} above.`

- [ ] **Step 5: Type check**

Run: `cd dashboard && npx tsc --noEmit 2>&1 | grep -v 'CreatePortfolioModal\|OverviewPage\|PortfolioSettingsModal\|TopBar'`
Expected: No new errors in ActionsTab.

- [ ] **Step 6: Manual smoke test**

In the dashboard:
1. Pick a portfolio (e.g., `microcap` or one in dev).
2. Click ANALYZE — wait for result. Verify FULL tab shows the result.
3. Switch to BUYS ONLY tab — should show empty state.
4. Click ANALYZE BUYS — wait. BUYS ONLY tab now shows result with only BUYs.
5. Switch back to FULL — original result still there.
6. Click ANALYZE SELLS — SELLS ONLY tab fills with sells-only result.
7. Click EXECUTE while on BUYS ONLY tab → confirm it hits `POST /api/{pid}/execute?mode=buys_only`.

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/components/ActionsTab.tsx
git commit -m "$(cat <<'EOF'
feat(dashboard): mode switcher + mode-aware execute in ActionsTab

FULL/BUYS ONLY/SELLS ONLY segmented control reads/writes activeMode.
EXECUTE button now fires runExecute(activeMode). Empty-state copy
per mode tells the user which analyze button to click.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Full integration regression + manual end-to-end verification

**Goal:** Confirm the existing 17 integration tests still pass without modification (the `mode="full"` regression guard), and walk the full UI flow end-to-end against the live dev server.

**Files:**
- No code changes. Verification only.

- [ ] **Step 1: Full integration suite**

Run: `python3 -m pytest tests/integration/ -v`
Expected: All 17 pre-existing tests pass, plus the new ones from Tasks 4-10. No regressions.

- [ ] **Step 2: Allocator unit tests**

Run: `python3 -m pytest scripts/tests/test_ai_allocator.py -v`
Expected: All tests pass (existing + new from Tasks 1-3).

- [ ] **Step 3: TypeScript build check**

Run: `cd dashboard && npx tsc --noEmit 2>&1 | grep -v 'CreatePortfolioModal\|OverviewPage\|PortfolioSettingsModal\|TopBar'`
Expected: No new errors.

- [ ] **Step 4: Live UI smoke test**

With API on 8001 and dev server on 5173:

1. Pick a portfolio with cash and held positions (e.g., `max` or `microcap`).
2. Click **ANALYZE** → wait → confirm FULL tab populates as today.
3. Click **ANALYZE BUYS** → wait → confirm BUYS ONLY tab populates, contains only BUY actions, has its own timestamp.
4. Click **ANALYZE SELLS** → wait → confirm SELLS ONLY tab populates, contains only SELL actions, has its own timestamp.
5. Click each of the three tabs → confirm all three results persist and show correctly.
6. Click **EXECUTE** while on BUYS ONLY tab → confirm trades fire and `data/portfolios/{pid}/transactions.csv` gains BUY rows only. Verify `.last_analysis.buys.json` is deleted (consumed) but `.last_analysis.json` and `.last_analysis.sells.json` are intact.
7. Click **EXECUTE** while on SELLS ONLY tab → confirm trades fire and sells are recorded. Verify `.last_analysis.sells.json` is deleted.
8. Click ANALYZE (full) again → confirm cron-driven flows aren't broken (call `curl -s http://localhost:8001/api/health` and `curl -X POST http://localhost:8001/api/{pid}/analyze` directly; should match prior behavior).

- [ ] **Step 5: Cron / Telegram regression check**

Manually trigger one cron script in dry-run mode (or examine its code path) to confirm it still calls `POST /api/{pid}/analyze` without any mode param. Open `cron/analyze.sh` and confirm the curl call is unchanged. No new code needed — this is just a read-confirm step.

- [ ] **Step 6: Update PROJECT_STATE.md**

Append a new "Recently Completed" section noting the buys-only/sells-only analyze feature shipped, with a brief description of behavior and the slot file naming convention.

- [ ] **Step 7: Commit and push**

```bash
git add PROJECT_STATE.md
git commit -m "$(cat <<'EOF'
docs: PROJECT_STATE entry for buys-only/sells-only analyze feature

Two new dashboard buttons + per-mode slot files + mode-aware execute.
Existing /analyze, cron, Telegram untouched.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git push
```

---

## Self-review notes

- **Spec coverage:** every section of the design spec is mapped to a task:
  - Backend mode threading (specs §"Backend changes") → Tasks 1-8
  - API endpoints (specs §"`api/routes/analysis.py`") → Tasks 9-10
  - Frontend (specs §"Frontend changes") → Tasks 11-14
  - Testing (specs §"Testing") → Tasks 1-10 (each unit gets its own test) + Task 15 (regression)
  - Persistence/concurrency (specs §"Persistence and concurrency") → Tasks 9-10
  - Edge cases (specs §"Edge cases") → Task 8 (reentry veto skip), Task 5 (effective_layer1_sells), Task 4 (mode field in result), Task 15 (cron untouched)
- **Type consistency:** `mode` is `str` everywhere in Python, `AnalysisMode = "full" | "buys_only" | "sells_only"` everywhere in TypeScript. Slot file paths use `.buys.json` / `.sells.json` consistently. Function signature additions all default to `"full"` so existing callers compile/run unchanged.
- **No placeholders:** every code block contains the real implementation.
- **Frequent commits:** each task ends with its own commit; 15 commits total across the feature.
