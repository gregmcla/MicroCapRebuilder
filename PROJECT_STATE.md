# MicroCapRebuilder — Project State

> **Read this at the start of every session before doing anything else.**
> **Update it at the end of every session.**

---

## Current Phase

**Operational — cron automation running daily. 16 active portfolios. Universe & Discovery Pipeline Rebuild complete + bug fixes (2026-04-01).**

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
