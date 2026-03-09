# MicroCapRebuilder — Project State

> **Read this at the start of every session before doing anything else.**
> **Update it at the end of every session.**

---

## Current Phase

**Idle — all features complete as of 2026-03-09**

---

## Recently Completed (2026-03-09)

### Fundamental Scoring Overhaul (commits: `a0f2791`, `66d06ea`)
- New 6-factor model: `price_momentum`, `earnings_growth`, `quality`, `volume`, `volatility`, `value_timing`
- Fundamental data from yfinance `.info` feeds `earnings_growth` and `quality` scores
- Missing data defaults to 50 (neutral) — never penalizes
- `prewarm_info_for_tickers()` pre-fetches info in parallel before scoring
- Fundamental pre-screen in `_passes_filters()`: negative margins / SPAC / >15% rev decline → reject
- `_migrate_weight_keys()` auto-converts old portfolio configs
- AI review prompt includes fundamental data block for BUY proposals
- All active portfolio configs updated; backward compat in factor_learning for old transactions

### Social Sentiment Feature (commits: `9892f3f` through `910bb87`)
- **Task 1 ✅** `scripts/social_sentiment.py`: ApeWisdom + Stocktwits, 2hr cache, `classify_heat()`
- **Task 2 ✅** `scripts/watchlist_manager.py`: `WatchlistEntry` gets `social_heat/rank/bullish_pct`
- **Task 3 ✅** `scripts/enhanced_structures.py`, `opportunity_layer.py`, `unified_analysis.py`: social signals flow to proposals
- **Task 4 ✅** `scripts/ai_review.py`: SPIKING = pump warning in prompt
- **Task 5 ✅** `dashboard/src/components/ActionsTab.tsx`: `SocialHeatBadge` + `WatchlistCandidate` social fields
- **Task 6 ✅** 40/40 tests passing

---

## Open Bugs / Known Issues

- `ALE`, `JBT` tickers are delisted — fail price fetch consistently (ignore)
- AWR price glitch happened once (yfinance returned stale price) — monitor
- Social enrichment in `update_watchlist()` adds 10–30 API calls to scan time (Stocktwits per-ticker) — acceptable for now, but watch for timeouts on large watchlists
- `_review_batch` in `ai_review.py` still uses `action.ticker` directly (pre-existing, only works for object actions, not dicts) — low risk since pipeline uses objects, but tracked

---

## Active Portfolios

| ID | Strategy | Notes |
|----|----------|-------|
| `microcap` | Small-cap momentum | 150 watchlist tickers |
| `ai` | AI & data centers aggressive | 8 sectors, 19 ETFs |
| `sph` | Geopolitical defense/energy | 3 sectors, 13 ETFs |
| `new` | General momentum | 20 watchlist tickers |
| `largeboi` | Large-cap | ETFs: SPY, QQQ, etc. |

---

## Architecture Decisions

- **Social heat = metadata only** — never inflates quant scores, risk overlay only
- `extended_max` capped at 300 for sector-filtered portfolios — prevents scan timeout
- `is_initial_deployment` threshold = `deployed_pct < initial_deployment_target_pct * 0.5`
- `accept` conviction multiplier = 1.0 (not 0.75) — 0.75 created a dead zone
- yfinance disk cache: `data/yf_cache/` with 4hr TTL (curl_cffi incompatible with requests-cache)
- Dashboard API on port 8001 (conflict avoidance with exitwise project on 8000)
- All portfolio data isolated under `data/portfolios/{id}/`
- `TYPE_CHECKING` guard in `enhanced_structures.py` for `SocialSignal` import

---

## Key Constraints

- Python 3 only (`python3` not `python`)
- No API keys required for social sentiment (ApeWisdom free, Stocktwits public)
- Paper mode — no real broker, all trades are CSV writes
- Never pass `session=` to yfinance — breaks with curl_cffi
- `react-resizable-panels` v4: use `Group`, `Panel`, `Separator` (not old names)
- Stocktwits rate limit: ~200 req/hr, ST_DELAY=0.4s between calls

---

## Pending Features (backlog)

1. **Post-trade review** — user requested, not yet designed
2. **Overview dashboard Map** — user wants constellation map replaced or significantly improved
3. Social sentiment Task 5 + 6 (in progress this session)
