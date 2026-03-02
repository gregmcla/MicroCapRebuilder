import { useRef, useMemo, useState, useEffect } from "react";
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
    // Assigning canvas.width/height resets the transform matrix, so ctx.scale is safe here.
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
