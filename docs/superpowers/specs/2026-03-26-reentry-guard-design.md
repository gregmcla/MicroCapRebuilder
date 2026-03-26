# Reentry Guard — Design Spec

**Date:** 2026-03-26
**Status:** Approved for implementation
**Scope:** `scripts/reentry_guard.py` (new), plus targeted changes to `opportunity_layer.py`, `unified_analysis.py`, `ai_review.py`, `ai_allocator.py`, `strategy_generator.py`, `portfolio_registry.py`, `enhanced_structures.py`

---

## Problem

The system has no memory of its own trade history when proposing buys. A ticker that was stopped out 2 days ago can immediately be re-proposed as a buy because `OpportunityLayer` only filters currently-held tickers. The existing 7-day hard stop-loss block in `opportunity_layer.py` is hardcoded and only covers `STOP_LOSS` exits — `TAKE_PROFIT`, `SIGNAL`, and `MANUAL` exits have no protection at all.

---

## Solution

Two complementary mechanisms:

1. **Hard cooldown** (already exists, make configurable): block re-proposals for N days after a `STOP_LOSS` exit. The hardcoded `7` in `opportunity_layer.py` becomes `stop_loss_cooldown_days` read from config.

2. **Context injection** (new): for any recent exit (all reasons, within lookback window), compute a factor score delta and inject it into the AI review prompt so Claude can make an informed reentry decision.

---

## Key Design Decisions

- **Score delta compares BUY entry scores vs current scores.** SELL transactions do not record factor scores; BUY transactions do (in the `factor_scores` JSON column). The question being answered is: "Has the thesis changed since we last decided to own this?" — which is the right question.
- **Most recent BUY transaction** for the ticker provides the entry score baseline.
- **Most recent SELL transaction** provides the exit date, reason, and days-since-exit.
- If no BUY with factor scores exists (migration data, old transactions), inject exit context without a delta.
- **Two separate injection points** — the mechanical path uses `OpportunityLayer` → `ProposedAction`; the AI-driven path builds `scored_candidates` directly in `_run_ai_driven_analysis()` and bypasses `OpportunityLayer` entirely. Both paths must call `get_reentry_context()` independently.
- **Both `ai_review.py` and `ai_allocator.py` get the injection.** AI-driven portfolios use `ai_allocator.py`; non-AI-driven use `ai_review.py`.
- **Existing 7-day hardcoded cooldown** in `opportunity_layer.py` is refactored to read `stop_loss_cooldown_days` from config, preserving its hard-block behavior.
- **`reentry_guard.py` has zero imports from other trading modules** — only `pathlib`, `typing`, `pandas`, `logging`, `datetime`, `json`. This avoids any circular import risk.
- **`_format_reentry_block()` lives in `reentry_guard.py`** and is imported by both `ai_review.py` and `ai_allocator.py`.
- **`None` check is explicit**: callers use `if reentry_ctx is not None:`, not `if reentry_ctx:`, since a future empty dict would be falsy incorrectly.
- **Existing portfolios use defaults silently** — no migration needed. When `reentry_guard` key is absent from `config.json`, all four defaults apply automatically. This is intentional; per-portfolio tuning is a separate future session.
- **SELL action prompts are not modified** — reentry context injection is BUY-only. SELL transactions do not record factor scores, and there is nothing useful to inject for sell proposals.

---

## Config Schema

Added under `enhanced_trading.reentry_guard` in each portfolio's `config.json`. This is a new subsection alongside the existing `layer1`, `layer2`, `layer3`, `layer4`, `rotation` subsections:

```json
"enhanced_trading": {
  "reentry_guard": {
    "enabled": true,
    "stop_loss_cooldown_days": 7,
    "lookback_days": 30,
    "meaningful_change_threshold_pts": 10
  }
}
```

### Defaults when key is absent

| Key | Default |
|---|---|
| `enabled` | `true` |
| `stop_loss_cooldown_days` | `7` |
| `lookback_days` | `30` |
| `meaningful_change_threshold_pts` | `10` |

Existing portfolio `config.json` files are unchanged. When `reentry_guard` is absent, defaults are read at runtime. No migration, no backfill. Per-portfolio tuning will be done in a separate session guided by each portfolio's DNA.

### Suggested values by strategy type

| Portfolio | cooldown_days | lookback_days | threshold_pts | Reason |
|---|---|---|---|---|
| catalyst-momentum-scalper | 1 | 5 | 5 | 48hr max hold, full rotation every 1-2 days |
| max | 1 | 7 | 5 | "max money in 2 trading days" aggressive rotation |
| defense-tech | 3 | 14 | 8 | 14 curated names, narrow universe would starve |
| asymmetric-microcap-compounder | 14 | 60 | 15 | Max 2 positions, 150% take-profit, high conviction |
| microcap, boomers, adjacent, others | 7 | 30 | 10 | Standard momentum, default values |

New portfolios created via `suggest_config_for_dna()` will receive AI-derived values for all four keys.

---

## Files

### New

| File | Purpose |
|---|---|
| `scripts/reentry_guard.py` | `get_reentry_context()` + `_format_reentry_block()` |
| `tests/test_reentry_guard.py` | Unit tests |

### Modified

| File | Change |
|---|---|
| `scripts/opportunity_layer.py` | Read `stop_loss_cooldown_days` from config (replaces hardcoded `7`); call `get_reentry_context()` for each buy proposal; attach result to `BuyProposal.reentry_context` |
| `scripts/enhanced_structures.py` | Add `reentry_context: Optional[dict] = None` to `BuyProposal` (after `social_signal`) and `ProposedAction` (after `source_proposal`) |
| `scripts/unified_analysis.py` | (1) Mechanical path: copy `reentry_context` from `BuyProposal` to `ProposedAction`. (2) AI-driven path: call `get_reentry_context()` in the `scored_candidates` build loop in `_run_ai_driven_analysis()` |
| `scripts/ai_review.py` | In `_build_review_prompt()`, inject `_format_reentry_block()` after `Factor Scores:` line for BUY actions |
| `scripts/ai_allocator.py` | Same injection in `_build_allocation_prompt()` candidate rendering loop |
| `scripts/strategy_generator.py` | Extend `SUGGEST_CONFIG_PROMPT` and `suggest_config_for_dna()` to include `reentry_guard` |
| `scripts/portfolio_registry.py` | Apply `reentry_guard` from `ai_config` in `create_portfolio()` |

---

## `reentry_guard.py` — Full Specification

This file lives in `scripts/` alongside all other modules. **No imports from other trading modules** — only stdlib and pandas.

### `get_reentry_context()`

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
    ...
```

**Logic:**

1. If `transactions_path` does not exist, return `None`.
2. Wrap everything in `try/except Exception as e:` — on any error, `logging.warning(...)` and return `None`.
3. Load CSV with `pd.read_csv(transactions_path, dtype=str)`.
4. If the `ticker` column is missing, return `None`.
5. Normalize: `df["ticker"] = df["ticker"].str.strip().str.upper()`.
6. Filter rows where `ticker` matches (case-insensitive after normalization).
7. Filter SELL rows (`action == "SELL"`) with parsed date `>= today - timedelta(days=lookback_days)`. If none, return `None`.
8. Take the most recent SELL by date — this is the exit event.
9. Search all BUY rows for the same ticker (no date restriction). Take the most recent BUY.
10. Parse `factor_scores` JSON from the BUY row:
    - Skip if column missing, value is NaN, empty string, `"null"`, or `"None"`
    - Wrap `json.loads()` in `try/except Exception as e:` — on failure, `exit_scores = None`
11. Compute `delta` only if both `exit_scores is not None` and `current_scores is not None`:
    - `delta = {f: current_scores[f] - exit_scores[f] for f in exit_scores if f in current_scores}`
    - Exclude the `"composite"` key from delta (not a raw factor score)
12. `meaningful_change = any(abs(v) >= meaningful_change_threshold_pts for v in delta.values())` if delta else `False`.

**Return value:**

```python
{
    "exit_date": "2026-03-20",        # ISO date string
    "exit_reason": "STOP_LOSS",       # STOP_LOSS | TAKE_PROFIT | SIGNAL | MANUAL
    "days_since_exit": 6,             # int
    "exit_scores": {...} | None,      # factor scores from most recent BUY, or None
    "current_scores": {...} | None,   # current_scores arg, or None if exit_scores is None
    "delta": {...} | None,            # per-factor delta, or None if no entry scores
    "meaningful_change": bool,        # True if any abs(delta) >= threshold_pts
}
```

### `_format_reentry_block()`

Shared formatter. Returns a multi-line string ready to append to prompt text.

```python
def _format_reentry_block(ctx: dict) -> str:
    ...
```

**No meaningful change:**
```
  ⚠ Reentry Warning: Sold 6 days ago (STOP_LOSS).
  Factor delta vs entry — price_momentum: 45→52 (+7), quality: 70→71 (+1)
  No factor changed ≥10pts. Critically justify reentry or reject.
```

**Meaningful change:**
```
  ↻ Reentry Context: Sold 14 days ago (TAKE_PROFIT).
  Factor delta vs entry — price_momentum: 81→65 (-16 ⚠), value_timing: 55→72 (+17 ✓)
  Significant shifts detected. Re-entry may be valid if thesis is fresh.
```

**No entry scores:**
```
  ↻ Reentry Context: Sold 8 days ago (SIGNAL). No entry scores available for delta comparison.
```

Flag rules: `⚠` on a factor if `change < 0 and abs(change) >= threshold`; `✓` if `change > 0 and abs(change) >= threshold`. The threshold used for flagging is 10pts (hardcoded in the formatter for display — the `meaningful_change` boolean already reflects the portfolio-specific threshold).

---

## `enhanced_structures.py` Changes

```python
@dataclass
class BuyProposal:
    ticker: str
    shares: int
    price: float
    total_value: float
    conviction_score: ConvictionScore
    position_size_pct: float
    rationale: str
    social_signal: Optional["SocialSignal"] = None
    reentry_context: Optional[dict] = None   # ← add here

@dataclass
class ProposedAction:
    action_type: str
    ticker: str
    shares: int
    price: float
    stop_loss: float
    take_profit: float
    quant_score: float
    factor_scores: dict
    regime: str
    reason: str
    source_proposal: Optional[object] = None
    reentry_context: Optional[dict] = None   # ← add here
```

---

## `opportunity_layer.py` Changes (mechanical path)

### 1. Read reentry config at top of `process()`

```python
rg_config = self.config.get("enhanced_trading", {}).get("reentry_guard", {})
reentry_guard_enabled = bool(rg_config.get("enabled", True))
stop_loss_cooldown_days = int(rg_config.get("stop_loss_cooldown_days", 7))
lookback_days = int(rg_config.get("lookback_days", 30))
meaningful_change_threshold_pts = float(rg_config.get("meaningful_change_threshold_pts", 10))
```

### 2. Replace hardcoded `7` in Bug #7 fix block

```python
cutoff = date.today() - timedelta(days=stop_loss_cooldown_days)
```

Guard the entire cooldown block with `if reentry_guard_enabled:`.

### 3. Attach reentry context to each buy proposal

After `_generate_buy_proposals()` returns:

```python
from reentry_guard import get_reentry_context

if reentry_guard_enabled:
    tx_file = get_transactions_file(state.portfolio_id)
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
            logging.warning("OpportunityLayer: reentry_guard failed for %s: %s", proposal.ticker, e)
```

Note: `ConvictionScore.factors` is always populated with all 6 factors + `"composite"` by `calculate_conviction()`. Exclude `"composite"` when passing to `get_reentry_context()`.

---

## `unified_analysis.py` Changes

### Mechanical path — copy field when converting BuyProposal → ProposedAction

In the loop at lines ~413–431 where `ProposedAction` is built from `buy_proposal`:

```python
proposed_action = ProposedAction(
    action_type="BUY",
    ticker=buy_proposal.ticker,
    ...
    source_proposal=buy_proposal,
    reentry_context=buy_proposal.reentry_context,   # ← add
)
```

### AI-driven path — inject in `_run_ai_driven_analysis()` scored_candidates loop

In the loop at lines ~127–148 that builds `scored_candidates` from `StockScore` objects, after the existing candidate dict is assembled, call `get_reentry_context()` directly:

```python
from reentry_guard import get_reentry_context

# At top of _run_ai_driven_analysis(), read config once:
rg_config = state.config.get("enhanced_trading", {}).get("reentry_guard", {})
rg_enabled = bool(rg_config.get("enabled", True))
rg_lookback = int(rg_config.get("lookback_days", 30))
rg_threshold = float(rg_config.get("meaningful_change_threshold_pts", 10))
tx_file = get_transactions_file(state.portfolio_id)

# Inside the scored_results loop:
for s in scored_results:
    if s:
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
        scored_candidates.append(candidate)
```

---

## `ai_review.py` Changes

Import at module level (safe — `reentry_guard.py` has no trading module imports):

```python
from reentry_guard import _format_reentry_block
```

In `_build_review_prompt()`, after the `Factor Scores: {json.dumps(factor_scores)}` line for BUY actions:

```python
reentry_ctx = _get_action_attr(action, "reentry_context", None)
if action_type == "BUY" and reentry_ctx is not None:
    try:
        actions_text += _format_reentry_block(reentry_ctx)
    except Exception as e:
        logging.warning("ai_review: failed to format reentry block for %s: %s", ticker, e)
```

---

## `ai_allocator.py` Changes

Import at module level:

```python
from reentry_guard import _format_reentry_block
```

In `_build_allocation_prompt()`, in the candidate rendering loop (both full-watchlist and detailed modes), after the factor scores line:

```python
rc = c.get("reentry_context")
if rc is not None:
    try:
        cand_lines.append(_format_reentry_block(rc).rstrip())
    except Exception as e:
        logging.warning("ai_allocator: failed to format reentry block for %s: %s", c.get("ticker"), e)
```

---

## `strategy_generator.py` Changes

### Extend JSON schema in `SUGGEST_CONFIG_PROMPT`

```
  "reentry_guard": {
    "stop_loss_cooldown_days": <integer 1–14>,
    "lookback_days": <integer 5–90>,
    "meaningful_change_threshold_pts": <integer 5–20>
  }
```

### Add to Guidelines section

```
- reentry_guard: Set based on rotation speed and universe breadth.
  - Fast rotation (hold < 3 days, large universe): cooldown 1, lookback 5–7, threshold 5
  - Standard momentum (7–14 day holds): cooldown 7, lookback 30, threshold 10
  - High conviction, long holds (1–3 positions, > 30 day targets): cooldown 14, lookback 60, threshold 15
  - Narrow curated universe (< 20 tickers): keep cooldown low (1–3) to avoid starving the universe
```

### Extend response parsing in `suggest_config_for_dna()`

```python
rg = data.get("reentry_guard", {})
result["reentry_guard"] = {
    "enabled": True,
    "stop_loss_cooldown_days": int(rg.get("stop_loss_cooldown_days", 7)),
    "lookback_days": int(rg.get("lookback_days", 30)),
    "meaningful_change_threshold_pts": float(rg.get("meaningful_change_threshold_pts", 10)),
}
```

---

## `portfolio_registry.py` Changes

In `create_portfolio()`, in the AI config overrides block:

```python
if "reentry_guard" in ai_config:
    if "enhanced_trading" not in config:
        config["enhanced_trading"] = {}
    config["enhanced_trading"]["reentry_guard"] = {
        "enabled": True,
        "stop_loss_cooldown_days": int(ai_config["reentry_guard"].get("stop_loss_cooldown_days", 7)),
        "lookback_days": int(ai_config["reentry_guard"].get("lookback_days", 30)),
        "meaningful_change_threshold_pts": float(
            ai_config["reentry_guard"].get("meaningful_change_threshold_pts", 10)
        ),
    }
```

---

## `tests/test_reentry_guard.py` — Test Matrix

| Test | Scenario | Expected |
|---|---|---|
| `test_returns_none_no_recent_sell` | No SELL in transactions | `None` |
| `test_returns_none_sell_outside_window` | SELL older than `lookback_days` | `None` |
| `test_returns_context_with_delta` | SELL + BUY both found with `factor_scores` | dict with `delta` not None |
| `test_returns_context_without_delta_no_buy_scores` | SELL found, BUY has no `factor_scores` | dict with `delta=None` |
| `test_meaningful_change_true` | One factor delta >= threshold | `meaningful_change=True` |
| `test_meaningful_change_false` | All factor deltas < threshold | `meaningful_change=False` |
| `test_uses_most_recent_sell` | Two SELLs in window — uses newer | `exit_date` matches newer SELL |
| `test_uses_most_recent_buy_for_entry_scores` | Two BUYs — uses newer for entry scores | delta reflects newer BUY scores |
| `test_sell_exactly_on_boundary` | SELL date == today - lookback_days | included (>= boundary) |
| `test_sell_one_day_outside_boundary` | SELL date == today - lookback_days - 1 | `None` |
| `test_handles_missing_transactions_file` | Path does not exist | `None` (no exception raised) |
| `test_handles_missing_ticker_column` | CSV has no `ticker` column | `None` (no exception raised) |
| `test_handles_malformed_factor_scores_json` | `factor_scores` contains invalid JSON | context with `exit_scores=None` |
| `test_handles_empty_factor_scores` | `factor_scores` is empty string | context with `exit_scores=None` |
| `test_excludes_composite_from_delta` | BUY `factor_scores` includes `"composite"` key | delta dict does not contain `"composite"` |

---

## Data Flow Summary

```
MECHANICAL PATH (non-AI-driven portfolios)
──────────────────────────────────────────
OpportunityLayer.process()
  ├── hard stop-loss cooldown (configurable via stop_loss_cooldown_days)
  ├── score_watchlist() → stock_scores
  ├── calculate_conviction() → conviction_scores  [factors dict always populated]
  ├── _generate_buy_proposals() → buy_proposals
  └── for each proposal:
        get_reentry_context(...) → attach to proposal.reentry_context

unified_analysis.py (mechanical path)
  └── BuyProposal → ProposedAction
        reentry_context=buy_proposal.reentry_context

ai_review.py
  └── _build_review_prompt()
        BUY action + reentry_context is not None:
          append _format_reentry_block(ctx)


AI-DRIVEN PATH (all current active portfolios)
──────────────────────────────────────────────
unified_analysis._run_ai_driven_analysis()
  ├── StockScorer.score_watchlist() → scored_results
  └── for each scored result:
        build candidate dict
        get_reentry_context(...) → candidate["reentry_context"]
        → scored_candidates

ai_allocator._build_allocation_prompt()
  └── for each candidate:
        candidate["reentry_context"] is not None:
          append _format_reentry_block(ctx)
```

---

## Error Handling

- `get_reentry_context()`: entire function body wrapped in `try/except Exception as e:` with `logging.warning()` — returns `None` on any failure, never raises
- `_format_reentry_block()` call sites: each wrapped in `try/except Exception as e:` with `logging.warning()` — a bad context dict never corrupts prompt generation
- All `except` clauses bind: `except Exception as e:` (per CLAUDE.md — never bare `except:`)

---

## What This Does NOT Change

- Scoring, conviction calculation, or position sizing
- Dashboard or API endpoints
- Existing portfolio `config.json` files (no migration — defaults apply silently)
- The hard stop-loss block logic — only its day count is made configurable
- SELL action prompts — injection is BUY-only (SELL transactions have no factor scores)
- `post_mortems.py`, `factor_learning.py`, `risk_layer.py` — untouched
