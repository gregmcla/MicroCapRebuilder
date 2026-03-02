# Performance Obelisk Field — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the scatter plot in the AllPositionsPanel with a pseudo-3D isometric sculpture field where each portfolio becomes a vertical monument shaped by its cumulative performance velocity and drawdowns.

**Architecture:** New `ObeliskField.tsx` component renders pure SVG. Geometry computed from `PortfolioSummary.sparkline[]`. Front face + right face + top cap = 3D illusion. All bodies monochrome obsidian. Portfolio color used only for rim light, crown glow, top-10% internal bleed. Load animation via `requestAnimationFrame` clipPath reveal. `AllPositionsPanel` in `OverviewPage.tsx` receives `portfolios: PortfolioSummary[]` alongside existing `positions` prop. Toggle label changes PLOT → OBELISK.

**Tech Stack:** React 19, SVG, TypeScript — no new dependencies.

---

## Constants (used across all tasks)

```typescript
const CONTAINER_W = 800;
const CONTAINER_H = 340;
const BASELINE_Y = 295;     // y of 0% return ground plane
const OBELISK_HEIGHT = 245; // max column height in px (at highest return)
const COL_BASE_WIDTH = 36;  // base column width in px
const FLARE_K = 4.0;        // velocity → width scaling
const SCAR_K = 1.8;         // drawdown magnitude → width reduction
const MIN_WIDTH = 8;         // minimum column width (never zero)
const DEPTH_X = 14;         // isometric right-face offset x
const DEPTH_Y = -7;         // isometric right-face offset y (up)
```

---

### Task 1: Geometry utility functions

**Files:**
- Create: `dashboard/src/components/ObeliskField.tsx`

Create the file with all geometry pure functions. No React yet — just math.

**Step 1: Create the file with geometry functions**

```typescript
/** Performance Obelisk Field — sculpted portfolio monuments. */

import { useMemo, useState, useEffect, useRef } from "react";
import type { PortfolioSummary } from "../lib/types";

// ── Constants ────────────────────────────────────────────────────────────────

const CONTAINER_W = 800;
const CONTAINER_H = 340;
const BASELINE_Y = 295;
const OBELISK_HEIGHT = 245;
const COL_BASE_WIDTH = 36;
const FLARE_K = 4.0;
const SCAR_K = 1.8;
const MIN_WIDTH = 8;
const DEPTH_X = 14;
const DEPTH_Y = -7;

// ── Geometry ─────────────────────────────────────────────────────────────────

interface ObeliskGeometry {
  cum: number[];        // cumulative return % at each step
  vel: number[];        // smoothed velocity (first derivative)
  dd: number[];         // drawdown from prior high (≤ 0)
  widths: number[];     // column half-total-width at each step
  finalReturn: number;  // cum[last]
  isNewHigh: boolean;   // ended at all-time high
  colTopY: number;      // y of crown (BASELINE_Y - finalReturn * scale)
}

function computeObeliskGeometry(
  sparkline: number[],
  scale: number        // pixels per percentage point, shared across all columns
): ObeliskGeometry | null {
  if (!sparkline || sparkline.length < 2) return null;

  const base = sparkline[0];
  if (base === 0) return null;

  // Step 1: cumulative return at each point
  const cum = sparkline.map((v) => ((v - base) / base) * 100);

  // Step 2: velocity (first derivative)
  const velRaw = cum.map((v, i) => (i === 0 ? 0 : v - cum[i - 1]));

  // Step 3: smooth velocity with 5-point moving average
  const vel = velRaw.map((_, i) => {
    const slice = velRaw.slice(Math.max(0, i - 2), Math.min(velRaw.length, i + 3));
    return slice.reduce((a, b) => a + b, 0) / slice.length;
  });

  // Step 4: drawdown from prior high
  let runMax = cum[0];
  const dd = cum.map((v) => {
    runMax = Math.max(runMax, v);
    return v - runMax; // always ≤ 0
  });

  // Step 5: width at each step
  const widths = vel.map((v, i) =>
    Math.max(MIN_WIDTH, COL_BASE_WIDTH + v * FLARE_K + dd[i] * SCAR_K)
  );

  const finalReturn = cum[cum.length - 1];
  const clampedReturn = Math.max(finalReturn, 0.5); // negative = stub column
  const colTopY = BASELINE_Y - clampedReturn * scale;

  const maxCum = Math.max(...cum);
  const isNewHigh = finalReturn >= maxCum - 0.01;

  return { cum, vel, dd, widths, finalReturn, isNewHigh, colTopY };
}

// ── Path builders ─────────────────────────────────────────────────────────────

/** Smooth polygon for the front face of the column. */
function buildFrontFace(
  colX: number,
  colTopY: number,
  widths: number[]
): string {
  const N = widths.length;
  const colH = BASELINE_Y - colTopY;

  // y for each time step: linear bottom→top
  const ys = widths.map((_, i) => BASELINE_Y - (i / (N - 1)) * colH);

  const L: [number, number][] = ys.map((y, i) => [colX - widths[i] / 2, y]);
  const R: [number, number][] = ys.map((y, i) => [colX + widths[i] / 2, y]);

  // Smooth path: quadratic beziers between adjacent points
  const smooth = (pts: [number, number][], reverse = false) => {
    const arr = reverse ? [...pts].reverse() : pts;
    let d = `L ${arr[0][0].toFixed(1)} ${arr[0][1].toFixed(1)}`;
    for (let i = 1; i < arr.length; i++) {
      const [cx, cy] = arr[i - 1];
      const [nx, ny] = arr[i];
      const mx = ((cx + nx) / 2).toFixed(1);
      const my = ((cy + ny) / 2).toFixed(1);
      d += ` Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${mx} ${my}`;
    }
    d += ` L ${arr[arr.length - 1][0].toFixed(1)} ${arr[arr.length - 1][1].toFixed(1)}`;
    return d;
  };

  return (
    `M ${L[0][0].toFixed(1)} ${L[0][1].toFixed(1)}` +  // bottom-left
    smooth(L).slice(1) +                                  // up left edge
    ` L ${R[N - 1][0].toFixed(1)} ${R[N - 1][1].toFixed(1)}` + // top-right
    smooth(R, true).slice(1) +                            // down right edge
    " Z"
  );
}

/** Parallelogram for the right (shadow) face. */
function buildRightFace(
  colX: number,
  colTopY: number,
  widths: number[]
): string {
  const N = widths.length;
  const colH = BASELINE_Y - colTopY;
  const ys = widths.map((_, i) => BASELINE_Y - (i / (N - 1)) * colH);

  // Front right edge
  const fr: [number, number][] = ys.map((y, i) => [colX + widths[i] / 2, y]);
  // Back right edge (isometric offset)
  const br: [number, number][] = fr.map(([x, y]) => [x + DEPTH_X, y + DEPTH_Y]);

  let d = `M ${fr[0][0].toFixed(1)} ${fr[0][1].toFixed(1)}`;
  for (let i = 1; i < N; i++) d += ` L ${fr[i][0].toFixed(1)} ${fr[i][1].toFixed(1)}`;
  d += ` L ${br[N - 1][0].toFixed(1)} ${br[N - 1][1].toFixed(1)}`;
  for (let i = N - 2; i >= 0; i--) d += ` L ${br[i][0].toFixed(1)} ${br[i][1].toFixed(1)}`;
  return d + " Z";
}

/** Small parallelogram cap at the crown. */
function buildTopCap(colX: number, colTopY: number, topWidth: number): string {
  const tl: [number, number] = [colX - topWidth / 2, colTopY];
  const tr: [number, number] = [colX + topWidth / 2, colTopY];
  const trb: [number, number] = [tr[0] + DEPTH_X, tr[1] + DEPTH_Y];
  const tlb: [number, number] = [tl[0] + DEPTH_X, tl[1] + DEPTH_Y];
  return `M ${tl[0]} ${tl[1]} L ${tr[0]} ${tr[1]} L ${trb[0]} ${trb[1]} L ${tlb[0]} ${tlb[1]} Z`;
}

/** Rim light path — right edge of front face only. */
function buildRimPath(
  colX: number,
  colTopY: number,
  widths: number[]
): string {
  const N = widths.length;
  const colH = BASELINE_Y - colTopY;
  const ys = widths.map((_, i) => BASELINE_Y - (i / (N - 1)) * colH);
  const R: [number, number][] = ys.map((y, i) => [colX + widths[i] / 2, y]);

  let d = `M ${R[0][0].toFixed(1)} ${R[0][1].toFixed(1)}`;
  for (let i = 1; i < N; i++) {
    const [cx, cy] = R[i - 1];
    const [nx, ny] = R[i];
    const mx = ((cx + nx) / 2).toFixed(1);
    const my = ((cy + ny) / 2).toFixed(1);
    d += ` Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${mx} ${my}`;
  }
  return d + ` L ${R[N - 1][0].toFixed(1)} ${R[N - 1][1].toFixed(1)}`;
}
```

**Step 2: TypeScript check**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit 2>&1
```
Expected: no errors (file has no JSX yet, just functions).

**Step 3: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/ObeliskField.tsx
git commit -m "feat: obelisk geometry utility functions"
```

---

### Task 2: ObeliskColumn component (static, no animation)

**Files:**
- Modify: `dashboard/src/components/ObeliskField.tsx`

Append the SVG defs and `ObeliskColumn` component to the file.

**Step 1: Append SVG defs block and ObeliskColumn**

Add after the geometry section:

```typescript
// ── SVG Defs (shared, rendered once in the outer SVG) ─────────────────────────

export function ObeliskDefs() {
  return (
    <defs>
      {/* Rim light blur */}
      <filter id="ob-rim-blur" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="0.8" />
      </filter>
      {/* Crown glow blur */}
      <filter id="ob-crown-blur" x="-100%" y="-100%" width="300%" height="300%">
        <feGaussianBlur stdDeviation="4" />
      </filter>
      {/* Beam blur */}
      <filter id="ob-beam-blur" x="-200%" y="-200%" width="500%" height="500%">
        <feGaussianBlur stdDeviation="2" />
      </filter>
      {/* Reflection blur */}
      <filter id="ob-reflect-blur">
        <feGaussianBlur stdDeviation="1.2" />
      </filter>
    </defs>
  );
}

// ── Crown components ──────────────────────────────────────────────────────────

function PositiveCrown({
  colX, colTopY, topWidth, color, isNewHigh, crownVisible,
}: {
  colX: number; colTopY: number; topWidth: number;
  color: string; isNewHigh: boolean; crownVisible: boolean;
}) {
  if (!crownVisible) return null;
  const cy = colTopY - 4;
  const rx = topWidth * 0.55;
  return (
    <g>
      {/* Glow ellipse */}
      <ellipse cx={colX} cy={cy} rx={rx} ry={5}
        fill={color} opacity={0.32} filter="url(#ob-crown-blur)" />
      {/* Tight crisp halo */}
      <ellipse cx={colX} cy={cy} rx={rx * 0.6} ry={3}
        fill={color} opacity={0.18} />
      {/* New-high beam */}
      {isNewHigh && (
        <line
          x1={colX} y1={colTopY - 4}
          x2={colX} y2={colTopY - 22}
          stroke={color} strokeWidth={1.5} strokeOpacity={0.55}
          filter="url(#ob-beam-blur)"
        />
      )}
    </g>
  );
}

function NegativeCrown({
  colX, colTopY, topWidth, color, crownVisible,
}: {
  colX: number; colTopY: number; topWidth: number;
  color: string; crownVisible: boolean;
}) {
  if (!crownVisible) return null;
  // 3 fractured skewed shards
  const shards: [number, number, number, number][] = [
    [colX - topWidth * 0.3, colTopY, colX - topWidth * 0.05, colTopY - 4],
    [colX - topWidth * 0.05, colTopY - 1, colX + topWidth * 0.25, colTopY - 5],
    [colX + topWidth * 0.18, colTopY, colX + topWidth * 0.38, colTopY - 3],
  ];
  return (
    <g opacity={0.6}>
      {shards.map(([x1, y1, x2, y2], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
          stroke={color} strokeWidth={1} opacity={0.5} />
      ))}
      <ellipse cx={colX} cy={colTopY} rx={topWidth * 0.4} ry={2.5}
        fill={color} opacity={0.12} filter="url(#ob-crown-blur)" />
    </g>
  );
}

// ── Single column ─────────────────────────────────────────────────────────────

interface ObeliskColumnProps {
  geo: ObeliskGeometry;
  colX: number;
  color: string;
  id: string;
  animProgress: number;   // 0→1 clip reveal
  crownVisible: boolean;
}

function ObeliskColumn({ geo, colX, color, id, animProgress, crownVisible }: ObeliskColumnProps) {
  const { widths, colTopY, finalReturn, isNewHigh } = geo;
  const topWidth = widths[widths.length - 1];

  const frontPath = useMemo(() => buildFrontFace(colX, colTopY, widths), [colX, colTopY, widths]);
  const rightPath = useMemo(() => buildRightFace(colX, colTopY, widths), [colX, colTopY, widths]);
  const capPath   = useMemo(() => buildTopCap(colX, colTopY, topWidth), [colX, colTopY, topWidth]);
  const rimPath   = useMemo(() => buildRimPath(colX, colTopY, widths), [colX, colTopY, widths]);

  const colH = BASELINE_Y - colTopY;
  const clipY = BASELINE_Y - colH * animProgress;
  const clipH = colH * animProgress + 40; // +40 for crown glow bleed

  // gradient IDs unique per column
  const bodyGradId = `ob-body-${id}`;
  const rimGradId  = `ob-rim-${id}`;
  const reflMaskId = `ob-rm-${id}`;
  const clipId     = `ob-clip-${id}`;

  return (
    <g>
      <defs>
        {/* Body gradient: near-black base, portfolio color bleeds top 10% */}
        <linearGradient id={bodyGradId} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%"   stopColor="#07070f" stopOpacity="1" />
          <stop offset="88%"  stopColor="#0d0d1a" stopOpacity="1" />
          <stop offset="100%" stopColor={color}   stopOpacity="0.18" />
        </linearGradient>

        {/* Rim light gradient: full at crown, dim at base */}
        <linearGradient id={rimGradId} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%"   stopColor={color} stopOpacity="0.15" />
          <stop offset="100%" stopColor={color} stopOpacity="0.85" />
        </linearGradient>

        {/* Reflection mask: opaque at top, fades down */}
        <linearGradient id={`${reflMaskId}-g`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="white" stopOpacity="1" />
          <stop offset="100%" stopColor="white" stopOpacity="0" />
        </linearGradient>
        <mask id={reflMaskId}>
          <rect x={colX - 120} y={BASELINE_Y} width={240} height={50}
            fill={`url(#${reflMaskId}-g)`} />
        </mask>

        {/* Animation clip */}
        <clipPath id={clipId}>
          <rect x={colX - 120} y={clipY} width={240} height={clipH} />
        </clipPath>
      </defs>

      {/* Floor reflection */}
      <g
        transform={`translate(0, ${BASELINE_Y * 2}) scale(1, -1)`}
        opacity={0.14}
        filter="url(#ob-reflect-blur)"
        mask={`url(#${reflMaskId})`}
      >
        <path d={frontPath} fill={`url(#${bodyGradId})`} />
        <path d={rightPath} fill="#030306" />
      </g>

      {/* Column body — clipped by animation rect */}
      <g clipPath={`url(#${clipId})`}>
        {/* Right (shadow) face — rendered behind front */}
        <path d={rightPath} fill="#030306" />
        {/* Top cap */}
        <path d={capPath} fill="#09090f" />
        {/* Front face */}
        <path d={frontPath} fill={`url(#${bodyGradId})`} />
        {/* Rim light */}
        <path
          d={rimPath}
          fill="none"
          stroke={`url(#${rimGradId})`}
          strokeWidth={1}
          filter="url(#ob-rim-blur)"
        />
      </g>

      {/* Crown — outside clip so it always glows at top */}
      {finalReturn >= 0 ? (
        <PositiveCrown
          colX={colX} colTopY={colTopY} topWidth={topWidth}
          color={color} isNewHigh={isNewHigh} crownVisible={crownVisible}
        />
      ) : (
        <NegativeCrown
          colX={colX} colTopY={colTopY} topWidth={topWidth}
          color={color} crownVisible={crownVisible}
        />
      )}
    </g>
  );
}
```

**Step 2: TypeScript check**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit 2>&1
```
Expected: no errors.

**Step 3: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/ObeliskField.tsx
git commit -m "feat: ObeliskColumn component with faces, crown, reflection"
```

---

### Task 3: ObeliskField container with animation

**Files:**
- Modify: `dashboard/src/components/ObeliskField.tsx`

Append `ObeliskField` — the main exported component — and the `PORTFOLIO_PALETTE` color lookup (same colors as OverviewPage uses).

**Step 1: Append ObeliskField component**

```typescript
// ── Color palette (matches OverviewPage PORTFOLIO_PALETTE) ────────────────────

const PALETTE = [
  "#34d399", "#818cf8", "#38bdf8", "#fb923c",
  "#f472b6", "#a78bfa", "#fbbf24", "#4ade80",
];

// ── Main component ────────────────────────────────────────────────────────────

interface ObeliskFieldProps {
  portfolios: PortfolioSummary[];
}

export default function ObeliskField({ portfolios }: ObeliskFieldProps) {
  const [animProgress, setAnimProgress] = useState(0);
  const [crownsVisible, setCrownsVisible] = useState<boolean[]>([]);
  const rafRef = useRef<number>(0);

  // Filter to portfolios with valid sparklines, sorted by final return (best last = front)
  const valid = useMemo(
    () =>
      portfolios
        .filter((p) => !p.error && p.sparkline && p.sparkline.length >= 2)
        .sort((a, b) => (a.total_return_pct ?? 0) - (b.total_return_pct ?? 0)),
    [portfolios]
  );

  // Compute shared scale: pixels per % point, based on max absolute return
  const scale = useMemo(() => {
    const maxRet = Math.max(
      1,
      ...valid.map((p) => {
        const base = p.sparkline![0];
        return Math.max(...p.sparkline!.map((v) => Math.abs(((v - base) / base) * 100)));
      })
    );
    return OBELISK_HEIGHT / maxRet;
  }, [valid]);

  // Pre-compute geometry for all columns
  const geos = useMemo(
    () => valid.map((p) => computeObeliskGeometry(p.sparkline!, scale)),
    [valid, scale]
  );

  // Load animation
  useEffect(() => {
    const start = performance.now();
    const duration = 1400;
    const easeExpoOut = (t: number) => 1 - Math.pow(2, -10 * t);

    const frame = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      setAnimProgress(easeExpoOut(t));
      if (t < 1) {
        rafRef.current = requestAnimationFrame(frame);
      } else {
        // Crown ignition: stagger by return rank (worst first, best last = most dramatic)
        valid.forEach((_, i) => {
          setTimeout(() => {
            setCrownsVisible((prev) => {
              const next = [...prev];
              next[i] = true;
              return next;
            });
          }, i * 80);
        });
      }
    };
    rafRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafRef.current);
  }, [valid.length]);

  // Hover state
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (valid.length === 0) {
    return (
      <div style={{ height: `${CONTAINER_H}px`, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ fontSize: "11px", color: "var(--text-0)" }}>No portfolio history to display</p>
      </div>
    );
  }

  // Column x positions: evenly spaced
  const colXs = valid.map((_, i) => {
    const margin = 80;
    const span = CONTAINER_W - margin * 2;
    return valid.length === 1
      ? CONTAINER_W / 2
      : margin + (i / (valid.length - 1)) * span;
  });

  return (
    <div style={{ position: "relative", background: "var(--surface-1)", border: "1px solid var(--border-0)", borderRadius: "7px", overflow: "hidden" }}>
      <svg
        width="100%"
        viewBox={`0 0 ${CONTAINER_W} ${CONTAINER_H}`}
        style={{ display: "block" }}
      >
        <ObeliskDefs />

        {/* Environment: void with subtle centered radial gradient */}
        <defs>
          <radialGradient id="ob-env-grad" cx="50%" cy="60%" r="55%">
            <stop offset="0%"   stopColor="#0d0d1f" stopOpacity="1" />
            <stop offset="100%" stopColor="#04040a" stopOpacity="1" />
          </radialGradient>
        </defs>
        <rect width={CONTAINER_W} height={CONTAINER_H} fill="url(#ob-env-grad)" />

        {/* Ground plane line */}
        <line
          x1={20} y1={BASELINE_Y} x2={CONTAINER_W - 20} y2={BASELINE_Y}
          stroke="rgba(255,255,255,0.05)" strokeWidth={1}
        />

        {/* Columns — render in order (lowest return behind, highest in front) */}
        {valid.map((p, i) => {
          const geo = geos[i];
          if (!geo) return null;
          const color = PALETTE[i % PALETTE.length];
          return (
            <g
              key={p.id}
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
              style={{ cursor: "default" }}
            >
              <ObeliskColumn
                geo={geo}
                colX={colXs[i]}
                color={color}
                id={p.id}
                animProgress={animProgress}
                crownVisible={crownsVisible[i] ?? false}
              />
            </g>
          );
        })}

        {/* Hover tooltip */}
        {hoveredIdx !== null && (() => {
          const p = valid[hoveredIdx];
          const geo = geos[hoveredIdx];
          if (!geo) return null;
          const cx = colXs[hoveredIdx];
          const ty = geo.colTopY - 32;
          const label = `${p.name}  ${geo.finalReturn >= 0 ? "+" : ""}${geo.finalReturn.toFixed(1)}%`;
          const tw = label.length * 6.5 + 16;
          const tx = Math.min(Math.max(cx - tw / 2, 8), CONTAINER_W - tw - 8);
          return (
            <g>
              <rect x={tx} y={ty} width={tw} height={18} rx={3}
                fill="rgba(13,13,26,0.92)" stroke="rgba(255,255,255,0.08)" strokeWidth={1} />
              <text x={tx + tw / 2} y={ty + 12} textAnchor="middle"
                fontSize="9.5" fontFamily="monospace" fontWeight="600"
                fill="rgba(255,255,255,0.75)">
                {label}
              </text>
            </g>
          );
        })()}

        {/* Portfolio name labels below base */}
        {valid.map((p, i) => (
          <text
            key={`lbl-${p.id}`}
            x={colXs[i]}
            y={BASELINE_Y + 14}
            textAnchor="middle"
            fontSize="8.5"
            fontFamily="monospace"
            fill="rgba(255,255,255,0.25)"
            letterSpacing="0.06em"
          >
            {p.id.toUpperCase()}
          </text>
        ))}
      </svg>
    </div>
  );
}
```

**Step 2: TypeScript check**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit 2>&1
```
Expected: no errors.

**Step 3: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/ObeliskField.tsx
git commit -m "feat: ObeliskField container with animation and hover"
```

---

### Task 4: Wire into AllPositionsPanel and OverviewPage

**Files:**
- Modify: `dashboard/src/components/OverviewPage.tsx`

Three changes:
1. Import `ObeliskField`
2. Add `portfolios` prop to `AllPositionsPanel`
3. Change toggle from `PLOT` → `OBELISK`, replace `ScatterPlot` with `ObeliskField`
4. Pass `enriched` portfolios from `OverviewPage` to `AllPositionsPanel`

**Step 1: Add import at top of OverviewPage.tsx**

Find the existing imports block. Add after the last import:

```typescript
import ObeliskField from "./ObeliskField";
```

**Step 2: Update AllPositionsPanel type signature and render**

Find:
```typescript
function AllPositionsPanel({ positions }: { positions: CrossPortfolioMover[] }) {
  const [view, setView] = useState<ViewMode>("map");
```

Replace the type and add portfolios:
```typescript
function AllPositionsPanel({ positions, portfolios }: {
  positions: CrossPortfolioMover[];
  portfolios: PortfolioSummary[];
}) {
  const [view, setView] = useState<ViewMode>("map");
```

**Step 3: Update the ViewMode type**

Find:
```typescript
type ViewMode = "map" | "plot";
```

Replace with:
```typescript
type ViewMode = "map" | "obelisk";
```

**Step 4: Update toggle button and render switch**

Find the toggle buttons block inside `AllPositionsPanel`:
```typescript
        {(["map", "plot"] as ViewMode[]).map((v) => (
```

Replace:
```typescript
        {(["map", "obelisk"] as ViewMode[]).map((v) => (
```

Find the label inside that map:
```typescript
              {v === "map" ? "MAP" : "PLOT"}
```

Replace:
```typescript
              {v === "map" ? "MAP" : "OBELISK"}
```

**Step 5: Replace ScatterPlot render**

Find:
```typescript
      {view === "map"
        ? <WeightedMap positions={positions} portfolioColors={portfolioColors} />
        : <ScatterPlot positions={positions} portfolioColors={portfolioColors} />
      }
```

Replace:
```typescript
      {view === "map"
        ? <WeightedMap positions={positions} portfolioColors={portfolioColors} />
        : <ObeliskField portfolios={portfolios} />
      }
```

**Step 6: Pass portfolios from OverviewPage**

Find the `<AllPositionsPanel positions={allPositions} />` call (around line 815):

Replace:
```tsx
<AllPositionsPanel positions={allPositions} portfolios={enriched} />
```

**Step 7: TypeScript check**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit 2>&1
```

If there's an error about `PortfolioSummary` not being imported in `OverviewPage.tsx`, check the existing imports — it is already imported. Fix any other type errors.

**Step 8: Visual check**

1. Open http://localhost:5173
2. Navigate to Overview page
3. Click "OBELISK" toggle in All Positions panel
4. Should see dark void with columns rising — one per portfolio (microcap, ai, new, largeboi)
5. Hover over a column — name + return should appear
6. Reload page — columns should animate upward, then crowns ignite

**Step 9: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/OverviewPage.tsx
git commit -m "feat: wire ObeliskField into AllPositionsPanel as OBELISK view"
```

---

### Task 5: Polish pass

**Files:**
- Modify: `dashboard/src/components/ObeliskField.tsx`

Small visual fixes after seeing it in the browser.

**Step 1: Check edge cases and fix**

These are the most likely visual issues to fix after first render:

1. **Columns too wide / overlapping** — if FLARE_K produces widths >80px, reduce `FLARE_K` from 4.0 to 2.5 and `SCAR_K` from 1.8 to 1.2
2. **Column too short for new portfolios** (few sparkline points) — works fine; smooth path handles 2-point case
3. **Reflection visible below SVG bounds** — add `overflow="hidden"` to the SVG or clip the reflection to `y ≥ BASELINE_Y`
4. **Crown glow too intense** — reduce `stopOpacity` on the glow ellipse from 0.32 → 0.22 if needed

**Step 2: Commit any polish fixes**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/ObeliskField.tsx
git commit -m "fix: obelisk visual polish after browser review"
```

**Step 3: Push**

```bash
git push
```
