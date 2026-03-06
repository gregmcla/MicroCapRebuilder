# PerformanceChart Visual Effects: Temporal Echoes, Drawdown Scars, ECG Pulse

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add three cinematic effects to PerformanceChart — temporal echo trails giving each line physical depth and mass, crimson drawdown scars filling the wound between a peak and its recovery, and ECG pulse animations that travel each line like a heartbeat.

**Architecture:** All three effects live entirely in `dashboard/src/components/PerformanceChart.tsx`. No new files. Temporal echoes are baked into the existing `drawLines` useCallback. Drawdown scars are a new `drawScars` useCallback rendered before lines. ECG pulse is a new dedicated RAF loop + `drawPulse` useCallback rendered last (on top of everything including hover).

**Tech Stack:** Canvas 2D API, React 19 hooks. No new dependencies.

**Working directory:** `/Users/gregmclaughlin/MicroCapRebuilder/dashboard/`

---

## Context for Implementer

The chart is a Canvas 2D component with this draw order (current):
```
drawGrid → drawLines → drawEndpoints → drawHover
```

After this plan, draw order becomes:
```
drawGrid → drawScars → drawLines → drawEndpoints → drawPulse → drawHover
```

The main draw effect (useEffect) fires whenever its deps change. The pulse system triggers redraws at 60fps by calling `setPulseTick(n => n + 1)` from a RAF loop whenever any pulse is actively animating. Between firings, the RAF loop runs but does NOT increment pulseTick, so no unnecessary redraws occur.

**Key constants already in the file (module-level):**
```typescript
const PAD_TOP    = 28;
const PAD_RIGHT  = 112;
const PAD_BOTTOM = 24;
const PAD_LEFT   = 40;
```

**Key module-level functions already in the file:**
- `toPixelX(dayIdx, maxLen, chartW)` — converts data index to CSS pixel X
- `interpolateAtX(cum, pixelX, maxLen, chartW)` — interpolates % return at pixel X
- `catmullRomPath(ctx, pts)` — draws smooth spline through points

---

## Task 1: Temporal Echo Trails

**What it does:** Each glowing line gains 3 ghost copies drawn before it — same path, progressively less data, decreasing opacity, increasing blur. During the mount animation, echoes lag behind the main line's leading edge. After animation, they permanently trail behind (stopping 6%, 12%, 20% short of the main line's tip), creating a "wake" that shows the line has mass and momentum.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

**Step 1: Add echo rendering inside `drawLines`**

Locate `drawLines` in `PerformanceChart.tsx` (around line 363). Inside the `for (let si = 0; ...)` loop, find this comment:
```typescript
        // ── Area fill (draw first, source-over, below the glowing lines) ─────
```

Insert the following BEFORE that comment (after `const baseAlpha = ...`):

```typescript
        // ── Temporal echo trails (drawn before area fill, furthest back) ──────
        const ECHO_DEFS = [
          { offset: 0.06, opacity: 0.28, blur: "1px",   width: 2.5 },
          { offset: 0.12, opacity: 0.14, blur: "2px",   width: 3.5 },
          { offset: 0.20, opacity: 0.06, blur: "3.5px", width: 5.5 },
        ] as const;

        for (const echo of ECHO_DEFS) {
          const echoProgress = Math.max(0, progress - echo.offset);
          if (echoProgress <= 0) continue;
          // Slice pts to echo's progress position — shorter line = lags behind main
          const echoMaxDataIdx = Math.min(
            Math.floor(echoProgress * (maxLen - 1)),
            s.cum.length - 1,
          );
          const echoPts = pts.slice(0, echoMaxDataIdx + 1);
          if (echoPts.length < 2) continue;

          ctx.save();
          ctx.globalCompositeOperation = "screen";
          ctx.globalAlpha = baseAlpha * echo.opacity;
          ctx.filter = `blur(${echo.blur})`;
          ctx.strokeStyle = s.color;
          ctx.lineWidth = echo.width;
          ctx.lineJoin = "round";
          ctx.lineCap  = "round";
          ctx.beginPath();
          catmullRomPath(ctx, echoPts);
          ctx.stroke();
          ctx.restore();
        }
```

**Step 2: Verify build**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -10
```
Expected: zero TypeScript errors, clean build.

**Step 3: Visual check**

Open http://localhost:5173 → Overview → CHART. Expected:
- During mount animation: each line has 3 trailing ghost copies lagging behind
- After animation: each line has a permanent blurred wake that ends before its tip
- The wake is subtle — visible as depth, not as separate lines
- Dimming on hover: echoes dim with the main line (baseAlpha applies)

**Step 4: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/PerformanceChart.tsx
git commit -m "feat: add temporal echo trails to PerformanceChart lines"
```

---

## Task 2: Drawdown Scars

**What it does:** For each portfolio, finds periods where the cumulative return fell more than 3% below its prior peak. Fills those regions with a deep crimson polygon between the "running maximum" line (where it peaked) and the actual return line (where it actually is). Opacity scales with drawdown depth — a 3% dip is barely a whisper; a 25% crash is a visible wound.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

**Step 1: Add `computeRunningMax` helper above the component**

Find this comment near line 92:
```typescript
// ── X scale ──────────────────────────────────────────────────────────────────
```

Insert BEFORE it:

```typescript
// ── Drawdown scar helpers ─────────────────────────────────────────────────────

/** Returns running maximum of cum — runMax[i] = max(cum[0..i]). */
function computeRunningMax(cum: number[]): number[] {
  const result: number[] = [];
  let rmax = cum[0];
  for (const v of cum) {
    if (v > rmax) rmax = v;
    result.push(rmax);
  }
  return result;
}
```

**Step 2: Add `drawScars` useCallback inside the component**

Place this after the `drawGrid` useCallback (and before `drawEndpoints`):

```typescript
  const drawScars = useCallback(
    (ctx: CanvasRenderingContext2D) => {
      const { toPixelY } = scale;
      const DD_THRESHOLD = 3.0; // minimum drawdown % to show a scar

      for (const s of series) {
        if (s.cum.length < 4) continue;
        const runMax = computeRunningMax(s.cum);

        let i = 0;
        while (i < s.cum.length) {
          const dd = runMax[i] - s.cum[i];
          if (dd <= DD_THRESHOLD) { i++; continue; }

          // Scar segment starts here
          const segStart = i;
          let maxDd = dd;
          while (i < s.cum.length && runMax[i] - s.cum[i] > DD_THRESHOLD) {
            maxDd = Math.max(maxDd, runMax[i] - s.cum[i]);
            i++;
          }
          const segEnd = i - 1;
          if (segEnd <= segStart) continue;

          // Opacity: sqrt scaling so shallow scars are subtle, deep scars visible
          // 3% dd → ~0.05 opacity, 15% → ~0.14, 40% → ~0.22 (capped)
          const opacity = Math.min(Math.sqrt(maxDd / 40) * 0.9, 0.22);

          // Build polygon: peak line top-edge → actual line bottom-edge (reversed)
          ctx.save();
          ctx.globalCompositeOperation = "source-over";
          ctx.globalAlpha = opacity;
          ctx.fillStyle = "rgb(190, 35, 55)";
          ctx.beginPath();
          ctx.moveTo(toPixelX(segStart, maxLen, chartW), toPixelY(runMax[segStart]));
          for (let j = segStart + 1; j <= segEnd; j++) {
            ctx.lineTo(toPixelX(j, maxLen, chartW), toPixelY(runMax[j]));
          }
          for (let j = segEnd; j >= segStart; j--) {
            ctx.lineTo(toPixelX(j, maxLen, chartW), toPixelY(s.cum[j]));
          }
          ctx.closePath();
          ctx.fill();
          ctx.restore();
        }
      }
    },
    [series, scale, chartW, maxLen],
  );
```

**Step 3: Update the draw effect to call `drawScars` between `drawGrid` and `drawLines`**

Find the draw useEffect (around line 579):
```typescript
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || dims.width === 0) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, dims.width, dims.height);
    drawGrid(ctx);
    drawLines(ctx, animProgress, hoverX !== null ? hoveredIdx : null);
    drawEndpoints(ctx, endpointsAlpha);
    if (hoverX !== null && animProgress >= 1) drawHover(ctx, hoverX);
  }, [drawGrid, drawLines, drawEndpoints, drawHover, dims, animProgress, endpointsAlpha, hoverX, hoveredIdx]);
```

Replace it with:
```typescript
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || dims.width === 0) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, dims.width, dims.height);
    drawGrid(ctx);
    drawScars(ctx);
    drawLines(ctx, animProgress, hoverX !== null ? hoveredIdx : null);
    drawEndpoints(ctx, endpointsAlpha);
    if (hoverX !== null && animProgress >= 1) drawHover(ctx, hoverX);
  }, [drawGrid, drawScars, drawLines, drawEndpoints, drawHover, dims, animProgress, endpointsAlpha, hoverX, hoveredIdx]);
```

**Step 4: Verify build**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -10
```
Expected: zero errors.

**Step 5: Visual check**

Open CHART view. Expected:
- Portfolios with meaningful drawdowns (>3%) show a faint crimson fill between the peak line and the trough
- Shallow dips: barely perceptible tint
- Deep drawdowns: visible dark red wound
- Lines and glow render on top of scars — scars are behind everything
- Portfolios with no significant drawdown show no scar at all

**Step 6: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/PerformanceChart.tsx
git commit -m "feat: add crimson drawdown scars to PerformanceChart"
```

---

## Task 3: ECG Pulse

**What it does:** After the mount animation completes, each portfolio line fires a glowing ball that travels from the endpoint back to the origin over 1.8s. The ball has a white-hot core, a colored mid-glow, and a soft outer bloom — like a signal being transmitted backward through the portfolio's history. Each series fires at a different interval (4–6s range), staggered so they don't all pulse simultaneously. Between pulses, the chart is silent.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

**Step 1: Add `PULSE_DURATION_MS` module-level constant**

At the top of the file, after the `PAD_*` constants (around line 17–20), add:

```typescript
const PULSE_DURATION_MS = 1800; // ms for one pulse to travel endpoint → origin
```

**Step 2: Add pulse state types, refs, and state inside the component**

After the existing animation state (after `endStartRef` declaration, around line 195), add:

```typescript
  // ── ECG pulse state ───────────────────────────────────────────────────────
  interface PulseState {
    active:    boolean;
    startTime: number; // performance.now() when pulse started
    nextFire:  number; // performance.now() when next pulse fires
    interval:  number; // ms between pulses
  }
  const pulseStatesRef = useRef<PulseState[]>([]);
  const pulseRafRef    = useRef<number | null>(null);
  const [pulseTick, setPulseTick] = useState(0); // incremented to trigger redraws
```

Note: TypeScript interfaces defined inside a component are valid and don't cause re-renders.

**Step 3: Add the pulse RAF loop useEffect**

Place this after the existing animation RAF loop `useEffect` (after the one with `[series.length]` dep):

```typescript
  // ECG pulse RAF loop — fires independently of mount animation
  useEffect(() => {
    // Initialize per-series pulse state, staggered to avoid simultaneous firings.
    // Wait for mount animation (1.2s) + endpoint fade (0.3s) + buffer (0.5s) before first pulse.
    const now = performance.now();
    pulseStatesRef.current = series.map((s, i) => ({
      active:    false,
      startTime: 0,
      // Stagger first fires: 2s, 2.7s, 3.4s, ... after mount
      nextFire:  now + 2000 + i * 700,
      // Derive interval from data so it's deterministic — each portfolio has its own rhythm
      interval:  4000 + i * 500 + (Math.abs(Math.round(s.finalReturn * 97)) % 900),
    }));

    function tick(now: number) {
      let needRedraw = false;

      for (const ps of pulseStatesRef.current) {
        if (!ps.active && now >= ps.nextFire) {
          ps.active    = true;
          ps.startTime = now;
          needRedraw   = true;
        }
        if (ps.active) {
          const elapsed = now - ps.startTime;
          if (elapsed >= PULSE_DURATION_MS) {
            ps.active    = false;
            ps.nextFire  = now + ps.interval;
          }
          needRedraw = true;
        }
      }

      if (needRedraw) setPulseTick((n) => n + 1);
      pulseRafRef.current = requestAnimationFrame(tick);
    }

    pulseRafRef.current = requestAnimationFrame(tick);
    return () => {
      if (pulseRafRef.current !== null) cancelAnimationFrame(pulseRafRef.current);
    };
  }, [series.length]); // restart when portfolio count changes
```

**Step 4: Add `drawPulse` useCallback**

Place this after the `drawHover` useCallback:

```typescript
  const drawPulse = useCallback(
    (ctx: CanvasRenderingContext2D) => {
      const { toPixelY } = scale;
      const states = pulseStatesRef.current;
      const now    = performance.now();

      for (let si = 0; si < series.length; si++) {
        const ps = states[si];
        if (!ps?.active) continue;

        const s       = series[si];
        const elapsed = now - ps.startTime;
        const pulseT  = Math.min(elapsed / PULSE_DURATION_MS, 1);

        // Bell curve alpha: fades in, peaks at midpoint, fades out
        const pulseAlpha = Math.sin(pulseT * Math.PI);

        // Position: moves from endpoint (pulseT=0) to origin (pulseT=1) along the line
        const dataFrac   = (1 - pulseT) * (s.cum.length - 1);
        const dataIdx    = Math.round(dataFrac);
        const pxX        = toPixelX(dataFrac, maxLen, chartW);
        const pxY        = toPixelY(s.cum[Math.min(dataIdx, s.cum.length - 1)]);

        // Outer bloom — large, soft
        ctx.save();
        ctx.globalAlpha = pulseAlpha * 0.40;
        ctx.filter      = "blur(7px)";
        ctx.beginPath();
        ctx.arc(pxX, pxY, 10, 0, Math.PI * 2);
        ctx.fillStyle = s.color;
        ctx.fill();
        ctx.restore();

        // Mid glow — tighter, portfolio color
        ctx.save();
        ctx.globalAlpha = pulseAlpha * 0.75;
        ctx.filter      = "blur(2px)";
        ctx.beginPath();
        ctx.arc(pxX, pxY, 5, 0, Math.PI * 2);
        ctx.fillStyle = s.color;
        ctx.fill();
        ctx.restore();

        // White-hot core — no blur, pure white, small
        ctx.save();
        ctx.globalAlpha = pulseAlpha * 0.95;
        ctx.beginPath();
        ctx.arc(pxX, pxY, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
        ctx.restore();
      }
    },
    [series, scale, chartW, maxLen],
  );
```

**Step 5: Update the draw effect to call `drawPulse` and depend on `pulseTick`**

Replace the current draw effect with:

```typescript
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || dims.width === 0) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, dims.width, dims.height);
    drawGrid(ctx);
    drawScars(ctx);
    drawLines(ctx, animProgress, hoverX !== null ? hoveredIdx : null);
    drawEndpoints(ctx, endpointsAlpha);
    drawPulse(ctx);
    if (hoverX !== null && animProgress >= 1) drawHover(ctx, hoverX);
  }, [drawGrid, drawScars, drawLines, drawEndpoints, drawPulse, drawHover, dims, animProgress, endpointsAlpha, hoverX, hoveredIdx, pulseTick]);
```

The `pulseTick` dep is the trigger: the pulse RAF loop increments it whenever any pulse is active, which causes the draw effect to fire and re-render the pulse position. Between pulse firings, `pulseTick` is not incremented, so the canvas is not redrawn at 60fps for nothing.

**Step 6: Verify build**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -10
```
Expected: zero errors.

**Step 7: Visual check**

Open CHART view. Wait ~2s after the mount animation completes. Expected:
- A glowing ball fires from the MICROCAP endpoint and travels left toward origin over ~1.8s
- The ball has a white-hot center surrounded by a teal bloom
- Other portfolios fire at staggered intervals (~4-6s each, offset from each other)
- The ball fades in smoothly, peaks at midpoint, fades out as it reaches origin
- Between firings, chart is completely static (no 60fps waste)
- Pulses render on top of hover scan line and tooltip

**Step 8: Commit and push**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/PerformanceChart.tsx
git commit -m "feat: add ECG pulse animation to PerformanceChart"
git push
```
