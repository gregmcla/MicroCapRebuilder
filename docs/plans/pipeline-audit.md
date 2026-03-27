# GScott Pipeline Audit
**Branch:** `trading-pipeline-refactor-experiment`
**Date:** 2026-03-27
**Status:** Iterations 1-6 complete — audit, plan, and implementations committed to branch

---

## Pipeline Flow Map

```
CRON (6:30 AM) → scan.sh
  └─ watchlist_manager.py --update --portfolio {id}
       └─ StockDiscovery.run_all_scans()
            └─ universe_provider.py → etf_holdings_provider.py + exchange_universe_provider.py
            └─ scan types: momentum_breakouts, oversold_bounces, sector_leaders, volume_anomalies
            └─ yf_session.cached_download() → yfinance (4hr disk cache, 60s timeout)
            └─ Writes to data/portfolios/{id}/watchlist.jsonl

CRON (9:35 AM) → execute.sh
  └─ unified_analysis.py --execute --portfolio {id}
       └─ load_portfolio_state(fetch_prices=True)
            ├─ data_files.load_config(portfolio_id)
            ├─ public_quotes.fetch_live_quotes() → cross-validated with yfinance
            └─ market_regime._get_cached_regime_analysis() (1hr TTL)
       │
       ├─ Layer 1: RiskLayer.process(state)
       │    └─ StockScorer.score_watchlist(held_tickers) — re-evaluates positions
       │    └─ Trailing stop / deterioration detection → SellProposal list
       │
       ├─ [if ai_driven=True] → _run_ai_driven_analysis()
       │    └─ WatchlistManager._load_watchlist() → ACTIVE candidates
       │    └─ prewarm_info_for_tickers() — yfinance .info() fundamentals
       │    └─ StockScorer.score_watchlist(candidates)
       │    └─ reentry_guard.get_reentry_context() per candidate
       │    └─ Rich context: TradeAnalyzer, PortfolioAnalytics, FactorLearner, EarlyWarning
       │    └─ ai_allocator.run_ai_allocation() → Claude (claude-opus-4-6)
       │         └─ _build_allocation_prompt() → single API call
       │         └─ _parse_json() → _validate_allocation() → _convert_to_reviewed_actions()
       │
       ├─ [if ai_driven=False + enable_layers=True] → mechanical path
       │    └─ Layer 2: OpportunityLayer.process() — conviction scoring + pattern detection
       │    └─ Layer 3: CompositionLayer.process() — sector limits, correlation checks
       │    └─ Layer 4: ExecutionSequencer.process() — priority ordering
       │    └─ ai_review.review_proposed_actions() — Claude reviews each action
       │
       ├─ [if ai_driven=False + enable_layers=False] → basic fallback
       │    └─ Direct scorer + threshold filter + size calculation
       │    └─ ai_review.review_proposed_actions()
       │
       ├─ Post-processing (ALL paths):
       │    └─ Warning severity position size reductions
       │    └─ Price refresh for proposed BUY tickers
       │    └─ Same-run reentry veto
       │
       └─ execute_approved_actions()
            └─ Sells first → save_transactions_batch() → remove_position() → save_positions()
            └─ Post-mortems → factor_learning.py update
            └─ Buys → validate_transaction() → save_transactions_batch() → update_position()

CRON (12:00 PM + 4:15 PM) → update.sh
  └─ update_positions.py --portfolio {id}
       └─ load_portfolio_state(fetch_prices=True)
       └─ save_snapshot() → daily_snapshots.csv
       └─ factor_learning.py --portfolio {id} (4:15 PM run only via execute.sh)

CRON (every 15 min) → api_watchdog.sh
  └─ curl health check → restart API if down
```

---

## Findings

### 🔴 CRITICAL

**C1 — `data_provider.py` is dead code**
`data_provider.py` is a 250+ line multi-source data abstraction (Alpha Vantage, Finnhub, Polygon, cache layer) that is not imported by any other module. It was built as the "smart data layer" but was superseded by `yf_session.py` + `public_quotes.py` + direct yfinance calls. The file references `"vgscottbles"` in comments (garbled text — suggests it was auto-generated or corrupted), and `CACHE_DIR = DATA_DIR / ".cache"` creates a separate cache dir.
- **Action:** Delete or move to `backup/`. Zero production impact.

**C2 — 15 scripts have duplicate `load_config()` pointing to wrong path**
The following scripts all define `CONFIG_FILE = DATA_DIR / "config.json"` and `def load_config()` that reads from the *global* `data/config.json` — not from `data/portfolios/{id}/config.json`. This is the fallback path used when a class is instantiated without a config dict. In multi-portfolio mode, if any of these classes are ever instantiated without being passed the correct portfolio config, they'll silently load the wrong config (or error if `data/config.json` doesn't exist).

Affected files: `stock_discovery.py`, `factor_learning.py`, `stock_scorer.py`, `etf_holdings_provider.py`, `risk_layer.py`, `opportunity_layer.py`, `watchlist_manager.py`, `market_regime.py`, `data_provider.py`, `universe_provider.py`, `risk_manager.py`, `composition_layer.py`, `migrate_data.py`, `execution_sequencer.py`, `data_files.py`.

`data_files.py` already has the correct portfolio-aware `load_config(portfolio_id)`. All other scripts should use `from data_files import load_config` instead of duplicating it.
- **Action:** Replace local `load_config()` implementations with `from data_files import load_config`. Medium complexity — need to verify each script's fallback behavior is preserved.

---

### 🟠 HIGH

**H1 — Legacy pipeline scripts (`execute_sells.py`, `pick_from_watchlist.py`) are maintained but nearly dead**
These scripts implement the legacy mode (triggered only when `UNIFIED_MODE=false` or no API key). They use the old `RiskManager` class rather than `RiskLayer`, and `explainability.py` (which is itself only used here). In practice, all 13 portfolios are either `ai_driven=true` or use `enable_layers=true` — the basic fallback in `unified_analysis.py` already handles the no-API case. These legacy scripts represent maintenance overhead: if `portfolio_state.py` changes, these need updating too.
- **Action:** Consider deprecating or archiving `execute_sells.py`, `pick_from_watchlist.py`, and `explainability.py`. Their `LEGACY MODE` in `run_daily.sh` is never triggered in production (cron uses `unified_analysis.py` directly). Alternatively, add a clear `# LEGACY - not used in production` header.

**H2 — `risk_manager.py` is partially superseded by `risk_layer.py`**
`risk_manager.py` contains `RiskManager` (simple stop/take-profit + position sizing). `risk_layer.py` contains `RiskLayer` (full dynamic stops, deterioration, trailing stops). `RiskManager` is still imported in `unified_analysis.py` (line 32) but never actually instantiated there — it's a leftover import. `RiskManager` is only instantiated in the legacy scripts. The position sizing logic in `risk_manager.py` is valuable but duplicated across `opportunity_layer.py` and the fallback path in `unified_analysis.py`.
- **Action:** Remove dead `from risk_manager import RiskManager` import from `unified_analysis.py`. Consider consolidating position sizing into a shared utility.

**H3 — One-time utility scripts pollute `scripts/` directory**
The following are one-time data migration/backfill scripts that have already been run and serve no ongoing purpose:
- `migrate_data.py` — legacy data migration
- `migrate_to_portfolios.py` — portfolio restructuring migration
- `backfill_position_sectors.py` — sector backfill
- `backfill_post_mortems.py` — post-mortem backfill
- `backfill_watchlist_sectors.py` — watchlist sector backfill
- `fix_total_today.py` — one-time fix script
- `audit_sell_prices.py` — one-time audit
- `set_roi_baseline.py` — one-time baseline setter

These shouldn't be mixed with the production pipeline scripts.
- **Action:** Move to `scripts/archive/` or `backup/scripts/`. No production impact.

**H4 — `CLAUDE_MODEL` hardcoded to `claude-opus-4-6` for all allocations**
`schema.py` line 97: `CLAUDE_MODEL = "claude-opus-4-6"`. This is used for every AI allocation call across all 13 portfolios. Small portfolios (asymmetric-microcap-compounder $1K, yolo-degen-momentum) are running the same expensive Opus model as large ones. AI allocation is the main cost driver.
- **Action:** Add per-portfolio `ai_model` config key, defaulting to current model. Small portfolios could use `claude-haiku-4-5-20251001` for ~10x cost reduction with negligible quality difference on simple allocations.

**H5 — `ai_allocator.py` has no tests; `_validate_allocation()` and `_parse_json()` are untested (known issue)**
Known from PROJECT_STATE.md. The allocator's JSON parsing uses regex fallback (`re.search`) which is fragile — malformed AI output silently falls back to Layer 1 sells only. No test coverage means regressions go undetected.
- **Action:** Add unit tests for `_validate_allocation()` and `_parse_json()` with edge cases: empty response, malformed JSON, over-budget buy, sell of non-held ticker.

---

### 🟡 MEDIUM

**M1 — `data_provider.py` shadow cache (`data/.cache/`) may exist with stale data**
`data_provider.py`'s `CacheManager` writes to `data/.cache/` (JSON files with 15-min TTL). This directory may exist and contain stale cached data from before the migration to `yf_session.py`. Not gitignored explicitly (though `data/` subdirs generally are).
- **Action:** Check if `data/.cache/` exists and delete it.

**M2 — `StockScorer` loads global config (not portfolio-specific) in its own `load_config()`**
`StockScorer.__init__` calls `self.config = load_config()` which reads from `data/config.json` (global), not the portfolio's `config.json`. This means the `scoring.default_weights` it reads come from the wrong place for portfolios. In practice, most portfolios probably don't have portfolio-specific scoring weights in their config, so this doesn't cause a bug today — but it means per-portfolio weight tuning via config won't work correctly. `factor_learning.py` adjusts weights and saves them... where?

**M2b — Factor learning feedback loop is BROKEN (HIGH priority)**
`factor_learning.py` saves adjusted weights to `data/portfolios/{id}/config.json` (portfolio-specific, correct).
`StockScorer.__init__` calls `self.config = load_config()` which reads from `data/config.json` (GLOBAL, wrong).

Verified:
- `data/portfolios/microcap/config.json` has factor-learning-adjusted weights: `price_momentum: 0.2309`
- `data/config.json` (global) still has original weights: `price_momentum: 0.25` (plus stale `regime_weights` block)
- `StockScorer` has no way to accept a config dict — it always reads global config

**Result**: Factor learning runs, saves weights correctly per portfolio, but the scorer always uses global weights. The learning loop is completely bypassed. This should be a HIGH finding.
- **Action:** Add `config: dict = None` parameter to `StockScorer.__init__`. All callers in active pipeline already have portfolio config available — pass it through.

**M3 — `social_sentiment.py` is always disabled but still imported lazily**
`DISABLE_SOCIAL=true` is hardcoded in all cron scripts and `run_dashboard.sh`. The code contains 3 separate lazy-import patterns guarded by `os.environ.get("DISABLE_SOCIAL")`. The module itself (Stocktwits 403s) is broken externally. This is dead weight in the analysis path.
- **Action:** Consider whether social sentiment is worth reviving with a different provider (Reddit/StockTwits alternatives) or removing the scaffolding entirely.

**M4 — `layer1_output` parameter is unused in `_run_ai_driven_analysis()`**
`unified_analysis.py` line 95: `layer1_output: dict` is accepted as a parameter but never used inside the function. The Layer 1 sell actions are passed separately via `layer1_sell_actions`. This is flagged in PROJECT_STATE.md open bugs.
- **Action:** Remove unused parameter from signature and all call sites.

**M5 — `run_daily.sh` is superseded by cron but kept in sync manually**
`run_daily.sh` is the original manual pipeline runner. The cron scripts (`cron/scan.sh`, `cron/execute.sh`, `cron/update.sh`) are the actual production pipeline. `run_daily.sh` still works but has a different structure (LEGACY_MODE fallback, different portfolio iteration). Any change to the pipeline needs to be maintained in both places.
- **Action:** Refactor `run_daily.sh` to be a thin wrapper around the cron scripts, or add a comment block clearly documenting the difference.

**M6 — `fetch_prices_batch()` in `portfolio_state.py` uses yfinance directly (bypassing `yf_session` timeout wrapper)**
`portfolio_state.py:413` calls `yf.download()` directly without going through `yf_session.cached_download()`. This means position price fetches (called every minute during dashboard use) don't have the 60-second timeout protection that scanner calls have. A hung yfinance call during price refresh could block the API response.
- **Action:** Wrap the `yf.download()` call in `fetch_prices_batch()` with the same thread-based timeout from `yf_session.py`, or route through `cached_download` with a short TTL.

**M7 — `calculate_cash()` iterates rows rather than using vectorized pandas**
`portfolio_state.py:351-360` uses a Python for loop over all transaction rows to calculate cash. With a large transaction history, this is slow. Should use `df.loc[mask, "total_value"].sum()` with boolean masks.

**M8 — `_update_positions_with_prices()` uses row iteration (`df.iterrows()`)**
Same pattern — can be vectorized with `.apply()` or vectorized column operations. Not critical for small portfolios but a bad pattern.

---

### 🟢 LOW / QUICK WINS

**L1 — `data_files.py` has a global `CONFIG_FILE = DATA_DIR / "config.json"` that's never used**
The module-level `CONFIG_FILE` path in `data_files.py` is defined but the `load_config()` function uses `_resolve_data_dir(portfolio_id) / "config.json"` internally. The module-level constant is misleading dead code.

**L2 — `schema.py` `LEGACY_COLUMN_MAP` is likely unused**
`LEGACY_COLUMN_MAP` maps old column names to new ones. Check if this is actually used anywhere in the active pipeline or if it's a relic from early migrations.

**L3 — `market_regime.py` has its own `load_config()` fallback returning hardcoded benchmark symbols**
Its fallback returns `{"benchmark_symbol": "^RUT", "fallback_benchmark": "IWM"}` which are defaults that should come from config. It works, but means `^RUT` is hardcoded in two places.

**L4 — Missing type annotations on several key functions in `unified_analysis.py`**
`run_unified_analysis()` returns `dict` with no typed schema. The dict structure is used in `execute_approved_actions()` which must assume the correct keys. A TypedDict or dataclass for the analysis result would prevent key errors.

**L5 — `webapp_helpers.py` — unclear what this does and if it's used**
Not imported by anything obvious. Needs verification.

**L6 — `pattern_detector.py` — only used in legacy mode of `run_daily.sh`**
Only called as `python3 scripts/pattern_detector.py` in the legacy path of `run_daily.sh`. Pattern detection in the active pipeline is handled inside `opportunity_layer.py`. This is dead code in production.

**L7 — `public_quotes.py` has a side-effect import guard but may suppress real errors**
`try: from public_quotes import ...; use_public = public_configured() except ImportError: use_public = False` in `portfolio_state.py`. If `public_quotes.py` exists but fails for a different reason (missing dependency, bad env var), it silently falls back to yfinance with no indication.

---

## Data Sources Assessment

| Source | Used For | Reliability | Notes |
|--------|----------|-------------|-------|
| yfinance | Historical prices, fundamentals (`.info`), benchmarks | Medium | Rate-limited, .info() can be empty; 60s timeout in yf_session |
| public.com SDK | Live position prices | Good | Requires `PUBLIC_API_KEY`; cross-validated against yfinance |
| Stocktwits | Social sentiment | Broken | 403 errors; DISABLE_SOCIAL=true everywhere |
| Alpha Vantage | (Planned in data_provider.py) | N/A | Dead code — never integrated |
| Polygon | (Planned in data_provider.py) | N/A | Dead code — never integrated |
| Finnhub | (Planned in data_provider.py) | N/A | Dead code — never integrated |

**Data source gaps:**
1. **Fundamentals quality**: `yfinance .info()` for earnings/quality/revenue data is notoriously unreliable (empty, stale, or wrong). The scoring model's `earnings_growth` and `quality` factors are only as good as yfinance's .info() cache.
2. **No intraday data**: All scoring uses daily bars. For intraday momentum strategies (catalyst-momentum-scalper), daily bars miss the actual catalyst window.
3. **No news/catalyst data**: The system scores on price/volume/fundamentals but has no news awareness. Catalyst-driven strategies (asymmetric-catalyst-hunters) are flying blind on catalysts.
4. **No options flow / dark pool**: Advanced retail traders use options activity and dark pool prints as leading indicators. Not integrated.

---

## Architecture Assessment

### What's Working Well
- `portfolio_state.py` as the single source of truth — no more scattered CSV reads
- `yf_session.py` disk cache + 60s timeout — stable under load
- `ai_allocator.py` separation from AI review path — clean boundary
- `reentry_guard.py` pure design (no trading module imports)
- Atomic CSV writes (`.tmp` + `Path.replace()`) — crash-safe
- `schema.py` central column definitions
- Per-portfolio config isolation under `data/portfolios/{id}/config.json`
- Cron automation with watchdog restart

### Structural Issues
1. **Two competing class hierarchies for risk**: `RiskManager` (legacy) + `RiskLayer` (active) — confusing
2. **Duplicate `load_config()` everywhere** — 15 files, most pointing to wrong path in multi-portfolio context
3. **Dead code volume**: `data_provider.py`, `pattern_detector.py` (production), 8 one-time utility scripts, `explainability.py` (legacy path only) all in `scripts/` mixed with production code
4. **`run_daily.sh` vs cron**: Two pipeline runners with drift risk
5. **No type safety on the analysis result dict**: The `run_unified_analysis()` → `execute_approved_actions()` handoff uses an untyped dict

---

## Smarter Approaches Worth Exploring

### Data Sources
1. **Financial Modeling Prep (FMP) free tier**: Better fundamentals than yfinance .info() — quarterly earnings, revenue growth, gross margins. 250 API calls/day free. Would fix the `earnings_growth` and `quality` scoring factors significantly.
2. **Unusual Whales or Market Chameleon (free tiers)**: Options flow data. High signal for small-cap catalysts.
3. **SEC EDGAR real-time RSS**: Free, official. 8-K filings = catalysts. Could feed the catalyst-driven portfolios.
4. **FRED API (Federal Reserve)**: Free macroeconomic data — interest rates, credit spreads, VIX term structure. Could strengthen market regime detection beyond just SMA50/200.

### Architecture
1. **Typed result objects instead of dicts**: `run_unified_analysis()` should return a `AnalysisResult` dataclass. Eliminates silent key-miss bugs.
2. **Centralize config loading**: Single `from data_files import load_config` everywhere. Fixes the multi-portfolio config bug risk.
3. **Portfolio-aware `StockScorer`**: Pass `portfolio_id` to scorer so it reads the right `config.json` for scoring weights. Right now factor learning adjusts weights but the scorer might not read them correctly.
4. **Consolidate position sizing**: Three places calculate position sizing (risk_manager.py, opportunity_layer.py, unified_analysis.py fallback). Should be one function.

### Process
1. **Pre-market data freshness**: Scan runs at 6:30 AM but yf_session cache TTL is 4 hours. If previous scan was at 3:30 PM prior day, cache is still valid and the 6:30 AM scan uses yesterday's data. Consider reducing TTL for pre-market scans or invalidating cache at scan start.
2. **Factor learning feedback loop**: `factor_learning.py` adjusts weights based on completed trades, but `StockScorer` reads from `data/config.json` (global) not portfolio-specific config. The learning loop may be writing weights that the scorer doesn't read.

---

## Summary: Top 10 Improvements by Impact

| Rank | Finding | Impact | Risk | Effort |
|------|---------|--------|------|--------|
| 1 | M2b: Fix broken factor learning feedback loop (StockScorer reads global config, ignores portfolio weights) | **CRITICAL** | Low | Low |
| 2 | C2: Centralize `load_config()` — fix multi-portfolio config bug risk | High | Medium | Medium |
| 3 | H4: Per-portfolio AI model tier — cost reduction | High | Low | Low |
| 4 | M6: Add timeout wrapper to `fetch_prices_batch()` | High | Low | Low |
| 5 | H5: Add tests for `_validate_allocation()` / `_parse_json()` | High | None | Medium |
| 6 | C1: Delete `data_provider.py` | Medium | None | None |
| 7 | H3: Archive one-time utility scripts | Medium | None | None |
| 8 | H2: Remove dead `RiskManager` import + L5/L6 dead code cleanup | Medium | None | Low |
| 9 | M4: Remove unused `layer1_output` param + M7+M8 vectorize loops | Low | None | Low |
| 10 | Data: Add FMP free tier for better fundamentals | High | Medium | Medium |

---

---

## Changes Implemented (branch: trading-pipeline-refactor-experiment)

### T1-A: Fixed broken factor learning feedback loop ✅
`StockScorer.__init__` now accepts `config: dict = None`. All active pipeline call sites updated:
- `unified_analysis.py` (both AI-driven and fallback paths): `StockScorer(config=state.config)` / `StockScorer(config=config)`
- `risk_layer.py` (both call sites): `StockScorer(regime=state.regime, config=self.config)`
- `opportunity_layer.py`: `StockScorer(regime=state.regime, config=self.config)`

### T1-B: Removed dead `RiskManager` import ✅
Removed `from risk_manager import RiskManager` from `unified_analysis.py` (was imported but never instantiated).

### T1-C: Removed unused `layer1_output` parameter ✅
Removed from `_run_ai_driven_analysis()` signature and call site.

### T1-D: Added 60s timeout to `fetch_prices_batch()` ✅
`portfolio_state.py` now wraps the yfinance batch download in the same thread-based timeout pattern used by `yf_session.cached_download()`. Prevents API hangs from blocking dashboard responses.

### T2-A: Archived dead `data_provider.py` ✅
Moved to `scripts/archive/`. Not imported by any module.

### T2-B: Archived 8 one-time utility scripts ✅
Moved to `scripts/archive/`: backfill_position_sectors, backfill_post_mortems, backfill_watchlist_sectors, fix_total_today, migrate_data, migrate_to_portfolios, audit_sell_prices, set_roi_baseline.

### T2-C: Marked legacy scripts with clear header ✅
`execute_sells.py` and `pick_from_watchlist.py` now have `# LEGACY PATH` header comments.

### T2-D: Removed dead code from `schema.py` ✅
Removed `TRANSACTION_COLUMNS_BASIC` and `LEGACY_COLUMN_MAP` — neither imported anywhere.

### T3-A: Per-portfolio AI model tier ✅
`ai_allocator.py` now reads `state.config.get("ai_model", CLAUDE_MODEL)`. Portfolios can set `"ai_model": "claude-haiku-4-5-20251001"` in config.json to use cheaper models for simple allocations without any code changes.

### T4-A: Vectorized `calculate_cash()` ✅
Replaced row iteration with vectorized pandas boolean mask operations.

**All 91 tests passing after changes.**

*See `pipeline-improvements.md` for full ranked plan including items not yet implemented (T4-B, T5-A-C).*
