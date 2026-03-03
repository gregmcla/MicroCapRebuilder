# Neural Constellation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the CSS flexbox WeightedMap in the overview dashboard with a canvas-based physics-driven particle constellation where every position is a living, glowing node.

**Architecture:** New `ConstellationMap.tsx` component owns a Canvas 2D + rAF physics loop. It receives `positions` and `portfolios` props from `OverviewPage.tsx`, which already fetches overview data. Minor API change adds `day_change_pct` to each mover. No new dependencies.

**Tech Stack:** React 19, Canvas 2D API, ResizeObserver, TypeScript, no new npm packages.

---

## Context for implementer

The dashboard is at `dashboard/` (Vite + React 19 + Tailwind v4). Run `npm run build` from `dashboard/` to type-check. The dev server is already running on port 5173 (hot reload). The overview page is `dashboard/src/components/OverviewPage.tsx`. The current map component is `WeightedMap` (defined inline in OverviewPage.tsx around line 131). We are replacing it.

Design doc: `docs/plans/2026-03-03-neural-constellation-design.md` — read it for full visual spec.

Portfolio colors come from `PORTFOLIO_PALETTE` already defined in OverviewPage.tsx (lines 98-107). You'll need to move or import it.

Key types in `dashboard/src/lib/types.ts`:
- `CrossPortfolioMover`: `{ portfolio_id, portfolio_name, ticker, pnl, pnl_pct, market_value? }`
- `PortfolioSummary`: `{ id, name, ... }`

API overview endpoint: `api/routes/portfolios.py` — find the function that builds `all_positions` list (search for `"all_positions"` or `CrossPortfolioMover` equivalent in Python dicts).

---

## Task 1: Add day_change_pct to CrossPortfolioMover

**Files:**
- Modify: `dashboard/src/lib/types.ts`
- Modify: `api/routes/portfolios.py`

**Step 1: Add field to TypeScript type**

In `dashboard/src/lib/types.ts`, find `CrossPortfolioMover` and add the optional field:

```typescript
export interface CrossPortfolioMover {
  portfolio_id: string;
  portfolio_name: string;
  ticker: string;
  pnl: number;
  pnl_pct: number;
  market_value?: number;
  day_change_pct?: number;   // ← add this
}
```

**Step 2: Add field to API overview response**

In `api/routes/portfolios.py`, find where `all_positions` list is built. Each entry is a dict with `ticker`, `portfolio_id`, etc. Add `day_change_pct`:

```python
# Find the list comprehension or loop that builds all_positions entries
# Add: "day_change_pct": float(pos.get("day_change_pct", 0) or 0),
```

Search for `all_positions` in portfolios.py to find the exact location. The positions data comes from `portfolio_state` — each position dict already has `day_change_pct` from the CSV.

**Step 3: Verify build**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -5
```
Expected: `✓ built in X.XXs`

**Step 4: Verify API response**

```bash
curl -s http://localhost:8000/api/portfolios/overview | python3 -c "import sys,json; d=json.load(sys.stdin); pos=d.get('all_positions',[]); print('day_change_pct present:', 'day_change_pct' in pos[0] if pos else 'no positions')"
```
Expected: `day_change_pct present: True` (or "no positions" if no open positions — that's fine)

**Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/lib/types.ts api/routes/portfolios.py
git commit -m "feat: add day_change_pct to CrossPortfolioMover type and overview API"
```

---

## Task 2: ConstellationMap — scaffold + physics engine

**Files:**
- Create: `dashboard/src/components/ConstellationMap.tsx`

**Step 1: Create the file with node types, physics constants, and the rAF loop skeleton**

Create `dashboard/src/components/ConstellationMap.tsx`:

```typescript
import { useEffect, useRef, useMemo } from "react";
import type { CrossPortfolioMover, PortfolioSummary } from "../lib/types";

// ─── Constants ───────────────────────────────────────────────────────────────
const K_SPRING  = 0.012;   // cluster gravity strength
const K_REP     = 1800;    // node-node repulsion
const K_WALL    = 0.3;     // boundary push
const DAMPING   = 0.88;
const WALL_PAD  = 24;
const MIN_R     = 8;
const MAX_R     = 28;

// ─── Types ───────────────────────────────────────────────────────────────────
interface PhysNode {
  ticker: string;
  portfolioId: string;
  pnlPct: number;
  dayChangePct: number;
  marketValue: number;
  r: number;           // visual radius
  x: number;
  y: number;
  vx: number;
  vy: number;
  anchorX: number;     // cluster anchor
  anchorY: number;
  phase: number;       // breathing phase offset (0–2π)
  rippleT: number;     // ripple timer (counts up, emits at 4s intervals)
}

interface Star {
  x: number;
  y: number;
  r: number;
  speed: number;
  dx: number;
  dy: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function nodeRadius(marketValue: number): number {
  return Math.max(MIN_R, Math.min(MAX_R, Math.sqrt((marketValue ?? 5000) / 500)));
}

function tickerPhase(ticker: string): number {
  let h = 0;
  for (let i = 0; i < ticker.length; i++) h = (h * 31 + ticker.charCodeAt(i)) >>> 0;
  return (h % 1000) / 1000 * Math.PI * 2;
}

function clusterAnchors(portfolioIds: string[], w: number, h: number): Record<string, { x: number; y: number }> {
  const ids = [...new Set(portfolioIds)];
  const cx = w / 2, cy = h / 2;
  const spread = Math.min(w, h) * 0.30;
  const angles: number[] = [];
  // distribute evenly around a circle, starting top
  for (let i = 0; i < ids.length; i++) {
    angles.push(-Math.PI / 2 + (i / ids.length) * Math.PI * 2);
  }
  const result: Record<string, { x: number; y: number }> = {};
  ids.forEach((id, i) => {
    result[id] = {
      x: cx + Math.cos(angles[i]) * spread,
      y: cy + Math.sin(angles[i]) * spread,
    };
  });
  return result;
}

function makeStars(count: number, w: number, h: number, speedRange: [number, number]): Star[] {
  const stars: Star[] = [];
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = speedRange[0] + Math.random() * (speedRange[1] - speedRange[0]);
    stars.push({
      x: Math.random() * w,
      y: Math.random() * h,
      r: 0.5 + Math.random() * 0.9,
      speed,
      dx: Math.cos(angle) * speed,
      dy: Math.sin(angle) * speed,
    });
  }
  return stars;
}

// ─── Component ───────────────────────────────────────────────────────────────
export interface ConstellationMapProps {
  positions: CrossPortfolioMover[];
  portfolios: PortfolioSummary[];
}

export default function ConstellationMap({ positions, portfolios }: ConstellationMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef  = useRef<PhysNode[]>([]);
  const starsRef  = useRef<{ slow: Star[]; fast: Star[] }>({ slow: [], fast: [] });
  const rafRef    = useRef<number>(0);
  const dimsRef   = useRef({ w: 0, h: 0 });
  const mouseRef  = useRef({ x: 0, y: 0 });
  const hoverRef  = useRef<string | null>(null);   // hovered ticker
  const clickRef  = useRef<string | null>(null);   // clicked ticker

  // Portfolio color palette (hex strings, cycle if more than palette length)
  const paletteRef = useRef<Record<string, string>>({});

  const PALETTE = [
    "#7C5CFC", "#22D3EE", "#F59E0B", "#10B981",
    "#F43F5E", "#A78BFA", "#34D399", "#FBBF24",
  ];

  // Build palette map from portfolios prop
  useMemo(() => {
    const map: Record<string, string> = {};
    portfolios.forEach((p, i) => {
      map[p.id] = PALETTE[i % PALETTE.length];
    });
    paletteRef.current = map;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [portfolios]);

  // ── Physics step ───────────────────────────────────────────────────────────
  function stepPhysics(nodes: PhysNode[], w: number, h: number, dt: number) {
    const n = nodes.length;

    // Reset forces
    const fx = new Float32Array(n);
    const fy = new Float32Array(n);

    for (let i = 0; i < n; i++) {
      const a = nodes[i];

      // 1. Spring toward cluster anchor
      fx[i] += K_SPRING * (a.anchorX - a.x);
      fy[i] += K_SPRING * (a.anchorY - a.y);

      // 2. Pairwise repulsion
      for (let j = i + 1; j < n; j++) {
        const b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dist2 = dx * dx + dy * dy;
        const minDist = a.r + b.r + 14;
        if (dist2 < 120 * 120 && dist2 > 0.01) {
          const dist = Math.sqrt(dist2);
          const overlap = Math.max(0, minDist - dist);
          const f = (K_REP / dist2) + (overlap > 0 ? 0.8 * overlap : 0);
          const nx = dx / dist, ny = dy / dist;
          fx[i] += nx * f; fy[i] += ny * f;
          fx[j] -= nx * f; fy[j] -= ny * f;
        }
      }

      // 3. Boundary walls
      const left = WALL_PAD + a.r, right = w - WALL_PAD - a.r;
      const top  = WALL_PAD + a.r, bottom = h - WALL_PAD - a.r;
      if (a.x < left)   fx[i] += K_WALL * (left   - a.x);
      if (a.x > right)  fx[i] += K_WALL * (right  - a.x);
      if (a.y < top)    fy[i] += K_WALL * (top    - a.y);
      if (a.y > bottom) fy[i] += K_WALL * (bottom - a.y);
    }

    // Integrate
    for (let i = 0; i < n; i++) {
      const nd = nodes[i];
      nd.vx = (nd.vx + fx[i]) * DAMPING;
      nd.vy = (nd.vy + fy[i]) * DAMPING;
      nd.x += nd.vx * dt;
      nd.y += nd.vy * dt;
      nd.rippleT += dt;
    }
  }

  // ── Init / resize ──────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ro = new ResizeObserver(entries => {
      const { width } = entries[0].contentRect;
      const h = 360;
      canvas.width  = Math.floor(width);
      canvas.height = h;
      dimsRef.current = { w: canvas.width, h };

      // Rebuild stars on resize
      starsRef.current = {
        slow: makeStars(60,  canvas.width, h, [0.03, 0.06]),
        fast: makeStars(120, canvas.width, h, [0.06, 0.12]),
      };

      // Rebuild cluster anchors + scatter nodes
      const { w } = dimsRef.current;
      const anchors = clusterAnchors(positions.map(p => p.portfolio_id), w, h);
      nodesRef.current = positions.map(pos => {
        const anchor = anchors[pos.portfolio_id] ?? { x: w / 2, y: h / 2 };
        const r = nodeRadius(pos.market_value ?? 5000);
        return {
          ticker:       pos.ticker,
          portfolioId:  pos.portfolio_id,
          pnlPct:       pos.pnl_pct,
          dayChangePct: pos.day_change_pct ?? 0,
          marketValue:  pos.market_value ?? 0,
          r,
          x: anchor.x + (Math.random() - 0.5) * 80,
          y: anchor.y + (Math.random() - 0.5) * 80,
          vx: 0, vy: 0,
          anchorX: anchor.x,
          anchorY: anchor.y,
          phase:    tickerPhase(pos.ticker),
          rippleT:  Math.random() * 4,
        };
      });
    });

    ro.observe(canvas);
    return () => ro.disconnect();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positions]);

  // ── rAF render loop ────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let last = performance.now();

    function frame(now: number) {
      const dt = Math.min((now - last) / 16.67, 2.5); // normalized to 60fps
      last = now;

      const { w, h } = dimsRef.current;
      if (w === 0 || h === 0) { rafRef.current = requestAnimationFrame(frame); return; }

      const nodes  = nodesRef.current;
      const stars  = starsRef.current;
      const mouse  = mouseRef.current;
      const hover  = hoverRef.current;
      const palette = paletteRef.current;

      stepPhysics(nodes, w, h, dt);

      // ── Draw ──────────────────────────────────────────────────────────────
      ctx.clearRect(0, 0, w, h);

      // Background
      ctx.fillStyle = "#07090f";
      ctx.fillRect(0, 0, w, h);

      // Stars — layer 1 (slow)
      const mxOff1 = mouse.x * 0.015, myOff1 = mouse.y * 0.015;
      const mxOff2 = mouse.x * 0.030, myOff2 = mouse.y * 0.030;

      ctx.save();
      stars.slow.forEach(s => {
        s.x = (s.x + s.dx * dt + w) % w;
        s.y = (s.y + s.dy * dt + h) % h;
        const sx = (s.x + mxOff1 + w) % w;
        const sy = (s.y + myOff1 + h) % h;
        ctx.beginPath();
        ctx.arc(sx, sy, s.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.4)";
        ctx.fill();
      });
      stars.fast.forEach(s => {
        s.x = (s.x + s.dx * dt + w) % w;
        s.y = (s.y + s.dy * dt + h) % h;
        const sx = (s.x + mxOff2 + w) % w;
        const sy = (s.y + myOff2 + h) % h;
        ctx.beginPath();
        ctx.arc(sx, sy, s.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.25)";
        ctx.fill();
      });
      ctx.restore();

      // Cluster wells
      const anchors = clusterAnchors(nodes.map(n => n.portfolioId), w, h);
      const portfolioIds = [...new Set(nodes.map(n => n.portfolioId))];
      portfolioIds.forEach(pid => {
        const anchor = anchors[pid];
        const color  = palette[pid] ?? "#7C5CFC";
        ctx.save();
        ctx.beginPath();
        ctx.arc(anchor.x, anchor.y, 80, 0, Math.PI * 2);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 5]);
        ctx.globalAlpha = 0.18;
        ctx.stroke();
        ctx.setLineDash([]);
        // Label
        const label = nodes.find(n => n.portfolioId === pid)?.portfolioId.toUpperCase() ?? pid.toUpperCase();
        ctx.globalAlpha = 0.45;
        ctx.fillStyle = color;
        ctx.font = "10px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillText(label, anchor.x, anchor.y - 86);
        ctx.restore();
      });

      // Arc connections (same portfolio pairs, skip if cluster > 12 nodes)
      portfolioIds.forEach(pid => {
        const cluster = nodes.filter(n => n.portfolioId === pid);
        if (cluster.length > 12) return;
        const color = palette[pid] ?? "#7C5CFC";
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 0.6;
        ctx.globalAlpha = 0.10;
        for (let i = 0; i < cluster.length; i++) {
          for (let j = i + 1; j < cluster.length; j++) {
            ctx.beginPath();
            ctx.moveTo(cluster[i].x, cluster[i].y);
            ctx.lineTo(cluster[j].x, cluster[j].y);
            ctx.stroke();
          }
        }
        ctx.restore();
      });

      // Nodes
      const t = now / 1000;
      const isHovering = hover !== null;

      nodes.forEach(nd => {
        const isHovered = nd.ticker === hover;
        const dimmed = isHovering && !isHovered;

        // Breathing radius
        const period = 3 + (tickerPhase(nd.ticker) / (Math.PI * 2)) * 2; // 3–5s
        const breathR = nd.r + Math.sin(t * (Math.PI * 2 / period) + nd.phase) * 2;
        const drawR   = breathR + (isHovered ? 3 : 0);

        // Color
        const color = nodeColor(nd.pnlPct);

        // Ripple ring
        const RIPPLE_INTERVAL = 4;
        if (Math.abs(nd.dayChangePct) > 1 && nd.rippleT >= RIPPLE_INTERVAL) {
          nd.rippleT = 0;
        }
        if (Math.abs(nd.dayChangePct) > 1 && nd.rippleT < 0.8) {
          const progress = nd.rippleT / 0.8;
          const rr = drawR + progress * drawR * 1.5;
          ctx.save();
          ctx.beginPath();
          ctx.arc(nd.x, nd.y, rr, 0, Math.PI * 2);
          ctx.strokeStyle = color;
          ctx.lineWidth = 1;
          ctx.globalAlpha = (1 - progress) * 0.4 * (dimmed ? 0.3 : 1);
          ctx.stroke();
          ctx.restore();
        }

        // Three-pass glow
        const baseAlpha = dimmed ? 0.35 : 1.0;
        const glowMult  = isHovered ? 2.0 : 1.0;

        // Pass 1 — outer halo
        ctx.save();
        ctx.shadowBlur   = 32 * glowMult;
        ctx.shadowColor  = color;
        ctx.globalAlpha  = 0.12 * baseAlpha;
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, drawR, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.restore();

        // Pass 2 — mid glow
        ctx.save();
        ctx.shadowBlur   = 12 * glowMult;
        ctx.shadowColor  = color;
        ctx.globalAlpha  = 0.35 * baseAlpha;
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, drawR, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.restore();

        // Pass 3 — core
        ctx.save();
        ctx.globalAlpha  = 1.0 * baseAlpha;
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, drawR, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.restore();

        // Ticker label
        ctx.save();
        ctx.font = "9px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillStyle = `rgba(255,255,255,${dimmed ? 0.25 : 0.65})`;
        ctx.fillText(nd.ticker, nd.x, nd.y + drawR + 10);
        ctx.restore();

        // Day change label (only if significant)
        if (Math.abs(nd.dayChangePct) > 0.5 && !dimmed) {
          const sign = nd.dayChangePct >= 0 ? "+" : "";
          ctx.save();
          ctx.font = "8px 'JetBrains Mono', monospace";
          ctx.textAlign = "center";
          ctx.fillStyle = nd.dayChangePct >= 0 ? "#4ADE80" : "#F87171";
          ctx.globalAlpha = 0.85;
          ctx.fillText(`${sign}${nd.dayChangePct.toFixed(2)}%`, nd.x, nd.y - drawR - 8);
          ctx.restore();
        }
      });

      rafRef.current = requestAnimationFrame(frame);
    }

    rafRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ position: "relative" }}>
      <canvas
        ref={canvasRef}
        style={{ display: "block", width: "100%", height: "360px" }}
        onMouseMove={e => {
          const rect = canvasRef.current!.getBoundingClientRect();
          const scaleX = canvasRef.current!.width / rect.width;
          const scaleY = canvasRef.current!.height / rect.height;
          mouseRef.current = {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY,
          };
          // Hover detection
          const mx = mouseRef.current.x, my = mouseRef.current.y;
          let found: string | null = null;
          for (const nd of nodesRef.current) {
            const dx = nd.x - mx, dy = nd.y - my;
            if (Math.sqrt(dx * dx + dy * dy) < nd.r + 10) { found = nd.ticker; break; }
          }
          hoverRef.current = found;
        }}
        onMouseLeave={() => { hoverRef.current = null; mouseRef.current = { x: 0, y: 0 }; }}
        onClick={e => {
          const rect = canvasRef.current!.getBoundingClientRect();
          const scaleX = canvasRef.current!.width / rect.width;
          const scaleY = canvasRef.current!.height / rect.height;
          const mx = (e.clientX - rect.left) * scaleX;
          const my = (e.clientY - rect.top)  * scaleY;
          let found: string | null = null;
          for (const nd of nodesRef.current) {
            const dx = nd.x - mx, dy = nd.y - my;
            if (Math.sqrt(dx * dx + dy * dy) < nd.r + 10) { found = nd.ticker; break; }
          }
          clickRef.current = found === clickRef.current ? null : found;
        }}
      />
    </div>
  );
}

// ─── Color helper ─────────────────────────────────────────────────────────────
function lerpColor(a: string, b: string, t: number): string {
  const ah = parseInt(a.slice(1), 16);
  const bh = parseInt(b.slice(1), 16);
  const ar = (ah >> 16) & 0xff, ag = (ah >> 8) & 0xff, ab_ = ah & 0xff;
  const br = (bh >> 16) & 0xff, bg = (bh >> 8) & 0xff, bb_ = bh & 0xff;
  const r = Math.round(ar + (br - ar) * t);
  const g = Math.round(ag + (bg - ag) * t);
  const b_ = Math.round(ab_ + (bb_ - ab_) * t);
  return `#${((r << 16) | (g << 8) | b_).toString(16).padStart(6, "0")}`;
}

function nodeColor(pnlPct: number): string {
  if (pnlPct >= 8)  return "#00FF9C";
  if (pnlPct >= 2)  return lerpColor("#4ADE80", "#00FF9C", (pnlPct - 2) / 6);
  if (pnlPct >= -2) return lerpColor("#94A3B8", "#4ADE80", (pnlPct + 2) / 4);
  if (pnlPct >= -8) return lerpColor("#FBBF24", "#94A3B8", (pnlPct + 8) / 6);
  return "#EF4444";
}
```

**Step 2: Verify build passes**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -8
```
Expected: `✓ built in X.XXs`

Fix any TypeScript errors before proceeding.

**Step 3: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/ConstellationMap.tsx
git commit -m "feat: add ConstellationMap component with physics engine and full render pipeline"
```

---

## Task 3: Add HTML overlay detail card

**Files:**
- Modify: `dashboard/src/components/ConstellationMap.tsx`

The detail card is an HTML overlay div positioned over the canvas. It shows on hover (or persists on click).

**Step 1: Add hover card state and the overlay div**

In `ConstellationMap`, add React state for the card:

```typescript
import { useEffect, useRef, useMemo, useState } from "react";

// inside component, after existing refs:
const [card, setCard] = useState<{
  ticker: string;
  portfolioName: string;
  portfolioColor: string;
  marketValue: number;
  pnl: number;
  pnlPct: number;
  dayChangePct: number;
  x: number;  // canvas px
  y: number;  // canvas px
} | null>(null);
```

Update the `mousemove` handler to set card state when a node is found:

```typescript
onMouseMove={e => {
  const rect = canvasRef.current!.getBoundingClientRect();
  const scaleX = canvasRef.current!.width / rect.width;
  const scaleY = canvasRef.current!.height / rect.height;
  const cx = (e.clientX - rect.left) * scaleX;
  const cy = (e.clientY - rect.top)  * scaleY;
  mouseRef.current = { x: cx, y: cy };

  let found: string | null = null;
  let foundNode: PhysNode | null = null;
  for (const nd of nodesRef.current) {
    const dx = nd.x - cx, dy = nd.y - cy;
    if (Math.sqrt(dx * dx + dy * dy) < nd.r + 10) { found = nd.ticker; foundNode = nd; break; }
  }
  hoverRef.current = found;

  if (foundNode && clickRef.current === null) {
    const pos = positions.find(p => p.ticker === foundNode!.ticker);
    if (pos) {
      setCard({
        ticker:        foundNode.ticker,
        portfolioName: pos.portfolio_name,
        portfolioColor: paletteRef.current[pos.portfolio_id] ?? "#7C5CFC",
        marketValue:   pos.market_value ?? 0,
        pnl:           pos.pnl,
        pnlPct:        pos.pnl_pct,
        dayChangePct:  pos.day_change_pct ?? 0,
        x: foundNode.x / scaleX,
        y: foundNode.y / scaleY,
      });
    }
  } else if (!foundNode && clickRef.current === null) {
    setCard(null);
  }
}}
onMouseLeave={() => {
  hoverRef.current = null;
  mouseRef.current = { x: 0, y: 0 };
  if (clickRef.current === null) setCard(null);
}}
```

Update the `click` handler to persist card on click:

```typescript
onClick={e => {
  const rect = canvasRef.current!.getBoundingClientRect();
  const scaleX = canvasRef.current!.width / rect.width;
  const scaleY = canvasRef.current!.height / rect.height;
  const cx = (e.clientX - rect.left) * scaleX;
  const cy = (e.clientY - rect.top)  * scaleY;
  let found: string | null = null;
  let foundNode: PhysNode | null = null;
  for (const nd of nodesRef.current) {
    const dx = nd.x - cx, dy = nd.y - cy;
    if (Math.sqrt(dx * dx + dy * dy) < nd.r + 10) { found = nd.ticker; foundNode = nd; break; }
  }
  if (found === clickRef.current) {
    // deselect
    clickRef.current = null;
    setCard(null);
  } else {
    clickRef.current = found;
    if (foundNode) {
      const pos = positions.find(p => p.ticker === foundNode!.ticker);
      if (pos) {
        setCard({
          ticker:        foundNode.ticker,
          portfolioName: pos.portfolio_name,
          portfolioColor: paletteRef.current[pos.portfolio_id] ?? "#7C5CFC",
          marketValue:   pos.market_value ?? 0,
          pnl:           pos.pnl,
          pnlPct:        pos.pnl_pct,
          dayChangePct:  pos.day_change_pct ?? 0,
          x: foundNode.x / scaleX,
          y: foundNode.y / scaleY,
        });
      }
    } else {
      setCard(null);
    }
  }
}}
```

**Step 2: Add the overlay div inside the return**

Replace the current `return` with:

```tsx
return (
  <div style={{ position: "relative" }}>
    <canvas
      ref={canvasRef}
      style={{ display: "block", width: "100%", height: "360px", cursor: hoverRef.current ? "pointer" : "default" }}
      onMouseMove={...}  {/* keep existing handlers */}
      onMouseLeave={...}
      onClick={...}
    />
    {card && (
      <DetailCard card={card} />
    )}
  </div>
);
```

**Step 3: Add the DetailCard sub-component** (at the bottom of the file, before the color helpers):

```tsx
function DetailCard({ card }: { card: NonNullable<ReturnType<typeof useState<{
  ticker: string; portfolioName: string; portfolioColor: string;
  marketValue: number; pnl: number; pnlPct: number; dayChangePct: number;
  x: number; y: number;
}>[0]>> }) {
  const CARD_W = 160, CARD_H = 100;
  // keep card inside 100% width / 360px height container
  const left = Math.min(Math.max(card.x - CARD_W / 2, 8), 99999);
  const top  = card.y > 200 ? card.y - CARD_H - 18 : card.y + 18;

  const pnlColor = card.pnlPct >= 0 ? "#4ADE80" : "#F87171";
  const dayColor = card.dayChangePct >= 0 ? "#4ADE80" : "#F87171";
  const sign  = (v: number) => v >= 0 ? "+" : "";

  return (
    <div
      style={{
        position:       "absolute",
        left,
        top,
        width:          CARD_W,
        background:     "rgba(8,10,20,0.90)",
        backdropFilter: "blur(12px)",
        border:         "1px solid rgba(255,255,255,0.08)",
        borderRadius:   8,
        padding:        "10px 14px",
        pointerEvents:  "none",
        transition:     "opacity 120ms",
        zIndex:         10,
      }}
    >
      {/* Portfolio badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: card.portfolioColor }} />
        <span style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.08em", color: card.portfolioColor, opacity: 0.85 }}>
          {card.portfolioName}
        </span>
      </div>
      {/* Ticker */}
      <div style={{ fontSize: 18, fontFamily: "monospace", fontWeight: 700, color: "#fff", lineHeight: 1.1, marginBottom: 6 }}>
        {card.ticker}
      </div>
      {/* Market value */}
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.55)", marginBottom: 4 }}>
        ${Math.round(card.marketValue).toLocaleString("en-US")}
      </div>
      {/* P&L */}
      <div style={{ fontSize: 12, color: pnlColor, fontFamily: "monospace" }}>
        {sign(card.pnl)}${Math.abs(card.pnl).toFixed(2)} &nbsp;
        <span style={{ opacity: 0.8 }}>{sign(card.pnlPct)}{card.pnlPct.toFixed(1)}%</span>
      </div>
      {/* Day change */}
      {Math.abs(card.dayChangePct) > 0.01 && (
        <div style={{ fontSize: 11, color: dayColor, fontFamily: "monospace", marginTop: 2, opacity: 0.85 }}>
          today {sign(card.dayChangePct)}{card.dayChangePct.toFixed(2)}%
        </div>
      )}
    </div>
  );
}
```

Note: TypeScript may complain about the `DetailCard` prop type. Simplify by defining a local `CardData` interface at the top of the file and use that everywhere.

**Step 4: Verify build**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -8
```

**Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/ConstellationMap.tsx
git commit -m "feat: add hover/click detail card overlay to ConstellationMap"
```

---

## Task 4: Integrate into OverviewPage

**Files:**
- Modify: `dashboard/src/components/OverviewPage.tsx`

**Step 1: Import ConstellationMap**

At the top of `OverviewPage.tsx`, add:

```typescript
import ConstellationMap from "./ConstellationMap";
```

**Step 2: Replace WeightedMap with ConstellationMap in the MAP branch**

Find the section in `AllPositionsPanel` (around line 188–227) where the MAP/CHART toggle renders either `<WeightedMap ... />` or `<PerformanceChart ... />`.

Replace the `<WeightedMap ... />` branch with:

```tsx
<ConstellationMap positions={positions} portfolios={portfolios} />
```

The `AllPositionsPanel` component needs to accept a `portfolios` prop. Add it:

```typescript
function AllPositionsPanel({
  positions,
  portfolios,         // ← add this
  enriched,
}: {
  positions: CrossPortfolioMover[];
  portfolios: PortfolioSummary[];    // ← add this
  enriched: EnrichedSummary[];
}) {
```

Pass `portfolios={summaries}` when rendering `AllPositionsPanel` in the main page body.

**Step 3: Verify build**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -8
```

Fix any TypeScript errors.

**Step 4: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/OverviewPage.tsx
git commit -m "feat: integrate ConstellationMap into overview page MAP view"
```

---

## Final Verification

1. Open http://localhost:5173/ in the browser
2. Navigate to the overview page (click the GScott nav or the overview portfolio)
3. Click the MAP toggle button
4. Verify:
   - Dark `#07090f` background with starfield
   - Glowing nodes visible, sized by market value, colored by P&L
   - Nodes drift and settle into portfolio clusters
   - Cluster labels (MICROCAP, AI, etc.) visible with dashed rings
   - Arc lines between same-portfolio nodes
   - Hovering a node: dims others, shows detail card
   - Clicking a node: card persists, click again or click background to dismiss
   - Breathing animation visible (subtle radius oscillation)
5. Run final build: `cd dashboard && npm run build`
