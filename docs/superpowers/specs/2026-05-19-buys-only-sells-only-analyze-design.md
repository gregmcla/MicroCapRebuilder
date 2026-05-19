# Buys-Only / Sells-Only Analyze — Design

**Date:** 2026-05-19
**Status:** Approved (design phase)
**Owner:** Greg McLaughlin / Claude

---

## Problem

The existing `/analyze` pipeline always returns a mixed buy+sell plan. Greg wants to direct the system based on market context — deploy cash when the market is down, cull weakness when the portfolio is down — without changing the existing pipeline or its consumers (cron, Telegram).

The solve is two additional analyze modes (`buys_only`, `sells_only`) reachable from two new dashboard buttons. Each mode runs the same underlying pipeline but constrains the prompt and filters the output to a single side. Each mode persists to its own slot so plans coexist and can be executed independently.

## Non-goals

- No changes to the existing `/analyze` endpoint behavior (full mode is bit-for-bit identical to today).
- No changes to cron (`scan.sh`, `analyze.sh`, `update.sh`).
- No changes to Telegram bot flows. New modes are dashboard-only.
- No new "stance" or "posture" abstraction. Strict hard-mode semantics only.
- No partial / hybrid modes (e.g., "buy-lean with rare sells"). The off-side is dropped.

## Architecture

```
TopBar buttons:    ANALYZE        ANALYZE BUYS          ANALYZE SELLS
                      ↓             ↓                     ↓
API endpoints:    POST /analyze   POST /analyze?mode=buys_only   POST /analyze?mode=sells_only
                      ↓             ↓                     ↓
Pipeline:         run_unified_analysis(mode="full"|"buys_only"|"sells_only")
                      ↓             ↓                     ↓
Slot files:    .last_analysis.json  .last_analysis.buys.json   .last_analysis.sells.json
                      ↓             ↓                     ↓
Execute:       POST /execute       POST /execute?mode=buys_only   POST /execute?mode=sells_only
```

## Backend changes

### `scripts/unified_analysis.py`

- Add `mode: str = "full"` parameter to `run_unified_analysis()`. Values: `"full"` (default, unchanged), `"buys_only"`, `"sells_only"`.
- Thread `mode` into the three branch helpers: `_run_ai_driven_analysis`, `_run_enhanced_layers_step2`, `_run_fallback_scoring_step2`, and into `_assemble_analysis_result`.

#### AI-driven path (the hot path for most portfolios)

- `sells_only`: skip the watchlist load, candidate scoring loop, and info pre-warm. Pass empty `scored_candidates` to the allocator. Saves 30–60s typical.
- `buys_only`: still load watchlist + score candidates (needed for buy proposals). Layer 1 still runs (cheap, provides context to Claude) but Claude is told to ignore its sell flags. Pass empty `layer1_sells` to the allocator since they aren't actionable in this mode.

#### Enhanced-layers path

- `buys_only`: drop `rotation_sells` from output *and* their paired `rotation_buys` (rotation buys without their funding sell break the cash math). Keep pure `buy_proposals` from Layer 2. Drop Layer 1 sells from the final action list.
- `sells_only`: skip Layer 2/3/4 entirely. Layer 1 sells flow through to AI review unchanged.

#### Fallback (basic-scorer) path

- `buys_only`: still scores the watchlist. Drop Layer 1 sells from the final action list.
- `sells_only`: skip scoring; Layer 1 sells only.

#### Defense-in-depth filter

In `_assemble_analysis_result` (and the AI-driven path's analogous return block), drop any actions that don't match the mode's allowed side *after* review. So even if Claude misbehaves or a layer leaks a sell into a buys_only output, the user never sees it.

### `scripts/ai_allocator.py`

- `_build_allocation_prompt` accepts a `mode` arg. Adds one new block immediately before HARD CONSTRAINTS:

  - `buys_only`:
    > ⚠️ CASH DEPLOYMENT MODE: This run focuses only on new buys. Treat current positions as fixed — do not propose any sells. Available cash is current cash only (no sell proceeds to assume). Return empty `sells: []`.

  - `sells_only`:
    > ⚠️ RISK REVIEW MODE: This run focuses only on existing positions. Do not propose any new buys. Return empty `allocation_plan: []`. Focus on broken theses, oversized positions, deteriorating factors, and Layer 1 flagged positions.

- `_validate_allocation` accepts `mode`. Enforces empty array on the off-side regardless of what Claude returned (logs a warning if Claude tried to populate it).

- `run_ai_allocation` accepts `mode` and threads it through.

### `api/routes/analysis.py`

- `/analyze` accepts `?mode=full|buys_only|sells_only` query param (default `full`).
- `_analysis_file(portfolio_id, mode)` resolves to:
  - `mode="full"` → `.last_analysis.json` (existing — bit-for-bit unchanged)
  - `mode="buys_only"` → `.last_analysis.buys.json`
  - `mode="sells_only"` → `.last_analysis.sells.json`
- `/execute` accepts the same `?mode=` param. Reads from the corresponding slot file. Uses its own `.executing.{mode}.json` rename guard so each mode's execute is independently lockable.

## Frontend changes

### `dashboard/src/lib/api.ts`

- `analyze(pid, mode?: "full" | "buys_only" | "sells_only")` — passes mode as a query string when set.
- `execute(pid, mode?: same)` — same.

### `dashboard/src/lib/store.ts`

- Replace the flat `portfolioAnalyses[pid]` slot with a keyed structure:
  ```ts
  portfolioAnalyses[pid] = {
    full:       { status, result, error, analyzedAt },
    buys_only:  { status, result, error, analyzedAt },
    sells_only: { status, result, error, analyzedAt },
  }
  ```
- New actions: `runBuysOnlyAnalysis`, `runSellsOnlyAnalysis`, `runBuysOnlyExecute`, `runSellsOnlyExecute`. (Or a unified `runAnalysis(mode)` / `runExecute(mode)` that the existing code calls with `mode="full"` by default.)
- The currently-displayed mode is tracked in UI state (see ActionsTab below), not in the persistence keys.

### `TopBar.tsx`

- Two new compact buttons next to ANALYZE: `ANALYZE BUYS` and `ANALYZE SELLS`. Each shows its own loading state and last-run timestamp on hover/tooltip.
- Labels chosen to disambiguate from the existing `+ BUY` button (manual buy modal, 2026-04-09). Final compact labels can be tightened during implementation (e.g., `ANL BUYS` / `ANL SELLS` if width is tight) — the key constraint is they must not read as "manual buy" or "manual sell" triggers.
- Existing ANALYZE button unchanged.

### `ActionsTab.tsx`

- Add a mode-switcher segmented control at the top: `FULL` | `BUYS ONLY` | `SELLS ONLY`. Each tab shows that mode's most recent result. Empty state when no run yet for that mode.
- The EXECUTE button at the bottom is mode-aware: it calls `runExecute(activeMode)` and reads `can_execute` from the active mode's slot.
- The badge/timestamp shows the analyzed time for the currently-active mode.

## Persistence and concurrency

- Three slot files per portfolio, all in `data/portfolios/{id}/`:
  - `.last_analysis.json` (full)
  - `.last_analysis.buys.json`
  - `.last_analysis.sells.json`
- Each uses the existing atomic-write pattern (`tmp` + `replace`).
- Each has its own concurrency guard: `.executing.json`, `.executing.buys.json`, `.executing.sells.json`. Each is independently lockable via atomic rename.
- Buys-only execute and sells-only execute may run concurrently — they touch disjoint tickers in most cases, and the shared `_atomic_state_writes` snapshot context manager already handles concurrent guards via `fcntl.flock` per Fix 9. No new locking primitive needed.
- Slot files survive across analyses — a buys-only run never touches the sells slot or the full slot.

## Edge cases

- **Same-run reentry veto** (in `run_unified_analysis`): only meaningful when both sides are present. Skip it in `buys_only` and `sells_only` modes.
- **Cash math (buys_only)**: `state.cash` only; no sell proceeds added. Enforced both in the prompt directive and in `_validate_allocation` (it currently computes `effective_cash = available_cash + claude_sell_proceeds`; in buys_only this collapses to `available_cash` since `sells = []`).
- **Layer 1 always runs.** Cheap; gives Claude context even in buys_only. Its sell output is dropped at the assemble step.
- **Telegram bot unchanged.** It only watches `.last_analysis.json` (full mode). New modes are silent on Telegram.
- **Cron unchanged.** `cron/analyze.sh` calls `/analyze` (default full mode). No changes.
- **`.last_analysis.json` is sacred.** Full-mode behavior must be bit-for-bit identical to today. Verified by the existing 17 integration tests passing without modification.
- **Warning severity / preservation mode**: existing checks still apply. In buys_only with `preservation_active=True`, the result is an empty BUYs list (matches today's `_run_fallback_scoring_step2` behavior). The user sees "no buys recommended — preservation mode active." This is correct.
- **Bear regime in fallback path**: same — empty buys list. Documented behavior.

## Testing

### New integration tests (in `tests/integration/`)

1. `test_buys_only_drops_sells_from_output` — full pipeline; assert `sells == []` in output regardless of what Layer 1 / Claude returns.
2. `test_buys_only_prompt_includes_cash_deployment_directive` — mock allocator; assert directive substring is present.
3. `test_buys_only_uses_cash_only_no_sell_proceeds` — assert `effective_cash == state.cash` in the validation call.
4. `test_sells_only_skips_watchlist_scoring` — mock scorer; assert `score_watchlist` is not called when `mode="sells_only"`.
5. `test_sells_only_drops_buys_from_output` — assert `allocation_plan == []` regardless of Claude's response.
6. `test_sells_only_prompt_includes_risk_review_directive` — mock allocator; assert directive present.
7. `test_each_mode_writes_own_slot_file` — run all three modes against the same portfolio; assert all three slot files exist and contain different `timestamp` values.
8. `test_executing_one_mode_does_not_lock_others` — simulate concurrent execute of buys_only and sells_only; both should succeed (or at minimum, the second should not be blocked by the first's `.executing.json`).
9. `test_full_mode_regression` — explicitly run `mode="full"` and compare result shape to the no-`mode`-arg call; must be identical.

### Existing tests

- All 17 existing tests in `tests/integration/` must continue to pass without modification. Full-mode behavior is the regression guard.

## Out of scope (deferred)

- Telegram approval for buys-only / sells-only proposals.
- Cron-driven schedule for sells-only (e.g., "run sells-only at 4 PM if portfolio is down >2%").
- Auto-select the active mode in the dashboard based on most recent activity.
- Cross-mode reconciliation (e.g., warning if buys_only plan would conflict with a pending sells_only plan).

## Open questions

None at design time. All architecture decisions resolved with Greg in brainstorming.
