# Reentry Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reentry awareness to GScott so that when a recently-sold ticker is proposed as a buy, the AI receives exit context + factor score delta since entry, enabling informed reentry decisions.

**Architecture:** Two complementary mechanisms — (1) make the existing 7-day stop-loss hard cooldown configurable per portfolio, and (2) inject a `REENTRY CONTEXT` block into both AI review prompts (ai_review.py for mechanical path, ai_allocator.py for AI-driven path) whenever a buy candidate was recently sold. A new standalone module `reentry_guard.py` owns all logic and formatting; `BuyProposal` and `ProposedAction` each gain a `reentry_context` field; both mechanical and AI-driven paths populate it independently.

**Tech Stack:** Python 3, pandas, pathlib, dataclasses, existing FastAPI/scripts architecture. No new dependencies.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/reentry_guard.py` | **Create** | `get_reentry_context()` + `_format_reentry_block()` — zero trading-module imports |
| `tests/test_reentry_guard.py` | **Create** | 15 unit tests (see test matrix in spec) |
| `scripts/enhanced_structures.py` | **Modify** | Add `reentry_context: Optional[dict] = None` to `BuyProposal` and `ProposedAction` |
| `scripts/opportunity_layer.py` | **Modify** | Read config, make cooldown configurable, attach reentry context to each buy proposal |
| `scripts/unified_analysis.py` | **Modify** | (1) Mechanical path: copy field to `ProposedAction`. (2) AI-driven path: call `get_reentry_context()` in `scored_candidates` loop |
| `scripts/ai_review.py` | **Modify** | Inject `_format_reentry_block()` after Factor Scores for BUY actions |
| `scripts/ai_allocator.py` | **Modify** | Same injection in candidate rendering loop |
| `scripts/strategy_generator.py` | **Modify** | Extend `SUGGEST_CONFIG_PROMPT` + `suggest_config_for_dna()` to include `reentry_guard` |
| `scripts/portfolio_registry.py` | **Modify** | Apply `reentry_guard` from `ai_config` in `create_portfolio()` |

---

## Task 1: Create `reentry_guard.py` with failing tests

**Files:**
- Create: `scripts/reentry_guard.py`
- Create: `tests/test_reentry_guard.py`

### Background

`reentry_guard.py` is the core module. It must have **zero imports from other trading modules** — only stdlib + pandas. This prevents circular imports. The `get_reentry_context()` function reads `transactions.csv`, finds the most recent SELL within the lookback window, finds the most recent BUY for entry scores, computes factor delta, and returns a context dict (or `None` if no recent exit). The `_format_reentry_block()` function formats that dict into a multi-line string for AI prompts.

### Key behaviors to understand before writing tests:

- Return `None` if `transactions_path` doesn't exist
- Return `None` if no SELL within `lookback_days`
- Return context dict if SELL found within window (even without factor scores on BUY)
- `delta` is `None` if no BUY factor_scores found
- `meaningful_change = any(abs(v) >= threshold for v in delta.values())` — `False` if delta is None or empty
- Uses most recent SELL and most recent BUY (by date) when multiple exist
- `"composite"` key must be excluded from delta computation
- All errors swallowed: returns `None` with `logging.warning()`

---

- [ ] **Step 1: Write all 15 failing tests**

Create `tests/test_reentry_guard.py`:

```python
#!/usr/bin/env python3
"""Tests for reentry_guard module."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from reentry_guard import _format_reentry_block, get_reentry_context


def _make_csv(tmp_path, rows):
    """Write a transactions CSV with the given rows and return the path."""
    df = pd.DataFrame(rows)
    p = tmp_path / "transactions.csv"
    df.to_csv(p, index=False)
    return p


TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
LAST_WEEK = TODAY - timedelta(days=6)
LONG_AGO = TODAY - timedelta(days=45)


def _buy(ticker, factor_scores=None, d=None):
    d = d or (TODAY - timedelta(days=14))
    return {
        "ticker": ticker, "action": "BUY", "date": str(d),
        "factor_scores": json.dumps(factor_scores) if factor_scores else "",
    }


def _sell(ticker, reason="STOP_LOSS", d=None):
    d = d or LAST_WEEK
    return {"ticker": ticker, "action": "SELL", "date": str(d), "reason": reason, "factor_scores": ""}


ENTRY_SCORES = {"price_momentum": 60.0, "quality": 70.0, "volume": 55.0,
                "volatility": 65.0, "earnings_growth": 50.0, "value_timing": 45.0}

CURRENT_SCORES = {"price_momentum": 72.0, "quality": 71.0, "volume": 56.0,
                  "volatility": 64.0, "earnings_growth": 51.0, "value_timing": 46.0}  # momentum +12


def test_returns_none_no_recent_sell(tmp_path):
    """No SELL transaction at all → None."""
    p = _make_csv(tmp_path, [_buy("AAPL", ENTRY_SCORES)])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is None


def test_returns_none_sell_outside_window(tmp_path):
    """SELL older than lookback_days → None."""
    p = _make_csv(tmp_path, [_sell("AAPL", d=LONG_AGO)])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is None


def test_returns_context_with_delta(tmp_path):
    """SELL + BUY both found with factor_scores → dict with delta not None."""
    p = _make_csv(tmp_path, [_buy("AAPL", ENTRY_SCORES), _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is not None
    assert result["delta"] is not None
    assert "price_momentum" in result["delta"]


def test_returns_context_without_delta_no_buy_scores(tmp_path):
    """SELL found, BUY has no factor_scores → dict with delta=None."""
    p = _make_csv(tmp_path, [_buy("AAPL", factor_scores=None), _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is not None
    assert result["delta"] is None


def test_meaningful_change_true(tmp_path):
    """price_momentum delta of +12 >= threshold 10 → meaningful_change=True."""
    p = _make_csv(tmp_path, [_buy("AAPL", ENTRY_SCORES), _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result["meaningful_change"] is True


def test_meaningful_change_false(tmp_path):
    """All factor deltas < threshold 10 → meaningful_change=False."""
    small_change = {k: v + 2.0 for k, v in ENTRY_SCORES.items()}  # all +2, < 10
    p = _make_csv(tmp_path, [_buy("AAPL", ENTRY_SCORES), _sell("AAPL")])
    result = get_reentry_context("AAPL", p, small_change, 30, 10)
    assert result["meaningful_change"] is False


def test_uses_most_recent_sell(tmp_path):
    """Two SELLs in window — context uses the more recent one."""
    older_sell = _sell("AAPL", d=TODAY - timedelta(days=10))
    newer_sell = _sell("AAPL", reason="TAKE_PROFIT", d=TODAY - timedelta(days=3))
    p = _make_csv(tmp_path, [_buy("AAPL", ENTRY_SCORES), older_sell, newer_sell])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result["exit_reason"] == "TAKE_PROFIT"
    assert result["days_since_exit"] == 3


def test_uses_most_recent_buy_for_entry_scores(tmp_path):
    """Two BUYs — more recent BUY scores are used for delta baseline."""
    old_scores = {k: 40.0 for k in ENTRY_SCORES}
    new_scores = ENTRY_SCORES
    older_buy = _buy("AAPL", old_scores, d=TODAY - timedelta(days=60))
    newer_buy = _buy("AAPL", new_scores, d=TODAY - timedelta(days=14))
    p = _make_csv(tmp_path, [older_buy, newer_buy, _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    # delta should be vs new_scores (60.0), not old_scores (40.0)
    expected_momentum_delta = CURRENT_SCORES["price_momentum"] - new_scores["price_momentum"]
    assert abs(result["delta"]["price_momentum"] - expected_momentum_delta) < 0.01


def test_sell_exactly_on_boundary(tmp_path):
    """SELL date == today - lookback_days → included (>= boundary)."""
    boundary_date = TODAY - timedelta(days=30)
    p = _make_csv(tmp_path, [_sell("AAPL", d=boundary_date)])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is not None


def test_sell_one_day_outside_boundary(tmp_path):
    """SELL date == today - lookback_days - 1 → None."""
    just_outside = TODAY - timedelta(days=31)
    p = _make_csv(tmp_path, [_sell("AAPL", d=just_outside)])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is None


def test_handles_missing_transactions_file():
    """Path does not exist → None (no exception raised)."""
    result = get_reentry_context("AAPL", Path("/nonexistent/transactions.csv"), CURRENT_SCORES, 30, 10)
    assert result is None


def test_handles_missing_ticker_column(tmp_path):
    """CSV has no ticker column → None (no exception raised)."""
    df = pd.DataFrame([{"symbol": "AAPL", "action": "SELL", "date": str(LAST_WEEK)}])
    p = tmp_path / "transactions.csv"
    df.to_csv(p, index=False)
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is None


def test_handles_malformed_factor_scores_json(tmp_path):
    """factor_scores contains invalid JSON → context with exit_scores=None."""
    row = _buy("AAPL")
    row["factor_scores"] = "{not valid json"
    p = _make_csv(tmp_path, [row, _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is not None
    assert result["exit_scores"] is None
    assert result["delta"] is None


def test_handles_empty_factor_scores(tmp_path):
    """factor_scores is empty string → context with exit_scores=None."""
    p = _make_csv(tmp_path, [_buy("AAPL", factor_scores=None), _sell("AAPL")])
    result = get_reentry_context("AAPL", p, CURRENT_SCORES, 30, 10)
    assert result is not None
    assert result["exit_scores"] is None


def test_excludes_composite_from_delta(tmp_path):
    """BUY factor_scores includes 'composite' key → delta dict does not contain 'composite'."""
    scores_with_composite = dict(ENTRY_SCORES, composite=65.0)
    p = _make_csv(tmp_path, [_buy("AAPL", scores_with_composite), _sell("AAPL")])
    current_with_composite = dict(CURRENT_SCORES, composite=70.0)
    result = get_reentry_context("AAPL", p, current_with_composite, 30, 10)
    assert result is not None
    assert result["delta"] is not None
    assert "composite" not in result["delta"]
```

- [ ] **Step 2: Run tests to verify they all fail** (module doesn't exist yet)

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/test_reentry_guard.py -v 2>&1 | head -40
```

Expected: All 15 tests fail with `ModuleNotFoundError: No module named 'reentry_guard'`

- [ ] **Step 3: Implement `reentry_guard.py`**

Create `scripts/reentry_guard.py`:

```python
#!/usr/bin/env python3
"""Reentry guard — detects recent exits and computes factor score delta for AI review."""
import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd


def get_reentry_context(
    ticker: str,
    transactions_path: Path,
    current_scores: Optional[dict],
    lookback_days: int,
    meaningful_change_threshold_pts: float,
) -> Optional[dict]:
    """Return reentry context dict if ticker was recently sold, else None.

    Args:
        ticker: Ticker symbol to check (case-insensitive).
        transactions_path: Path to transactions.csv for the portfolio.
        current_scores: Current factor scores dict (without 'composite' key).
        lookback_days: How far back to look for SELL transactions.
        meaningful_change_threshold_pts: Min abs delta to flag as meaningful change.

    Returns:
        Dict with exit context and factor delta, or None if no recent exit.
    """
    if not Path(transactions_path).exists():
        return None

    try:
        df = pd.read_csv(transactions_path, dtype=str)

        if "ticker" not in df.columns:
            return None

        df["ticker"] = df["ticker"].str.strip().str.upper()
        ticker = ticker.strip().upper()
        ticker_df = df[df["ticker"] == ticker]

        # Find most recent SELL within lookback window
        cutoff = date.today() - timedelta(days=lookback_days)
        sells = ticker_df[ticker_df["action"] == "SELL"].copy()
        if sells.empty:
            return None

        sells["_date"] = pd.to_datetime(sells["date"], errors="coerce").dt.date
        sells = sells.dropna(subset=["_date"])
        sells = sells[sells["_date"] >= cutoff]
        if sells.empty:
            return None

        most_recent_sell = sells.sort_values("_date", ascending=False).iloc[0]
        exit_date = most_recent_sell["_date"]
        days_since_exit = (date.today() - exit_date).days
        exit_reason = most_recent_sell.get("reason", "SIGNAL") if "reason" in most_recent_sell.index else "SIGNAL"
        if pd.isna(exit_reason) or not str(exit_reason).strip():
            exit_reason = "SIGNAL"

        # Find most recent BUY for entry scores
        buys = ticker_df[ticker_df["action"] == "BUY"].copy()
        exit_scores = None
        if not buys.empty and "factor_scores" in buys.columns:
            buys["_date"] = pd.to_datetime(buys["date"], errors="coerce").dt.date
            buys = buys.dropna(subset=["_date"])
            if not buys.empty:
                most_recent_buy = buys.sort_values("_date", ascending=False).iloc[0]
                raw = most_recent_buy.get("factor_scores", "")
                if raw and str(raw).strip() not in ("", "nan", "null", "None"):
                    try:
                        parsed = json.loads(str(raw))
                        if isinstance(parsed, dict) and parsed:
                            exit_scores = {k: v for k, v in parsed.items() if k != "composite"}
                    except Exception as e:
                        logging.warning("reentry_guard: failed to parse factor_scores for %s: %s", ticker, e)

        # Compute delta
        delta = None
        if exit_scores is not None and current_scores is not None:
            filtered_current = {k: v for k, v in current_scores.items() if k != "composite"}
            delta = {
                f: float(filtered_current[f]) - float(exit_scores[f])
                for f in exit_scores
                if f in filtered_current
            }

        meaningful_change = (
            any(abs(v) >= meaningful_change_threshold_pts for v in delta.values())
            if delta
            else False
        )

        return {
            "exit_date": str(exit_date),
            "exit_reason": str(exit_reason),
            "days_since_exit": days_since_exit,
            "exit_scores": exit_scores,
            "current_scores": current_scores if exit_scores is not None else None,
            "delta": delta,
            "meaningful_change": meaningful_change,
        }

    except Exception as e:
        logging.warning("reentry_guard: get_reentry_context failed for %s: %s", ticker, e)
        return None


def _format_reentry_block(ctx: dict) -> str:
    """Format reentry context dict into a multi-line string for AI prompts."""
    days = ctx["days_since_exit"]
    reason = ctx["exit_reason"]
    delta = ctx.get("delta")
    exit_scores = ctx.get("exit_scores")
    meaningful = ctx.get("meaningful_change", False)
    flag_threshold = 10  # display threshold (hardcoded — meaningful_change already reflects portfolio threshold)

    if exit_scores is None:
        return (
            f"\n  ↻ Reentry Context: Sold {days} days ago ({reason})."
            f" No entry scores available for delta comparison.\n"
        )

    # Build factor delta lines
    factor_parts = []
    if delta:
        for factor, change in delta.items():
            entry_val = exit_scores.get(factor, 0)
            current_val = entry_val + change
            flag = ""
            if abs(change) >= flag_threshold:
                flag = " ⚠" if change < 0 else " ✓"
            sign = "+" if change >= 0 else ""
            factor_parts.append(
                f"{factor}: {entry_val:.0f}→{current_val:.0f} ({sign}{change:.0f}{flag})"
            )

    delta_line = ", ".join(factor_parts) if factor_parts else "no delta"

    if meaningful:
        header = f"↻ Reentry Context: Sold {days} days ago ({reason})."
        footer = "Significant shifts detected. Re-entry may be valid if thesis is fresh."
    else:
        header = f"⚠ Reentry Warning: Sold {days} days ago ({reason})."
        footer = f"No factor changed ≥{flag_threshold}pts. Critically justify reentry or reject."

    return f"\n  {header}\n  Factor delta vs entry — {delta_line}\n  {footer}\n"
```

- [ ] **Step 4: Run tests to verify all 15 pass**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/test_reentry_guard.py -v
```

Expected: All 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add scripts/reentry_guard.py tests/test_reentry_guard.py && git commit -m "feat: add reentry_guard module with get_reentry_context and _format_reentry_block"
```

---

## Task 2: Add `reentry_context` field to `BuyProposal` and `ProposedAction`

**Files:**
- Modify: `scripts/enhanced_structures.py`

### Background

`BuyProposal` and `ProposedAction` are the dataclasses that flow through the mechanical path (non-AI-driven portfolios). Adding `reentry_context: Optional[dict] = None` to both allows `OpportunityLayer` to attach the context to each buy proposal, and `unified_analysis.py` to forward it into `ProposedAction` where `ai_review.py` will read it.

Both fields must have a default of `None` and come AFTER all non-default fields (Python dataclass rule). `BuyProposal.reentry_context` goes after `social_signal`. `ProposedAction.reentry_context` goes after `source_proposal`.

The existing test suite in `tests/test_enhanced_structures.py` (if it exists) should still pass.

---

- [ ] **Step 1: Check for existing tests**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && python3 -m pytest tests/ -k "enhanced_structures" -v 2>&1 | tail -10
```

Note the results. If tests exist they should all pass after the change.

- [ ] **Step 2: Add fields to `BuyProposal` and `ProposedAction`**

In `scripts/enhanced_structures.py`, after the `social_signal: Optional["SocialSignal"] = None` line in `BuyProposal`, add:

```python
    reentry_context: Optional[dict] = None
```

And after the `source_proposal: Optional[object] = None` line in `ProposedAction`, add:

```python
    reentry_context: Optional[dict] = None
```

- [ ] **Step 3: Verify no import errors**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "from enhanced_structures import BuyProposal, ProposedAction; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run the full test suite to confirm nothing broke**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add scripts/enhanced_structures.py && git commit -m "feat: add reentry_context field to BuyProposal and ProposedAction"
```

---

## Task 3: Make stop-loss cooldown configurable in `OpportunityLayer` and attach reentry context

**Files:**
- Modify: `scripts/opportunity_layer.py`

### Background

The existing Bug #7 fix block in `opportunity_layer.py` has a hardcoded `timedelta(days=7)` for stop-loss cooldown (around line 163). This needs to become `timedelta(days=stop_loss_cooldown_days)` read from `config["enhanced_trading"]["reentry_guard"]`.

After reading the config at the top of `process()`, the entire cooldown block should be guarded by `if reentry_guard_enabled:`. Then, after `_generate_buy_proposals()` returns, iterate each buy proposal and call `get_reentry_context()` to attach the result to `proposal.reentry_context`.

The helper `get_transactions_file()` already exists in `opportunity_layer.py` or can be imported from `portfolio_state.py` — check before adding a new reference.

**Important:** The call to `get_reentry_context()` is separate from the hard cooldown block. The cooldown is a hard filter (skip the ticker entirely for N days after STOP_LOSS). The reentry context is an annotation added to proposals that survived the filter, for any exit reason within `lookback_days`.

---

- [ ] **Step 1: Read the relevant section of `opportunity_layer.py`**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && sed -n '1,30p' scripts/opportunity_layer.py
```

Then check where `get_transactions_file` is defined or imported:

```bash
grep -n "get_transactions_file\|transactions_path\|transactions_file" scripts/opportunity_layer.py | head -20
```

Note how the transactions file path is obtained (needed for the reentry context call).

- [ ] **Step 2: Read the Bug #7 cooldown block to understand exact lines**

```bash
grep -n "stop_loss\|STOP_LOSS\|timedelta\|cooldown" scripts/opportunity_layer.py | head -20
```

- [ ] **Step 3: Read the config at top of `process()`**

In `scripts/opportunity_layer.py`, inside the `process()` method (right after the existing config reads at the top of the method body), add:

```python
rg_config = self.config.get("enhanced_trading", {}).get("reentry_guard", {})
reentry_guard_enabled = bool(rg_config.get("enabled", True))
stop_loss_cooldown_days = int(rg_config.get("stop_loss_cooldown_days", 7))
lookback_days = int(rg_config.get("lookback_days", 30))
meaningful_change_threshold_pts = float(rg_config.get("meaningful_change_threshold_pts", 10))
```

- [ ] **Step 4: Make cooldown configurable and guard the block**

Replace the hardcoded `timedelta(days=7)` with `timedelta(days=stop_loss_cooldown_days)`.

Wrap the entire cooldown block with `if reentry_guard_enabled:` (the block that filters out recently-stopped-out tickers).

- [ ] **Step 5: Attach reentry context after buy proposals are generated**

First, add the import at the **top of `opportunity_layer.py`** with the other imports (not inline):

```python
from reentry_guard import get_reentry_context
```

After the line where `buy_proposals` is assigned from `_generate_buy_proposals()`, add the following block. First check what the transactions path variable is called (from Step 1) — it's likely the same path used for the stop-loss cooldown CSV read, or use `Path(__file__).parent.parent / "data" / "portfolios" / state.portfolio_id / "transactions.csv"`:

```python
if reentry_guard_enabled:
    tx_file = <transactions_path_for_this_portfolio>
    for proposal in buy_proposals:
        try:
            current_scores = {
                k: v for k, v in proposal.conviction_score.factors.items()
                if k != "composite"
            }
            proposal.reentry_context = get_reentry_context(
                ticker=proposal.ticker,
                transactions_path=tx_file,
                current_scores=current_scores,
                lookback_days=lookback_days,
                meaningful_change_threshold_pts=meaningful_change_threshold_pts,
            )
        except Exception as e:
            logging.warning(
                "OpportunityLayer: reentry_guard failed for %s: %s", proposal.ticker, e
            )
```

Note: `ConvictionScore.factors` always contains all 6 factors + `"composite"`. Excluding `"composite"` here is required — the `get_reentry_context()` function also filters it, but filtering at the call site is clearer.

Also note: if `reentry_guard_enabled` is `False`, skip the entire attachment loop (the `if reentry_guard_enabled:` guard handles this). The cooldown block is also wrapped the same way.

- [ ] **Step 6: Verify import and syntax**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from opportunity_layer import OpportunityLayer
print('OK')
"
```

Expected: `OK`

- [ ] **Step 7: Run full test suite**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 8: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add scripts/opportunity_layer.py && git commit -m "feat: make stop-loss cooldown configurable and attach reentry context to buy proposals"
```

---

## Task 4: Propagate `reentry_context` through the mechanical path in `unified_analysis.py`

**Files:**
- Modify: `scripts/unified_analysis.py`

### Background

The mechanical path in `unified_analysis.py` converts each `BuyProposal` into a `ProposedAction`. This happens in a loop around lines 413–431. The `ProposedAction` constructor call needs one additional keyword argument: `reentry_context=buy_proposal.reentry_context`.

This is a surgical one-line change — no logic, just propagation.

---

- [ ] **Step 1: Find the exact `ProposedAction(` call in the mechanical path**

```bash
grep -n "ProposedAction(" scripts/unified_analysis.py
```

- [ ] **Step 2: Read the constructor call to see all current arguments**

```bash
sed -n '<line-10>p,<line+5>p' scripts/unified_analysis.py
```

(substitute the actual line number from Step 1 ± 10 lines)

- [ ] **Step 3: Add `reentry_context=buy_proposal.reentry_context` to the `ProposedAction(...)` constructor call**

It should go after `source_proposal=buy_proposal` (the last positional arg before closing paren).

- [ ] **Step 4: Verify syntax**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from unified_analysis import run_unified_analysis
print('OK')
"
```

Expected: `OK`

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add scripts/unified_analysis.py && git commit -m "feat: propagate reentry_context from BuyProposal to ProposedAction in mechanical path"
```

---

## Task 5: Inject reentry context into the AI-driven path in `unified_analysis.py`

**Files:**
- Modify: `scripts/unified_analysis.py`

### Background

AI-driven portfolios bypass `OpportunityLayer` entirely — their buy candidates come from `_run_ai_driven_analysis()` via a `scored_candidates` list built directly from `StockScore` objects. This path has no `BuyProposal` step, so Task 3's attachment in `OpportunityLayer` does nothing here.

The fix: call `get_reentry_context()` inside the `scored_results` loop that builds `scored_candidates` (around lines 127–148). The config is read once at the top of `_run_ai_driven_analysis()`.

`StockScore` is a dataclass — access attributes with dot notation, not dict keys:
- `s.ticker`, `s.composite_score`, `s.current_price`
- `s.price_momentum_score`, `s.earnings_growth_score`, `s.quality_score`
- `s.value_timing_score`, `s.volume_score`, `s.volatility_score`

The transactions file path — verify how it's obtained for a given `state.portfolio_id`. The pattern used elsewhere is something like `Path(__file__).parent.parent / "data" / "portfolios" / state.portfolio_id / "transactions.csv"`, but check the actual helper in use.

---

- [ ] **Step 1: Read `_run_ai_driven_analysis()` to understand the scored_candidates loop**

```bash
sed -n '100,160p' scripts/unified_analysis.py
```

Identify:
1. Where `scored_candidates` is populated
2. How the candidate dict is structured (which keys are set)
3. How the transactions file path is obtained elsewhere in the file

- [ ] **Step 2: Read the config and set up transactions path at the top of `_run_ai_driven_analysis()`**

Add the import at the **top of `unified_analysis.py`** with the other imports (not inline):

```python
from reentry_guard import get_reentry_context
```

Near the top of the `_run_ai_driven_analysis()` function body (after the initial state/config reads), add:

```python
rg_config = state.config.get("enhanced_trading", {}).get("reentry_guard", {})
rg_enabled = bool(rg_config.get("enabled", True))
rg_lookback = int(rg_config.get("lookback_days", 30))
rg_threshold = float(rg_config.get("meaningful_change_threshold_pts", 10))
# Use same path pattern as other scripts:
tx_file = Path(__file__).parent.parent / "data" / "portfolios" / state.portfolio_id / "transactions.csv"
# (If unified_analysis.py already has a get_transactions_file() helper or a path pattern, use that instead)
```

If `rg_enabled` is `False`, skip the `get_reentry_context()` call in the loop entirely (the `if rg_enabled:` guard handles this).

- [ ] **Step 3: Add `reentry_context` field to each candidate dict in the loop**

In the `scored_results` loop, after `current_scores` dict is built from `s.*_score` attributes, add `"reentry_context": None` to the candidate dict, then call `get_reentry_context()`:

```python
current_scores = {
    "price_momentum": s.price_momentum_score,
    "earnings_growth": s.earnings_growth_score,
    "quality": s.quality_score,
    "value_timing": s.value_timing_score,
    "volume": s.volume_score,
    "volatility": s.volatility_score,
}
candidate = {
    "ticker": s.ticker,
    "composite_score": s.composite_score,
    "current_price": s.current_price,
    "factor_scores": current_scores,
    "reentry_context": None,
    # ... other fields already in the dict
}
if rg_enabled:
    try:
        candidate["reentry_context"] = get_reentry_context(
            ticker=s.ticker,
            transactions_path=tx_file,
            current_scores=current_scores,
            lookback_days=rg_lookback,
            meaningful_change_threshold_pts=rg_threshold,
        )
    except Exception as e:
        logging.warning("reentry_guard: AI path failed for %s: %s", s.ticker, e)
```

Note: The existing candidate dict may already have most fields — this modifies the existing dict construction rather than replacing it wholesale.

- [ ] **Step 4: Verify syntax**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from unified_analysis import run_unified_analysis
print('OK')
"
```

Expected: `OK`

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add scripts/unified_analysis.py && git commit -m "feat: inject reentry context into AI-driven scored_candidates loop"
```

---

## Task 6: Inject reentry block into `ai_review.py` prompt

**Files:**
- Modify: `scripts/ai_review.py`

### Background

`ai_review.py` handles the mechanical (non-AI-driven) path. The `_build_review_prompt()` function constructs the prompt string for each proposed action. After the `Factor Scores: {json.dumps(factor_scores)}` line (around line 151), we inject the reentry block for BUY actions.

`_get_action_attr(action, "reentry_context", None)` is the existing helper that safely reads attributes from action objects (handles both dict and object access). The `action_type` variable should already be set in `_build_review_prompt()`.

Use `if action_type == "BUY" and reentry_ctx is not None:` — explicit None check, not truthiness check.

---

- [ ] **Step 1: Read the relevant section of `_build_review_prompt()`**

```bash
sed -n '82,175p' scripts/ai_review.py
```

Identify:
1. The exact line with `Factor Scores:` — this is where the injection goes (after it)
2. Whether `action_type` variable is set at that point in the function
3. The `_get_action_attr` helper signature

- [ ] **Step 2: Add the module-level import**

At the top of `scripts/ai_review.py`, near the other imports, add:

```python
from reentry_guard import _format_reentry_block
```

- [ ] **Step 3: Inject the reentry block in `_build_review_prompt()`**

After the `Factor Scores:` line (confirm exact position from Step 1), add:

```python
reentry_ctx = _get_action_attr(action, "reentry_context", None)
if action_type == "BUY" and reentry_ctx is not None:
    try:
        actions_text += _format_reentry_block(reentry_ctx)
    except Exception as e:
        logging.warning(
            "ai_review: failed to format reentry block for %s: %s", ticker, e
        )
```

- [ ] **Step 4: Verify import and syntax**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from ai_review import AIReviewer
print('OK')
"
```

Expected: `OK`

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add scripts/ai_review.py && git commit -m "feat: inject reentry context block into ai_review prompt for BUY actions"
```

---

## Task 7: Inject reentry block into `ai_allocator.py` prompt

**Files:**
- Modify: `scripts/ai_allocator.py`

### Background

`ai_allocator.py` handles all AI-driven portfolios. The `_build_allocation_prompt()` function has a candidate rendering loop with two branches: `full_watchlist` mode (simple one-line per candidate) and standard mode (multi-line with factor scores). The reentry block must be injected in **both branches** after the factor scores line.

Candidates are dicts. `c.get("reentry_context")` returns the context dict or `None`. Use `if rc is not None:` — explicit None check.

`cand_lines.append(...)` is the pattern used to build the per-candidate text block. Use `.rstrip()` on `_format_reentry_block(rc)` to avoid double newlines.

---

- [ ] **Step 1: Read the candidate rendering section of `_build_allocation_prompt()`**

```bash
sed -n '210,285p' scripts/ai_allocator.py
```

Identify:
1. The `full_watchlist` branch (line ~218): what each candidate line looks like
2. The standard branch (line ~256): the `cand_lines` list pattern
3. Whether there's a shared helper or two distinct code paths

- [ ] **Step 2: Add the module-level import**

At the top of `scripts/ai_allocator.py`, near the other imports, add:

```python
from reentry_guard import _format_reentry_block
```

- [ ] **Step 3: Inject reentry block in the standard branch**

In the standard branch (where `cand_lines` is built), after the factor scores are appended, add:

```python
rc = c.get("reentry_context")
if rc is not None:
    try:
        cand_lines.append(_format_reentry_block(rc).rstrip())
    except Exception as e:
        logging.warning(
            "ai_allocator: failed to format reentry block for %s: %s",
            c.get("ticker"), e
        )
```

- [ ] **Step 4: Inject reentry block in the full_watchlist branch (if it has its own rendering)**

From the code read in Step 1, determine whether `full_watchlist` mode has its own separate candidate rendering loop:
- If YES (separate loop): add an identical `rc = c.get("reentry_context"); if rc is not None: ...` block after the factor scores line in that branch too.
- If NO (shares the same `cand_lines` loop): Step 3 already covers it.

The spec requires both branches to inject the reentry block — do not skip this check.

- [ ] **Step 5: Verify import and syntax**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from ai_allocator import AIAllocator
print('OK')
"
```

Expected: `OK`

- [ ] **Step 6: Run full test suite**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add scripts/ai_allocator.py && git commit -m "feat: inject reentry context block into ai_allocator candidate prompt"
```

---

## Task 8: Extend `strategy_generator.py` to infer `reentry_guard` config from DNA

**Files:**
- Modify: `scripts/strategy_generator.py`

### Background

`suggest_config_for_dna()` sends a DNA string to Claude and parses the returned JSON config. Extending it to include `reentry_guard` settings means new portfolios automatically get per-strategy reentry config without manual editing.

Two changes needed:
1. **Extend `SUGGEST_CONFIG_PROMPT`**: add `reentry_guard` to the JSON schema section and add guidelines for how to choose values based on rotation speed and universe breadth.
2. **Extend `suggest_config_for_dna()` return parsing**: extract `reentry_guard` from the parsed response and add it to `result`.

The current `SUGGEST_CONFIG_PROMPT` is at line 28 and `suggest_config_for_dna()` response parsing block is at lines 89–98. Read these before editing.

---

- [ ] **Step 1: Read the current prompt and parsing block**

```bash
sed -n '28,100p' scripts/strategy_generator.py
```

Identify:
1. The JSON schema section in `SUGGEST_CONFIG_PROMPT` (where to add `reentry_guard`)
2. The guidelines section (where to add the reentry_guard rules)
3. The exact response parsing block (what `data.get(...)` calls exist)

- [ ] **Step 2: Add `reentry_guard` to the JSON schema in `SUGGEST_CONFIG_PROMPT`**

In the schema section of the prompt (where the expected JSON keys are listed), add:

```
  "reentry_guard": {
    "stop_loss_cooldown_days": <integer 1–14>,
    "lookback_days": <integer 5–90>,
    "meaningful_change_threshold_pts": <integer 5–20>
  }
```

- [ ] **Step 3: Add guidelines for `reentry_guard` selection**

In the guidelines section of the prompt, add:

```
- reentry_guard: Set based on rotation speed and universe breadth.
  - Fast rotation (hold < 3 days, large universe): cooldown 1, lookback 5–7, threshold 5
  - Standard momentum (7–14 day holds): cooldown 7, lookback 30, threshold 10
  - High conviction, long holds (1–3 positions, >30 day targets): cooldown 14, lookback 60, threshold 15
  - Narrow curated universe (<20 tickers): keep cooldown low (1–3) to avoid starving the universe
```

- [ ] **Step 4: Extend response parsing in `suggest_config_for_dna()`**

After the existing `result[...]` assignments, add:

```python
rg = data.get("reentry_guard", {})
result["reentry_guard"] = {
    "enabled": True,
    "stop_loss_cooldown_days": int(rg.get("stop_loss_cooldown_days", 7)),
    "lookback_days": int(rg.get("lookback_days", 30)),
    "meaningful_change_threshold_pts": float(rg.get("meaningful_change_threshold_pts", 10)),
}
```

- [ ] **Step 5: Verify syntax**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from strategy_generator import suggest_config_for_dna
print('OK')
"
```

Expected: `OK`

- [ ] **Step 6: Run full test suite**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add scripts/strategy_generator.py && git commit -m "feat: extend suggest_config_for_dna to infer reentry_guard settings from portfolio DNA"
```

---

## Task 9: Apply `reentry_guard` from AI config in `portfolio_registry.py`

**Files:**
- Modify: `scripts/portfolio_registry.py`

### Background

`create_portfolio()` in `portfolio_registry.py` has a Layer 4 AI-config overrides block (around lines 486–523) where `ai_config` values (from `suggest_config_for_dna()`) are applied to the portfolio config. After the existing override applications, add the `reentry_guard` block.

This ensures newly created AI-driven portfolios automatically have their DNA-derived reentry guard settings written to `config.json`.

---

- [ ] **Step 1: Read the Layer 4 overrides block**

```bash
sed -n '480,530p' scripts/portfolio_registry.py
```

Identify:
1. Where existing `ai_config` values are applied (look for `if "some_key" in ai_config:` patterns)
2. The exact structure of the config dict at that point
3. Where to insert the `reentry_guard` block

- [ ] **Step 2: Add `reentry_guard` application**

After the existing AI config override applications, add:

```python
if "reentry_guard" in ai_config:
    if "enhanced_trading" not in config:
        config["enhanced_trading"] = {}
    config["enhanced_trading"]["reentry_guard"] = {
        "enabled": True,
        "stop_loss_cooldown_days": int(
            ai_config["reentry_guard"].get("stop_loss_cooldown_days", 7)
        ),
        "lookback_days": int(
            ai_config["reentry_guard"].get("lookback_days", 30)
        ),
        "meaningful_change_threshold_pts": float(
            ai_config["reentry_guard"].get("meaningful_change_threshold_pts", 10)
        ),
    }
```

- [ ] **Step 3: Verify syntax**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from portfolio_registry import PortfolioRegistry
print('OK')
"
```

Expected: `OK`

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add scripts/portfolio_registry.py && git commit -m "feat: apply reentry_guard from AI config in create_portfolio"
```

---

## Task 10: End-to-end smoke test and API restart

**Files:**
- No file changes

### Background

All code changes are complete. Verify the full pipeline doesn't crash with a real portfolio. Use `--dry-run` (analyze only, no trade execution). Check that reentry context logging appears in output (either as warnings for portfolios with no recent sells, or as info about context being found).

---

- [ ] **Step 1: Run the full test suite one final time**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass. Note the count.

- [ ] **Step 2: Restart the API**

```bash
pkill -f "uvicorn api.main" 2>/dev/null; sleep 1
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && DISABLE_SOCIAL=true nohup uvicorn api.main:app --host 0.0.0.0 --port 8001 > /tmp/mcr_api.log 2>&1 &
sleep 3 && curl -s http://localhost:8001/api/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: Trigger a dry-run analysis for a portfolio with trade history**

```bash
curl -s -X POST http://localhost:8001/api/microcap/analyze | python3 -m json.tool 2>&1 | head -60
```

Expected: Returns JSON analysis without errors. (Reentry context won't show in the JSON response directly — it's injected into the AI prompt — but no 500 errors is the key verification.)

- [ ] **Step 4: Check API log for any reentry-guard errors**

```bash
grep -i "reentry" /tmp/mcr_api.log | tail -20
```

Expected: Either no lines (no recent sells in the lookback window) or context-found lines. No `ERROR` or uncaught exception traces.

- [ ] **Step 5: Commit final state to GitHub**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git push origin main
```

---

## Summary

9 files changed across 10 tasks. All production code changes guarded with `try/except Exception as e:`. Existing portfolios silently use defaults. New portfolios get DNA-derived reentry config. Both mechanical and AI-driven paths covered.

**Remaining (future session):** Manually edit each existing portfolio's `config.json` to add an appropriate `reentry_guard` block based on their DNA:

| Portfolio | cooldown_days | lookback_days | threshold_pts |
|---|---|---|---|
| catalyst-momentum-scalper | 1 | 5 | 5 |
| max | 1 | 7 | 5 |
| defense-tech | 3 | 14 | 8 |
| asymmetric-microcap-compounder | 14 | 60 | 15 |
| microcap, boomers, adjacent, others | 7 | 30 | 10 |
