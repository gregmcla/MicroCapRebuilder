# EKG Strip — Real Performance Data

**Date:** 2026-03-10
**Status:** Approved

## Summary

Replace the synthetic heartbeat animation in the Portfolio Vitals EKG strip with real daily P&L data from the active portfolio's `daily_snapshots.csv`.

## Context

The `EKGStrip` component renders inside `MatrixGrid` in the single-portfolio view. It currently generates a fake heartbeat using sin waves and random noise — it looks alive but carries no information. The real `day_pnl_pct` data needed to drive it is already loaded in `App.tsx` via `usePortfolioState()`.

This feature only applies to the single-portfolio view. The overview page is out of scope.

## Design

### Data Flow

```
usePortfolioState() → state.snapshots[].day_pnl_pct
  → activeMatrixPortfolio.equityCurve (new field)
    → MatrixGrid portfolios prop
      → EKGStrip
```

No new API calls. All data is already fetched.

### Visual Behavior

- Single line centered vertically in the 48px strip
- Each `day_pnl_pct` value expands into ~20 scrolling points: flat baseline → spike → flat return
- **Green spike up** for gain days (`pct > 0.05`)
- **Red dip down** for loss days (`pct < -0.05`)
- **Dim baseline noise** for flat days
- Big moves (`|pct| ≥ 1.0`) get a glow halo
- Live cursor dot tracks the right edge
- Scrolls continuously left at ~30fps

### Fallback

If `equityCurve` is absent or has fewer than 3 points, the component falls back to the existing synthetic heartbeat animation unchanged.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/src/components/MatrixGrid/types.ts` | Add `equityCurve?: number[]` to `MatrixPortfolio` |
| `dashboard/src/App.tsx` | Spread `equityCurve: state.snapshots.map(s => s.day_pnl_pct)` into `activeMatrixPortfolio` |
| `dashboard/src/components/MatrixGrid/EKGStrip.tsx` | Replace synthetic draw logic with real-data renderer; fallback to synthetic when no data |

## Constraints

- Strip height stays 48px — no layout changes
- "PORTFOLIO VITALS" label unchanged
- Overview page unaffected (`showEKG` already defaults to `true` but overview doesn't render `MatrixGrid` with EKG)
- No new API endpoints
