# EKG Strip Real Performance Data — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the synthetic EKG heartbeat animation with the portfolio's actual `day_pnl_pct` history from `daily_snapshots.csv`.

**Architecture:** Add `equityCurve?: number[]` to `MatrixPortfolio`, populate it from `state.snapshots` in `App.tsx` (data already in scope), then update `EKGStrip.tsx` to draw real values with a synthetic fallback for new portfolios with fewer than 3 days of data.

**Tech Stack:** React 19, TypeScript, Canvas 2D API, Vite

---

## Chunk 1: Type + Data Threading

### Task 1: Add `equityCurve` to `MatrixPortfolio`

**Files:**
- Modify: `dashboard/src/components/MatrixGrid/types.ts`

- [ ] **Step 1: Add the field**

  Open `dashboard/src/components/MatrixGrid/types.ts`. The `MatrixPortfolio` interface currently ends at `hex`. Add one field:

  ```ts
  export interface MatrixPortfolio {
    id: string;
    name: string;
    abbr: string;
    color: string;
    hex: [number, number, number];
    equityCurve?: number[];   // ← add this
  }
  ```

- [ ] **Step 2: Verify TypeScript compiles**

  ```bash
  cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
  npx tsc --noEmit 2>&1 | head -20
  ```

  Expected: no errors (the field is optional so no existing code breaks).

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/gregmclaughlin/MicroCapRebuilder
  git add dashboard/src/components/MatrixGrid/types.ts
  git commit -m "feat: add equityCurve field to MatrixPortfolio type"
  ```

---

### Task 2: Thread snapshot data into `activeMatrixPortfolio` in `App.tsx`

**Files:**
- Modify: `dashboard/src/App.tsx:71-79`

The `activeMatrixPortfolio` memo already runs when `portfolioId` or `overview` changes. We need to also recompute when `state.snapshots` changes, and spread the equity curve into the result.

- [ ] **Step 1: Update the `useMemo` dependency array and spread `equityCurve`**

  Locate this block in `App.tsx` (lines ~71–79):

  ```ts
  const activeMatrixPortfolio = useMemo<MatrixPortfolio | null>(() => {
    if (isOverview || !portfolioId) return null;
    const summaries = overview?.portfolios ?? [];
    const ids = summaries.length > 0
      ? summaries.map((s) => ({ id: s.id, name: s.name }))
      : [{ id: portfolioId, name: portfolioId }];
    const map = buildPortfolioMap(ids);
    return map.get(portfolioId) ?? null;
  }, [isOverview, portfolioId, overview]);
  ```

  Replace with:

  ```ts
  const activeMatrixPortfolio = useMemo<MatrixPortfolio | null>(() => {
    if (isOverview || !portfolioId) return null;
    const summaries = overview?.portfolios ?? [];
    const ids = summaries.length > 0
      ? summaries.map((s) => ({ id: s.id, name: s.name }))
      : [{ id: portfolioId, name: portfolioId }];
    const map = buildPortfolioMap(ids);
    const base = map.get(portfolioId) ?? null;
    if (!base) return null;
    const equityCurve = state?.snapshots?.map((s) => s.day_pnl_pct) ?? [];
    return equityCurve.length >= 3 ? { ...base, equityCurve } : base;
  }, [isOverview, portfolioId, overview, state?.snapshots]);
  ```

  Key points:
  - `state` is already in scope (line 64: `const { data: state, isLoading } = usePortfolioState()`)
  - Only spreads `equityCurve` when ≥ 3 data points exist — otherwise returns `base` unchanged (EKGStrip will fall back to synthetic)
  - `state?.snapshots` added to dependency array so the memo recomputes when snapshots arrive

- [ ] **Step 2: Verify TypeScript compiles**

  ```bash
  cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
  npx tsc --noEmit 2>&1 | head -20
  ```

  Expected: no errors.

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/gregmclaughlin/MicroCapRebuilder
  git add dashboard/src/App.tsx
  git commit -m "feat: thread snapshot equity curve into MatrixPortfolio"
  ```

---

## Chunk 2: EKGStrip Renderer

### Task 3: Rewrite `EKGStrip.tsx` draw logic

**Files:**
- Modify: `dashboard/src/components/MatrixGrid/EKGStrip.tsx`

The current file is 107 lines. We're replacing the `draw` function's inner loop only. The canvas setup, resize logic, and RAF loop structure stay identical.

**How the real-data renderer works:**
- Each `day_pnl_pct` value is the amplitude of a spike
- A day expands into 20 canvas points: flat baseline noise → spike at center → flat baseline noise
- `pct > 0.05` → green (`#4ade80`); `pct < -0.05` → red (`#f87171`); flat → dim portfolio color
- `|pct| ≥ 1.0` → glow halo (extra wide semi-transparent stroke before main stroke)
- A 2px cursor dot drawn at the right edge tracks the current point
- Amplitudes are clamped to `[-4, 4]` before scaling

**Fallback:** if `portfolios[0].equityCurve` is absent or length < 3, the existing synthetic heartbeat logic runs unchanged.

- [ ] **Step 1: Add a `buildBuffer` helper and the real-data draw path**

  Replace the entire contents of `EKGStrip.tsx` with:

  ```tsx
  import { useRef, useEffect } from "react";
  import type { MatrixPortfolio } from "./types";

  interface EKGStripProps {
    portfolios: MatrixPortfolio[];
  }

  /** Expand an array of daily pnl % values into a smooth scrolling point buffer.
   *  Each day → 20 points: flat noise → spike → flat noise. */
  function buildBuffer(pnlArray: number[]): { v: number; pct: number }[] {
    const pts: { v: number; pct: number }[] = [];
    for (const pct of pnlArray) {
      const amp = Math.max(-4, Math.min(4, pct));
      for (let k = 0; k < 20; k++) {
        let v: number;
        if      (k === 9 || k === 10) v = amp;
        else if (k === 8 || k === 11) v = amp * 0.55;
        else if (k === 7 || k === 12) v = amp * 0.22;
        else if (k === 6 || k === 13) v = amp * 0.07;
        else                          v = (Math.random() - 0.5) * 0.09;
        pts.push({ v, pct });
      }
    }
    return pts;
  }

  export default function EKGStrip({ portfolios }: EKGStripProps) {
    const ref        = useRef<HTMLCanvasElement>(null);
    const frameRef   = useRef<number>(0);

    // Synthetic heartbeat state (used when no real data)
    const linesRef = useRef(
      portfolios.map(() => ({ pts: [] as number[], phase: Math.random() * 100 }))
    );

    // Real-data buffer state
    const realRef = useRef<{ pts: { v: number; pct: number }[]; pos: number } | null>(null);

    useEffect(() => {
      linesRef.current = portfolios.map(() => ({
        pts: [] as number[],
        phase: Math.random() * 100,
      }));
      // Rebuild real buffer when equity curve changes
      const curve = portfolios[0]?.equityCurve;
      if (curve && curve.length >= 3) {
        realRef.current = { pts: buildBuffer(curve), pos: 0 };
      } else {
        realRef.current = null;
      }
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
        c.width  = w * dpr;
        c.height = h * dpr;
        c.style.width  = w + "px";
        c.style.height = h + "px";
      };
      resize();
      window.addEventListener("resize", resize);

      let frame = 0;

      const draw = () => {
        frameRef.current = requestAnimationFrame(draw);
        frame++;
        const ctx = c.getContext("2d")!;
        ctx.save();
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, w, h);

        if (realRef.current && realRef.current.pts.length >= 3) {
          // ── Real-data path ──────────────────────────────────────────────
          const real    = realRef.current;
          const step    = 1.5;
          const visible = Math.floor(w / step) + 2;
          const y0      = h / 2;
          const range   = h * 0.38;
          const color   = portfolios[0]?.color ?? "#4ade80";

          // Advance scroll every 2 frames
          if (frame % 2 === 0) real.pos = (real.pos + 1) % real.pts.length;

          // Collect visible slice
          const slice: { v: number; pct: number }[] = [];
          for (let k = 0; k < visible; k++) {
            slice.push(real.pts[(real.pos + k) % real.pts.length]);
          }

          // Zero baseline
          ctx.beginPath();
          ctx.moveTo(0, y0);
          ctx.lineTo(w, y0);
          ctx.strokeStyle = "rgba(255,255,255,0.04)";
          ctx.lineWidth   = 0.5;
          ctx.stroke();

          // Colored segments
          for (let j = 1; j < slice.length; j++) {
            const x0 = (j - 1) * step;
            const x1 = j       * step;
            const yA = y0 - slice[j - 1].v * range;
            const yB = y0 - slice[j].v     * range;
            const pct   = slice[j].pct;
            const isGain = pct >  0.05;
            const isLoss = pct < -0.05;
            const isBig  = Math.abs(pct) >= 1.0;
            const col    = isGain ? "#4ade80" : isLoss ? "#f87171" : color;
            const alpha  = isBig             ? "ee"
                         : Math.abs(pct) > 0.4 ? "bb"
                         : Math.abs(pct) > 0.1 ? "77"
                         : "2a";

            // Glow halo on big moves
            if (isBig) {
              ctx.beginPath();
              ctx.moveTo(x0, yA);
              ctx.lineTo(x1, yB);
              ctx.strokeStyle = col + "22";
              ctx.lineWidth   = 6;
              ctx.stroke();
            }

            // Main line
            ctx.beginPath();
            ctx.moveTo(x0, yA);
            ctx.lineTo(x1, yB);
            ctx.strokeStyle = col + alpha;
            ctx.lineWidth   = 1.2;
            ctx.stroke();
          }

          // Cursor dot at right edge
          const last   = slice[slice.length - 1];
          const cx     = (slice.length - 1) * step;
          const cy     = y0 - last.v * range;
          const dotCol = last.pct > 0 ? "#4ade80" : last.pct < 0 ? "#f87171" : "#4ade80";
          ctx.beginPath();
          ctx.arc(cx, cy, 2, 0, Math.PI * 2);
          ctx.fillStyle = dotCol + "cc";
          ctx.fill();

        } else {
          // ── Synthetic fallback (original logic) ──────────────────────────
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
            ctx.lineWidth   = 1;
            ctx.stroke();

            ctx.strokeStyle = port.color + "18";
            ctx.lineWidth   = 3;
            ctx.stroke();

            ctx.font      = "7px monospace";
            ctx.fillStyle = port.color + "44";
            ctx.fillText(port.abbr, 4, y0 + 3);

            if (i < portfolios.length - 1) {
              ctx.beginPath();
              ctx.moveTo(0, (i + 1) * laneH);
              ctx.lineTo(w, (i + 1) * laneH);
              ctx.strokeStyle = "rgba(255,255,255,0.02)";
              ctx.lineWidth   = 0.5;
              ctx.stroke();
            }
          });
        }

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

- [ ] **Step 2: Verify TypeScript compiles**

  ```bash
  cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
  npx tsc --noEmit 2>&1 | head -20
  ```

  Expected: no errors.

- [ ] **Step 3: Smoke-test in the browser**

  ```bash
  # In one terminal — API must already be running on port 8001.
  # If not: source .venv/bin/activate && uvicorn api.main:app --host 0.0.0.0 --port 8001
  cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
  npm run dev
  ```

  Open `http://localhost:5173`, navigate to any portfolio that has at least 3 days of snapshots.

  **Verify:**
  - [ ] EKG strip shows a single centered line (not stacked lanes)
  - [ ] Green spikes visible for gain days, red dips for loss days
  - [ ] Line scrolls continuously left
  - [ ] Cursor dot visible at right edge
  - [ ] Navigate to a **brand-new portfolio** with 0–2 snapshots → synthetic heartbeat appears (fallback works)

- [ ] **Step 4: Commit**

  ```bash
  cd /Users/gregmclaughlin/MicroCapRebuilder
  git add dashboard/src/components/MatrixGrid/EKGStrip.tsx
  git commit -m "feat: EKG strip driven by real portfolio day_pnl_pct data

  Replaces synthetic heartbeat with actual daily P&L history.
  Gain days → green spike, loss days → red dip, big moves glow.
  Falls back to synthetic animation for portfolios with < 3 snapshots.

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Chunk 3: Push

### Task 4: Push to GitHub

- [ ] **Step 1: Push**

  ```bash
  cd /Users/gregmclaughlin/MicroCapRebuilder
  git push
  ```
