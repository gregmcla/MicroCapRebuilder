# Realized P&L Header Metric — Design

**Date:** 2026-03-06
**Status:** Approved

## Problem

"All-Time P&L" (`total_equity - starting_capital`) is correct but opaque — it blends gains locked in from closed trades with floating gains still at risk in open positions. When a position is sold, the unrealized gain disappears from the positions panel and the metric appears to drop (actually a stale-price artifact on the remaining positions repricing), which is confusing.

## Solution

Add a **Realized P&L** chip to the portfolio header strip that shows how much has been locked in from closed trades, independent of open position movements.

## Calculation

No post-mortem lookup or trade matching required — pure math from state already in memory:

```
realized_pnl = cash + sum(avg_cost_basis × shares for open positions) - starting_capital
```

**Why this works:**
- `all_time_pnl = realized_pnl + unrealized_pnl`
- `unrealized_pnl = sum(market_value - cost_basis)` for open positions
- Therefore: `realized_pnl = all_time_pnl - unrealized_pnl`
- Expanding: `realized_pnl = (cash + sum(market_value) - starting_capital) - (sum(market_value) - sum(cost_basis))`
- Simplifies to: `cash + sum(cost_basis) - starting_capital`

Interpretation: cash on hand plus what's currently deployed at cost, minus what you started with = money generated from closed trades net of initial capital.

## Changes

### `api/routes/state.py`
Add to `_serialize_state()`:
```python
cost_deployed = sum(
    float(row.get("avg_cost_basis", 0)) * float(row.get("shares", 0))
    for row in positions_list
)
realized_pnl = round(state.cash - starting_capital + cost_deployed, 2)
```
Return as `"realized_pnl": realized_pnl` in the response dict.

### `dashboard/src/lib/types.ts`
Add `realized_pnl: number` to `PortfolioState` interface.

### `dashboard/src/components/PortfolioSummary.tsx`
Add "Realized" chip to the header strip between "Open P&L" and "All-Time P&L":
```tsx
const realizedPnl = state?.realized_pnl ?? 0;
const realizedColor = realizedPnl >= 0 ? "text-profit" : "text-loss";
```

## Files Changed

| File | Change |
|------|--------|
| `api/routes/state.py` | Add `realized_pnl` to state response |
| `dashboard/src/lib/types.ts` | Add `realized_pnl: number` to `PortfolioState` |
| `dashboard/src/components/PortfolioSummary.tsx` | Add Realized chip to header strip |
