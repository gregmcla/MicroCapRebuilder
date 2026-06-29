# CLAUDE.md — MicroCapRebuilder (GScott)

Adaptive multi-portfolio trading system. Python backend (`scripts/`) + FastAPI (`api/`) + React/Vite dashboard (`dashboard/`). **LIVE mode** (`mode` key in config.json; `paper_trading.enabled` is a legacy field — ignore it). Global rules (session start/end, memory capture, planning, verify, git safety, creative/debugging guidelines) live in `~/.claude/CLAUDE.md` and are NOT repeated here. **Read `PROJECT_STATE.md` first.**

## Run it
- **python3, not python.** API port **8001** (8000 conflicts with another project).
- Dashboard: `./run_dashboard.sh` (API 8001 + Vite 5173). Daily pipeline: `./run_daily.sh`.
- Health: `curl -s http://localhost:8001/api/health`
- After any backend change, restart uvicorn automatically — never ask the user to do it.

## Verify (run before claiming done)
- Full suite: `python3 -m pytest tests/ scripts/tests/` — should be 242+ green.
- **Touching `unified_analysis.py`, `yf_session.py`, `screener_provider.py`, or the `execute_approved_actions` write path? Run `python3 -m pytest tests/integration/ -v` FIRST.** 17 tests guard known production regressions (phantom sells, double-execute race, cash double-count, stale-price filter, atomic rollback). Hermetic, ~4s, all externals mocked.

## Architecture — the load-bearing rules
- **Single source of truth: `portfolio_state.py`.** `load_portfolio_state(fetch_prices=True, portfolio_id=...)` → `PortfolioState`. No direct CSV reads/writes for trading data — everything goes through it.
- **AI makes the calls.** For ai_driven portfolios, `ai_allocator.py` replaces mechanical Layers 2-4 (calls Claude, validates stop/take_profit, returns ReviewedAction). All active portfolios are ai_driven — the mechanical path is effectively dead code.
- Daily pipeline: `load_portfolio_state` → `execute_sells` → `pick_from_watchlist` → `update_positions`. Dashboard: `run_unified_analysis(dry_run=True)` → `execute_approved_actions()`.
- API is a **thin REST layer — no business logic.** One file per route group in `api/routes/`.
- Everything else (every script, the full route table, dashboard component map, data schemas, directory tree) is discoverable in code — read it rather than trusting a stale list here. Live portfolio list: `python3 -c "import json; print(list(json.load(open('data/portfolios.json'))['portfolios']))"`.

## Conventions
- `#!/usr/bin/env python3`; `pathlib.Path` for all paths; import column names from `schema.py` (don't hardcode).
- All strategy params from `data/portfolios/{id}/config.json` — never hardcode.
- `except Exception as e:` — never bare `except:`.
- TypeScript for all dashboard code.

## Data-model gotchas (non-obvious, will bite you)
- `StockScore` is a **dataclass** — `.price_momentum_score` etc., not dict keys. `StockScorer._migrate_weight_keys()` converts old config weight keys; safe on any config dict.
- `PreservationStatus` is a dataclass — `.active`, not `.get()`. `FactorLearner.get_factor_summary()` is a **method**, not a module-level function.
- `day_change` in positions.csv is **total position dollars**, not per-share (per-share = `day_change / shares`).
- `fetch_prices_batch()` returns a **3-tuple** `(prices, failures, prev_closes)`, period `5d`.
- NaN floats are **truthy** — `float(NaN) or 0` returns NaN. Use `math.isnan()`; cross-portfolio float fields go through the overview `_f()` helper.
- AI JSON responses need cleaning: strip markdown fences, find JSON boundaries, drop trailing commas.

## Execution invariants (breaking these corrupts trade data)
- `execute_approved_actions` writes are **atomic** — the whole save block is wrapped in `_atomic_state_writes(portfolio_id)` (snapshots positions/transactions/daily_snapshots, restores all 3 on any exception). Never add a write to those files outside the `with` block.
- **Save transactions BEFORE mutating positions.**
- `execute_approved_actions` fetches **live prices** at execute time (corrects stale yfinance cache); stop/target % distances are rescaled, not lost. Cross-source check (Public.com vs yfinance, 5% tolerance) is mandatory — guards the INTC stale-price incident.
- `max_positions` enforcement is **opt-in** per portfolio (`enforce_max_positions: true`). Without it, Claude's BUY list passes unfiltered. New portfolios get the flag; old ones were never migrated.
- `OpportunityLayer` must filter held tickers before scoring, and needs `price_map` from scorer results (`state.price_cache` only has held positions).
- `save_snapshot` must drop today's existing row before computing day P&L (else repeat updates zero it out).
- `stale_alerts` must load from the tracker file even when `fetch_prices=False`.

## Caching (Fix 19 — all through `scripts/cache_layer.py`)
- **Never add a disk cache without `cache_layer.cache_key()` + `CacheLogger`.** Ad-hoc caches caused multiple silent-staleness bugs.
- Three caches: yfinance bars (pickle, tiered TTL 4h market / 12h overnight via `bars_ttl()`; `sweep_stale_cache()` bounds the dir, content-validates ticker labels), screener (`screener_cache.{hash}.json`, 24h), refinement (`refinement_cache.{hash}.json`, 7d, auto-invalidates with screener). Hash includes inputs → edit inputs = guaranteed miss.
- Manual bust: `POST /api/{portfolio_id}/cache/invalidate?scope=screener|refinement|all`.
- **yfinance footguns:** never pass `session=` to `yf.download()` (curl_cffi, yfinance ≥0.2.50); always read OHLCV via `from yf_session import cached_download` (never `yf.download` directly); `.info` needs a 5s per-ticker timeout or scans hang.

## Scans & perf
- `SCAN` → `watchlist_manager.update_watchlist(run_discovery=True)`. 5 scan types, all on. Warm scan ~12s since the 2026-06-26 overhaul (prewarmed 3mo bars passed into `score_stock` — no per-ticker re-download; scoring parallelized; `.info` cached 30d).
- Remaining slowness is yfinance throttling on cold fetches. `SCAN_CONCURRENCY` (default 1) is a process-wide semaphore so portfolios don't stampede Yahoo.
- API can be OOM-killed during heavy scans — restart: `uvicorn api.main:app --host 0.0.0.0 --port 8001`.

## Worktrees (you now run parallel Claudes)
- **Removing a worktree does NOT stop its uvicorn.** A stale API process from a deleted worktree keeps answering with stale/missing data. `kill` it explicitly (`lsof -p <pid> | grep cwd` to find it) before/after `wt rm`.
- **Git safety:** never `git stash`/`reset --hard`/`checkout` a different ref here — `data/portfolios/{id}/*.csv` and `*.jsonl` are tracked runtime data. Use `git show <sha>:<path>` for baselines.

## Learning pipeline
- Factor scores stored on each BUY; post-mortems on each SELL (`post_mortems.csv`). `factor_learning.py` adjusts weights ±5%/cycle, min 10 completed trades (fast learning at 5). No factor below 5% or above 40%.

## Scoring (constraints only — full model in `stock_scorer.py`)
- 6 regime-weighted factors. Min score threshold: BULL 40 / SIDEWAYS 50 / BEAR 60. Fundamental pre-screen rejects negative gross margins, >15% revenue decline, SPACs; missing data = permissive.

## Dashboard invariants
- **Never remove the `ErrorBoundary` in `App.tsx`** — it catches render crashes instead of blanking the page.
- Duplicate tickers across portfolios are real (e.g. APA in 3) — node/position identity is **`ticker:portfolioId`**, never ticker alone.
- `react-resizable-panels` v4 uses `Group`/`Panel`/`Separator` (not `PanelGroup`/`PanelResizeHandle`).
