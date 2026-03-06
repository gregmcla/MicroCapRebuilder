# PerformanceChart Intensity Upgrade: Glow Overhaul, Vignette, Dual-Zone Y-Scale

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Three upgrades that make the chart feel genuinely cinematic: a glow intensity overhaul that makes lines radiate rather than whisper, a vignette that burns in from the edges, and a dual-zone Y-scale that splits the chart so the leader gets its own space and the compressed field portfolios finally have room to breathe.

**Architecture:** All changes are in `dashboard/src/components/PerformanceChart.tsx`. Task 1 changes constants and opacity values only. Task 2 adds a CSS div to the JSX. Task 3 is the most invasive — adds dual-scale computation, modifies `computeYScale`, and updates every drawing callback to route to the correct zone scale.

**Tech Stack:** Canvas 2D API, React 19 hooks. No new dependencies.

**Working directory:** `/Users/gregmclaughlin/MicroCapRebuilder/dashboard/`

---

## Context for Implementer

The full file is at `/Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/components/PerformanceChart.tsx`.

Current draw order:
```
drawGrid → drawScars → drawLines → drawRankStrip → drawEndpoints → drawPulse → drawHover
```

**Key module-level constants:**
```typescript
const PAD_TOP = 28; const PAD_RIGHT = 112; const PAD_BOTTOM = 24; const PAD_LEFT = 40;
```

**Key component variables (closure-accessible in all useCallbacks):**
```typescript
const chartW = dims.width  - PAD_LEFT - PAD_RIGHT;
const chartH = dims.height - PAD_TOP  - PAD_BOTTOM;
const maxLen = useMemo(() => Math.max(1, ...series.map((s) => s.cum.length)), [series]);
```

**`series` array** — sorted by `finalReturn` descending (index 0 = best performer).

---

## Task 1: Visual Intensity Overhaul

**What it does:** Multiplies all glow/fill/effect opacities by ~2.5-3x so lines actually radiate. Boosts echo trails. Makes chromatic zones visible. Enlarges rank strip.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

### Step 1: Update ECHO_DEFS module-level constant

Find:
```typescript
const ECHO_DEFS = [
  { offset: 0.06, opacity: 0.28, blur: "1px",   width: 2.5 },
  { offset: 0.12, opacity: 0.14, blur: "2px",   width: 3.5 },
  { offset: 0.20, opacity: 0.06, blur: "3.5px", width: 5.5 },
] as const;
```

Replace with:
```typescript
const ECHO_DEFS = [
  { offset: 0.06, opacity: 0.40, blur: "2px", width: 3.5 },
  { offset: 0.12, opacity: 0.25, blur: "3px", width: 5.0 },
  { offset: 0.20, opacity: 0.12, blur: "5px", width: 8.0 },
] as const;
```

### Step 2: Update glow passes in drawLines

In the `drawLines` useCallback, make 3 targeted replacements inside the glow passes:

**Area fill** — find:
```typescript
        ctx.globalAlpha = glowAlpha * 0.04;
```
Replace with:
```typescript
        ctx.globalAlpha = glowAlpha * 0.14;
```

**Pass 1 (wide blurred halo)** — find these 4 lines together:
```typescript
        ctx.filter = "blur(2px)";
        ctx.globalAlpha = glowAlpha * 0.15;
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 10;
```
Replace with:
```typescript
        ctx.filter = "blur(7px)";
        ctx.globalAlpha = glowAlpha * 0.30;
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 14;
```

**Pass 2 (inner glow)** — find:
```typescript
        ctx.globalAlpha = glowAlpha * 0.40;
```
Replace with:
```typescript
        ctx.globalAlpha = glowAlpha * 0.65;
```

### Step 3: Update chromatic zone opacities in drawGrid

Find:
```typescript
        greenGrad.addColorStop(0, "rgba(80,200,120,0.04)");
```
Replace with:
```typescript
        greenGrad.addColorStop(0, "rgba(80,200,120,0.12)");
```

Find:
```typescript
        redGrad.addColorStop(1, "rgba(200,60,60,0.06)");
```
Replace with:
```typescript
        redGrad.addColorStop(1, "rgba(200,60,60,0.15)");
```

### Step 4: Update rank strip dimensions in drawRankStrip

Find:
```typescript
      const stripH  = 14;
```
Note: it may already be 14 from a prior session. If it is 7, change to 14. If already 14, skip this step.

Find:
```typescript
        ctx.globalAlpha = 0.60;
```
Replace with:
```typescript
        ctx.globalAlpha = 0.85;
```

### Step 5: Verify build

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -15
```
Expected: zero TypeScript errors.

### Step 6: Commit

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/PerformanceChart.tsx && git commit -m "feat: crank visual intensity - glow overhaul, bright zones, thick rank strip"
```

---

## Task 2: Vignette Overlay

**What it does:** Adds a radial dark gradient burning in from the corners over the canvas. Creates depth and cinematic focus. Pure CSS div, zero canvas impact.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

### Step 1: Add vignette div to JSX

In the JSX return of PerformanceChart, there is already a scanline `<div>` with `zIndex: 1`. The structure looks like:
```tsx
    <div ref={containerRef} style={{ ... }}>
      {/* Scanline texture overlay */}
      <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient...", zIndex: 1 }} />
      <canvas ... />
    </div>
```

Add a NEW div BETWEEN the scanline div and the `<canvas>` element:

```tsx
      {/* Vignette overlay — radial burn from corners */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "radial-gradient(ellipse at 50% 50%, transparent 30%, rgba(0,0,0,0.60) 100%)",
          pointerEvents: "none",
          zIndex: 2,
        }}
      />
```

### Step 2: Verify build

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -15
```

### Step 3: Commit

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/PerformanceChart.tsx && git commit -m "feat: add vignette overlay to PerformanceChart"
```

---

## Task 3: Dual-Zone Y-Scale

**What it does:** When the top performer's return is more than 3x the second place AND at least 5% ahead, the chart splits: the top 50% of vertical space shows only the leader with its own scale, the bottom 50% shows all field portfolios with a tighter scale that gives them room to show detail. A subtle separator line divides the zones. When no outlier is detected, the chart falls back to the current single-scale behavior unchanged.

**Files:**
- Modify: `dashboard/src/components/PerformanceChart.tsx`

### Step 1: Modify `computeYScale` to accept a `zoneTop` parameter

Find the current function signature and `toPixelY` line:
```typescript
function computeYScale(allCums: number[][], chartH: number): YScale {
```
Replace with:
```typescript
function computeYScale(allCums: number[][], zoneH: number, zoneTop: number = PAD_TOP): YScale {
```

Find (inside the function body):
```typescript
  const toPixelY = (pct: number): number =>
    PAD_TOP + ((yMax - pct) / (yMax - yMin)) * chartH;
```
Replace with:
```typescript
  const toPixelY = (pct: number): number =>
    zoneTop + ((yMax - pct) / (yMax - yMin)) * zoneH;
```

Verify: `chartH` should NOT appear anywhere else in `computeYScale` after these replacements. Search the function body to confirm.

### Step 2: Add leaderIdx, zone geometry, and dual-scale computation in component body

Find the existing `scale` useMemo (and the `const { toPixelY } = scale;` destructure that may appear right before `const maxLen`):
```typescript
  const scale = useMemo(
    () => computeYScale(series.map((s) => s.cum), chartH),
    [series, chartH]
  );
```

Replace the ENTIRE `scale` useMemo with these 5 declarations:

```typescript
  // ── Dual-zone Y-scale ────────────────────────────────────────────────────
  // Detect outlier: split when leader's return > 3x second place AND > 5%
  const leaderIdx = useMemo(() => {
    if (series.length < 2) return -1;
    const top    = series[0].finalReturn;
    const second = series[1].finalReturn;
    if (top > 5.0 && top > second * 3.0) return 0;
    return -1;
  }, [series]);

  const leaderZoneH = leaderIdx >= 0 ? Math.floor(chartH * 0.50) : chartH;
  const fieldZoneH  = leaderIdx >= 0 ? chartH - leaderZoneH       : chartH;
  const separatorY  = leaderIdx >= 0 ? PAD_TOP + leaderZoneH      : -1;

  // Leader scale: covers only the leader series (or all series when no split)
  const scale = useMemo(
    () => computeYScale(
      leaderIdx >= 0 ? [series[leaderIdx].cum] : series.map((s) => s.cum),
      leaderZoneH,
      PAD_TOP,
    ),
    [series, leaderIdx, leaderZoneH],
  );

  // Field scale: covers all non-leader series in the bottom zone (same as scale when no split)
  const fieldScale = useMemo(
    () => leaderIdx >= 0
      ? computeYScale(
          series.filter((_, i) => i !== leaderIdx).map((s) => s.cum),
          fieldZoneH,
          PAD_TOP + leaderZoneH,
        )
      : scale,
    [series, leaderIdx, leaderZoneH, fieldZoneH, scale],
  );
```

### Step 3: Update `drawGrid` to render both zone guides + separator

**Replace** the destructuring at the top of `drawGrid`:
```typescript
      const { toPixelY, guides } = scale;
```
With:
```typescript
      const { toPixelY: leaderPixelY, guides: leaderGuides } = scale;
      const { toPixelY: fieldPixelY,  guides: fieldGuides  } = fieldScale;
```

**Replace** the entire `for (const g of guides)` loop body with two loops plus separator. The new content (inside the existing `ctx.save()` / `ctx.restore()` block) is:

```typescript
      // Leader zone guides
      for (const g of leaderGuides) {
        const py     = leaderPixelY(g);
        const isZero = g === 0;
        ctx.beginPath();
        ctx.moveTo(PAD_LEFT - 6, py);
        ctx.lineTo(dims.width - PAD_RIGHT + 8, py);
        ctx.strokeStyle = isZero ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.05)";
        ctx.lineWidth = 1;
        ctx.stroke();
        const decimals = Math.abs(g) < 1 ? 1 : 0;
        const label = g === 0 ? "0%" : `${g > 0 ? "+" : ""}${g.toFixed(decimals)}%`;
        ctx.fillStyle = isZero ? "rgba(255,255,255,0.28)" : "rgba(255,255,255,0.18)";
        ctx.fillText(label, PAD_LEFT - 8, py);
      }

      // Zone separator (only when split)
      if (separatorY > 0) {
        // Glow bloom
        ctx.save();
        ctx.globalAlpha = 0.35;
        ctx.filter      = "blur(3px)";
        ctx.beginPath();
        ctx.moveTo(PAD_LEFT, separatorY);
        ctx.lineTo(dims.width - PAD_RIGHT, separatorY);
        ctx.strokeStyle = "rgba(255,255,255,0.40)";
        ctx.lineWidth   = 1;
        ctx.stroke();
        ctx.filter = "none";
        ctx.restore();
        // Hard line
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(PAD_LEFT, separatorY);
        ctx.lineTo(dims.width - PAD_RIGHT, separatorY);
        ctx.strokeStyle = "rgba(255,255,255,0.18)";
        ctx.lineWidth   = 1;
        ctx.setLineDash([5, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
      }

      // Field zone guides (only when split)
      if (separatorY > 0) {
        for (const g of fieldGuides) {
          const py     = fieldPixelY(g);
          const isZero = g === 0;
          ctx.beginPath();
          ctx.moveTo(PAD_LEFT - 6, py);
          ctx.lineTo(dims.width - PAD_RIGHT + 8, py);
          ctx.strokeStyle = isZero ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.05)";
          ctx.lineWidth = 1;
          ctx.stroke();
          const decimals = Math.abs(g) < 1 ? 1 : 0;
          const label = g === 0 ? "0%" : `${g > 0 ? "+" : ""}${g.toFixed(decimals)}%`;
          ctx.fillStyle = isZero ? "rgba(255,255,255,0.28)" : "rgba(255,255,255,0.18)";
          ctx.fillText(label, PAD_LEFT - 8, py);
        }
      }
```

**Update drawGrid dep array** — add `fieldScale`, `separatorY`:
```typescript
    [scale, dims, chartW, chartH, maxLen, fieldScale, separatorY]
```

### Step 4: Update `drawScars` to use per-series scale

Replace the `for (const s of series)` loop header with an indexed loop:
```typescript
      for (let si = 0; si < series.length; si++) {
        const s = series[si];
        const { toPixelY } = (leaderIdx >= 0 && si !== leaderIdx) ? fieldScale : scale;
        if (s.cum.length < 4) continue;
```

The rest of the drawScars body is unchanged — it already uses `toPixelY` from the destructure above.

**Update drawScars dep array** — add `fieldScale`, `leaderIdx`:
```typescript
    [series, scale, fieldScale, leaderIdx, chartW, maxLen],
```

### Step 5: Update `drawLines` to use per-series scale and per-series clip

In `drawLines`, the current code has an outer `ctx.save()` + clip before the loop:
```typescript
      ctx.save();
      // Clip to animated reveal region
      ctx.beginPath();
      ctx.rect(0, PAD_TOP, clipX, chartH);
      ctx.clip();

      for (let si = 0; si < series.length; si++) {
        const s = series[si];
        const pts: [number, number][] = s.cum.map((v, i) => [
          toPixelX(i, maxLen, chartW),
          toPixelY(v),
        ]);
```

And a `ctx.restore() // remove clip` AFTER the loop (before the closing `},`).

**Remove** the outer `ctx.save()` + clip block entirely (the `ctx.save()`, `ctx.beginPath()`, `ctx.rect(...)`, `ctx.clip()` lines before the for loop).

**Remove** the outer `ctx.restore(); // remove clip` line after the loop.

**Replace** the loop opening and first few lines with:
```typescript
      for (let si = 0; si < series.length; si++) {
        const s = series[si];
        const { toPixelY } = (leaderIdx >= 0 && si !== leaderIdx) ? fieldScale : scale;

        // Per-series clip: restrict to this series' zone
        const zoneTop    = leaderIdx >= 0 && si !== leaderIdx ? PAD_TOP + leaderZoneH : PAD_TOP;
        const zoneHeight = leaderIdx >= 0 && si !== leaderIdx ? fieldZoneH            : leaderZoneH;

        ctx.save();
        ctx.beginPath();
        ctx.rect(0, zoneTop, clipX, zoneHeight);
        ctx.clip();

        const pts: [number, number][] = s.cum.map((v, i) => [
          toPixelX(i, maxLen, chartW),
          toPixelY(v),
        ]);
```

Update the area fill close path. Find:
```typescript
        ctx.lineTo(pts[pts.length - 1][0], toPixelY(0));
        ctx.lineTo(pts[0][0], toPixelY(0));
```
Replace with:
```typescript
        const zoneBottomY = leaderIdx >= 0
          ? (si === leaderIdx ? separatorY : PAD_TOP + chartH)
          : PAD_TOP + chartH;
        ctx.lineTo(pts[pts.length - 1][0], zoneBottomY);
        ctx.lineTo(pts[0][0], zoneBottomY);
```

At the END of the loop body (right before `}`), add the per-series restore:
```typescript
        ctx.restore(); // end per-series clip
      }
```

**Update drawLines dep array** — add `fieldScale`, `leaderIdx`, `leaderZoneH`, `fieldZoneH`, `separatorY`:
```typescript
    [series, scale, fieldScale, leaderIdx, leaderZoneH, fieldZoneH, separatorY, chartW, chartH, maxLen]
```

### Step 6: Update `drawEndpoints` to use per-series scale

Find:
```typescript
      const items = series.map((s) => {
        const lastX = toPixelX(s.cum.length - 1, maxLen, chartW);
        const lastY = toPixelY(s.cum[s.cum.length - 1]);
        return { s, lastX, lastY };
      });
```
Replace with:
```typescript
      const items = series.map((s, si) => {
        const { toPixelY: tpy } = (leaderIdx >= 0 && si !== leaderIdx) ? fieldScale : scale;
        const lastX = toPixelX(s.cum.length - 1, maxLen, chartW);
        const lastY = tpy(s.cum[s.cum.length - 1]);
        return { s, lastX, lastY };
      });
```

**Update drawEndpoints dep array** — add `fieldScale`, `leaderIdx`:
```typescript
    [series, scale, fieldScale, leaderIdx, dims, chartW, maxLen]
```

### Step 7: Update `drawHover` to use per-series scale

Find the crosshair dots loop. Currently it's `for (const s of series)`. Replace:
```typescript
      for (const s of series) {
        const v = interpolateAtX(s.cum, pixelX, maxLen, chartW);
        if (v === null) continue;
        const py = toPixelY(v);
```
With:
```typescript
      for (let si = 0; si < series.length; si++) {
        const s = series[si];
        const { toPixelY } = (leaderIdx >= 0 && si !== leaderIdx) ? fieldScale : scale;
        const v = interpolateAtX(s.cum, pixelX, maxLen, chartW);
        if (v === null) continue;
        const py = toPixelY(v);
```

**Update drawHover dep array** — add `fieldScale`, `leaderIdx`:
```typescript
    [series, scale, fieldScale, leaderIdx, dims, chartW, maxLen]
```

### Step 8: Update `drawPulse` to use per-series scale

Find the single destructure at the top of `drawPulse`:
```typescript
      const { toPixelY } = scale;
```
Remove this line entirely.

Then inside the `for (let si = 0; si < series.length; si++)` loop, find the `pxY` line:
```typescript
        const pxY      = toPixelY(s.cum[dataIdx]);
```
Replace with:
```typescript
        const { toPixelY } = (leaderIdx >= 0 && si !== leaderIdx) ? fieldScale : scale;
        const pxY = toPixelY(s.cum[dataIdx]);
```

**Update drawPulse dep array** — add `fieldScale`, `leaderIdx`:
```typescript
    [series, scale, fieldScale, leaderIdx, chartW, maxLen],
```

### Step 9: Verify build

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npm run build 2>&1 | tail -15
```
Expected: zero TypeScript errors. Pay special attention to:
- Any error about `chartH` still referenced inside `computeYScale` (should be `zoneH` now)
- Any error about `toPixelY` not found (check every callback was updated)
- Any "unused variable" warning about the old `const { toPixelY } = scale` removed from drawPulse

### Step 10: Visual check

Open http://localhost:5173 → Overview → CHART. Expected:
- With MICROCAP at 13%+ and others at 1-2%: chart splits at the midpoint. Top half = MICROCAP with +5%/+10%/+13% scale. Bottom half = field with +0.5%/+1.0%/+1.5%/+2.0% scale. Lines in the field zone now fill their half meaningfully.
- A dashed separator line (with soft bloom) divides the two zones
- Each zone has its own Y-axis labels on the left
- When all portfolios cluster together (no outlier): single scale, full height — chart unchanged from before

### Step 11: Commit and push

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && git add dashboard/src/components/PerformanceChart.tsx && git commit -m "feat: dual-zone Y-scale splits leader from field portfolios" && git push
```
