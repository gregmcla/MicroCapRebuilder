# Largecap Portfolio Fixes Design

**Date:** 2026-02-24

## Problem

Three issues with the largecap portfolio ($1M, broad market large caps):

1. **Analyze does nothing** — analysis runs but returns empty results with no UI feedback, making it look broken
2. **Discovery too narrow** — ETF sources (SPY, IVV, VOO) all overlap on S&P 500; watchlist only has 2 tickers
3. **Trading strategy misconfigured** — parameters copied from microcap preset, inappropriate for $1M large cap

## Changes

### 1. Config Overhaul (`data/portfolios/largecap/config.json`)

| Parameter | Before | After | Rationale |
|-----------|--------|-------|-----------|
| risk_per_trade_pct | 6% | 3% | $30k risk/trade, not $60k |
| max_position_pct | 10% | 8% | Better diversification at $1M |
| max_positions | 999 | 25 | Realistic for $1M |
| default_stop_loss_pct | 5% | 7% | Less whipsaw on large-cap vol |
| default_take_profit_pct | 20% | 25% | Let blue chips run |
| drawdown_threshold_pct | 10% | 7% | Earlier preservation on $1M |
| high_conviction_pct | 12% | 8% | Must stay under max_position |
| medium_conviction_pct | 8% | 6% | Proportional |
| low_conviction_pct | 5% | 4% | Proportional |
| sector_limit_pct | 40% | 30% | Broader diversification |
| top3_limit_pct | 45% | 30% | No concentration risk |
| min_score BEAR | 60 | 50 | Avoid signal drought |
| trailing_stop_trigger | 10% | 12% | More room for large-cap moves |
| trailing_stop_distance | 6% | 7% | Less whipsaw |

### 2. Discovery Universe Expansion

Replaced overlapping ETFs with diverse sources:
- **SPY** — S&P 500 core
- **QQQ** — Nasdaq 100 (tech/growth)
- **DIA** — Dow 30 (blue chips)
- **VTV** — Vanguard Value (value plays)
- **VUG** — Vanguard Growth (growth plays)

Disabled curated universe (microcap-specific). Expanded tiers: core 150, extended 400.

### 3. UI Empty State Feedback

Added "No opportunities found" message to `ActionsTab.tsx` when analysis returns `total_proposed === 0`. Suggests running SCAN first, shows re-analyze button.
