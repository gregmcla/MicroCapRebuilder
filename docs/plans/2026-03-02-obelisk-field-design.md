# Performance Obelisk Field — Design Doc

## Concept

Replace the scatter plot with a pseudo-3D isometric sculpture field. Each portfolio becomes a vertical performance monument. Geometry is derived entirely from the portfolio's cumulative return curve — velocity drives flares, drawdown drives scars. No extra metrics encoded. Pure performance made spatial.

---

## Data Pipeline

**Input:** `overview.portfolios[].sparkline` (daily equity values, already in component)

**Steps:**
1. `cum[t] = (sparkline[t] - sparkline[0]) / sparkline[0] * 100` → cumulative return % at each step
2. `vel[t] = cum[t] - cum[t-1]` → velocity (first derivative) — drives **outward flares**
3. `dd[t] = cum[t] - Math.max(...cum.slice(0, t+1))` → drawdown from prior high — drives **inward scars**
4. Column height at each step = `cum[t]` mapped to pixels (consistent scale across all columns)
5. Width at step t = `BASE_WIDTH + vel[t] × FLARE_K - Math.abs(dd[t]) × SCAR_K` (clamped ≥ MIN_WIDTH)

**Baseline:** 0% return = the shared ground plane. Portfolios below 0% get a compressed "sub-basement" zone capped at a fixed small height with a crushed crown — never truly negative height.

---

## Geometry

Each column is a 3D isometric form built from three SVG faces:

### Front Face
- A closed polygon built from left-edge and right-edge point arrays
- Left edge: `[colX - w(t)/2, baseY - h(t)]` per time step
- Right edge: `[colX + w(t)/2, baseY - h(t)]` per time step
- Path uses **quadratic Bézier curves** (SVG `Q`) between points for smooth undulation — no math smoothing needed
- Fill: near-black gradient (`#07070f` base → `#0d0d1a` top)
- Faint portfolio-color gradient bleeds in only on the **top 10%** of the column height

### Right Face (depth illusion)
- Parallelogram: right edge of front face + offset `(+10px, -5px)` (isometric angle)
- Fill: darker than front (`#040408`) — shadow side
- No glow

### Top Cap
- Small parallelogram at the crown, same isometric offset
- Same dark fill as right face

### Rim Light
- Thin `<path>` tracing the right edge of the front face only
- `stroke = portfolio color`, `strokeWidth = 1`, `filter: blur(0.5px)`
- Opacity fades from full at crown → 20% at base

---

## Crown Behavior (performance-derived)

**Positive final return:**
- Crisp parallelogram cap
- Radial glow ellipse at crown, `fill = portfolio color`, opacity ~35%, `filter: blur(4px)`
- If `cum[last] === max(cum)` (ended at all-time high): thin vertical beam 15px upward, fades to transparent. One beam, no pulse.

**Negative final return:**
- Crown replaced with 2–3 small skewed parallelogram shards at slightly different angles — "collapsed" look
- Reduced glow, desaturated
- No beam

---

## Material

- All column bodies: monochrome zinc/obsidian (`#07070f` to `#0d0d1a`)
- Portfolio color used **only** for: rim light stroke, crown glow, top-10% internal gradient bleed
- No color on the body itself — color = energy, not paint

---

## Floor Reflection

- Columns mirrored via `transform: scaleY(-1)` with `transform-origin: bottom`
- Gradient mask (SVG `<mask>` with linearGradient): full opacity at base → transparent at ~40px below
- Opacity 15%, `filter: blur(1px)`
- Reflection is geometry-accurate: it distorts with the column shape

---

## Environment

- Background: near-black void (`#04040a`) with subtle centered radial gradient (slightly lighter: `#07071280`)
- No grid, no axes, no tick marks
- Columns evenly spaced, centered horizontally in the container
- Container height: 320px

---

## Labels

- **Default:** no always-on labels
- **On hover:** portfolio name + return % appear as a minimal tooltip (monospace, small, above crown)
- Hover also brightens the column's rim light slightly

---

## Load Animation

- Each column masked with an animated `clipRect` (or `clipPath` with animated `height`)
- All columns start from `height = 0` and grow upward simultaneously
- Duration: 1.4s, easing: `cubic-bezier(0.16, 1, 0.3, 1)` (expo out)
- **Crown ignition:** after the grow animation completes, crown glow fades in — ranked by final return (best performer's crown ignites last, slightly brighter). Subtle, not gamified.
- No stagger on the growth itself — all rise together, one unified construction

---

## Component Interface

Replaces `ScatterPlot` in `AllPositionsPanel`. Toggle label changes from `PLOT` → `OBELISK`.

```tsx
function ObeliskField({ portfolios }: { portfolios: PortfolioSummary[] })
```

Receives `overview.portfolios` (already available in `OverviewPage` via `useOverview()`). Does not need `CrossPortfolioMover` data.

---

## What Stays the Same

- MAP/toggle button pattern (now MAP | OBELISK)
- Container dimensions and margins
- `AllPositionsPanel` wrapper component
- No new API calls
