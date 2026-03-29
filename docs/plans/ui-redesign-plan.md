# UI Redesign Plan — GScott Dashboard
**Date:** 2026-03-27
**Status:** PLANNED → IN PROGRESS

---

## Philosophy

This is a mission control panel for one person managing 13 portfolios daily. The design language is dark/terminal/matrix-inspired. The redesign amplifies this — not softens it. Changes target:

1. **Speed of information consumption** — reduce time-to-insight on every open
2. **Action hierarchy** — make ANALYZE and EXECUTE impossible to miss
3. **Visual coherence** — one accent color family, one type scale, one border language
4. **Readable text** — eliminate sub-9px text from interactive surfaces

---

## Information Hierarchy: What Should Dominate

### Tier 1 — Always dominant, always legible
- The treemap (portfolio positions)
- Open P&L (is the portfolio up or down today?)
- ANALYZE / EXECUTE buttons (primary CTAs)

### Tier 2 — Important, secondary visual weight
- Equity value (the absolute number)
- Position detail: trade thesis, stop/target
- Regime and risk score

### Tier 3 — Ambient/contextual, low visual weight
- Market indices (S&P, VIX)
- Cash remaining
- All-time P&L
- Benchmark alpha
- Scan status, freshness

---

## Layout Changes

### TopBar: From 72px to 48px

**Current:** Logo | Portfolio+Freshness | VDivider | Indices | VDivider | Controls
**New:** Logo (32px) | Portfolio switcher (compact) | ∙ | Day P&L | Equity | VDivider | Indices (condensed) | VDivider | ANALYZE | EXECUTE | VDivider | Regime | Risk | SCAN | UPDATE | LOGS | Mode

**Key changes:**
- Height: 72px → 48px (recover 24px for the treemap)
- Move ANALYZE and EXECUTE to the TopBar, right of center divider — they are the primary actions and belong at the top
- The equity figure and day P&L move into TopBar (were previously in the strip below)
- Market indices: remove sparklines from TopBar to save space — just value + % change
- The `LOGS` button gets the same accent/ghost style as everything else (currently zinc-colored orphan)
- The PortfolioSummary strip below can then be simplified dramatically

### PortfolioSummary Strip: From 68px dense strip to 44px thin strip

With equity/P&L/Analyze/Execute moved to TopBar, the strip below can be a secondary context bar:
- All-time P&L | Open P&L | Cash | Positions | Benchmarks (SPX/NDX/RUT alpha) | Regime | Risk | Stale count

This becomes a quick-glance status row, not a primary action surface.

The CommandBar (`UpdateButton`, `ScanButton`, `AnalyzeExecute`) currently imported into PortfolioSummary moves to TopBar. The strip then imports only display metrics.

### MatrixGrid: Give it max height

With TopBar at 48px and PortfolioSummary at 44px, the treemap gains 48px more vertical space. On a 900px viewport that's a ~5% gain in treemap real estate — meaningful for seeing smaller positions.

### BottomPanel: Increase readable text sizes

The BottomPanel detail view is the secondary daily task (read thesis, check stop/target). Minimum sizes:
- Section labels: 6px → 9px (font-mono, uppercase, text-muted)
- Body text (company description, AI reasoning): 7-8px → 11px
- Stat values: 9-11px → 12px
- Ticker: keep at 28px
- P&L %: keep at 26px

The panel height stays at 280px (correct for the content volume).

---

## Visual Language

### Typography Scale (enforced, not scattered)

```
xs:    9px  — labels, badges, hints (minimum readable size)
sm:    11px — secondary data, stat values, tab labels
base:  13px — primary body text, AI reasoning, position detail
md:    15px — section headers, metric values
lg:    20px — secondary hero numbers
xl:    24px — hero data (equity, major P&L)
xxl:   32px — accent/dominant (ticker in detail panel)
```

**Rule:** Nothing interactive or informational below 9px. Decorative hints (keyboard shortcuts, status bar at bottom) can go to 8px.

### Color System: Resolve the Green vs Violet Conflict

The MatrixGrid uses `#4ade80` green everywhere. The rest uses `#7c5cfc` violet. Fix:

**Keep the green for:**
- Positive P&L values (`--color-profit`)
- Treemap cell backgrounds (positive positions)
- EKG strip, waveform, atmospheric effects within the treemap
- Boot terminal (it IS the Matrix)
- The treemap tab active state (green fits the matrix aesthetic of the GRID view)

**Use violet for:**
- ALL tab bars outside the treemap (actions, watchlist, activity, logs tabs within MatrixGrid)
- All action buttons (UPDATE/SCAN/ANALYZE/EXECUTE) — currently correct, keep it
- All badges and decision indicators in ActionsTab
- TopBar border, accent highlights

**New rule for MatrixGrid tabs:**
- PORTFOLIO tab active: green (matrix green, it's the treemap)
- ACTIONS tab active: violet (it's the AI/analysis system)
- WATCHLIST tab active: amber (it's discovery/opportunity)
- ACTIVITY tab active: violet (same system as actions)

This creates meaningful color-function mapping instead of everything being green.

### Surface Hierarchy

```
void (#0a0a0b):    App background
surface-0 (#0e0e10): PortfolioSummary, ActivityFeed, panel backgrounds
surface-1 (#141416): Cards, BottomPanel, ActionsTab cards
surface-2 (#1a1a1d): Hover states, selected states
surface-3 (#222225): Active badges, elevated surfaces
```

**Rule:** Do not apply `border` to every `div`. Borders reserved for:
1. Section dividers (1px `border-b border-border`)
2. Card outlines (1px `border-border`)
3. Active/hover states (color-coded)

The current MatrixGrid cell boxes have `inset 0 1px 0 rgba(255,255,255,0.05), inset 0 0 0 1px rgba(255,255,255,0.02)` as box-shadow — this is fine and subtle.

### Spacing System

Enforce consistent gaps:
- **Tight**: 4px — within stat groups, icon+label
- **Normal**: 8px — between elements in a row
- **Section**: 16px — between sections
- **Panel**: 20px — panel padding (keep existing)

---

## Component-by-Component Plan

### TopBar.tsx

**Changes:**
- Height: 72px → 48px
- Add `dayPnl` and `totalEquity` display between portfolio switcher and indices
  - Pull from `state` prop (already passed in as PortfolioState)
  - Format: `$XX,XXX` equity | `+$XXX` day P&L (color-coded)
- Move `UpdateButton`, `ScanButton`, `AnalyzeExecute` from CommandBar/PortfolioSummary into TopBar right section
- `LogsButton`: apply same ghost button style as other buttons, not the zinc orphan style
- Remove sparklines from IndexTile — just show value + % change (saves ~56px width per tile)
- Market indices font: 12px value, 9px % change (currently 14px + 11px — disproportionate)
- TopBar border: keep the violet accent bottom border — it's a good grounding element

**Do not change:** The modal dialogs (EmergencyClose, ModeToggle) — they work fine. The PortfolioSettingsModal button stays.

### PortfolioSummary.tsx

**Changes:**
- Height: 68px → 44px
- Remove: day P&L (moved to TopBar)
- Remove: equity figure (moved to TopBar)
- Remove: action buttons (moved to TopBar)
- Keep: Open P&L | All-Time P&L | Return % | Cash | Benchmarks (SPX/NDX/RUT alpha) | Regime | Risk | Position count
- Rename visual role: this is now a "context strip" not an "action bar"
- Label size: 8.5px → 9px (slight improvement)
- Metric value size: 12px → 13px (one step up)

**Do not change:** The animated equity counter — move it to TopBar instead of removing.

### MatrixGrid Tab Bar

**Changes:**
- Active tab color rules:
  - PORTFOLIO: keep green (`#4ade80`) — fits the matrix aesthetic
  - ACTIONS: violet (`var(--accent-bright)`) with violet bottom indicator
  - WATCHLIST: amber (`var(--amber)`)
  - ACTIVITY: violet
  - LOGS: text-secondary
- Tab label font: 8px → 10px (still compact, but readable)
- ACTIONS tab badge behavior: when analysis results are ready, apply accent glow pulse to the ACTIONS tab button (currently amber, change to violet pulsing glow)

### BottomPanel.tsx

**Changes:**
- Section labels (6px → 9px): ENTERED, DAY %, VOL, BETA, VALUE, PRICE, SHARES, AVG COST, STOP, TARGET, MKT CAP, P/E, 52W, ANALYST, DIV, SOCIAL
- Company description text (8px → 11px)
- Stats grid values (9-11px → 12px)
- AI reasoning text in TradeThesis (7-8px → 11px)
- Factor bar labels in TradeThesis (6px → 9px)
- Factor bar values (8px → 10px)
- The bottom hint "ESC OR ✕ TO CLOSE" (7px): keep at 8px, it's decorative

**Do not change:** Layout (3-column grid, heights, accent color system, reticle animation).

### TradeThesis.tsx

**Changes:**
- Header label "TRADE THESIS" / "EXIT THESIS": 6px → 9px
- Decision badge: 7px → 10px
- Factor labels: 6px → 9px
- Factor values: 8px → 10px
- Regime/confidence labels: 6px → 9px
- Regime/confidence values: 8px → 10px
- AI reasoning text: 8px → 11px (main readable content — this is critical)
- Sell reasoning text: 8px → 11px

### ActionsTab.tsx

**Changes:**
- `PreFlightDashboard` section labels: 9px → 10px (already decent)
- Watchlist candidates CandidateRow: keep existing sizes (11px ticker, 11px score — readable)
- The main ANALYZE button at bottom of PreFlight: good as-is
- `sectionHeaderStyle` (9.5px): keep — already readable
- ActionCard AI reasoning text: font size already 12px (fine), but remove `italic` — hard to read italic at small sizes in dark themes

### ActivityFeed.tsx (slide-over)

**No structural changes.** The component itself is clean. The orphan issue (no trigger button) is fixed by ensuring the keyboard shortcut is documented or a trigger exists. The MatrixGrid has an ACTIVITY tab with `ActivityPanel` — these serve the same data differently. Keep both: MatrixGrid's ACTIVITY tab for inline context, the slide-over for larger reading.

### LogsButton in TopBar

**Change:** Apply `ghostBtn` style (same as rest of TopBar) instead of zinc orphan style.

---

## What Stays Exactly the Same

- **MatrixGrid treemap cell rendering** — squarified layout, parallax, glitch, anomaly effects
- **BackgroundCanvas** — particle system
- **EKGStrip** — portfolio vitals strip
- **TickerTape** — scrolling position tape
- **Boot sequence terminal** — atmospheric, distinctive
- **All modal dialogs** (EmergencyClose, ModeToggle, CompanyInfoModal, PortfolioSettingsModal)
- **BottomPanel layout structure** — 3-column grid, accent color logic, slide-up animation
- **ActivityFeed data and interaction** — expandable rows, date grouping, P&L display
- **All API calls and data contracts** (lib/types.ts, lib/api.ts)
- **All keyboard shortcuts**
- **ConstellationMap** (overview page)
- **PerformanceChart** (performance tab)
- **Sidebar.tsx** and navigation structure
- **CommandBar component definitions** — kept for reuse, just relocated
- **CSS variable definitions in index.css** — extend, do not replace

---

## Implementation Sequence

### Iteration 3: Core Layout + Information Hierarchy
1. Shrink TopBar to 48px, add equity/dayPnl display
2. Move ANALYZE/EXECUTE/UPDATE/SCAN into TopBar
3. Strip PortfolioSummary down to context-only strip (44px)
4. Fix LogsButton style consistency

### Iteration 4: Matrix Grid + Activity
1. Fix tab bar color coding (actions→violet, watchlist→amber, portfolio→green)
2. Increase tab bar font size (8px → 10px)
3. Improve BottomPanel text sizes (minimum 9px labels, 11px body)
4. TradeThesis text size fixes

### Iteration 5: Typography, Spacing, Visual System
1. Systematic pass: every component, raise minimum readable sizes
2. Enforce spacing tokens (no random `gap: 14px` vs `gap: 16px` vs `gap: 12px`)
3. Polish hover states and empty states
4. Fix color inconsistencies (zinc in LogsButton, random greens in non-matrix contexts)

---

## Implementation Status

- [x] Audit complete
- [x] Design document written
- [x] Iteration 3: Core layout — TopBar redesigned (72px→48px), equity/day P&L + action buttons moved to TopBar, PortfolioSummary stripped to 44px context bar
- [x] Iteration 4: Matrix Grid + Activity — Tab bar color-coded (grid=green, actions=violet, watchlist=amber), tab font 8px→10px, BottomPanel text sizes raised (6px labels→9px, 7-8px body→11px), TradeThesis text sizes raised
- [x] Iteration 5: Typography + Visual System — Consistency pass across MatrixGrid controls, hover panel, WatchlistPanel, ActivityPanel, LogsPanel; minimum readable size enforced at 9px labels, 11px body
- [x] Iteration 6: TypeScript verification — ZERO errors (tsc --noEmit clean), Vite production build passes in 823ms

---

## Final Implementation Summary

### What Was Implemented

**TopBar (TopBar.tsx) — complete redesign:**
- Height: 72px → 48px (recovered 24px for treemap real estate)
- Added `PortfolioStats` component: equity + day P&L displayed inline between switcher and indices
- Moved UPDATE/SCAN/ANALYZE/EXECUTE buttons from PortfolioSummary into TopBar right section
- `LogsButton` rewritten with ghost button style matching the rest of the app (was using zinc color scheme, now uses violet accent system)
- Market indices condensed: removed sparklines (saved ~56px per tile), reduced font sizes (14px→12px value, 11px→10px %)
- `FreshnessIndicator` placed compactly between equity and divider

**PortfolioSummary.tsx — simplified to context strip:**
- Height: 68px → 44px
- Removed: equity figure (moved to TopBar), day P&L (moved to TopBar), action buttons (moved to TopBar)
- Kept: Open P&L, All-Time P&L, Return %, Cash, Benchmarks (SPX/NDX/RUT alpha), Regime, Risk score, Position count
- All metric values bumped from 12px to 13px; labels from 8.5px to 9px

**MatrixGrid tab bar — color-coded system:**
- PORTFOLIO tab: green (#4ade80) — matrix aesthetic preserved
- ACTIONS tab: violet (#917aff) — AI/analysis system color
- WATCHLIST tab: amber (#fbbf24) — discovery/opportunity color
- ACTIVITY tab: violet — same system as actions
- LOGS tab: muted gray
- Tab font: 8px → 10px
- ACTIONS pending state: amber (was previously the same)

**BottomPanel (BottomPanel.tsx) — readability overhaul:**
- All 6px section labels → 9px
- Company description: 8px → 11px
- Stats grid values: 9-11px → 12px
- Stop/Target labels: 6px → 9px, values: 11px → 12px, distances: 7px → 9px
- Social heat labels: 6px → 9px, values: 10px → 11px
- Company name: 10px → 12px
- Industry: 8px → 10px
- Info stats (P/E, 52W, etc.): 6px labels → 9px, 9px values → 11px
- Portfolio/sector line: 9px → 10px, Entry date: 7px → 9px
- Day%, Day$, Vol, Beta labels: 6px → 9px, values: 11px → 12px

**TradeThesis.tsx — readability overhaul:**
- Header label: 6px → 9px
- Decision badge: 7px → 9px
- Factor labels: 6px → 9px, values: 8px → 10px
- Regime/confidence labels: 6px → 9px, values: 8px → 10px
- AI reasoning body text: 8px → 11px (critical — this is the main content)
- Sell reasoning body text: 8px → 11px

**MatrixGrid controls/panels — consistency pass:**
- Stats labels: 6px → 9px, values: 11px → 12px
- Sort button labels: 8px → 9px, shortcut hints: 6px → 8px
- Status bar: 7px → 8px, color lightened from #555 to #444
- Hover detail panel stat labels: 6px → 9px, values: 11px → 12px
- PORTFOLIO VITALS label: 7px → 8px
- WatchlistPanel header row: 7px → 9px, row content: 9px → 11px (notes/sector/source: 8px → 10px)
- ActivityPanel header row: 7px → 9px, reasoning text: 8px → 11px
- LogsPanel labels: 7px → 9px, status: 9px → 11px, stat values: 14px → 15px, timestamps: 8px → 10px, sector bars: 7px → 10px

**ActionsTab.tsx:**
- AI reasoning: removed `italic` style (hard to read italic at small sizes in dark theme)

### What Was Deferred and Why

**EquityCurve Fourier component** — still not rendered anywhere. The component is complete and works. Adding it to the UI would require choosing a placement (PortfolioSummary has no room now at 44px; TopBar has no room). Best placement would be as an expandable panel or the overview page. Deferred because there is no natural home in the current layout without introducing a new expandable section.

**Activity feed slide-over** — still has no visible trigger button (toggle exists in store, but no button calls it). The MatrixGrid ACTIVITY tab serves the same data. This is a low-priority orphan. Deferred.

**Portfolio keyboard cycling** — would require changes to PortfolioSwitcher and key handler logic. Not critical. Deferred.

**Sell reasoning annotations on treemap cells** — the data is available (`pendingSellReasoningMap`), but adding overlays to treemap cells would require changes to cell rendering. Deferred for a future focused iteration.

**Cell hover state refinement** — the `.matrix-cell:hover { background: linear-gradient(to bottom, #1e4a2e, #163826) }` is inline `<style>` in MatrixGrid which makes it hard to update. Works correctly, just can't be changed to violet without a CSS-in-JS refactor. Deferred.
