# Exit Logic Audit
**Branch:** `discovery-and-exits-upgrade`
**Date:** 2026-03-27

---

## Critical Finding: Two Exit Paths, One Active

The system has TWO exit code paths:

| Path | File | Status |
|---|---|---|
| **Legacy** | `execute_sells.py` | Only runs when `UNIFIED_MODE=false` in `run_daily.sh` |
| **Active (production)** | `risk_layer.py` via `unified_analysis.py` | All 13 portfolios use this |

**`execute_sells.py` has stagnation and liquidity exit logic that `risk_layer.py` does not.**

Every portfolio running via unified_analysis.py (all of them) is silently missing two entire exit categories. Zombie positions and collapsed-volume stocks are never flagged.

---

## Active Path Exit Inventory (`risk_layer.py`)

### Exit 1: Fixed Stop Loss
**Trigger:** `current_price <= fixed_stop` where `fixed_stop = current_stop or entry_price * 0.92`

**Assessment: FAIR**
- The 8% default is regime-agnostic — same stop for a highly volatile micro-cap ($2M float) as a liquid mid-cap
- `current_stop` comes from the position row (set at buy time) — correct, it's preserved from entry
- No mechanism to update the fixed stop if the original stop was set on bad data or a stale price
- Fine as a floor, but doing all the heavy lifting it wasn't designed for when more dynamic stops don't activate

---

### Exit 2: Trailing Stop
**Trigger:** Position up ≥10% from entry; stop trails 8% below the historical price high

**Implementation:**
```python
trigger_pct = 10%  # activates when gain ≥ 10%
distance_pct = 8%  # trail from price_high
min_stop = entry_price * 1.05  # floor: never below entry+5%
trailing = price_high * (1 - distance_pct)
return max(trailing, min_stop, current_stop)
```

**Assessment: GOOD with gaps**

What's good:
- Uses `price_high` (historical max since entry), not current_price — so stop never moves down
- `min_stop = entry_price * 1.05` once activated — preserves at least a 5% gain once trailing kicks in
- Capital preservation mode tightens trigger to 8% and distance to 5.6%

Gaps:
- **Dead zone at 0-9.9% gain:** A stock can run from entry up to +9.9% and back to entry with zero trailing protection. The stop is still 8% below cost basis. A position that peaks at +9% and retreats to breakeven hits no trigger.
- **Price high from `pos.get("price_high")` requires the position row to track it.** If `price_high` is null (legacy positions, no UPDATE run yet), it falls back to `current_price` — so the trailing stop anchors on today's price, not the historical high.
- **8% trail is wide for small-caps.** A small-cap with 4% ATR needs a 2× ATR trail (~8%), but one with 8% ATR needs a 3×-4× ATR trail (~24-32%) to avoid whipsawing out. A uniform 8% trail is too tight for volatile names and too loose for stable ones.

---

### Exit 3: Volatility-Adjusted Stop
**Trigger:** ATR% determines stop distance (6-10% below entry)

```python
if atr_pct > 5.0:   stop = entry * 0.90  # high vol: 10% below
elif atr_pct < 2.0: stop = entry * 0.94  # low vol: 6% below
else:               stop = entry * 0.92  # default: 8%
```

**Assessment: WEAK**
- Only three bands. ATR% in small-caps can range from 1% to 20%+ — three buckets is very coarse.
- Calculated from entry_price, not current_price. It's a static number that never updates.
- Doesn't integrate with the trailing stop logic — it's just another input to `max(all_stops)`.
- Gets real ATR values from `StockScorer` scoring (good), but then uses them in a blunt threshold.

---

### Exit 4: Regime-Adjusted Stop
**Trigger:** Tightens stop in bear markets (6% below entry vs 8% in bull)

```python
BULL:     entry * 0.92  # 8%
SIDEWAYS: entry * 0.93  # 7%
BEAR:     entry * 0.94  # 6%
```

**Assessment: BACKWARDS**
- In a bear market, stocks fall faster and more violently. A 6% stop (tighter than bull's 8%) means positions get stopped out on normal intraday moves, not actual trend reversals.
- In bear markets you want either: (a) wider stops to survive the volatility, or (b) no new positions at all (already handled by the `MarketRegime.BEAR` check in `pick_from_watchlist.py`).
- This logic tightens stops in bear markets when it should widen them (or simply not be adding new positions to be stopped out of).

---

### Exit 5: Score Deterioration
**Trigger:**
- 20+ point score drop from entry → full exit (EMERGENCY/HIGH urgency)
- 15-19 point drop → 50% exit (MEDIUM urgency)
- 15+ point drop → alert only (no exit)

**Assessment: SOLID**

What's good:
- Entry score is read from the most recent BUY transaction `composite_score` field — correct source
- Fallback to 70.0 for legacy positions without score history is reasonable
- Partial exit (50% of shares) for borderline deterioration is smart — preserves exposure while reducing risk
- Urgency scoring scales with drop magnitude

Gaps:
- **Alert threshold (15) overlaps sell threshold (15).** `score_drop >= 15` creates an alert AND the `elif score_drop >= 15` branch handles partial exit. But the code checks `>= 20` first, then `>= 15` for partial, then `>= 15` for alert-only. So the 15-19 range correctly triggers partial exit + alert via `deterioration_alerts.append()` in the partial branch. The alert-only branch (third `elif`) can only be reached by scores in [15, 15) — it's unreachable. The min_score_drop_alert is initialized to 15 and min_score_drop_partial to 15: they're the same default value, meaning the alert-only path never fires.
- **No minimum position age before deterioration exit.** A stock bought yesterday that's momentarily rescored lower (data cache lag) can trigger a 50% exit. Should have a minimum 3-day hold before score deterioration exits apply.

---

## Missing Exits (Legacy Path Only)

### Missing Exit A: Stagnation
**What it does in `execute_sells.py`:**
- Position held >45 days
- Unrealized P&L between -5% and +5% (flat)
- Triggers full exit

**Why it matters:** Capital tied up in a stock going nowhere for 6+ weeks is dead money. In small-cap momentum strategies, a stock that hasn't moved in 45 days has failed its thesis. Opportunity cost is real.

**Quality assessment of the legacy implementation:**
- -5% to +5% flat zone is sensible for small-caps (wider than the ±2% you'd use for large-caps)
- 45-day window is reasonable but hardcoded — should be configurable per portfolio strategy
- No check for whether the stock has a pending catalyst (earnings, FDA, etc.) — would benefit from awareness of why it's stagnant

**Status: COMPLETELY ABSENT from active pipeline.**

---

### Missing Exit B: Liquidity Drop
**What it does in `execute_sells.py`:**
- 5-day average volume < 30% of 3-month average volume
- Triggers full exit (LIQUIDITY_DROP reason)

**Why it matters:** In small-caps, volume collapse is a leading indicator of price collapse. Market makers widen spreads, institutional interest has left, and the exit door narrows. A stock with 70% volume decline from its baseline is fundamentally less tradeable.

**Quality assessment of the legacy implementation:**
- 5d vs 3mo window: reasonable. The baseline excludes recent days implicitly (uses mean of all 3mo data including recent — this could contaminate the baseline with the spike itself, unlike the volume_anomalies scan which correctly excludes recent days).
- 30% threshold: fine for general use
- No check for whether the volume drop is sector-wide (market holiday week, etc.) vs stock-specific

**Status: COMPLETELY ABSENT from active pipeline.**

---

## Smarter Exit Logic — What Would Add Real Edge

### A. Momentum Fade Detection
**Signal:** Stock closes below its 5-day SMA for 3 consecutive days
**Thesis:** In small-cap momentum, the 5-day MA is a short-term trend anchor. Three days below it = momentum has definitively shifted. This is a leading indicator vs waiting for the stop to be hit.
**Advantage over fixed stop:** Catches trend reversals before they become stop losses. A stock can be well above its 8% stop but clearly in a downtrend.

### B. Parabolic Extension Protection
**Signal:** RSI > 80 + price > 15% above 20-day SMA
**Action:** Tighten trailing stop from 8% to 4% (or trigger immediate partial exit of 30-50%)
**Thesis:** Parabolic moves in small-caps almost always mean-revert, often violently. Protecting gains on extended names before they reverse is better than watching a 40% gain become 10%.

### C. Time-Based Stagnation (Port from Legacy)
The stagnation logic from `execute_sells.py` needs to be ported to `risk_layer.py`. The parameters should be configurable in portfolio config:
- `stagnation_days`: days before flagging (default 45, momentum portfolios might want 30)
- `stagnation_pnl_window_pct`: flat zone definition (default ±5%)

### D. Liquidity Drop (Port from Legacy)
The liquidity check from `execute_sells.py` needs to be ported to `risk_layer.py`. The baseline calculation should be fixed to exclude the most recent 5 days (same pattern as `scan_volume_anomalies`).

### E. Earnings-Window Stop Tightening
**Signal:** Position within 2 trading days of earnings announcement
**Action:** Tighten trailing stop to 50% of normal distance
**Thesis:** Small-caps can move 20-40% on earnings. If you're long and it's a miss, the stop needs to catch the gap-down. If you don't know the earnings date, you'll often be stopped out at a very bad price.
**Limitation:** yfinance's `earningsDate` from `.info` is often inaccurate for small-caps. This would require the earnings calendar integration flagged in the discovery audit.

---

## Summary: Exit Coverage Matrix

| Exit Type | Active Path | Legacy Path | Missing from Active |
|---|---|---|---|
| Fixed stop loss | ✅ | ✅ | — |
| Trailing stop | ✅ | ❌ | — |
| Volatility stop | ✅ | ❌ | — |
| Regime stop | ✅ | ❌ | — |
| Score deterioration | ✅ | ❌ | — |
| Take-profit ceiling | ❌ (intentional) | ✅ | intentional |
| **Stagnation** | **❌** | **✅** | **YES — critical** |
| **Liquidity drop** | **❌** | **✅** | **YES — critical** |
| Momentum fade | ❌ | ❌ | new signal needed |
| Parabolic extension | ❌ | ❌ | new signal needed |
| Earnings protection | ❌ | ❌ | needs calendar data |

---

*No code changes in this iteration. See discovery-audit.md for discovery findings.*
