# PerformanceChart Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace the broken WebGL ObeliskField with a dark, cinematic multi-portfolio performance line chart using Canvas 2D additive blending.

**Architecture:** Pure Canvas 2D component (`PerformanceChart.tsx`) — no Three.js, no external charting libs. Three-pass glow rendering with `globalCompositeOperation: "screen"`. Sparklines normalized to % return from inception. Mouse hover tracks a scan line with interpolated crosshair dots and a fixed-order tooltip.

**Tech Stack:** React 19, TypeScript, Canvas 2D API, `useRef`/`useEffect`/`useState`/`useMemo`/`useCallback`, `ResizeObserver`. No new npm deps.

**Design doc:** `docs/plans/2026-03-02-performance-chart-design.md`

---

## Context for Implementer

**Working directory:** `/Users/gregmclaughlin/MicroCapRebuilder/dashboard/`

**File being replaced:** `src/components/ObeliskField.tsx` — delete it. Create `src/components/PerformanceChart.tsx` instead.

**File being modified:** `src/components/OverviewPage.tsx` — update import + toggle label.

**Data shape available:**
```typescript
interface PortfolioSummary {
  id: string;
  name: string;
  sparkline?: number[];       // daily equity values — normalize to % return
  total_return_pct: number;   // final cumulative return %
  error?: string;
}
```

**Container:** 340px height, fills parent width.

**Color palette (fixed — do not change):**
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

---

## Task 1: Deps cleanup + scaffold + wiring

**Goal:** Delete ObeliskField, create empty PerformanceChart that renders the container, wire it into OverviewPage. Verify no build errors.

**Files:**
- Delete: `dashboard/src/components/ObeliskField.tsx`
- Create: `dashboard/src/components/PerformanceChart.tsx`
- Modify: `dashboard/src/components/OverviewPage.tsx`
- Modify: `dashboard/package.json`

**Step 1: Remove Three.js dependencies**

In `dashboard/package.json`, remove these four entries from `dependencies`:
- `"three"`
- `"@react-three/fiber"`
- `"@react-three/drei"`
- `"@types/three"` (may be in `devDependencies`)

Then run:
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm install
```
Expected: clean install, no three.js in node_modules.

**Step 2: Delete ObeliskField.tsx**

```bash
rm /Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/components/ObeliskField.tsx
```

**Step 3: Create PerformanceChart.tsx scaffold**

Create `dashboard/src/components/PerformanceChart.tsx`:

```tsx
import { useRef, useMemo, useState, useEffect, useCallback } from "react";
import type { PortfolioSummary } from "../lib/types";

// ── Constants ────────────────────────────────────────────────────────────────

const PAD_TOP    = 28;
const PAD_RIGHT  = 112;
const PAD_BOTTOM = 24;
const PAD_LEFT   = 40;

const CHART_PALETTE = [
  "#7dd3c8", // muted teal
  "#8b9cf4", // soft indigo
  "#e8b87a", // warm amber
  "#a3b8d4", // steel blue
  "#b8a8d4", // soft lavender
  "#8bbfa8", // sage green
  "#d4b8a8", // dusty rose
  "#9ab4c4", // slate
];

// ── Types ────────────────────────────────────────────────────────────────────

interface SeriesData {
  id: string;
  name: string;
  color: string;
  cum: number[];       // % return at each day index
  finalReturn: number; // cum[last]
}

// ── Component ────────────────────────────────────────────────────────────────

interface PerformanceChartProps {
  portfolios: PortfolioSummary[];
}

export default function PerformanceChart({ portfolios }: PerformanceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const [dims, setDims] = useState({ width: 600, height: 340 });

  // Scaffold — full implementation follows in subsequent tasks
  const series: SeriesData[] = useMemo(() => {
    return portfolios
      .filter((p) => !p.error && (p.sparkline?.length ?? 0) >= 2)
      .sort((a, b) => (b.total_return_pct ?? 0) - (a.total_return_pct ?? 0))
      .map((p, i) => {
        const base = p.sparkline![0];
        const cum  = p.sparkline!.map((v) => ((v - base) / base) * 100);
        return {
          id: p.id,
          name: p.name ?? p.id,
          color: CHART_PALETTE[i % CHART_PALETTE.length],
          cum,
          finalReturn: cum[cum.length - 1],
        };
      });
  }, [portfolios]);

  // ResizeObserver
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDims({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Size canvas for devicePixelRatio
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = dims.width  * dpr;
    canvas.height = dims.height * dpr;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);
  }, [dims]);

  if (series.length === 0) {
    return (
      <div style={{ height: "340px", display: "flex", alignItems: "center", justifyContent: "center", background: "#010107", borderRadius: "7px" }}>
        <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.2)", fontFamily: "monospace" }}>
          No portfolio history
        </p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        height: "340px",
        background: "#010107",
        borderRadius: "7px",
        overflow: "hidden",
        position: "relative",
        border: "1px solid var(--border-0)",
      }}
    >
      {/* Scanline texture overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "repeating-linear-gradient(0deg, transparent, transparent 1px, rgba(255,255,255,0.006) 1px, rgba(255,255,255,0.006) 2px)",
          pointerEvents: "none",
          zIndex: 1,
        }}
      />
      <canvas
        ref={canvasRef}
        style={{ display: "block", width: "100%", height: "100%" }}
      />
    </div>
  );
}
```

**Step 4: Update OverviewPage.tsx**

Find and replace the import at the top of `src/components/OverviewPage.tsx`:
```tsx
// OLD:
import ObeliskField from "./ObeliskField";
// NEW:
import PerformanceChart from "./PerformanceChart";
```

Find the toggle labels in `AllPositionsPanel`. They read `"OBELISK"`. Change to `"CHART"`:
```tsx
// OLD:
{v === "map" ? "MAP" : "OBELISK"}
// NEW:
{v === "map" ? "MAP" : "CHART"}
```

Find the JSX that renders `<ObeliskField portfolios={portfolios} />` and replace:
```tsx
// OLD:
: <ObeliskField portfolios={portfolios} />
// NEW:
: <PerformanceChart portfolios={portfolios} />
```

Also update the views array (the toggle values) — it references `"obelisk"`:
```tsx
// OLD:  (["map", "obelisk"] somewhere in AllPositionsPanel)
// Find it and change "obelisk" → "chart"
```

**Step 5: Verify build**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -20
```
Expected: clean build, zero TypeScript errors. No `ObeliskField` references remain.

**Step 6: Verify in browser**

```bash
# In one terminal (if not already running):
cd /Users/gregmclaughlin/MicroCapRebuilder
./run_dashboard.sh
```
Navigate to http://localhost:5173 → Overview page → click CHART toggle.
Expected: dark `#010107` container, 340px, scanline overlay visible, "No portfolio history" message if no data or a blank canvas with correct dimensions.

**Step 7: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/PerformanceChart.tsx
git add dashboard/src/components/OverviewPage.tsx
git add dashboard/package.json dashboard/package-lock.json
git commit -m "feat: scaffold PerformanceChart, wire into OverviewPage, remove three.js deps"
```

---

## Task 2: Canvas setup, Y-scale, and grid

**Goal:** Implement the coordinate system, guide line computation, and draw the background grid with Y-axis labels.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

**Step 1: Add scale utilities inside PerformanceChart.tsx, above the component**

Add these pure functions after the `CHART_PALETTE` constant:

```typescript
// ── Cubic-bezier easing: cubic-bezier(0.16, 1, 0.3, 1) ──────────────────────

function cubicBezierEase(t: number): number {
  const p1x = 0.16, p1y = 1.0, p2x = 0.3, p2y = 1.0;
  const cx = 3 * p1x, bx = 3 * (p2x - p1x) - cx, ax = 1 - cx - bx;
  const cy = 3 * p1y, by = 3 * (p2y - p1y) - cy, ay = 1 - cy - by;
  let u = t;
  for (let i = 0; i < 8; i++) {
    const xu = ((ax * u + bx) * u + cx) * u;
    const dxu = (3 * ax * u + 2 * bx) * u + cx;
    if (Math.abs(dxu) < 1e-6) break;
    u -= (xu - t) / dxu;
  }
  u = Math.max(0, Math.min(1, u));
  return ((ay * u + by) * u + cy) * u;
}

// ── Y scale ──────────────────────────────────────────────────────────────────

interface YScale {
  yMin: number;
  yMax: number;
  toPixelY: (pct: number) => number;
  guides: number[];
}

function computeYScale(allCums: number[][], chartH: number): YScale {
  let globalMin =  Infinity;
  let globalMax = -Infinity;
  for (const cum of allCums) {
    for (const v of cum) {
      if (v < globalMin) globalMin = v;
      if (v > globalMax) globalMax = v;
    }
  }
  if (!isFinite(globalMin)) { globalMin = -10; globalMax = 10; }

  const range = globalMax - globalMin || 20;
  const pad   = range * 0.12;
  const yMin  = globalMin - pad;
  const yMax  = globalMax + pad;

  const toPixelY = (pct: number): number =>
    PAD_TOP + ((yMax - pct) / (yMax - yMin)) * chartH;

  // Compute 3-5 nice guide values
  const roughStep = (yMax - yMin) / 4;
  const magnitude = Math.pow(10, Math.floor(Math.log10(Math.abs(roughStep) || 1)));
  const niceMultiples = [1, 2, 2.5, 5, 10];
  const mult = niceMultiples.find((m) => m * magnitude >= roughStep) ?? 10;
  const step = mult * magnitude;

  const guideSet = new Set<number>();
  const start = Math.ceil(yMin / step) * step;
  for (let v = start; v <= yMax + step * 0.01; v += step) {
    const rounded = Math.round(v * 10) / 10;
    guideSet.add(rounded);
  }
  // Always include 0 if in range
  if (yMin <= 0 && yMax >= 0) guideSet.add(0);

  const guides = [...guideSet]
    .filter((v) => v >= yMin && v <= yMax)
    .sort((a, b) => a - b)
    .slice(0, 5);

  return { yMin, yMax, toPixelY, guides };
}

// ── X scale ──────────────────────────────────────────────────────────────────

function toPixelX(dayIdx: number, maxLen: number, chartW: number): number {
  if (maxLen <= 1) return PAD_LEFT;
  return PAD_LEFT + (dayIdx / (maxLen - 1)) * chartW;
}
```

**Step 2: Add `drawGrid` function inside the component (as a useCallback)**

Inside the `PerformanceChart` component, add:

```typescript
const chartW = dims.width  - PAD_LEFT - PAD_RIGHT;
const chartH = dims.height - PAD_TOP  - PAD_BOTTOM;

const scale = useMemo(
  () => computeYScale(series.map((s) => s.cum), chartH),
  [series, chartH]
);

const maxLen = useMemo(
  () => Math.max(1, ...series.map((s) => s.cum.length)),
  [series]
);

const drawGrid = useCallback(
  (ctx: CanvasRenderingContext2D) => {
    const { toPixelY, guides } = scale;

    // Fill background
    ctx.fillStyle = "#010107";
    ctx.fillRect(0, 0, dims.width, dims.height);

    ctx.save();
    ctx.font = "600 8px/1 monospace";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";

    for (const g of guides) {
      const py = toPixelY(g);
      const isZero = g === 0;

      // Horizontal guide line
      ctx.beginPath();
      ctx.moveTo(PAD_LEFT - 6, py);
      ctx.lineTo(dims.width - PAD_RIGHT + 8, py);
      ctx.strokeStyle = isZero
        ? "rgba(255,255,255,0.10)"
        : "rgba(255,255,255,0.05)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Y-axis label
      const label = g === 0 ? "0%" : `${g > 0 ? "+" : ""}${g.toFixed(0)}%`;
      ctx.fillStyle = isZero
        ? "rgba(255,255,255,0.28)"
        : "rgba(255,255,255,0.18)";
      ctx.fillText(label, PAD_LEFT - 8, py);
    }

    ctx.restore();
  },
  [scale, dims]
);
```

**Step 3: Add a draw effect that calls drawGrid**

```typescript
useEffect(() => {
  const canvas = canvasRef.current;
  if (!canvas || dims.width === 0) return;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, dims.width, dims.height);
  drawGrid(ctx);
}, [drawGrid, dims]);
```

**Step 4: Verify in browser**

Navigate to CHART view. Expected:
- Near-black background
- 3–5 faint solid horizontal hairlines
- Y-axis percentage labels on the left (0%, +25%, etc. based on actual data)
- Zero line slightly brighter than others

**Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/PerformanceChart.tsx
git commit -m "feat: add canvas coordinate system, Y-scale, and grid to PerformanceChart"
```

---

## Task 3: Glow line rendering

**Goal:** Draw the actual portfolio lines with three-pass glow effect and additive blending.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

**Step 1: Add `catmullRomPath` helper (above the component)**

```typescript
/**
 * Traces a smooth Catmull-Rom spline through pts onto ctx.
 * Converts to cubic bezier control points for Canvas bezierCurveTo.
 */
function catmullRomPath(
  ctx: CanvasRenderingContext2D,
  pts: [number, number][]
): void {
  if (pts.length < 2) return;
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
    ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1]);
  }
}
```

**Step 2: Add `drawLines` useCallback inside the component**

The `progress` parameter clips the X range to 0–progress (for the mount animation).
The `dimmedAlpha` parameter overrides global alpha for non-hovered lines.

```typescript
const drawLines = useCallback(
  (
    ctx: CanvasRenderingContext2D,
    progress: number,          // 0→1 clip for mount animation
    hoveredIdx: number | null  // null = no hover; index = one series fully lit
  ) => {
    const { toPixelY } = scale;
    const clipX = PAD_LEFT + chartW * progress;

    ctx.save();
    // Clip to animated reveal region
    ctx.beginPath();
    ctx.rect(0, PAD_TOP, clipX, chartH + PAD_BOTTOM);
    ctx.clip();

    for (let si = 0; si < series.length; si++) {
      const s = series[si];
      const pts: [number, number][] = s.cum.map((v, i) => [
        toPixelX(i, maxLen, chartW),
        toPixelY(v),
      ]);

      if (pts.length < 2) continue;

      // Dimming: if something is hovered and this isn't it, reduce alpha
      const baseAlpha = hoveredIdx !== null && hoveredIdx !== si ? 0.35 : 1.0;

      // ── Area fill (draw first, source-over, below the glowing lines) ─────
      ctx.save();
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = baseAlpha * 0.04;
      const grad = ctx.createLinearGradient(0, toPixelY(scale.yMax), 0, toPixelY(scale.yMin));
      grad.addColorStop(0, s.color);
      grad.addColorStop(1, "transparent");
      ctx.beginPath();
      catmullRomPath(ctx, pts);
      ctx.lineTo(pts[pts.length - 1][0], toPixelY(0));
      ctx.lineTo(pts[0][0], toPixelY(0));
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.restore();

      // ── Three-pass glow (screen blending) ───────────────────────────────
      ctx.globalCompositeOperation = "screen";

      // Pass 1: wide blurred halo
      ctx.save();
      ctx.filter = "blur(2px)";
      ctx.globalAlpha = baseAlpha * 0.15;
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 10;
      ctx.lineJoin = "round";
      ctx.lineCap  = "round";
      ctx.beginPath();
      catmullRomPath(ctx, pts);
      ctx.stroke();
      ctx.restore();

      // Pass 2: inner glow
      ctx.save();
      ctx.globalAlpha = baseAlpha * 0.40;
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.lineCap  = "round";
      ctx.beginPath();
      catmullRomPath(ctx, pts);
      ctx.stroke();
      ctx.restore();

      // Pass 3: crisp core
      ctx.save();
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = baseAlpha * 1.0;
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 1.5;
      ctx.lineJoin = "round";
      ctx.lineCap  = "round";
      ctx.beginPath();
      catmullRomPath(ctx, pts);
      ctx.stroke();
      ctx.restore();
    }

    ctx.restore(); // remove clip
  },
  [series, scale, chartW, chartH, maxLen]
);
```

**Step 3: Update the draw effect to call drawLines**

Replace the draw effect from Task 2 with:

```typescript
useEffect(() => {
  const canvas = canvasRef.current;
  if (!canvas || dims.width === 0) return;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, dims.width, dims.height);
  drawGrid(ctx);
  drawLines(ctx, 1, null); // progress=1 (full), no hover yet
}, [drawGrid, drawLines, dims]);
```

**Step 4: Verify in browser**

Navigate to CHART view. Expected:
- Glowing colored lines drawn across the chart
- Lines have visible glow halo (subtle, not flashy)
- Overlapping lines brighten slightly at crossings
- Near-black area fill under each line
- Correct Y positioning (highest return = line higher on chart)

**Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/PerformanceChart.tsx
git commit -m "feat: add three-pass glow line rendering to PerformanceChart"
```

---

## Task 4: Endpoint dots and labels

**Goal:** Draw the permanent endpoint treatment — filled dot at the line's last data point and floating label in the right zone.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

**Step 1: Add `drawEndpoints` useCallback**

```typescript
const drawEndpoints = useCallback(
  (ctx: CanvasRenderingContext2D, alpha: number) => {
    if (alpha <= 0) return;
    const { toPixelY } = scale;

    ctx.save();
    ctx.globalAlpha = alpha;

    // Sort labels by Y position to avoid collision (render bottom-up)
    const labeled = series.map((s, i) => {
      const lastX = toPixelX(s.cum.length - 1, maxLen, chartW);
      const lastY = toPixelY(s.cum[s.cum.length - 1]);
      return { s, i, lastX, lastY };
    });

    for (const { s, lastX, lastY } of labeled) {
      // Dot
      ctx.beginPath();
      ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
      ctx.fillStyle = s.color;
      ctx.fill();

      // Label: "NAME +XX.X%"
      const ret   = s.finalReturn;
      const sign  = ret >= 0 ? "+" : "";
      const label = `${s.id.toUpperCase()}  ${sign}${ret.toFixed(1)}%`;

      const labelX = dims.width - PAD_RIGHT + 14;

      ctx.font      = "700 8.5px/1 monospace";
      ctx.fillStyle = s.color;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(label, labelX, lastY);
    }

    ctx.restore();
  },
  [series, scale, dims, chartW, maxLen]
);
```

**Step 2: Update the draw effect**

```typescript
useEffect(() => {
  const canvas = canvasRef.current;
  if (!canvas || dims.width === 0) return;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, dims.width, dims.height);
  drawGrid(ctx);
  drawLines(ctx, 1, null);
  drawEndpoints(ctx, 1);
}, [drawGrid, drawLines, drawEndpoints, dims]);
```

**Step 3: Verify in browser**

Expected:
- Each line ends with a 3px filled dot in the portfolio color
- Right of the chart (in the 112px zone): `MICROCAP  +42.3%` etc.
- Labels positioned at the correct Y height matching the line endpoint
- Labels don't visually overlap for normal data (4-5 portfolios)
- Text is small, monospace, color-matched

**Step 4: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/PerformanceChart.tsx
git commit -m "feat: add endpoint dots and floating labels to PerformanceChart"
```

---

## Task 5: Mount animation

**Goal:** Lines draw left-to-right over 1.2s on mount. Endpoint labels/dots fade in after the draw completes.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

**Step 1: Add animation state refs and state**

Inside the component, add:

```typescript
const [animProgress,    setAnimProgress]    = useState(0);
const [endpointsAlpha,  setEndpointsAlpha]  = useState(0);
const rafRef         = useRef<number | null>(null);
const startTimeRef   = useRef<number | null>(null);
const endStartRef    = useRef<number | null>(null);
```

**Step 2: Add animation RAF loop**

```typescript
useEffect(() => {
  // Reset on series change
  setAnimProgress(0);
  setEndpointsAlpha(0);
  startTimeRef.current = null;
  endStartRef.current  = null;
  if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);

  const DRAW_DURATION = 1.2;  // seconds
  const FADE_DURATION = 0.3;  // seconds

  function tick(now: number) {
    const t0 = startTimeRef.current;
    if (t0 === null) {
      startTimeRef.current = now;
      rafRef.current = requestAnimationFrame(tick);
      return;
    }
    const elapsed = (now - t0) / 1000;

    if (elapsed < DRAW_DURATION) {
      const t = elapsed / DRAW_DURATION;
      setAnimProgress(cubicBezierEase(t));
      rafRef.current = requestAnimationFrame(tick);
    } else {
      setAnimProgress(1);
      // Start endpoint fade
      if (endStartRef.current === null) endStartRef.current = now;
      const fadeElapsed = (now - endStartRef.current) / 1000;
      const fadeT = Math.min(fadeElapsed / FADE_DURATION, 1);
      setEndpointsAlpha(fadeT);
      if (fadeT < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    }
  }

  rafRef.current = requestAnimationFrame(tick);
  return () => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
  };
}, [series.length]); // reset and replay when series changes
```

**Step 3: Update the draw effect to use animProgress and endpointsAlpha**

```typescript
useEffect(() => {
  const canvas = canvasRef.current;
  if (!canvas || dims.width === 0) return;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, dims.width, dims.height);
  drawGrid(ctx);
  drawLines(ctx, animProgress, null);
  drawEndpoints(ctx, endpointsAlpha);
}, [drawGrid, drawLines, drawEndpoints, dims, animProgress, endpointsAlpha]);
```

**Step 4: Verify in browser**

Refresh the page and navigate to CHART view. Expected:
- All lines draw simultaneously from left to right, expo-out eased, over ~1.2s
- After lines complete, endpoint dots and labels fade in smoothly (~0.3s)
- Refreshing the page replays the animation
- No flickering or half-drawn states

**Step 5: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/PerformanceChart.tsx
git commit -m "feat: add mount animation to PerformanceChart (left-to-right line draw + endpoint fade)"
```

---

## Task 6: Hover interaction

**Goal:** Vertical scan line, interpolated intersection dots, dimming of non-closest lines, fixed-order tooltip.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

**Step 1: Add hover state**

```typescript
const [hoverX,      setHoverX]      = useState<number | null>(null);
const [hoveredIdx,  setHoveredIdx]  = useState<number | null>(null);
```

**Step 2: Add interpolation helper (above component)**

```typescript
/** Linear interpolation of a series' cum return at a given pixel X. */
function interpolateAtX(
  cum: number[],
  pixelX: number,
  maxLen: number,
  chartW: number
): number | null {
  if (cum.length === 0) return null;
  // Convert pixelX to fractional index
  const fracIdx = ((pixelX - PAD_LEFT) / chartW) * (maxLen - 1);
  if (fracIdx < 0 || fracIdx > cum.length - 1) return null;
  const lo = Math.floor(fracIdx);
  const hi = Math.min(lo + 1, cum.length - 1);
  const t  = fracIdx - lo;
  return cum[lo] * (1 - t) + cum[hi] * t;
}
```

**Step 3: Add `drawHover` useCallback**

```typescript
const drawHover = useCallback(
  (ctx: CanvasRenderingContext2D, pixelX: number) => {
    const { toPixelY } = scale;

    // Scan line
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(pixelX, PAD_TOP);
    ctx.lineTo(pixelX, dims.height - PAD_BOTTOM);
    ctx.strokeStyle = "rgba(255,255,255,0.12)";
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();

    // Crosshair dots + collect tooltip rows
    const rows: { color: string; name: string; ret: number }[] = [];
    for (const s of series) {
      const v = interpolateAtX(s.cum, pixelX, maxLen, chartW);
      if (v === null) continue;
      const py = toPixelY(v);
      ctx.beginPath();
      ctx.arc(pixelX, py, 4, 0, Math.PI * 2);
      ctx.fillStyle = s.color;
      ctx.fill();
      rows.push({ color: s.color, name: s.id.toUpperCase(), ret: v });
    }

    if (rows.length === 0) return;

    // Tooltip — fixed order (series array is sorted by finalReturn on mount)
    const LINE_H  = 16;
    const PAD_H   = 8;
    const CARD_W  = 130;
    const cardH   = rows.length * LINE_H + PAD_H * 2;

    // Position tooltip: left of cursor if near right edge
    let tx = pixelX + 12;
    if (tx + CARD_W > dims.width - PAD_RIGHT) tx = pixelX - CARD_W - 12;
    const ty = PAD_TOP + 8;

    // Card background
    ctx.save();
    ctx.fillStyle   = "rgba(4,4,12,0.94)";
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth   = 1;
    ctx.beginPath();
    ctx.roundRect(tx, ty, CARD_W, cardH, 4);
    ctx.fill();
    ctx.stroke();

    // Rows
    ctx.font      = "600 8.5px/1 monospace";
    ctx.textBaseline = "middle";
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const ry  = ty + PAD_H + i * LINE_H + LINE_H / 2;

      // Color dot
      ctx.beginPath();
      ctx.arc(tx + 10, ry, 3, 0, Math.PI * 2);
      ctx.fillStyle = row.color;
      ctx.fill();

      // Name
      ctx.fillStyle = "rgba(255,255,255,0.65)";
      ctx.textAlign = "left";
      ctx.fillText(row.name, tx + 20, ry);

      // Return value
      const sign  = row.ret >= 0 ? "+" : "";
      const label = `${sign}${row.ret.toFixed(1)}%`;
      ctx.fillStyle = row.ret >= 0 ? "rgba(180,230,210,0.85)" : "rgba(230,160,160,0.85)";
      ctx.textAlign = "right";
      ctx.fillText(label, tx + CARD_W - 8, ry);
    }

    ctx.restore();
  },
  [series, scale, dims, chartW, maxLen]
);
```

**Step 4: Add mouse event handlers to the canvas**

Inside the component, add:

```typescript
const handleMouseMove = useCallback(
  (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;

    // Clamp to chart area
    if (x < PAD_LEFT || x > dims.width - PAD_RIGHT) {
      setHoverX(null);
      setHoveredIdx(null);
      return;
    }

    setHoverX(x);

    // Determine closest series to cursor Y
    const { toPixelY } = scale;
    const y = e.clientY - rect.top;
    let closest = 0;
    let closestDist = Infinity;
    series.forEach((s, i) => {
      const v = interpolateAtX(s.cum, x, maxLen, chartW);
      if (v === null) return;
      const dist = Math.abs(toPixelY(v) - y);
      if (dist < closestDist) { closestDist = dist; closest = i; }
    });
    setHoveredIdx(closest);
  },
  [series, scale, dims, chartW, maxLen]
);

const handleMouseLeave = useCallback(() => {
  setHoverX(null);
  setHoveredIdx(null);
}, []);
```

**Step 5: Update the draw effect to include hover**

```typescript
useEffect(() => {
  const canvas = canvasRef.current;
  if (!canvas || dims.width === 0) return;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, dims.width, dims.height);
  drawGrid(ctx);
  drawLines(ctx, animProgress, hoverX !== null ? hoveredIdx : null);
  drawEndpoints(ctx, endpointsAlpha);
  if (hoverX !== null) drawHover(ctx, hoverX);
}, [drawGrid, drawLines, drawEndpoints, drawHover, dims, animProgress, endpointsAlpha, hoverX, hoveredIdx]);
```

**Step 6: Wire mouse handlers onto the canvas element**

Update the `<canvas>` JSX:

```tsx
<canvas
  ref={canvasRef}
  style={{ display: "block", width: "100%", height: "100%" }}
  onMouseMove={handleMouseMove}
  onMouseLeave={handleMouseLeave}
/>
```

**Step 7: Verify in browser**

Move mouse over the CHART view. Expected:
- Vertical scan line follows cursor (only within chart area, not label zone)
- 4px dots appear at each series' interpolated Y at cursor X
- Line closest to cursor Y stays full brightness; others dim to 35% opacity
- Tooltip card appears: all portfolios listed in fixed order (best return first), name left, +/-% right, color-coded green/red
- Moving off the chart: everything returns to idle state (full brightness, endpoint labels only)

**Step 8: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/PerformanceChart.tsx
git commit -m "feat: add hover scan line, crosshair dots, dimming, and tooltip to PerformanceChart"
```

---

## Task 7: Polish, edge cases, and final verification

**Goal:** Handle edge cases, tighten label collision avoidance, verify the full experience.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

**Step 1: Label collision avoidance**

The endpoint labels can overlap if two portfolios have similar final returns. Add vertical nudging:

In `drawEndpoints`, replace the label rendering loop with a collision-aware version:

```typescript
// Sort by Y descending (top of chart first) to assign positions top-down
const sorted = labeled.slice().sort((a, b) => a.lastY - b.lastY);
const MIN_GAP = 12; // px minimum vertical gap between labels
const assignedY: number[] = [];

for (const item of sorted) {
  // Find a Y that doesn't collide with already-assigned labels
  let y = item.lastY;
  for (const used of assignedY) {
    if (Math.abs(y - used) < MIN_GAP) {
      y = used + MIN_GAP;
    }
  }
  assignedY.push(y);

  // Draw dot at actual line Y, label at adjusted Y
  ctx.beginPath();
  ctx.arc(item.lastX, item.lastY, 3, 0, Math.PI * 2);
  ctx.fillStyle = item.s.color;
  ctx.fill();

  const ret   = item.s.finalReturn;
  const sign  = ret >= 0 ? "+" : "";
  const label = `${item.s.id.toUpperCase()}  ${sign}${ret.toFixed(1)}%`;
  ctx.font         = "700 8.5px/1 monospace";
  ctx.fillStyle    = item.s.color;
  ctx.textAlign    = "left";
  ctx.textBaseline = "middle";
  ctx.fillText(label, dims.width - PAD_RIGHT + 14, y);
}
```

**Step 2: Handle single-portfolio case**

In `drawLines`, if `series.length === 1`, skip the dimming logic entirely (nothing to dim). Already handled because `hoveredIdx !== si` is never true when there's only one series.

**Step 3: Handle portfolios with very short sparklines**

In the `series` useMemo, the filter already excludes sparklines with fewer than 2 points. Confirm it:
```typescript
.filter((p) => !p.error && (p.sparkline?.length ?? 0) >= 2)
```

**Step 4: Verify `ctx.roundRect` browser support**

`roundRect` is supported in Chrome 99+, Safari 15.4+, Firefox 112+. For the tooltip card, add a fallback:

Replace the `ctx.roundRect` call in `drawHover` with:
```typescript
// Use roundRect with fallback
if (typeof ctx.roundRect === "function") {
  ctx.roundRect(tx, ty, CARD_W, cardH, 4);
} else {
  ctx.rect(tx, ty, CARD_W, cardH);
}
```

**Step 5: Final visual verification checklist**

Open http://localhost:5173 → Overview → CHART.

Check each of the following:
- [ ] Lines glow cleanly — not flashy, not flat. Luminous.
- [ ] Colors are cohesive — muted teal, indigo, amber, etc. No neon.
- [ ] Grid guides are solid hairlines (not dashed), 3–5 of them, zero line slightly brighter
- [ ] Y-axis labels: `0%`, `+25%`, `-10%` etc. — small, faint, right-aligned
- [ ] Endpoint dots: 3px, clean
- [ ] Endpoint labels: in the 112px right zone, no overlap
- [ ] Mount animation: left-to-right draw, expo-out, then endpoint fade-in
- [ ] Hover: scan line follows cursor, dots appear at each line, non-closest lines dim
- [ ] Tooltip: fixed order, clean layout, green/red return values
- [ ] Scanline texture: barely visible CRT quality
- [ ] MAP toggle still works correctly
- [ ] No Three.js in the network tab (deps removed)

**Step 6: Build verification**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -20
```
Expected: zero errors, zero warnings about missing modules.

**Step 7: Final commit + GitHub push**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/PerformanceChart.tsx
git commit -m "feat: polish PerformanceChart — label collision avoidance, roundRect fallback, edge cases"
git push
```
