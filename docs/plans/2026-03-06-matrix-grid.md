# MatrixGrid Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the MatrixGrid sci-fi HUD visualization and wire it in as the primary dashboard view — replacing `AllPositionsPanel` in overview and the 3-column layout in portfolio view.

**Architecture:** React functional component tree with all animation in Canvas 2D or CSS. No external animation libraries. Data from existing hooks (`useOverview`, `usePortfolioState`). Portfolio colors from a fixed palette derived from portfolio ID. Synthetic sparklines generated from `unrealized_pnl_pct`.

**Tech Stack:** React 19, TypeScript, Canvas 2D API, Azeret Mono (Google Fonts), existing TanStack Query hooks.

---

## Context

### Key files to NOT modify (read-only reference)
- `dashboard/src/App.tsx` — routing logic (we DO modify this in Task 5)
- `dashboard/src/components/OverviewPage.tsx` — we replace `AllPositionsPanel` (Task 6)
- `dashboard/src/lib/types.ts` — existing types; import from here, don't duplicate
- `dashboard/src/hooks/usePortfolios.ts` — provides `useOverview()` with `overview.all_positions` (CrossPortfolioMover[]) and `overview.portfolios` (PortfolioSummary[])
- `dashboard/src/hooks/usePortfolioState.ts` — provides `state.positions` (Position[]) for per-portfolio view

### Internal MatrixPosition type (defined in types.ts)

```typescript
export interface MatrixPosition {
  ticker: string;
  portfolioId: string;
  portfolioName: string;
  portfolioAbbr: string;   // 2-3 char abbreviation e.g. "AI", "MC", "LB"
  portfolioColor: string;  // hex color e.g. "#22d3ee"
  portfolioHex: [number, number, number]; // RGB triple for canvas ops
  value: number;           // market_value in dollars
  perf: number;            // all-time P&L % (unrealized_pnl_pct)
  day: number;             // day change % (day_change_pct ?? 0)
  sparkline: number[];     // 28-point synthetic array (see genSparkline)
  sector: string;          // "N/A" if not available
  vol: number | null;      // not available in Position — use null
  beta: number | null;     // not available in Position — use null
  mktCap: string;          // "N/A" if not available
}

export interface MatrixPortfolio {
  id: string;
  name: string;
  abbr: string;
  color: string;
  hex: [number, number, number];
}
```

### Portfolio color palette (deterministic by portfolio.id)

Define in `constants.ts`. When a portfolio ID is seen, assign it the next color from this list (cycle if more than 8). Use a stable sort by portfolio ID string so colors are consistent across renders.

```typescript
export const PORTFOLIO_COLORS: Array<{ color: string; hex: [number,number,number] }> = [
  { color: "#22d3ee", hex: [34,211,238] },   // cyan
  { color: "#f59e0b", hex: [245,158,11] },   // amber
  { color: "#a78bfa", hex: [167,139,250] },  // purple
  { color: "#34d399", hex: [52,211,153] },   // emerald
  { color: "#f87171", hex: [248,113,113] },  // red
  { color: "#fb923c", hex: [251,146,60] },   // orange
  { color: "#f472b6", hex: [244,114,182] },  // pink
  { color: "#bef264", hex: [190,242,100] },  // lime
];

export const BG_COLOR = "#040608";
export const ACCENT_GREEN = "#4ade80";
export const DANGER_RED = "#f87171";
export const MATRIX_FONT = "'Azeret Mono','JetBrains Mono','Fira Code',monospace";
```

### Portfolio abbreviation

For abbreviation, use the first 2 chars of id uppercased, or custom map:

```typescript
export function portfolioAbbr(id: string): string {
  const map: Record<string, string> = {
    microcap: "MC", ai: "AI", sph: "SP", new: "NW",
    largeboi: "LB", "10k": "TK", klop: "KL",
  };
  return map[id] ?? id.slice(0, 2).toUpperCase();
}
```

### Sparkline generation (synthetic)

Position type has no price history. Generate a plausible 28-point sparkline from `perf` (same algorithm as reference):

```typescript
export function genSparkline(perf: number): number[] {
  // deterministic-ish based on perf value, not random, so it doesn't re-generate on every render
  const pts: number[] = [];
  let v = 50;
  const seed = Math.abs(perf * 13.7);
  for (let i = 0; i < 28; i++) {
    // pseudo-random from seed+i
    const r = ((seed + i * 7.3) % 100) / 100;
    v += (r - 0.47 + perf * 0.008) * 5;
    v = Math.max(5, Math.min(95, v));
    pts.push(v);
  }
  return pts;
}
```

### Data mapping functions (define in constants.ts)

```typescript
// Map CrossPortfolioMover → MatrixPosition (used in overview / all-portfolios)
export function crossMoverToMatrix(
  mover: CrossPortfolioMover,
  portfolioMap: Map<string, MatrixPortfolio>
): MatrixPosition {
  const port = portfolioMap.get(mover.portfolio_id) ?? {
    id: mover.portfolio_id,
    name: mover.portfolio_name,
    abbr: portfolioAbbr(mover.portfolio_id),
    color: "#4ade80",
    hex: [74, 222, 128] as [number,number,number],
  };
  return {
    ticker: mover.ticker,
    portfolioId: port.id,
    portfolioName: port.name,
    portfolioAbbr: port.abbr,
    portfolioColor: port.color,
    portfolioHex: port.hex,
    value: mover.market_value ?? 0,
    perf: mover.pnl_pct,
    day: mover.day_change_pct ?? 0,
    sparkline: genSparkline(mover.pnl_pct),
    sector: "N/A",
    vol: null,
    beta: null,
    mktCap: "N/A",
  };
}

// Map Position → MatrixPosition (used in per-portfolio view)
export function positionToMatrix(
  pos: Position,
  port: MatrixPortfolio
): MatrixPosition {
  return {
    ticker: pos.ticker,
    portfolioId: port.id,
    portfolioName: port.name,
    portfolioAbbr: port.abbr,
    portfolioColor: port.color,
    portfolioHex: port.hex,
    value: pos.market_value,
    perf: pos.unrealized_pnl_pct,
    day: pos.day_change_pct ?? 0,
    sparkline: genSparkline(pos.unrealized_pnl_pct),
    sector: "N/A",
    vol: null,
    beta: null,
    mktCap: "N/A",
  };
}
```

### Props interface for MatrixGrid

```typescript
interface MatrixGridProps {
  positions: MatrixPosition[];
  portfolios: MatrixPortfolio[];
  onPositionClick?: (pos: MatrixPosition) => void;
  onBack?: () => void;
  initialFilter?: string;   // portfolio id to pre-filter
  showEKG?: boolean;        // default true
  showTickerTape?: boolean; // default true
}
```

---

## Task 1: Foundation Files

**Files:**
- Create: `dashboard/src/components/MatrixGrid/types.ts`
- Create: `dashboard/src/components/MatrixGrid/constants.ts`

**Step 1: Create the directory**

```bash
mkdir -p dashboard/src/components/MatrixGrid
```

**Step 2: Write `types.ts`**

Contains `MatrixPosition` and `MatrixPortfolio` interfaces, and `MatrixGridProps`. Import `CrossPortfolioMover` and `Position` from `../../lib/types`.

```typescript
import type { CrossPortfolioMover, Position } from "../../lib/types";

export interface MatrixPortfolio {
  id: string;
  name: string;
  abbr: string;
  color: string;
  hex: [number, number, number];
}

export interface MatrixPosition {
  ticker: string;
  portfolioId: string;
  portfolioName: string;
  portfolioAbbr: string;
  portfolioColor: string;
  portfolioHex: [number, number, number];
  value: number;
  perf: number;
  day: number;
  sparkline: number[];
  sector: string;
  vol: number | null;
  beta: number | null;
  mktCap: string;
}

export interface MatrixGridProps {
  positions: MatrixPosition[];
  portfolios: MatrixPortfolio[];
  onPositionClick?: (pos: MatrixPosition) => void;
  onBack?: () => void;
  initialFilter?: string;
  showEKG?: boolean;
  showTickerTape?: boolean;
}

// Re-export for convenience in mapping functions
export type { CrossPortfolioMover, Position };
```

**Step 3: Write `constants.ts`**

Contains PORTFOLIO_COLORS, BG_COLOR, ACCENT_GREEN, DANGER_RED, MATRIX_FONT, and the three helper functions: `portfolioAbbr`, `genSparkline`, `buildPortfolioMap`, `crossMoverToMatrix`, `positionToMatrix`.

```typescript
import type { CrossPortfolioMover, Position, MatrixPosition, MatrixPortfolio } from "./types";

export const PORTFOLIO_COLORS: Array<{ color: string; hex: [number, number, number] }> = [
  { color: "#22d3ee", hex: [34, 211, 238] },
  { color: "#f59e0b", hex: [245, 158, 11] },
  { color: "#a78bfa", hex: [167, 139, 250] },
  { color: "#34d399", hex: [52, 211, 153] },
  { color: "#f87171", hex: [248, 113, 113] },
  { color: "#fb923c", hex: [251, 146, 60] },
  { color: "#f472b6", hex: [244, 114, 182] },
  { color: "#bef264", hex: [190, 242, 100] },
];

export const BG_COLOR = "#040608";
export const ACCENT_GREEN = "#4ade80";
export const DANGER_RED = "#f87171";
export const MATRIX_FONT = "'Azeret Mono','JetBrains Mono','Fira Code',monospace";

export function portfolioAbbr(id: string): string {
  const map: Record<string, string> = {
    microcap: "MC", ai: "AI", sph: "SP", new: "NW",
    largeboi: "LB", "10k": "TK", klop: "KL",
  };
  return map[id] ?? id.slice(0, 2).toUpperCase();
}

export function genSparkline(perf: number): number[] {
  const pts: number[] = [];
  let v = 50;
  const seed = Math.abs(perf * 13.7);
  for (let i = 0; i < 28; i++) {
    const r = ((seed + i * 7.3) % 100) / 100;
    v += (r - 0.47 + perf * 0.008) * 5;
    v = Math.max(5, Math.min(95, v));
    pts.push(v);
  }
  return pts;
}

/** Build a stable color-assigned portfolio map from a list of PortfolioSummary or id/name pairs.
 *  Sort by id alphabetically so color assignment is deterministic. */
export function buildPortfolioMap(
  portfolioIds: Array<{ id: string; name: string }>
): Map<string, MatrixPortfolio> {
  const sorted = [...portfolioIds].sort((a, b) => a.id.localeCompare(b.id));
  const map = new Map<string, MatrixPortfolio>();
  sorted.forEach((p, i) => {
    const palette = PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length];
    map.set(p.id, {
      id: p.id,
      name: p.name,
      abbr: portfolioAbbr(p.id),
      color: palette.color,
      hex: palette.hex,
    });
  });
  return map;
}

export function crossMoverToMatrix(
  mover: CrossPortfolioMover,
  portfolioMap: Map<string, MatrixPortfolio>
): MatrixPosition {
  const port = portfolioMap.get(mover.portfolio_id) ?? {
    id: mover.portfolio_id,
    name: mover.portfolio_name,
    abbr: portfolioAbbr(mover.portfolio_id),
    color: ACCENT_GREEN,
    hex: [74, 222, 128] as [number, number, number],
  };
  return {
    ticker: mover.ticker,
    portfolioId: port.id,
    portfolioName: port.name,
    portfolioAbbr: port.abbr,
    portfolioColor: port.color,
    portfolioHex: port.hex,
    value: mover.market_value ?? 0,
    perf: mover.pnl_pct,
    day: mover.day_change_pct ?? 0,
    sparkline: genSparkline(mover.pnl_pct),
    sector: "N/A",
    vol: null,
    beta: null,
    mktCap: "N/A",
  };
}

export function positionToMatrix(pos: Position, port: MatrixPortfolio): MatrixPosition {
  return {
    ticker: pos.ticker,
    portfolioId: port.id,
    portfolioName: port.name,
    portfolioAbbr: port.abbr,
    portfolioColor: port.color,
    portfolioHex: port.hex,
    value: pos.market_value,
    perf: pos.unrealized_pnl_pct,
    day: pos.day_change_pct ?? 0,
    sparkline: genSparkline(pos.unrealized_pnl_pct),
    sector: "N/A",
    vol: null,
    beta: null,
    mktCap: "N/A",
  };
}

// Color helpers
export const pc = (p: number) =>
  p > 5 ? "#4ade80" : p > 0 ? "#5a9a6a" : p > -5 ? "#9a6a5a" : "#f87171";

export const pbg = (p: number) => {
  if (p > 15) return "rgba(74,222,128,0.06)";
  if (p > 5)  return "rgba(74,222,128,0.025)";
  if (p > 0)  return "rgba(74,222,128,0.008)";
  if (p > -5) return "rgba(248,113,113,0.008)";
  if (p > -10) return "rgba(248,113,113,0.025)";
  return "rgba(248,113,113,0.06)";
};

export const fv = (v: number) =>
  v >= 1000 ? `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k` : String(Math.round(v));
```

**Step 4: Commit**

```bash
git add dashboard/src/components/MatrixGrid/
git commit -m "feat: add MatrixGrid foundation types and constants"
```

---

## Task 2: Sub-components

**Files:**
- Create: `dashboard/src/components/MatrixGrid/Sparkline.tsx`
- Create: `dashboard/src/components/MatrixGrid/AllocRing.tsx`
- Create: `dashboard/src/components/MatrixGrid/Waveform.tsx`
- Create: `dashboard/src/components/MatrixGrid/Reticle.tsx`
- Create: `dashboard/src/components/MatrixGrid/TickerTape.tsx`
- Create: `dashboard/src/components/MatrixGrid/DetailCard.tsx`

These are direct TypeScript ports of the reference implementation sub-components. Port each function exactly from `matrix-cracked.jsx`, converting `style={{}}` to typed React style props and adding TypeScript types.

**Step 1: Write `Sparkline.tsx`**

Port the `Spark` function. Props: `{ data: number[]; color: string; w?: number; h?: number }`. Uses `useRef` + `useEffect` for Canvas 2D animation. Animation runs on mount with `requestAnimationFrame`, drawing line and glow, stopping when `rev >= data.length`. Uses `devicePixelRatio = 2` (hardcoded, matching reference).

```typescript
import { useRef, useEffect } from "react";

interface SparklineProps {
  data: number[];
  color: string;
  w?: number;
  h?: number;
}

export default function Sparkline({ data, color, w = 48, h = 14 }: SparklineProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const aRef = useRef<number>(0);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    const d = 2;
    c.width = w * d;
    c.height = h * d;
    ctx.scale(d, d);
    let rev = 0;

    const draw = () => {
      rev = Math.min(data.length, rev + 0.8);
      ctx.clearRect(0, 0, w, h);
      const mn = Math.min(...data);
      const mx = Math.max(...data);
      const rg = mx - mn || 1;
      const s = w / (data.length - 1);

      // glow pass
      ctx.beginPath();
      for (let i = 0; i < Math.floor(rev); i++) {
        const x = i * s;
        const y = h - ((data[i] - mn) / rg) * (h - 2) - 1;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = color + "33";
      ctx.lineWidth = 3;
      ctx.stroke();

      // crisp line
      ctx.beginPath();
      for (let i = 0; i < Math.floor(rev); i++) {
        const x = i * s;
        const y = h - ((data[i] - mn) / rg) * (h - 2) - 1;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = color + "99";
      ctx.lineWidth = 1;
      ctx.stroke();

      // area fill
      if (rev > 1) {
        ctx.beginPath();
        for (let i = 0; i < Math.floor(rev); i++) {
          const x = i * s;
          const y = h - ((data[i] - mn) / rg) * (h - 2) - 1;
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.lineTo((Math.floor(rev) - 1) * s, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        const g = ctx.createLinearGradient(0, 0, 0, h);
        g.addColorStop(0, color + "14");
        g.addColorStop(1, color + "01");
        ctx.fillStyle = g;
        ctx.fill();
      }

      // endpoint dot
      if (rev >= data.length) {
        const lx = (data.length - 1) * s;
        const ly = h - ((data[data.length - 1] - mn) / rg) * (h - 2) - 1;
        ctx.beginPath();
        ctx.arc(lx, ly, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      }

      if (rev < data.length) aRef.current = requestAnimationFrame(draw);
    };

    aRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(aRef.current);
  }, [data, color, w, h]);

  return <canvas ref={ref} style={{ width: w, height: h, display: "block" }} />;
}
```

**Step 2: Write `AllocRing.tsx`**

Port `AllocRing`. Props: `{ positions: MatrixPosition[]; portfolios: MatrixPortfolio[] }`. Draws a 32×32 donut chart (ring) showing portfolio weight distribution. No animation — draws once on mount when positions change.

```typescript
import { useRef, useEffect } from "react";
import type { MatrixPosition, MatrixPortfolio } from "./types";

interface AllocRingProps {
  positions: MatrixPosition[];
  portfolios: MatrixPortfolio[];
}

export default function AllocRing({ positions, portfolios }: AllocRingProps) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    const d = 2;
    const s = 32;
    c.width = s * d;
    c.height = s * d;
    ctx.scale(d, d);

    const totals: Record<string, number> = {};
    positions.forEach((p) => {
      totals[p.portfolioId] = (totals[p.portfolioId] ?? 0) + p.value;
    });
    const total = Object.values(totals).reduce((a, b) => a + b, 0) || 1;
    const cx = s / 2, cy = s / 2, r = 12, inner = 8;

    let angle = -Math.PI / 2;
    portfolios.forEach((port) => {
      const val = totals[port.id] ?? 0;
      const sweep = (val / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(cx, cy, r, angle, angle + sweep);
      ctx.arc(cx, cy, inner, angle + sweep, angle, true);
      ctx.closePath();
      ctx.fillStyle = port.color + "88";
      ctx.fill();
      angle += sweep;
    });

    // center hole
    ctx.beginPath();
    ctx.arc(cx, cy, inner - 1, 0, Math.PI * 2);
    ctx.fillStyle = "#06080a";
    ctx.fill();
  }, [positions, portfolios]);

  return <canvas ref={ref} style={{ width: 32, height: 32 }} />;
}
```

**Step 3: Write `Waveform.tsx`**

Port `Waveform`. Props: `{ width?: number; height?: number }`. Continuous RAF animation of 40 oscillating bars.

```typescript
import { useRef, useEffect } from "react";

interface WaveformProps {
  width?: number;
  height?: number;
}

export default function Waveform({ width = 160, height = 16 }: WaveformProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const d = 2;
    c.width = width * d;
    c.height = height * d;
    const ctx = c.getContext("2d")!;
    let t = 0;

    const draw = () => {
      frameRef.current = requestAnimationFrame(draw);
      ctx.save();
      ctx.scale(d, d);
      ctx.clearRect(0, 0, width, height);
      t += 0.03;
      const bars = 40;
      const bw = width / bars;
      for (let i = 0; i < bars; i++) {
        const h2 =
          (Math.sin(t + i * 0.3) * 0.5 + 0.5) *
          (Math.sin(t * 1.7 + i * 0.15) * 0.5 + 0.5) *
          height * 0.8 + 1;
        ctx.fillStyle = `rgba(74,222,128,${0.1 + (h2 / height) * 0.25})`;
        ctx.fillRect(i * bw + 1, (height - h2) / 2, bw - 2, h2);
      }
      ctx.restore();
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, [width, height]);

  return <canvas ref={ref} style={{ width, height, display: "block", opacity: 0.6 }} />;
}
```

**Step 4: Write `Reticle.tsx`**

Port `Ret`. Simple CSS div component. Props: `{ color?: string; s?: number }`.

```typescript
interface ReticleProps {
  color?: string;
  s?: number;
}

export default function Reticle({ color = "#4ade80", s = 7 }: ReticleProps) {
  const b = `1px solid ${color}55`;
  return (
    <>
      <div style={{ position: "absolute", top: 0, left: 0, width: s, height: s, borderTop: b, borderLeft: b }} />
      <div style={{ position: "absolute", top: 0, right: 0, width: s, height: s, borderTop: b, borderRight: b }} />
      <div style={{ position: "absolute", bottom: 0, left: 0, width: s, height: s, borderBottom: b, borderLeft: b }} />
      <div style={{ position: "absolute", bottom: 0, right: 0, width: s, height: s, borderBottom: b, borderRight: b }} />
    </>
  );
}
```

**Step 5: Write `TickerTape.tsx`**

Port `TickerTape`. Props: `{ positions: MatrixPosition[] }`. Uses `useMemo` to create 30-item shuffled slice. Note: `Math.random()` in `useMemo` is fine here — it only runs once per positions change. Duplicates items for seamless scroll loop. Uses `@keyframes ticker` CSS animation (40s translateX(-50%)).

```typescript
import { useMemo } from "react";
import type { MatrixPosition } from "./types";

interface TickerTapeProps {
  positions: MatrixPosition[];
}

export default function TickerTape({ positions }: TickerTapeProps) {
  const items = useMemo(() => {
    return [...positions]
      .sort(() => Math.random() - 0.5)
      .slice(0, 30)
      .map((p) => ({ ticker: p.ticker, day: p.day, color: p.portfolioColor }));
  }, [positions]);

  return (
    <div style={{
      overflow: "hidden", whiteSpace: "nowrap",
      borderTop: "1px solid rgba(74,222,128,0.04)",
      borderBottom: "1px solid rgba(74,222,128,0.04)",
      padding: "4px 0",
    }}>
      <div style={{ display: "inline-block", animation: "matrixTicker 40s linear infinite" }}>
        {[...items, ...items].map((item, i) => (
          <span key={i} style={{
            fontSize: 9, letterSpacing: "0.04em", marginRight: 20,
            color: item.day >= 0 ? "#4ade8088" : "#f8717188",
            fontVariantNumeric: "tabular-nums",
          }}>
            <span style={{ color: "#333", marginRight: 4 }}>{item.ticker}</span>
            {item.day >= 0 ? "▲" : "▼"} {item.day >= 0 ? "+" : ""}{item.day.toFixed(2)}%
          </span>
        ))}
      </div>
    </div>
  );
}
```

**Step 6: Write `DetailCard.tsx`**

Port `DetailCard`. Props: `{ pos: MatrixPosition | null; onClose: () => void }`. Full-screen overlay with blurred backdrop, portfolio-colored accent line, large ticker, sparkline, stats grid, signal frequency bar, ESC hint. Uses keyboard `Escape` to close.

```typescript
import { useEffect } from "react";
import type { MatrixPosition } from "./types";
import Sparkline from "./Sparkline";
import Reticle from "./Reticle";
import { pc } from "./constants";

interface DetailCardProps {
  pos: MatrixPosition | null;
  onClose: () => void;
}

export default function DetailCard({ pos, onClose }: DetailCardProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!pos) return null;
  const col = pos.portfolioColor;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 500,
        background: "rgba(3,3,6,0.7)", backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        animation: "matrixFadeIn 0.2s ease", cursor: "pointer",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "rgba(8,10,14,0.95)",
          border: `1px solid ${col}33`,
          borderRadius: 2, padding: 0, width: 420, position: "relative",
          boxShadow: `0 0 60px ${col}11, 0 0 120px rgba(0,0,0,0.8)`,
          cursor: "default", animation: "matrixScaleIn 0.2s ease",
        }}
      >
        {/* Top accent line */}
        <div style={{ height: 2, background: `linear-gradient(90deg,transparent,${col}88,transparent)` }} />

        <div style={{ padding: "20px 24px" }}>
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ position: "relative", display: "inline-block", padding: "2px 8px" }}>
                <Reticle color={col} s={8} />
                <span style={{
                  fontSize: 24, fontWeight: 700, color: "#fff", letterSpacing: "0.06em",
                  textShadow: `0 0 20px ${col}44`,
                }}>{pos.ticker}</span>
              </div>
              <div style={{ fontSize: 10, color: col, letterSpacing: "0.08em", marginTop: 6, marginLeft: 8 }}>
                ● {pos.portfolioName} · {pos.sector} · {pos.mktCap}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{
                fontSize: 22, fontWeight: 700, color: pc(pos.perf),
                textShadow: `0 0 12px ${pc(pos.perf)}44`,
              }}>
                {pos.perf > 0 ? "+" : ""}{pos.perf.toFixed(1)}%
              </div>
              <div style={{ fontSize: 10, color: "#444", marginTop: 2 }}>ALL-TIME</div>
            </div>
          </div>

          {/* Large sparkline */}
          <div style={{
            margin: "20px 0 16px", padding: "12px",
            background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.03)",
          }}>
            <Sparkline data={pos.sparkline} color={pos.perf >= 0 ? "#4ade80" : "#f87171"} w={370} h={60} />
          </div>

          {/* Stats grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12 }}>
            {[
              { label: "VALUE", val: `$${pos.value.toLocaleString()}` },
              { label: "DAY", val: `${pos.day > 0 ? "+" : ""}${pos.day.toFixed(2)}%`, color: pc(pos.day) },
              { label: "VOL", val: pos.vol != null ? `${pos.vol}%` : "N/A" },
              { label: "BETA", val: pos.beta != null ? String(pos.beta) : "N/A" },
            ].map((s) => (
              <div key={s.label}>
                <div style={{ fontSize: 7, color: "#333", letterSpacing: "0.14em" }}>{s.label}</div>
                <div style={{
                  fontSize: 13, color: s.color ?? "#aaa", fontWeight: 500,
                  marginTop: 2, fontVariantNumeric: "tabular-nums",
                }}>{s.val}</div>
              </div>
            ))}
          </div>

          {/* Signal frequency bar */}
          <div style={{ marginTop: 16, display: "flex", gap: 1, alignItems: "flex-end", height: 20 }}>
            {Array.from({ length: 60 }, (_, i) => {
              const h2 = 2 + Math.abs(Math.sin(i * 0.3 + pos.perf) * Math.cos(i * 0.17)) * 18;
              return (
                <div key={i} style={{
                  width: 5, height: h2,
                  background: pos.perf >= 0
                    ? `rgba(74,222,128,${0.15 + (h2 / 20) * 0.35})`
                    : `rgba(248,113,113,${0.15 + (h2 / 20) * 0.35})`,
                }} />
              );
            })}
          </div>
        </div>

        {/* Bottom accent */}
        <div style={{ height: 1, background: `linear-gradient(90deg,transparent,${col}33,transparent)` }} />

        {/* Close hint */}
        <div style={{
          padding: "6px 0", textAlign: "center", fontSize: 8, color: "#222",
          letterSpacing: "0.12em", background: "rgba(255,255,255,0.01)",
        }}>
          ESC OR CLICK OUTSIDE TO CLOSE
        </div>
      </div>
    </div>
  );
}
```

**Step 7: Commit**

```bash
git add dashboard/src/components/MatrixGrid/
git commit -m "feat: add MatrixGrid sub-components (Sparkline, AllocRing, Waveform, Reticle, TickerTape, DetailCard)"
```

---

## Task 3: BackgroundCanvas and EKGStrip

**Files:**
- Create: `dashboard/src/components/MatrixGrid/BackgroundCanvas.tsx`
- Create: `dashboard/src/components/MatrixGrid/EKGStrip.tsx`

These are the two most complex Canvas components. They run continuous RAF loops.

**Step 1: Write `BackgroundCanvas.tsx`**

Port `BG` component from reference. Props: `{ mouseX: React.MutableRefObject<number>; mouseY: React.MutableRefObject<number>; tickers: string[] }`.

The `tickers` prop feeds the rain drops (use real ticker symbols from `positions.map(p => p.ticker)` passed from parent, with dedup). Component uses `useRef` for drops and particles to avoid re-renders. All canvas operations (grid, particles, ticker rain, scan beams) from reference preserved exactly. The parent passes `mouseXRef` and `mouseYRef` as refs so canvas can read latest value without re-subscribing.

```typescript
import { useRef, useEffect } from "react";

interface BackgroundCanvasProps {
  mouseX: React.MutableRefObject<number>;
  mouseY: React.MutableRefObject<number>;
  tickers: string[];
}

export default function BackgroundCanvas({ mouseX, mouseY, tickers }: BackgroundCanvasProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);
  const dropsRef = useRef<Array<{ x: number; y: number; speed: number; opacity: number; char: string }>>([]);
  const particlesRef = useRef<Array<{
    x: number; y: number; vx: number; vy: number;
    size: number; opacity: number; color: [number, number, number];
  }>>([]);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const parent = c.parentElement!;
    const dpr = Math.min(window.devicePixelRatio, 2);
    let w = 0, h = 0;

    const tickerList = tickers.length > 0 ? tickers : ["AAPL", "MSFT", "NVDA"];

    const resize = () => {
      w = parent.clientWidth;
      h = parent.clientHeight;
      c.width = w * dpr;
      c.height = h * dpr;
      c.style.width = w + "px";
      c.style.height = h + "px";

      // Rain drops
      dropsRef.current = Array.from({ length: 50 }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        speed: 0.2 + Math.random() * 1,
        opacity: 0.01 + Math.random() * 0.03,
        char: tickerList[Math.floor(Math.random() * tickerList.length)],
      }));

      // Particles
      particlesRef.current = Array.from({ length: 80 }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.2,
        vy: (Math.random() - 0.5) * 0.2,
        size: 0.5 + Math.random() * 1.5,
        opacity: 0.05 + Math.random() * 0.15,
        color: (Math.random() > 0.5 ? [74, 222, 128] : [248, 113, 113]) as [number, number, number],
      }));
    };

    resize();
    window.addEventListener("resize", resize);

    let t = 0;
    const draw = () => {
      frameRef.current = requestAnimationFrame(draw);
      const ctx = c.getContext("2d")!;
      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, w, h);
      t += 0.016;

      // Grid lines
      ctx.strokeStyle = "rgba(74,222,128,0.008)";
      ctx.lineWidth = 0.5;
      for (let x = 0; x < w; x += 50) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      }
      for (let y = 0; y < h; y += 50) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
      }

      // Particles
      particlesRef.current.forEach((p) => {
        if (mouseX.current > 0) {
          const dx = mouseX.current - p.x;
          const dy = mouseY.current - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 200 && dist > 0) {
            p.vx += (dx / dist) * 0.01;
            p.vy += (dy / dist) * 0.01;
          }
        }
        p.vx *= 0.995; p.vy *= 0.995;
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = w; if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h; if (p.y > h) p.y = 0;

        const pulse = 0.7 + Math.sin(t * 2 + p.x * 0.01) * 0.3;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * pulse, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color.join(",")},${p.opacity * pulse})`;
        ctx.fill();

        // Connect nearby
        particlesRef.current.forEach((q) => {
          if (p === q) return;
          const d = Math.sqrt((p.x - q.x) ** 2 + (p.y - q.y) ** 2);
          if (d < 60) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = `rgba(74,222,128,${(1 - d / 60) * 0.02})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        });
      });

      // Ticker rain
      ctx.font = "8px monospace";
      dropsRef.current.forEach((d) => {
        ctx.fillStyle = `rgba(74,222,128,${d.opacity})`;
        ctx.fillText(d.char, d.x, d.y);
        d.y += d.speed;
        if (d.y > h + 20) {
          d.y = -20;
          d.x = Math.random() * w;
          d.char = tickerList[Math.floor(Math.random() * tickerList.length)];
        }
      });

      // Horizontal scan beam (green)
      const sy = (t * 30) % (h + 60) - 30;
      const sg = ctx.createLinearGradient(0, sy - 20, 0, sy + 20);
      sg.addColorStop(0, "rgba(74,222,128,0)");
      sg.addColorStop(0.5, "rgba(74,222,128,0.025)");
      sg.addColorStop(1, "rgba(74,222,128,0)");
      ctx.fillStyle = sg;
      ctx.fillRect(0, sy - 20, w, 40);
      ctx.beginPath(); ctx.moveTo(0, sy); ctx.lineTo(w, sy);
      ctx.strokeStyle = "rgba(74,222,128,0.04)"; ctx.lineWidth = 1; ctx.stroke();

      // Vertical scan beam (cyan, slower)
      const sx = (t * 15) % (w + 60) - 30;
      const sg2 = ctx.createLinearGradient(sx - 20, 0, sx + 20, 0);
      sg2.addColorStop(0, "rgba(34,211,238,0)");
      sg2.addColorStop(0.5, "rgba(34,211,238,0.012)");
      sg2.addColorStop(1, "rgba(34,211,238,0)");
      ctx.fillStyle = sg2;
      ctx.fillRect(sx - 20, 0, 40, h);

      ctx.restore();
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [mouseX, mouseY, tickers]);

  return (
    <canvas
      ref={ref}
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
    />
  );
}
```

**Step 2: Write `EKGStrip.tsx`**

Port `EKGStrip`. Props: `{ portfolios: MatrixPortfolio[] }`. Each portfolio gets one lane. Continuous RAF. Phase advances per frame. Sharp cardiac spike when `Math.sin(phase * 3.7) > 0.85`.

```typescript
import { useRef, useEffect } from "react";
import type { MatrixPortfolio } from "./types";

interface EKGStripProps {
  portfolios: MatrixPortfolio[];
}

export default function EKGStrip({ portfolios }: EKGStripProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);
  const linesRef = useRef(
    portfolios.map(() => ({ pts: [] as number[], phase: Math.random() * 100 }))
  );

  useEffect(() => {
    // Reset lines when portfolios change
    linesRef.current = portfolios.map(() => ({
      pts: [] as number[],
      phase: Math.random() * 100,
    }));
  }, [portfolios]);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const parent = c.parentElement!;
    const dpr = 2;
    let w = 0, h = 0;

    const resize = () => {
      w = parent.clientWidth;
      h = parent.clientHeight;
      c.width = w * dpr;
      c.height = h * dpr;
      c.style.width = w + "px";
      c.style.height = h + "px";
    };
    resize();
    window.addEventListener("resize", resize);

    const draw = () => {
      frameRef.current = requestAnimationFrame(draw);
      const ctx = c.getContext("2d")!;
      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, w, h);

      const laneH = portfolios.length > 0 ? h / portfolios.length : h;

      portfolios.forEach((port, i) => {
        const line = linesRef.current[i];
        if (!line) return;
        const y0 = i * laneH + laneH / 2;

        line.phase += 0.06;
        const heartbeat =
          Math.sin(line.phase) * 0.3 +
          (Math.sin(line.phase * 3.7) > 0.85
            ? Math.sin(line.phase * 3.7) * 3
            : 0) +
          (Math.random() - 0.5) * 0.15;
        line.pts.push(heartbeat);
        if (line.pts.length > w / 1.5) line.pts.shift();

        const step = 1.5;
        ctx.beginPath();
        for (let j = 0; j < line.pts.length; j++) {
          const x = w - (line.pts.length - j) * step;
          const y = y0 + line.pts[j] * (laneH * 0.35);
          j === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.strokeStyle = port.color + "55";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Glow
        ctx.strokeStyle = port.color + "18";
        ctx.lineWidth = 3;
        ctx.stroke();

        // Label
        ctx.font = "7px monospace";
        ctx.fillStyle = port.color + "44";
        ctx.fillText(port.abbr, 4, y0 + 3);

        // Lane separator
        if (i < portfolios.length - 1) {
          ctx.beginPath();
          ctx.moveTo(0, (i + 1) * laneH);
          ctx.lineTo(w, (i + 1) * laneH);
          ctx.strokeStyle = "rgba(255,255,255,0.02)";
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      });

      ctx.restore();
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [portfolios]);

  return (
    <canvas ref={ref} style={{ width: "100%", height: "100%", display: "block" }} />
  );
}
```

**Step 3: Commit**

```bash
git add dashboard/src/components/MatrixGrid/
git commit -m "feat: add BackgroundCanvas and EKGStrip sub-components"
```

---

## Task 4: Main MatrixGrid Component

**Files:**
- Create: `dashboard/src/components/MatrixGrid/MatrixGrid.tsx`
- Create: `dashboard/src/components/MatrixGrid/index.ts`

This is the largest task. Port all state, effects, and rendering from `MatrixCracked` in the reference. Replace all hardcoded `P` references with the `portfolios` prop. Replace `genPositions()` with the `positions` prop.

**Step 1: Understand the state structure**

From the reference `MatrixCracked`, the state we need:
- `hovIdx: number | null` — which grid cell index is hovered
- `sortBy: "value" | "perf" | "alpha" | "portfolio"` — current sort key
- `filterP: string | null` — active portfolio filter (by portfolio id)
- `mounted: boolean` — true after boot sequence completes (triggers stagger animation)
- `boot: 0 | 1 | 2 | 3` — boot phase for fade timing
- `clock: string` — live clock string updated every 47ms
- `glitchIdx: number` — index of currently glitching cell (-1 if none)
- `anomalies: Set<number>` — set of position indices currently pulsing red
- `selectedPos: MatrixPosition | null` — currently selected position for detail card
- `breathPhase: number` — sine wave offset, incremented by RAF
- `bootLines: string[]` — terminal lines that appear one by one
- `mouseXRef / mouseYRef` — mouse position refs (NOT state)
- `gridRef` — ref to the grid container div for 3D parallax

**Step 2: Write `MatrixGrid.tsx`**

The component must:

1. **Import all sub-components** from sibling files
2. **Inject Google Font** via a `<link>` in JSX (same as reference line 673)
3. **Inject CSS keyframe animations** via a `<style>` tag in JSX. Required animations:
   - `@keyframes matrixTicker` — used by TickerTape (translateX(-50%))
   - `@keyframes matrixFadeIn` — used by DetailCard backdrop
   - `@keyframes matrixScaleIn` — used by DetailCard card
   - `@keyframes matrixGlitch` — used by glitching cells
   - `@keyframes matrixSlideUp` — used by hover detail panel
   - `@keyframes matrixAnomalyPulse` — used by anomaly cells
   - `@keyframes matrixTermLine` — used by boot terminal lines
   - `@keyframes matrixBlink` — cursor blink and LIVE indicator
   - `.matrix-cell:hover` — background highlight
   - `.matrix-cell:hover .matrix-tk` — ticker glow
   - `.matrix-cell:hover .matrix-ret` — reticle appear
   - Custom scrollbar CSS

   **IMPORTANT**: Prefix all class names with `matrix-` to avoid collisions with Tailwind classes!

4. **Effects**: clock (setInterval 47ms), glitch (setInterval 3-5s), anomaly (setInterval 5s), breathPhase (RAF), boot sequence (setTimeout chain), keyboard shortcuts, mouse tracking

5. **Sorted/filtered positions**: `useMemo` deriving `sorted` from `positions`, `sortBy`, `filterP`

6. **Grid rendering**: Map `sorted` to cell divs with all visual features from spec

7. **Header**: "THE MATRIX" + version badge + AllocRing + system status dots + stats row + clock

8. **EKG strip** (if `showEKG !== false`)

9. **Ticker tape** (if `showTickerTape !== false`)

10. **Controls bar**: sort buttons + portfolio filter chips

11. **Grid**: 3D parallax container + cells

12. **Status bar**: top/bottom movers + keyboard hints + Waveform + LIVE indicator

13. **Hover detail panel**: fixed bottom bar that slides up on hover

14. **Detail card overlay**: `<DetailCard>` component

**Full component code:**

```typescript
import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import type { MatrixGridProps, MatrixPosition } from "./types";
import { pc, pbg, fv, MATRIX_FONT, ACCENT_GREEN } from "./constants";
import Sparkline from "./Sparkline";
import AllocRing from "./AllocRing";
import Waveform from "./Waveform";
import Reticle from "./Reticle";
import TickerTape from "./TickerTape";
import DetailCard from "./DetailCard";
import BackgroundCanvas from "./BackgroundCanvas";
import EKGStrip from "./EKGStrip";

const BOOT_LINES = [
  "[SYS] MATRIX v3.0 initializing...",
  "[MEM] Allocating position buffers",
  "[NET] Connecting to market feed — OK",
  "[GPU] Particle system online",
  "[EKG] Vitals monitoring active",
  "[SCN] Threat scanner armed",
  "█████████████████████████ 100%",
  "[RDY] ALL SYSTEMS NOMINAL",
];

export default function MatrixGrid({
  positions,
  portfolios,
  onPositionClick,
  onBack,
  initialFilter,
  showEKG = true,
  showTickerTape = true,
}: MatrixGridProps) {
  const [hovIdx, setHovIdx] = useState<number | null>(null);
  const [sortBy, setSortBy] = useState<"value" | "perf" | "alpha" | "portfolio">("value");
  const [filterP, setFilterP] = useState<string | null>(initialFilter ?? null);
  const [mounted, setMounted] = useState(false);
  const [boot, setBoot] = useState(0);
  const [clock, setClock] = useState("");
  const [glitchIdx, setGlitchIdx] = useState(-1);
  const [anomalies, setAnomalies] = useState(new Set<number>());
  const [selectedPos, setSelectedPos] = useState<MatrixPosition | null>(null);
  const [breathPhase, setBreathPhase] = useState(0);
  const [bootLines, setBootLines] = useState<string[]>([]);
  const mouseXRef = useRef(-1000);
  const mouseYRef = useRef(-1000);
  const gridRef = useRef<HTMLDivElement>(null);
  const breathFrameRef = useRef<number>(0);

  // Boot sequence
  useEffect(() => {
    BOOT_LINES.forEach((line, i) => {
      setTimeout(() => setBootLines((prev) => [...prev, line]), i * 120);
    });
    setTimeout(() => setBoot(1), 300);
    setTimeout(() => setBoot(2), 700);
    setTimeout(() => { setBoot(3); setMounted(true); }, 1100);
  }, []);

  // Clock
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setClock(
        d.toLocaleTimeString("en-US", { hour12: false }) +
        "." + String(d.getMilliseconds()).padStart(3, "0")
      );
    };
    tick();
    const i = setInterval(tick, 47);
    return () => clearInterval(i);
  }, []);

  // Glitch
  useEffect(() => {
    const schedule = () => {
      const delay = 2500 + Math.random() * 4000;
      return setTimeout(() => {
        setGlitchIdx(Math.floor(Math.random() * positions.length));
        setTimeout(() => setGlitchIdx(-1), 100);
        scheduleRef.current = schedule();
      }, delay);
    };
    const scheduleRef = { current: schedule() };
    return () => clearTimeout(scheduleRef.current);
  }, [positions.length]);

  // Anomaly scanner
  useEffect(() => {
    const i = setInterval(() => {
      const newA = new Set<number>();
      const count = Math.min(3, positions.length);
      for (let j = 0; j < count; j++) newA.add(Math.floor(Math.random() * positions.length));
      setAnomalies(newA);
      setTimeout(() => setAnomalies(new Set()), 2000);
    }, 5000);
    return () => clearInterval(i);
  }, [positions.length]);

  // Breathing wave
  useEffect(() => {
    const tick = () => {
      setBreathPhase((prev) => prev + 0.02);
      breathFrameRef.current = requestAnimationFrame(tick);
    };
    breathFrameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(breathFrameRef.current);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "1") setSortBy("value");
      if (e.key === "2") setSortBy("perf");
      if (e.key === "3") setSortBy("alpha");
      if (e.key === "4") setSortBy("portfolio");
      if (e.key === "Escape") { setSelectedPos(null); setFilterP(null); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Parallax
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = gridRef.current?.getBoundingClientRect();
    if (!rect) return;
    mouseXRef.current = e.clientX;
    mouseYRef.current = e.clientY;
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const rx = (e.clientX - cx) / rect.width * 6;
    const ry = (e.clientY - cy) / rect.height * 4;
    if (gridRef.current) {
      gridRef.current.style.transform =
        `perspective(1200px) rotateY(${rx}deg) rotateX(${-ry}deg)`;
    }
  }, []);

  const handleMouseLeave = useCallback(() => {
    mouseXRef.current = -1000;
    mouseYRef.current = -1000;
    if (gridRef.current) {
      gridRef.current.style.transform = "perspective(1200px) rotateY(0deg) rotateX(0deg)";
    }
  }, []);

  // Sorted / filtered positions
  const sorted = useMemo(() => {
    let arr = [...positions];
    if (filterP) arr = arr.filter((p) => p.portfolioId === filterP);
    if (sortBy === "value") arr.sort((a, b) => b.value - a.value);
    else if (sortBy === "perf") arr.sort((a, b) => b.perf - a.perf);
    else if (sortBy === "alpha") arr.sort((a, b) => a.ticker.localeCompare(b.ticker));
    else if (sortBy === "portfolio") arr.sort((a, b) => a.portfolioId.localeCompare(b.portfolioId) || b.value - a.value);
    return arr;
  }, [positions, sortBy, filterP]);

  const maxVal = useMemo(() => Math.max(...positions.map((p) => p.value), 1), [positions]);
  const hovered = hovIdx !== null ? sorted[hovIdx] : null;
  const totalVal = positions.reduce((s, p) => s + p.value, 0);
  const avgP = positions.length > 0
    ? (positions.reduce((s, p) => s + p.perf, 0) / positions.length).toFixed(1)
    : "0.0";
  const wins = positions.filter((p) => p.perf > 0).length;
  const top = [...positions].sort((a, b) => b.perf - a.perf)[0];
  const bot = [...positions].sort((a, b) => a.perf - b.perf)[0];
  const tickers = useMemo(() => [...new Set(positions.map((p) => p.ticker))], [positions]);

  return (
    <div
      style={{
        width: "100%", height: "100%", background: "#040608",
        fontFamily: MATRIX_FONT, color: "#ccc",
        position: "relative", overflow: "hidden",
        display: "flex", flexDirection: "column",
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {/* Google Font */}
      <link
        href="https://fonts.googleapis.com/css2?family=Azeret+Mono:wght@300;400;500;600;700&display=swap"
        rel="stylesheet"
      />

      {/* CSS animations + cell hover effects */}
      <style>{`
        @keyframes matrixTicker { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }
        @keyframes matrixFadeIn { from{opacity:0} to{opacity:1} }
        @keyframes matrixScaleIn { from{opacity:0;transform:scale(0.95)} to{opacity:1;transform:scale(1)} }
        @keyframes matrixGlitch {
          0%{transform:translate(0);filter:none}
          25%{transform:translate(-3px,1px);filter:hue-rotate(90deg)}
          50%{transform:translate(3px,-1px);filter:hue-rotate(-90deg) saturate(2)}
          75%{transform:translate(-1px,-2px);filter:hue-rotate(45deg)}
          100%{transform:translate(0);filter:none}
        }
        @keyframes matrixSlideUp { from{transform:translateY(100%);opacity:0} to{transform:translateY(0);opacity:1} }
        @keyframes matrixAnomalyPulse {
          0%,100%{box-shadow:inset 0 0 0 1px rgba(248,113,113,0.1)}
          50%{box-shadow:inset 0 0 0 1px rgba(248,113,113,0.5),0 0 12px rgba(248,113,113,0.15)}
        }
        @keyframes matrixTermLine { from{opacity:0;transform:translateX(-4px)} to{opacity:1;transform:translateX(0)} }
        @keyframes matrixBlink { 0%,100%{opacity:1} 50%{opacity:0} }
        .matrix-cell:hover { background: rgba(74,222,128,0.035) !important; }
        .matrix-cell:hover .matrix-tk { color:#fff !important; text-shadow:0 0 10px rgba(74,222,128,0.5); }
        .matrix-cell:hover .matrix-ret { opacity:1 !important; }
        .matrix-cell:hover .matrix-chroma { opacity:1 !important; }
        .matrix-sb:hover { color:#4ade80 !important; }
        .matrix-fb:hover { border-color:rgba(74,222,128,0.2) !important; color:#888 !important; }
        ::-webkit-scrollbar{width:3px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:rgba(74,222,128,0.12);border-radius:3px}
      `}</style>

      {/* Background canvas layer */}
      <BackgroundCanvas mouseX={mouseXRef} mouseY={mouseYRef} tickers={tickers} />

      {/* Scanlines overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", zIndex: 1,
        background: "repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.025) 2px,rgba(0,0,0,0.025) 4px)",
      }} />

      {/* Boot terminal overlay */}
      {boot < 3 && (
        <div style={{
          position: "absolute", inset: 0, zIndex: 100, background: "#040608",
          padding: "40px", display: "flex", flexDirection: "column", justifyContent: "center",
        }}>
          <div style={{ maxWidth: 500 }}>
            {bootLines.map((line, i) => (
              <div key={i} style={{
                fontSize: 11, fontFamily: MATRIX_FONT, marginBottom: 4,
                color: line.includes("100%") || line.includes("RDY") ? "#4ade80" : "#4ade8088",
                animation: "matrixTermLine 0.15s ease",
                letterSpacing: "0.03em",
              }}>
                {line}
              </div>
            ))}
            <span style={{
              display: "inline-block", width: 8, height: 14, background: "#4ade80",
              animation: "matrixBlink 0.8s step-end infinite", marginTop: 4,
            }} />
          </div>
        </div>
      )}

      {/* Main content */}
      <div style={{
        position: "relative", zIndex: 2, display: "flex", flexDirection: "column",
        flex: 1, overflow: "hidden",
        opacity: boot >= 3 ? 1 : 0, transition: "opacity 0.6s",
      }}>

        {/* ── HEADER ── */}
        <div style={{ padding: "10px 20px 0", display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 20 }}>
            <div>
              <div style={{ fontSize: 7, color: "#4ade8044", letterSpacing: "0.2em", marginBottom: 3 }}>
                SYS::MATRIX_v3.0
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ fontSize: 18, fontWeight: 700, color: "#e8ffe8", letterSpacing: "0.08em", textShadow: "0 0 25px rgba(74,222,128,0.12)" }}>
                  THE MATRIX
                </span>
                <span style={{ fontSize: 8, color: "#f87171", letterSpacing: "0.06em", border: "1px solid #f8717133", padding: "1px 5px", background: "rgba(248,113,113,0.05)" }}>
                  LIVE
                </span>
              </div>
            </div>
            <AllocRing positions={positions} portfolios={portfolios} />
            <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 2 }}>
              {(["FEED", "SYNC", "SCAN", "EKG", "THREAT"] as const).map((s, i) => (
                <div key={s} style={{
                  display: "flex", alignItems: "center", gap: 3, fontSize: 7,
                  color: i === 4 ? (anomalies.size > 0 ? "#f87171" : "#222") : "#333",
                  letterSpacing: "0.1em", transition: "color 0.3s",
                }}>
                  <span style={{
                    display: "inline-block", width: 4, height: 4, borderRadius: "50%",
                    background: i === 4 ? (anomalies.size > 0 ? "#f87171" : "#222") : "#4ade80",
                    boxShadow: i === 4 && anomalies.size > 0 ? "0 0 6px #f8717166" : i < 4 ? "0 0 4px #4ade8044" : "none",
                    transition: "all 0.3s",
                  }} />
                  {s}
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", gap: 16, alignItems: "flex-end" }}>
            {[
              { l: "POS", v: String(sorted.length), c: "#e8ffe8" },
              { l: "EQUITY", v: `$${totalVal.toLocaleString()}`, c: "#e8ffe8" },
              { l: "AVG P&L", v: `${avgP}%`, c: pc(parseFloat(avgP)) },
            ].map((s) => (
              <div key={s.l} style={{ textAlign: "right" }}>
                <div style={{ fontSize: 7, color: "#222", letterSpacing: "0.14em" }}>{s.l}</div>
                <div style={{ fontSize: 13, color: s.c, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{s.v}</div>
              </div>
            ))}
            {/* W/L */}
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 7, color: "#222", letterSpacing: "0.14em" }}>W/L</div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                <span style={{ color: "#4ade80" }}>{wins}</span>
                <span style={{ color: "#151515" }}>/</span>
                <span style={{ color: "#f87171" }}>{positions.length - wins}</span>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 7, color: "#222", letterSpacing: "0.14em" }}>SYS.CLK</div>
              <div style={{ fontSize: 10, color: "#4ade8044", fontVariantNumeric: "tabular-nums" }}>{clock}</div>
            </div>
          </div>
        </div>

        {/* ── EKG VITALS ── */}
        {showEKG && (
          <div style={{
            height: 48, margin: "4px 20px 0",
            border: "1px solid rgba(74,222,128,0.04)",
            position: "relative", overflow: "hidden", background: "rgba(0,0,0,0.2)",
            flexShrink: 0,
          }}>
            <EKGStrip portfolios={portfolios} />
            <div style={{ position: "absolute", top: 2, right: 6, fontSize: 7, color: "#222", letterSpacing: "0.12em" }}>
              PORTFOLIO VITALS
            </div>
          </div>
        )}

        {/* ── TICKER TAPE ── */}
        {showTickerTape && (
          <div style={{ margin: "4px 20px 0", flexShrink: 0 }}>
            <TickerTape positions={positions} />
          </div>
        )}

        {/* ── CONTROLS ── */}
        <div style={{ padding: "6px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
          <div style={{ display: "flex", gap: 1, alignItems: "center" }}>
            <span style={{ fontSize: 7, color: "#1a1a1a", letterSpacing: "0.14em", marginRight: 8 }}>SORT</span>
            {(["value", "perf", "alpha", "portfolio"] as const).map((k, n) => (
              <button key={k} className="matrix-sb" onClick={() => setSortBy(k)} style={{
                padding: "2px 8px", fontSize: 8, letterSpacing: "0.08em", textTransform: "uppercase",
                fontFamily: MATRIX_FONT,
                background: sortBy === k ? "rgba(74,222,128,0.07)" : "transparent",
                color: sortBy === k ? "#4ade80" : "#1e1e1e",
                border: sortBy === k ? "1px solid rgba(74,222,128,0.12)" : "1px solid transparent",
                cursor: "pointer", transition: "all 0.15s",
              }}>
                {sortBy === k && <span style={{ marginRight: 3 }}>▸</span>}
                {k}
                <span style={{ fontSize: 6, color: "#1a1a1a", marginLeft: 4 }}>[{n + 1}]</span>
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 2 }}>
            {onBack && (
              <button onClick={onBack} style={{
                padding: "2px 7px", fontSize: 7, fontFamily: MATRIX_FONT,
                background: "transparent", color: "#333",
                border: "1px solid rgba(255,255,255,0.04)",
                cursor: "pointer", letterSpacing: "0.08em", marginRight: 8,
              }}>← BACK</button>
            )}
            <button className="matrix-fb" onClick={() => setFilterP(null)} style={{
              padding: "2px 7px", fontSize: 7, fontFamily: MATRIX_FONT,
              background: !filterP ? "rgba(74,222,128,0.05)" : "transparent",
              color: !filterP ? "#4ade80" : "#1a1a1a",
              border: !filterP ? "1px solid rgba(74,222,128,0.1)" : "1px solid rgba(255,255,255,0.02)",
              cursor: "pointer", letterSpacing: "0.08em", transition: "all 0.15s",
            }}>ALL</button>
            {portfolios.map((p) => (
              <button key={p.id} className="matrix-fb" onClick={() => setFilterP(filterP === p.id ? null : p.id)} style={{
                padding: "2px 7px", fontSize: 7, fontFamily: MATRIX_FONT,
                background: filterP === p.id ? `${p.color}12` : "transparent",
                color: filterP === p.id ? p.color : "#1a1a1a",
                border: `1px solid ${filterP === p.id ? p.color + "33" : "rgba(255,255,255,0.02)"}`,
                cursor: "pointer", letterSpacing: "0.08em", transition: "all 0.15s",
                display: "flex", alignItems: "center", gap: 3,
              }}>
                <span style={{
                  width: 3, height: 3, borderRadius: "50%", background: p.color,
                  opacity: filterP === p.id ? 1 : 0.15,
                  boxShadow: filterP === p.id ? `0 0 5px ${p.color}66` : "none",
                  transition: "all 0.2s",
                }} />
                {p.abbr}
              </button>
            ))}
          </div>
        </div>

        {/* ── GRID (with 3D parallax) ── */}
        <div style={{ flex: 1, padding: "4px 14px", overflow: "auto", minHeight: 0 }}>
          <div
            ref={gridRef}
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(112px, 1fr))",
              gap: 2, alignContent: "start",
              transition: "transform 0.1s ease-out",
              transformStyle: "preserve-3d",
            }}
          >
            {sorted.map((pos, i) => {
              const isHov = hovIdx === i;
              const isGlitch = glitchIdx === i;
              const isAnomaly = anomalies.has(positions.indexOf(pos));
              const barW = (pos.value / maxVal) * 100;
              const breath = Math.sin(breathPhase + i * 0.08) * 0.3;

              return (
                <div
                  key={`${pos.ticker}-${pos.portfolioId}-${i}`}
                  className="matrix-cell"
                  onMouseEnter={() => setHovIdx(i)}
                  onMouseLeave={() => setHovIdx(null)}
                  onClick={() => {
                    setSelectedPos(pos);
                    onPositionClick?.(pos);
                  }}
                  style={{
                    background: pbg(pos.perf),
                    padding: "6px 6px 4px",
                    cursor: "crosshair",
                    position: "relative",
                    overflow: "hidden",
                    opacity: mounted ? 0.85 + breath * 0.15 : 0,
                    transform: mounted ? `translateZ(${breath * 2}px)` : "translateY(6px)",
                    transition: "opacity 0.3s, transform 0.4s, background 0.15s",
                    transitionDelay: mounted ? `${Math.min(i * 10, 800)}ms` : "0ms",
                    borderLeft: `2px solid ${pos.portfolioColor}${isHov ? "99" : "10"}`,
                    animation: isGlitch
                      ? "matrixGlitch 0.1s ease"
                      : isAnomaly
                      ? "matrixAnomalyPulse 0.8s ease infinite"
                      : "none",
                  }}
                >
                  {/* Chromatic aberration on hover */}
                  <div className="matrix-chroma" style={{
                    position: "absolute", inset: 0, pointerEvents: "none",
                    opacity: isHov ? 1 : 0, transition: "opacity 0.1s", mixBlendMode: "screen",
                  }}>
                    <div style={{ position: "absolute", inset: 0, background: "rgba(255,0,0,0.015)", transform: "translate(-1px,0)" }} />
                    <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,255,0.015)", transform: "translate(1px,0)" }} />
                  </div>

                  {/* Reticles */}
                  <div className="matrix-ret" style={{ position: "absolute", inset: 0, opacity: isHov ? 1 : 0, transition: "opacity 0.12s", pointerEvents: "none" }}>
                    <Reticle color="#4ade80" s={5} />
                  </div>

                  {/* Anomaly indicator */}
                  {isAnomaly && (
                    <div style={{ position: "absolute", top: 2, right: 3, fontSize: 6, color: "#f87171", textShadow: "0 0 4px rgba(248,113,113,0.5)" }}>⚠</div>
                  )}

                  {/* Value bar (bottom edge) */}
                  <div style={{
                    position: "absolute", bottom: 0, left: 0,
                    width: `${barW}%`, height: isHov ? 2 : 1,
                    background: `linear-gradient(90deg,${pos.portfolioColor}${isHov ? "55" : "12"},transparent)`,
                    transition: "all 0.15s",
                  }} />

                  {/* Ticker + all-time perf */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <span className="matrix-tk" style={{ fontSize: 10, fontWeight: 600, color: "#555", letterSpacing: "0.04em", transition: "all 0.12s" }}>
                      {pos.ticker}
                    </span>
                    <span style={{ fontSize: 8, fontWeight: 500, color: pc(pos.perf), fontVariantNumeric: "tabular-nums" }}>
                      {pos.perf > 0 ? "+" : ""}{pos.perf.toFixed(1)}
                    </span>
                  </div>

                  {/* Value + sparkline */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginTop: 2 }}>
                    <span style={{ fontSize: 7, color: "#292929", fontVariantNumeric: "tabular-nums" }}>{fv(pos.value)}</span>
                    <Sparkline data={pos.sparkline} color={pos.perf >= 0 ? "#4ade80" : "#f87171"} w={40} h={12} />
                  </div>

                  {/* Day change micro bar */}
                  <div style={{ marginTop: 3, height: 2, display: "flex", gap: 0.5 }}>
                    <div style={{
                      width: `${Math.min(100, Math.abs(pos.day) * 25)}%`,
                      height: "100%",
                      background: pos.day >= 0 ? "rgba(74,222,128,0.25)" : "rgba(248,113,113,0.25)",
                      transition: "width 0.3s",
                    }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── STATUS BAR ── */}
        <div style={{
          padding: "4px 20px",
          borderTop: "1px solid rgba(74,222,128,0.04)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          fontSize: 7, color: "#1a1a1a", letterSpacing: "0.1em", flexShrink: 0,
        }}>
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            {top && <span>▲ <span style={{ color: "#4ade80" }}>{top.ticker} +{top.perf.toFixed(1)}%</span></span>}
            {bot && <span>▼ <span style={{ color: "#f87171" }}>{bot.ticker} {bot.perf.toFixed(1)}%</span></span>}
            <span style={{ color: "#161616" }}>│</span>
            <span>KEYS: [1-4] SORT · [ESC] RESET · CLICK CELL FOR DETAIL</span>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <Waveform width={100} height={12} />
            <span>MATRIX::v3.0</span>
            <span style={{ color: "#4ade8044", animation: "matrixBlink 2s step-end infinite" }}>■ LIVE</span>
          </div>
        </div>
      </div>

      {/* ── HOVER DETAIL PANEL (bottom bar) ── */}
      {hovered && !selectedPos && (
        <div style={{
          position: "fixed", bottom: 0, left: 0, right: 0,
          background: "rgba(4,6,8,0.95)",
          borderTop: "1px solid rgba(74,222,128,0.1)",
          padding: "8px 20px",
          display: "flex", gap: 24, alignItems: "center",
          zIndex: 200, animation: "matrixSlideUp 0.12s ease",
          backdropFilter: "blur(12px)",
        }}>
          <div style={{ position: "relative", padding: "3px 10px" }}>
            <Reticle color={hovered.portfolioColor} s={7} />
            <span style={{
              fontSize: 16, fontWeight: 700, color: "#fff",
              textShadow: `0 0 14px ${hovered.portfolioColor}44`,
            }}>{hovered.ticker}</span>
          </div>
          {[
            { l: "PORTFOLIO", v: hovered.portfolioName, c: hovered.portfolioColor },
            { l: "VALUE", v: `$${hovered.value.toLocaleString()}` },
            { l: "ALL-TIME", v: `${hovered.perf > 0 ? "+" : ""}${hovered.perf.toFixed(1)}%`, c: pc(hovered.perf) },
            { l: "DAY", v: `${hovered.day > 0 ? "+" : ""}${hovered.day.toFixed(2)}%`, c: pc(hovered.day) },
            { l: "VOL", v: hovered.vol != null ? `${hovered.vol}%` : "N/A" },
            { l: "BETA", v: hovered.beta != null ? String(hovered.beta) : "N/A" },
            { l: "SECTOR", v: hovered.sector },
          ].map((s) => (
            <div key={s.l}>
              <div style={{ fontSize: 6, color: "#222", letterSpacing: "0.14em" }}>{s.l}</div>
              <div style={{ fontSize: 11, color: s.c ?? "#888", fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>{s.v}</div>
            </div>
          ))}
          <div style={{ flex: 1, display: "flex", justifyContent: "flex-end" }}>
            <Sparkline data={hovered.sparkline} color={hovered.perf >= 0 ? "#4ade80" : "#f87171"} w={110} h={24} />
          </div>
        </div>
      )}

      {/* ── DETAIL CARD OVERLAY ── */}
      <DetailCard pos={selectedPos} onClose={() => setSelectedPos(null)} />
    </div>
  );
}
```

**Step 3: Write `index.ts`**

```typescript
export { default } from "./MatrixGrid";
export type { MatrixGridProps, MatrixPosition, MatrixPortfolio } from "./types";
export { buildPortfolioMap, crossMoverToMatrix, positionToMatrix } from "./constants";
```

**Step 4: Commit**

```bash
git add dashboard/src/components/MatrixGrid/
git commit -m "feat: add main MatrixGrid component with all visual features"
```

---

## Task 5: Wire MatrixGrid into Portfolio View (App.tsx)

**Files:**
- Modify: `dashboard/src/App.tsx`
- Modify: `dashboard/src/hooks/usePortfolioState.ts` (if needed to expose portfolio meta)

**Step 1: Read `App.tsx` to understand current layout**

Currently, portfolio view renders:
```
<PortfolioSummary />
Three columns: PositionsPanel (320px) | CenterPane | FocusPane (300px)
```

**Step 2: Understand what data is needed**

- `state.positions` (Position[]) — available from `usePortfolioState()`
- Portfolio metadata (id, name) — we need the active portfolio's `PortfolioSummary` from overview data, OR we can use `usePortfolios()` hook

Check if `usePortfolios` is already imported. If not, import it.

**Step 3: Add imports to App.tsx**

```typescript
import MatrixGrid from "./components/MatrixGrid";
import { buildPortfolioMap, positionToMatrix } from "./components/MatrixGrid/constants";
import type { MatrixPortfolio } from "./components/MatrixGrid/types";
import { useOverview } from "./hooks/usePortfolios";
```

**Step 4: Build the portfolio MatrixPositions in App.tsx**

Inside the `App` component, after `const portfolioId = usePortfolioStore(...)`:

```typescript
const { data: overview } = useOverview();

// Build MatrixPortfolio for the active portfolio
const activeMatrixPortfolio = useMemo<MatrixPortfolio | null>(() => {
  if (isOverview || !portfolioId) return null;
  const summaries = overview?.portfolios ?? [];
  const ids = summaries.map((s) => ({ id: s.id, name: s.name }));
  // If we don't have it from overview yet, use a minimal fallback
  const portfolioMeta = ids.find((p) => p.id === portfolioId)
    ?? { id: portfolioId, name: portfolioId };
  const map = buildPortfolioMap([portfolioMeta]);
  return map.get(portfolioId) ?? null;
}, [isOverview, portfolioId, overview]);

const matrixPositions = useMemo(() => {
  if (!activeMatrixPortfolio || !state?.positions) return [];
  return state.positions.map((pos) => positionToMatrix(pos, activeMatrixPortfolio));
}, [state?.positions, activeMatrixPortfolio]);
```

**Step 5: Replace the 3-column layout with MatrixGrid**

In the portfolio branch of the JSX, replace the three-column div:

```typescript
{isOverview ? (
  <main className="flex-1 flex flex-col overflow-hidden min-w-0">
    <OverviewPage />
  </main>
) : (
  <div className="flex-1 flex flex-col overflow-hidden min-w-0">
    <PortfolioSummary />
    {/* MatrixGrid replaces the 3-column layout */}
    <div className="flex-1 overflow-hidden" style={{ minHeight: 0 }}>
      <MatrixGrid
        positions={matrixPositions}
        portfolios={activeMatrixPortfolio ? [activeMatrixPortfolio] : []}
        initialFilter={portfolioId}
      />
    </div>
  </div>
)}
```

**Step 6: Add missing import `useMemo` if not already imported**

Check the imports at the top of App.tsx. Add `useMemo` to the Component import if missing.

**Step 7: Commit**

```bash
git add dashboard/src/App.tsx
git commit -m "feat: wire MatrixGrid into portfolio view replacing 3-column layout"
```

---

## Task 6: Wire MatrixGrid into Overview (OverviewPage.tsx)

**Files:**
- Modify: `dashboard/src/components/OverviewPage.tsx`

**Step 1: Add imports to OverviewPage.tsx**

```typescript
import MatrixGrid from "./MatrixGrid";
import { buildPortfolioMap, crossMoverToMatrix } from "./MatrixGrid/constants";
import type { MatrixPortfolio } from "./MatrixGrid/types";
```

**Step 2: Build MatrixPositions and MatrixPortfolios inside OverviewPage**

Find where `OverviewPage` renders and add these memoized values:

```typescript
// Inside the OverviewPage component, after overview and portfolios data is loaded:
const matrixPortfolios = useMemo<MatrixPortfolio[]>(() => {
  if (!portfolios?.length) return [];
  const ids = portfolios.map((p) => ({ id: p.id, name: p.name }));
  const map = buildPortfolioMap(ids);
  return ids.map((p) => map.get(p.id)!).filter(Boolean);
}, [portfolios]);

const matrixPositions = useMemo(() => {
  if (!overview?.all_positions?.length || !matrixPortfolios.length) return [];
  const map = buildPortfolioMap(matrixPortfolios.map((p) => ({ id: p.id, name: p.name })));
  return overview.all_positions.map((m) => crossMoverToMatrix(m, map));
}, [overview?.all_positions, matrixPortfolios]);
```

**Step 3: Replace `AllPositionsPanel` with MatrixGrid**

Find the render location of `<AllPositionsPanel ... />` (around line 153 in OverviewPage). Replace it with:

```typescript
{/* Replace AllPositionsPanel with MatrixGrid */}
{matrixPositions.length > 0 && (
  <div style={{ flex: 1, minHeight: "400px", marginTop: "16px" }}>
    <MatrixGrid
      positions={matrixPositions}
      portfolios={matrixPortfolios}
      onPositionClick={(pos) => setPortfolio(pos.portfolioId)}
    />
  </div>
)}
```

**Step 4: Verify the OverviewPage structure**

OverviewPage renders in order: AggregateBar → portfolio cards → AllPositionsPanel. After this change, the layout is: AggregateBar → portfolio cards → MatrixGrid (full width, fills remaining height).

The `OverviewPage` component itself is inside a `flex-1 flex-col` container (from App.tsx). The MatrixGrid needs `flex: 1` to fill the remaining space. Check that the wrapping div in OverviewPage allows this.

If OverviewPage renders with `overflow-y: auto` on its root, add `minHeight: 0` to allow the MatrixGrid to fill the flex space properly.

**Step 5: Remove unused AllPositionsPanel component and imports**

Remove the `AllPositionsPanel` function definition and its `import { ConstellationMap }` + `import { PerformanceChart }` if no longer used anywhere in OverviewPage.

**Step 6: Commit**

```bash
git add dashboard/src/components/OverviewPage.tsx
git commit -m "feat: wire MatrixGrid into overview replacing AllPositionsPanel"
```

---

## Task 7: Smoke Test + Fix Tailwind Interference

**Goal:** Run the dashboard and verify the MatrixGrid renders correctly. Fix any CSS conflicts between Tailwind classes and MatrixGrid inline styles.

**Step 1: Start the dev server**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run dev
```

Expected: Vite starts on port 5173, no TypeScript errors. Also start the API:
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8001
```

**Step 2: Common issues to check and fix**

1. **`<link>` tag in component JSX**: React may warn about rendering `<link>` outside `<head>`. If so, move the Google Fonts link to `index.html` in the Vite public folder. Add this to `dashboard/index.html` inside `<head>`:
   ```html
   <link href="https://fonts.googleapis.com/css2?family=Azeret+Mono:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
   ```
   Then remove the `<link>` from MatrixGrid.tsx.

2. **TypeScript errors on `mixBlendMode`**: The CSS property `mixBlendMode` expects type `React.CSSProperties["mixBlendMode"]`. Ensure it's typed as a string literal: `mixBlendMode: "screen" as const`.

3. **`flex-1` on wrapper not working**: If MatrixGrid doesn't fill height, the wrapper div in App.tsx needs explicit height. Change `className="flex-1 overflow-hidden"` to also add `style={{ height: "100%" }}`.

4. **OverviewPage scroll**: OverviewPage may have `overflow-y: auto` on its root. Add `display: flex; flexDirection: column; height: 100%` to the OverviewPage root to allow MatrixGrid to fill the remaining space.

5. **EKGStrip re-renders**: The `linesRef` update effect must list `portfolios` as a dependency. If EKG flickers, ensure the portfolios prop is memoized in the parent before passing.

6. **`position: "fixed"` hover panel covers bottombar**: The hover detail panel uses `position: fixed; bottom: 0` which will overlap the status bar. This is intentional — the detail panel only shows on hover, and the status bar is above it in z-index. If the status bar disappears, check z-index: hover panel is `zIndex: 200`, status bar has `zIndex: 2`. The hover panel should overlay it. This is correct behavior from the reference.

**Step 3: Verify boot sequence**

On first render, the boot terminal should appear with lines fading in over ~1s, then the grid fades in. Cells should stagger-animate upward.

**Step 4: Verify all visual features**

Check each feature from the spec:
- [ ] Grid cells show ticker, perf%, value, sparkline, day-change bar
- [ ] Left border colored by portfolio
- [ ] Value bar at bottom of each cell
- [ ] Reticle corners appear on hover
- [ ] Chromatic aberration on hover
- [ ] Glitch animation fires occasionally
- [ ] Anomaly pulse fires on ~3 cells every 5 seconds
- [ ] Background particles + rain + scan beams visible
- [ ] EKG strip animates
- [ ] Ticker tape scrolls
- [ ] Header shows stats + AllocRing + status dots + clock
- [ ] Sort buttons work (1-4 keyboard shortcuts)
- [ ] Portfolio filter chips work
- [ ] Hover panel slides up from bottom
- [ ] Click opens detail card, ESC closes it
- [ ] 3D parallax on mouse move
- [ ] Status bar shows top/bottom movers + waveform

**Step 5: Commit any fixes**

```bash
git add -p  # stage specific fixes only
git commit -m "fix: MatrixGrid smoke test fixes"
```

---

## Task 8: Update PROJECT_STATE.md and Push

**Step 1: Update PROJECT_STATE.md**

Update the file at `/Users/gregmclaughlin/MicroCapRebuilder/PROJECT_STATE.md`:

Change the current phase to `MatrixGrid Dashboard (Complete)` and add to "Recently Completed":

```markdown
### MatrixGrid Dashboard (2026-03-06)
- Built complete MatrixGrid sci-fi HUD visualization
- Replaced AllPositionsPanel in OverviewPage with MatrixGrid
- Replaced 3-column layout in portfolio view with MatrixGrid
- Sub-components: Sparkline, AllocRing, Waveform, Reticle, TickerTape, DetailCard, BackgroundCanvas, EKGStrip
- Data mapping: CrossPortfolioMover → MatrixPosition (overview), Position → MatrixPosition (portfolio)
- Portfolio colors: deterministic palette by portfolio.id (alphabetical sort)
- Synthetic sparklines from unrealized_pnl_pct (deterministic, no Math.random per render)
- Boot sequence, 3D parallax, glitch+anomaly effects, breathing wave, all CSS animations
- Font: Azeret Mono (Google Fonts), injected in index.html
```

**Step 2: Push to GitHub**

```bash
git push origin main
```

---

## Quick Reference: Data Flow

```
Overview mode:
  useOverview() → overview.all_positions (CrossPortfolioMover[])
  usePortfolios() → portfolios (PortfolioSummary[])
  buildPortfolioMap(portfolios) → Map<id, MatrixPortfolio>
  all_positions.map(crossMoverToMatrix) → MatrixPosition[]
  → <MatrixGrid positions={...} portfolios={...} onPositionClick={setPortfolio} />

Portfolio mode:
  usePortfolioState() → state.positions (Position[])
  useOverview() → overview.portfolios → find active portfolio name
  buildPortfolioMap([{id, name}]) → Map<id, MatrixPortfolio>
  state.positions.map(positionToMatrix) → MatrixPosition[]
  → <MatrixGrid positions={...} portfolios={[activePort]} initialFilter={portfolioId} />
```
