# Realized P&L Header Metric Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Realized" P&L chip to the portfolio header strip so locked-in gains/losses from closed trades are visible alongside open P&L and all-time P&L.

**Architecture:** Compute `realized_pnl = cash + cost_deployed - starting_capital` in the state API (no new data sources — pure math from existing state), return it in the state response, add it to the TypeScript types, and render it as a new chip in `PortfolioSummary.tsx`.

**Tech Stack:** Python 3 / FastAPI (`api/routes/state.py`), TypeScript / React 19 (`dashboard/src/`), pytest for backend test.

**Design doc:** `docs/plans/2026-03-06-realized-pnl-design.md`

---

## Task 1: Add `realized_pnl` to state API

**Files:**
- Modify: `api/routes/state.py:39-75`
- Test: `tests/test_realized_pnl_api.py`

### Step 1: Write the failing test

Create `tests/test_realized_pnl_api.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import types
import pandas as pd
from api.routes.state import _serialize_state


def _make_state(cash: float, positions: list[dict], starting_capital: float):
    """Build a minimal PortfolioState-like object for testing."""
    state = types.SimpleNamespace()
    state.cash = cash
    state.positions = pd.DataFrame(positions) if positions else pd.DataFrame(
        columns=["ticker", "shares", "avg_cost_basis", "current_price",
                 "market_value", "unrealized_pnl", "unrealized_pnl_pct",
                 "day_change", "day_change_pct"]
    )
    state.transactions = pd.DataFrame()
    state.snapshots = pd.DataFrame()
    state.regime = "BULL"
    state.regime_analysis = {}
    state.positions_value = sum(p.get("market_value", 0) for p in positions)
    state.total_equity = cash + state.positions_value
    state.num_positions = len(positions)
    state.config = {"starting_capital": starting_capital}
    state.stale_alerts = []
    state.paper_mode = True
    state.price_failures = []
    state.timestamp = None
    return state


def test_realized_pnl_no_positions():
    """All cash, no positions: realized = cash - starting_capital."""
    state = _make_state(cash=60000, positions=[], starting_capital=50000)
    result = _serialize_state(state)
    assert "realized_pnl" in result
    assert result["realized_pnl"] == 10000.0


def test_realized_pnl_with_open_positions():
    """Cash + deployed capital - starting: realized excludes unrealized gains."""
    state = _make_state(
        cash=30000,
        positions=[{
            "ticker": "AAPL",
            "shares": 10,
            "avg_cost_basis": 150.0,
            "current_price": 200.0,   # $500 unrealized gain — should NOT count
            "market_value": 2000.0,
            "unrealized_pnl": 500.0,
            "unrealized_pnl_pct": 33.3,
            "day_change": 0.0,
            "day_change_pct": 0.0,
        }],
        starting_capital=50000,
    )
    # realized = cash(30000) + cost_deployed(10 * 150 = 1500) - starting(50000) = -18500
    result = _serialize_state(state)
    assert result["realized_pnl"] == -18500.0


def test_realized_pnl_break_even():
    """Starting capital all in cash means 0 realized P&L."""
    state = _make_state(cash=50000, positions=[], starting_capital=50000)
    result = _serialize_state(state)
    assert result["realized_pnl"] == 0.0
```

### Step 2: Run to verify it fails

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
pytest tests/test_realized_pnl_api.py -v
```

Expected: FAIL — `KeyError: 'realized_pnl'`

### Step 3: Add `realized_pnl` to `_serialize_state()`

In `api/routes/state.py`, find the block starting at line 39:

```python
    # Total return + all-time P&L
    starting_capital = float(state.config.get("starting_capital", 50000))
    total_return_pct = 0.0
    all_time_pnl = 0.0
    if starting_capital > 0:
        total_return_pct = ((state.total_equity - starting_capital) / starting_capital) * 100
        all_time_pnl = state.total_equity - starting_capital
```

Add immediately after (before the `if not market_open_today` block):

```python
    # Realized P&L = cash + cost of open positions - starting capital
    # = all_time_pnl - unrealized_pnl (math: excludes floating gains/losses)
    positions_for_cost = state.positions
    if not positions_for_cost.empty and "avg_cost_basis" in positions_for_cost.columns:
        cost_deployed = float(
            (positions_for_cost["avg_cost_basis"] * positions_for_cost["shares"]).sum()
        )
    else:
        cost_deployed = 0.0
    realized_pnl = round(state.cash + cost_deployed - starting_capital, 2)
```

Then add `"realized_pnl": realized_pnl,` to the return dict after `"all_time_pnl"`:

```python
        "all_time_pnl": round(all_time_pnl, 2),
        "realized_pnl": realized_pnl,     # ADD THIS
        "starting_capital": starting_capital,
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/test_realized_pnl_api.py -v
```

Expected: PASS all 3 tests.

### Step 5: Run full test suite to confirm nothing broke

```bash
pytest tests/ -v
```

Expected: all 20 tests pass.

### Step 6: Commit

```bash
git add api/routes/state.py tests/test_realized_pnl_api.py
git commit -m "feat: add realized_pnl to state API response"
```

---

## Task 2: Add Realized chip to dashboard header

**Files:**
- Modify: `dashboard/src/lib/types.ts` (add field to interface)
- Modify: `dashboard/src/components/PortfolioSummary.tsx` (render chip)

No automated tests — verify by build passing.

### Step 1: Add `realized_pnl` to `PortfolioState` in `types.ts`

Open `dashboard/src/lib/types.ts`. Find the `PortfolioState` interface (around line 40). It has fields like `all_time_pnl`, `total_return_pct`, etc. Add:

```typescript
  realized_pnl: number;
```

after `all_time_pnl: number;`.

### Step 2: Add `realizedPnl` variable in `PortfolioSummary.tsx`

Open `dashboard/src/components/PortfolioSummary.tsx`. Find the block around line 418-423:

```typescript
  const overallPnl = state?.positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0) ?? 0;
  const overallColor = overallPnl >= 0 ? "text-profit" : "text-loss";
  const allTimePnl = state?.all_time_pnl ?? 0;
  const allTimeColor = allTimePnl >= 0 ? "text-profit" : "text-loss";
  const dayColor = (state?.day_pnl ?? 0) >= 0 ? "text-profit" : "text-loss";
  const returnColor = (state?.total_return_pct ?? 0) >= 0 ? "text-profit" : "text-loss";
```

Add after `returnColor`:

```typescript
  const realizedPnl = state?.realized_pnl ?? 0;
  const realizedColor = realizedPnl >= 0 ? "text-profit" : "text-loss";
```

### Step 3: Add the Realized chip to the P&L metrics row

Find the P&L metrics row in `PortfolioSummary.tsx` (around line 459). It currently shows: All-Time P&L → Open P&L → Today → Return → Cash.

Insert the **Realized** chip between **All-Time P&L** and **Open P&L**:

```tsx
            {/* All-Time P&L */}
            <div>
              <div className={`font-mono text-sm tabular-nums font-semibold ${allTimeColor}`}>
                {allTimePnl >= 0 ? "+" : ""}${allTimePnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div style={labelStyle}>All-Time P&L</div>
            </div>
            {/* Realized P&L */}
            <div>
              <div className={`font-mono text-sm tabular-nums font-semibold ${realizedColor}`}>
                {realizedPnl >= 0 ? "+" : ""}${realizedPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div style={labelStyle}>Realized</div>
            </div>
            {/* Open P&L */}
```

### Step 4: Build to verify no TypeScript errors

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -8
```

Expected:
```
✓ built in ~950ms
```

If TypeScript errors appear, they will reference missing `realized_pnl` — check that `types.ts` was updated correctly.

### Step 5: Commit

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/lib/types.ts dashboard/src/components/PortfolioSummary.tsx
git commit -m "feat: add Realized P&L chip to portfolio header strip"
```

---

## Final: Push

```bash
git push origin main
```
