# MicroCapRebuilder — Project State

> **Read this at the start of every session before doing anything else.**
> **Update it at the end of every session.**

---

## Current Phase

**MatrixGrid Dashboard** (Complete as of 2026-03-06)

---

## Recently Completed (this session, 2026-03-06)

### Fixes (pre-social-sentiment)
- `opportunity_layer.py`: `is_initial_deployment` now uses `deployed_pct < target * 0.5` (was `num_positions == 0`) — fixes tiny position sizing on subsequent ANALYZE runs
- `etf_holdings_provider.py`: Added FALLBACK_HOLDINGS for ITA, PPA, HACK, CIBR, BUG, FENY, OIH, PSCT, VGT, SMH, IGV, BOTZ, ROBO, ARKQ, ARKW, WCLD, SKYY, AIQ, KOMP, ARKG, FINX → all portfolios now have sufficient coverage
- `sph/config.json`: Reduced `extended_max` 3000 → 300, added PPA/BUG/OIH/PSCT ETFs
- `ai/config.json`: Removed PLD (Prologis — not an ETF), reduced `extended_max` to 300
- `klop/config.json`, `10k/config.json`: reduced `extended_max` to 300
- `dashboard/src/lib/tradeUtils.ts`: Richer sell explainer narratives (near-stop, near-target, in-between context)

### Social Sentiment Feature (in progress)
- **Task 1 ✅** (`scripts/social_sentiment.py` + `tests/test_social_sentiment.py`): `SocialSentimentProvider`, `SocialSignal`, `classify_heat()`. ApeWisdom + Stocktwits, 2hr disk cache, 10 tests. Commits: `9892f3f`, `9e7eb50`
- **Task 2 ✅** (`scripts/watchlist_manager.py` + `tests/test_watchlist_social.py`): `WatchlistEntry` gets `social_heat`, `social_rank`, `social_bullish_pct`. Enrichment after scan. Commit: `5675b51`
- **Task 3 ✅** (`scripts/enhanced_structures.py`, `opportunity_layer.py`, `unified_analysis.py`): `BuyProposal.social_signal` field, signals flow from unified_analysis → OpportunityLayer → proposals. Commits: `c0a61d0`, `fcbad67`
- **Task 4 ✅** (`scripts/ai_review.py` + `tests/test_ai_review_social.py`): Social heat lines injected into AI review prompt per BUY action. SPIKING gets explicit pump warning. Commits: `e4ae532`, `910bb87`
- **Task 5 🔲** — Dashboard: `social_heat?` fields on `WatchlistCandidate` type + `SocialHeatBadge` component
- **Task 6 🔲** — Full test suite run + smoke test + MEMORY.md update + push

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
