# MicroCapRebuilder — Project State

> **Read this at the start of every session before doing anything else.**
> **Update it at the end of every session.**

---

## Current Phase

**Operational — cron automation running daily. 26 active portfolios. Pipeline visibility + screener universe + portfolio creation redesign complete (2026-04-02 → 2026-04-07). Cron PAUSED for market holiday 2026-04-03 — needs to be re-enabled.**

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
- No tests for `_validate_allocation()` / `_parse_json()` in `ai_allocator.py`
- `tariff-moat-industrials` finding few candidates — tariff selloff killed momentum signals. Will populate when tape turns.
- `ai-pickaxe-infrastructure` — semis/AI infra crushed in selloff. Same situation.
- `pre-earnings-momentum` — no actual earnings-date awareness in scanner; relies on momentum building pre-earnings. Q1 earnings season starts mid-April.

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
