# Exchange-Based Universe Coverage — Design

**Date:** 2026-03-05
**Status:** Approved

## Problem

The current universe (~838 tickers) is built from hand-curated lists + ETF fallback holdings of ~40 stocks each. yfinance `funds_data.top_holdings` returns only the top ~10–25 holdings by weight — so IWM (2,000 real stocks) contributes ~25, SPY (500) contributes ~25, etc. Mid, large, and all-cap portfolios are severely underserved.

## Solution

Pull the free public NASDAQ exchange listing files (no API key) to build a complete picture of all ~4,000–5,500 investable US common stocks. Feed these into the extended tier for smallcap/midcap/largecap/allcap portfolios. microcap stays ETF-only (curated list already well-targeted; broader coverage wastes scan cycles on stocks that fail the $50M–$300M cap filter).

## Data Source

NASDAQ publishes two tab-delimited files updated nightly:
- `https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt` — all tickers traded on NASDAQ systems
- `https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt` — NYSE Arca, BATS, etc.

Filters applied at parse time:
- `ETF = "N"` (exclude funds)
- `Test Issue = "N"` (exclude test symbols)
- `Financial Status = "N"` (normal — exclude deficient/delinquent)
- Listing exchange in `[N, Q, A, P]` (NYSE, NASDAQ, AMEX, NYSE Arca)

Result after filtering: ~4,000–5,500 real common stocks.

## Architecture

### New file: `scripts/exchange_universe_provider.py`

```python
class ExchangeUniverseProvider:
    def get_tickers(self) -> List[str]
    def _download_and_parse(self) -> List[str]
    def _is_cache_fresh(self) -> bool  # 7-day TTL
```

- Downloads both NASDAQ files via `urllib.request` (stdlib, no new deps)
- Parses tab-delimited format, applies filters
- Caches result to `data/exchange_universe_cache.json` with timestamp
- 7-day TTL — exchange listings don't change fast
- Falls back to cached data if download fails

### Modified: `scripts/universe_provider.py`

Add `_load_exchange_listings()` method:
- Instantiates `ExchangeUniverseProvider`
- Adds returned tickers to extended tier
- Only called when `universe.sources.exchange_listings.enabled = true` in config

Call it from `_build_universe()` after `_load_etf_holdings()`.

### Modified: `scripts/portfolio_registry.py`

For `smallcap`, `midcap`, `largecap`, `allcap` presets:
- Add `exchange_listings.enabled: true` to the sources config block
- Bump `extended_max` from 1000 → 3000

`microcap` preset: no change.

## Per-Portfolio Impact

| Universe | Before | After | How filtered |
|----------|--------|-------|-------------|
| microcap | ~838 | ~838 | Unchanged — ETF-only |
| smallcap | ~838 | ~3,000 | $300M–$2B market cap filter at scan time |
| midcap | ~838 | ~3,000 | $2B–$10B market cap filter at scan time |
| largecap | ~838 | ~3,000 | $10B+ market cap filter at scan time |
| allcap | ~838 | ~3,000 | $50M+ market cap filter at scan time |

No new filter logic needed — `stock_discovery.py` already applies per-portfolio `discovery_filters` (market cap, volume, price).

## Scan Performance

- `extended_max=3000` + `rotating_3day` = ~1,000 tickers/day in extended batch
- Cold cache: ~15–20 min (up from 5–6 min). Acceptable for background scans.
- Warm cache (4hr TTL on price data): ~3–4 min. No regression on daily re-runs.
- microcap completely unaffected.

## Files Changed

| File | Change |
|------|--------|
| `scripts/exchange_universe_provider.py` | New — download, parse, cache exchange listings |
| `scripts/universe_provider.py` | Add `_load_exchange_listings()`, integrate into `_build_universe()` |
| `scripts/portfolio_registry.py` | Enable exchange listings + `extended_max: 3000` for smallcap/midcap/largecap/allcap |

No changes to `stock_discovery.py`, `etf_holdings_provider.py`, API routes, or dashboard.
