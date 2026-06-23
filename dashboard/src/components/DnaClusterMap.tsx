/** DnaClusterMap — cross-portfolio 2D PCA scatter of strategy DNAs.
 *
 * Each portfolio = a labeled dot in genome-space. Distance between dots
 * = qualitative similarity. Hover for the genome breakdown. Toggle between
 * STATED (config-derived) and MEASURED (90d behavior).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { DnaClusterPoint } from "../lib/types";
import DnaRadar from "./IntelligenceBrief/DnaRadar";
import { DNA_AXES, type DnaAxis } from "../lib/types";

const FONT = "'JetBrains Mono', 'SF Mono', monospace";

export default function DnaClusterMap() {
  const [mode, setMode] = useState<"stated" | "measured">("stated");
  const { data, isLoading } = useQuery({
    queryKey: ["dna-cluster", mode],
    queryFn: () => api.getDnaCluster(mode, "all"),
    staleTime: 5 * 60_000,
  });
  const [hovered, setHovered] = useState<string | null>(null);

  if (isLoading || !data) {
    return (
      <div style={{ padding: "20px", color: "var(--text-1)", fontFamily: FONT }}>
        Loading cluster map…
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: FONT }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "baseline", justifyContent: "space-between",
        padding: "8px 0", borderBottom: "1px solid var(--border-0)", marginBottom: "12px",
      }}>
        <div>
          <div style={{ color: "var(--text-4)", fontSize: "14px", fontWeight: 700 }}>
            Strategy DNA — Cluster Map
          </div>
          <div style={{ color: "var(--text-1)", fontSize: "10px", marginTop: "2px" }}>
            Each portfolio projected to 2D from its 8-axis DNA via PCA. Closer = more similar.
            Variance explained: PC1 {(data.variance_explained[0] * 100).toFixed(0)}% · PC2 {(data.variance_explained[1] * 100).toFixed(0)}%
          </div>
        </div>
        <div style={{ display: "flex", gap: "2px", background: "var(--surface-2)", borderRadius: "6px", padding: "2px" }}>
          {(["stated", "measured"] as const).map((opt) => (
            <button
              key={opt}
              onClick={() => setMode(opt)}
              style={{
                padding: "4px 10px",
                borderRadius: "4px",
                fontSize: "10px",
                fontWeight: mode === opt ? 700 : 500,
                color: mode === opt ? "var(--text-4)" : "var(--text-1)",
                background: mode === opt ? "var(--surface-4)" : "transparent",
                border: "none",
                cursor: "pointer",
                fontFamily: FONT,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      {/* Plot + tooltip */}
      <div style={{ flex: 1, display: "flex", gap: "16px", minHeight: 0 }}>
        <div style={{ flex: 1, position: "relative", minHeight: 0 }}>
          <ScatterCanvas points={data.portfolios} hovered={hovered} onHover={setHovered} />
        </div>
        <div style={{ width: "320px", flexShrink: 0, overflowY: "auto" }}>
          {hovered ? (
            <HoveredPanel point={data.portfolios.find((p) => p.id === hovered)} />
          ) : (
            <DefaultPanel points={data.portfolios} />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Canvas scatter ──────────────────────────────────────────────────────────

function ScatterCanvas({
  points,
  hovered,
  onHover,
}: {
  points: DnaClusterPoint[];
  hovered: string | null;
  onHover: (id: string | null) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 600, h: 400 });

  // Resize observer
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Compute layout coords
  const layout = useMemo(() => {
    if (!points.length) return { coords: new Map<string, [number, number]>(), bounds: { minX: 0, maxX: 0, minY: 0, maxY: 0 } };
    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    return { bounds: { minX, maxX, minY, maxY }, coords: new Map<string, [number, number]>() };
  }, [points]);

  // Draw
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size.w * dpr;
    canvas.height = size.h * dpr;
    canvas.style.width = `${size.w}px`;
    canvas.style.height = `${size.h}px`;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, size.w, size.h);

    if (!points.length) return;
    const { minX, maxX, minY, maxY } = layout.bounds;
    const padX = (maxX - minX || 1) * 0.15;
    const padY = (maxY - minY || 1) * 0.15;
    const x0 = minX - padX, x1 = maxX + padX;
    const y0 = minY - padY, y1 = maxY + padY;

    const project = (px: number, py: number): [number, number] => [
      ((px - x0) / (x1 - x0)) * size.w,
      ((y1 - py) / (y1 - y0)) * size.h,   // invert Y so larger PC2 → higher on screen
    ];

    // Background grid
    ctx.strokeStyle = "rgba(255,255,255,0.04)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const x = (i / 4) * size.w;
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, size.h); ctx.stroke();
      const y = (i / 4) * size.h;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(size.w, y); ctx.stroke();
    }

    // Origin crosshair (where the mean projects to)
    const [ox, oy] = project(0, 0);
    ctx.strokeStyle = "rgba(255,255,255,0.10)";
    ctx.beginPath();
    ctx.moveTo(ox - 10, oy); ctx.lineTo(ox + 10, oy);
    ctx.moveTo(ox, oy - 10); ctx.lineTo(ox, oy + 10);
    ctx.stroke();

    // Points
    layout.coords.clear();
    points.forEach((p) => {
      const [cx, cy] = project(p.x, p.y);
      layout.coords.set(p.id, [cx, cy]);
      const isHovered = hovered === p.id;
      const isDimmed = hovered && !isHovered;

      // Dot
      ctx.beginPath();
      ctx.arc(cx, cy, isHovered ? 9 : 6, 0, Math.PI * 2);
      ctx.fillStyle = isDimmed ? "rgba(124,92,252,0.30)" : "#a78bfa";
      ctx.fill();
      ctx.strokeStyle = isHovered ? "#fbbf24" : "rgba(255,255,255,0.6)";
      ctx.lineWidth = isHovered ? 2 : 1;
      ctx.stroke();

      // Label
      ctx.font = `${isHovered ? "bold " : ""}11px ${FONT}`;
      ctx.fillStyle = isDimmed ? "rgba(176,176,200,0.4)" : "#e0e0f0";
      ctx.textAlign = "left";
      ctx.fillText(p.name || p.id, cx + 10, cy + 4);
    });
  }, [points, size, hovered, layout]);

  // Hover detection
  const onMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    let nearest: string | null = null;
    let nearestDist = 12 * 12;       // 12px radius
    layout.coords.forEach((coord, id) => {
      const dx = coord[0] - mx;
      const dy = coord[1] - my;
      const d2 = dx * dx + dy * dy;
      if (d2 < nearestDist) {
        nearestDist = d2;
        nearest = id;
      }
    });
    onHover(nearest);
  };

  return (
    <div
      ref={containerRef}
      style={{
        flex: 1,
        position: "relative",
        background: "var(--surface-1)",
        border: "1px solid var(--border-0)",
        borderRadius: "8px",
        minHeight: "400px",
      }}
    >
      <canvas
        ref={canvasRef}
        onMouseMove={onMouseMove}
        onMouseLeave={() => onHover(null)}
        style={{ display: "block", width: "100%", height: "100%", cursor: "crosshair" }}
      />
    </div>
  );
}

// ─── Right-rail panels ───────────────────────────────────────────────────────

function HoveredPanel({ point }: { point?: DnaClusterPoint }) {
  if (!point) return null;
  return (
    <div style={{
      background: "var(--surface-1)",
      border: "1px solid var(--border-0)",
      borderRadius: "8px",
      padding: "12px",
    }}>
      <div style={{ color: "var(--text-4)", fontSize: "13px", fontWeight: 700, marginBottom: "4px" }}>
        {point.name}
      </div>
      <div style={{ color: "var(--text-1)", fontSize: "9px", letterSpacing: "0.06em", marginBottom: "12px" }}>
        Confidence {(point.genome.confidence * 100).toFixed(0)}%
      </div>
      <DnaRadar
        stated={point.genome}      // single-genome render: just show as solid
        measured={point.genome}    // overlay onto itself
        drift={Object.fromEntries(DNA_AXES.map((a) => [a, 0])) as Record<DnaAxis, number>}
        size={280}
        showLabels={true}
        showValues={false}
      />
    </div>
  );
}

function DefaultPanel({ points }: { points: DnaClusterPoint[] }) {
  // Compute pairwise distances and show top 3 nearest pairs
  const pairs: Array<{ a: DnaClusterPoint; b: DnaClusterPoint; d: number }> = [];
  for (let i = 0; i < points.length; i++) {
    for (let j = i + 1; j < points.length; j++) {
      const dx = points[i].x - points[j].x;
      const dy = points[i].y - points[j].y;
      pairs.push({ a: points[i], b: points[j], d: Math.sqrt(dx * dx + dy * dy) });
    }
  }
  pairs.sort((p, q) => p.d - q.d);
  const closest = pairs.slice(0, 3);

  return (
    <div style={{ color: "var(--text-2)", fontSize: "11px" }}>
      <div style={{ color: "var(--text-0)", fontSize: "9px", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: "8px" }}>
        DNA-similar portfolios
      </div>
      {closest.length === 0 ? (
        <div>No portfolios to compare.</div>
      ) : (
        closest.map((p, i) => (
          <div key={i} style={{
            padding: "8px 10px",
            marginBottom: "6px",
            background: "var(--surface-1)",
            border: "1px solid var(--border-0)",
            borderRadius: "6px",
          }}>
            <div style={{ fontWeight: 600, color: "var(--text-3)" }}>
              {p.a.name} ↔ {p.b.name}
            </div>
            <div style={{ color: "var(--text-1)", fontSize: "10px", marginTop: "2px" }}>
              distance: {p.d.toFixed(2)}
            </div>
          </div>
        ))
      )}
      <div style={{ marginTop: "16px", color: "var(--text-0)", fontSize: "9px", lineHeight: 1.5 }}>
        Hover any dot to see its full DNA radar. Closer pairs are running similar strategies — candidates to merge or differentiate.
      </div>
    </div>
  );
}
