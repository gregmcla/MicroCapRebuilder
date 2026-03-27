# Discovery & Exit Improvements — Implementation Plan
**Branch:** `discovery-and-exits-upgrade`
**Date:** 2026-03-27

---

## Discovery Improvements

### D1. Fix `scan_oversold_bounces` Performance Bug (HIGH PRIORITY)
**Problem:** O(n×m) RSI computation — 2,500 full RSI calculations per scan cycle (500 stocks × 5 bars).

**Fix:** Use a vectorized RSI calculation. Compute the full RSI series once, then read the last N values.

```python
# BEFORE (broken):
rsi_series = pd.Series([calculate_rsi(close.iloc[:i+1], 14) for i in range(len(close)-5, len(close))])

# AFTER (vectorized):
def _compute_rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period-1, adjust=False).mean()
    avg_loss = loss.ewm(com=period-1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('inf'))
    return 100 - (100 / (1 + rs))

rsi_series = _compute_rsi_series(close).iloc[-14:]  # last 14 bars, not 5
```

**Change the signal window from 5 bars to 14 bars** — 5 bars is too narrow to catch a clean oversold cross.

**Add volume confirmation of the bounce:** volume in the last 3 days > 1.5x the 20-day average (the stock needs participation as it recovers, not just drifting up on thin air).

**yfinance data needed:** None new — already uses 1y download.

**Why it has edge:** Mean reversion in uptrending stocks is a documented pattern. The fix makes the signal actually fire for the right reason (clean RSI cross-above with participation), not just "RSI was below 35 in the last 5 days."

---

### D2. Enable `scan_volume_anomalies` (HIGH PRIORITY)
**Problem:** Disabled by default in config despite being a high-signal scanner.

**Fix:** Enable in `data/portfolios/*/config.json` where `scan_types.volume_anomalies` is `false`.

**Also fix the single-day price check:** The current `price_change < 0: continue` rejects stocks that had up-volume but gave back intraday gains — which is actually bullish consolidation. Replace with:
```python
# Require positive price over the 3-day window, not just last 1 day
price_3d_change = (close.iloc[-1] - close.iloc[-4]) / close.iloc[-4]
if price_3d_change < 0:
    continue
```

**yfinance data needed:** Already downloaded (OHLCV 1y/3mo).

**Why it has edge:** Unusual volume with positive price = institutional accumulation signal. This is one of the most reliable small-cap signals and is currently being ignored.

---

### D3. Add Relative Volume Surge Scan (NEW SCAN)
**Signal:** Current-day volume ≥ 4x the 30-day average volume, price up ≥ 2% on the day

**Implementation:**
```python
def scan_relative_volume_surge(self, tickers: list[str]) -> list[DiscoveryResult]:
    results = []
    for ticker in tickers:
        df = self._get_ohlcv(ticker, period="3mo")
        if df is None or len(df) < 31:
            continue
        close = df["Close"]
        volume = df["Volume"]

        avg_vol_30d = volume.iloc[-31:-1].mean()  # exclude today from baseline
        current_vol = volume.iloc[-1]
        current_price = close.iloc[-1]
        prev_price = close.iloc[-2]
        price_change_pct = (current_price - prev_price) / prev_price * 100

        if avg_vol_30d <= 0:
            continue
        rvol = current_vol / avg_vol_30d

        if rvol >= 4.0 and price_change_pct >= 2.0:
            score = min(100, 50 + int(rvol * 5) + int(price_change_pct * 2))
            results.append(DiscoveryResult(
                ticker=ticker,
                scan_type="relative_volume_surge",
                discovery_score=score,
                signal_data={
                    "rvol": round(rvol, 1),
                    "price_change_pct": round(price_change_pct, 2),
                    "avg_vol_30d": int(avg_vol_30d),
                    "current_vol": int(current_vol),
                }
            ))
    return results
```

**yfinance data needed:** Already downloaded (3mo OHLCV is available from existing batch download).

**Why it has edge:** Same-day relative volume is the single most reliable signal that something important is happening NOW. A stock trading 4x normal volume on a 2%+ up day has institutional sponsorship. The 30-day baseline correctly excludes today from the average (no contamination).

---

### D4. Fix `scan_momentum_breakouts` 52-Week High Mismatch Bug (MEDIUM PRIORITY)
**Problem:** `_analyze_stock` computes `high_52wk = close.max()` on a 3-month dataframe — so it's actually a 3-month high. The scan pre-filters on 1y data but reports a misleading metric.

**Fix:** Pass the 1y close data to `_analyze_stock`, or compute `near_52wk_high_pct` from the 1y data directly in the scan before calling `_analyze_stock`.

**Also tighten volume threshold:** Change from 1.3x to 1.8x 5-day vs 20-day average. Real breakouts need meaningful volume expansion.

**yfinance data needed:** 1y data already downloaded.

---

### D5. Add Multi-Timeframe Momentum Confirmation to Discovery Score (MEDIUM PRIORITY)
**Problem:** Discovery scans use 20-day momentum only. A stock can have positive 20-day but negative 5-day and 60-day momentum — it's not in a confirmed trend.

**Fix:** Add a multi-timeframe alignment bonus to `_calculate_discovery_score()`:
```python
# MTF alignment: bonus if 5d, 20d, and 60d all positive
if momentum_5d > 0 and momentum_20d > 0 and momentum_60d > 0:
    score += 10  # confirmed uptrend at all scales
elif momentum_5d > 0 and momentum_20d > 0:
    score += 5   # short-term aligned
```

**yfinance data needed:** Already computed in `_analyze_stock`.

---

## Exit Improvements

### E1. Port Stagnation Exit to Active Pipeline (CRITICAL)
**Problem:** Stagnation detection only exists in `execute_sells.py` (legacy). The active pipeline (`risk_layer.py`) has no time-based exits.

**Implementation:** Add a `check_stagnation` method to `RiskLayer.process()`:

```python
def _check_stagnation(self, pos: pd.Series, current_price: float) -> Optional[SellProposal]:
    """Exit positions held >N days with flat P&L (zombie capital)."""
    stagnation_days = self.layer1_config.get("stagnation_days", 45)
    stagnation_window_pct = self.layer1_config.get("stagnation_pnl_window_pct", 5.0)

    raw_entry = pos.get("entry_date")
    if not raw_entry or pd.isna(raw_entry):
        return None

    from datetime import date, datetime
    if isinstance(raw_entry, str):
        entry_date = datetime.strptime(raw_entry[:10], "%Y-%m-%d").date()
    elif hasattr(raw_entry, "date"):
        entry_date = raw_entry.date()
    else:
        entry_date = raw_entry

    days_held = (date.today() - entry_date).days
    if days_held <= stagnation_days:
        return None

    avg_cost = float(pos.get("avg_cost_basis", 0) or 0)
    if avg_cost <= 0:
        return None

    pnl_pct = (current_price - avg_cost) / avg_cost * 100
    if -stagnation_window_pct <= pnl_pct <= stagnation_window_pct:
        return SellProposal(
            ticker=pos["ticker"],
            shares=int(pos["shares"]),
            current_price=current_price,
            reason=f"STAGNATION: held {days_held}d with flat P&L ({pnl_pct:+.1f}%)",
            urgency_level=UrgencyLevel.LOW,
            urgency_score=25,
        )
    return None
```

**Config parameters added to layer1 config:**
- `stagnation_days` (default: 45)
- `stagnation_pnl_window_pct` (default: 5.0)

---

### E2. Port Liquidity Drop Exit to Active Pipeline (CRITICAL)
**Problem:** Liquidity drop detection only exists in `execute_sells.py` (legacy).

**Implementation:** Add a `_check_liquidity_drop` method to `RiskLayer`:

```python
def _check_liquidity_drop(self, ticker: str, current_price: float, shares: int) -> Optional[SellProposal]:
    """Exit positions where recent volume has collapsed vs 3-month baseline."""
    threshold = self.layer1_config.get("liquidity_drop_threshold", 0.30)

    try:
        from yf_session import cached_download
        data = cached_download(ticker, period="3mo", interval="1d")
        if data is None or data.empty:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            try:
                data = data.xs(ticker, axis=1, level=1)
            except KeyError:
                return None

        if "Volume" not in data.columns:
            return None

        volume = data["Volume"].dropna()
        if len(volume) < 15:
            return None

        # Exclude last 5 days from baseline to avoid contaminating it with the anomaly
        avg_3mo = volume.iloc[:-5].mean()
        avg_5d = volume.iloc[-5:].mean()

        if avg_3mo <= 0:
            return None

        ratio = avg_5d / avg_3mo
        if ratio < threshold:
            return SellProposal(
                ticker=ticker,
                shares=shares,
                current_price=current_price,
                reason=f"LIQUIDITY DROP: 5d avg vol is {ratio:.0%} of 3mo baseline",
                urgency_level=UrgencyLevel.MEDIUM,
                urgency_score=40,
            )
    except Exception as e:
        print(f"Warning: liquidity check failed for {ticker}: {e}")

    return None
```

**Config parameter:** `liquidity_drop_threshold` (default: 0.30, i.e., 5d avg < 30% of baseline)

**Improvement over legacy:** Excludes last 5 days from baseline (same pattern as `scan_volume_anomalies`), so a recent spike doesn't inflate the baseline and hide a true collapse.

---

### E3. Add Momentum Fade Detection (NEW)
**Signal:** Stock closes below 5-day SMA for 3 consecutive days

**Implementation:** Add to `RiskLayer.process()` loop after stop loss checks:

```python
def _check_momentum_fade(self, df_ohlcv: pd.DataFrame, ticker: str, current_price: float, shares: int) -> Optional[SellProposal]:
    """Detect momentum reversal before the stop loss is hit."""
    if df_ohlcv is None or len(df_ohlcv) < 10:
        return None

    close = df_ohlcv["Close"].dropna()
    if len(close) < 10:
        return None

    sma5 = close.rolling(5).mean()
    # Last 3 days all below SMA5
    if all(close.iloc[i] < sma5.iloc[i] for i in [-3, -2, -1]):
        return SellProposal(
            ticker=ticker,
            shares=shares,
            current_price=current_price,
            reason="MOMENTUM FADE: 3 consecutive closes below 5-day SMA",
            urgency_level=UrgencyLevel.LOW,
            urgency_score=30,
        )
    return None
```

**Note:** This requires downloading OHLCV for held positions during risk layer processing. Since `calculate_dynamic_stops` already calls `StockScorer.score_watchlist` which downloads data, we can reuse that data rather than making separate downloads.

---

### E4. Add Parabolic Extension Protection (NEW)
**Signal:** RSI > 82 + price > 15% above 20-day SMA

**Action:** Tighten trailing stop from normal distance to half distance (partial profit protection)

**Implementation:** Modify `_calculate_trailing_stop` to accept a `parabolic` flag:
```python
if parabolic_extension:
    distance_pct = distance_pct * 0.5  # half the normal trail distance
    stop_type = "trailing[parabolic-tightened]"
```

Detect in `RiskLayer.process()` using RSI + SMA distance from the `StockScorer` score object.

---

## Implementation Order

| Priority | Item | File | Complexity |
|---|---|---|---|
| 1 | E1: Stagnation exit → active pipeline | `risk_layer.py` | Low |
| 2 | E2: Liquidity drop → active pipeline | `risk_layer.py` | Low |
| 3 | D2: Enable volume_anomalies + fix price check | `stock_discovery.py` + configs | Low |
| 4 | D1: Fix RSI computation in oversold_bounces | `stock_discovery.py` | Medium |
| 5 | D3: Add relative_volume_surge scan | `stock_discovery.py` | Medium |
| 6 | D4: Fix 52wk high mismatch bug | `stock_discovery.py` | Low |
| 7 | E3: Momentum fade detection | `risk_layer.py` | Medium |
| 8 | D5: MTF alignment bonus in discovery score | `stock_discovery.py` | Low |
| 9 | E4: Parabolic extension protection | `risk_layer.py` | Medium |

---

## What NOT to Implement (Deferred)
- **Earnings-window stop tightening**: Requires reliable earnings calendar. yfinance `.info.earningsDate` is too inaccurate for small-caps. Deferred until better data source available.
- **Regime stop inversion fix**: Regime stops are overridden by trailing/volatility stops in practice. Fixing the backwards logic matters less than the missing stagnation/liquidity exits.
- **Discovery score RSI backwards fix**: The RSI scoring penalizes momentum breakout candidates (RSI 45-65 preferred, RSI >80 penalized). This is being addressed via the multi-timeframe confirmation bonus instead of rewriting the score function.

---

## Implementation Status (Updated 2026-03-27)

### Completed
- **D1**: Fixed `scan_oversold_bounces` RSI computation — replaced O(n×m) list comprehension with vectorized `_compute_rsi_series()`. Expanded window from 5 to 14 bars. Added volume confirmation (1.3x required on recovery).
- **D2**: Enabled `scan_volume_anomalies` by default in `run_all_scans()` (changed default from `False` to `True`). Fixed 1-day price check to 3-day window to stop incorrectly filtering bullish consolidation.
- **D3**: Added `scan_relative_volume_surge` — new scan detecting 4x+ same-day volume vs clean 30-day baseline (excluding last 5 days). Added `RELATIVE_VOLUME_SURGE` to `DiscoverySource` enum. Added to `run_all_scans()`. Annotates discovery record with RVOL and price change.
- **D4**: Fixed `_analyze_stock` to use 1y price data for `near_52wk_high_pct` calculation when available, eliminating the 3-month-high-masquerading-as-52-week-high bug.
- **E1**: Ported stagnation exit to active pipeline (`risk_layer.py`) — `_check_stagnation()`. Configurable via `stagnation_days` (default 45) and `stagnation_pnl_window_pct` (default 5.0). Toggle: `enable_stagnation_exit` (default True).
- **E2**: Ported liquidity drop exit to active pipeline (`risk_layer.py`) — `_check_liquidity_drop()`. Uses improved baseline (excludes last 5 days). Configurable via `liquidity_drop_threshold` (default 0.30). Toggle: `enable_liquidity_exit` (default True).
- **E3**: Added momentum fade detection to active pipeline (`risk_layer.py`) — `_check_momentum_fade()`. 3 consecutive closes below 5-day SMA triggers LOW urgency sell proposal. Toggle: `enable_momentum_fade_exit` (default True).
- **D5** (partial): Source bonus added for `RELATIVE_VOLUME_SURGE` (10 pts, same as `MOMENTUM_BREAKOUT`).

### Deferred
- **D4 volume threshold**: `scan_momentum_breakouts` min_volume_ratio default left at config-controlled value (not hardcoded change).
- **D5 full MTF alignment bonus**: Discovery score MTF alignment bonus not added — the new scan types provide better signal coverage.
- **E4 Parabolic extension protection**: Deferred — requires RSI data from the score object, which is available but adds complexity to the stop calculation path.
- **Earnings-window stop tightening**: Deferred — yfinance earningsDate is unreliable for small-caps.
- **Regime stop inversion fix**: Deferred — overridden by trailing/volatility stops in practice.

### Test Results
All 91 tests pass. Both modules import cleanly.
