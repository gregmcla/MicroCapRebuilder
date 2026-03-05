# Scan All Portfolios — Design

**Date:** 2026-03-05
**Status:** Approved

## Problem

The overview dashboard has no way to refresh watchlists across all portfolios at once. Users must navigate into each portfolio individually and click Scan. With 4 portfolios this is tedious, especially after market open when all watchlists need refreshing.

## Solution

Add a "Scan All" button to the overview aggregate bar (next to the existing "Update All" button). It runs each portfolio's scan sequentially, with live per-portfolio feedback on both the button and each portfolio card.

## Approach: Frontend-Orchestrated Sequential

No backend changes except lowering the scan timeout from 15 → 8 minutes. The frontend drives the chain using existing endpoints:

- `POST /api/{portfolio_id}/scan` — starts scan background thread
- `GET /api/{portfolio_id}/scan/status` — polls result

Sequential (not parallel) so that the shared `data/yf_cache/` warms progressively: microcap scans ~838 tickers first, subsequent portfolios get fast reads.

## Architecture

### State shape (in OverviewPage)

```ts
interface ScanAllState {
  running: boolean;
  currentId: string | null;       // portfolio currently being scanned
  results: Record<string, {
    status: "running" | "complete" | "error";
    added: number;                 // candidates added (0 on error)
    active: number;                // total active watchlist size
    error: string | null;
  }>;
}
```

### `handleScanAll` logic

1. Get active portfolio IDs from `portfolioList`, in list order (microcap first — largest universe, most cache warming)
2. For each portfolio ID, sequentially:
   - Set `currentId`, status = `"running"`
   - Fire `api.scan(id)`
   - Poll `api.scanStatus(id)` every 3s until `status !== "running"`
   - On complete: store `{ added, active }` from result stats, call `queryClient.invalidateQueries(["overview"])` to refresh card data live
   - On error or frontend timeout (9 min): store error, continue to next portfolio
3. When chain finishes: compute total added, show summary on button for 5s, clear

A `cancelledRef` boolean lets the loop abort cleanly if the component unmounts mid-chain.

## UI

### Aggregate bar — "Scan All" button

| State | Label |
|-------|-------|
| Idle | `Scan All` |
| Running | `Scanning microcap…` (current portfolio name) |
| Done | `+22 added · 4 scanned` → clears after 5s |
| Disabled | While running |

Styled identically to the existing "Update All" button.

### Portfolio card — scan badge

A small status strip added below the bottom stats row of each `PortfolioCard`. Only visible when `scanAllState.results[id]` exists for that card.

| State | Appearance |
|-------|-----------|
| Running | Pulsing amber dot + `"Scanning…"` |
| Complete | Green dot + `"+9 added · 150 active"` |
| Error | Red dot + `"Scan error"` |

Badge persists until the next Scan All run clears it.

## Timeout & Error Handling

- **Backend timeout:** lowered from 900s → 480s (8 min) in `api/routes/discovery.py`
- **Frontend guard:** 540s (9 min) per portfolio — slightly over backend limit so backend timeout fires first
- **Per-portfolio errors are non-fatal:** chain continues, card shows error badge
- **Concurrent conflict:** if a portfolio's per-portfolio ScanButton is already running when Scan All reaches it, the backend returns `"already running"` — frontend treats this as a running scan and polls normally until it completes
- **Navigation away:** in-progress backend scan thread completes, but chain sequencing stops (frontend-driven). Acceptable — this is a watched interactive action.

## Files Changed

| File | Change |
|------|--------|
| `api/routes/discovery.py` | Lower `SCAN_TIMEOUT_SECONDS` 900 → 480 |
| `dashboard/src/components/OverviewPage.tsx` | Add `scanAllState`, `handleScanAll`, pass to `AggregateBar` and `PortfolioCard` |

No other files touched.
