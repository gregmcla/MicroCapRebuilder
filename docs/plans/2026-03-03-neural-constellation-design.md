# Neural Constellation — Overview Map Redesign

**Goal:** Replace the current CSS flexbox WeightedMap with a canvas-based physics-driven particle visualization where every position is a living, glowing node in a neural constellation.

**Architecture:** Single new component `ConstellationMap.tsx`. Canvas 2D, requestAnimationFrame physics loop, HTML overlay for hover detail card. Replaces `WeightedMap` in `OverviewPage.tsx`. The MAP/CHART toggle remains — MAP now renders ConstellationMap.

**Tech stack:** React 19, Canvas 2D API, ResizeObserver, no new dependencies.

---

## Visual Design

### Canvas
- Height: 360px, full width, responsive
- Background: `#07090f` (deeper than surrounding UI)
- Two-layer parallax starfield: 60 slow stars + 120 fast stars, tiny white dots (0.8–1.4px radius), slowly drifting. Mouse position shifts layers by ±6px / ±12px respectively.

### Nodes
Each position = one node. Appearance:
- **Core radius**: `clamp(8, sqrt(market_value / 500), 28)` px
- **Color by pnl_pct**:
  - `> +8%` → `#00FF9C` (emerald, high bloom)
  - `+2% to +8%` → lerp `#4ADE80` → `#00FF9C`
  - `-2% to +2%` → `#94A3B8` (silver-neutral)
  - `-2% to -8%` → lerp `#FBBF24` → `#F87171` (amber → red)
  - `< -8%` → `#EF4444` (crimson)
- **Three-pass glow render** (same pattern as PerformanceChart lines):
  1. Outer halo: `shadowBlur=32`, `shadowColor=nodeColor`, `globalAlpha=0.12`
  2. Mid glow: `shadowBlur=12`, `globalAlpha=0.35`
  3. Core: solid fill, `globalAlpha=1.0`
- **Breathing**: each node has a phase offset (seeded from ticker string), radius oscillates ±2px, sin wave, period 3–5s
- **Day ripple**: if `|day_change_pct| > 1%`, emit an expanding ring every 4s (ring grows from core radius to 2.5× core, opacity 0.4 → 0, lineWidth 1px, color = node color)

### Labels
- Ticker: 9px JetBrains Mono, `rgba(255,255,255,0.65)`, centered below node, y-offset = core + 10px
- Day pct: 8px, color-coded, centered above node, y-offset = -(core + 8px). Only rendered if `|day_change_pct| > 0.5%`

### Portfolio Clusters
Each portfolio has a fixed anchor point (arranged in a soft diamond: top, right, bottom, left for 4 portfolios; adjusted for fewer/more). Cluster visual:
- Ghost circle: `radius = 80px`, `strokeStyle = portfolioColor`, `lineWidth = 1`, `setLineDash([3,5])`, `globalAlpha = 0.18`
- Portfolio label: 10px caps, `portfolioColor`, `globalAlpha = 0.45`, centered at anchor

### Arc Connections
Drawn between every pair of nodes within the same portfolio:
- `lineWidth = 0.6`, `strokeStyle = portfolioColor`, `globalAlpha = 0.10`
- Drawn before nodes so they sit underneath
- Skip arcs when node count in cluster > 12 (too dense, performance + visual noise)

---

## Physics Simulation

Each node maintains: `{ x, y, vx, vy, targetX, targetY, radius, phase, rippleT }`

Forces per frame (60fps rAF loop):
1. **Cluster gravity**: spring toward portfolio anchor. `F = k_spring * (target - pos)`, `k_spring = 0.012`
2. **Node repulsion**: between every pair, `F = k_rep / dist²`, `k_rep = 1800`. Only applied when `dist < 120px`
3. **Boundary soft wall**: if node within 24px of edge, push force inward. `F = k_wall * overlap`, `k_wall = 0.3`
4. **Damping**: `vx *= 0.88, vy *= 0.88` per frame

Initial positions: scatter nodes around their portfolio anchor with random offset ±40px. Nodes settle into cluster after ~1.5s of simulation.

**On data change** (positions prop updates): smoothly re-target nodes to new anchors. Don't reset physics — let them drift.

---

## Interaction

### Hover
- Detect within `radius + 10px` of cursor on `mousemove`
- Hovered node: glow 2× intensity, core radius +3px
- All other nodes: `globalAlpha *= 0.35` (dim)
- Hover card appears (HTML overlay, see below)

### Click
- Flare: emit 6 spark particles outward (fast, decay 400ms)
- Detail card persists until click-away or ESC

### Mouse parallax
- Store mouse position, apply to starfield layer offsets each frame
- Layer 1 (slow): `offsetX = mouseX * 0.015`, `offsetY = mouseY * 0.015`
- Layer 2 (fast): `offsetX = mouseX * 0.030`, `offsetY = mouseY * 0.030`

---

## Hover/Click Detail Card

HTML `<div>` overlay (not canvas) positioned absolutely over the canvas. Appears on hover/click.

Contents:
- Portfolio colored dot + portfolio name (10px caps)
- Ticker (18px monospace, bold)
- Market value (14px, `$X,XXX`)
- P&L row: `+$X.XX` and `+X.X%` colored by sign
- Day change row: `+X.XX%` colored by sign. Hidden if 0.

Styling: `background: rgba(8,10,20,0.88)`, `backdrop-filter: blur(12px)`, `border: 1px solid rgba(255,255,255,0.08)`, `border-radius: 8px`, `padding: 10px 14px`. Positioned to avoid canvas edges (flip left/right, up/down if near boundary).

Fade-in: 120ms opacity transition.

---

## Data

### Frontend type change
`CrossPortfolioMover` in `types.ts` — add optional field:
```typescript
day_change_pct?: number;
```

### API change
In `api/routes/portfolios.py`, the overview endpoint builds `all_positions` from each portfolio's positions. Add `day_change_pct` to each mover dict from `pos.get("day_change_pct", 0)`.

---

## Component API

```typescript
interface ConstellationMapProps {
  positions: CrossPortfolioMover[];   // all open positions across all portfolios
  portfolios: PortfolioSummary[];     // for portfolio colors + anchor labels
}
```

File: `dashboard/src/components/ConstellationMap.tsx`

---

## Integration

In `OverviewPage.tsx`:
- Import `ConstellationMap`
- In the MAP/CHART toggle section, replace `<WeightedMap ... />` with `<ConstellationMap positions={allPositions} portfolios={summaries} />`
- Keep toggle label as "MAP"

---

## Performance Notes

- Max ~50 nodes across all portfolios — physics loop is O(n²) for repulsion but n≤50 is trivial
- Starfield: 180 fixed points, just translate on draw — negligible
- Arc connections skipped for dense clusters (>12 nodes)
- Canvas cleared and redrawn every frame — standard rAF pattern, no offscreen canvas needed
