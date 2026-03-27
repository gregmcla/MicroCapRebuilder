# GScott Pipeline Improvements — Ranked Implementation Plan
**Branch:** `trading-pipeline-refactor-experiment`
**Date:** 2026-03-27
**Source:** `pipeline-audit.md` iteration 1 findings

---

## Implementation Strategy

All changes on `trading-pipeline-refactor-experiment` branch only. No API contract changes, no CSV schema changes, no config.json structure changes. No interaction with running app on port 8001.

Changes are ordered: highest impact first, then within same tier: lowest risk / lowest effort.

---

## Tier 1: Fix Real Bugs (implement in iterations 3-4)

### T1-A: Fix broken factor learning feedback loop ⚡ HIGHEST PRIORITY

**File:** `scripts/stock_scorer.py`
**Problem:** `StockScorer.__init__` always calls `self.config = load_config()` which reads `data/config.json` (global). Factor learning saves weights to `data/portfolios/{id}/config.json` (portfolio-specific). The scorer never sees updated weights — the learning loop is broken.

**Fix:**
```python
def __init__(self, regime=None, lookback_days=20, config=None):
    self.config = config or load_config()
    ...
```

**Callers to update:**
- `unified_analysis.py` `_run_ai_driven_analysis()`: `scorer = StockScorer()` → `scorer = StockScorer(config=state.config)`
- `unified_analysis.py` basic fallback: `scorer = StockScorer()` → `scorer = StockScorer(config=config)`
- `opportunity_layer.py` `OpportunityLayer`: `StockScorer(regime=self.regime)` → `StockScorer(regime=self.regime, config=self.config)`
- `risk_layer.py` `RiskLayer`: same pattern
- Note: `execute_sells.py` and `pick_from_watchlist.py` (legacy) can keep using fallback

**Test verification:** After fix, `StockScorer(config=state.config)` for microcap portfolio should use `price_momentum: 0.2309` not `0.25`.

---

### T1-B: Remove dead `RiskManager` import from `unified_analysis.py`

**File:** `scripts/unified_analysis.py` line 32
**Problem:** `from risk_manager import RiskManager` is imported but `RiskManager` is never instantiated in `unified_analysis.py`. Dead import that loads extra module.

**Fix:** Remove line 32.

---

### T1-C: Remove unused `layer1_output` parameter

**File:** `scripts/unified_analysis.py`
**Problem:** `_run_ai_driven_analysis()` accepts `layer1_output: dict` but never uses it. The Layer 1 sells are passed via `layer1_sell_actions`.

**Fix:** Remove `layer1_output` param from function signature and the call site.

---

### T1-D: Fix `fetch_prices_batch()` missing timeout protection

**File:** `scripts/portfolio_state.py`
**Problem:** `fetch_prices_batch()` calls `yf.download()` directly (line ~413) without the 60-second thread-based timeout in `yf_session.cached_download()`. Price fetches for live positions (called on every API request during dashboard use) can hang indefinitely.

**Fix:** Wrap the `yf.download()` call in `fetch_prices_batch()` with the same timeout pattern from `yf_session.py`:
```python
import threading
_result = [pd.DataFrame()]
def _do_download():
    try:
        _result[0] = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
    except Exception as e:
        print(f"  [warn] batch price fetch failed: {e}")
t = threading.Thread(target=_do_download, daemon=True)
t.start()
t.join(timeout=60)
if t.is_alive():
    print(f"  [warn] price fetch timed out for {len(tickers)} tickers")
df = _result[0]
```
Note: Don't use `cached_download()` here since position prices need to be live (no cache). Just add the timeout wrapper.

---

## Tier 2: Dead Code & Cleanup (implement in iterations 4-5)

### T2-A: Delete `data_provider.py`

**File:** `scripts/data_provider.py`
**Problem:** Not imported by any module. 250+ lines of dead code (Alpha Vantage, Finnhub, Polygon, CacheManager). Was an early multi-source abstraction replaced by `yf_session.py` + `public_quotes.py`.
**Fix:** Delete the file. Verify no imports first.

---

### T2-B: Archive one-time utility scripts

**Files to move to `scripts/archive/`** (create dir):
- `backfill_position_sectors.py`
- `backfill_post_mortems.py`
- `backfill_watchlist_sectors.py`
- `fix_total_today.py`
- `migrate_data.py`
- `migrate_to_portfolios.py`
- `audit_sell_prices.py`
- `set_roi_baseline.py`

These are one-time operation scripts that have been run. They don't belong mixed with production pipeline code. Moving to archive keeps them available for reference without cluttering `scripts/`.

---

### T2-C: Mark legacy scripts clearly

**Files:** `scripts/execute_sells.py`, `scripts/pick_from_watchlist.py`, `scripts/pattern_detector.py`, `scripts/explainability.py`

These only run in LEGACY MODE (`UNIFIED_MODE=false`) of `run_daily.sh`, which is never triggered in production (cron uses `unified_analysis.py` directly). Rather than deleting (they're a valid fallback), add a clear header comment:

```python
# ── LEGACY PATH ──────────────────────────────────────────────────────────────
# This script is only used when UNIFIED_MODE=false in run_daily.sh.
# In production, the cron pipeline always uses unified_analysis.py.
# Last active use: pre-2026-03-01
# ─────────────────────────────────────────────────────────────────────────────
```

---

### T2-D: Remove dead code from `schema.py`

**File:** `scripts/schema.py`
**Items:**
- `LEGACY_COLUMN_MAP` (lines 60-72): defined but imported nowhere — dead code
- `TRANSACTION_COLUMNS_BASIC` (line 29): defined but imported nowhere — verify

**Fix:** Remove both if confirmed unused.

---

### T2-E: Mark `social_sentiment.py` as disabled

**Files:** `scripts/social_sentiment.py`, relevant guard points
The module has `DISABLE_SOCIAL=true` hardcoded in all cron scripts. Add a header doc note and consider whether to revive with a better provider (Reddit API, alternative) or remove the scaffolding. For now, add header comment.

---

### T2-F: Mark `webapp_helpers.py`

**File:** `scripts/webapp_helpers.py`
Not imported anywhere. Add header comment or delete if truly unused.

---

## Tier 3: Per-Portfolio AI Model Tier (implement in iteration 5)

### T3-A: Add per-portfolio `ai_model` config key

**Problem:** All 13 portfolios use `claude-opus-4-6` (from `schema.py:CLAUDE_MODEL`) regardless of portfolio size or complexity. Small portfolios ($1K-$5K) are paying Opus prices for simple allocation decisions.

**Fix:** Add `ai_model` to `ai_allocator.run_ai_allocation()` signature, defaulting to `CLAUDE_MODEL`. Read from portfolio config:

In `ai_allocator.py`:
```python
model = state.config.get("ai_model", CLAUDE_MODEL)
response = client.messages.create(model=model, ...)
```

**Suggested portfolio tiers:**
- `claude-opus-4-6`: Large portfolios, complex strategies (max, adjacent-supporters-of-ai, defense-tech)
- `claude-sonnet-4-6`: Medium portfolios (microcap, boomers, cash-cow-compounders)
- `claude-haiku-4-5-20251001`: Small/aggressive portfolios (yolo-degen-momentum, asymmetric-microcap-compounder)

No config.json changes required — uses existing `ai_model` key if present, falls back to Opus.

---

## Tier 4: Code Quality (implement in iterations 5-6)

### T4-A: Vectorize `calculate_cash()`

**File:** `scripts/portfolio_state.py` lines 348-360
**Problem:** Python for-loop over all transaction rows. Grows linearly with trade history.

**Fix:**
```python
def calculate_cash(transactions: pd.DataFrame, starting_capital: float) -> float:
    if transactions.empty:
        return starting_capital
    buy_mask = transactions["action"].isin(["BUY", Action.BUY, "ADD", Action.ADD])
    sell_mask = transactions["action"].isin(["SELL", Action.SELL, "TRIM", Action.TRIM])
    total_spent = transactions.loc[buy_mask, "total_value"].astype(float).sum()
    total_received = transactions.loc[sell_mask, "total_value"].astype(float).sum()
    return starting_capital - total_spent + total_received
```

---

### T4-B: Vectorize `_update_positions_with_prices()`

**File:** `scripts/portfolio_state.py`
**Problem:** `df.iterrows()` loop for price updates. Can be vectorized for clarity and speed.

This is a more involved refactor — the `bought_today` logic for day_change uses per-row date comparison. Map-based approach:
```python
# Map price updates vectorized
tickers_with_prices = [t for t in df["ticker"] if t in price_cache]
# ... use df.loc[mask, col] = values pattern
```

Lower priority than T1s — only worth doing if the iteration allows it.

---

### T4-C: Add `LEGACY_COLUMN_MAP` usage check

Verify `LEGACY_COLUMN_MAP` is actually used anywhere before removing from `schema.py`. Use grep to confirm.

---

## Tier 5: Data Source Improvements (future work, document only in this iteration)

### T5-A: Financial Modeling Prep (FMP) free tier for fundamentals

**Problem:** `yfinance .info()` for earnings/quality/revenue is unreliable (empty, stale, wrong). The `earnings_growth` and `quality` factors — 30% of the composite score combined — are only as good as yfinance's .info() cache.

**FMP free tier:** 250 calls/day. Provides quarterly income statements, balance sheets, key metrics. Would significantly improve fundamentals quality for scoring.

**Implementation sketch:**
- Add `FMP_API_KEY` env var support
- New `scripts/fmp_provider.py` module with `get_fundamentals(ticker)` returning earnings growth, revenue growth, gross margins, ROE, debt/equity
- Integrate into `StockScorer.score_ticker()` as primary source for `earnings_growth` and `quality` factors, with yfinance .info() as fallback

**Risk:** New dependency, rate limit management. Medium effort.

---

### T5-B: SEC EDGAR RSS for catalyst detection

Free, official. 8-K filings = material events (earnings surprises, FDA approvals, M&A). Would directly feed catalyst-driven portfolios (asymmetric-catalyst-hunters, catalyst-momentum-scalper).

---

### T5-C: Improve market regime detection with FRED macroeconomic data

Current regime uses only SMA50/200 on benchmark. Adding VIX term structure, credit spreads (HYG/LQD spread), and yield curve from FRED API (free) would improve regime signal quality, especially for SIDEWAYS detection.

---

## Implementation Order for Iterations 3-6

| Iteration | Tasks |
|-----------|-------|
| **3** | T1-A (StockScorer config fix — highest impact), T1-B (dead import), T1-C (unused param) |
| **4** | T1-D (timeout wrapper), T2-A (delete data_provider), T2-B (archive scripts), T2-D (schema cleanup) |
| **5** | T2-C (mark legacy scripts), T2-E/F (doc comments), T3-A (per-portfolio AI model) |
| **6** | T4-A (vectorize cash calc), final review, commit, update docs |

---

*Written in Iteration 2. Ready for implementation in Iterations 3-5.*
