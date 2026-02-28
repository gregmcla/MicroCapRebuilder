# MicroCapRebuilder — Design System

> **Purpose**: This file is the single source of truth for the visual design of MicroCapRebuilder's React frontend. Claude Code should read this file completely before making any visual changes. Every value in here is exact — do not approximate, interpret, or substitute.

---

## 1. Intent (Read Once, Then Forget)

This is a personal quant trading dashboard used by one person for hours at a time. It should feel like a precision instrument — dark, dense, controlled, and rewarding to look at. Not a SaaS product. Not a marketing site. A private command center for someone who enjoys staring at data. Every visual decision serves information density, sustained focus, and the quiet satisfaction of clean structure.

That's the only context you need. Everything below is implementation.

---

## 2. Color Tokens

Use CSS custom properties. Define these at `:root` and reference them everywhere. No hardcoded hex values anywhere in component files.

### Backgrounds (darkest to lightest)

```css
--void:       #0a0a0b;    /* Page background, deepest layer */
--surface-0:  #0e0e10;    /* Sidebar, rail backgrounds */
--surface-1:  #141416;    /* Cards, panels, table backgrounds */
--surface-2:  #1a1a1d;    /* Hover states on cards, input backgrounds on focus */
--surface-3:  #222225;    /* Segmented control tracks, active tab fills, tooltips */
--surface-4:  #2a2a2e;    /* Rare — only for layered elements inside cards */
```

### Borders

```css
--border-0:   rgba(255,255,255,0.05);   /* Default card/panel borders — bumped from 0.035 for visibility */
--border-1:   rgba(255,255,255,0.06);   /* Input borders, dividers */
--border-2:   rgba(255,255,255,0.09);   /* Hover borders, checkbox borders */
--border-3:   rgba(255,255,255,0.13);   /* Focus borders (non-accent) */
```

> **Note on `--border-0`**: The original spec used 0.035 opacity which can be invisible against true `#0a0a0b`. Use 0.05 minimum and test in a dark room before going lower.

### Text

```css
--text-0:     rgba(255,255,255,0.32);   /* Tertiary labels, timestamps, section headers */
--text-1:     rgba(255,255,255,0.48);   /* Secondary text, inactive nav, descriptions */
--text-2:     rgba(255,255,255,0.68);   /* Default body text, table cell text */
--text-3:     rgba(255,255,255,0.88);   /* Emphasized text, active nav items, entity names */
--text-4:     rgba(255,255,255,0.95);   /* Page titles, hero metrics */
```

### Accent — ONE color only

```css
--accent:        #7c5cfc;                    /* Primary accent — buttons, active states, chart strokes */
--accent-bright: #917aff;                    /* Hover states, highlighted values */
--accent-dim:    rgba(124,92,252,0.12);      /* Active chip/tab backgrounds, selected row tints */
--accent-border: rgba(124,92,252,0.25);      /* Focus rings, selected card borders */
--accent-glow:   rgba(124,92,252,0.06);      /* Subtle box-shadow glows */
--accent-cyan:   #5ce0d6;                    /* Chart secondary stroke, gradient endpoints only */
```

**Rule**: `accent-cyan` appears ONLY in chart gradients blended with `accent`. Never as a standalone UI color. Never on buttons, text, or borders.

### Semantic (status indicators only)

```css
--green:      #34d399;
--green-dim:  rgba(52,211,153,0.10);
--amber:      #fbbf24;
--amber-dim:  rgba(251,191,36,0.08);
--red:        #f87171;
--red-dim:    rgba(248,113,113,0.08);
```

**Rule**: Semantic colors appear ONLY inside status pills and P&L values. Green for profit/active. Red for loss/stopped. Amber for pending/caution. Nowhere else.

---

## 3. Typography

### Font Stack

```css
--sans:  'DM Sans', -apple-system, sans-serif;
--mono:  'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
```

Load from Google Fonts:
```
DM Sans: 300, 400, 500, 600 (opsz 9-40)
JetBrains Mono: 300, 400, 500
```

### Usage Rules

| Context | Font | Weight | Size | Color | Extra |
|---------|------|--------|------|-------|-------|
| Page title | --sans | 500 | 17px | --text-4 | letter-spacing: -0.015em |
| Section label (sidebar, rail) | --sans | 600 | 9px | --text-0 | uppercase, letter-spacing: 0.13em |
| Nav item | --sans | 500 | 11px | --text-1 (inactive), --accent-bright (active) | |
| Card label | --sans | 500 | 9.5px | --text-0 | uppercase, letter-spacing: 0.08em |
| Body text | --sans | 400 | 12px | --text-2 | |
| Table header | --sans | 500 | 9.5px | --text-0 | uppercase, letter-spacing: 0.08em |
| Table cell | --sans | 400 | 11.5px | --text-2 | |
| **All numbers** | **--mono** | 400 | 11px | --text-2 | **font-variant-numeric: tabular-nums** |
| Hero metric | --mono | 300 | 22px | --text-4 | font-variant-numeric: tabular-nums |
| Stock ticker | --mono | 500 | 11px | --text-3 | uppercase |
| Timestamp | --mono | 400 | 9.5px | --text-0 | font-variant-numeric: tabular-nums |
| P&L value | --mono | 400 | 11px | --green or --red | font-variant-numeric: tabular-nums |
| Keyboard hint | --mono | 400 | 8.5px | --text-0 | border: 1px solid --border-1, border-radius: 3px, padding: 1px 4px |

**Non-negotiable**: Every number, price, percentage, timestamp, score, and factor value uses `--mono` with `font-variant-numeric: tabular-nums`. No exceptions. This ensures columns of numbers align perfectly.

**Max heading size**: 17px for page titles. Nothing in the UI exceeds 22px (hero metrics only). If it feels like you need bigger text, you don't — use weight and opacity instead.

---

## 4. Spacing & Layout

### Base Grid

```css
html { font-size: 13px; }
```

### Three-Column Layout

```
┌──────────────────────────────────────────────────┐
│           MARKET TICKER BAR (36px)                │
├──────────────────────────────────────────────────┤
│                    TOPBAR (48px)                   │
├────────┬─────────────────────────┬────────────────┤
│SIDEBAR │      MAIN CONTENT       │   RIGHT RAIL   │
│232px   │     flex (scrollable)   │    312px       │
│fixed   │                         │    fixed       │
└────────┴─────────────────────────┴────────────────┘
```

```css
.layout {
  display: grid;
  grid-template-columns: 232px 1fr 312px;
  height: calc(100vh - 36px - 48px);
}
```

The market ticker bar sits above everything. The topbar holds the command palette and action buttons. The three-column grid is the workspace.

### Sidebar Behavior

The sidebar is collapsible. It is not just navigation — it also holds ambient awareness data (portfolio list, watchlist count, last scan time, strategy health, system state) that is useful to see persistently without clicking.

- **Default expanded** (232px): screens ≥ 1600px wide
- **Default collapsed** (48px icon rail): screens < 1600px
- **Toggle**: user-controlled, persisted to `localStorage`
- **Collapsed state shows**: portfolio icon, nav icons, strategy health grade dot only — no labels
- **Transition**: `width` animates with the standard easing curve, 0.35s

When collapsed, the layout grid column shrinks to 48px. Main content and right rail expand to fill.

### Spacing Scale

Use these values only. Do not invent intermediate values.

```
4px   — icon-to-text gap, badge internal padding
6px   — chip gap, tight element spacing
8px   — card internal section spacing, small gaps
10px  — grid gap between cards
12px  — card padding (compact), section margin
14px  — card padding (standard), table cell padding
16px  — card padding (comfortable)
18px  — section-to-section margin in main content
20px  — main content page padding
```

### Border Radius

```css
--radius:    8px;    /* Cards, panels, dropdowns */
--radius-sm: 6px;    /* Buttons, inputs, segmented controls */
--radius-xs: 4px;    /* Tabs, sidebar items, small elements */
```

**Rule**: Nothing in the UI has a radius above 8px except pills (border-radius: 9999px for status pills and filter chips).

---

## 5. Component Patterns

### Cards

```css
.card {
  background: var(--surface-1);
  border: 1px solid var(--border-0);
  border-radius: var(--radius);
  padding: 14px 16px;
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.card:hover {
  transform: translateY(-1px);
  border-color: var(--border-1);
  background: linear-gradient(to bottom, var(--surface-2), var(--surface-1));
}
```

**Rule**: Cards hover up by exactly 1px. No more. No box-shadow on hover. The elevation change is communicated through the border-color shift and the gradient background.

### Metric Cards (Position cards, factor scores, strategy health)

```
┌─────────────────────────┐
│ LABEL              9.5px│  ← uppercase, --text-0
│ $14,832.40        22px  │  ← --mono, --text-4
│ +12.4%            10px  │  ← green pill or red pill
│ ▁▂▃▅▃▆▅▇         36px  │  ← sparkline SVG
└─────────────────────────┘
```

Sparklines use SVG polyline with `stroke: var(--accent)`, `stroke-width: 1.5`, `stroke-linecap: round`. Area fill uses a vertical gradient from `rgba(124,92,252,0.15)` to `transparent`. Last data point gets a dot with `filter: drop-shadow(0 0 3px rgba(124,92,252,0.6))`.

### Buttons

**Primary** (SCAN, ANALYZE, UPDATE, EXECUTE):
```css
background: var(--accent);
color: #fff;
height: 30px;
padding: 0 14px;
border-radius: var(--radius-sm);
font-size: 11.5px;
font-weight: 500;
box-shadow: 0 0 12px rgba(124,92,252,0.15);
```
Hover: `background: var(--accent-bright); box-shadow: 0 0 24px rgba(124,92,252,0.3); transform: translateY(-1px);`

**Ghost** (secondary actions):
```css
background: transparent;
border: 1px solid var(--border-1);
color: var(--text-1);
height: 30px;
```
Hover: border brightens, text brightens, faint `var(--surface-1)` background.

### Filter Chips

```css
height: 26px;
padding: 0 10px;
border-radius: 13px;  /* pill shape */
border: 1px solid var(--border-1);
background: transparent;
font-size: 11px;
```

Active state:
```css
border-color: var(--accent-border);
color: var(--accent-bright);
background: var(--accent-dim);
```

### Tables (Positions, Watchlist, Trade Proposals)

- Header: 9.5px uppercase, `--text-0`, sticky top
- Rows: 1px `--border-0` dividers, hover background `rgba(255,255,255,0.012)`
- Selected row: `background: rgba(124,92,252,0.03)` with `box-shadow: inset 3px 0 0 var(--accent)` on first cell
- Expandable rows: clicking a position opens a detail panel below with `max-height` transition
- All number columns right-aligned, `--mono`, tabular-nums

### Status Pills

```
┌─ Active ──┐   ┌─ Stopped ──┐   ┌─ Pending ──┐
│ ● Active  │   │ ● Stopped  │   │ ● Pending  │
└───────────┘   └────────────┘   └────────────┘
```

```css
display: inline-flex;
align-items: center;
gap: 4px;
padding: 2px 8px;
border-radius: 10px;
font-size: 10.5px;
font-weight: 500;
```

- Active/Profit: `background: var(--green-dim); color: var(--green);` dot gets `box-shadow: 0 0 6px rgba(52,211,153,0.5)`
- Stopped/Loss: `background: var(--red-dim); color: var(--red);`
- Pending/Review: `background: var(--accent-dim); color: var(--accent-bright);` dot gets glow

### Sidebar Navigation

- Active item: 3px vertical bar on left edge, `background: rgba(124,92,252,0.05)`, text `--text-3`, icon tinted `--accent-bright`
- Active bar: `width: 3px; border-radius: 0 2px 2px 0; background: var(--accent); box-shadow: 0 0 12px rgba(124,92,252,0.4);`
- Inactive: text `--text-1`, icon opacity 0.4
- Section labels: 9px uppercase, `--text-0`, letter-spacing 0.13em

### Inputs (Search/Command)

```css
background: var(--surface-1);
border: 1px solid var(--border-1);
border-radius: var(--radius);
height: 32px;
font-size: 11.5px;
color: var(--text-2);
```

Focus state:
```css
border-color: var(--accent-border);
box-shadow: 0 0 0 3px rgba(124,92,252,0.06), 0 0 30px rgba(124,92,252,0.05);
background: var(--surface-2);
```

---

## 6. Charts & Data Visualization

### Line Charts (Price charts, portfolio performance)

- Primary stroke: `linear-gradient` from `var(--accent)` to `var(--accent-cyan)`, stroke-width 2, stroke-linecap round
- Secondary stroke: same gradient reversed, stroke-width 1.5, opacity 0.4
- Area fill: vertical gradient from `rgba(124,92,252,0.1)` at top to `transparent` at bottom
- Grid lines: `rgba(255,255,255,0.025)`, stroke-width 1
- Axis labels: `--mono`, 9px, `--text-0`, tabular-nums
- Hover crosshair: dashed vertical line `rgba(124,92,252,0.2)`, dot on data point with glow
- Animate on mount: `stroke-dashoffset` technique, 2s duration, `cubic-bezier(0.16, 1, 0.3, 1)` easing

### Bar Charts (Volume, factor scores)

- Default: `rgba(124,92,252,0.12)` fill
- Hover: `rgba(124,92,252,0.3)`
- Current/latest bar: solid `var(--accent)` with `box-shadow: 0 0 6px rgba(124,92,252,0.3)`
- Staggered entrance animation: each bar animates height from 0, 20ms offset between bars

### Score Bars (Factor scores, confidence)

```
0.94  ████████████████████░░░
```

```css
width: 40px; height: 3px;
background: var(--surface-3);
border-radius: 2px;
```

Fill: `linear-gradient(90deg, var(--accent), var(--accent-cyan))` with width set to score percentage.

### Donut Charts (Portfolio allocation, strategy breakdown)

- SVG stroke-based rings, NOT filled wedges
- `stroke-width: 5; stroke-linecap: round;`
- Segments separated by small gaps via `stroke-dasharray`
- Center text: `--mono`, 14px, `--text-3` for total value
- Animate on mount: `stroke-dashoffset` transition

---

## 7. Motion

### One Easing Curve

```css
cubic-bezier(0.16, 1, 0.3, 1)
```

Use this for everything. Fast entry, gentle settle. This is the only easing curve in the system.

### Duration Scale

| Action | Duration |
|--------|----------|
| Hover color/border change | 0.2s |
| Card lift on hover | 0.35s |
| Panel expand/collapse | 0.4s |
| Sidebar collapse/expand | 0.35s |
| Chart stroke draw | 2.0s |
| Cascade load stagger | 30ms per element |
| Toast enter/exit | 0.5s |

### Cascade Loading

On page mount, elements fade up with stagger:

```css
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

.anim { animation: fadeUp 0.55s cubic-bezier(0.16, 1, 0.3, 1) both; }
.d1 { animation-delay: 30ms; }
.d2 { animation-delay: 60ms; }
.d3 { animation-delay: 90ms; }
/* ... increment by 30ms */
```

### Count-Up Animation

All hero metric values animate from 0 to their target value on mount. Duration 1.2s, cubic ease-out. Large numbers get `toLocaleString()` formatting during animation. Prices get proper decimal formatting.

### What NOT to Animate

- No bounce effects
- No spring physics
- No looping animations except live status indicators
- No decorative motion
- No entrance animations on scroll (only on page mount)

---

## 8. Scrollbar

```css
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.06); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.12); }
```

---

## 9. MicroCapRebuilder-Specific Components

### Market Ticker Bar

Persistent bar above everything showing major market indices with inline sparklines.

```
     S&P 500  6,878.88  -0.43% ∿∿  |  Russell 2000  2,632.36  -1.68% ∿∿  |  VIX  19.86  +6.60% ∿∿
```

- Background: `var(--surface-0)`, height 36px, fixed top, full width, z-index above layout
- Border-bottom: `var(--border-0)`
- Index name: `--sans`, 10px, `--text-0`, uppercase
- Index price: `--mono`, 12px, `--text-3`, tabular-nums
- Change %: `--mono`, 10.5px, `--green` or `--red`
- Inline sparkline: 48px wide, 16px tall, `stroke-width: 1.5`, `stroke-linecap: round`. Stroke color matches change direction (green/red). No fill, no axes
- Items centered horizontally with `gap: 40px`
- Data source: `/api/market/indices` polled every 60s during market hours

### Position Row (Data columns — do not change)

```
☐  AEIS  [sparkline]  $335.57  +$3.51 +1.0%  +$1,521 +31.1%  ●
    ticker  trend       price    day P&L        overall P&L     dot
```

**The six columns are fixed and must not be changed.** They were deliberately chosen and represent significant prior work:

| Column | Content | Font | Notes |
|--------|---------|------|-------|
| Ticker | Symbol (e.g. AEIS) | --mono 500 11px --text-3 | uppercase |
| Trend | Sparkline (40 days) | SVG | max-width 140px, accent stroke |
| Price | Current price | --mono --text-2 | tabular-nums |
| Day P&L | Two lines: $ change / % change | --mono | green or red, tabular-nums |
| Overall P&L | Two lines: $ total / % total | --mono | green or red, tabular-nums |
| Dot | Stop/target range indicator | SVG dot | green >60%, amber 30-60%, red <30% |

Row height: 40px. Apply design tokens to these columns — do not replace them with different data.

### Trade Proposal Card (AI Review)

```
┌──────────────────────────────────────────────────┐
│ BUY  AMBA  Ambarella Inc                  0.87   │
│                                                  │
│ AI Verdict: APPROVED                             │
│ "Strong momentum convergence with volume         │
│  confirmation. RSI exiting oversold zone..."      │
│                                                  │
│ Entry: $62.40   Stop: $58.10   Target: $71.80    │
│                                                  │
│ [Approve]  [Modify]  [Veto]                      │
└──────────────────────────────────────────────────┘
```

- Card border: `var(--accent-border)` when AI-approved, `var(--amber)` at 0.25 opacity when modified, `var(--red)` at 0.15 opacity when vetoed
- "AI Verdict" label: 9.5px uppercase, `--text-0`
- Verdict value: `--mono`, `--accent-bright` for approved, `--amber` for modified, `--red` for vetoed
- AI reasoning text: `--sans`, 11.5px, `--text-1`, italic
- Entry/Stop/Target: `--mono`, tabular-nums, arranged in a 3-column mini grid

### Factor Score Display

```
Momentum      ████████░░  0.82
RelStrength   ██████░░░░  0.61
Volatility    ███░░░░░░░  0.34
Volume        █████████░  0.91
MeanRevert    ██████████  0.97
RSI           ███████░░░  0.73
```

Each factor: label in `--sans` 10.5px, bar 40px wide using the score bar pattern, value in `--mono` 10.5px. Highlight the strongest factor with `--accent-bright` text. Weakest factor in `--text-0`.

### Strategy Health Grade

Display as a single large letter (A+, B, C-) in `--mono`, 18px, centered in a small card. Color mapped:
- A+/A: `--green`
- B+/B: `--accent-bright`
- C+/C: `--amber`
- D or below: `--red`

### "Mommy" AI Co-pilot

Persistent bar pinned to the bottom of the viewport. Always visible.

```
● MOMMY — Heads up, sweetheart. Low Win Rate. Review entry criteria and consider factor weight adjustme...  ↑
```

- Background: `var(--surface-0)`, height 40px, border-top `var(--border-0)`
- Green dot: live indicator with `livePulse` animation
- "MOMMY" label: `--mono`, 10px, `--text-0`, uppercase
- Commentary text: `--sans`, 11.5px, `--text-1`, italic. Single line, truncated with ellipsis
- Expand arrow on right edge to reveal full message panel
- When flagging something urgent: left border flashes once with `--accent` or `--amber` glow (no looping)

### Portfolio Selector (Multi-portfolio switching)

Segmented control at top of main content. Each portfolio name in a segment button. Active portfolio gets `--surface-3` background with `--text-3` text. Inactive gets `--text-1`.

---

## 10. Non-Negotiable Rules

1. **No bright backgrounds.** The lightest surface in the entire system is `#2a2a2e`.
2. **No second accent color.** Violet is the only saturated hue. `accent-cyan` is a gradient endpoint only.
3. **No type larger than 22px.** Hero metrics max. Everything else is smaller.
4. **No border-radius above 8px** except pills.
5. **No box-shadow for elevation.** Use border-color shifts and background gradients.
6. **No decorative elements.** No illustrations, no ornamental gradients, no background patterns.
7. **All icons outline-only.** stroke-width 1.5, stroke-linecap round. Never filled.
8. **All numbers in monospace with tabular-nums.** No exceptions.
9. **One easing curve.** `cubic-bezier(0.16, 1, 0.3, 1)` everywhere.
10. **Dense, not cramped.** If spacing feels tight, check the spacing scale. Don't add arbitrary padding.
11. **No competing visual weight.** Only one element on screen should glow or pulse at any given time.
12. **Green and red are for money only.** Profit/loss, active/stopped. Not for buttons, not for decoration.
13. **Position row columns are fixed.** Do not change what data appears in position rows. Apply tokens to existing columns only.

---

## 11. Implementation Notes for Claude Code

- Define all tokens in `index.css` under `@theme` (Tailwind v4) or `:root`. Reference tokens everywhere — no hardcoded hex in component files.
- If applying to existing components, work file by file. Don't try to refactor everything at once.
- Start with color tokens and typography, then move to component patterns.
- The sidebar collapse behavior must persist to `localStorage` under key `sidebar-collapsed`.
- The market ticker bar is a new component — data comes from `/api/market/indices` (already exists), poll every 60s.
- Test in a dark room. The contrast ratios are calibrated for low-light viewing.
- If something feels "off," the answer is almost always: reduce contrast, reduce size, or reduce spacing. This system errs toward subtlety.
- When in doubt about a value, refer back to this document. Do not approximate.
