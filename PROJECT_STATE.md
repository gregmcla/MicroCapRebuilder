# MicroCapRebuilder — Project State

> **Read this at the start of every session before doing anything else.**
> **Update it at the end of every session.**

---

## Current Phase

**Operational — 7 active live-mode portfolios, all `ai_driven=True`: max, asymmetric-catalyst-hunters, gov-infra, unloved-microcap-cash-cows, max2, max-b, manualbuy. Cron RE-ENABLED + hardened. `scan-perf-overhaul` merged to main 2026-06-26.**

---

## Recently Completed (2026-07-01) — Dashboard UX Overhaul + Build Health (PR #12, branch `dashboard-ux-feedback-flash-a11y`)

Frontend-only UX/quality pass on the dashboard + portfolio views, from a UX audit. **Open PR #12 (not yet merged); no CI on the repo, so "green" = local `npm run build` exit 0.** tsc 0 errors throughout; each step verified via tsc-diff + eslint + `vite build` + dev-server transform (no browser automation available — behavior of new UI not runtime-QA'd).

- **Feedback/toast layer** — new zero-dep `lib/toastStore`+`lib/toast`+`ui/Toaster` (dedupe, reduced-motion-safe). Global `QueryCache`/`MutationCache` `onError` toast every failed query/mutation; `api.ts` now surfaces FastAPI `detail`. **Execute confirms fills** + success toasts on all money paths. De-silenced swallowed catches; IB tabs (main brief, Dna/Lineage/Decisions) no longer stick on "Loading…" (inline error + Retry).
- **Live value flash** — `useValueFlash`+`ui/FlashValue`: P&L flashes green/red on change (TopBar, MatrixGrid cells, overview cards).
- **Win-milestone celebration** — `lib/milestones`+`useMilestoneCross`+`ui/MilestoneBadge`: gold chip on books ≥25% all-time; pops + synthesized `milestone` fanfare (`sounds.ts`) on a fresh cross (seeded on mount, no page-load spam).
- **a11y/motion** — global `:focus-visible` ring; app-wide `prefers-reduced-motion` gate; `aria-label`s on 8 icon-only buttons.
- **MatrixGrid** — selection ring on click; real empty state; removed invisible chromatic-aberration layer.
- **Intelligence Brief polish** — tablist/tab + roving-tabindex + arrow-key nav; neutral (was red/danger) close-button hover; expandable warning rail.
- **Label clarity** — tooltips on Health / vs-SPY / vs-Bench / Trend / regime / Deployed / posture.
- **Build health** — cleared all **25 pre-existing `tsc` errors** (`npm run build` was red before this) — added `ai_driven` to `PortfolioState`, `take_profit_pct`/`max_positions`/`screener`/`ai_refinement` to `AiConfig`; deleted dead `CenterPane.tsx`; removed unused code; `fontVariantNumeric`→`tabular-nums` class; misc type fixes.
- **eslint debt** — 64 → 31 problems. Fixed all classic issues (`no-explicit-any` ×12, `no-unused-expressions` ×8, `no-unused-vars` via `_`-ignore config) + `static-components` ×11 (hoisted `Stat`/`SecondaryChip` to module scope). **Remaining 31 (21 err + 10 warn) are aggressive React-Compiler rules** (`set-state-in-effect`, `purity`/Date.now-in-render, `refs`, `exhaustive-deps`, `preserve-manual-memoization`) on working code — **deferred**: need in-browser QA to fix safely (e.g. useQuery migration for the fetch effects), not blind refactors in a live app.

**Deferred / follow-ups:** MatrixGrid micro-cell size-floor (restructures the squarified treemap — needs visual QA); the 31 remaining React-Compiler lint items; merge PR #12 after review.

---

## Recently Completed (2026-06-26, session 2) — Cron Hardening, Overview Fix, Model Tiers, day_change Fix

### Cron Hardening
- **`cron/scan.sh`** — atomic `mkdir` overlap guard (POSIX, no `flock` needed on macOS), 180s per-portfolio timeout, weekend DOW check, `caffeinate -i` to prevent Mac sleep mid-run.
- **`cron/analyze.sh`** — same atomic `mkdir` lock + `caffeinate -i` added.
- **`cron/api_watchdog.sh`** — 500KB log rotation; redirected restarted API stdout to `/tmp/mcr_api.log` (was leaking all uvicorn output into the watchdog log → 5.5MB bloat).
- **Mac wake schedule**: user ran `sudo pmset repeat wakeorpoweron MTWRF 06:25:00` — Mac wakes at 6:25 AM weekdays so cron jobs run before market open. Note: cron doesn't catch up missed jobs after wake; `caffeinate` prevents sleep mid-job.

### Overview Endpoint Parallelization
- **`api/routes/portfolios.py`** — overview endpoint was timing out (25-30s) because it loaded all portfolios serially via `load_portfolio_state(fetch_prices=True)`. Refactored to `ThreadPoolExecutor(max_workers=min(N,8))` with `as_completed`. Result: 7.7s first call, 93ms warm.

### Last-Scanned Timestamp
- **`api/routes/discovery.py`** — `_watchlist_last_scanned()` reads `watchlist.jsonl` mtime; returned as `last_scanned` ISO string in `/scan/status`.
- **`dashboard/src/components/CommandBar.tsx`** — SCAN button shows `"Xm ago"` timestamp below it.
- **`dashboard/src/components/ActionsTab.tsx`** — watchlist header uses `last_scanned` as fallback.

### Model Tier Architecture
- **Opus 4.8** (`CLAUDE_MODEL` in `schema.py`): money-critical paths only — `ai_allocator` + `ai_review`.
- **Sonnet 4.6**: analysis/content — `screener_provider`, `reflection`, `strategy_generator`, `intelligence.py`, `system.py`. Each module uses a local `_XYZ_MODEL` constant so global CLAUDE_MODEL bumps don't accidentally hit them.
- **Haiku 4.5**: ephemeral generation — `trade_reviews` re-analyze (unchanged).
- Updated `schema.py` CLAUDE_MODEL to `claude-opus-4-8`.

### day_change Zeroing Bug Fix
- **Root cause**: when yfinance is rate-limited, `prev_close` returns `None` → old code wrote `0.0` to `day_change_pct`, clobbering correct prior values.
- **Fix**: `has_day_change` flag in `portfolio_state._update_positions_with_prices` — day-change columns only written when `prev_close` is actually available.

### Other
- **`restart.sh`** — new script: kills old API/bot/Vite and restarts all three.
- **`run_dashboard.sh`** — now launches Telegram bot as third process.
- **Branch merged**: `scan-perf-overhaul` → `main` with `--no-ff`, pushed.

---

## Recently Completed (2026-06-26) — Scan Performance Overhaul (Phases 0 + 1)

**Problem:** scans had been timing out (>12 min) for a long time. Deep audit (5 module agents + a live timed run) found the cause empirically, not by guesswork.

**Root causes (measured):** `score_stock` re-downloaded `3mo` bars **per ticker, serially, throttled ~10s each** (`stock_scorer.py:743`), discarding the batch-prewarmed DataFrame already in hand — scoring alone was **375s for 136 tickers**. Compounded by: an unstable batch cache key (universe reshuffled 3×/scan → ~0% cache reuse → 18,452 files / **6.3 GB** of write-only bloat), a 1y prewarm whose data is unused in score-all, an unconditional `sleep(5)`/chunk, a Public.com call with no timeout (**~2.5 min hang**), and a 4h `.info` TTL re-scraping quarterly fundamentals (~44s/scan).

**Result: scans timeout (>720s) → ~12s warm.** Branch `scan-perf-overhaul`, 3 commits, 57/57 integration+cache tests green.
- **Phase 0** (`75961417`): pass prewarmed `df` into `score_stock` (eliminates the 375s leg; falls back to fetch when missing); `_prewarm_cache` fetches 3mo-only on the score-all path with a 1y safety-net when 3mo is throttled; adaptive inter-chunk sleep; `public_quotes` hard timeout (`_call_with_timeout`); `yf_session.sweep_stale_cache()` bounds the cache dir.
- **Phase 1a** (`512e26ed`): `.info` disk TTL 4h → `TTL.FUNDAMENTALS_QUARTERLY` (30d) — `.info` prewarm 44s→0.7s; `_passes_filters` skips (not fails) the market-cap check on empty `.info` (was silently dropping good tickers); scoring loop parallelized (ThreadPoolExecutor, benchmark warmed once); deterministic day-seeded extended rotation (`slot = day_of_year % 3`) replacing 3 per-scan random shuffles → stable cache keys + 3-day coverage 70%→100%.
- **Phase 1b** (`daaa8a56`): process-wide scan semaphore (`SCAN_CONCURRENCY`, default 1) so portfolios don't stampede Yahoo; removed the illusory nested-executor timeout; duplicate-scan guard (thread-liveness); per-portfolio once-a-day watchlist backups (was cross-portfolio clobber + ~6 copies/scan); parallel sector backfill (160s→~8s worst case); discovery exception logged + surfaced in `stats["discovery_error"]` instead of a silent "0 discovered".

**Measured (microcap, 434 tickers):** total 376s → 12.2s; `.info` 44s→0.7s; scoring 375s→~1.4s; warm prewarm 0.1s.

**Deferred** (low value now / higher risk): per-ticker cache keys+persistence (P1.1/P1.2, cold-scan consistency), single-load/save watchlist refactor + fully-async social, per-chunk hard-cancel deadline.

**Remaining — Phase 2 (warm-store redesign):** install `yfscreen` (also fixes the 0-ticker portfolios), consume bulk fundamentals (`screener_provider.py:214` discards them), incremental `ScoreStore` gating, nightly prefetch cron, vectorized panel scoring. Plan: `~/.claude/plans/tender-hatching-abelson.md`.

**Gotcha:** repeated test scans rate-limit yfinance; a cold benchmark/bar fetch then hits the 60s download timeout, so a single scan can read ~60-80s even though warm prewarm is 0.1s. Same ~60s signature appears in `test_analyze_stop_loss_triggered` when bars cache is cold (pre-existing test-hermeticity gap, reproduces with the scan changes reverted).

---

## Recently Completed (2026-06-22) — Decision Trace (#9) + AH P&L Split

### Decision Trace (Feature #9 from the roadmap)
Every `/analyze` cycle now emits a structured JSON tree of decisions to `data/portfolios/{id}/decisions/{trace_id}.json` (gitignored), indexed by `.index.jsonl`. The trace captures 8 typed steps: regime_detection → layer1_risk → watchlist_scoring → ai_allocator_prompt → ai_allocator_call → ai_allocator_parse → ai_allocator_validate → result_assemble; an ExecuteStep is appended when execute runs.

**Linkage spine:** every ProposedAction now gets a stable `proposal_id = uuid.uuid4()[:8]` minted at analyze time. Persisted into `.last_analysis.json` and into `transactions.csv` (new `source_proposal_id` + `source_trace_id` columns — additive, `_load_csv` preserves extras). This is what enables click-from-trade → see-the-decision deep-linking.

**API (`api/routes/decisions.py`):** `/recent`, `/{trace_id}`, `/by_proposal/{id}`, `/by_ticker/{ticker}`, `/diff?a=&b=`. Diff highlights regime flips, ≥5pt score changes, prompt-block additions, validation set deltas, count changes.

**UI:** new "DECISIONS" tab in IntelligenceBrief (`dashboard/src/components/IntelligenceBrief/DecisionsTab.tsx`). Recent-cycle rail on the left, typed renderers per step type, prompt + raw Claude response show/hide, diff view picker. Deep-link TRACE buttons added to ActionsTab (every proposed action) and ActivityFeed (every executed transaction in expanded detail). Uses extended `useBriefStore` with `briefInitialProposalId` + `briefInitialTraceId`.

**Verified live on MAX:** analyze produced `max_20260622_185543_f20c.json`, 98KB, 8 expected steps, 8 proposals with unique proposal_ids; `/decisions/by_proposal/5792394c` resolves correctly.

**Tests:** 12 new unit tests in `scripts/tests/test_decision_trace.py`. Full backend suite 338/339 (1 flake in `test_cron_scripts` unrelated, passes alone). TypeScript clean.

**Deferred (per plan):** Telegram deep-links (needs URL state plumbing + auth), mechanical-path instrumentation (dead code), trace replay simulation (#1 territory), decision-quality ML model (needs months of accumulated traces).

**Plan doc:** `docs/superpowers/plans/2026-06-22-decision-trace.md`

### After-Hours P&L Split (same commit)
Fixed the post-4pm "daily stats reset to zero" bug. Root cause: `state.py` was explicitly zeroing `day_change` outside 9:30–16:00 ET; `portfolio_state.fetch_prices_batch` was also suppressing `prev_closes` when yfinance's last bar wasn't today (which lags in the 4:00–6:00pm window).

**Backend:** `fetch_prices_batch` now returns a 4-tuple including `today_closes` (yfinance daily-bar close = frozen 4pm close after market close). `_update_positions_with_prices` emits `regular_session_change(_pct)` + `extended_hours_change(_pct)` per position; `day_change` preserved as their sum. `prev_closes` gate loosened to "trading-day weekday past 9:30 ET". `api/routes/state.py` emits `session_status` (regular_hours/after_hours/pre_market/closed) + `regular_session_pnl(_pct)` + `extended_hours_pnl(_pct)`. Same split added to `/api/portfolios/overview` and `/api/digest`.

**Frontend:** all live-data surfaces — TopBar, PositionsPanel, PositionDetail, OverviewPage card + AggregateBar, MatrixGrid PortfolioStrip/BottomPanel, Digest BookHero + PortfolioCompare — render regular-session as primary, append `(+$Y AH)` muted in parens during after-hours/pre-market.

**Snapshot history** (MatrixGrid history table, Snapshot type) and tiny visual indicators (ConstellationMap tick, mover lists) left as-is per plan — historical snapshots are regular-session by construction.

---

## Recently Completed (2026-06-05) — AI-Driven Path Fundamental Scoring Fix

**Bug (since AI-driven mode was born, commit `1d23f14e`):** `run_ai_driven_analysis` pre-warmed yfinance `.info` fundamentals into `info_cache` but never passed it to `scorer.score_watchlist()` (`unified_analysis.py:154`). Result: every AI-driven portfolio scored `earnings_growth=50.0` and `quality=50.0` (the "data unavailable" defaults) on every watchlist candidate — 30% of composite weight dead, and `factor_learning` had zero variance on those two factors (learning on 4 of 6 factors). The AI allocator DID receive info_cache for its prompt, which masked the bug (Claude's reasoning cited real fundamentals while quant scores read 50/50).

**Fix:** one kwarg — `score_watchlist(candidates, info_cache=info_cache)`. Plus corrected the symptom-normalizing comment in `ai_allocator.py:331` ("always 50 in AI-driven"). Regression test `test_ai_driven_factor_scores_use_fundamentals` proven to fail on unfixed code. Two test stubs updated to tolerant signatures. Full suite **327 green**. Real-data verified: MAX watchlist tickers now score eg 75–82.5 / quality 70–81.7.

**Deliberately untouched:** `unified_analysis.py:513` (fallback path) never prewarms fundamentals at all — fixing it adds a prewarm latency hit; no active portfolio uses that branch. Backlog.

---

## Recently Completed (2026-06-01) — Daily Digest Home (new default landing)

Replaced the Overview grid as the default landing (`portfolioId === "overview"`) with an observational **Daily Digest**. Branch: `feature/daily-digest-home` (26 commits). Spec: `docs/superpowers/specs/2026-05-29-daily-digest-home-design.md`. Plan: `docs/superpowers/plans/2026-05-29-daily-digest-home.md`. Built subagent-driven (15 tasks, TDD, per-task two-stage review).

**Four stacked regions** (`dashboard/src/components/Digest/`): BookHero (whole-book equity + you-vs-SPY curve, range toggle), GScottRead (full-width narrative), PortfolioCompare (ranked table, per-portfolio configured benchmark), SinceYesterdayStrip (timeline footer). A sticky **action bar** (DigestActions) restores Update All / Scan All / Analyze All / + New with a live status strip (progress + completion summary). Old 35-card **Grid** preserved via a toggle (reuses OverviewPage); **Map/Chart** views retired from the landing (components kept, unlinked).

**Backend:** `scripts/digest_service.py` (`build_digest`, capital-flow-neutral `build_book_curve`, `build_recap`, posture, structured narrative + disk cache) → `GET /api/digest` and `GET /api/digest/narrative` (`api/routes/digest.py`). 18 digest tests; full suite 317 green.

**Key decisions / fixes:**
- Scope = **active AND live** portfolios (paper-mode excluded entirely; `exclude_from_aggregates` respected). Only 6 are active live (docs saying 16/35 were stale).
- **Book curve is capital-flow-neutral** — compounds daily market P&L over equity base, so deposits/seeding don't fake returns (killed a bogus +244% vs SPY).
- **Benchmark fetch bug fixed** — `cached_download` defaults `period`, so passing `start`/`end` raised in yfinance and returned empty SPY; now fetch by period + slice (`_fetch_bench_series`).
- **GScott's Read** caches server-side (`data/digest_narrative.json`) — NO Claude call per page load; manual ↻ refresh + "Updated" timestamp. Uses **Sonnet 4.6** (synthesis task; Opus was overkill).
- Range toggle now drives a live **You/SPY/α** readout + window-return delta bubble.
- a11y: reduced-motion gating, focus rings, keyboard nav, row click-through to portfolio.

**Status:** feature-complete and verified in-browser (scroll, range toggle, actions all confirmed working). Pending: merge/PR decision.

---

## Recently Completed (2026-05-27) — GScott Adaptive Learning Overhaul

Three-task overhaul replacing GScott's weak factor-learning loop. Commit: `7ad79f33`.

**Task 1 (prior session):** Per-trade detail in Claude's analyze prompt. `scripts/recent_trades.py` joins `transactions.csv` + `post_mortems.csv` via `buy_transaction_id` (not ticker-only), surfaces last 15 closed trades with entry reasoning, factor scores at entry, exit summary, and pattern tags. Replaces aggregate-stats block.

**Task 2 (this session):** Regime-conditional Bayesian weight learner (`scripts/bayesian_weights.py`) replaces the broken ±5% adjuster. Beta(10,10) prior, top-30%/bottom-30% bucket predictive power, iterative clamp+renormalize that actually enforces the cap. Fixes the normalization leak that was letting MAX's price_momentum drift to 0.4955. Per-portfolio `weight_cap` / `weight_floor` in `learning.*` config; MAX + MAX2 get cap=0.55. Initial recalibration run on 4 active portfolios. 11 unit tests.

**Task 3 (this session):** Self-curating Opus observation memory (`scripts/reflection.py`). After every execute with trades, Opus reviews per-trade + clustered history and emits retire/update/add/add_shared curation operations to `data/portfolios/{id}/observations.json` and `data/shared_observations.json`. Observations are tagged by regime; analyze prompt only injects regime-matching + ALL observations. Cross-portfolio factor-level signal pool in `shared_observations.json`. Pattern-clustered trade history (group by dominant entry factor, W/L/avg P&L) also injected into analyze prompt. 13 unit tests.

**Test count:** 185 total (was 36 integration + 149 scripts), all green.

**Key files:** `scripts/bayesian_weights.py`, `scripts/reflection.py`, `scripts/recent_trades.py` (cluster fns added), `scripts/unified_analysis.py` (swapped weight learner + wired reflection), `scripts/ai_allocator.py` (clustered + observations blocks), `tests/integration/conftest.py` (reflection mock).

**asymmetric-catalyst-hunters** — returned False on recalibration (fewer than 10 closed trades). Will recalibrate automatically once it accumulates enough trades.

**UI: Learning tab in FACTORS panel (also 2026-05-27):**
- `api/routes/intelligence.py` — `intelligence-brief` now returns `observations` field (from `reflection.read_observations`)
- `dashboard/src/lib/types.ts` — added `PortfolioObservation` type + `observations?` to `IntelligenceBriefData`
- `dashboard/src/components/IntelligenceBrief/FactorIntelligence.tsx` — two new sections:
  - **Bayesian Weights by Regime**: compact 3-column table (BULL/BEAR/SIDEWAYS) × 6 factors; dominant factor per regime highlighted; active regime column lit in regime color
  - **Opus Observations**: cards with regime badge, n=sample_size, win%, claim text; sorted by sample_size

---

## Recently Completed (2026-05-19) — Buys-Only / Sells-Only Analyze Modes

Two new dashboard buttons (`ANALYZE BUYS`, `ANALYZE SELLS`) reachable from TopBar. Each runs the same `/analyze` pipeline with a `mode` flag that:
- Adds a stance directive to the AI allocator prompt (`CASH DEPLOYMENT MODE` / `RISK REVIEW MODE`) before HARD CONSTRAINTS
- Skips watchlist scoring entirely in `sells_only` (30-60s perf win)
- Passes empty `layer1_sells` to the allocator in `buys_only` so Claude only emits buys
- Filters output by allowed action_type at multiple defense-in-depth layers (`_validate_allocation`, `_assemble_analysis_result`, and the AI-driven path's own return block)
- Drops same-run reentry veto in non-full modes (it requires both sides)
- For enhanced-layers path: `sells_only` short-circuits before Layer 2/3; `buys_only` drops rotation pairs (cash math)

**Endpoints:** `POST /api/{pid}/analyze?mode=full|buys_only|sells_only` and `POST /api/{pid}/execute?mode=...`. Default `full` mode is bit-for-bit identical to today — cron (`cron/analyze.sh` calls without mode) and Telegram untouched.

**Persistence:** three slot files per portfolio — `.last_analysis.json` (full), `.last_analysis.buys.json`, `.last_analysis.sells.json`. Each has its own `.executing.{mode}.json` atomic-rename concurrency guard so the three modes can be executed independently without blocking each other.

**Dashboard:** `dashboard/src/lib/store.ts` was refactored — `portfolioAnalyses[pid]` is now a nested record with three slots (`full`, `buys_only`, `sells_only`), and a new `activeMode` UI state determines which slot the top-level `result`/`isAnalyzing`/etc. mirror. `ActionsTab.tsx` has a `FULL | BUYS ONLY | SELLS ONLY` segmented switcher; EXECUTE button is mode-aware (calls `runExecute(activeMode)` with the matching label).

**Testing:** Full backend suite green at 79 tests (43 ai_allocator unit + 36 integration). Each task shipped with TDD red-green-commit; existing 17 integration regression tests stayed green throughout. TypeScript `--noEmit` clean (no new errors).

**Spec:** `docs/superpowers/specs/2026-05-19-buys-only-sells-only-analyze-design.md`
**Plan:** `docs/superpowers/plans/2026-05-19-buys-only-sells-only-analyze.md`
**Commits:** `9630b00a` (T1) → `d6b9759a` (T1 fix) → `76e27dc5` (T2) → `e20470e1` (T3) → `f1a54417` (T4) → `7ba880c7` (T5) → `7fe25668` (T6) → `0545fcc5` (T7) → `4403f58b` (T8) → `d0ac5657` (T9) → `5beb9e94` (T10) → `107368a9` (T11) → `740686d1` (T12) → `76557ecd` (T13) → `280b10e1` (T14)

**Hotfix `75c6563e`** — dashboard went black on portfolio click after T12. Root cause: `useAnalysisStore(...)` was called inside `{!isOverviewOrLogs && (...)}` in `TopBar.tsx`, violating React's rules of hooks. When switching overview→portfolio, the hook count changed → React threw → TopBar crashed outside the ErrorBoundary → entire page blank. Fix: hoisted `isBuysOnlyRunning` / `isSellsOnlyRunning` to unconditional top-level variables. Also fixed `OverviewPage` `setPortfolioAnalysis` calls (missing `"full"` mode arg) and `ReviewQueuePanel` prop type (now correctly accesses `.full` slot from `AnalysisSlots`).

**Bonus work absorbed in T1:** new `scripts/tests/test_ai_allocator.py` with 36 tests for `_parse_json` and `_validate_allocation` (closes the gap documented in this file's "Open Bugs / Known Issues" section).

---

## Recently Completed (2026-04-27, evening) — Audit Remediation Phases 1-3

Driven by an Opus-4.7 codebase audit that surfaced 18 issues across architecture, reliability, and security. 12 fixes shipped + 1 regression caught and fixed mid-session. Plan file: `~/.claude/plans/stateful-drifting-pinwheel.md`.

**Phase 1 — Stop financial bleeding:**
- `077653d7` Fix 1: atomic write for `.last_analysis.json`
- `1e7f0abf` Fix 2: concurrency guard on `/execute` via atomic rename (race-tested with 5 parallel curls — 1 winner, 4 4xx, no double-execution)
- `c054725c` Fix 4: `threading.Lock` around `_scan_jobs` (race-tested with 2 parallel scans)
- `c99d455b` Fix 5: explicit 180s per-call timeout on `ai_allocator.messages.create()`

**Phase 2 — Reliability hardening:**
- `e468010a` Fix 6: async `httpx.AsyncClient` in `telegram_bot.py` (replaces sync `requests`, frees event loop during execute)
- `f4583aea` Fix 8: schema validation in `_load_csv` (warns + reindexes on column drift; preserves extras)
- `601a1701` Fix 9: per-portfolio file lock via `fcntl.flock` (`scripts/portfolio_lock.py` — blocks cron+API write races on positions/transactions/snapshots/watchlist)
- `3999f9e4` Fix 7 (subagent-driven): `validate_portfolio_id` Depends on every portfolio-scoped route (~24 routes); `field_validator` on `CreatePortfolioRequest.id` rejects path traversal

**Phase 3 — Cleanups:**
- `293741f3` Fix 10+11: replace manual `.env` parsing with `os.environ.get`; use `CLAUDE_MODEL` in `screener_provider.py` (was hardcoded to `claude-sonnet-4-6`, missed in 4.6→4.7 migration)
- `7676dde9` Fix 12: `useEffect` cleanup in `CommandBar` (clears scan polling interval on unmount)
- `71c025c3` Fix 13: replace daemon-thread leak in `stock_discovery` info fetchers (`prewarm_info_for_tickers` + `_get_stock_info`) — `ThreadPoolExecutor` ownership instead of zombie threads

**Regression caught + fixed mid-session:**
- `089bc780` `POSITION_COLUMNS` was stale (missing `day_change`, `day_change_pct`, `price_high`). Fix 8's reindex was DROPPING those columns from positions.csv on load. Result: dashboard "Today" sort showed 0.0 for every position, didn't sort. Fix: add the three real columns to `POSITION_COLUMNS`; change `_load_csv` to PRESERVE extras instead of dropping them. 21/21 MAX positions now show correct day_change values.

**Phase 4 (deferred — needs separate brainstorming sessions):**
- ~~Fix 3: atomic transactions+positions rollback~~ ✅ **shipped 2026-05-06** — `_atomic_state_writes()` context manager in `unified_analysis.py` snapshots positions.csv + transactions.csv + daily_snapshots.csv before any write; restores on exception. Wraps the entire save block. Test 17 flipped from xfail to pass.
- ~~Fix 14: integration test for analyze→execute pipeline~~ ✅ **shipped 2026-05-06** — see below
- ~~Fix 15: structured logging across `scripts/`~~ ✅ **shipped 2026-05-06** — new `scripts/logging_setup.py` (configure_logging + get_logger). Wired into `api/main.py` startup. Migrated key warning sites in `yf_session.py`, `portfolio_state.py`, `unified_analysis.py` from `print(f"Warning: ...")` to `log.warning(...)`. Pattern documented in module docstring; remaining `print()` calls in other modules can migrate as they're touched (no need to convert in one go — they're not breaking anything, just inconsistent).
- ~~Fix 16: split `unified_analysis.py` god functions~~ ✅ **shipped 2026-05-06** — `run_unified_analysis` cut from 612 → 308 lines via 5 extractions: `_run_layer1_risk()`, `_run_enhanced_layers_step2()`, `_run_fallback_scoring_step2()`, `_build_portfolio_context()`, `_assemble_analysis_result()`. The parent function now reads as orchestration: load state → Layer 1 → branch (AI / enhanced / fallback) → context → review → assemble. All 242 tests green, Fix 14 integration suite still 17/17. `execute_approved_actions` (354 lines) left untouched — it already has the cleanest natural seams (price refresh, validate-and-size, atomic writes block, post-mortems) and Fix 3's `_atomic_state_writes` extracted the most critical chunk.
- ~~Fix 17: async-by-default for FastAPI long-running routes~~ ✅ **closed as won't-fix 2026-05-06** — investigation showed the original concern was based on a misconception. FastAPI runs sync `def` route handlers in a Starlette threadpool (40 threads by default), so a long-running `/scan` does NOT block other routes from serving. Converting to `async def` and awaiting sync work via `run_in_threadpool` would be strictly worse (more code, same threading model, easier to introduce event-loop-blocking bugs). The dashboard "hang during scan" symptom that motivated this fix is already handled — `discovery.start_scan` uses background threads and returns immediately. Real concurrency improvements would target threadpool sizing or BackgroundTasks adoption (already partial), not async route conversion.
- Fix 18: **partial 2026-05-06** — extracted 4 small purely-presentational components from `OverviewPage.tsx` (EquitySparkline, SideHeader, LoadingPane, SkeletonBlock → `Overview/presentational.tsx`) and WatchlistPanel from `MatrixGrid.tsx` → `MatrixGrid/WatchlistPanel.tsx`. Moved `HEAT_COLOR` constant to `MatrixGrid/constants.ts`. OverviewPage 1515 → 1440 lines, MatrixGrid 1316 → 1257 lines. TypeScript build check (`npx tsc --noEmit`) clean. The bigger panels in MatrixGrid (ActivityPanel, LogsPanel, HistoryPanel) and the orchestration components in OverviewPage (AggregateBar, PortfolioCard, ReviewQueuePanel, ControlsBar, AttentionPanel, MoversPanel) have helper-function and store dependencies that need careful threading per extraction — best done in a dev-server-running session where each split can be visually verified. The pattern (extract → tsc → commit) is now established.
- ~~Fix 19: cache infrastructure refactor~~ ✅ **shipped 2026-05-06** — see below.

**Fix 19a (HOTFIX shipped 2026-05-06)**: content validation in `scripts/yf_session.py:cached_download`. Discovered live during cluster-ignition analyze: yfinance disk cache for `HUT|3mo` contained MNDY (Monday.com) data, last close $74.18. AI allocator scored HUT using MNDY's price tape and proposed BUY HUT @ $74.18 when actual was $107+. Would have recorded wrong cost basis on execute. Patch: `_content_matches_tickers()` checks MultiIndex ticker level against requested ticker on every cache read AND every download write; mismatch → delete file, return empty, log warning. Verified: corrupt HUT file rejected on first read, refetched fresh $108.43 close. Root cause of poisoning still unknown (not a hash collision — keys are distinct; suspected yfinance race or stray write). Patch is defensive: even if root cause recurs, the bad data can never reach the scorer.

**Fix 19 (shipped 2026-05-06)**: Cache infrastructure refactor (full b+c+d+e bundle). New `scripts/cache_layer.py` with `cache_key()` (canonical-JSON SHA256 16-hex), `CacheLogger` (structured logging.getLogger("cache") with hit/miss/write/evict + extra fields), `TTL` constants tiered by data volatility, `is_market_hours()`/`bars_ttl()` helpers. 15 unit tests in `tests/test_cache_layer.py`. **19b** (hash-keyed invalidation) refactored `screener_provider.py` so cache files are now `screener_cache.{hash}.json` and `refinement_cache.{hash}.json` keyed on filter inputs (sectors/industries/cap/region) and (refinement_prompt + upstream-result hash). Editing `industries` now produces a different hash → guaranteed cache miss. Verified: `industries=[Banks - Regional, Credit Services]` hashes to `59192c70a096ce43`, adding `Capital Markets` → `bbeeea30505ba789`. Old hash files swept >7 days. **19c** (tiered TTLs) `yf_session.cached_download` now uses `BARS_INTRADAY=1h` during 9:30-16:00 ET, `BARS_OVERNIGHT=12h` otherwise. `social_sentiment.CACHE_TTL` tightened 2h→1h. `YF_CACHE_TTL_SECONDS` env var preserved as global override. **19d** (observability) every cache hit/miss/write across 11 modules now emits structured `logging.getLogger("cache")` events with cache name, key prefix (12 char), age_s, reason, size — visible in /tmp/uvicorn.log. **19e** (cache-bust endpoint) new `POST /api/{portfolio_id}/cache/invalidate?scope=screener|refinement|all` in `api/routes/cache.py`. Verified live: deleted legacy screener_cache.json on cluster-ignition. Full suite 241 passed + 1 xfail (no regressions).

**Fix 14 (shipped 2026-05-06)**: `tests/integration/` integration suite for `run_unified_analysis()` + `execute_approved_actions()`. 17 tests, all green (1 xfail expected for Fix 3). Coverage on `unified_analysis.py`: 74% (target 80%; gaps documented in `tests/integration/README.md`). Full project test count: 226 passing + 1 xfail. Hermetic: real fixture portfolios in tmp `_test_pipeline_<hex>` dirs, all externals mocked (Anthropic, yfinance, Public.com, social, news). Files: `conftest.py` (fixtures), `fixtures/seed_portfolio.py` (factory), `fixtures/mock_responses.py` (canned Claude payloads), `test_analyze_pipeline.py` (5 tests: 3 branches + no-candidates + stop-loss), `test_execute_pipeline.py` (10 tests: writes happy path, phantom-sell, double-execute race, atomic .last_analysis, cash double-count, stale-price filter, factor_scores, ai_mode field, micro-position floor, insufficient cash), `test_pipeline_e2e.py` (2 tests: full round-trip + xfailed failure-recovery for Fix 3). Suite runtime: ~4s without coverage, ~6.5s with. Plan: `~/.claude/plans/nifty-painting-ullman.md`.

**Verification through every fix:** 111/111 tests pass. API + bot both healthy through every restart. Phase 4 should land *after* Fix 14 (test harness) so refactors have a safety net.

---

## Recently Completed (2026-04-27, afternoon) — Telegram Bot Notifications ✅

Merged to main. Bot running from `scripts/telegram_bot.py`, logging to `cron/logs/telegram_bot.log`.

**New files:**
- `scripts/telegram_notifier.py` — send-only notifier (scan summary, analysis proposals with APPROVE/REJECT buttons, position snapshots). 18 tests passing.
- `scripts/telegram_bot.py` — long-running async PTB 22.7 bot. APPROVE taps call `/api/{portfolio_id}/execute`. REJECT = silent cleanup. 60-min expiry loop. Watchdog-monitored.
- `cron/analyze.sh` — new cron: calls `/analyze` API per portfolio, then sends Telegram proposals. No auto-execute.

**Modified files:**
- `cron/scan.sh` — tracks OK/FAILED per portfolio, sends consolidated scan summary
- `cron/update.sh` — tracks OK/FAILED per portfolio, sends portfolio snapshot
- `cron/api_watchdog.sh` — restructured (removed early `exit 0`), added bot watchdog block
- `api/routes/discovery.py` — dashboard SCAN button sends single-portfolio Telegram notification
- `.gitignore` — `data/telegram/` added
- `crontab` — `analyze.sh` entry added (paused, ready to uncomment)

**Smoke test results:**
- Proposal message delivered with correct APPROVE/REJECT inline buttons ✅
- REJECT flow: button tap → answerCallbackQuery → editMessageText "❌ Rejected" → pending file deleted → no trades fired ✅
- APPROVE flow: not tested live (user declined to trade), but path verified (same code, hits `/execute` instead)

**One remaining step:** When cron re-enabled, uncomment `analyze.sh` line in crontab (it's already there, just commented out).

**Creds in `.env`:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID=6399477170`, `TELEGRAM_APPROVAL_TIMEOUT_MINUTES=60`

**Spec:** `docs/superpowers/specs/2026-04-27-telegram-notifications-design.md`
**Plan:** `docs/superpowers/plans/2026-04-27-telegram-notifications.md`

---

## Recently Completed (2026-04-22 → 2026-04-26) — Model Experiment + MAX2 + Bug Fixes

### Model swap: 4.6 → 4.7
- `scripts/schema.py` — `CLAUDE_MODEL` bumped from `claude-opus-4-6` → `claude-opus-4-7`
- New `MODEL_EXPERIMENT` config (baseline/challenger/switch_date/end_date)
- All AI surfaces use 4.7 by default: ai_review, ai_allocator, strategy_generator
- `ai_model` field added to `ReviewedAction` dataclass; populated from `response.model` in both ai_review.py and ai_allocator.py
- Tag preserved in `trade_rationale` JSON on every transaction going forward
- **Bug fixed:** `_normalize_reviewed_action()` in unified_analysis.py was dropping `ai_model` when reconstructing dict→namespace (round-trip via /analyze .last_analysis.json → /execute). Added `ai_model=r.get("ai_model")` to SimpleNamespace.

### LOGS page: Model Experiment panel
- New `GET /api/system/model-comparison?attribution=sell|buy` endpoint
- Two cohort panels (baseline 4.6 vs challenger 4.7) with countdown to end of experiment
- Metrics per cohort: buys, closed/open lots, win rate, avg per-trade return, realized/unrealized/total P&L, total P&L % vs starting capital
- Per-portfolio breakdown table below cohort panels
- Toggle between SELL-cohort attribution (default — credits realized P&L to exit decision) and BUY-cohort (legacy — origin attribution)
- Cohort attribution: explicit `ai_model` tag preferred, falls back to date-based (pre/post 2026-04-23 switch)
- **Counting bug fixed:** original FIFO loop incremented `closed`/`wins`/`losses` per match-event, not per lot. Lot fully sold over 3 partial SELLs counted as 3 closes. Refactored to per-lot aggregation pass; closed count + win rate now lot-level (228 buys = 170 closed + 58 open, matches positions.csv reality).

### MAX2 — DNA replica side experiment
- New portfolio cloned from MAX's exact config (same DNA, allcap universe, $5M starting capital)
- Empty positions/transactions/snapshots — fresh start
- `exclude_from_aggregates: true` flag in portfolios.json — keeps MAX2 out of overview totals AND model-comparison cohort (no 4.6 baseline for it)
- Visible as its own card; not pinned to a model (drifts with global default)
- Added `exclude_from_aggregates` field to `PortfolioMeta` dataclass + registry loader

### Overview: Analyze All button + shared analysis store
- "Analyze All" button on Overview header (mirrors Scan All pattern); iterates active portfolios sequentially
- New ReviewQueuePanel below aggregate bar — per-portfolio sections with action lists, click-to-navigate, per-portfolio Execute button
- **Major refactor:** moved per-portfolio analysis state from OverviewPage local useState into shared `useAnalysisStore` keyed by portfolio_id. Top-level `result`/`isAnalyzing`/etc. auto-sync to active portfolio via subscription on `usePortfolioStore`. Solves the "navigate away → results disappear" problem; ActionsTab now sees pre-analyzed results when navigating from Overview.

### Stale-price bug — Public.com cross-source check
- **Root cause:** Public.com returned $80.07 for INTC on 2026-04-23 when actual close was $66.78. Caused MAX2 to record an immediate $122k phantom loss (-2.4%). Old execute logic explicitly bypassed the sanity check for Public.com prices ("trusted, real-time").
- **Fix in `unified_analysis.py:execute_approved_actions`:** always fetch BOTH Public.com AND yfinance, cross-check at 5% tolerance, prefer yfinance on disagreement (verifiable via prev_close). Sanity-check ratio tightened from 2.0× / 0.5× → 1.30× / 0.70×, applied to ALL sources regardless of provider.
- **Data fix:** MAX2's INTC transaction repaired (cost basis $80.07 → $66.78), $122k refunded to cash, stop/target rescaled. Backup at `data/portfolios/max2/.backup-intc-fix/`.

### Other UI / data fixes
- PositionPulse clock: replaced wall-clock time with countdown to market close (4pm ET); fonts bumped (zone widened 130→170px)
- Reverted XNDU + 9 other morning trades in MAX (10 total)
- Backfilled 4/16 + 4/17 history rows across all portfolios (computed from yfinance closes against current positions)
- EXAS/GLDD acquisition cleanup — both delisted; positions closed at fixed acquisition prices ($105 EXAS, $17 GLDD) across all affected portfolios
- Asymmetric-catalyst-hunters scaled 100x ($10k → $1M starting capital + all transaction/position/snapshot rows)
- ActionsTab redesigned: compact rows + click-to-expand details + collapsible Vetoed section

### Diagnosed but NOT fixed (deferred)
- **`day_pnl` zeroed post-market** in `state.py:178-181` — explicitly forces `day_pnl=0` outside 9:30–16:00 ET, even when snapshot has a real value
- **Momentum-fade exit fires on 1-day-held positions** — `_check_momentum_fade` in `risk_layer.py` reads stock's 3-month price tape, ignores entry date. Buying a "bounce" candidate that's already 3 days below 5d SMA → immediate sell signal next analyze. Possible fix: skip if `days_held < 3` AND if fade was already present at entry.
- **Cron still paused** since 2026-04-03 (no daily scans without manual trigger; watchlist scores age out)

---

## Recently Completed (2026-04-11) — Post-Trade Review Feature

New TRADES tab in the Intelligence Brief modal with aggregate stats, filterable closed-trade list, and per-trade detail panel (entry thesis, factor scores, exit analysis, Re-analyze with Claude button). Second entry point from MatrixGrid History tab via deep-link.

### Backend
- **`GET /api/{portfolio_id}/trade-reviews`** — `api/routes/trade_reviews.py`. Joins `transactions.csv` + `post_mortems.csv` into enriched closed-trade objects. FIFO matching for multi-round-trip tickers. Handles missing post-mortem, malformed `trade_rationale` JSON, and None prices gracefully. Parses `what_worked`/`what_failed` JSON arrays into readable joined strings via `_parse_json_list`.
- **`POST /api/{portfolio_id}/trade-reviews/{trade_id}/analyze`** — ephemeral Claude Haiku synthesis. Builds prompt from entry thesis + factor scores + exit reasoning + post-mortem. 60s timeout, error handling returns 503 on failure, safe content extraction over blocks.
- **8 tests** in `tests/test_trade_reviews.py` (TDD): no transactions, open position excluded, basic round-trip, missing post-mortem graceful, multi-ticker FIFO, JSON array parsing, prompt builder content, None-price regression.
- **Router registered** in `api/main.py:46`.

### Frontend
- **`useBriefStore`** in `dashboard/src/lib/store.ts` — Zustand store controlling Intelligence Brief open state globally. `openBrief(tab, tradeId)` / `closeBrief()`. Lets any component deep-link.
- **TopBar.tsx** refactored from local `showBrief` useState to `useBriefStore` selectors (5-call pattern to avoid unrelated re-renders).
- **`TradesTab.tsx`** (~500 lines) — split-panel: 40% left (AggregatePanel with win rate / avg P&L / avg hold / total + BY EXIT and BY REGIME breakdowns, TradeList with filter bar and sortable columns), 60% right (TradeDetail with header, Entry Thesis, FactorBar rows, Exit Analysis with WORKED/FAILED/RECOMMENDATION cards, Re-analyze button). TanStack Query `["trade-reviews", portfolioId]`, 2min staleTime. Keyboard-accessible (role=button, tabIndex, onKeyDown). Sort has deterministic trade_id tiebreaker. Ephemeral re-analyzed state resets on trade change via prevTradeId pattern.
- **IntelligenceBrief/index.tsx** — added 5th "TRADES" tab, `initialTab` + `initialTradeId` props for deep-linking.
- **MatrixGrid HistoryPanel** — clickable CLOSED TRADES section below snapshots (max 50 rows). Calls `openBrief("trades", trade_id)` on click. Keyboard-accessible.

### Architecture
- **Spec:** `docs/superpowers/specs/2026-04-11-post-trade-review-design.md`
- **Plan:** `docs/superpowers/plans/2026-04-11-post-trade-review.md`
- Executed via subagent-driven development with two-stage review (spec + code quality) per task.

### Smoke-tested against real portfolios
- microcap: 47 closed trades
- max: 90 closed trades
- defense-tech: 23 closed trades
- Analyze endpoint: returns ~900-char Claude narrative synthesizing thesis vs outcome

---

## Recently Completed (2026-04-09) — Manual Buy/Sell + Watchlist Cap + Tailscale

### Manual Sell (partial + full)
- `POST /api/{portfolio_id}/sell/{ticker}` now accepts optional `{ "shares": N }` body for partial sells
- New `reduce_position()` function in `portfolio_state.py` handles share reduction
- `SellModal` component (`dashboard/src/components/SellModal.tsx`) — share count input, 25%/50%/75%/ALL presets, live trade preview, confirmation
- SELL button added to MatrixGrid `BottomPanel` inline with STOP/TARGET blocks
- Old inline `SellButton` in `PositionDetail.tsx` replaced with modal trigger

### Manual Buy
- `GET /api/{portfolio_id}/quote/{ticker}` — live price + company info + risk config defaults + auto-suggested share count
- `POST /api/{portfolio_id}/buy` — manual buy at market price, validates cash, records transaction as `MANUAL`
- `BuyModal` component (`dashboard/src/components/BuyModal.tsx`) — ticker input → quote fetch → shares/stop/target editing → trade preview → confirm
- "+ BUY" button added to TopBar (green, between SCAN and ANALYZE)
- `getQuote` and `buyPosition` added to `api.ts`

### Watchlist Cap
- MAX portfolio `max_tickers` bumped from 250 → 500 (matches `total_watchlist_slots`)
- Original 250 cap reasons mostly outdated: score-all architecture, 4hr disk cache, Public.com API, rotating 3-day extended tier all mitigate old constraints

### CLAUDE.md Updates
- Updated sell endpoint docs to reflect partial sell support
- Updated scan timeout notes to reflect current mitigations
- Corrected scan time estimates

### Tailscale Access
- `vite.config.ts` — added `host: true` to server config for LAN/Tailscale access
- Dashboard accessible at `http://100.91.78.110:5173` from phone

---

## Recently Completed (2026-04-08) — AI Allocator Prompt Improvements

- **TRIM authority** added to AI allocator (`scripts/ai_allocator.py`) — Claude can now emit partial sells (`shares < held_quantity`) to lock gains on winners or reduce oversized positions instead of binary exit/hold.
- **Sector overlap data annotations** on every candidate line: `OVERLAP: N held in <sector> (X% of book — HEAVY/MODERATE/LIGHT/none)`. Pure data; concentration *policy* is left to strategy DNA per first-principles drill (data goes in scaffolding, policy in DNA).
- **Reentry guard guidance** + top-level `RECENTLY SOLD FROM THIS PORTFOLIO` block aggregates names sold in last 7d so Claude doesn't immediately re-buy yesterday's stop-outs.
- **MACRO CONTEXT block** — new `scripts/macro_context.py` module fetches 7 macro indicators (WTI, Brent, Gold, DXY, VIX, US 10Y, SPY) + per-position headlines (last 48h, top 2 per ticker) and injects between regime_block and l1_block in the analyze prompt. Caches headlines to `data/news_cache/` (60min TTL), reuses 4hr `yf_session` cache for indicator prices. Failure-mode silent — if news fetch fails, block is omitted; analyze never breaks. Built TDD with 16 unit tests (all passing). Plan: `docs/plans/2026-04-08-macro-context-block.md`.
- Handles current yfinance news schema (`{id, content: {title, provider.displayName, pubDate}}`) with legacy fallback.
- Lesson driving the change: 2026-04-07 MAX rotated 4-deep into energy on the day of a binary Hormuz deadline event with zero macro-headline awareness — block fixes that gap.

---

## Recently Completed (2026-04-06 → 2026-04-07) — Portfolio Creation UX Redesign

Full rewrite of `dashboard/src/components/CreatePortfolioModal.tsx` (354 → ~600 lines).

### Backend
- `api/routes/portfolios.py` — added `POST /portfolios/random-dna` endpoint that calls Claude (haiku) to generate a random structured-brief strategy DNA. ~30s timeout, returns `{"dna": "..."}`.
- `dashboard/src/lib/api.ts` — added `randomDna()` function.

### Screen 1 (Strategy Input)
- Capital input with `$` prefix and live comma formatting
- 🎲 Random button — calls `POST /portfolios/random-dna` for fresh creative strategy each click
- 🔧 Builder toggle — expandable panel with chip selectors for Style/Aggression/Cap/Hold/Concentration/Sectors. "Build DNA" button assembles into structured brief format and fills textarea
- Better loading state on Generate Config: "GScott is analyzing your strategy..."

### Screen 2 (Review & Configure)
- Editable name + universe pill badge
- Universe Filters card showing screener sectors + industries as removable tag badges
- Claude Universe Refinement toggle switch + editable prompt textarea
- Risk & Sizing in 2x3 grid (all 6 fields editable inline: stop loss, take profit, risk/trade, max position, max positions, capital)
- Collapsible Strategy DNA preview
- Removed: ETF badges (dead UI), curated tickers preview

### Light mode (partial)
- Added `data-theme="light"` CSS variable overrides in `dashboard/src/index.css` for both `:root` raw vars and `@theme` Tailwind vars
- Added theme toggle button (☀/☾) in TopBar
- `useUIStore.theme` state with localStorage persistence
- Inline `<script>` in `index.html` sets `data-theme` on first paint to avoid flash
- KNOWN INCOMPLETE: Many MatrixGrid components have hardcoded hex colors (e.g., `#0a0a0b`, `rgba(255,255,255,0.04)`) that don't respond to CSS variable swap. Overview page works in light mode; portfolio detail views look mostly dark even in light mode.

### MatrixGrid status bar relocation
- Moved Waveform + MATRIX::v3.0 + clock from bottom status bar to right side of CONTROLS bar (next to portfolio filter chips) using `marginLeft: auto`

---

## Recently Completed (2026-04-02) — Pipeline Visibility Features

Implemented in 6 task subagent flow with two-stage review per task. All 8 tests passing.

1. **`ai_mode` flag** in every analysis result — `"claude" | "mechanical" | "mechanical_fallback"`. Tracked via module-level `_last_ai_mode` in `ai_allocator.py`, set in 3 paths (success, no-client fallback, exception fallback). Read by `_run_ai_driven_analysis` and added to return dict.

2. **Execution summary** in `execute_approved_actions` return — `{proposed: {buys, sells}, executed: {buys, sells}, dropped: [{ticker, reason}], ai_mode}`. All 6 silent-drop paths now track to `dropped_actions` list with specific reasons.

3. **Post-mortem trade history in Claude prompt** — `get_portfolio_trade_summary(portfolio_id, max_trades=20)` in `post_mortem.py` returns `{total_trades, win_rate_pct, avg_win_pct, avg_loss_pct, avg_hold_days, top_patterns, recent_streak}`. Injected into `_build_allocation_prompt` as `_trade_history_block`. Only shows when ≥5 trades exist.

4. **`data_completeness` (0-6)** in StockScore — each factor function (`score_price_momentum`, `score_earnings_growth`, `score_quality`, `score_volume`, `score_volatility`, `score_value_timing`) now returns `(score, has_real_data)` tuple. `score_stock` sums the booleans. Passed to Claude in candidate prompt as `data={n}/6`.

5. **Dashboard updates** — `dashboard/src/lib/types.ts` got `ai_mode` field on `AnalysisResult` + new `ExecutionSummary` interface. `ActionsTab.tsx` shows AI MODE/FALLBACK badge in summary bar. `MatrixGrid.tsx` shows critical/high warnings strip when active.

6. **Pipeline health endpoint** — `execute_approved_actions` writes `data/pipeline_status/{portfolio_id}.json` after each run. New `GET /api/system/pipeline-health` endpoint reads all status files, returns `{portfolios, anomalies}`. Anomalies detected: mechanical_fallback active, all-buys-dropped.

### Sell Validation Hardening (same session)
- `_validate_allocation` in `ai_allocator.py` now checks `held_tickers` and caps shares to `held_shares_map` for AI sells (prevents phantom sells from Claude hallucinations)
- `execute_approved_actions` filters phantom sells before saving transactions (defense in depth) with `[Guard] Blocked phantom sells` log

### Stop-Loss Architecture Change
- Changed from "Layer 1 auto-executes mechanical sells" to "Layer 1 flags at-risk positions; Claude makes ALL final sell decisions"
- `_build_allocation_prompt`: changed from "LAYER 1 MECHANICAL SELLS (executing regardless)" to "POSITIONS FLAGGED BY RISK ANALYSIS — you decide whether to sell"
- Mechanical fallback only when AI client unavailable

### Post-Mortem Per-Portfolio Fix
- `post_mortem.py:save_post_mortem` now accepts `portfolio_id` and writes to `data/portfolios/{id}/post_mortems.csv`
- Backfilled 202 historical records to correct portfolios via `buy_transaction_id` matching, dropped 159 from deleted portfolios
- `controls.py` sell/close-all paths now build PostMortem objects properly (was passing ticker string)
- `load_post_mortems` and `get_recent_post_mortems` accept `portfolio_id`

### Factor Scores Recording Fix
- `ai_allocator._convert_to_reviewed_actions` was hardcoding `factor_scores={}`. Now passes through `factor_scores_map` from scored candidates so future buys record real factor breakdowns. Existing historical data still has `{}`.

### PTEN Phantom Cash Bug Fix
- Found double-sell bug: both Layer 1 and Claude AI sold the same position simultaneously, crediting cash twice. Fixed by adding dedup filter in `_validate_allocation` (later superseded by stop-loss architecture change). Removed phantom $6,883.88 from MAX portfolio cash.

---

## Recently Completed (2026-04-02) — Screener-Based Universe Migration

Migrated all 25 non-`gov-infra` portfolios from broken `etf_holdings` (top-10-per-ETF) to `yfscreen`-based screener universe.

- All portfolios: `etf_holdings.enabled` → `false`, `screener` block added with appropriate `market_cap_min`, `region: us`
- 6 thematic portfolios get sector/industry filters + `ai_refinement` prompt:
  - `adjacent-supporters-of-ai` — Industrials/Utilities/Energy/Technology sectors, AI infra physical layer prompt
  - `ai-pickaxe-infrastructure` — Industrials/Utilities/Technology/Real Estate, AI infra picks & shovels prompt
  - `boomers` — Healthcare/Real Estate/Consumer Defensive, aging boomer profit prompt
  - `cash-cow-compounders` — Industrials/Financial Services/Consumer Defensive/Utilities, wide-moat cash generators prompt
  - `defense-tech` — Industrials/Technology, autonomous defense systems prompt
  - `tariff-moat-industrials` — Industrials/Basic Materials/Consumer Cyclical, domestic tariff beneficiary prompt
- `diversified-healthcare` — Healthcare sector filter, no ai_refinement
- All remaining portfolios — market cap + region only (broad/all-sector strategies)
- `scripts/migrate_to_screener.py` — migration script (kept for reference)
- 26 files committed: `feat: migrate all portfolios to screener-based universe`

---

## Recently Completed (2026-04-01) — Portfolio Isolation Fixes

### Cross-portfolio watchlist contamination removed
- `scripts/watchlist_manager.py` — removed "Step 5: Supplement with shared universe" block from `update_watchlist()`. Each portfolio's watchlist is now built exclusively from its own universe. `/api/convergent-signals` remains for cross-portfolio visibility.

### Portfolio-specific scoring weights active during discovery
- `scripts/stock_discovery.py` — `StockScorer(config=self.config)` now passed in `_score_all_universe()`. Each portfolio's learned factor weights (from `factor_learning.py`) now apply during discovery scoring, not just at buy-proposal time.

### Tests added (25 total)
- `test_update_watchlist_does_not_inject_cross_portfolio_candidates` — regression guard for isolation
- `test_score_all_uses_portfolio_config_weights` — regression guard for per-portfolio scoring

---

## Recently Completed (2026-04-01) — Score-First Watchlist Architecture

Replaced the 5-gate scan → 60-day decay watchlist with: score every ticker daily → delta-ranked rebuild.

### ScoreStore (new)
- `scripts/score_store.py` — append-only JSONL per portfolio (`data/portfolios/{id}/daily_scores.jsonl`). Records composite + 6 factor scores per ticker per day. Methods: `save_scores()`, `get_latest_scores()`, `get_all_deltas()`, `get_top_by_blended(n, delta_weight=0.3)`, `cleanup(keep_days=30)`.

### stock_discovery.py changes
- `_score_all_universe()` Phase 4 loop now collects `all_scores_for_store` (ALL scored tickers, not just candidates above threshold) and writes to ScoreStore after the loop.
- `run_all_scans()` — removed 500-ticker threshold. Score-all always runs for ALL universe sizes. The 5 scan gate types (momentum_breakouts, oversold_bounces, etc.) are bypassed entirely.

### watchlist_manager.py changes
- `WatchlistEntry` — added `score_delta: float = 0.0` field (backward compatible with old JSONL files).
- `update_watchlist()` rewritten as score-first daily rebuild: (1) remove poor performers → (2) run discovery (score-all) → (3) read ScoreStore top-N by blended rank → (4) rebuild: CORE always + top-N fill → (5) shared universe supplement → (6) sector backfill → (7) balance/enforce → (8) social enrichment. Removed: `mark_stale_tickers()`, `remove_stale_tickers()`, `_remove_zero_score_tickers()` — no more staleness decay.
- First-run safe: falls back to `discovered_stocks` directly if ScoreStore is empty.

### API change
- `api/routes/discovery.py` `get_watchlist()` — adds `score_delta` and `blended` (= score + 0.3*delta) to each candidate. Sorts by `blended` descending.

### Migration (one-time, run complete)
- `scripts/migrate_watchlists.py` (new) — extracted CORE tickers to `core_watchlist.jsonl`, cleared all `watchlist.jsonl` files.
- Result: microcap 41 CORE tickers preserved; 2,003 total entries cleared across 24 portfolios.

### E2E verification
- microcap scan post-migration: score-all mode triggered (338 tickers → 299 survivors → 221 candidates in 67s), ScoreStore saved 222 scores, watchlist rebuilt to 200 entries (41 CORE + 159 SCORE_ALL), `score_delta=0.0` (first run), `blended` fields present in API response.

---

## Recently Completed (2026-04-01) — Universe & Discovery Pipeline Rebuild

### Bug Fixes (post-rebuild, same session)
- `scripts/strategy_generator.py` — Anthropic timeout raised 60s → 300s; `max_tokens` raised 4096 → 8192. 150 tickers with rationale exceeded both limits, causing timeouts and truncated JSON.
- `scripts/stock_discovery.py` — `StockScorer()` takes no `portfolio_id` arg. `_score_all_universe()` was passing it, causing score-all to silently return 0 candidates for every new portfolio.

### Portfolio Genesis (AI-Curated Universe at Creation)
- `scripts/strategy_generator.py` — `suggest_config_for_dna()` now returns `curated_tickers` (50-150 tickers with sector + rationale). `max_tokens` 8192, timeout 300s.
- `scripts/portfolio_registry.py` — `_save_curated_universe()` saves AI-curated tickers to `data/portfolios/{id}/curated_universe.json` at creation time when `ai_config.curated_tickers` is provided.
- `scripts/universe_provider.py` — `_load_curated()` checks portfolio-level `curated_universe.json` first (replaces global curated file for AI-driven portfolios). Extracted `_ingest_curated_dict()` helper.
- `api/routes/portfolios.py` — `ai_config: dict | None` passes `curated_tickers` through to `create_portfolio()` automatically.

### Score-All Mode (Cold-Start Fix for Small Universes)
- `scripts/stock_discovery.py` — `_score_all_universe()` method added: when universe < 500 tickers, bypasses all 5 scan type gates and scores every ticker with the full 6-factor model. Applies `_passes_filters()` (sector/cap/fundamental), populates `market_cap_m` from info dict, logs per-ticker errors.
- Bypass check in `run_all_scans()`: `if len(self.scan_universe) < 500: return self._score_all_universe()`.
- Fixes: new portfolios with ETF-only universes (200-400 tickers) were getting 0-1 candidates because scan gates rejected everything.

### Shared Universe Cache
- `scripts/shared_universe.py` (new) — `SharedScanResult` dataclass + `SharedUniverse` class. Per-portfolio JSON files under `data/shared_scan_cache/` (gitignored). Atomic write (write-to-tmp + rename). Methods: `write_results`, `read_results`, `get_convergent_tickers`, `get_best_score`, `cleanup`.
- `scripts/stock_discovery.py` — `run_all_scans()` and `_score_all_universe()` write results to shared cache after each scan (non-fatal).
- `scripts/watchlist_manager.py` — `update_watchlist()` reads shared cache after local discovery, adds candidates from OTHER portfolios with score >= 35 that aren't already in watchlist. Counts toward `stats["added"]`.

### Cross-Portfolio Convergence API
- `api/routes/discovery.py` — new `GET /api/convergent-signals` endpoint (`min_portfolios: int = Query(default=2, ge=1)`). Returns tickers found independently by N+ portfolios, sorted by portfolio_count desc + best_score desc. NaN-safe via `serialize()`.
- `api/main.py` — registers new `global_router` for non-portfolio-scoped routes.

### Test Coverage
- `scripts/tests/test_strategy_generator.py` — 2 tests
- `scripts/tests/test_portfolio_genesis.py` — 2 tests
- `scripts/tests/test_genesis_integration.py` — 1 API-layer test (TestClient, POST /api/portfolios)
- `scripts/tests/test_score_all.py` — 3 tests
- `scripts/tests/test_shared_universe.py` — 4 tests
- Total: 12 tests, all passing.

---

## Recently Completed (~2026-03-30) — Intelligence Brief + Portfolio Rename + Bug Fixes

### Intelligence Brief (major feature)
- **`api/routes/intelligence.py`** (464 lines) — new route group registered under `/api/{portfolio_id}`. Endpoints: aggregate data (`/intelligence/data`), AI audit brief (`/intelligence/audit`, 10-min cache), portfolio chat (`/intelligence/chat`).
- **`dashboard/src/components/IntelligenceBrief/`** — 8-component modal (2,510 lines total):
  - `index.tsx` — main modal shell (854 lines)
  - `AuditChat.tsx` — AI audit + live chat (453 lines)
  - `FactorIntelligence.tsx` — factor weights, deltas, suggestions (387 lines)
  - `RiskPulse.tsx` — risk scoreboard + warnings (314 lines)
  - `TradeIntelligence.tsx` — trade stats, hold time, most-traded (215 lines)
  - `CompositionPanel.tsx` — sector breakdown, concentration (137 lines)
  - `DnaCard.tsx` — strategy DNA card (147 lines)
  - `HeroRow.tsx` — summary hero row
- TopBar button opens Intelligence Brief for any active portfolio.
- `strategy_health.py` bug fix: `StrategyHealthCalculator` was always loading the default portfolio (missing `portfolio_id` in 3 internal calls). Now correctly scoped per portfolio.
- `get_risk_scoreboard()` now takes `portfolio_id` param (used by intelligence route).

### Portfolio Rename
- `rename_portfolio(portfolio_id, new_name)` in `portfolio_registry.py`
- `PUT /api/portfolios/{portfolio_id}/rename` endpoint
- `CreatePortfolioModal.tsx` — name is now editable before confirming creation (previews slug ID live)

### MatrixGrid — HISTORY Tab
- New `history` tab in MatrixGrid secondary tabs (sky-blue color).
- Accepts `snapshots` + `startingCapital` props, renders equity history.
- Tab badge shows snapshot count.

### ActionsTab — Dedup Fix
- Actions deduplicated by `ticker:action_type` key — richest AI reasoning wins.
- Tab badge count now reflects deduplicated count.

### Universe Provider Fix
- If no core tickers exist after classification, extended tickers are promoted to core (up to `core_max`).
- Fixes ETF-only portfolios that were stuck on `rotating_3day` until 3 scans completed.

### API / Backend
- FD limit raised in `api/main.py` (`RLIMIT_NOFILE → min(4096, hard)`) — prevents "too many open files" during cold scans.
- CORS changed to `allow_origins=["*"]`, `allow_credentials=False` (dev convenience).
- `unified_analysis.py`: `pd.to_datetime(..., format="mixed")` — fixes parse warning on mixed-format date columns.
- `stock_discovery.py`: yfinance logger suppressed to `CRITICAL` — removes duplicate 401/429 noise in API output.

---

## Recently Completed (2026-03-29) — Dashboard UI + New Portfolios

### Dashboard Bug Fixes
- **React hooks violation (OverviewPage)** — `const sorted = useMemo(...)` was declared AFTER `if (isLoading) return`. Caused "Rendered more hooks than during the previous render" crash on every load. Fixed by moving `sorted` above the loading guard.
- **ConstellationMap hover flash** — `portIds` new array every render → `rebuildLayout` invalidated → `canvas.width` cleared canvas. Fixed with `useMemo` on `portIds`.
- **"Overview" ghost tooltip** — Native browser `title="Overview"` on logo button appearing mid-screen. Removed.
- **Matrix cell toggle-close** — Clicking a selected cell again now closes the bottom panel.

### Dashboard UI Improvements
- **GScottLogo** — "Terminal" font 38→62px. Viewbox widened.
- **PositionPulse wired in** — 36px kinetic strip renders in MatrixGrid. Glyphs show `perf%` not `day%` (zeros when market closed).
- **Large treemap cells** (≥150×110px) — show current price, value, shares@avgcost, full-width sparkline, held + SL distance.

### ETF Holdings — New ETFs Added to DEFAULT_ETFS
`VTI`, `IWC`, `PAVE`, `GRID`, `IFRA`, `IGF`, `SOXX`, `SMH`, `XME`, `ITA`, `RSPT`

**Root cause of empty universes on new portfolios**: ETFs specified in portfolio config but absent from DEFAULT_ETFS were silently ignored, leaving 28-ticker universes.

### New Portfolios
| ID | Capital | Strategy |
|----|---------|----------|
| `tariff-moat-industrials` | $100K | Domestic manufacturers with tariff moat |
| `pre-earnings-momentum` | $1M | Pre-earnings momentum, all caps |
| `ai-pickaxe-infrastructure` | $2M | AI infrastructure picks & shovels |

All three: `extended scan_frequency: daily`, `min_score_threshold: {BULL:35, SIDEWAYS:40, BEAR:50}`, `volume_anomalies: true`.

### Capital Adjustment
- `asymmetric-microcap-compounder` — $1,000 → $10,000 (positions were < $250 minimum, getting skipped at execute)

---

## Recently Completed (2026-03-27) — AI-Generated Sell Reasoning + Discovery/Exit Upgrade

- Layer 1 mechanical sells get AI-generated reasoning (not static labels)
- Fixed O(n×m) RSI bug in discovery scanner
- Fixed 52wk high using 3mo data instead of 1y
- Enabled `scan_volume_anomalies` by default
- New `scan_relative_volume_surge` (4x+ volume vs 30d baseline)
- Ported stagnation + liquidity drop exits to active pipeline
- New momentum fade exit (3 closes below 5d SMA)
- Regime weights removed from scoring — flat default_weights + flat threshold

---

## Previously Completed (2026-03-26)

- Cron automation (scan 6:30AM / execute 9:35AM / update 12PM+4:15PM / watchdog)
- Reentry Guard (`scripts/reentry_guard.py`)
- System Logs Page (`/logs` route)
- VCX same-run reentry veto + min_stop_loss_pct floor
- yf.download() 60s timeout
- Public.com cross-validation (>15% divergence → use yfinance)
- ETF holdings global cache (`data/etf_holdings_cache.json`)
- 5 new prompt context blocks sent to Claude at execute time

---

## Open Bugs / Known Issues

- `ALE`, `JBT` delisted — fail price fetch consistently (ignore)
- Stocktwits 403s broadly — social heat won't populate (DISABLE_SOCIAL workaround)
- ~~No tests for `_validate_allocation()` / `_parse_json()` in `ai_allocator.py`~~ ✅ closed 2026-05-19 (T1 added 36 tests)
- `tariff-moat-industrials` finding few candidates — tariff selloff killed momentum signals. Will populate when tape turns.
- `ai-pickaxe-infrastructure` — semis/AI infra crushed in selloff. Same situation.
- `pre-earnings-momentum` — no actual earnings-date awareness in scanner; relies on momentum building pre-earnings. Q1 earnings season starts mid-April.
- **`yfscreen` not installed** → bulk screener path dead; screener-only portfolios (e.g. `gov-infra`) currently scan **0 tickers**, and all fundamentals fall back to per-ticker `.info`. Fixed by Phase 2 P2.1 (install + consume bulk fundamentals). Until then, affected portfolios rely on cached screener results / curated + ETF-fallback universes.

---

## Active Portfolios (16)

| ID | Notes |
|----|-------|
| `microcap` | Small-cap momentum, ^RUT benchmark |
| `adjacent-supporters-of-ai` | AI infra, allcap, AI-driven |
| `boomers` | General momentum allcap |
| `max` | AI-driven allcap, rotating_3day |
| `defense-tech` | Defense tech, AI-driven |
| `cash-cow-compounders` | Cash-printing businesses |
| `asymmetric-catalyst-hunters` | <$300M mktcap violent re-ratings |
| `catalyst-momentum-scalper` | Intraday momentum on catalysts |
| `momentum-scalper` | Technical breakout scalper |
| `asymmetric-microcap-compounder` | $10K capital, max 2 positions |
| `vcx-ai-concentration` | min_stop_loss_pct=-0.35 |
| `microcap-momentum-compounder` | Focused microcap momentum |
| `yolo-degen-momentum` | 2 positions @ 50% each |
| `tariff-moat-industrials` | $100K, daily scan |
| `pre-earnings-momentum` | $1M, daily scan, allcap |
| `ai-pickaxe-infrastructure` | $2M, daily scan, allcap |

---

## Architecture Decisions

- **DISABLE_SOCIAL=true** — always set
- **Scan timing**: 6:30 AM ET
- **ETF holdings cache** global: `data/etf_holdings_cache.json`
- **Regime weights removed** — flat defaults only
- **yf.download() 60s timeout** — thread-based in `yf_session.py`
- **New portfolios** must use `extended scan_frequency: daily` (rotating_3day causes near-empty universes until 3 scans run)
- **ETF DEFAULT_ETFS** — any ETF in portfolio config must also be in DEFAULT_ETFS or holdings silently ignored
- Dashboard API on port 8001

---

## Key Constraints

- Python 3 only
- Paper mode — no real broker
- Never pass `session=` to yfinance
- `react-resizable-panels` v4: `Group`, `Panel`, `Separator`
- Build check: `npx tsc --noEmit 2>&1 | grep -v 'CreatePortfolioModal\|OverviewPage\|PortfolioSettingsModal\|TopBar'`

---

## Pending Features (backlog)

1. Post-trade review — user requested, not yet designed
2. Earnings date awareness — pre-earnings-momentum has no explicit earnings-date filter in scanner
