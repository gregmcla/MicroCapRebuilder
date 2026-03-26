# MicroCapRebuilder — Project State

> **Read this at the start of every session before doing anything else.**
> **Update it at the end of every session.**

---

## Current Phase

**Operational — cron automation running daily as of 2026-03-26**

---

## Recently Completed (2026-03-26) — Reentry Guard

### Reentry Guard
- **`scripts/reentry_guard.py`** (new) — `get_reentry_context()` + `_format_reentry_block()`. Zero trading-module imports. Reads `transactions.csv`, finds most recent SELL within configurable lookback window, computes factor delta from most recent BUY entry scores vs current scores.
- **Configurable stop-loss cooldown** — hardcoded `timedelta(days=7)` in `opportunity_layer.py` now reads `stop_loss_cooldown_days` from `config["enhanced_trading"]["reentry_guard"]`
- **Mechanical path injection** — `OpportunityLayer` attaches `reentry_context` to each `BuyProposal`; `unified_analysis.py` forwards it to `ProposedAction`; `ai_review.py` injects formatted block into prompt for BUY actions
- **AI-driven path injection** — `_run_ai_driven_analysis()` in `unified_analysis.py` calls `get_reentry_context()` in the `scored_candidates` loop; `ai_allocator.py` injects block in both `full_watchlist` and standard rendering branches
- **DNA-driven config for new portfolios** — `strategy_generator.py` extended to infer `reentry_guard` values from portfolio DNA; `portfolio_registry.py` applies them at creation time
- **Per-portfolio config** under `enhanced_trading.reentry_guard`: `enabled`, `stop_loss_cooldown_days` (default 7), `lookback_days` (default 30), `meaningful_change_threshold_pts` (default 10)
- 18 tests in `tests/test_reentry_guard.py` all passing
- Existing portfolios use defaults silently — no config migration needed

---

## Recently Completed (2026-03-26) — System Logs Page

### System Logs Page (`/logs` route)
- New `LOGS` button in TopBar (between VIX/regime area and CLOSE ALL) — toggles back to overview on re-click
- `LogsPage.tsx` — 3 sections: Today's Briefing (Claude narrative), Pipeline Grid (14-day), Event Timeline (collapsible per day)
- `api/routes/system.py` — `GET /api/system/logs` (30-day summaries) + `GET /api/system/narrative` (Claude daily briefing, 10-min cache, `?regenerate=true` bypass)
- `scripts/log_parser.py` — parses `cron/logs/` files: scan/execute (regex summary line), update (line counting), watchdog (restart events), + trade counts from `transactions.csv`
- 10 tests in `tests/test_log_parser.py` all passing
- All portfolio hooks (`usePortfolioState`, `useRisk`, `usePerformance`) gated to skip when `activePortfolioId === "logs"`

---

## Previously Completed (2026-03-26)

### Prompt Context Enrichment
5 new context blocks now sent to Claude during the execute/allocate phase:
- **PORTFOLIO PERFORMANCE** — win rate, avg win/loss, benchmark comparison (from `analytics.py`)
- **ACTIVE ALERTS** — early warning alerts on held positions forwarded from `early_warning.py`
- **FACTOR INTELLIGENCE** — which factors have been most predictive (from `factor_learning.py`)
- **Position age** — days held per position injected into prompt extras
- **Cash idle time** — how long uninvested cash has been sitting
- Built in `_run_ai_driven_analysis()` via `prompt_extras` dict → `_build_allocation_prompt()`

### FactorLearner Date Parsing Fix
- `pd.to_datetime(df["date"])` was crashing on mixed formats (`2026-03-25` vs `2026-03-25T16:07:12`)
- Fix: `format="mixed"` parameter in `factor_learning.py`

### DISABLE_SOCIAL Env Var
- Added guard in `unified_analysis.py` and `watchlist_manager.py`: skip social enrichment if `DISABLE_SOCIAL` is set
- Baked into `run_dashboard.sh`: `DISABLE_SOCIAL=true uvicorn ...`
- All cron scripts export `DISABLE_SOCIAL=true`
- Reason: Stocktwits 403 errors + 10–30 extra API calls per scan → timeout

### Cron Automation
- 4 scripts in `cron/`: `scan.sh`, `execute.sh`, `update.sh`, `api_watchdog.sh`
- Crontab installed with 6 entries:
  - 6:30 AM ET Mon–Fri: `scan.sh` (pre-market watchlist refresh)
  - 9:35 AM ET Mon–Fri: `execute.sh` (AI analyze + execute all portfolios)
  - 12:00 PM ET Mon–Fri: `update.sh` (mid-day P&L)
  - 4:15 PM ET Mon–Fri: `update.sh` (post-close snapshot + factor learning)
  - Every 15 min: `api_watchdog.sh` (restart API if down)
  - Sunday midnight: log cleanup (delete logs > 30 days)
- Tests: `tests/test_cron_scripts.py` — 6 tests all passing
- Logs: `cron/logs/` (gitignored)

### Watchlist Fixes
- microcap `max_tickers` lowered 300→200
- `_remove_zero_score_tickers()` added — grace-period cleanup for stale zero-score tickers
- Zero-score ETF seeds demoted CORE→ETF_HOLDINGS (no longer protected from removal)
- Stale window shortened 60→30 days

### Public.com Cross-Validation
- UPDATE now always fetches both public.com AND yfinance
- Divergence >15% → use yfinance close, log override
- Fixes stale OTC prices (VCX was showing $459 vs actual $380) and `day_change=$0` bug

### ETF Holdings Cache
- Moved from per-portfolio to single global `data/etf_holdings_cache.json`

### New Portfolios (2026-03-26)
- `asymmetric-microcap-compounder` — microcap, AI-driven, $1K→$10K, max 2 positions, 45% risk/trade
- `vcx-ai-concentration` — TBD strategy DNA, needs configuration

---

## Previously Completed (2026-03-25)

- Alpha scoring per position (`unrealized_pnl_pct − benchmark_return_since_entry`)
- Trade timestamps (ISO datetime, not date-only)
- Market hours ET fix (pre-market $0 day P&L bug)
- Null filter crash fix (`max_market_cap_m: null` → `float("inf")`)
- Execute 500 error fix (dataclass serialization via `serialize()` + `_normalize_reviewed_action()`)
- Duplicate AI reasoning fix in DetailCard
- 4 new portfolios: cash-cow-compounders, asymmetric-catalyst-hunters, catalyst-momentum-scalper, momentum-scalper
- CSV writes atomic (`.tmp` + `Path.replace()`)
- `_last_analysis` persisted to disk (survives API restarts)

---

## Previously Completed (2026-03-23)

- Portfolio setup redesign — AI-driven-only 2-step creation modal
- `suggest_config_for_dna()` in `strategy_generator.py`
- Hardened AI-driven creation defaults

---

## Open Bugs / Known Issues

- `ALE`, `JBT` tickers delisted — fail price fetch consistently (ignore)
- `vcx-ai-concentration` — needs strategy DNA configured before it will scan/execute properly
- New portfolios (asymmetric-microcap-compounder, vcx-ai-concentration) need initial scans to populate watchlists
- Stocktwits returning 403s broadly — social heat won't populate (external issue, DISABLE_SOCIAL workaround in place)
- No tests for `_validate_allocation()` / `_parse_json()` in `ai_allocator.py`
- `layer1_output` param unused in `_run_ai_driven_analysis()`

---

## Active Portfolios

| ID | Strategy | Notes |
|----|----------|-------|
| `microcap` | Small-cap momentum | ~838 tickers, ^RUT benchmark, max 200 watchlist |
| `adjacent-supporters-of-ai` | AI infrastructure picks-and-shovels | allcap, AI-driven |
| `boomers` | General momentum allcap | Not AI-driven |
| `max` | AI-driven allcap | `extended_max=3000`, `rotating_3day` |
| `defense-tech` | Defense tech / autonomous systems | AI-driven, null market cap cap, 14 curated core names |
| `cash-cow-compounders` | Boring cash-printing businesses | AI-driven |
| `asymmetric-catalyst-hunters` | Small-float violent re-ratings | AI-driven, <$300M mktcap |
| `catalyst-momentum-scalper` | Intraday momentum on catalysts | AI-driven |
| `momentum-scalper` | Pure technical breakout scalper | AI-driven |
| `asymmetric-microcap-compounder` | $1K→$10K microcap compounder | AI-driven, max 2 positions |
| `vcx-ai-concentration` | TBD | Needs DNA configured |

---

## Architecture Decisions

- **Alpha = position_return_pct − benchmark_return_since_entry** — per-position, computed at state load
- **DISABLE_SOCIAL=true** — always set; social enrichment too unreliable/slow for production use
- **Scan timing**: 6:30 AM (not 7:30 AM) — needs 3-hour buffer before 9:35 AM execute for cold cache worst case
- **Watchdog health check**: substring match `[[ "$HEALTH" == *'"status":"ok"'* ]]` — more robust than exact string match
- `extended_max` capped at 3000 for AI-driven portfolios with `rotating_3day`
- `accept` conviction multiplier = 1.0 (not 0.75 — 0.75 creates a dead zone)
- Dashboard API on port 8001 (conflict avoidance with exitwise on 8000)
- ETF holdings cache is global: `data/etf_holdings_cache.json` (not per-portfolio)

---

## Key Constraints

- Python 3 only (`python3` not `python`)
- Paper mode — no real broker, all trades are CSV writes
- Never pass `session=` to yfinance — breaks with curl_cffi
- `react-resizable-panels` v4: use `Group`, `Panel`, `Separator`
- Sector-specific AI portfolios need CURATED_CORE watchlist entries (scan alone won't find large-caps)

---

## Pending Features (backlog)

1. **Post-trade review** — user requested, not yet designed
2. Configure strategy DNA for `vcx-ai-concentration`
3. Initial scans for `asymmetric-microcap-compounder` and `vcx-ai-concentration`
4. **Per-portfolio `reentry_guard` config** — manually add `enhanced_trading.reentry_guard` block to each existing portfolio's `config.json` per the suggested values table in `docs/superpowers/specs/2026-03-26-reentry-guard-design.md`
