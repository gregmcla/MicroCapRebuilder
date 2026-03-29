# Overview Dashboard Redesign Plan
Date: 2026-03-27

## Decision Summary

The constellation map is NOT the right primary view for a morning workflow. A well-designed portfolio scoreboard grid answers the key questions faster and more reliably than a physics simulation. The constellation map will be retained as a secondary "MAP" tab — it has genuine value for exploring position composition but should not be the only view.

---

## 1. PRIMARY VIEW: Portfolio Scoreboard Grid

**Decision: Replace the current basic card grid with a richer scoreboard that can be sorted.**

The current cards are actually decent — they show the right data. The problems are:
- No sorting
- Top movers not shown
- No attention section
- Cards don't signal interactivity clearly

The redesign enhances the cards, adds sorting controls, and introduces flanking sections (movers + attention).

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ AGGREGATE BAR (enhanced)                                        │
├──────────────────────┬───────────────────────────────────────────┤
│  ATTENTION PANEL     │  PORTFOLIO GRID (sortable)               │
│  (left, ~240px)      │                                          │
│  • Errors            │  [Sort: Day P&L ▾]  [Sort: Return ▾]    │
│  • High risk         │                                          │
│  • Idle cash >20%    │  Cards: name, equity, day P&L, return,   │
│                      │  deployed bar, regime badge, sparkline,  │
│  MOVERS PANEL        │  positions count                         │
│  • Top 5 today       │                                          │
│  • Bottom 5 today    │  Click card → navigate to portfolio      │
└──────────────────────┴───────────────────────────────────────────┘
```

**Secondary views (tab toggle in header):**
- GRID (default, scoreboard)
- MAP (ConstellationMap — existing)
- CHART (PerformanceChart — existing, improved)

---

## 2. INFORMATION HIERARCHY

**The 5 numbers that matter most at a glance:**

1. **Total Equity** — where is my money (current: ✓, good)
2. **Day P&L** — am I winning today (current: ✓ but not prominent enough)
3. **Deployed %** — how much is actually working (current: ✗ missing from agg bar)
4. **Portfolios up vs down count** — situational awareness ("8↑ 4↓") (current: ✗ missing)
5. **All-Time Return %** — overall system health (current: ✓)

**AggregateBar redesign:**
- Hero: Total Equity (26px, current is fine)
- Row 2 chips: Day P&L ($+%) | All-Time Return | Deployed % | Up/Down count | Total Cash
- Remove: Unrealized P&L chip (less actionable), Portfolios count chip (redundant)
- Add: Deployed % = (total_equity - total_cash) / total_equity * 100
- Add: Up count / Down count badges (computed from portfolios[] day_pnl)

---

## 3. PERFORMANCE CHART IMPROVEMENTS

**Current problems with 13 portfolios:**
- 8-color palette wraps — portfolios 9-13 share colors with 1-5
- Legend would need 13 entries — runs off screen
- All 13 lines together are visually noisy

**Improvements to implement:**
1. **Expand palette to 13 colors** — add 5 more distinct colors to CHART_PALETTE
2. **Legend improvements** — show labels at line endpoints with name truncated to 12 chars, ranked by final return, not just 8 entries but all
3. **Filter toggle** — in CHART view, show top 5 by return, bottom 5 by return, and ability to toggle individual series
4. **Keep dual-zone logic** — it's a genuinely good solution for outlier portfolios

The PerformanceChart changes must be surgical — preserve all existing canvas drawing logic, just extend the palette and improve label rendering.

---

## 4. CROSS-PORTFOLIO MOVERS SECTION

**Current state:** `top_movers` and `bottom_movers` are in the API response but COMPLETELY unused in the UI. This is a critical gap.

**Format:** Left panel, two sections:
```
TOP TODAY
  TICKER    +portfolio    +$X   +X%
  TICKER    +portfolio    +$X   +X%
  ...

BOTTOM TODAY
  TICKER    +portfolio    -$X   -X%
  ...
```

- Show top 5 movers, bottom 5 movers
- Compact rows: ticker (bold mono, fixed width) | portfolio name (small, muted) | P&L $ | P&L %
- Click on a mover row → navigate to that portfolio
- Color-coded: green rows for top, red rows for bottom
- The `day_change_pct` field on CrossPortfolioMover is the right field to use for "today"

---

## 5. NAVIGATION: INSTANT AND OBVIOUS

**Current issues:**
- Multiple onClick handlers on card sub-elements
- No hover state on cards
- Unclear what's clickable

**Fix:**
- Wrap entire card in a single `<div onClick>` (not nested buttons) except for the delete button
- Add CSS hover state: border color brightens to `--border-2`, slight lift (translateY(-1px)), background to `--surface-2`
- Add `cursor: pointer` to card container
- The delete button stays as an absolutely-positioned overlay
- On click → `setPortfolio(summary.id)` immediately

---

## 6. DAILY WORKFLOW: ATTENTION PANEL

**Morning briefing panel (left column):**

### Attention Needed
Automatically flags:
1. **Error state** — portfolio.error is non-null → red badge
2. **High idle cash** — deployed_pct < 30% → amber badge
3. **No positions** — num_positions === 0 → amber badge

Format: compact list, each item shows portfolio name + reason + one-click navigate

### Morning Briefing Strip (in aggregate bar)
Instead of a separate narrative panel (that would require an extra API call), surface inline:
- "X↑ Y↓ today" — computed from day_pnl > 0 counts
- Deployed gauge bar showing aggregate deployment

---

## What to KEEP, REPLACE, ADD

### KEEP (preserve as-is):
- AggregateBar position and structure (top sticky bar)
- PortfolioCard sparkline component (EquitySparkline)
- PortfolioCard delete functionality with confirmation
- "Scan All" and "Update All" buttons
- "New Portfolio" button
- Scan badge on cards
- ConstellationMap.tsx — keep it, just add as a tab
- PerformanceChart.tsx — keep it, just expose it in overview as a tab
- `setPortfolio()` for navigation
- All TypeScript types (never touch types.ts)

### REPLACE:
- Card grid styling — upgrade hover states, border feedback
- AggregateBar chips — replace Unrealized P&L + Portfolios count with Deployed % + Up/Down counts
- Card P&L row — make day P&L more prominent (larger text, color contrast)
- Card bottom stats — improve readability (slightly larger text)

### ADD:
- Sort controls above grid (sort by: Day P&L | Return | Equity | Deployed | Name)
- Left panel: Attention Needed section (errors, idle cash, no positions)
- Left panel: Top/Bottom movers (using existing top_movers/bottom_movers API data)
- View toggle: GRID | MAP | CHART tabs
- Card hover state (border brightening + subtle lift)
- Card "click anywhere to open" behavior (single onClick zone)
- Up/Down count in aggregate bar
- Deployed % in aggregate bar
- Morning status label in aggregate bar

---

## Implementation Phases

### Iteration 3: Primary View Redesign
- Aggregate bar: add deployed %, up/down counts, remove redundant chips
- Portfolio cards: better hover, clear click target, day P&L more prominent
- Sort controls above grid
- View toggle tabs: GRID | MAP | CHART
- Wire ConstellationMap into MAP tab

### Iteration 4: Movers + Attention + Charts
- Left attention panel: errors, idle cash, no positions
- Top/Bottom movers list (use top_movers/bottom_movers from API)
- Wire PerformanceChart into CHART tab
- Extend PerformanceChart palette to 13+ colors
- Morning summary line in aggregate bar

### Iteration 5: Polish
- Typography consistency
- Loading states
- Empty states
- Hover micro-interactions
- Consistent surface/border hierarchy

---

## Constraints
- No new npm dependencies
- No changes to scripts/, api/, data/, cron/, tests/
- No changes to lib/types.ts
- ConstellationMap changes must be surgical (canvas-based)
- PerformanceChart changes must be surgical (canvas-based)
- Build must pass: `npx tsc --noEmit | grep -v 'CreatePortfolioModal|OverviewPage|PortfolioSettingsModal|TopBar'`

---

## Final Shipped vs Deferred (2026-03-27)

### Shipped

**OverviewPage.tsx — complete redesign:**
- Enhanced AggregateBar: Day P&L promoted to hero (16px bold, colored), deployed % gauge with bar, up/down count (X↑ Y↓), streamlined chip layout
- Sort controls: sort by Day P&L / Return / Equity / Deployed / Name (default: Day P&L desc)
- View toggle tabs: GRID | MAP | CHART (persistent, lazy-loaded via React.lazy + Suspense)
- Left panel: Attention panel — automatically flags error portfolios (red), no positions (amber), idle cash <25% deployed (amber); click to navigate
- Left panel: Movers panel — top_movers and bottom_movers from API now rendered for the first time; top 5 / bottom 5 with ticker, portfolio, P&L %, P&L $; click to navigate
- Portfolio cards: full-card hover state (lift + border brighten + bg shift), single onClick zone, day P&L promoted to 13px bold with day% inline, sparkline gradient ID fix (uses portfolio id not returnPct)
- Card hover: `translateY(-2px)`, border rgba(255,255,255,0.10), bg var(--surface-2), elevated box-shadow
- MAP tab: wires existing ConstellationMap into overview (was never rendered before)
- CHART tab: wires existing PerformanceChart into overview (was never rendered before), passes height=480
- Skeleton loading state (full structured skeleton, not just a spinner)
- Better empty state: larger text, action button directly in empty state
- SideHeader: consistent uppercase label with border-bottom divider

**PerformanceChart.tsx — targeted improvements:**
- Palette extended from 8 to 15 colors — prevents color duplication with 13 portfolios
- `height` prop added (default 340) — overview uses 480px, portfolio view keeps 340px

---

## Map + Chart Redesign (2026-03-27 — Session 2)

### What Shipped

**ConstellationMap.tsx — complete rewrite (physics simulation approach):**
- Replaced solar-system metaphor (portfolios as suns, positions as orbiting planets) with force-directed node network — nodes represent positions, grouped by portfolio via spring forces toward fixed centroids
- Performance-based color encoding: `perf >= +10%` = `#4ade80`, linear gradient through white at 0%, down to `#f87171` at -10%+ — replaces portfolio-color encoding which communicated nothing
- Node sizing: `radius = clamp(sqrt(value/maxValue) * 40 + 8, 8, 48)` — relative to largest position, much wider differentiation range (8px min → 48px max vs old 5-13px)
- Glow encoding: `shadowBlur = 4 + abs(perf) * 0.8` capped at 24 — magnitude of P&L drives glow intensity
- Ticker text inside node face (proportional to radius): when r≥18 shows ticker + perf% on two lines; when r≥8 shows ticker only; smaller nodes show 4-char truncation
- Physics: spring force toward portfolio centroid (strength 0.022), pairwise repulsion (k=800×r_i×r_j), soft boundary walls, damping 0.88 per frame
- Portfolio cluster rings: faint dashed circles around each portfolio group, sized to actual node bounds; portfolioAbbr label above each ring
- Background: `#08090d` with subtle center radial glow, 90-star static star field (seeded, no re-randomization)
- onPositionClick prop added for future position navigation
- Hover: dims others to 0.25 opacity, glassmorphic tooltip with ticker, portfolio name, perf%, value, day%
- nodeKey preserved as `"ticker:portfolioId"` per CLAUDE.md gotcha

**PerformanceChart.tsx — targeted improvements:**
- New palette: 15 distinct medium-saturation hues spaced around color wheel (sky blue, violet, orange, emerald, pink, yellow, teal, rose, lime, blue, purple, green, orange-red, cyan, fuchsia) — replaces neon-saturated palette that made all lines equally loud
- Echo trails removed entirely — they created 39 blur paths per frame and added noise, not signal
- Glow simplified: 1.5px line with `shadowBlur 4` (not three-pass halo up to 22px width) — lines are crisp and distinct
- Hovered series: 3px line, `shadowBlur 10` — clear focus state
- Non-hovered when something is hovered: 0.18 opacity (vs 0.35 before) — stronger dimming for better focus
- Area fill opacity reduced from 0.26 to 0.10 — background zones now breathe
- Zero line: `strokeStyle rgba(255,255,255,0.22)`, `lineWidth 1.5` — visible reference line (was 0.10 and invisible)
- `drawRankStrip` replaced with `drawLegend`: right-side vertical legend, sorted by return desc, 8px color dot + 12-char truncated portfolio name + return %, 10px monospace, fades in with endpoints
- PAD_RIGHT increased from 112 to 148 to accommodate legend
- All dual-zone Y-scale logic preserved unchanged
- All `ctx.save()`/`ctx.restore()` clipping invariants preserved
- `pts.length < 2` guard calls `ctx.restore()` before `continue`

**OverviewPage.tsx — polish:**
- Day P&L card element upgraded: 15px/800-weight with colored tinted background pill (rgba green/red 6%) — most visually dominant element on each card
- CSS fade transition between GRID/MAP/CHART tabs via `animation: fadeIn 0.15s ease`
- `@keyframes fadeIn` added to index.css

### Deferred
- **Narrative/morning briefing panel**: the LogsPage's narrative feature (`/api/system/narrative`) could surface in the overview header. Deferred because it requires an extra API call and the attention panel already covers the "what needs action" use case.
- **Risk score per card**: adding risk score from `/api/{id}/risk` would require 13 extra API calls on overview load — too expensive for a summary view.
- **Real-time day change % on cards**: `day_pnl / equity * 100` approximation is used; exact day_change_pct requires price refresh. Acceptable approximation.
- **Interactive chart filter toggle**: filtering individual series on/off in CHART view. Complex React state interaction with the canvas drawing loop — deferred to avoid risk to the canvas draw invariants.
- **Constellation map portfolio click navigation**: the MAP tab shows suns (portfolios) but sun-click navigation is not wired. The planet hover/detail card already works. Portfolio navigation from MAP view requires adding onClick to the canvas hit-test loop — surgical but deferred.

