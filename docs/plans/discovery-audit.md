# Stock Discovery Audit
**Branch:** `discovery-and-exits-upgrade`
**Date:** 2026-03-27

---

## Current Architecture

Discovery runs via `WatchlistManager.update_watchlist()` → `discover_stocks(portfolio_id)` → `StockDiscovery.run_all_scans()`.

**Pipeline:**
1. Batch download OHLCV (1y + 3mo periods, 200-ticker chunks, 60s timeout via yf_session)
2. Public.com live price overlay for current close
3. Price/volume pre-filter (min $5, min 200k avg vol or 2x recent spike)
4. Parallel .info fetch for survivors (8 workers, 5s timeout/ticker, 4hr disk cache)
5. Run 4 scans on pre-warmed data
6. Deduplicate by ticker (keep highest score), sort by discovery_score
7. Bucketed sector selection (if sector_weights configured)

**`volume_anomalies` is disabled by default** (`scan_types.volume_anomalies: False`).

---

## Scan-by-Scan Assessment

### Scan 1: `scan_momentum_breakouts`
**Signal:** Within 10% of 52-week high + 20-day momentum >10% + volume ratio >1.3x

**Alpha thesis:** 52-week high breakouts are one of the most well-documented small-cap patterns. Stocks making new highs often continue — institutional accumulation, short covering, and momentum chasing all reinforce the move.

**Implementation quality: MEDIUM**

Issues:
- Uses 3-month price data for the 52-week high calculation (`_analyze_stock` uses 3mo, but the scan itself fetches 1y). The `_analyze_stock` function calculates `high_52wk = close.max()` on a 3mo dataframe — so it's actually a 3-month high, not a 52-week high. This is a **signal mismatch bug**: the scan filters by 52-week proximity (1y data), then the discovery record reports `near_52wk_high_pct` computed from only 3 months of data.
- Volume confirmation is weak: 1.3x 5-day vs 20-day average is a low bar. Real breakouts need 2x+ on the breakout day itself, not just a weekly average.
- No price action confirmation: no check that the breakout candle closed near its high (a breakout that closes in the lower 20% of its range is often a failed breakout).
- No check for prior base formation — buying after a parabolic run vs. after a consolidation base are very different risk profiles.
- Momentum threshold (10% over 20 days) is too coarse for small-caps: a stock can be +10% from a previous crash and still be in a downtrend.

**What's good:** The 52-week high filter itself is solid. The volume ratio escape hatch (recent spike lets through stocks with low 3-month average) is clever and useful for emerging momentum names.

---

### Scan 2: `scan_oversold_bounces`
**Signal:** Above 200-day SMA + RSI recently below 35 and now crossing above + volume pickup

**Alpha thesis:** Mean reversion in uptrending stocks. If the long-term trend is up (above 200 SMA) and the stock pulled back to oversold levels, the pullback is a buying opportunity.

**Implementation quality: POOR**

Issues:
- **Massive performance problem:** `rsi_series = pd.Series([calculate_rsi(close.iloc[:i+1], 14) for i in range(len(close)-5, len(close))])` — this computes RSI from scratch for each of the last 5 bars. Each call processes up to 200+ days of data. With a universe of 500+ stocks, this runs 500 × 5 = 2,500 full RSI computations. Extremely slow.
- **Wrong RSI signal:** Checks if RSI was "recently oversold" in the last 5 observations. Five daily bars is a very short window — a stock could have been oversold 3 days ago, bounced, and be overbought today. Should check a 10-14 day window with a clean cross-back-above pattern.
- **No volume confirmation of the bounce:** The thesis requires "volume pickup on recovery" but the implementation doesn't check volume during the bounce — only the general scan filter's volume minimum.
- **Requires 200 days of data (`len(df) < 200`):** This filters out any stock with less than 8 months of history — catches delisted/relisted stocks and recent IPOs. Good filter, but makes the scan nearly useless in practice for many small-caps that have gaps in yfinance data.
- **The `_analyze_stock` call recalculates RSI independently** — so the RSI used for filtering and the RSI in the discovery record may differ slightly due to re-fetching with 3mo vs 1y data.

**What's good:** The 200-SMA filter is correct. The "was oversold + now recovering" pattern is the right thesis.

---

### Scan 3: `scan_sector_leaders`
**Signal:** Stock outperforming its sector ETF over 20 days, sector ETF showing >5% 20-day momentum

**Alpha thesis:** Sector rotation drives small-cap returns as much as individual stock selection. Finding the leading sector first, then finding the strongest stock within it, is a sound top-down approach.

**Implementation quality: MEDIUM**

Issues:
- **Info cache dependency:** The scan ONLY uses pre-cached info (`self._info_cache.get(ticker)`) and skips any ticker not in the cache. This means it only covers stocks that survived the price/volume pre-filter AND had successful .info fetches. In practice, many small-caps have empty or failed .info fetches — this scan silently misses them.
- **Top 3 sectors only:** Hard-coded to top 3 by 20-day momentum. In strongly rotating markets, this may include only 1-2 genuinely leading sectors, diluting the signal with "least bad" sectors.
- **Outperformance measured at 20-day intervals only:** Using a single 20-day window means a stock that was +30% 3 weeks ago but -10% this week looks like an outperformer. Should use the last 5 and 10-day windows too (multi-timeframe confirmation).
- **No minimum outperformance threshold:** A stock that returned 5.1% vs a sector ETF at 5.0% qualifies as a "sector leader." Need a minimum excess return gap (e.g., >2% outperformance).

**What's good:** The sector ETF momentum gating is smart. Top-down approach is correct. The info-cache-only pattern prevents 500+ sequential .info calls during the scan.

---

### Scan 4: `scan_volume_anomalies`
**Signal:** 3-day average volume >2x the 20-25 day baseline + price up on the day

**Alpha thesis:** Unusual volume with positive price action = institutional accumulation signal. Smart money can't hide large buys — they show up as volume spikes.

**Implementation quality: FAIR — but DISABLED**

**This scan is disabled by default** (`scan_types.volume_anomalies: False`). It should be enabled — volume anomaly detection is one of the higher-signal inputs for small-cap discovery.

Issues:
- The "price up on the day" check (`price_change < 0: continue`) only looks at the last 1-day price change. This misses "up on significant volume but gave back intraday" situations which are actually bullish consolidation.
- 3-day average vs 20-day average is reasonable, but the threshold of 2x is the same for a micro-cap ($100M) as a mid-cap ($2B). Micro-caps regularly see 5-10x volume spikes on real catalysts, so 2x is noise at that level.
- No check for multi-day accumulation pattern (3 consecutive days of above-average volume is more reliable than a single spike).
- Baseline period (`volume.iloc[-25:-5].mean()`) excludes the last 5 days from the baseline — good design to avoid contaminating baseline with the anomaly itself.

**What's good:** Baseline calculation excludes recent spike. The "price up" check correctly distinguishes accumulation from distribution.

---

## Discovery Score Function Issues

`_calculate_discovery_score()` has structural problems:

1. **RSI scoring is backwards for momentum:** Gives maximum points (20) for RSI 45-65 and deducts 15 points for RSI >80. But for `scan_momentum_breakouts`, RSI 75-80 (strong momentum, not yet extended) is actually the ideal zone. The RSI scoring penalizes momentum breakout candidates.

2. **Source bonus is too small:** 10 points bonus for momentum breakout, 5 for volume anomaly. These bonuses barely affect rankings vs the momentum/volume scoring that dominates. They're cosmetic.

3. **52-week high proximity doubles up:** The scan already pre-filters for within 10% of 52wk high, and then the discovery score adds 15 bonus points for being within 5%. Every momentum breakout that passes the scan gets these bonus points — so the bonus is just a uniform lift, not discriminating.

4. **No fundamental quality gate in score:** A financially deteriorating company can score 90+ on pure price momentum. The fundamental pre-filter (`grossMargins < 0` rejects) is the only protection.

---

## What's Missing / What Would Add Real Edge

### For small-caps specifically, these signals have documented edge:

**A. Relative Volume Surge (same-day)**
The current scans measure volume over 3-20 day windows. For small-cap momentum, the current-day volume vs 30-day average is the key signal. A stock trading 5x its 30-day average on a given day is a fundamentally different signal than one that averaged 1.5x over a week.

**B. Multi-timeframe momentum alignment**
The scorer already does this (5/20/60 day momentum), but discovery scans only use 20-day. A stock with positive momentum at all three timeframes (5d > 0, 20d > 0, 60d > 0) is in a confirmed uptrend at all scales — much higher probability trade.

**C. New 52-week highs with volume confirmation (the real breakout signal)**
The current breakout scan checks "within 10% of 52wk high" not "making a new high today." The actual breakout event (stock hitting a new 52-week high on high volume) is the signal. Stocks consolidating near prior highs for weeks, then breaking to new highs, have a well-documented continuation pattern.

**D. Earnings-based momentum (post-earnings drift)**
Post-earnings announcement drift (PEAD) is one of the most durable anomalies in equity markets. A small-cap that beats earnings and gaps up 10%+ has historically continued drifting higher for 20-60 days. The system has no earnings calendar awareness.

**E. Price-relative-to-average (% above moving averages)**
Simple but effective: stocks making new highs while crossing above their 50-day and 200-day SMAs have confirmed trend acceleration. Catching this cross-above moment is better than chasing stocks already 15% above their MAs.

---

## Watchlist Flow Issues

1. **No score decay:** A ticker added to the watchlist keeps its original `discovery_score` forever. A stock discovered 3 weeks ago at score 75 competes equally with one discovered yesterday at score 75. There's no mechanism to age-down stale discoveries.

2. **`_remove_zero_score_tickers` after 7 days** is the only score-based cleanup. Tickers with low but non-zero scores (e.g. 25) stay indefinitely until marked stale (30 days).

3. **CORE tickers never removed regardless of quality:** `_select_by_buckets` always protects CORE entries. ETF seed tickers that are fundamentally broken can sit in the watchlist permanently.

---

*No code changes in this iteration. See exit-audit.md for exit logic findings.*
