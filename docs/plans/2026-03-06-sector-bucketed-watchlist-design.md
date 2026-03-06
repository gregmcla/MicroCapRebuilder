# Sector-Bucketed Watchlist — Design

**Date:** 2026-03-06
**Status:** Approved

## Problem

The current watchlist fills by global score sort: top N candidates by `discovery_score` regardless of sector. When a sector runs hot (e.g., Tech in a bull market), it crowds out the rest. A "healthcare-focused" or "balanced" portfolio ends up with a Tech-heavy watchlist — ANALYZE then proposes mostly Tech buys, sector risk concentrates, and rotation comparisons are meaningless ("is there a better stock anywhere?" instead of "is there a better Tech stock?").

## Solution

Sector-bucketed watchlist filling. The watchlist shape is derived from the portfolio's strategy — each target sector gets a proportional slice of `total_watchlist_slots`. Candidates compete within their sector bucket, not globally.

**Mode detection (auto-derived, no new config knob):**
- `sector_weights` present and non-empty in config → **sector-bucketed mode**
- `sector_weights` absent or `{}` → **global mode** (current behavior, unchanged)

Portfolios without sector targets (microcap, no-filter allcap) stay on global mode automatically.

## Config Schema

`discovery.watchlist` gains two new fields in sector-bucketed mode:

```json
"watchlist": {
  "total_watchlist_slots": 200,
  "sector_weights": {
    "Technology": 40,
    "Healthcare": 25,
    "Industrials": 15,
    "Financial Services": 10,
    "Energy": 10
  },
  "stale_days_threshold": 30,
  "remove_poor_performers": true,
  "min_trades_for_removal": 3,
  "max_loss_rate_for_removal": 0.75
}
```

**Slot math:** `bucket_size[sector] = round(total_slots × weight / sum(weights))`. Weights are normalized automatically — they don't need to sum to 100. Rounding remainders go to the highest-weight sector.

**`max_tickers` is kept for global mode** and remains the controlling field when `sector_weights` is absent.

### Default `total_watchlist_slots` per universe preset

| Universe | Default slots |
|----------|---------------|
| microcap | unchanged (flat 150, global mode) |
| smallcap | 150 |
| midcap | 180 |
| largecap | 200 |
| allcap | 250 |

## Discovery Filling Logic (`stock_discovery.py`)

The scan pipeline is **unchanged** — same universe, same pre-warm, same per-ticker scoring and filters. Only the final selection step changes.

**Sector-bucketed mode:**
1. Compute `bucket_sizes: Dict[str, int]` from `sector_weights` + `total_watchlist_slots`
2. Scan universe normally (`sector_filter` = `sector_weights.keys()` — already gates scan to target sectors)
3. After scan, group passing candidates by sector
4. For each bucket: take top `bucket_sizes[sector]` by `discovery_score`
5. Return the union (len ≤ `total_watchlist_slots`)

If a sector yields fewer candidates than its bucket size, those slots stay empty — no cross-sector backfill.

**Global mode:** unchanged — sort all candidates by score, return top `max_tickers`.

## Watchlist Enforcement (`watchlist_manager.py`)

### New: `enforce_bucket_sizes()`

Replaces `enforce_max_size()` in sector-bucketed mode:
- For each sector in `sector_weights`, find all ACTIVE entries for that sector
- Sort by `discovery_score` descending
- Drop anything beyond `bucket_sizes[sector]`
- Core tickers are always protected

### `balance_sectors()` — skipped in bucketed mode

`balance_sectors()` (25% sector cap trim) is redundant when buckets already constrain distribution. It remains in the code and continues to run in global mode. In `update_watchlist()`, it is skipped when `sector_weights` is configured.

### `update_watchlist()` flow

```
remove_poor_performers()
→ discover_stocks()           # returns bucketed or global candidates
→ add_discovered_stocks()
→ _backfill_missing_sectors()
→ mark_stale_tickers()
→ remove_stale_tickers()
→ balance_sectors()           # skipped if sector-bucketed
→ enforce_bucket_sizes()      # NEW: replaces enforce_max_size() in bucketed mode
→ enforce_max_size()          # global mode only
```

## Portfolio Creation

### Wizard path (`CreatePortfolioModal.tsx`)

New step added after sector selection: **Sector Weights**.
- Each selected sector shown with a percentage input
- Auto-normalizes as user types so weights always sum to 100
- Default: equal weight across all selected sectors
- Submits `sector_weights: {[sector]: weight}` to `POST /api/portfolios`

### AI strategy path (`strategy_generator.py`)

Claude prompt updated to include `sector_weights` in the strategy JSON output, with reasoning per sector. Example output:

```json
{
  "sectors": ["Technology", "Healthcare", "Industrials"],
  "sector_weights": {
    "Technology": 50,
    "Healthcare": 30,
    "Industrials": 20
  },
  "sector_weights_rationale": "Technology overweighted — AI infrastructure is the primary thesis. Healthcare as defensive balance. Industrials for reshoring exposure."
}
```

### `create_portfolio()` (`portfolio_registry.py`)

- Accepts new `sector_weights: dict` param
- Writes `config["discovery"]["watchlist"]["sector_weights"]` when provided
- Sets `config["discovery"]["watchlist"]["total_watchlist_slots"]` from universe preset default
- `POST /api/portfolios` route extended to accept and pass through `sector_weights`

## Files Changed

| File | Change |
|------|--------|
| `scripts/stock_discovery.py` | Bucketed selection after scan (new `_select_by_buckets()` helper) |
| `scripts/watchlist_manager.py` | `enforce_bucket_sizes()`, skip `balance_sectors()` in bucketed mode |
| `scripts/portfolio_registry.py` | `total_watchlist_slots` defaults per preset, `sector_weights` param in `create_portfolio()` |
| `scripts/strategy_generator.py` | Output `sector_weights` + rationale in AI strategy JSON |
| `api/routes/portfolios.py` | Accept `sector_weights` in create request body |
| `dashboard/src/components/CreatePortfolioModal.tsx` | New weight-assignment step after sector selection |

No changes to `opportunity_layer.py`, `risk_layer.py`, `unified_analysis.py`, or `api/` analysis routes — they consume the watchlist as-is and automatically benefit from improved sector distribution.

## Downstream Benefits (No Code Changes Required)

- **ANALYZE** proposals reflect actual sector intent — watchlist only contains target-sector candidates
- **Rotation logic** compares within-sector alternatives naturally
- **Risk concentration** is meaningful — watchlist shape mirrors portfolio risk posture
- **`sector_balanced` stats** in scan results become accurate indicators of strategy alignment
