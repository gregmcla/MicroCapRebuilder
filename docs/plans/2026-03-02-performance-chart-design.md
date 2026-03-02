# Performance Chart — Design Doc

## Concept

Replace the WebGL ObeliskField with a dark, cinematic multi-portfolio performance chart.
Each portfolio becomes a glowing trajectory line drawn over time, normalized to % return from
inception. Canvas 2D with `globalCompositeOperation: "screen"` (additive blending) makes
overlapping lines intensify naturally at intersections without artificial amplification.

The aesthetic: a luxury trading terminal. Luminous lines, absolute void background, restrained
glow. Expensive, not flashy.

---

## Data Pipeline

**Input:** `portfolios: PortfolioSummary[]` — each has `sparkline: number[]` (daily equity values)

**Normalization:**
```
cum[t] = (sparkline[t] - sparkline[0]) / sparkline[0] * 100
```
All series start at 0%. Shorter portfolios end at their last data point.

**Y scale:** Global min/max across all portfolios' cum arrays + 12% padding. Shared across all
series — no per-series normalization.

**X scale:** Day index from inception (0 = first sparkline point). Shorter portfolios terminate
early; their line simply ends without occupying the full width.

---

## Visual Identity

**Background:** `#010107` — absolute void.

**Scanline texture:** CSS `repeating-linear-gradient` overlay div at 0.6% opacity — barely
perceptible material quality.

**Glow — restrained, three-pass rendering per line:**
1. Halo pass: `ctx.filter = "blur(2px)"`, 15% opacity, stroke width ~10px
2. Inner glow: no filter, 40% opacity, stroke width 2px
3. Core: no filter, 100% opacity, stroke width 1.5px

Each pass uses `globalCompositeOperation: "screen"` — lines that cross physically add their
light. Intersections brighten naturally. No artificial amplification needed.

**Area fill:** `globalCompositeOperation: "source-over"` (not screened), portfolio color at
4% opacity. Gradient from line Y down to chart bottom. Territory marking only.

**Color palette — desaturated, cohesive, cool:**
```
#7dd3c8  muted teal
#8b9cf4  soft indigo
#e8b87a  warm amber
#a3b8d4  steel blue
#b8a8d4  soft lavender
#8bbfa8  sage green
#d4b8a8  dusty rose
#9ab4c4  slate
```
All at similar luminosity. No raw saturation. Reads as instrument readouts, not festival colors.

---

## Layout

**Container:** 340px height, full parent width, `background: #010107`, `border-radius: 7px`,
`overflow: hidden`.

**Canvas padding:**
- Top: 28px
- Right: 112px (label zone — endpoint labels have air to breathe)
- Bottom: 24px
- Left: 40px (Y-axis tick labels)

**Device pixel ratio:** Canvas scaled by `window.devicePixelRatio` for crisp retina rendering.

---

## Grid

**Horizontal guides:** 3–5 solid hairlines, 1px, `rgba(255,255,255,0.05)`. Not dashed —
solid low-opacity lines. Always includes 0%. Count and spacing computed from the data range
(e.g., if range is 0–60%, guides at 0%, +20%, +40%, +60%). Never more than 5.

**Zero line:** Slightly brighter than other guides: `rgba(255,255,255,0.10)`, 1px solid —
the primary visual anchor.

**Y-axis labels:** Right-aligned at each guide, `rgba(255,255,255,0.18)`, 8px monospace.
Format: `+25%` / `-10%` / `0%`.

**No X-axis labels.** Time granularity isn't the point; trajectory shape is.

---

## Endpoint Treatment

At each line's terminal data point:
- **Dot:** 3px filled circle, portfolio color, no halo
- **Label:** `NAME +XX.X%` — 9px monospace, color-matched, floating right of the dot

Labels are positioned in the 112px right zone, anchored to their line's Y value. No
termination tick mark (removed — clean finish, not engineered).

For shorter portfolios, the dot + label treatment is identical — the intentional stop is
communicated by the dot itself. No additional visual indicator needed.

---

## Hover Behavior

**Scan line:** 1px vertical, `rgba(255,255,255,0.12)`, follows cursor X continuously.
No snapping — smooth tracking with linear interpolation of Y values at cursor X.

**Dimming:** Non-hovered lines dim to 35% opacity. Hovered line (closest to cursor Y) stays
full brightness. This creates depth without obscuring trajectory data.

**Intersection dots:** At each portfolio's interpolated Y position, 4px filled circle,
portfolio color.

**Tooltip card:**
- Position: just above cursor, left-aligned to scan line
- Background: `rgba(4,4,12,0.94)`, 1px border `rgba(255,255,255,0.08)`, border-radius 4px
- Lists all portfolios in **fixed order** (sorted by final return, established on mount)
  — not re-sorted at each X position
- Per row: color dot (5px) + name (left) + return at cursor X (right), 9px monospace
- No shadow

**Idle state:** When not hovering, only endpoint dots and labels are visible chrome.
The chart breathes.

---

## Animation

**Mount:** Lines draw left-to-right via a Canvas clip rect expanding from x=0 to full chart
width over 1.2s, easing `cubic-bezier(0.16, 1, 0.3, 1)`. Full canvas redraws each RAF frame
inside the expanding clip.

**After draw (1.2s):** Endpoint dots and labels fade in over 300ms via a separate
`animEndpoints` opacity state (0 → 1).

**No stagger** — all lines rise together.

---

## Component Interface

```tsx
function PerformanceChart({ portfolios }: { portfolios: PortfolioSummary[] })
```

Replaces `ObeliskField` in `AllPositionsPanel`. Toggle label changes from `OBELISK` → `CHART`.

**File:** Replace contents of `dashboard/src/components/ObeliskField.tsx` entirely and rename
the export + import to `PerformanceChart`. Update `OverviewPage.tsx` import + toggle label.

**Dependencies:** None new. Three.js, `@react-three/fiber`, `@react-three/drei` can be removed
from `package.json` entirely.

---

## What Stays the Same

- `AllPositionsPanel` wrapper component and MAP/CHART toggle pattern
- Container dimensions (340px height)
- `PortfolioSummary[]` prop interface
- No new API calls
