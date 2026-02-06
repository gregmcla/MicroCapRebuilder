# MicroCapRebuilder System Overhaul Design

**Date**: 2026-02-05
**Scope**: Architecture consolidation, trading safety, learning pipeline, dashboard overhaul

## Problem Statement

An audit of the MicroCapRebuilder codebase identified four interconnected problem areas:

1. **Architecture fragility** — Cash calculated in 3 places, regime detected in 4, no script coordination
2. **Trading safety gaps** — Silent price fetch failures skip stop losses, bare exceptions default to wrong regimes
3. **Dead code (~20%)** — factor_learning.py, pattern_detector.py (40%), attribution.py depend on data never collected
4. **Dashboard UX** — Full page reloads on every interaction, chat vanishes on navigation, decorative-only quick chips

These are addressed in four sequential phases, each building on the previous.

---

## Phase 1: Architecture Consolidation

### Goal
Single source of truth for portfolio state. Scripts consume state, propose actions, and return results — they don't read/write files directly.

### New Module: `portfolio_state.py`

```python
@dataclass
class PortfolioState:
    cash: float
    positions: pd.DataFrame
    transactions: pd.DataFrame
    snapshots: pd.DataFrame
    regime: MarketRegime
    regime_analysis: RegimeAnalysis
    total_equity: float
    config: dict
    price_failures: list[str]  # Tickers that failed to fetch
    timestamp: datetime

def load_portfolio_state() -> PortfolioState:
    """Single entry point. Loads all data, calculates cash, detects regime."""
    ...

def save_transaction(state: PortfolioState, transaction: dict) -> PortfolioState:
    """Append transaction, return updated state."""
    ...

def update_positions(state: PortfolioState, prices: dict) -> PortfolioState:
    """Update position prices, return updated state."""
    ...

def save_snapshot(state: PortfolioState) -> None:
    """Append daily snapshot."""
    ...
```

### What Gets Deleted
- `calculate_cash()` in pick_from_watchlist.py (lines 70-85)
- `calculate_cash()` in unified_analysis.py (lines 96-104)
- Duplicate `load_config()` in market_regime.py, stock_scorer.py, capital_preservation.py
- Direct CSV reads/writes scattered across trading scripts

### What Changes
- `run_daily.sh` pipeline: load state once, pass through each step
- `unified_analysis.py`: receives PortfolioState, returns proposed actions
- `execute_sells.py`: takes state + prices, returns SellSignal list (no file writes)
- `pick_from_watchlist.py`: takes state, returns buy proposals (no file writes)
- All config access through `state.config` — no more per-module config loading

### Data Write Flow
```
load_portfolio_state()
    |
    v
execute_sells(state) -> [SellSignal, ...]
    |
    v
save_transaction(state, sell_txn) -> updated_state  (for each sell)
    |
    v
pick_from_watchlist(updated_state) -> [BuyProposal, ...]
    |
    v
save_transaction(state, buy_txn) -> updated_state  (for each buy)
    |
    v
update_positions(state, prices) -> final_state
    |
    v
save_snapshot(final_state)
```

This eliminates the race condition where scripts independently calculate cash.

---

## Phase 2: Trading Safety

### Price Fetch Failures

**Current**: If yf.download() fails for a ticker, execute_sells.py silently skips it. Stop loss never checked.

**Fix**: PortfolioState.price_failures tracks tickers that failed to fetch. Behavior:
- Positions with PRICE_UNKNOWN are flagged as urgent alerts
- Stop loss checking is NOT skipped — if price is unknown, the position enters a "stale price" state
- After 2 consecutive days of unknown price, system triggers forced review alert
- Dashboard shows stale-price positions prominently with last-known price and staleness duration

### Exception Handling Policy

**Rule**: Fail loud on money decisions, fail graceful on display.

Money decisions (halt on error):
- Regime detection failure -> halt new buys, log error (not silent SIDEWAYS default)
- Cash calculation error -> halt all trading
- Price validation failure -> skip that ticker with explicit warning
- Transaction write failure -> abort and alert

Display decisions (degrade gracefully):
- Analytics calculation failure -> show "N/A" with tooltip
- Chart generation failure -> show placeholder
- AI chat failure -> show error message with retry button

### Specific Fixes

1. **unified_analysis.py lines 148-150**: Replace bare `except:` with explicit error handling. If regime fails, set `state.regime = MarketRegime.UNKNOWN` and halt buys.

2. **execute_sells.py lines 32-46**: Track failed fetches in returned result. Caller decides what to do.

3. **risk_manager.py line 199**: Review volatility adjustment formula. Current: `0.05 / volatility` — verify this produces correct direction (higher vol = smaller position).

4. **Transaction validation**: Before recording any transaction, validate:
   - price > 0
   - shares > 0
   - ticker string is non-empty and valid
   - For buys: cash >= shares * price
   - For sells: position exists with >= shares

5. **yfinance column handling**: Centralize multi-level column flattening in data_provider.py. All scripts get clean single-level DataFrames. Remove per-file flattening from execute_sells.py, stock_scorer.py.

---

## Phase 3: Learning Pipeline

### Goal
When Mommy buys, she records why. When she sells, she learns what worked. Over time, factor weights adapt based on real results.

### Data Collection: Factor Scores at Buy Time

**Where**: pick_from_watchlist.py, at transaction recording time

**What**: Serialize StockScore's individual factor scores as JSON on the transaction row.

```python
factor_scores = {
    "momentum": score.momentum_score,
    "volatility": score.volatility_score,
    "volume": score.volume_score,
    "relative_strength": score.relative_strength_score,
    "mean_reversion": score.mean_reversion_score,
    "rsi": score.rsi_score,
    "composite": score.composite_score,
}
transaction["factor_scores"] = json.dumps(factor_scores)
transaction["regime_at_entry"] = regime.value
```

**Schema change**: Add `factor_scores` (JSON string) and `regime_at_entry` (string) columns to transactions.csv. Existing rows get empty strings (backward compatible).

### Data Collection: Post-Mortems at Sell Time

**Where**: execute_sells.py, after each sell is recorded

**What**: Generate and persist a post-mortem record.

```python
@dataclass
class PostMortem:
    transaction_id: str
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    holding_days: int
    exit_reason: str        # STOP_LOSS, TAKE_PROFIT, MANUAL
    regime_at_entry: str
    regime_at_exit: str
    entry_factor_scores: dict
    summary: str
```

**Storage**: `data/post_mortems.csv` — one row per completed trade.

### Learning Loop: Factor Weight Adjustment

**When**: Run weekly (or on PIVOT button press), not on every trade.

**How factor_learning.py works (now with real data)**:
1. Load completed trades from post_mortems.csv
2. Group by regime (BULL/SIDEWAYS/BEAR)
3. For each factor, calculate correlation between entry score and trade outcome (P&L %)
4. Factors with positive correlation to winners get weight increased
5. Factors with negative correlation get weight decreased
6. Adjustments capped at +/-5% per cycle
7. Minimum 20 completed trades before any adjustment
8. Results written to config.json under `regime_weights`

**Safety rails**:
- No factor drops below 5% weight
- No factor exceeds 40% weight
- All weights must sum to 100%
- Learning can be disabled via config flag `learning.enabled`
- Weight changes logged to `data/learning_log.csv` for auditability

### Fixes to Existing Dead Code

**factor_learning.py**: Now functional — reads factor_scores from transactions and post_mortems.csv

**pattern_detector.py**: Remove dead `factor_failure` and `regime_mismatch` checks (lines 211-277). Replace with queries against post_mortems.csv:
- "Stocks bought with high momentum scores in BEAR regime tend to lose" (from real data)
- "Stop losses cluster on Mondays" (from real data)

**attribution.py**: Reads factor_scores directly from the new transaction column instead of parsing non-existent JSON.

### Documentation Fix
Update CLAUDE.md scoring weights to match actual code (6 factors, not 5). Document RSI as the 6th factor. Remove the double-filtering of RSI (pick_from_watchlist.py lines 304-308) — the scorer's score of 10.0 for overbought stocks is sufficient, no need to hard-filter again.

---

## Phase 4: Dashboard Overhaul

### Goal
Single scrollable page for daily check-ins. No tabs, no reloads, no vanishing state.

### Layout (top to bottom)

#### 1. Hero Card
One glance summary at the very top:
```
[$52,340 Total Equity]  [+$340 (+0.65%) Today]  [12 Positions]  [BULL]  [2 Alerts]
```
- Equity with daily change (color-coded green/red)
- Position count
- Regime badge (colored)
- Alert count (clickable, scrolls to alerts)

#### 2. Alerts Bar
Only renders if alerts exist. Types:
- Positions within 5% of stop loss (with current price, stop price, distance)
- Positions within 8% of take profit target
- Stale prices (from Phase 2)
- Early warnings (drawdown approaching threshold, losing streak)
- Each alert shows enough context to act on — no need to click through

#### 3. Positions Table
All open positions in a sortable, styled table:
- Ticker, shares, entry price, current price, P&L ($), P&L (%), progress bar (stop-to-target)
- Color-coded rows (green for winners, red for losers)
- Each row expandable to show: entry rationale (from explainability), factor scores at entry, trade history for that ticker
- Sort by: P&L, entry date, distance to stop, distance to target

#### 4. Recent Activity
Last 5 transactions (expandable to full history):
- Date, ticker, action (BUY/SELL), shares, price, reason
- Sells show realized P&L

#### 5. Mommy Chat (Slide-Up Panel)
- Persistent panel at bottom of page, not a sidebar
- Does not vanish on scroll or interaction
- Quick chips ("Health", "Risk", "Targets") actually submit to chat input
- Chat history persists in session state across all interactions
- Random placeholder text set once per session, not per rerun

#### 6. Action Bar (Sticky Footer)
Persistent at bottom of viewport:
- ANALYZE button: runs unified analysis, shows results inline above the bar
- EXECUTE button: only enabled after analysis, shows full summary of proposed actions before confirm
- EMERGENCY button: shows complete position summary (every ticker, shares, value) before any confirmation

### Specific UX Fixes

1. **No st.rerun() on navigation** — Use callbacks and session state for all interactions
2. **Emergency CLOSE ALL** — Must show full position list with values before YES/NO
3. **Analysis results inline** — No tab switch needed to see proposed buys/sells
4. **Loading states** — Show what's happening during long operations (which tickers being fetched, how many scored)
5. **"What changed" section** — Compare today vs yesterday: new positions, closed positions, biggest movers

### What Gets Deleted
- Tab navigation system (webapp.py lines 324-334 and all tab routing)
- webapp_components.py unused sparkline code
- Dead onclick JavaScript handlers (line 598)
- Duplicate calculate_position_progress (keep webapp_helpers.py version)
- webapp_styles.py tab-related CSS

### Performance
- Use @st.cache_data for data loading (positions, transactions, snapshots)
- Lazy-load chart data only when user scrolls to chart section
- Single load_portfolio_state() call per page render, not per-section

---

## Cross-Cutting Concerns

### Error Logging
Add structured logging throughout. Every silent `except:` becomes a logged event:
```python
import logging
logger = logging.getLogger("mommy")

try:
    regime = get_market_regime()
except Exception as e:
    logger.error(f"Regime detection failed: {e}", exc_info=True)
    raise TradingHaltError("Cannot determine market regime")
```

Log to `logs/mommy.log` with rotation.

### Config Consolidation
Single config load path through portfolio_state.py. Remove all per-module config loading. Config accessed as `state.config` everywhere.

### Schema Evolution
Add new columns to transactions.csv (factor_scores, regime_at_entry) with backward compatibility — existing rows have empty values. No migration script needed; code handles missing columns gracefully.

### Testing
Add `scripts/test_integration.py` coverage for:
- PortfolioState load/save roundtrip
- Transaction validation (rejects bad data)
- Factor score serialization/deserialization
- Post-mortem generation from buy+sell pair
- Learning loop weight adjustment within bounds

---

## Implementation Order

1. **Phase 1**: portfolio_state.py + refactor scripts to use it (~15 files touched)
2. **Phase 2**: Safety fixes (exception handling, validation, price tracking) (~8 files)
3. **Phase 3**: Factor scores at buy, post-mortems at sell, fix factor_learning.py (~6 files)
4. **Phase 4**: Dashboard single-page rewrite (~4 files: webapp.py, webapp_helpers.py, webapp_styles.py, webapp_components.py)

Each phase is independently testable and deployable.
