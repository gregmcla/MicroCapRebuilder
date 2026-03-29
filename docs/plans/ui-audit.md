# UI Audit — GScott Dashboard
**Date:** 2026-03-27
**Auditor:** Claude Sonnet 4.6

---

## 1. Layout Overview

The dashboard has three primary "modes" determined by `activePortfolioId`:

- **overview** → `OverviewPage` (constellation map + portfolio cards)
- **logs** → `LogsPage`
- **any portfolio** → `PortfolioSummary` strip + `MatrixGrid` (full screen)

The main daily workflow always lands on portfolio mode. The layout is:

```
TopBar (72px, always visible)
└── PortfolioSummary (68px strip)
    └── MatrixGrid (fills remaining height)
        ├── EKGStrip (48px)
        ├── TickerTape (variable)
        ├── Controls row (sort/filter)
        ├── Tab bar (PORTFOLIO / ACTIONS / WATCHLIST / ACTIVITY / LOGS)
        └── Content area (treemap OR tab content)
            └── BottomPanel (280px, slides up on cell click)
```

The ActivityFeed is a separate slide-over from the left, toggled by a store flag. Currently no clear way to access it — the toggle mechanism is in the store but I cannot find a trigger button in the visible UI (the TopBar has no activity button; this appears to be an orphaned feature).

---

## 2. What the User Does Most Frequently (Workflow Analysis)

### Primary daily workflow:
1. Open dashboard → land on MatrixGrid for active portfolio
2. Scan which cells are red vs green (P&L health check)
3. Run ANALYZE → read AI reasoning in ACTIONS tab
4. Execute approved trades
5. Check individual positions: click cell → BottomPanel → read TradeThesis

### Secondary workflow:
- Run SCAN to refresh watchlist
- Run UPDATE to refresh prices
- Switch to WATCHLIST tab to see new candidates
- Overview view to see cross-portfolio health

---

## 3. Critical Findings

### 3.1 DUPLICATE/REDUNDANT CONTROLS — HIGH SEVERITY

The action buttons (UPDATE, SCAN, ANALYZE, EXECUTE) appear in TWO places:
- `PortfolioSummary` (rendered from `CommandBar.tsx` components)
- Inside `MatrixGrid` there is also an `ActionsTab` with its own ANALYZE button

The primary CTA buttons are buried in the `PortfolioSummary` strip, which is a 68px horizontal bar that also contains equity, P&L metrics, benchmarks, regime, and risk status. This strip is extremely dense and forces the user to hunt for buttons among data.

The `AnalyzeExecute` component in `CommandBar.tsx` is dead-simple and correct. The identical functionality also lives in `ActionsTab.tsx` (PreFlightDashboard → Analyze button). Two places to trigger the same thing.

### 3.2 THE TOPBAR IS WASTING 72px — HIGH SEVERITY

The TopBar at 72px is enormous for what it does:
- Left: Logo (decorative) + Portfolio switcher + FreshnessIndicator
- Center: Market indices (S&P 500, Russell 2000, VIX) with sparklines — **good data but at wrong visual weight**
- Right: stale/failed counts + LOGS button + CLOSE ALL + PAPER/LIVE toggle

The LOGS button is styled completely differently from everything else (zinc color scheme vs the violet/accent system everywhere else). It looks like it was bolted on.

The TopBar does NOT contain ANALYZE or EXECUTE. The most important actions are buried in the PortfolioSummary strip below. A user opening the dashboard sees 72px of chrome before they even get to action buttons.

The market indices (S&P, Russell, VIX) are useful context but occupying the visual center of the top bar gives them equal weight to the portfolio's own equity and P&L. A user who runs 13 portfolios cares more about their open P&L than the S&P value at any given moment.

### 3.3 PORTFOLIO SUMMARY STRIP IS OVERLOADED — HIGH SEVERITY

The `PortfolioSummary` at 68px tries to show:
- Portfolio equity ($)
- Today P&L
- Open P&L
- All-Time P&L
- Return %
- Cash
- SPX/NDX/RUT alpha (when available)
- UPDATE / SCAN / ANALYZE / EXECUTE buttons
- Regime
- Risk score
- Position count
- Stale alerts indicator

That is 14+ distinct data points in a 68px strip. The result: everything is competing at the same visual weight. The equity figure is slightly larger (22px) but nothing else dominates. The buttons (UPDATE/SCAN/ANALYZE) are tiny (28px height, 10px font) and use three different colors (blue/amber/violet) that don't read as primary actions.

### 3.4 THE EQUITY CURVE (FOURIER STRIP) IS HIDDEN AND UNUSED — MEDIUM

`PortfolioSummary.tsx` contains an `EquityCurve` component with a sophisticated animated Fourier decomposition visualization. It is NOT rendered anywhere in the current UI. The component exists, works (presumably), but is never used. Either it was removed from the layout and forgotten, or it was intended but never wired up.

### 3.5 MATRIX GRID TAB SYSTEM USES GREEN WHILE REST OF APP USES VIOLET — MEDIUM

The MatrixGrid uses its own isolated color system (`#4ade80` green) including:
- Tab bar active indicator: green
- Cell hover states: green
- Sort buttons: green
- EKG strip: green
- Boot terminal: green
- Status bar: green

The rest of the app (TopBar, PortfolioSummary, ActionsTab, ActivityFeed) uses the violet accent system (`#7c5cfc`, `--accent`). This creates a hard visual break every time you look at the treemap vs. any panel above or below it.

The matrix green is intentional and atmospheric (matrix movie reference), but the mismatch with the violet system means the interface has two competing design languages.

### 3.6 BOTTOMP PANEL OVERLAPS THE TREEMAP CONTENT — MEDIUM

The `BottomPanel` is `position: absolute, bottom: 0, height: 280px`. When it opens, the treemap tries to reflow to `containerSize.h - 296` (the `bottomReserve` calculation). This works but creates a jarring layout jump — cells animate into smaller positions while a panel slides up simultaneously. The animation timing doesn't feel coordinated.

The 280px BottomPanel height is generous, but the three-column layout inside (identity | sparkline+stats | thesis+company info) uses very small text (6px labels, 7-8px body text in some areas). Reading the trade thesis requires straining.

### 3.7 FONT SIZE CHAOS — MEDIUM

Font sizes used across the codebase (measured, not estimated):

- **6px** — labels in BottomPanel (ENTERED, DAY %, VOL, BETA, VALUE, PRICE, SHARES, AVG COST, STOP, TARGET, MKT CAP, P/E, 52W, ANALYST, SOCIAL headers)
- **7px** — BottomPanel description text, AIreasoning in TradeThesis, various hints
- **8px** — BottomPanel company info stats, TradeThesis factor labels and values, status bar in MatrixGrid
- **8.5px** — Metric labels in PortfolioSummary
- **9px** — Small badge text throughout
- **10px** — Stale/failed counts in TopBar, CommandBar button text, tag text
- **11px** — Tab bar text, some metric values, CandidateRow ticker text
- **12px** — Metric values in PortfolioSummary
- **13px** — Default body, cell tickers (normal), controls
- **14px** — IndexTile values in TopBar
- **22px** — Equity figure in PortfolioSummary
- **26px** — P&L percentage in BottomPanel
- **28px** — Ticker name in BottomPanel

There is no coherent type scale. The jump from 8px → 14px → 22px → 26px → 28px has no rhythmic relationship. The 6px text is functionally unreadable on any modern display.

### 3.8 ACTIONS TAB IS BURIED AS A SUB-TAB — MEDIUM

The primary analyze workflow requires:
1. Pressing ANALYZE in the summary strip
2. Waiting for analysis to complete
3. The view automatically switches to the ACTIONS tab inside MatrixGrid
4. Reading and executing from there

Step 3 works (auto-switch on analysis complete), but the ACTIONS tab lives inside the MatrixGrid — the same component that shows the treemap. Switching to ACTIONS hides the treemap entirely. There's no way to see "which positions are being flagged for sell" while simultaneously viewing "which cells in the treemap correspond to those positions."

### 3.9 ACTIVITY FEED SLIDE-OVER IS ORPHANED — MEDIUM

The `ActivityFeed` component is a slide-over panel controlled by `activityOpen` in `useUIStore`. The toggle is `toggleActivity`. But looking at the TopBar code, there is no button that calls `toggleActivity`. There is also an "ACTIVITY" tab inside MatrixGrid that renders an `ActivityPanel` (not `ActivityFeed`). So the slide-over version appears to be fully disconnected from the UI — there's no way to open it unless via keyboard shortcut or code.

Actually cross-checking: `useKeyboardShortcuts` might wire it. But this is still confusing — there are two different activity displays.

### 3.10 WATCHLIST TAB IS SEPARATE FROM ACTIONS/PRE-FLIGHT — LOW

The `ActionsTab`'s `PreFlightDashboard` shows watchlist candidates. The MatrixGrid also has a dedicated WATCHLIST tab. The candidate list in PreFlightDashboard is the same data. This duplication isn't harmful but means the same content appears in two different contexts with slightly different presentation.

### 3.11 PORTFOLIO SWITCHER PLACEMENT — LOW

The `PortfolioSwitcher` lives in the TopBar, above the PortfolioSummary. This means the switcher and the data it controls (summary strip) are in different rows. Click portfolio in TopBar → data changes in strip below → content changes even further below (MatrixGrid). The navigation source is visually separated from its target.

### 3.12 BOTTOMP ANEL THREE-COLUMN LAYOUT IS UNBALANCED — LOW

The BottomPanel grid is `1fr 1.6fr 0.85fr`. The right column (trade thesis + company info) is narrowest but has the most text content. The middle column has the sparkline + 4 stat boxes + stop/target/signal bars — useful but less time-critical than the thesis. The left column shows ticker + large P&L, which is important but could be more compact.

---

## 4. What Works Well (Do Not Break)

- **MatrixGrid treemap cells**: the squarified layout, 3D parallax, glitch effects, anomaly pulses, and portfolio color coding work beautifully. The visual language is distinctive.
- **BottomPanel TradeThesis**: the factor bar visualization is clear and readable (despite tiny labels).
- **Boot sequence terminal**: pure atmosphere, sets the tone immediately.
- **ActionsTab ActionCard**: the per-action cards with BUY/SELL badges, confidence dots, decision badges, factor breakdown, and AI reasoning is excellent.
- **ActivityFeed FeedItem**: clean expandable rows with P&L, days held, and buy reasoning.
- **CSS variable system**: well-structured dual-token bridge. The `--accent` violet family is coherent.
- **CommandBar button styles**: the three color families (blue=update, amber=scan, violet=analyze/execute) are meaningful and readable.
- **Background canvas particle system**: adds depth without distracting.
- **EKGStrip**: shows portfolio equity vitals — atmospheric and functional.
- **TickerTape**: running ticker of held positions — good ambient information.
- **The PortfolioSummary equity counter animation** (useCountUp): satisfying feedback.
- **Keyboard shortcuts**: A=analyze, E=execute, R=refresh, 1-5=sort, Escape=close. Correct defaults.

---

## 5. Information Hierarchy Problems

### Current hierarchy (in visual order, top to bottom):
1. Logo + Portfolio switcher + Market indices + Mode toggle (TopBar)
2. Equity + all P&L metrics + benchmarks + action buttons + status (Summary strip)
3. Portfolio vitals EKG + ticker tape (MatrixGrid header)
4. Sort/filter controls
5. Tab bar
6. Treemap (the actual portfolio)
7. BottomPanel (position detail)

### Problems:
- Market indices (secondary data) are at the TOP, same visual level as the primary brand/navigation
- Primary action buttons (ANALYZE, EXECUTE) are on row 2, buried in a crowded strip
- The treemap (the thing you look at most) is on row 6 of 7
- Status indicators (regime, risk) are also on row 2, competing with action buttons

### What should dominate:
- The treemap should feel like it owns the screen
- ANALYZE/EXECUTE should be the most visually prominent CTAs
- Position P&L and equity should be high-contrast, immediately legible
- Market context (indices, regime) should be ambient/secondary

---

## 6. Inconsistencies in Visual Language

| Property | TopBar | PortfolioSummary | MatrixGrid | ActionsTab |
|----------|--------|-----------------|------------|------------|
| Primary color | violet accent | violet + profit/loss | **green** (#4ade80) | violet accent |
| Font family | sans | mono for numbers | mono (JetBrains) | mixed |
| Border style | rgba accent | rgba white | rgba green | rgba white |
| Button height | 32px | 28px | 2px+7px (tiny) | various |
| Label size | 9px | 8.5px | 6-7px | 9px |

The MatrixGrid being green while everything else is violet is the biggest inconsistency. It's intentional (Matrix reference) but creates a perception of two separate applications glued together.

---

## 7. Missing Features That Would Help Daily Use

1. **Keyboard shortcut to cycle portfolios** — with 13 portfolios, clicking the switcher every time is slow
2. **Position count and total P&L visible at all times** — currently only in the summary strip, which disappears if you're in overview/logs mode
3. **Sell reasoning visible on treemap cells** — cells that have pending sell actions could be annotated directly (already has the data via `pendingSellReasoningMap`)
4. **"Execute" confirmation in-line** — the execute flow requires finding the ACTIONS tab, reading cards, finding the execute button. A single prominent EXECUTE button that appears after ANALYZE completes would be faster.
5. **Timestamp of last UPDATE** — the FreshnessIndicator shows this, but it's tiny and buried under the portfolio switcher

---

## 8. Performance Concerns

- The MatrixGrid 3D parallax (`perspective(1200px) rotateY/rotateX`) is applied to the entire grid div on every `mousemove` — this means every mouse movement triggers a CSS transform on a potentially large DOM. No requestAnimationFrame throttling visible.
- The EKG strip (`EKGStrip.tsx`) and Fourier canvas in PortfolioSummary both run `requestAnimationFrame` loops. The Fourier canvas isn't rendered anywhere, so it's not actively consuming resources.
- The glitch effect and anomaly scanner run `setInterval` timers independently — these create state updates every few seconds even with no user interaction.

---

## 9. Summary of Priority Issues

| Priority | Issue | Impact |
|----------|-------|--------|
| CRITICAL | Font sizes 6-7px are unreadable | Daily readability |
| CRITICAL | Action buttons buried / redundant | Core workflow friction |
| HIGH | Green vs violet color system conflict | Visual coherence |
| HIGH | PortfolioSummary strip is overloaded | Information clarity |
| HIGH | TopBar at 72px wastes prime real estate | Layout efficiency |
| MEDIUM | BottomPanel text is too small | Position detail readability |
| MEDIUM | Activity feed slide-over is orphaned | Feature discoverability |
| MEDIUM | No way to see treemap + action results simultaneously | Workflow friction |
| LOW | EquityCurve component is never rendered | Wasted feature |
| LOW | Watchlist data appears in two tabs | Minor duplication |
