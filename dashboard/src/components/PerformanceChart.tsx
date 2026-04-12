import { useRef, useMemo, useState, useEffect, useCallback } from "react";
import type { PortfolioSummary } from "../lib/types";

// ── Constants ────────────────────────────────────────────────────────────────

const CHART_PALETTE = [
  "#38bdf8", // sky blue
  "#a78bfa", // violet
  "#fb923c", // orange
  "#22C55E", // emerald → new green
  "#f472b6", // pink
  "#facc15", // yellow
  "#2dd4bf", // teal
  "#fb7185", // rose
  "#a3e635", // lime
  "#60a5fa", // blue
  "#c084fc", // purple
  "#22C55E", // green
  "#f97316", // orange-red
  "#22d3ee", // cyan
  "#e879f9", // fuchsia
];

const DD_SCAR_THRESHOLD = 3.0; // minimum peak-to-trough drawdown % to render a scar

const PULSE_DURATION_MS = 1800; // ms for one pulse to travel endpoint → origin

const PAD_TOP    = 28;
const PAD_RIGHT  = 172;
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

function computeYScale(allCums: number[][], zoneH: number, zoneTop: number = PAD_TOP): YScale {
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
    zoneTop + ((yMax - pct) / (yMax - yMin)) * zoneH;

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

// ── Drawdown scar helpers ─────────────────────────────────────────────────────

/** Returns running maximum of cum — runMax[i] = max(cum[0..i]). */
function computeRunningMax(cum: number[]): number[] {
  if (cum.length === 0) return [];
  const result: number[] = [];
  let rmax = cum[0];
  for (const v of cum) {
    if (v > rmax) rmax = v;
    result.push(rmax);
  }
  return result;
}

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

// ── X-axis time label helper ──────────────────────────────────────────────────

/** Converts a day count into a compact human label: 365+ → "1y", 60+ → "4mo", 14+ → "3w", else "5d" */
function daysAgo(n: number): string {
  if (n >= 365) return Math.round(n / 365) + "y";
  if (n >= 60)  return Math.round(n / 30)  + "mo";
  if (n >= 14)  return Math.round(n / 7)   + "w";
  return n + "d";
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

// ── ECG pulse types ───────────────────────────────────────────────────────────

interface PulseState {
  active:    boolean;
  startTime: number; // performance.now() when pulse started
  nextFire:  number; // performance.now() when next pulse fires
  interval:  number; // ms between pulses
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
  height?: number;
}

export default function PerformanceChart({ portfolios, height = 340 }: PerformanceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const [dims, setDims] = useState({ width: 600, height });

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

  const maxLen = useMemo(
    () => Math.max(1, ...series.map((s) => s.cum.length)),
    [series]
  );

  const seriesKey = series.map((s) => `${s.id}:${s.finalReturn.toFixed(1)}`).join("|");

  const [animProgress,   setAnimProgress]   = useState(0);
  const [endpointsAlpha, setEndpointsAlpha] = useState(0);
  const rafRef       = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const endStartRef  = useRef<number | null>(null);

  const [hoverX,     setHoverX]     = useState<number | null>(null);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  // ── ECG pulse state ───────────────────────────────────────────────────────
  const pulseStatesRef = useRef<PulseState[]>([]);
  const pulseRafRef      = useRef<number | null>(null);
  const pulseFrameTimeRef = useRef<number>(0);
  const [pulseTick, setPulseTick] = useState(0); // incremented to trigger redraws

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

  // ECG pulse RAF loop — fires independently of mount animation
  useEffect(() => {
    const now = performance.now();
    pulseStatesRef.current = series.map((s, i) => ({
      active:    false,
      startTime: 0,
      // Stagger first fires: wait for mount animation + endpoint fade + buffer
      nextFire:  now + 2000 + i * 700,
      // Deterministic interval derived from portfolio data — each portfolio has its own rhythm
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

      pulseFrameTimeRef.current = now;
      if (needRedraw) setPulseTick((n) => n + 1);
      pulseRafRef.current = requestAnimationFrame(tick);
    }

    pulseRafRef.current = requestAnimationFrame(tick);
    return () => {
      if (pulseRafRef.current !== null) cancelAnimationFrame(pulseRafRef.current);
    };
  }, [seriesKey]); // restart when portfolio identities or returns change

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
      const { toPixelY: leaderPixelY, guides: leaderGuides } = scale;
      const { toPixelY: fieldPixelY,  guides: fieldGuides  } = fieldScale;

      // Fill background
      ctx.fillStyle = "#020617";
      ctx.fillRect(0, 0, dims.width, dims.height);

      ctx.save();
      // ── Chromatic background zones (only when zero line is in range) ──────
      // Very subtle — just a whisper of tone, not a colored region
      if (scale.yMin < 0 && scale.yMax > 0) {
        const zeroY = scale.toPixelY(0);

        // Green zone above zero — barely perceptible
        const greenGrad = ctx.createLinearGradient(0, PAD_TOP, 0, zeroY);
        greenGrad.addColorStop(0, "rgba(0,255,140,0.05)");
        greenGrad.addColorStop(1, "rgba(0,255,140,0)");
        ctx.fillStyle = greenGrad;
        ctx.fillRect(PAD_LEFT, PAD_TOP, chartW, zeroY - PAD_TOP);

        // Red zone below zero — barely perceptible
        const redGrad = ctx.createLinearGradient(0, zeroY, 0, PAD_TOP + chartH);
        redGrad.addColorStop(0, "rgba(255,50,80,0)");
        redGrad.addColorStop(1, "rgba(255,50,80,0.02)");
        ctx.fillStyle = redGrad;
        ctx.fillRect(PAD_LEFT, zeroY, chartW, PAD_TOP + chartH - zeroY);
      }
      ctx.restore();

      ctx.save();
      ctx.font = "600 10px/1 'JetBrains Mono', 'Courier New', monospace";
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";

      // Leader zone guides
      for (const g of leaderGuides) {
        const py     = leaderPixelY(g);
        const isZero = g === 0;
        ctx.beginPath();
        ctx.moveTo(PAD_LEFT - 6, py);
        ctx.lineTo(dims.width - PAD_RIGHT + 8, py);
        ctx.strokeStyle = isZero ? "rgba(255,255,255,0.20)" : "rgba(255,255,255,0.06)";
        ctx.lineWidth   = isZero ? 1 : 1;
        ctx.stroke();
        const decimals = Math.abs(g) < 1 ? 1 : 0;
        const label = g === 0 ? "0%" : `${g > 0 ? "+" : ""}${g.toFixed(decimals)}%`;
        ctx.fillStyle = isZero ? "rgba(255,255,255,0.40)" : "rgba(255,255,255,0.28)";
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
          ctx.strokeStyle = isZero ? "rgba(255,255,255,0.20)" : "rgba(255,255,255,0.06)";
          ctx.lineWidth   = 1;
          ctx.stroke();
          const decimals = Math.abs(g) < 1 ? 1 : 0;
          const label = g === 0 ? "0%" : `${g > 0 ? "+" : ""}${g.toFixed(decimals)}%`;
          ctx.fillStyle = isZero ? "rgba(255,255,255,0.40)" : "rgba(255,255,255,0.28)";
          ctx.fillText(label, PAD_LEFT - 8, py);
        }
      }

      ctx.restore();

      // ── X-axis time markers ───────────────────────────────────────────────
      if (maxLen > 1) {
        const stepSize = Math.max(1, Math.round(maxLen / 5));
        ctx.save();
        ctx.font        = "600 10px/1 'JetBrains Mono', 'Courier New', monospace";
        ctx.fillStyle   = "rgba(255,255,255,0.40)";
        ctx.textAlign   = "center";
        ctx.strokeStyle = "rgba(255,255,255,0.25)";
        ctx.lineWidth   = 1;

        for (let d = stepSize; d < maxLen - 1 - stepSize / 2; d += stepSize) {
          const tickX = toPixelX(d, maxLen, chartW);

          // 4px tick mark at bottom of chart area
          ctx.beginPath();
          ctx.moveTo(tickX, PAD_TOP + chartH);
          ctx.lineTo(tickX, PAD_TOP + chartH + 4);
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

      // "NOW" label — right-aligned to nowX so it stays within the chart clip
      ctx.save();
      ctx.beginPath();
      ctx.rect(PAD_LEFT, PAD_TOP, chartW, chartH);
      ctx.clip();
      ctx.font         = "700 9px/1 'JetBrains Mono', 'Courier New', monospace";
      ctx.fillStyle    = "rgba(255,255,255,0.30)";
      ctx.textAlign    = "right";
      ctx.textBaseline = "top";
      ctx.fillText("NOW", nowX - 2, PAD_TOP + 4);
      ctx.restore();
    },
    [scale, dims, chartW, chartH, maxLen, fieldScale, separatorY]
  );

  // drawScars: disabled — filled maroon blocks destroyed the visual; no-op.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const drawScars = useCallback((_ctx: CanvasRenderingContext2D) => { /* no-op */ }, []);

  /** Right-side vertical legend sorted by return descending. */
  const drawLegend = useCallback(
    (ctx: CanvasRenderingContext2D, alpha: number) => {
      if (alpha <= 0 || series.length === 0) return;

      // Legend column is exactly PAD_RIGHT - 14px wide, fully within canvas
      // Layout: [8px left margin] [dot 3px] [4px gap] [name truncated] [return right-aligned]
      // Total column: dims.width - PAD_RIGHT + 12 → dims.width - 6
      const DOT_R       = 3;
      const LEGEND_L    = dims.width - PAD_RIGHT + 12; // left edge of legend column
      const LEGEND_R    = dims.width - 6;               // right edge (6px from canvas edge)
      const LEGEND_W    = LEGEND_R - LEGEND_L;          // total usable width
      const START_Y     = PAD_TOP + 4;
      const AVAIL_H     = dims.height - PAD_TOP - PAD_BOTTOM;
      // Compress row height when many entries so all fit
      const ENTRY_H     = series.length > 13
        ? Math.max(11, Math.floor(AVAIL_H / series.length))
        : 15;
      const MAX_ENTRIES = Math.min(series.length, Math.floor(AVAIL_H / ENTRY_H));
      // Smaller font when >13 entries
      const FONT_SIZE   = series.length > 13 ? 9 : 10;

      ctx.save();
      ctx.globalAlpha  = alpha;
      ctx.font         = `600 ${FONT_SIZE}px/1 'JetBrains Mono', 'Courier New', monospace`;
      ctx.textBaseline = "middle";

      for (let i = 0; i < MAX_ENTRIES; i++) {
        const s   = series[i];
        const y   = START_Y + i * ENTRY_H + ENTRY_H / 2;
        const ret = s.finalReturn;
        const sign = ret >= 0 ? "+" : "";

        // Colored dot
        ctx.beginPath();
        ctx.arc(LEGEND_L + DOT_R, y, DOT_R, 0, Math.PI * 2);
        ctx.fillStyle = s.color;
        ctx.shadowColor = s.color;
        ctx.shadowBlur  = 3;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Return % — right-aligned first (fixed-width, always fits)
        const retLabel = `${sign}${ret.toFixed(1)}%`;
        ctx.fillStyle  = ret >= 0 ? "rgba(160,240,200,0.85)" : "rgba(240,160,160,0.85)";
        ctx.textAlign  = "right";
        ctx.fillText(retLabel, LEGEND_R, y);

        // Portfolio name — truncated to 14 chars, left of return column
        // Measure return label width to know how much name space we have
        const retW  = ctx.measureText(retLabel).width;
        const nameX = LEGEND_L + DOT_R * 2 + 5;
        const nameMaxW = LEGEND_W - retW - DOT_R * 2 - 5 - 4; // 4px gap between name and return

        const raw = (s.name ?? s.id).toUpperCase();
        const truncated = raw.length > 13 ? raw.slice(0, 12) + "\u2026" : raw;
        // Clip to available width before drawing (hard guard against overflow)
        ctx.save();
        ctx.beginPath();
        ctx.rect(nameX, y - ENTRY_H / 2, Math.max(nameMaxW, 0), ENTRY_H);
        ctx.clip();
        ctx.fillStyle = "rgba(255,255,255,0.70)";
        ctx.textAlign = "left";
        ctx.fillText(truncated, nameX, y);
        ctx.restore();
      }

      ctx.restore();
    },
    [series, dims],
  );

  const drawEndpoints = useCallback(
    (ctx: CanvasRenderingContext2D, alpha: number) => {
      if (alpha <= 0) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      // Build list of label items sorted by Y (top of chart first = smallest pixel Y)
      const items = series.map((s, si) => {
        const { toPixelY: tpy } = (leaderIdx >= 0 && si !== leaderIdx) ? fieldScale : scale;
        const lastX = toPixelX(s.cum.length - 1, maxLen, chartW);
        const lastY = tpy(s.cum[s.cum.length - 1]);
        return { s, lastX, lastY };
      });
      const sorted = items.slice().sort((a, b) => a.lastY - b.lastY);

      // Draw only the endpoint dot at the actual line terminus — no label text here.
      // Labels are rendered by drawLegend as a clean sorted list.
      for (const item of sorted) {
        ctx.beginPath();
        ctx.arc(item.lastX, item.lastY, 3, 0, Math.PI * 2);
        ctx.fillStyle   = item.s.color;
        ctx.shadowColor = item.s.color;
        ctx.shadowBlur  = 4;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      ctx.restore();
    },
    [series, scale, fieldScale, leaderIdx, dims, chartW, maxLen]
  );

  const drawLines = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      progress: number,          // 0→1 clip for mount animation
      hoveredIdx: number | null  // null = no hover; index = one series fully lit
    ) => {
      const clipX = PAD_LEFT + chartW * progress;

      for (let si = 0; si < series.length; si++) {
        const s = series[si];
        const { toPixelY, yMax: zoneYMax, yMin: zoneYMin } = (leaderIdx >= 0 && si !== leaderIdx) ? fieldScale : scale;

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

        if (pts.length < 2) { ctx.restore(); continue; }

        // Dimming: hovered line = full opacity + 2px; all others drop to 0.25
        const isHovered = hoveredIdx !== null && hoveredIdx === si;
        const baseAlpha = hoveredIdx !== null && !isHovered ? 0.25 : 1.0;
        const lineWidth = isHovered ? 2.0 : 1.5;

        // ── Area fill — barely-there whisper of color beneath each line ───────
        ctx.save();
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = baseAlpha * 0.04;
        const grad = ctx.createLinearGradient(0, toPixelY(zoneYMax), 0, toPixelY(zoneYMin));
        grad.addColorStop(0, s.color);
        grad.addColorStop(1, "transparent");
        ctx.beginPath();
        catmullRomPath(ctx, pts);
        const zoneBottomY = leaderIdx >= 0
          ? (si === leaderIdx ? separatorY : PAD_TOP + chartH)
          : PAD_TOP + chartH;
        ctx.lineTo(pts[pts.length - 1][0], zoneBottomY);
        ctx.lineTo(pts[0][0], zoneBottomY);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.restore();

        // ── Line — glow only on hovered series; others are clean 1.5px ───────
        ctx.save();
        ctx.globalAlpha    = baseAlpha;
        ctx.strokeStyle    = s.color;
        ctx.lineWidth      = lineWidth;
        ctx.lineJoin       = "round";
        ctx.lineCap        = "round";
        if (isHovered) {
          ctx.shadowColor  = s.color;
          ctx.shadowBlur   = 10;
        }
        ctx.beginPath();
        catmullRomPath(ctx, pts);
        ctx.stroke();
        ctx.shadowBlur = 0;
        ctx.restore();
        ctx.restore(); // end per-series clip
      }
    },
    [series, scale, fieldScale, leaderIdx, leaderZoneH, fieldZoneH, separatorY, chartW, chartH, maxLen]
  );

  const drawHover = useCallback(
    (ctx: CanvasRenderingContext2D, pixelX: number) => {
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
      for (let si = 0; si < series.length; si++) {
        const s = series[si];
        const { toPixelY } = (leaderIdx >= 0 && si !== leaderIdx) ? fieldScale : scale;
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
      ctx.fillStyle   = "rgba(8,9,13,0.95)";
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
      ctx.font         = "600 9px/1 'JetBrains Mono', 'Courier New', monospace";
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
    [series, scale, fieldScale, leaderIdx, dims, chartW, maxLen]
  );

  const drawPulse = useCallback(
    (ctx: CanvasRenderingContext2D) => {
      const states = pulseStatesRef.current;
      const now    = pulseFrameTimeRef.current;

      for (let si = 0; si < series.length; si++) {
        const ps = states[si];
        if (!ps?.active) continue;

        const s       = series[si];
        if (s.cum.length < 2) continue;
        const elapsed = now - ps.startTime;
        const pulseT  = Math.min(elapsed / PULSE_DURATION_MS, 1);

        // Bell-curve alpha: fades in, peaks at midpoint, fades out
        const pulseAlpha = Math.sin(pulseT * Math.PI);

        // Position: moves from endpoint (pulseT=0) to origin (pulseT=1) along the line
        const dataFrac = (1 - pulseT) * (s.cum.length - 1);
        const dataIdx  = Math.min(Math.round(dataFrac), s.cum.length - 1);
        const pxX      = toPixelX(dataFrac, maxLen, chartW);
        const { toPixelY } = (leaderIdx >= 0 && si !== leaderIdx) ? fieldScale : scale;
        const pxY = toPixelY(s.cum[dataIdx]);

        // Outer bloom — large, soft
        ctx.save();
        ctx.globalAlpha = pulseAlpha * 0.40;
        ctx.filter      = "blur(7px)";
        ctx.beginPath();
        ctx.arc(pxX, pxY, 10, 0, Math.PI * 2);
        ctx.fillStyle = s.color;
        ctx.fill();
        ctx.filter = "none";
        ctx.restore();

        // Mid glow — tighter, portfolio color
        ctx.save();
        ctx.globalAlpha = pulseAlpha * 0.75;
        ctx.filter      = "blur(2px)";
        ctx.beginPath();
        ctx.arc(pxX, pxY, 5, 0, Math.PI * 2);
        ctx.fillStyle = s.color;
        ctx.fill();
        ctx.filter = "none";
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
    [series, scale, fieldScale, leaderIdx, chartW, maxLen],
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
      const y = e.clientY - rect.top;
      let closest = 0;
      let closestDist = Infinity;
      series.forEach((s, si) => {
        const { toPixelY: sToPixelY } = (leaderIdx >= 0 && si !== leaderIdx) ? fieldScale : scale;
        const v = interpolateAtX(s.cum, x, maxLen, chartW);
        if (v === null) return;
        const dist = Math.abs(sToPixelY(v) - y);
        if (dist < closestDist) { closestDist = dist; closest = si; }
      });
      setHoveredIdx(closest);
    },
    [series, scale, fieldScale, leaderIdx, dims, chartW, maxLen]
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
    drawScars(ctx);
    drawLines(ctx, animProgress, hoverX !== null ? hoveredIdx : null);
    drawEndpoints(ctx, endpointsAlpha);
    drawLegend(ctx, endpointsAlpha);
    drawPulse(ctx);
    if (hoverX !== null && animProgress >= 1) drawHover(ctx, hoverX);
  }, [drawGrid, drawScars, drawLines, drawLegend, drawEndpoints, drawPulse, drawHover, dims, animProgress, endpointsAlpha, hoverX, hoveredIdx, pulseTick]);

  if (series.length === 0) {
    return (
      <div style={{ height: `${height}px`, display: "flex", alignItems: "center", justifyContent: "center", background: "#020617", borderRadius: "7px" }}>
        <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.2)", fontFamily: "'JetBrains Mono', 'Courier New', monospace" }}>
          No portfolio history
        </p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        height: `${height}px`,
        background: "#020617",
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
      <canvas
        ref={canvasRef}
        style={{ display: "block", width: "100%", height: "100%" }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />
    </div>
  );
}
