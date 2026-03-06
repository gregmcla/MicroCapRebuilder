# Session Context — 2026-03-06

## What Was Done This Session

### 1. Trailing Stop High-Watermark Fix
- **Problem**: Trailing stop used `current_price` as anchor — a stock that peaked at $343 and fell to $311 showed stop at $286 instead of $315
- **Fix**: Added `price_high` column to positions.csv (initialized to entry price, updated to `max(current, existing_high)` on every price refresh)
- `scripts/portfolio_state.py`: `_update_positions_with_prices()` + `update_position()`
- `scripts/risk_layer.py`: extracts `price_high` from position row, passes to `_calculate_trailing_stop()` which now trails from historical high
- Commit: `b7642be`

### 2. Micro-Buy Floor Fix
- **Problem**: AI MODIFY decisions could set shares to 1 (e.g. DAWN @ $12.73 = $12.73 total). Also cash exhaustion in opportunity layer left dregs for low-ranked candidates.
- **Fix**: Per-proposal minimum notional floor = `max(5 shares, $250)` applied in:
  - `scripts/opportunity_layer.py` (new-buy and rotation-swap paths)
  - `scripts/unified_analysis.py` (filter modified BUY proposals before dashboard display + reject at execute time)
- Commit: `728cdca`

### 3. CIVI Removed (Delisted)
- Removed from `scripts/etf_holdings_provider.py` fallback lists (IWM, VB)
- Commit: `728cdca`

### 4. Exchange Universe Coverage
- **Problem**: ETF fallback lists only had ~40 tickers each; yfinance only returns top ~25 holdings. ~838 total tickers, too narrow for mid/large/allcap portfolios.
- **Solution**: New `scripts/exchange_universe_provider.py` downloads NASDAQ/NYSE listing files (~5,900 real common stocks), 7-day cache at `data/exchange_universe_cache.json`
- `scripts/universe_provider.py`: added `exchange_listings_enabled` toggle + `_load_exchange_listings()` method
- `scripts/portfolio_registry.py`: smallcap/midcap/largecap/allcap presets get `exchange_listings_enabled: true` + `extended_max: 3000`
- `data/portfolios/ai/config.json`, `largeboi/config.json`, `new/config.json`: manually enabled exchange listings + extended_max=3000
- microcap unchanged (838 tickers, ETF-only)
- largeboi extended tier changed from `daily` → `rotating_3day` (was timing out at 15min cold scan)
- Commits: `ca5f791`, `638f51e`, `5c939f0`, `f030050`, `edd9e3e`
- Verified: largeboi scan completed in 2m39s, added 65 new candidates, 150 active watchlist

---

## Next: Sector-Bucketed Watchlist (BRAINSTORM NEEDED)

### Problem
Current watchlist is a flat score-sorted list capped at N. Portfolios targeting specific sectors end up with whatever scores highest globally — tech dominates when tech runs hot, regardless of portfolio intent.

### Proposed Design Direction
Replace flat `max_watchlist_size` with sector-bucketed filling:
- Each portfolio config defines `watchlist.slots_per_sector` (default) + optional per-sector overrides
- Discovery fills sector buckets: top M candidates per target sector
- `max_watchlist` becomes derived: `len(target_sectors) × slots_per_sector`
- Watchlist reflects the portfolio's actual sector intent

### What Needs Brainstorming
1. Config schema for slots_per_sector + overrides
2. How discovery fills buckets (replacement logic for existing flat sort)
3. What happens if a sector has fewer qualifying stocks than its slot allocation
4. How this interacts with `sector_filter` in config
5. Preset defaults per universe type (microcap vs largecap have different sector dynamics)
6. How rotation/swap proposals in opportunity_layer use sector buckets
7. Whether the `sector_balanced` trim logic in discovery gets replaced or kept

### Files That Will Change
- `data/portfolios/{id}/config.json` — new `watchlist` section
- `scripts/stock_discovery.py` — core watchlist filling logic
- `scripts/portfolio_registry.py` — preset defaults for slots_per_sector
- Possibly `scripts/opportunity_layer.py` — sector-aware rotation proposals
