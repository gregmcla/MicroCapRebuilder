# AI Allocation Prompt Context Enrichment — Design Spec

**Goal:** Give Claude richer portfolio-specific context in the allocation prompt so it can make better-informed decisions on stock selection, position sizing, and risk management.

**Scope:** 5 new context items added to `_build_allocation_prompt` via a single `prompt_extras` dict param. Two files change: `unified_analysis.py` (data sourcing) and `ai_allocator.py` (prompt rendering).

---

## What's Being Added

### 1. Portfolio Recent Performance
Win rate, avg win/loss, total return vs benchmark, alpha, current drawdown. Lets Claude know if the strategy is working and whether to be more aggressive or defensive.

**Source:** `TradeAnalyzer(portfolio_id).calculate_trade_stats()` (already called in `run_unified_analysis` — just store the full result) + `PortfolioAnalytics(portfolio_id=portfolio_id).calculate_all_metrics()` (fetches cached yfinance benchmark data, ~1-2s).

**Rendered as:**
```
PORTFOLIO PERFORMANCE:
  Total return: +12.3% vs benchmark +8.1% (alpha +4.2%)
  Current drawdown: -2.1% from peak
  Win rate: 64% over 22 trades | avg win +8.4% / avg loss -4.1%
  Reward/risk ratio: 2.05
```
Omitted entirely if fewer than 5 completed trades or analytics returns None.

### 2. Deterioration Alerts
Full warning messages from `early_warning.py` (score drops, drawdown, win rate decline, positions near stop). Currently only the severity label ("CAUTION") reaches Claude — the actual reasons do not.

**Source:** `get_warnings(portfolio_id)` — called once in `run_unified_analysis`. Severity is derived from this list (replacing the redundant separate `get_warning_severity()` call). The full `List[Warning]` is passed in `prompt_extras["warnings"]`.

**Rendered as (only when warnings exist):**
```
ACTIVE ALERTS (1 HIGH):
  [HIGH] Low Win Rate: 38% over last 10 trades — below 45% threshold
  [MEDIUM] Position near stop: ETR within 3% of stop loss ($32.96)
```
Omitted entirely when no warnings are active.

### 3. Position Age
Days held for each open position. Claude currently sees P&L but not time context — a -3% position held 2 days is very different from one held 6 weeks.

**Source:** `entry_date` column already in `state.positions`. Compute `(date.today() - entry_date).days` per position. Zero extra cost.

**Rendered as** an addition to the existing positions line:
```
AROC: 84 shares @ $36.84, P&L +2.8%, weight 6.2%, stop $32.96, target $42.99 (20 days held)
```

### 4. Cash Idle Time
How long cash has been sitting uninvested. Prevents Claude from being overly conservative with cash that's been idle for weeks.

**Source:** Last BUY transaction date from `state.transactions` (already loaded on `PortfolioState`). `days_since_last_buy = (date.today() - last_buy_date).days`. If no buys yet, `None`.

**Rendered as** an addition to the existing cash line in PORTFOLIO STATE:
```
Current Cash: $76,258 (idle 8 days — last buy 2026-03-17)
```
If no buys yet: `Current Cash: $76,258 (no buys yet — fresh portfolio)`

### 5. Factor Intelligence
Which scoring factors have actually been predictive for this portfolio based on real trade outcomes. Lets Claude bias toward stocks scoring well on proven factors.

**Source:** `FactorLearner(portfolio_id=portfolio_id).get_factor_summary()` — CSV read, fast. Returns factors sorted by `total_contribution`.

**Rendered as (only when ≥10 completed trades):**
```
FACTOR INTELLIGENCE (22 completed trades):
  Strongest predictors for this portfolio:
    value_timing   — 71% win rate, trend: improving
    price_momentum — 65% win rate, trend: stable
    quality        — 58% win rate, trend: stable
  Weakest: volume (44% win rate, trend: declining)
  Note: Weight your decisions toward stocks scoring well on the top factors above.
```
Omitted entirely when `get_factor_summary()` returns `status: insufficient_data`.

---

## Data Flow

```
run_unified_analysis()
  │
  ├── get_warnings(portfolio_id)          → warnings list
  │     └── derive warning_severity from list (replaces separate get_warning_severity() call)
  │
  ├── TradeAnalyzer(portfolio_id)
  │     └── .calculate_trade_stats()     → trade_stats (already called, store result)
  │
  ├── PortfolioAnalytics(portfolio_id)
  │     └── .calculate_all_metrics()     → portfolio_metrics
  │
  ├── state.transactions                  → days_since_last_buy
  │
  └── FactorLearner(portfolio_id)
        └── .get_factor_summary()        → factor_summary
  │
  └── bundle into prompt_extras dict
        └── pass to _run_ai_driven_analysis() → run_ai_allocation() → _build_allocation_prompt()
```

---

## `prompt_extras` Dict Schema

```python
prompt_extras = {
    "trade_stats": TradeStats | None,
    "portfolio_metrics": RiskMetrics | None,
    "warnings": list[Warning],           # empty list if none
    "days_since_last_buy": int | None,   # None = no buys yet
    "factor_summary": dict | None,       # None = insufficient_data status
}
```

---

## Files Changed

| File | Change |
|---|---|
| `scripts/unified_analysis.py` | Call `get_warnings()` once; derive severity from it; call `PortfolioAnalytics` and `FactorLearner`; compute `days_since_last_buy`; bundle `prompt_extras`; pass to `run_ai_allocation` |
| `scripts/ai_allocator.py` | Add `prompt_extras: Optional[dict] = None` to `run_ai_allocation` and `_build_allocation_prompt`; build 3 new blocks (PORTFOLIO PERFORMANCE, ACTIVE ALERTS, FACTOR INTELLIGENCE); enrich positions lines with days-held; enrich cash line with idle time |

---

## Error Handling

All data fetches are wrapped in `try/except Exception as e:` with a print. If any source fails, the corresponding `prompt_extras` key is `None` or `[]` and the block is silently omitted from the prompt. Claude never sees a broken/partial block — it either gets the full block or nothing.

---

## What Is NOT Changed

- `_validate_allocation()` — no changes to constraint enforcement
- `_convert_to_reviewed_actions()` — no changes
- `run_ai_allocation()` return type — unchanged
- Warning severity → position size reduction logic in `run_unified_analysis` — unchanged (still uses derived severity)
- Any other callers of `_build_allocation_prompt` — there are none (private function)

---

## Key Gotchas

- `TradeAnalyzer` and `FactorLearner` must be initialized with `portfolio_id` to read the correct portfolio's transactions/post_mortems. Without it they fall back to a global file path.
- `PortfolioAnalytics(portfolio_id=portfolio_id).calculate_all_metrics()` fetches yfinance benchmark data — it is cached (4hr TTL) but on a cold cache will add ~2-3s to the analyze call.
- `state.transactions` may be empty for a new portfolio — handle `days_since_last_buy = None` gracefully.
- `get_warnings()` currently called via `get_warning_severity()` (which calls it internally). After this change, call `get_warnings()` directly and compute severity inline to avoid the double call.
- Factor summary sorted by `total_contribution` (not win rate) — show top 3 and worst 1.
