# Phase C: Signal Dashboard Redesign

**Date:** 2026-02-26
**Scope:** Full layout restructure, typography system, color separation, component rethink.
**Goal:** A dashboard where positions are the signal and everything else disappears until needed.

---

## Core Principles

1. **One thing at a time.** The screen has a clear primary (positions) and a secondary (focus pane). No four equal panels competing.
2. **Chrome is invisible.** UI structure is defined by background color variation, not borders or decorative elements.
3. **Color encodes meaning only.** Profit is green. Loss is red. Jade appears exactly twice: the ANALYZE button and the selected position. Nothing else is colored.
4. **Data is the hero.** Numbers are large, monospace, tabular. Labels are small, uppercase, muted.
5. **Progressive disclosure.** Show the minimum. Reveal more on demand.

---

## Layout

```
┌──────────────────────────────────────────────────────────┐
│  MARKET TICKER BANNER                                    │  ~28px
├──────────────────────────────────────────────────────────┤
│  TOPBAR  36px, no pill backgrounds, inline text metrics  │
├──────────────────────────┬───────────────────────────────┤
│                          │                               │
│  POSITIONS               │  FOCUS PANE                   │
│  55% width               │  45% width                    │
│  full height             │  context-sensitive            │
│                          │                               │
│  28px rows, always       │  default: portfolio summary   │
│  visible                 │  click position: detail+chart │
│                          │  analyze: results             │
│                          │  risk/perf: those views       │
│                          │                               │
│                          ├───────────────────────────────┤
│                          │  MOMMY STRIP  36px, 1 line    │
│                          │  click → expands into chat    │
└──────────────────────────┴───────────────────────────────┘
```

**No resizable panels.** Fixed 55/45 split via CSS flex. No separator handles.

**ActivityFeed** moves to a slide-over overlay triggered by `F` keyboard shortcut. Not in the primary layout.

---

## Color System

Separates accent (jade) from profit (green). Jade is UI chrome. Green is data.

```css
--color-bg-primary:    #000000   /* true black */
--color-bg-surface:    #080808   /* panels */
--color-bg-elevated:   #101010   /* hover, cards */

--color-border:        #151515   /* barely there */
--color-border-hover:  #222222

--color-accent:        #00D488   /* jade — UI chrome ONLY */
--color-accent-dim:    #003D27

--color-profit:        #4ADE80   /* data: up */
--color-profit-dim:    #14532D
--color-loss:          #F87171   /* data: down */
--color-loss-dim:      #4D0010

--color-warning:       #FBBF24
--color-warning-dim:   #78350F

--color-text-primary:  #EDEDED
--color-text-secondary: #4A4A4A
--color-text-muted:    #282828

/* glow: off. none at rest. */
--shadow-glow-cyan:    none
--shadow-glow-cyan-lg: none
```

**Jade appears exactly twice in the entire UI:**
1. ANALYZE button (solid fill, black text)
2. Left border of selected position row (2px)

---

## Typography System

| Role | Font | Size | Weight | Color |
|------|------|------|--------|-------|
| Portfolio equity (hero) | JetBrains Mono | 32px | 600 | `#EDEDED` |
| Position prices | JetBrains Mono | 13px | 400 | `#EDEDED` |
| Position P&L % | JetBrains Mono | 13px | 600 | profit/loss |
| Position tickers | JetBrains Mono | 13px | 700 | `#EDEDED` |
| Section labels | Inter | 10px | 500 | `#4A4A4A` — uppercase, tracked |
| Body (Mommy) | Inter | 12px | 400 | `#888888` |
| Buttons | Inter | 11px | 600 | varies |

The visual contrast between Mono data and Inter labels IS the hierarchy. No extra color needed.

---

## Component Changes

### TopBar (MODIFY)

Height: `h-9` (36px). No background — uses `bg-bg-surface` to blend.

**Before:** Metric pills (rounded bg containers), colored badges, 48px height.

**After:** Single line of inline text with `·` separators:
```
M MOMMY  |  Micro-Cap ▾  ·  $55,518  −$776  +11.0%  ·  BULL 79  ·  [UPDATE] [SCAN] [ANALYZE]
```

- Remove `MetricPill` component — metrics become plain `<span>` elements
- Remove background and border from `RegimeBadge` — just text + emoji
- Remove background and border from `RiskBadge` — just `Risk 79` text
- ANALYZE: solid jade (`bg-accent text-black`), 3px border-radius
- UPDATE/SCAN: plain text buttons, `text-text-secondary`, hover `text-text-primary`
- CLOSE ALL / PAPER/LIVE: keep semantic colors but no fill, just text

### PositionsPanel (MODIFY)

**Row height:** `h-7` (28px). Currently ~56px. **2× density.**

**New row anatomy (4 columns only):**
```
AEIS   [sparkline]   $329.73   +28.0%   ●
```
- Ticker: `w-12`, `font-mono text-[13px] font-bold text-text-primary`
- Sparkline: `flex-1`, height 22px (new prop on PositionRowSparkline)
- Price: `w-20 text-right`, `font-mono text-[13px] tabular-nums`
- P&L%: `w-14 text-right`, `font-mono text-[13px] font-semibold tabular-nums`, profit/loss color
- Dot: `w-4 flex items-center justify-center` — 6px circle
  - `#4ADE80` (progress > 60%)
  - `#282828` (progress 30-60%)
  - `#F87171` (progress < 30%)

**Row states:**
- Default: `hover:bg-bg-elevated`
- Selected: `bg-bg-elevated border-l-2 border-accent`
- No glow. No bottom border encoding.

**Remove:** qty column, entry price column, day change column, days held column. All in detail pane.

**Column header row** simplified to match: Ticker · Trend · Price · P&L

### PositionRowSparkline (MODIFY)

Accept `height?: number` prop (default 30, new usage passes 22). Width stays 60px.

### FocusPane (CREATE)

Replaces `RightPanel.tsx`. Context-sensitive, driven by store state.

**Priority logic:**
```tsx
if (mommyExpanded) → return null (MommyStrip takes full column)
if (selectedPosition) → <PositionDetail pos={selectedPosition} />
if (isAnalyzing || analysisResult) → <ActionsTab />
if (rightTab === "risk") → <RiskTab />
if (rightTab === "performance") → <PerformanceTab />
default → <PortfolioSummary />
```

**FocusPane header** (replaces tab bar):
- When in default/summary: no header, just content
- When position selected: `← Back` link + ticker name
- When in risk/perf: `← Summary` link + section name

### PortfolioSummary (CREATE)

Default state of FocusPane. Clean, authoritative, data-first.

```
[Summary]  [Risk]  [Performance]     ← 10px Inter text-text-secondary

$55,518                              ← 32px JetBrains Mono
PORTFOLIO EQUITY                     ← 10px Inter uppercase muted

+$3,090 total  ·  −$776 today  ·  +11.0%  ← 13px mono, colored

[30-day equity curve — full width, 64px tall]

──────────────────────────────────────
BULL  ·  Risk 81  ·  13 positions  ·  Paper
──────────────────────────────────────
```

Summary/Risk/Performance links at top navigate FocusPane between views without tabs.

### MommyCoPilot → MommyStrip (MODIFY)

**Collapsed state (always visible, 36px):**
```
● MOMMY  ─  Heads up, sweetheart. Low Win Rate...  [↑]
```
- `●` dot: 6px jade circle (the only ambient jade in the UI)
- Insight text: truncated, 12px Inter, `#888888`
- `[↑]` expand button: small

**Expanded state:** FocusPane column is replaced by full MommyCoPilot (existing implementation, lightly restyled). A `[↓]` button in top-right collapses back.

**Store change needed:** Add `mommyExpanded: boolean` + `toggleMommy()` to UIStore.

### App.tsx (MODIFY)

Remove `react-resizable-panels`. New layout is pure CSS flex:

```tsx
<div className="h-screen flex flex-col bg-bg-primary">
  <MarketTickerBanner />
  <TopBar />
  <div className="flex flex-1 overflow-hidden">
    {/* Left: positions, always 55% */}
    <div className="w-[55%] border-r border-border bg-bg-surface overflow-hidden">
      <PositionsPanel />
    </div>
    {/* Right: focus pane + mommy strip, 45% */}
    <div className="flex-1 flex flex-col bg-bg-surface overflow-hidden">
      {mommyExpanded
        ? <MommyCoPilot />
        : <FocusPane className="flex-1" />
      }
      <MommyStrip />
    </div>
  </div>
  {/* Activity feed slide-over */}
  {activityOpen && <ActivitySlideOver />}
</div>
```

### ActivityFeed → Slide-Over (MODIFY)

Wrap existing `ActivityFeed` in a slide-over overlay:
- Fixed position, left side, `w-72`, full height minus topbar
- Opens/closes with `F` key (add to `useKeyboardShortcuts`)
- Semi-transparent backdrop
- `ESC` also closes it

### store.ts (MODIFY)

Add to UIStore:
- `mommyExpanded: boolean` + `toggleMommy: () => void`
- `activityOpen: boolean` + `toggleActivity: () => void`

### RightPanel.tsx (DELETE)

Functionality absorbed by FocusPane.

---

## Files Summary

| File | Action |
|------|--------|
| `src/index.css` | Update color tokens |
| `src/App.tsx` | New layout, no resizable panels |
| `src/lib/store.ts` | Add mommyExpanded, activityOpen |
| `src/hooks/useKeyboardShortcuts.ts` | Add F key for activity |
| `src/components/TopBar.tsx` | Compress, remove pills |
| `src/components/PositionsPanel.tsx` | 28px rows, 4 cols, dot |
| `src/components/PositionRowSparkline.tsx` | height prop |
| `src/components/FocusPane.tsx` | CREATE — context pane |
| `src/components/PortfolioSummary.tsx` | CREATE — default FocusPane state |
| `src/components/MommyCoPilot.tsx` | Add MommyStrip collapsed mode |
| `src/components/RightPanel.tsx` | DELETE |

**Kept intact (reused inside FocusPane):**
`ActionsTab.tsx`, `RiskTab.tsx`, `PerformanceTab.tsx`, `PositionDetail.tsx`, `ActivityFeed.tsx`, `CandlestickChart.tsx`
