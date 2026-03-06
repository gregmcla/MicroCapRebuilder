# PerformanceChart 2045 Visual Upgrades: Chromatic Zones, Glow Hierarchy, Rank Strip

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Three targeted upgrades that make the chart feel like institutional-grade 2045 hardware: a living chromatic background that encodes profit/loss zones, glow intensity that reflects performance rank, and a rank-evolution strip that shows competitive history at a glance.

**Architecture:** All three effects live entirely in `dashboard/src/components/PerformanceChart.tsx`. No new files. Task 1 enhances `drawGrid`. Task 2 modifies `drawLines`. Task 3 adds a new `drawRankStrip` useCallback and a module-level `computeDailyLeaders` helper.

**Tech Stack:** Canvas 2D API, React 19 hooks. No new dependencies.

**Working directory:** `/Users/gregmclaughlin/MicroCapRebuilder/dashboard/`

---

## Context for Implementer

The full file is at `/Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/components/PerformanceChart.tsx`.

Current draw order:
```
drawGrid → drawScars → drawLines → drawEndpoints → drawPulse → drawHover
```

After this plan:
```
drawGrid → drawScars → drawLines → drawRankStrip → drawEndpoints → drawPulse → drawHover
```

**Key module-level constants already in the file:**
```typescript
const PAD_TOP    = 28;
const PAD_RIGHT  = 112;
const PAD_BOTTOM = 24;
const PAD_LEFT   = 40;
```

**Key module-level functions already in the file:**
- `toPixelX(dayIdx, maxLen, chartW)` — converts data index to CSS pixel X
- `computeRunningMax(cum)` — returns running peak array
- `catmullRomPath(ctx, pts)` — draws Catmull-Rom spline

**Key component variables (declared in component body, accessible in all useCallbacks via closure):**
```typescript
const chartW = dims.width  - PAD_LEFT - PAD_RIGHT;
const chartH = dims.height - PAD_TOP  - PAD_BOTTOM;
const maxLen = useMemo(() => Math.max(1, ...series.map((s) => s.cum.length)), [series]);
```

**The `scale` object** (returned by `computeYScale`) has:
- `scale.yMin`, `scale.yMax` — Y axis extremes (padded)
- `scale.toPixelY(pct: number): number` — converts % return to pixel Y
- `scale.guides` — array of nice Y guide values

**`series` array** — sorted by `finalReturn` descending (index 0 = best performer). Each entry:
```typescript
{ id: string; name: string; color: string; cum: number[]; finalReturn: number }
```

**`drawGrid` useCallback** — currently around line 353, deps `[scale, dims]`.

**`drawLines` useCallback** — currently around line 496. The `for (let si = 0; si < series.length; si++)` loop body contains in order: `baseAlpha` computation, echo trails, area fill, three-pass glow.

**`drawScars` useCallback** — currently around line 394, deps `[series, scale, chartW, maxLen]`.

**The main draw useEffect** — currently around line 797. Current call sequence:
```typescript
    drawGrid(ctx);
    drawScars(ctx);
    drawLines(ctx, animProgress, hoverX !== null ? hoveredIdx : null);
    drawEndpoints(ctx, endpointsAlpha);
    drawPulse(ctx);
    if (hoverX !== null && animProgress >= 1) drawHover(ctx, hoverX);
```

---

## Task 1: Chromatic Background Zones + Time Context + NOW Beacon

**What it does:** The chart background becomes a living data layer. When the zero line is visible, the region above zero glows faintly green (profit zone) and below glows faintly red (loss zone). X-axis time markers appear in the bottom padding to orient the viewer. A blurred NOW beacon marks the right edge of the data.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

### Step 1: Add the `daysAgo` module-level helper

Find the `toPixelX` function (around line 118):
```typescript
// ── X scale ──────────────────────────────────────────────────────────────────

function toPixelX(dayIdx: number, maxLen: number, chartW: number): number {
```

Insert the following BEFORE that `// ── X scale` comment block:

```typescript
// ── X-axis time label helper ──────────────────────────────────────────────────

/** Converts a day count into a compact human label: 365+ → "1y", 60+ → "4mo", 14+ → "3w", else "5d" */
function daysAgo(n: number): string {
  if (n >= 365) return Math.round(n / 365) + "y";
  if (n >= 60)  return Math.round(n / 30)  + "mo";
  if (n >= 14)  return Math.round(n / 7)   + "w";
  return n + "d";
}

```

### Step 2: Modify `drawGrid` — add chromatic background zones

Locate the `drawGrid` useCallback. The function body begins with:
```typescript
      // Fill background
      ctx.fillStyle = "#010107";
      ctx.fillRect(0, 0, dims.width, dims.height);

      ctx.save();
```

Insert the following BETWEEN `ctx.fillRect(0, 0, dims.width, dims.height);` and the subsequent `ctx.save();`:

```typescript
      // ── Chromatic background zones (only when zero line is in range) ──────
      if (scale.yMin < 0 && scale.yMax > 0) {
        const zeroY = scale.toPixelY(0);

        // Green zone above zero
        const greenGrad = ctx.createLinearGradient(0, PAD_TOP, 0, zeroY);
        greenGrad.addColorStop(0, "rgba(80,200,120,0.04)");
        greenGrad.addColorStop(1, "rgba(80,200,120,0)");
        ctx.fillStyle = greenGrad;
        ctx.fillRect(PAD_LEFT, PAD_TOP, chartW, zeroY - PAD_TOP);

        // Red zone below zero
        const redGrad = ctx.createLinearGradient(0, zeroY, 0, PAD_TOP + chartH);
        redGrad.addColorStop(0, "rgba(200,60,60,0)");
        redGrad.addColorStop(1, "rgba(200,60,60,0.06)");
        ctx.fillStyle = redGrad;
        ctx.fillRect(PAD_LEFT, zeroY, chartW, PAD_TOP + chartH - zeroY);
      }

```

### Step 3: Modify `drawGrid` — add X-axis time markers and NOW beacon

Locate the end of `drawGrid`. The function ends with:
```typescript
      ctx.restore();
    },
    [scale, dims]
  );
```

The `ctx.restore()` above closes the `ctx.save()` that wraps the guide labels loop. Insert the following AFTER that `ctx.restore();` and BEFORE the closing `},`:

```typescript
      // ── X-axis time markers ───────────────────────────────────────────────
      if (maxLen > 1) {
        const stepSize = Math.max(1, Math.round(maxLen / 5));
        ctx.save();
        ctx.font      = "600 7px/1 monospace";
        ctx.fillStyle = "rgba(255,255,255,0.14)";
        ctx.textAlign = "center";

        for (let d = stepSize; d < maxLen - stepSize / 2; d += stepSize) {
          const tickX = toPixelX(d, maxLen, chartW);

          // 4px tick mark at bottom of chart area
          ctx.beginPath();
          ctx.moveTo(tickX, PAD_TOP + chartH);
          ctx.lineTo(tickX, PAD_TOP + chartH + 4);
          ctx.strokeStyle = "rgba(255,255,255,0.14)";
          ctx.lineWidth   = 1;
          ctx.stroke();

          // Label: how far from NOW this point is ("~4mo", "~1y", etc.)
          ctx.fillText(daysAgo(maxLen - 1 - d), tickX, PAD_TOP + chartH + 12);
        }

        ctx.restore();
      }

      // ── NOW beacon (right edge of data) ──────────────────────────────────
      const nowX = toPixelX(maxLen - 1, maxLen, chartW);

      // Blurred bloom
      ctx.save();
      ctx.globalAlpha = 0.25;
      ctx.filter      = "blur(3px)";
      ctx.beginPath();
      ctx.moveTo(nowX, PAD_TOP);
      ctx.lineTo(nowX, PAD_TOP + chartH);
      ctx.strokeStyle = "rgba(255,255,255,0.5)";
      ctx.lineWidth   = 2;
      ctx.stroke();
      ctx.filter = "none";
      ctx.restore();

      // Hard dashed line
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,0.12)";
      ctx.lineWidth   = 1;
      ctx.setLineDash([3, 4]);
      ctx.beginPath();
      ctx.moveTo(nowX, PAD_TOP);
      ctx.lineTo(nowX, PAD_TOP + chartH);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();

      // "NOW" label
      ctx.save();
      ctx.font         = "700 7px/1 monospace";
      ctx.fillStyle    = "rgba(255,255,255,0.20)";
      ctx.textAlign    = "center";
      ctx.textBaseline = "top";
      ctx.fillText("NOW", nowX, PAD_TOP + 4);
      ctx.restore();
```

### Step 4: Update `drawGrid` dependency array

Change the current dep array `[scale, dims]` to:

```typescript
    [scale, dims, chartW, chartH, maxLen]
```

### Step 5: Verify build

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -15
```

Expected: zero TypeScript errors, clean build.

### Step 6: Visual check

Open http://localhost:5173 → Overview → CHART. Expected:
- Faint green wash above zero line, faint red wash below (only visible when zero is in Y range)
- X-axis time labels in bottom gutter ("3mo", "6mo", "1y" etc.) with 4px tick marks
- A vertical dashed line at the right edge of the data, labeled "NOW" at the top with a soft bloom behind it

### Step 7: Commit

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/PerformanceChart.tsx && git commit -m "feat: add chromatic background zones, X-axis time markers, NOW beacon"
```

---

## Task 2: Performance-Ranked Glow Hierarchy

**What it does:** `series` is already sorted by `finalReturn` descending — index 0 is the best performer. This task uses that rank to modulate each line's glow intensity and core line width. The top performer glows at full power; each lower rank loses glow (down to 50% for last). The winner visually dominates.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

### Step 1: Add rank factor computation inside `drawLines`

Locate `drawLines`. Inside the `for (let si = 0; si < series.length; si++)` loop, find the existing `baseAlpha` line:

```typescript
        // Dimming: if something is hovered and this isn't it, reduce alpha
        const baseAlpha = hoveredIdx !== null && hoveredIdx !== si ? 0.35 : 1.0;
```

Insert the following IMMEDIATELY AFTER that line:

```typescript
        // ── Performance rank modulates glow ──────────────────────────────────
        // si=0 = best performer (series is sorted by finalReturn desc).
        // rankFactor: 1.0 for best, tapering to 0.50 for last.
        const rankN         = series.length;
        const rankFactor    = rankN <= 1 ? 1.0 : 1.0 - (si / (rankN - 1)) * 0.50;
        const glowAlpha     = baseAlpha * rankFactor;
        // Core line width tapers slightly by rank: 1.5px best → 1.0px worst
        const coreLineWidth = rankN <= 1 ? 1.5 : 1.5 - (si / (rankN - 1)) * 0.5;
```

### Step 2: Replace `baseAlpha` with `glowAlpha` in five places

All replacements are inside the same loop body (`for si`). Apply in order:

**Echo trails block** — find:
```typescript
          ctx.globalAlpha = baseAlpha * echo.opacity;
```
Replace with:
```typescript
          ctx.globalAlpha = glowAlpha * echo.opacity;
```

**Area fill block** — find:
```typescript
        ctx.globalAlpha = baseAlpha * 0.04;
```
Replace with:
```typescript
        ctx.globalAlpha = glowAlpha * 0.04;
```

**Pass 1 — wide blurred halo** — find:
```typescript
        ctx.globalAlpha = baseAlpha * 0.15;
```
Replace with:
```typescript
        ctx.globalAlpha = glowAlpha * 0.15;
```

**Pass 2 — inner glow** — find:
```typescript
        ctx.globalAlpha = baseAlpha * 0.40;
```
Replace with:
```typescript
        ctx.globalAlpha = glowAlpha * 0.40;
```

**Pass 3 — crisp core** — find:
```typescript
        ctx.globalAlpha = baseAlpha * 1.0;
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 1.5;
```
Replace with:
```typescript
        ctx.globalAlpha = glowAlpha * 1.0;
        ctx.strokeStyle = s.color;
        ctx.lineWidth   = coreLineWidth;
```

Note: `baseAlpha` itself is kept — it still controls hover dimming (0.35 vs 1.0). `rankFactor` multiplies on top of whatever `baseAlpha` resolved to, so hover dimming still works correctly.

### Step 3: Verify build

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -15
```

Expected: zero TypeScript errors, no unused variable warnings (both `baseAlpha` and `glowAlpha` are used).

### Step 4: Visual check

Expected:
- Best performer: full glow (1.0), 1.5px crisp core, strong echo trails
- Second performer: slightly dimmer glow (~0.83), ~1.25px core
- Worst performer: half glow (0.50), 1.0px core — visible but visually recedes
- Hover dimming still works correctly on all lines
- Single-series chart: unchanged (rankFactor = 1.0)

### Step 5: Commit

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/PerformanceChart.tsx && git commit -m "feat: modulate glow intensity by performance rank"
```

---

## Task 3: Rank Evolution Heat Strip

**What it does:** A 7px chromatic strip sits inside the bottom padding zone, just below the chart area. Each pixel column is colored with the palette color of whichever portfolio was leading on that day. Stretches of one color = one portfolio dominated that period. Rapid color changes = close competition. A "RANK" label sits in the left gutter.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

### Step 1: Add `computeDailyLeaders` module-level helper

Find `computeRunningMax` (around line 105):
```typescript
function computeRunningMax(cum: number[]): number[] {
  if (cum.length === 0) return [];
  ...
}
```

Insert the following IMMEDIATELY AFTER the closing `}` of `computeRunningMax`:

```typescript
/** For each day index, returns the series index (si) with the highest cum return, or -1 if no series has data that far. */
function computeDailyLeaders(seriesArr: SeriesData[], numDays: number): Int8Array {
  const leaders = new Int8Array(numDays).fill(-1);
  for (let d = 0; d < numDays; d++) {
    let bestSi  = -1;
    let bestVal = -Infinity;
    for (let si = 0; si < seriesArr.length; si++) {
      if (d < seriesArr[si].cum.length && seriesArr[si].cum[d] > bestVal) {
        bestVal = seriesArr[si].cum[d];
        bestSi  = si;
      }
    }
    leaders[d] = bestSi;
  }
  return leaders;
}

```

Note: `SeriesData` is a module-level interface, so this function can reference it by name.

### Step 2: Add `drawRankStrip` useCallback inside the component

Locate the end of `drawScars` useCallback:
```typescript
    [series, scale, chartW, maxLen],
  );
```

Insert `drawRankStrip` immediately after:

```typescript
  const drawRankStrip = useCallback(
    (ctx: CanvasRenderingContext2D) => {
      if (series.length < 2) return; // strip not meaningful with one series
      const leaders = computeDailyLeaders(series, maxLen);
      const stripY  = dims.height - PAD_BOTTOM + 3; // just inside bottom padding zone
      const stripH  = 7;
      const colW    = chartW / maxLen;

      // Background track — faint defined boundary
      ctx.save();
      ctx.fillStyle = "rgba(255,255,255,0.03)";
      ctx.fillRect(PAD_LEFT, stripY, chartW, stripH);

      // Color columns: one per day
      for (let d = 0; d < maxLen; d++) {
        const si = leaders[d];
        if (si < 0) continue;
        ctx.globalAlpha = 0.60;
        ctx.fillStyle   = series[si].color;
        // Math.max(1, colW) prevents sub-pixel gaps at high data density
        ctx.fillRect(PAD_LEFT + (d / maxLen) * chartW, stripY, Math.max(1, colW), stripH);
      }
      ctx.restore();

      // "RANK" label in left gutter
      ctx.save();
      ctx.font          = "600 6px/1 monospace";
      ctx.fillStyle     = "rgba(255,255,255,0.15)";
      ctx.textAlign     = "right";
      ctx.textBaseline  = "middle";
      ctx.fillText("RANK", PAD_LEFT - 6, stripY + stripH / 2);
      ctx.restore();
    },
    [series, dims, chartW, maxLen],
  );
```

### Step 3: Update the draw useEffect to call `drawRankStrip`

Locate the main draw useEffect (around line 797). Replace the entire useEffect with:

```typescript
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || dims.width === 0) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, dims.width, dims.height);
    drawGrid(ctx);
    drawScars(ctx);
    drawLines(ctx, animProgress, hoverX !== null ? hoveredIdx : null);
    drawRankStrip(ctx);
    drawEndpoints(ctx, endpointsAlpha);
    drawPulse(ctx);
    if (hoverX !== null && animProgress >= 1) drawHover(ctx, hoverX);
  }, [drawGrid, drawScars, drawLines, drawRankStrip, drawEndpoints, drawPulse, drawHover, dims, animProgress, endpointsAlpha, hoverX, hoveredIdx, pulseTick]);
```

### Step 4: Verify build

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -15
```

Expected: zero TypeScript errors. `Int8Array` is a standard browser global — no import needed.

### Step 5: Visual check

Expected:
- A 7px chromatic strip appears just below the chart lines, above the bottom edge
- Each day column is filled with the leading portfolio's color at 60% opacity
- Long single-color runs: one portfolio dominated for that stretch
- Rapid color changes: close competition
- "RANK" label in left gutter, vertically centered on the strip, barely legible
- Single-portfolio chart: strip not rendered

### Step 6: Commit and push

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/PerformanceChart.tsx && git commit -m "feat: add rank evolution heat strip to PerformanceChart" && git push
```
