import { useRef, useMemo, useState, useEffect, useCallback } from "react";
import type { PortfolioSummary } from "../lib/types";

// ── Constants ────────────────────────────────────────────────────────────────

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

const ECHO_DEFS = [
  { offset: 0.06, opacity: 0.28, blur: "1px",   width: 2.5 },
  { offset: 0.12, opacity: 0.14, blur: "2px",   width: 3.5 },
  { offset: 0.20, opacity: 0.06, blur: "3.5px", width: 5.5 },
] as const;

const PAD_TOP    = 28;
const PAD_RIGHT  = 112;
const PAD_BOTTOM = 24;
const PAD_LEFT   = 40;

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

// ── Catmull-Rom spline renderer ───────────────────────────────────────────────

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

/** Linear interpolation of a series' cum return at a given pixel X. */
function interpolateAtX(
  cum: number[],
  pixelX: number,
  maxLen: number,
  chartW: number
): number | null {
  if (cum.length === 0) return null;
  const fracIdx = ((pixelX - PAD_LEFT) / chartW) * (maxLen - 1);
  if (fracIdx < 0 || fracIdx > cum.length - 1) return null;
  const lo = Math.floor(fracIdx);
  const hi = Math.min(lo + 1, cum.length - 1);
  const t  = fracIdx - lo;
  return cum[lo] * (1 - t) + cum[hi] * t;
}

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

  const [animProgress,   setAnimProgress]   = useState(0);
  const [endpointsAlpha, setEndpointsAlpha] = useState(0);
  const rafRef       = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const endStartRef  = useRef<number | null>(null);

  const [hoverX,     setHoverX]     = useState<number | null>(null);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

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
        // Start endpoint fade — transition fires once
        if (endStartRef.current === null) {
          endStartRef.current = now;
          setAnimProgress(1);
        }
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
  }, [series.length]); // reset and replay when portfolio count changes

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
    // Assigning canvas.width/height resets the transform matrix, so ctx.scale is safe here.
    ctx.scale(dpr, dpr);
  }, [dims]);

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

        // Horizontal guide line — solid hairline (not dashed)
        ctx.beginPath();
        ctx.moveTo(PAD_LEFT - 6, py);
        ctx.lineTo(dims.width - PAD_RIGHT + 8, py);
        ctx.strokeStyle = isZero
          ? "rgba(255,255,255,0.10)"
          : "rgba(255,255,255,0.05)";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Y-axis label
        const decimals = Math.abs(g) < 1 ? 1 : 0;
        const label = g === 0 ? "0%" : `${g > 0 ? "+" : ""}${g.toFixed(decimals)}%`;
        ctx.fillStyle = isZero
          ? "rgba(255,255,255,0.28)"
          : "rgba(255,255,255,0.18)";
        ctx.fillText(label, PAD_LEFT - 8, py);
      }

      ctx.restore();
    },
    [scale, dims]
  );

  const drawEndpoints = useCallback(
    (ctx: CanvasRenderingContext2D, alpha: number) => {
      if (alpha <= 0) return;
      const { toPixelY } = scale;

      ctx.save();
      ctx.globalAlpha = alpha;

      // Build list of label items sorted by Y (top of chart first = smallest pixel Y)
      const items = series.map((s) => {
        const lastX = toPixelX(s.cum.length - 1, maxLen, chartW);
        const lastY = toPixelY(s.cum[s.cum.length - 1]);
        return { s, lastX, lastY };
      });
      const sorted = items.slice().sort((a, b) => a.lastY - b.lastY);

      // Assign vertical positions with collision avoidance
      const MIN_GAP = 12; // px minimum vertical gap between labels
      const assignedY: number[] = [];
      for (const item of sorted) {
        let y = item.lastY;
        for (const used of assignedY) {
          if (Math.abs(y - used) < MIN_GAP) {
            y = used + MIN_GAP;
          }
        }
        assignedY.push(y);

        // Dot at actual line endpoint Y
        ctx.beginPath();
        ctx.arc(item.lastX, item.lastY, 3, 0, Math.PI * 2);
        ctx.fillStyle = item.s.color;
        ctx.fill();

        // Label: "ID  +XX.X%" in the right zone
        const ret   = item.s.finalReturn;
        const sign  = ret >= 0 ? "+" : "";
        const label = `${item.s.id.toUpperCase()}  ${sign}${ret.toFixed(1)}%`;
        const labelX = dims.width - PAD_RIGHT + 14;

        ctx.font         = "700 8.5px/1 monospace";
        ctx.fillStyle    = item.s.color;
        ctx.textAlign    = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(label, labelX, y);
      }

      ctx.restore();
    },
    [series, scale, dims, chartW, maxLen]
  );

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
      ctx.rect(0, PAD_TOP, clipX, chartH);
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

        // ── Temporal echo trails (drawn before area fill, furthest back) ──────
        for (const echo of ECHO_DEFS) {
          const echoProgress = progress - echo.offset;
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
        ctx.save();
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
        ctx.restore(); // end screen blending wrapper
      }

      ctx.restore(); // remove clip
    },
    [series, scale, chartW, chartH, maxLen]
  );

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
      ctx.save();
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
      ctx.restore();

      if (rows.length === 0) return;

      // Tooltip — fixed order (series is sorted by finalReturn on mount, rows follows that order)
      const LINE_H  = 16;
      const PAD_H   = 8;
      const CARD_W  = 130;
      const cardH   = rows.length * LINE_H + PAD_H * 2;

      // Position: left of cursor if near right edge; clamp to chart left boundary
      let tx = pixelX + 12;
      if (tx + CARD_W > dims.width - PAD_RIGHT) tx = pixelX - CARD_W - 12;
      tx = Math.max(PAD_LEFT, tx);
      const ty = PAD_TOP + 8;

      // Card background
      ctx.save();
      ctx.fillStyle   = "rgba(4,4,12,0.94)";
      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      ctx.lineWidth   = 1;
      ctx.beginPath();
      if (typeof ctx.roundRect === "function") {
        ctx.roundRect(tx, ty, CARD_W, cardH, 4);
      } else {
        ctx.rect(tx, ty, CARD_W, cardH);
      }
      ctx.fill();
      ctx.stroke();

      // Rows
      ctx.font         = "600 8.5px/1 monospace";
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

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = e.clientX - rect.left;

      // Clamp to chart area only (not label zone)
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
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />
    </div>
  );
}
