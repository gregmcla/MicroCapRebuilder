# Manual Buy Feature — Design Spec

**Date:** 2026-04-09
**Status:** Approved

## Summary

Add the ability to manually buy any ticker from the dashboard via a top-bar BUY button. The system auto-suggests share count from risk config, shows stop/target defaults, and lets the user edit everything before confirming.

## Backend

### New endpoint: `POST /api/{portfolio_id}/buy`

**Request body (Pydantic model `BuyRequest`):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ticker` | string | yes | — | Stock ticker symbol |
| `shares` | int | yes | — | Number of shares to buy |
| `stop_loss_pct` | float | no | from config (7.0) | Stop loss as % below entry |
| `take_profit_pct` | float | no | from config (20.0) | Take profit as % above entry |

**Execution flow:**

1. Load portfolio state with `fetch_prices=False` (we fetch the specific ticker's price separately)
2. Fetch live price for the ticker via `fetch_prices_batch([ticker])` — fail if no price returned
3. Validate:
   - `shares > 0`
   - `total_cost = shares * price <= state.cash`
   - Price is a valid positive number
4. Calculate absolute stop/target: `stop = price * (1 - stop_loss_pct/100)`, `target = price * (1 + take_profit_pct/100)`
5. Build transaction dict with `reason: "MANUAL"`, `action: "BUY"`
6. `save_transactions_batch()` FIRST, then `update_position()`, then `save_positions()`
7. Return response

**Response:**

```json
{
  "ticker": "AAPL",
  "shares": 100,
  "price": 175.50,
  "total_value": 17550.00,
  "stop_loss": 163.22,
  "take_profit": 210.60,
  "remaining_cash": 1629155.51,
  "message": "Bought 100 shares of AAPL @ $175.50 for $17,550.00"
}
```

**No max_position_pct enforcement** — manual buys trust user judgment. Only hard gate is cash sufficiency.

### New endpoint: `GET /api/{portfolio_id}/quote/{ticker}`

Lightweight price + info lookup for the modal. Portfolio-scoped so it can return risk config defaults and available cash for auto-suggesting share count.

**Response:**

```json
{
  "ticker": "AAPL",
  "price": 175.50,
  "name": "Apple Inc.",
  "sector": "Technology",
  "prev_close": 174.20,
  "available_cash": 1646705.51,
  "risk_per_trade_pct": 8.0,
  "default_stop_loss_pct": 7.0,
  "default_take_profit_pct": 20.0,
  "suggested_shares": 750
}
```

`suggested_shares` = `floor(available_cash * risk_per_trade_pct / 100 / price)`.

**Implementation:** `fetch_prices_batch([ticker])` for price + `yf.Ticker(ticker).info` with 5s timeout for name/sector. Config values read from portfolio config.

## Frontend

### BuyModal component (`dashboard/src/components/BuyModal.tsx`)

**Trigger:** "BUY" button added to the top bar, styled to match existing buttons (ANALYZE, SCAN, etc.).

**Modal states:**

1. **Ticker input** — opens with empty ticker field, auto-focused. User types ticker and presses Enter or blurs.
2. **Loading** — fetches quote via `GET /api/quote/{ticker}`. Shows spinner.
3. **Trade form** — once price loads, shows:
   - Company name + current price
   - Shares input (auto-filled with suggested size from `cash * risk_per_trade_pct / price`)
   - Stop loss % input (default from config, e.g. 7.0)
   - Take profit % input (default from config, e.g. 20.0)
   - Trade preview: total cost, % of available cash, absolute stop price, absolute target price
   - Confirm button: "Buy {shares} {ticker}"
4. **Result** — success/error message, auto-closes on success after 2s

**Auto-suggest calculation:** The modal needs `cash` and `risk_per_trade_pct` from portfolio state. These are already available via the existing `usePortfolioState` hook — `state.cash` and config values.

**Risk config access:** Add `risk_per_trade_pct`, `default_stop_loss_pct`, `default_take_profit_pct` to the portfolio state API response if not already present. Alternatively, hardcode sensible defaults in the modal and let the user edit.

### API client addition (`dashboard/src/lib/api.ts`)

```typescript
getQuote: (pid: string, ticker: string) =>
  get<{ ticker: string; price: number; name: string; sector: string; prev_close: number; available_cash: number; risk_per_trade_pct: number; default_stop_loss_pct: number; default_take_profit_pct: number; suggested_shares: number }>(`/${pid}/quote/${ticker}`),

buyPosition: (pid: string, body: { ticker: string; shares: number; stop_loss_pct?: number; take_profit_pct?: number }) =>
  post<{ ticker: string; shares: number; price: number; total_value: number; stop_loss: number; take_profit: number; remaining_cash: number; message: string }>(`/${pid}/buy`, body),
```

### Top bar integration

Add a "BUY" button to the top bar in `TopBar.tsx` (or wherever ANALYZE/SCAN/etc. live). Green-tinted ghost button to match the visual language. Opens BuyModal on click.

## Files to modify

| File | Change |
|------|--------|
| `api/routes/controls.py` | Add `POST /buy` and `GET /quote/{ticker}` endpoints |
| `dashboard/src/components/BuyModal.tsx` | New file — the buy modal component |
| `dashboard/src/lib/api.ts` | Add `getQuote` and `buyPosition` functions |
| `dashboard/src/components/TopBar.tsx` (or equivalent) | Add BUY button that opens BuyModal |

## Out of scope

- Watchlist row buy buttons (can add later)
- AI review of manual buys
- Position size enforcement (max_position_pct)
- Limit orders / price targeting
