# Solar System Portfolio Map — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current physics-simulation ConstellationMap with a solar system visualization where portfolios are suns and positions orbit them — genuinely beautiful, not just functional.

**Architecture:** Pure Canvas 2D, single rAF loop, no physics. Deterministic orbital mechanics (Keplerian-style). Replaces `ConstellationMap.tsx` in-place — same props, same import.

**Tech Stack:** React 19, Canvas 2D API, rAF animation loop, ResizeObserver

---

## Visual Spec (what "good" means here)

The bar is high. Every layer needs to be polished:

### Background
- Near-black deep space: `#05060f`
- Radial vignette: `radial-gradient(ellipse at 50% 50%, transparent 20%, rgba(0,0,0,0.7) 100%)` overlaid as a DOM div
- **No star field** — it was noisy. Clean dark space only.

### Suns (portfolios)
Each sun is rendered with 4 layers (drawn back to front):
1. **Outer corona** — very large radius (2.5× sun radius), low opacity (~0.06), blurred, portfolio color
2. **Inner glow** — 1.6× sun radius, opacity ~0.18, blurred
3. **Surface fill** — solid circle at full radius, radial gradient from bright center to darker edge (not flat color)
4. **Highlight** — small bright ellipse offset top-left (like a specular highlight on a sphere)

Sun color = portfolio total_return_pct:
- ≥ +5%: `#22c55e` (green)
- ≥ 0%: `#f59e0b` (amber)
- < 0%: `#ef4444` (red)

Sun radius: 28px base. Name label 14px above the corona edge, small caps monospace, matching sun color at 70% opacity.

### Orbit rings
- Dashed line: `[2, 6]` dash pattern
- Color: same as sun color at 10% opacity
- Line width: 0.5px
- Only drawn within the canvas bounds (clip to canvas rect)

### Position nodes (planets)
Each node: 3 rendering layers:
1. **Halo** — large radius (3× node radius), very low opacity (0.08), blurred, node color
2. **Glow ring** — 1.4× node radius, opacity 0.25, no blur
3. **Core** — solid circle, radial gradient (bright center → slightly darker edge)

Node color = pnl_pct:
- > +8%: `#00ff9c` (electric green)
- > +2%: interpolate `#4ade80` → `#00ff9c`
- > -2%: interpolate `#94a3b8` → `#4ade80`
- > -8%: interpolate `#fbbf24` → `#94a3b8`
- ≤ -8%: `#ef4444`

Node radius: `clamp(5, sqrt(marketValue / 800), 14)` px

Ticker label: 8px monospace, centered below node at `radius + 9px`, white at 60% opacity. Hidden if node radius < 7px (too small/crowded).

**Day change flare**: if `|dayChangePct| > 1%`, draw an animated ripple ring once every 5s. Ring expands from node radius → 2.5× over 0.7s, fading out. Color matches node color.

### Orbital mechanics
- Orbit radius for position i in portfolio: `sunRadius + 30 + i * (nodeRadius * 2 + 18)` — stacked rings
- If two positions would share an orbit (same distance), offset by ±10px alternating
- Angular speed: `baseSpeed / orbitRadius` — outer orbits slower (Kepler's third law feel)
- `baseSpeed = 0.018` rad/s (slow enough to feel weighty)
- Initial angle: deterministic from ticker string hash (same layout on every reload)
- Global system rotation: `+0.0006` rad/s added to all angles each frame (very slow drift)

### Hover interaction
- Hit test: `distance(mouse, node.x, node.y) < node.radius + 12`
- On hover: node pauses (angular velocity = 0 for that node only), all other nodes dim to 30% opacity
- Glassmorphic detail card appears near node (same style as existing: `rgba(8,10,20,0.90)`, blur 12px, border `rgba(255,255,255,0.08)`)
- Card contents: ticker (large, monospace), portfolio name (small, colored), market value, P&L $ and %, day change %
- Card auto-positions: right of node if space, left if near right edge, above if near bottom

### Sun layout (static, computed once on resize)
- 1 portfolio: centered
- 2 portfolios: left-center and right-center (x at 28% and 72%, y at 50%)
- 3 portfolios: triangle — top-center, bottom-left, bottom-right
- 4 portfolios: 2×2 grid at (28%, 33%), (72%, 33%), (28%, 67%), (72%, 67%)
- 5+: evenly spaced on a circle of radius 35% of min(w,h), centered

### Animation
- Single rAF loop, always running
- `dt = min((now - last) / 16.67, 2.5)` normalized to 60fps
- All angles update each frame: `angle += speed * dt`
- Canvas cleared and fully redrawn each frame

---

## Component Interface

```typescript
// Same props as current ConstellationMap — drop-in replacement
interface ConstellationMapProps {
  positions: CrossPortfolioMover[];
  portfolios: PortfolioSummary[];
}
export default function ConstellationMap(props: ConstellationMapProps)
```

## Files
- **Modify**: `dashboard/src/components/ConstellationMap.tsx` — full rewrite
