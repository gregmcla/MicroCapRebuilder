# MicroCapRebuilder — Project State

> **Read this at the start of every session before doing anything else.**
> **Update it at the end of every session.**

---

## Current Phase

**Idle — all features complete as of 2026-03-25**

---

## Recently Completed (2026-03-25)

### Alpha Scoring
- `api/routes/state.py`: `_compute_position_alphas()` — per-position financial alpha = `unrealized_pnl_pct - benchmark_return_since_entry_date`
- Uses `cached_download` with portfolio benchmark (^GSPC allcap, ^RUT microcap); gracefully skips on error
- `alpha` field added to `Position` (types.ts), `MatrixPosition` (types.ts), and `positionToMatrix()` (constants.ts)
- MatrixGrid alpha sort: `(b.alpha ?? 0) - (a.alpha ?? 0)`; alpha sizeOf: `Math.max(Math.abs(pos.alpha ?? 0), 0.5)`

### Trade Timestamps
- All transaction dates changed from `date.today().isoformat()` to `datetime.now().strftime("%Y-%m-%dT%H:%M:%S")` in `unified_analysis.py`, `execute_sells.py`, `pick_from_watchlist.py`, `api/routes/controls.py`
- ActivityPanel (MatrixGrid) and ActivityFeed slide-over both show `tx.date.slice(11, 16)` when date includes time

### Market Hours Fix
- `market_open_today` in `state.py` now checks actual ET hours (9:30–16:00) via `zoneinfo.ZoneInfo("America/New_York")` — was weekday-only check, causing stale day P&L to show pre-market
- Fixes the "$-22,259 Today" pre-market display bug

### Null Filter Fix (stock_discovery.py)
- `None * 1e6` was a silent TypeError failing ALL filter candidates when `max_market_cap_m` was null
- Fixed all four numeric filter values with null-safe pattern:
  - `min_price = filters.get("min_price") or 5.0`
  - `max_price = (_max_price_m if _max_price_m is not None else float("inf"))`
  - `min_cap = (_min_cap_m or 0) * 1e6`
  - `max_cap = (_max_cap_m * 1e6) if _max_cap_m is not None else float("inf")`

### Execute 500 Error Fix
- Root cause: `json.dump(result, f, default=str)` serialized ReviewedAction dataclasses as strings; loaded back as strings, crashing `execute_approved_actions` with `'str' object has no attribute 'original'`
- Fix 1: `api/routes/analysis.py` now uses `serialize()` before saving to `.last_analysis.json`
- Fix 2: `unified_analysis.py` `_normalize_reviewed_action()` reconstructs proper SimpleNamespace objects from dicts for both analyze and execute paths

### Defense-Tech Fixes
- `max_market_cap_m` removed (set to null) — was blocking all large-cap defense names (LMT=$100B, RTX=$140B etc.)
- 14 CURATED_CORE names appended to `watchlist.jsonl`: LMT, RTX, NOC, GD, LHX, KTOS, PLTR, AXON, LDOS, SAIC, CACI, BWXT, HEI, TDG
- `strategy_dna` updated with DEPLOYMENT POSTURE section directing Claude to buy dips, not wait for momentum

### Duplicate AI Reasoning Fix
- Root cause: `ai_allocator.py` set both `action.reason` and `reviewed.ai_reasoning` to `buy["reasoning"]` (same text) — stored as both `quant_reason` and `ai_reasoning` in `trade_rationale` JSON
- Fix 1: `ai_allocator.py` now sets `reason="AI allocation"` for buys and sells (short label, not the full Claude text)
- Fix 2: `TradeThesis.tsx` guards: `topLine = _rawTopLine !== rationale.ai_reasoning ? _rawTopLine : ""`
- Visual result: Trade Thesis section shows factor bars + REGIME/AI CONF + AI reasoning once; company description shows below divider

### New Portfolios Added (this session)
4 new AI-driven portfolios created:
- `cash-cow-compounders` — boring cash-printing businesses (waste, railroads, payroll, pest control)
- `asymmetric-catalyst-hunters` — small-float violent re-ratings, market cap < $300M
- `catalyst-momentum-scalper` — intraday momentum on overnight catalyst stocks
- `momentum-scalper` — pure technical breakout scalper, volume confirmation

---

## Previously Completed (2026-03-23)

### Portfolio Setup Redesign — AI-Driven Only
- `CreatePortfolioModal.tsx` rewritten: 954 lines → ~340 lines, 2-step flow (DNA → Claude suggests config → review & create)
- `StrategyReviewCard.tsx` deleted
- Wizard mode, AI Strategy mode, mode switcher all deleted
- New `POST /api/portfolios/suggest-config` endpoint — Opus 4.6 infers name, universe, ETFs, risk params from DNA
- `strategy_generator.py` replaced: `generate_strategy()`, `suggest_etfs_for_dna()`, `GeneratedStrategy` deleted; new `suggest_config_for_dna()`
- 3 old endpoints deleted: `generate-strategy`, `trading-styles`, `sectors`
- Hardened AI-driven creation defaults: `extended_max=3000`, `rotating_3day`, `exchange_listings=false`

### Bug Fixes (2026-03-17)
- Sell actions no longer show $0.00 stop/target in ActionsTab (only shown for buys now)
- AI review sell reasoning enriched with position P&L context instead of generic market commentary
- Watchlist JSONL corrupt line crash fixed — `_load_watchlist()`, `_load_core_watchlist()`, `portfolio_state.py` all skip bad lines

---

## Previously Completed (2026-03-09)

### Fundamental Scoring Overhaul
- New 6-factor model: `price_momentum`, `earnings_growth`, `quality`, `volume`, `volatility`, `value_timing`
- Fundamental data from yfinance `.info` feeds `earnings_growth` and `quality` scores
- Missing data defaults to 50 (neutral) — never penalizes
- Fundamental pre-screen in `_passes_filters()`: negative margins / SPAC / >15% rev decline → reject

---

## Open Bugs / Known Issues

- `ALE`, `JBT` tickers are delisted — fail price fetch consistently (ignore)
- `_review_batch` in `ai_review.py` uses `action.ticker` directly (pre-existing, only works for object actions) — low risk, tracked
- Stocktwits returning 403s across the board — social heat won't populate (external issue)
- New portfolios (cash-cow, asymmetric-catalyst, catalyst-scalper, momentum-scalper) need scans to populate watchlists

---

## Active Portfolios

| ID | Strategy | Notes |
|----|----------|-------|
| `microcap` | Small-cap momentum | ~838 tickers, ^RUT benchmark |
| `adjacent-supporters-of-ai` | AI infrastructure picks-and-shovels | allcap, AI-driven |
| `boomers` | General momentum allcap | Not AI-driven |
| `max` | AI-driven allcap | `extended_max=3000`, `rotating_3day` |
| `defense-tech` | Defense tech / autonomous systems | AI-driven, null market cap cap, 14 curated core names |
| `cash-cow-compounders` | Boring cash-printing businesses | AI-driven, new 2026-03-25 |
| `asymmetric-catalyst-hunters` | Small-float violent re-ratings | AI-driven, new 2026-03-25 |
| `catalyst-momentum-scalper` | Intraday momentum on catalysts | AI-driven, new 2026-03-25 |
| `momentum-scalper` | Pure technical breakout scalper | AI-driven, new 2026-03-25 |

---

## Architecture Decisions

- **Alpha = position_return_pct − benchmark_return_since_entry** — per-position, computed at state load time
- **Social heat = metadata only** — never inflates quant scores, risk overlay only
- `extended_max` capped at 3000 for AI-driven portfolios with `rotating_3day`
- `accept` conviction multiplier = 1.0 (not 0.75) — 0.75 created a dead zone
- yfinance disk cache: `data/yf_cache/` with 4hr TTL (curl_cffi incompatible with requests-cache)
- Dashboard API on port 8001 (conflict avoidance with exitwise project on 8000)
- All portfolio data isolated under `data/portfolios/{id}/`
- `ai_allocator.py` sets `reason="AI allocation"` — never duplicates `ai_reasoning` into `quant_reason`

---

## Key Constraints

- Python 3 only (`python3` not `python`)
- Paper mode — no real broker, all trades are CSV writes
- Never pass `session=` to yfinance — breaks with curl_cffi
- `react-resizable-panels` v4: use `Group`, `Panel`, `Separator` (not old names)
- Sector-specific AI portfolios need CURATED_CORE watchlist entries to seed thesis-aligned names (scan alone won't find large-caps like LMT)

---

## Pending Features (backlog)

1. **Post-trade review** — user requested, not yet designed
2. Populate watchlists for 4 new portfolios via scans
