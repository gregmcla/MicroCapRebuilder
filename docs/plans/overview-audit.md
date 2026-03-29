# Overview Dashboard Audit
Date: 2026-03-27

## Current State

The overview is the cross-portfolio view shown when `activePortfolioId === "overview"`. It consists of:

1. **AggregateBar** — sticky top bar with: Total Equity (animated count-up), All-Time P&L, Unrealized P&L, Day P&L, Cash, Positions count, Portfolio count, + action buttons (Update All, Scan All, New Portfolio)
2. **PortfolioCard grid** — auto-fill grid of cards, each with: name/universe/live badge, equity + return %, P&L row (all-time, day, open), sparkline strip, top 3 holdings by market value, bottom stats (regime, positions, deployed bar, cash), scan badge
3. **No constellation map** in current OverviewPage.tsx — ConstellationMap.tsx exists but is NOT currently rendered in OverviewPage. The CLAUDE.md references it as the "MAP view" but the actual component is unused in overview.
4. **No PerformanceChart** in OverviewPage — PerformanceChart.tsx exists but is also not rendered here.

## What Questions Does the Overview Currently Answer?

- Total money across all portfolios (equity, cash)
- All-time P&L and return %
- Day P&L aggregate
- Which portfolios exist (name, universe, live/paper)
- Per-portfolio equity and return %
- Per-portfolio day P&L and open P&L (buried in small text)
- Per-portfolio regime, positions count, deployed %
- Per-portfolio sparkline (equity trend shape)
- Top 3 holdings per portfolio by market value
- Scan results when scan-all is running

## What It Does NOT Answer (But Should)

- **Which portfolios are up vs down today?** — Day P&L is shown but not sorted by it; cards are in API order. No at-a-glance winner/loser ranking.
- **Which portfolios need attention?** — No attention/alert section. Error states show on cards but there's no summary. No idle cash alert, no high-risk flags.
- **Cross-portfolio top/bottom movers** — `top_movers` and `bottom_movers` arrays exist in OverviewData but are NOT rendered anywhere.
- **Portfolio relative performance** — no ranking or comparison between portfolios
- **How many portfolios are up vs down today?** — not surfaced
- **Total deployed vs idle cash** — total cash shown but not what % is idle
- **Morning readiness** — no "portfolios needing attention" section

## ConstellationMap Assessment

The constellation map (ConstellationMap.tsx) is a solar-system canvas animation — portfolios as "suns", positions as orbiting planets. It's visually impressive but NOT the right primary view for a trader's morning workflow:

**What it communicates well:**
- Relative position size within a portfolio (planet radius = market value)
- Position P&L at a glance (planet color: green = profit, red = loss)
- Which portfolios have many vs few positions
- Hover interactivity for individual position details

**What it communicates poorly:**
- Portfolio-level financial performance (you'd have to find the sun's color)
- Absolute equity per portfolio (no data encoded)
- Day P&L (not directly visible)
- Deployed % (not visible)
- Cash position (not visible)
- Which portfolios are winning vs losing at a glance is hard with 13 solar systems arranged in a circle
- With 13 portfolios, the layout gets extremely crowded — suns overlap orbit rings

**Verdict:** The constellation map is decorative/exploratory. It's good for understanding position composition and exploring what you own across portfolios. It's NOT useful for "quick scan before 9:30 AM." It should be demoted to a secondary tab or toggle, not removed.

## PerformanceChart Assessment

PerformanceChart.tsx is a sophisticated canvas chart with:
- Catmull-Rom smooth curves per portfolio
- ECG pulse animations on line endpoints
- Dual-zone Y-scale for outlier portfolios
- Drawdown scars
- Hover crosshair with value display
- 8-color palette that cycles for 13 portfolios (wraps after 8)

**Readability with 13 portfolios:**
- Color palette has only 8 colors — portfolios 9-13 duplicate colors from 1-5, making them indistinguishable
- With 13 overlapping lines, the chart is visually overwhelming
- The right-side legend would need 13 entries — at current sizing this runs off screen
- The chart is good for spotting outliers (the dual-zone helps) but "which line is which" becomes very hard
- Not currently rendered in OverviewPage at all

## Cross-Portfolio Summary Numbers Assessment

Current AggregateBar shows: Total Equity | All-Time P&L | Unrealized P&L | Day P&L | Cash | Positions | Portfolios

**What's right:** Total equity (the most important number), Day P&L (critical), Cash (important)

**What's missing:**
- Total deployed % (what fraction of capital is actually working?)
- Portfolios up/down today count
- Unrealized P&L is less actionable than deployed %

**What's slightly off:**
- "Portfolios" count is low-value — you already see the cards
- The chip format makes comparison hard — all numbers look visually equal importance

## Navigation Assessment

Navigation: clicking portfolio card body calls `setPortfolio(summary.id)` which routes to the portfolio view. This works but:
- Cursor is `pointer` but the clickable zone is unclear — the delete button, sparkline, holdings, and bottom stats all have their own onClick handlers
- No visual hover state on the card to indicate clickability
- The card is dense — new users won't know to click it
- Navigation is instant (Zustand state update), which is good

## What Would Make This Genuinely Useful at 9:30 AM

1. **Instant P&L status** — "8 portfolios up today, 4 down, 1 flat" as a headline
2. **Sorted by performance** — portfolios sorted by day P&L descending by default
3. **Visible top/bottom movers** — the actual stocks driving today's moves
4. **Attention flags** — portfolios with errors, high risk, or excessive idle cash
5. **Deployment gauge** — total deployed % across all capital
6. **Clear navigation** — hover state on cards that makes "click to enter" obvious
7. **Morning briefing format** — the narrative from `/api/system/narrative` already exists (LogsPage uses it)

## Summary of Issues by Severity

**HIGH:**
- `top_movers` and `bottom_movers` from the API are completely unused — this is valuable data being discarded
- No attention/alert section for portfolios needing action
- No sorting by performance — cards are in arbitrary API order

**MEDIUM:**
- ConstellationMap not rendered (noted as "MAP view" in docs but absent from code)
- PerformanceChart not rendered in overview
- No hover state on portfolio cards to signal interactivity
- Deployed % not in aggregate bar
- 13 portfolios would overwhelm PerformanceChart's 8-color palette

**LOW:**
- "Portfolios" chip in AggregateBar is redundant
- The top P&L row in cards uses very small text (10px) for important data
- Sparkline gradient ID uses returnPct which isn't guaranteed unique — potential SVG gradient collision
