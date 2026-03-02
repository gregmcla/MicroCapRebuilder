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

const PAD_TOP    = 28;
const PAD_RIGHT  = 112;
const PAD_BOTTOM = 24;
const PAD_LEFT   = 40;

// ── Cubic-bezier easing: cubic-bezier(0.16, 1, 0.3, 1) ──────────────────────

// @ts-ignore used in Task 5 animation
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

// @ts-ignore used in Task 3 line rendering
function toPixelX(dayIdx: number, maxLen: number, chartW: number): number {
  if (maxLen <= 1) return PAD_LEFT;
  return PAD_LEFT + (dayIdx / (maxLen - 1)) * chartW;
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

  const chartH = dims.height - PAD_TOP  - PAD_BOTTOM;

  const scale = useMemo(
    () => computeYScale(series.map((s) => s.cum), chartH),
    [series, chartH]
  );

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

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || dims.width === 0) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, dims.width, dims.height);
    drawGrid(ctx);
  }, [drawGrid, dims]);

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
