# CLAUDE.md — MicroCapRebuilder (GScott)

## Rules for AI Assistants

### Session Start (do this before anything else)
1. **Read `PROJECT_STATE.md`** — it has current phase, open bugs, recent completions, and backlog. Don't skip this.
2. Check if the API is running: `curl -s http://localhost:8001/api/health`

### Session End (do this before closing)
1. **Update `PROJECT_STATE.md`** — current phase, what was completed, any new bugs found, backlog changes.
2. **Capture memories** — save any feedback corrections, confirmed approaches, or architectural decisions with a "why" to `~/.claude/projects/-Users-gregmclaughlin/memory/`. See memory types: feedback (corrections + confirmations), project (decisions with motivation), reference (where to find things).
3. **Push to GitHub** if meaningful changes were made — automatically, no need to ask.

### Proactive Memory Capture (mid-session)
Don't wait for session end. Capture immediately when:
- The user corrects my approach → feedback memory
- A significant design/architecture decision is made with a clear reason → project memory
- An unusual approach is confirmed by the user accepting it → feedback memory
- A non-obvious bug is fixed that reveals a recurring pattern → project memory

### Workflow Rules
- **Plan before coding.** For anything beyond a trivial fix, enter plan mode first. Outline the approach, get approval, then implement.
- **Verify before claiming success.** After making changes, run the dev server or relevant script and check output for errors. Do NOT claim something works without proof.
- **Preserve existing functionality.** When rewriting or refactoring, enumerate what currently works and confirm with the user what should be kept. Never silently remove features.
- **Don't deploy unless explicitly asked.** Don't push, deploy, or change scope without explicit approval. "Figure it out" is not explicit approval to push to GitHub.
- **Update this file.** After completing a major feature or phase, update this CLAUDE.md to reflect the current state of the project.
- **Use python3**, not python, on this machine.
- **Always `except Exception as e:`** — never bare `except:`. It hides real bugs.

### Code Conventions
- Python 3 shebang: `#!/usr/bin/env python3`
- Use `pathlib.Path` for all file paths: `Path(__file__).parent.parent / "data"`
- Imports from `schema.py` for consistent column names
- All parameters from `data/portfolios/{id}/config.json` — don't hardcode
- TypeScript for all frontend code (React dashboard)

---

## Project Overview

MicroCapRebuilder (aka **GScott**) is an intelligent, adaptive portfolio trading system. Supports multiple portfolios with different strategies (microcap, allcap, mean reversion, momentum, etc.). Currently in **PAPER mode**.

**Core capabilities:**
- Multi-portfolio management with isolated data per portfolio
- Multi-factor stock scoring (price_momentum, earnings_growth, quality, volume, volatility, value_timing)
- Market regime detection (bull/bear/sideways)
- Automated risk management (stop losses, take profits, position sizing)
- Unified analysis pipeline with AI review (APPROVE/MODIFY/VETO)
- Learning pipeline (factor scores at entry, post-mortems at exit, weight adjustment)
- Risk scoreboard and early warning system
- React dashboard with FastAPI backend ("GScott" co-pilot personality)

---

## Architecture

### 1. Python Backend (`scripts/`)
Core trading logic, analysis, and data management.

**Single source of truth:** `portfolio_state.py`
```python
from portfolio_state import load_portfolio_state, PortfolioState
state = load_portfolio_state(fetch_prices=True, portfolio_id="microcap")
```
All scripts consume `PortfolioState` — no direct CSV reads/writes for trading data.

**Key scripts:**
- `portfolio_state.py` — loads all portfolio data into a single PortfolioState dataclass
- `unified_analysis.py` — ANALYZE → EXECUTE pipeline
- `ai_review.py` — AI review layer (APPROVE/MODIFY/VETO)
- `stock_scorer.py` — 6-factor scoring model
- `stock_discovery.py` — universe scanning and candidate discovery
- `universe_provider.py` — two-tier universe (core + extended), ETF holdings
- `watchlist_manager.py` — per-portfolio watchlist management
- `etf_holdings_provider.py` — ETF holdings provider (23 DEFAULT_ETFS)
- `portfolio_registry.py` — portfolio creation, SECTOR_ETF_MAP, TRADING_STYLES, universe presets
- `strategy_generator.py` — AI strategy generation via Anthropic API
- `ai_allocator.py` — AI-driven allocation (replaces Layers 2-4 for AI-driven portfolios; calls Claude, validates stop/take_profit, returns ReviewedAction)
- `market_regime.py` — bull/bear/sideways detection
- `risk_layer.py` — trailing stops, volatility stops, regime-adjusted stops
- `risk_manager.py` — position sizing, concentration limits
- `risk_scoreboard.py` — overall risk score (5 components)
- `opportunity_layer.py` — buy proposal generation (filters held tickers, uses scorer price_map)
- `composition_layer.py` — portfolio composition and correlation checks
- `execution_sequencer.py` — trade sequencing by priority
- `analytics.py` — Sharpe, drawdown, CAGR, benchmark comparison
- `factor_learning.py` — factor weight adjustment from real trades
- `early_warning.py` — proactive risk alerts
- `strategy_health.py` — A-F grading
- `strategy_pivot.py` — PIVOT recommendations
- `capital_preservation.py` — capital preservation system
- `yf_session.py` — DataFrame-level disk cache for yfinance (4hr TTL, curl_cffi compat)
- `public_quotes.py` — real-time price wrapper around publicdotcom-py SDK; primary price source in execute + load_portfolio_state; falls back to yfinance (`PUBLIC_API_KEY` env var required)
- `schema.py` — column constants and enums
- `execute_sells.py`, `update_positions.py`, `pick_from_watchlist.py` — daily pipeline scripts

### 2. FastAPI API (`api/`)
Thin REST layer. No business logic here.

- `api/main.py` — app, CORS, router registration
- `api/deps.py` — sys.path setup, `serialize()` helper
- `api/routes/portfolios.py` — portfolio management (`/api/portfolios`)
- `api/routes/state.py` — portfolio state (`/api/{portfolio_id}/state`)
- `api/routes/analysis.py` — analyze + execute (`/api/{portfolio_id}/analyze`)
- `api/routes/risk.py` — risk + warnings (`/api/{portfolio_id}/risk`)
- `api/routes/performance.py` — performance + learning (`/api/{portfolio_id}/performance`)
- `api/routes/chat.py` — ~~deleted~~ (chat feature removed 2026-03-10)
- `api/routes/controls.py` — mode toggle, sell, close-all (`/api/{portfolio_id}/...`)
- `api/routes/discovery.py` — scan (`/api/{portfolio_id}/scan`)
- `api/routes/market.py` — market indices + charts (`/api/market/...`)

### 3. React Dashboard (`dashboard/`)
Vite + React 19 + Tailwind v4 + TanStack Query + Zustand.

---

## Directory Structure

```
MicroCapRebuilder/
├── scripts/                        # Python backend (all trading logic)
├── api/                            # FastAPI REST layer
│   ├── main.py
│   ├── deps.py
│   └── routes/                     # One file per route group
├── dashboard/                      # React SPA (Vite + React 19 + Tailwind v4)
│   └── src/
│       ├── App.tsx                 # Resizable panel layout shell
│       ├── components/             # TopBar, PositionsPanel, FocusPane, etc.
│       ├── hooks/                  # usePortfolioState, useRisk, usePerformance
│       └── lib/                    # api.ts, types.ts, store.ts
├── data/
│   ├── portfolios/                 # Per-portfolio data (gitignored CSVs)
│   │   └── {id}/
│   │       ├── config.json         # Portfolio config (tracked in git)
│   │       ├── positions.csv
│   │       ├── transactions.csv
│   │       ├── daily_snapshots.csv
│   │       └── watchlist.jsonl
│   ├── portfolios.json             # Registry of all portfolios
│   └── yf_cache/                   # yfinance disk cache (4hr TTL, gitignored)
├── docs/plans/                     # Design documents and implementation plans
├── run_dashboard.sh                # Launches API (8001) + React dev (5173)
└── run_daily.sh                    # Daily trading pipeline
```

**Active portfolios:** microcap, adjacent-supporters-of-ai, boomers, max, defense-tech (trimmed to 5 as of 2026-03-23)

---

## API Endpoints

All portfolio-scoped routes use `/api/{portfolio_id}/` prefix.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolios` | List all portfolios |
| POST | `/api/portfolios` | Create portfolio |
| DELETE | `/api/portfolios/{id}` | Delete portfolio |
| POST | `/api/portfolios/suggest-config` | AI config suggestion from strategy DNA |
| GET | `/api/portfolios/overview` | Cross-portfolio overview |
| GET | `/api/{portfolio_id}/position/{ticker}/info` | Company name + description (yfinance, 24hr in-memory cache) |
| GET | `/api/{portfolio_id}/state` | Portfolio state (cached prices) |
| GET | `/api/{portfolio_id}/state/refresh` | Portfolio state (live prices) |
| POST | `/api/{portfolio_id}/analyze` | Run unified analysis (dry run) |
| POST | `/api/{portfolio_id}/execute` | Execute approved actions |
| GET | `/api/{portfolio_id}/risk` | Risk scoreboard |
| GET | `/api/{portfolio_id}/warnings` | Early warnings |
| GET | `/api/{portfolio_id}/performance` | Strategy health + analytics |
| GET | `/api/{portfolio_id}/learning` | Factor summary + suggestions |
| POST | `/api/{portfolio_id}/sell/{ticker}` | Manual sell |
| POST | `/api/{portfolio_id}/close-all` | Close all positions |
| GET | `/api/{portfolio_id}/mode` | Paper/live mode |
| POST | `/api/{portfolio_id}/mode/toggle` | Toggle paper/live |
| POST | `/api/{portfolio_id}/scan` | Trigger watchlist discovery scan |
| GET | `/api/{portfolio_id}/scan/status` | Scan status + result |
| POST | `/api/{portfolio_id}/chat` | GScott chat |
| GET | `/api/{portfolio_id}/gscott/insight` | Context-aware rotating insight |
| GET | `/api/market/indices` | Market indices (SPY, QQQ, etc.) |
| GET | `/api/market/chart/{ticker}` | OHLCV chart data |
| GET | `/api/health` | Health check |

---

## React Dashboard

**Launch:** `./run_dashboard.sh` (API on 8001, React on 5173)

**Layout:** Resizable two-panel split via `react-resizable-panels` v4.
- **Left panel** (default 55%): PositionsPanel + PositionDetailInfo (slides in below when position selected)
- **Right panel** (default 45%): FocusPane (tabs: Summary, Actions, Risk, Performance) + GScottStrip

**TopBar:** M GScott (clickable nav) | equity | day P&L | % dep | regime | risk score | UPDATE | SCAN | ANALYZE | CLOSE ALL | PAPER/LIVE

**Position rows:** ticker | price | day P&L ($/%) | overall P&L ($/%) | range dot

**Position detail (split):**
- `PositionDetailChart` — right pane (chart, P&L cards, range selector)
- `PositionDetailInfo` — left pane below positions (compact header, SELL, progress bar, detail grid), `max-h-[40%]`, slideDown animation

**react-resizable-panels v4:** uses `Group`, `Panel`, `Separator` — NOT PanelGroup/PanelResizeHandle.

**Keyboard shortcuts:** A = analyze, E = execute, R = refresh, Escape = close detail

**Overview page (MAP view):** `ConstellationMap.tsx` — canvas physics simulation. Each position = glowing node (size = market value, color = P&L). Nodes cluster by portfolio with faint dashed rings + name labels. Force-directed physics (spring gravity + pairwise repulsion + boundary walls). Hover dims others + shows glassmorphic detail card. Click pins the card. Stars parallax with mouse. `nodeKey = "ticker:portfolioId"` — handles duplicate tickers across portfolios. Design doc: `docs/plans/2026-03-03-neural-constellation-design.md`.

**PerformanceChart upgrades (2026-03-03):**
- Glow 2-3× stronger, echo trails boosted, area fills more opaque, rank strip doubled in size
- CSS radial-gradient vignette overlay burning in from corners
- Dual-zone Y-scale: when one portfolio return > 5% AND > 3× second place, chart splits 50/50 — leader gets top zone with own scale, field gets bottom zone with own scale, glowing separator between
- Outlier detection: `top > 5.0 && top > second * 3.0` — `leaderIdx = 0`, `fieldScale` separate useMemo
- Per-series `ctx.save()`/`ctx.restore()` clipping inside loop — `pts.length < 2` guard must call `ctx.restore()` before `continue`

---

## Trading Flow

### Daily Pipeline (`run_daily.sh`)
```
load_portfolio_state(fetch_prices=True)
    → execute_sells(state)       # Check stop/target triggers
    → pick_from_watchlist(state) # Score candidates, propose buys
    → update_positions(state)    # Update prices, save snapshot
    → generate_graph()           # Performance chart
```

### ANALYZE → EXECUTE (Dashboard)
```
ANALYZE → run_unified_analysis(dry_run=True)
    1. Check stop/target triggers → proposed sells
    2. Score watchlist candidates (filtered: not already held)
    3. AI reviews proposals in batches of 10
    → Returns approved/modified/vetoed with quant scores + reasoning
EXECUTE → execute_approved_actions()
```

### SCAN (Dashboard)
```
SCAN → watchlist_manager.update_watchlist(run_discovery=True)
    → universe_provider: core (daily) + extended (rotating_3day)
    → stock_discovery: score candidates, apply filters
    → Update watchlist.jsonl (add new, remove stale/poor)
    ~30-50s warm cache, ~5-6min cold cache
```

---

## Scoring Model

6 factors with regime-weighted scoring (as of 2026-03-09 overhaul):
- **price_momentum** (0.25): multi-timeframe (5/20/60d) momentum (60%) + RS vs benchmark (40%) + alignment bonus
- **earnings_growth** (0.15): yfinance `.info` — earningsQuarterlyGrowth, revenueGrowth, forward/trailing P/E comparison. Defaults to 50 when data unavailable.
- **quality** (0.15): yfinance `.info` — grossMargins, returnOnEquity, debtToEquity. Defaults to 50 when data unavailable.
- **volume** (0.10): recent vs average volume (liquidity signal)
- **volatility** (0.15): lower volatility = higher score
- **value_timing** (0.20): SMA distance (50%) + RSI sweet-spot (50%), hard filter above RSI 85

Regime weights: BULL favors price_momentum, BEAR favors quality+volatility, SIDEWAYS balanced.
Min score threshold: BULL=40, SIDEWAYS=50, BEAR=60.

**StockScore is a dataclass** — access `.price_momentum_score`, `.earnings_growth_score`, `.quality_score`, `.volume_score`, `.volatility_score`, `.value_timing_score` (not dict keys).

**Weight migration**: `StockScorer._migrate_weight_keys(weights)` auto-converts old key names to new ones — safe to call on any config dict.

**Fundamental pre-screen** (in `_passes_filters()`): rejects negative gross margins, >15% revenue decline, SPACs/blank check companies. Missing data = permissive (skip check).

**AI review**: BUY proposals include a fundamental data block (margins, earnings growth, P/E, D/E, ROE, description snippet) so Claude can evaluate business quality.

**Social sentiment** (scripts/social_sentiment.py): ApeWisdom + Stocktwits → `classify_heat()` returns COLD/WARM/HOT/SPIKING. Watchlist entries enriched after scan. SPIKING triggers pump warning in AI review prompt. Dashboard shows colored heat badges in watchlist candidates list.

---

## Portfolio Configuration

Each portfolio has its own `data/portfolios/{id}/config.json` with:
- `strategy.trading_style`: `mean_reversion` | `momentum` | `balanced` | `defensive`
- `universe.tiers.core.scan_frequency`: `daily` (always scan all core)
- `universe.tiers.extended.scan_frequency`: `rotating_3day` (scan 1/3 of extended per day)
- `scoring.regime_weights`: per-regime factor weights
- `enhanced_trading.layer2.conviction_multipliers`: `acceptable: 1.0` (NOT 0.75 — that was a dead zone bug)

**Universe presets:** `microcap`, `allcap` (no market cap limits), `largecap`

---

## yfinance Cache (`scripts/yf_session.py`)

- **yfinance ≥ 0.2.50 uses curl_cffi** — rejects custom requests-cache sessions
- **Solution:** DataFrame-level pickle cache in `data/yf_cache/` with **4hr TTL**
- Use `from yf_session import cached_download` — never pass `session=` to yf.download()
- `yf.Ticker(ticker).info` must have a per-ticker timeout (5s) to prevent hanging scans
- TTL configurable via `YF_CACHE_TTL_SECONDS` env var

---

## Known Gotchas

- `ALE`, `JBT` tickers appear delisted — fail price fetch consistently
- **Duplicate tickers across portfolios** (e.g., APA in largeboi + new + klop): `ConstellationMap` uses `nodeKey = "ticker:portfolioId"` for hover/click identity — never use ticker alone as a node key. `positions.find()` must match both `ticker` AND `portfolio_id`.
- **day_change "immediate" after buy**: `bought_today` positions use `avg_cost_basis` as baseline. If yfinance cache was stale at analyze time, the recorded buy price differs from fresh prices → shows non-zero day_change on first UPDATE. This is expected behavior, not a bug.
- **Dual-zone canvas clipping**: each series gets its own `ctx.save()`/`ctx.clip()`/`ctx.restore()` in PerformanceChart. Any early `continue` inside the series loop MUST call `ctx.restore()` first or canvas state leaks.
- `stale_alerts` must load from tracker file even when `fetch_prices=False`
- `FactorLearner.get_factor_summary()` is a method, not a module-level function
- `PreservationStatus` is a dataclass — use `.active` not `.get()`
- AI JSON responses need cleaning: strip markdown blocks, find JSON boundaries, remove trailing commas
- `OpportunityLayer` must filter out held tickers before scoring — otherwise only held positions match
- `OpportunityLayer._generate_buy_proposals()` needs `price_map` from scorer results — `state.price_cache` only has held positions, not watchlist candidates
- `fetch_prices_batch` returns 3-tuple: `(prices, failures, prev_closes)` — uses `period="5d"`
- `save_snapshot` must filter out today's row before computing day P&L (avoid zeroing on repeat updates)
- `run_dashboard.sh` uses `wait` not `wait -n` (macOS bash lacks `wait -n`)
- `day_change` in positions CSV is **total position dollar change** (not per-share). Per-share = `day_change / shares`
- **Scan timeout:** cold cache scan can take 5-6 min and crash API from memory pressure. Keep `rotating_3day` on extended tier. 4hr cache TTL reduces cold scan frequency.
- API process can be killed by macOS if scan consumes too much memory — restart with `uvicorn api.main:app --host 0.0.0.0 --port 8001`
- `execute_approved_actions` bug (fixed): must save transactions BEFORE mutating positions
- **NaN in overview JSON**: pandas uses `NaN` for missing floats; `float(NaN) or 0` still returns `NaN` (NaN is truthy). Use `math.isnan()` check. Overview endpoint uses `_f()` helper to sanitize all floats. Any new cross-portfolio float fields must go through the same helper.
- **Stale buy prices**: `execute_approved_actions()` now fetches live prices via `fetch_prices_batch()` at execute time before recording transactions. Corrects cases where yfinance cache had prev-close prices. Stop/target % distances are preserved and rescaled.
- **Company info endpoint**: `GET /api/{portfolio_id}/position/{ticker}/info` — uses `yf.Ticker(t).info` with 5s thread timeout, 24hr in-memory cache. Clicking a ticker opens `CompanyInfoModal` (glassmorphic popup with sector/industry, stats grid, analyst rating, description, website).
- **ErrorBoundary in App.tsx**: wraps the entire body row. Any render crash shows a "Render error / Try again" fallback instead of blanking the whole page. Error message + component stack logged to console. Never remove this.

---

## Learning Pipeline

- Factor scores recorded as JSON on each BUY transaction
- Post-mortems generated on each SELL (`data/portfolios/{id}/post_mortems.csv`)
- `factor_learning.py` correlates entry scores with outcomes, adjusts weights ±5% per cycle
- Minimum 10 completed trades before any adjustment (fast pattern learning at 5)
- No factor below 5% or above 40% weight

---

## Data Schemas

### positions.csv
```
ticker, shares, avg_cost_basis, current_price, market_value,
unrealized_pnl, unrealized_pnl_pct, stop_loss, take_profit, entry_date,
day_change, day_change_pct
```

### transactions.csv
```
transaction_id, date, ticker, action, shares, price, total_value,
stop_loss, take_profit, reason, factor_scores, regime_at_entry
```
Actions: `BUY`, `SELL` | Reasons: `SIGNAL`, `STOP_LOSS`, `TAKE_PROFIT`, `MANUAL`, `MIGRATION`

### daily_snapshots.csv
```
date, cash, positions_value, total_equity, day_pnl, day_pnl_pct, benchmark_value
```

---

## Creative & Brainstorming

When brainstorming or generating creative ideas, start bold and unconventional. Do NOT play it safe on first rounds. The user consistently rejects "too safe", "too clever", or "too elevated" suggestions and wants raw, novel, ambitious ideas.

---

## Debugging Guidelines

When debugging visual/CSS issues, investigate root causes (overlays, z-index, inherited styles) BEFORE making incremental value adjustments. Small tweaks to color values waste rounds when the real problem is structural.

---

## Project State Tracking

A `PROJECT_STATE.md` file lives at the repo root and tracks current phase, completed tasks, open bugs, architecture decisions, and key constraints. **Read it at the start of every session before doing anything else. Update it at the end of every session.**

---

## Files That Are Gitignored
- `data/portfolios/{id}/*.csv`, `*.jsonl` (except config.json — that IS tracked)
- `data/yf_cache/`, `data/yfinance_cache.sqlite`
- `charts/`, `reports/`, `backup/`, `logs/`
- `.venv/`, `__pycache__/`, `node_modules/`, `dashboard/dist/`
