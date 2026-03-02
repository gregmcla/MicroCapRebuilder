/** Overview page — shown when activePortfolioId === "overview". */

import { useMemo, useState, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOverview, usePortfolios } from "../hooks/usePortfolios";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import { useCountUp } from "../hooks/useCountUp";
import type { PortfolioSummary, CrossPortfolioMover } from "../lib/types";
import CreatePortfolioModal from "./CreatePortfolioModal";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function pnlColor(v: number) {
  return v > 0 ? "var(--green)" : v < 0 ? "var(--red)" : "var(--text-2)";
}

function fmt$(v: number, decimals = 0) {
  return `${v >= 0 ? "+" : ""}$${Math.abs(v).toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

function fmtPct(v: number, decimals = 1) {
  return `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`;
}

/** Box-shadow glow — lowered thresholds so they actually show. */
function cardGlow(returnPct: number): string {
  if (returnPct >= 15)  return "0 0 22px 3px rgba(52,211,153,0.30), 0 0 8px 1px rgba(52,211,153,0.20)";
  if (returnPct >= 5)   return "0 0 14px 2px rgba(52,211,153,0.18), 0 0 4px 1px rgba(52,211,153,0.10)";
  if (returnPct >= 1.5) return "0 0 8px 1px rgba(52,211,153,0.10)";
  if (returnPct <= -8)  return "0 0 14px 2px rgba(248,113,113,0.20), 0 0 4px 1px rgba(248,113,113,0.12)";
  if (returnPct <= -2)  return "0 0 8px 1px rgba(248,113,113,0.10)";
  return "none";
}

// ---------------------------------------------------------------------------
// Equity sparkline — standalone visible strip
// ---------------------------------------------------------------------------

function EquitySparkline({ values, returnPct }: { values: number[]; returnPct: number }) {
  const W = 200; const H = 36;
  const points = useMemo(() => {
    if (values.length < 2) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    return values.map((v, i) => {
      const x = (i / (values.length - 1)) * W;
      const y = H - 1 - ((v - min) / range) * (H - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  }, [values]);

  if (!points) return null;
  const up = returnPct >= 0;
  const color = up ? "var(--green)" : "var(--red)";

  return (
    <svg
      width="100%" height={H}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      style={{ display: "block" }}
    >
      <defs>
        <linearGradient id={`g-${returnPct}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={color} stopOpacity="0.01" />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${H} ${points} ${W},${H}`}
        fill={`url(#g-${returnPct})`}
      />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.9"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// All Positions Panel — weighted map + scatter plot toggle
// ---------------------------------------------------------------------------

const PORTFOLIO_PALETTE = [
  "#34d399", // emerald
  "#818cf8", // indigo
  "#38bdf8", // sky
  "#fb923c", // orange
  "#f472b6", // pink
  "#a78bfa", // violet
  "#fbbf24", // amber
  "#4ade80", // green
];

type ViewMode = "map" | "plot";

function usePortfolioColors(positions: CrossPortfolioMover[]) {
  return useMemo(() => {
    const ids = [...new Set(positions.map((p) => p.portfolio_id))].sort();
    const map: Record<string, string> = {};
    ids.forEach((id, i) => { map[id] = PORTFOLIO_PALETTE[i % PORTFOLIO_PALETTE.length]; });
    return map;
  }, [positions]);
}

function blockBg(pct: number) {
  if (pct >= 12)  return "rgba(52,211,153,0.55)";
  if (pct >= 6)   return "rgba(52,211,153,0.36)";
  if (pct >= 2)   return "rgba(52,211,153,0.20)";
  if (pct >= 0)   return "rgba(52,211,153,0.08)";
  if (pct >= -2)  return "rgba(248,113,113,0.08)";
  if (pct >= -6)  return "rgba(248,113,113,0.20)";
  if (pct >= -12) return "rgba(248,113,113,0.36)";
  return "rgba(248,113,113,0.55)";
}

// ── View 1: Weighted Map ─────────────────────────────────────────────────────

function WeightedMap({ positions, portfolioColors }: {
  positions: CrossPortfolioMover[];
  portfolioColors: Record<string, string>;
}) {
  const sorted = useMemo(
    () => [...positions].sort((a, b) => b.pnl_pct - a.pnl_pct),
    [positions]
  );

  return (
    <div style={{
      display: "flex", flexWrap: "wrap", gap: "2px", padding: "6px",
      background: "var(--surface-1)", border: "1px solid var(--border-0)", borderRadius: "7px",
    }}>
      {sorted.map((pos) => {
        const mv = pos.market_value ?? 1000;
        // sqrt normalization + flex-basis 0 so flex-grow is the sole size driver
        const flexGrow = Math.max(Math.sqrt(mv / 500), 0.8);
        const portfolioColor = portfolioColors[pos.portfolio_id] ?? "#818cf8";
        const pnlColor = pos.pnl_pct >= 0 ? "var(--green)" : "var(--red)";
        return (
          <div
            key={`${pos.portfolio_id}-${pos.ticker}`}
            title={`${pos.ticker} · ${pos.portfolio_name} · ${fmtPct(pos.pnl_pct)} · $${mv.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
            style={{
              background: blockBg(pos.pnl_pct),
              borderRadius: "4px",
              borderTop: `2px solid ${portfolioColor}`,
              borderLeft: "1px solid rgba(255,255,255,0.04)",
              borderRight: "1px solid rgba(255,255,255,0.04)",
              borderBottom: "1px solid rgba(255,255,255,0.04)",
              padding: "4px 7px",
              display: "flex", flexDirection: "column", alignItems: "center", gap: "1px",
              cursor: "pointer", transition: "opacity 0.15s",
              minWidth: "46px",
              flex: `${flexGrow} 0 0`,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.7")}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
          >
            <span style={{ fontSize: "9.5px", fontWeight: 700, color: "var(--text-4)", fontFamily: "var(--font-mono)", letterSpacing: "0.03em" }}>
              {pos.ticker}
            </span>
            <span style={{ fontSize: "9px", fontWeight: 600, color: pnlColor, fontFamily: "var(--font-mono)" }}>
              {fmtPct(pos.pnl_pct, 1)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── View 2: Scatter Plot ─────────────────────────────────────────────────────

function ScatterPlot({ positions, portfolioColors }: {
  positions: CrossPortfolioMover[];
  portfolioColors: Record<string, string>;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const VW = 800, VH = 230;
  const ML = 58, MR = 16, MT = 18, MB = 36;
  const CW = VW - ML - MR;
  const CH = VH - MT - MB;

  const xVals = positions.map((p) => p.pnl_pct);
  const yVals = positions.map((p) => p.market_value ?? 0);
  const xMin = Math.min(...xVals);
  const xMax = Math.max(...xVals);
  const xPad = Math.max((xMax - xMin) * 0.10, 2);
  const xLo = xMin - xPad;
  const xHi = xMax + xPad;
  const yMax = Math.max(...yVals) * 1.18;

  const xs = (v: number) => ML + ((v - xLo) / (xHi - xLo)) * CW;
  const ys = (v: number) => MT + CH - (v / yMax) * CH;
  const zeroX = xs(0);

  // X ticks
  const xRange = xHi - xLo;
  const tickStep = xRange < 10 ? 2 : xRange < 25 ? 5 : 10;
  const xTicks: number[] = [];
  for (let t = Math.ceil(xLo / tickStep) * tickStep; t <= xHi; t += tickStep) xTicks.push(t);

  // Y ticks
  const yTickCount = 4;
  const yTicks = Array.from({ length: yTickCount + 1 }, (_, i) => (yMax / yTickCount) * i);

  // Label extremes so labels spread across the chart — not the 0% cluster
  // Top 4 gainers (rightmost) + worst 4 losers (leftmost) + top 3 by size (topmost)
  const byGain = [...positions].sort((a, b) => b.pnl_pct - a.pnl_pct);
  const bySize = [...positions].sort((a, b) => (b.market_value ?? 0) - (a.market_value ?? 0));
  const extremeKeys = new Set([
    ...byGain.slice(0, 4).map((p) => `${p.portfolio_id}-${p.ticker}`),
    ...byGain.slice(-4).map((p) => `${p.portfolio_id}-${p.ticker}`),
    ...bySize.slice(0, 3).map((p) => `${p.portfolio_id}-${p.ticker}`),
  ]);
  const topKeys = extremeKeys;

  // Unique portfolio entries for legend
  const portfolioEntries = Object.entries(portfolioColors).filter(([id]) =>
    positions.some((p) => p.portfolio_id === id)
  );

  const hoveredPos = hovered ? positions.find((p) => `${p.portfolio_id}-${p.ticker}` === hovered) : null;

  return (
    <div style={{ background: "var(--surface-1)", border: "1px solid var(--border-0)", borderRadius: "7px", padding: "6px 6px 4px" }}>
      <svg
        ref={svgRef}
        width="100%"
        viewBox={`0 0 ${VW} ${VH}`}
        style={{ display: "block", overflow: "visible" }}
      >
        {/* Subtle grid */}
        {yTicks.map((y, i) => (
          <line key={`yg${i}`} x1={ML} y1={ys(y)} x2={VW - MR} y2={ys(y)}
            stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
        ))}
        {xTicks.map((x, i) => (
          <line key={`xg${i}`} x1={xs(x)} y1={MT} x2={xs(x)} y2={VH - MB}
            stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
        ))}

        {/* Zero line */}
        <line x1={zeroX} y1={MT} x2={zeroX} y2={VH - MB}
          stroke="rgba(255,255,255,0.18)" strokeWidth="1" strokeDasharray="4,3" />

        {/* Quadrant hint text */}
        <text x={zeroX + 7} y={MT + 11} fontSize="8" fill="rgba(52,211,153,0.30)" fontFamily="monospace">gains →</text>
        <text x={zeroX - 7} y={MT + 11} fontSize="8" fill="rgba(248,113,113,0.30)" fontFamily="monospace" textAnchor="end">← losses</text>

        {/* Y axis labels */}
        {yTicks.map((y, i) => (
          <text key={`yt${i}`} x={ML - 5} y={ys(y) + 3} fontSize="8" fill="var(--text-0)"
            textAnchor="end" fontFamily="monospace">
            {y >= 1000 ? `$${(y / 1000).toFixed(0)}k` : `$${y.toFixed(0)}`}
          </text>
        ))}

        {/* X axis labels */}
        {xTicks.map((x, i) => (
          <text key={`xt${i}`} x={xs(x)} y={VH - MB + 13} fontSize="8" fill="var(--text-0)"
            textAnchor="middle" fontFamily="monospace">
            {x >= 0 ? `+${x}%` : `${x}%`}
          </text>
        ))}

        {/* Axis titles */}
        <text x={ML + CW / 2} y={VH - 2} fontSize="8" fill="var(--text-0)" textAnchor="middle" fontFamily="monospace" letterSpacing="0.08em">
          UNREALIZED RETURN
        </text>
        <text x={10} y={MT + CH / 2} fontSize="8" fill="var(--text-0)" textAnchor="middle" fontFamily="monospace"
          transform={`rotate(-90, 10, ${MT + CH / 2})`} letterSpacing="0.08em">
          POSITION SIZE
        </text>

        {/* Bubbles — render all non-hovered first, then hovered on top */}
        {[false, true].map((renderHov) =>
          positions.map((pos) => {
            const key = `${pos.portfolio_id}-${pos.ticker}`;
            const isHov = hovered === key;
            if (renderHov !== isHov) return null;
            const cx = xs(pos.pnl_pct);
            const cy = ys(pos.market_value ?? 0);
            const color = portfolioColors[pos.portfolio_id] ?? "#818cf8";
            const showLabel = topKeys.has(key) || isHov;
            return (
              <g key={key} style={{ cursor: "pointer" }}
                onMouseEnter={() => setHovered(key)}
                onMouseLeave={() => setHovered(null)}
              >
                {isHov && (
                  <circle cx={cx} cy={cy} r="14"
                    fill={color} fillOpacity="0.12" stroke={color} strokeOpacity="0.3" strokeWidth="1" />
                )}
                <circle cx={cx} cy={cy} r={isHov ? 8 : 5.5}
                  fill={color} fillOpacity={isHov ? 0.95 : 0.7}
                  stroke={color} strokeOpacity={0.5} strokeWidth={isHov ? 1.5 : 1}
                  style={{ transition: "r 0.12s" }}
                />
                {showLabel && (
                  <text x={cx} y={pos.pnl_pct >= 0 || cy > VH - MB - 28 ? cy - 10 : cy + 18} fontSize="8.5" fontWeight="700"
                    fill="var(--text-3)" textAnchor="middle" fontFamily="monospace">
                    {pos.ticker}
                  </text>
                )}
              </g>
            );
          })
        )}

        {/* SVG tooltip */}
        {hoveredPos && (() => {
          const cx = xs(hoveredPos.pnl_pct);
          const cy = ys(hoveredPos.market_value ?? 0);
          const mv = hoveredPos.market_value ?? 0;
          const tx = cx > VW * 0.72 ? cx - 126 : cx + 14;
          const ty = cy > VH * 0.65 ? cy - 58 : cy + 10;
          return (
            <g>
              <rect x={tx} y={ty} width="120" height="50" rx="4"
                fill="var(--bg-elevated)" stroke="var(--border-1)" strokeWidth="1" />
              <text x={tx + 8} y={ty + 15} fontSize="10.5" fontWeight="700"
                fill="var(--text-3)" fontFamily="monospace">{hoveredPos.ticker}</text>
              <text x={tx + 8} y={ty + 27} fontSize="9"
                fill={hoveredPos.pnl_pct >= 0 ? "var(--green)" : "var(--red)"}
                fontFamily="monospace">
                {fmtPct(hoveredPos.pnl_pct)} · {fmt$(hoveredPos.pnl, 0)}
              </text>
              <text x={tx + 8} y={ty + 39} fontSize="8.5" fill="var(--text-0)" fontFamily="monospace">
                ${mv.toLocaleString(undefined, { maximumFractionDigits: 0 })} · {hoveredPos.portfolio_id}
              </text>
            </g>
          );
        })()}
      </svg>

      {/* Portfolio legend */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", paddingLeft: "4px", marginTop: "2px" }}>
        {portfolioEntries.map(([id, color]) => (
          <div key={id} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <svg width="10" height="10" viewBox="0 0 10 10">
              <circle cx="5" cy="5" r="4" fill={color} fillOpacity="0.8" />
            </svg>
            <span style={{ fontSize: "9px", color: "var(--text-0)", fontFamily: "var(--font-mono)" }}>{id}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── All Positions Panel (container with toggle) ───────────────────────────────

function AllPositionsPanel({ positions }: { positions: CrossPortfolioMover[] }) {
  const [view, setView] = useState<ViewMode>("map");
  const portfolioColors = usePortfolioColors(positions);

  if (positions.length === 0) return null;

  return (
    <div style={{ marginTop: "16px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "7px" }}>
        <p style={{ fontSize: "9.5px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)" }}>
          All Positions — {positions.length}
        </p>
        <div style={{ display: "flex", gap: "2px", background: "var(--surface-1)", border: "1px solid var(--border-0)", borderRadius: "5px", padding: "2px" }}>
          {(["map", "plot"] as ViewMode[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              style={{
                fontSize: "9px", fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase",
                padding: "3px 10px", borderRadius: "3px", border: "none", cursor: "pointer",
                background: view === v ? "var(--accent)" : "transparent",
                color: view === v ? "white" : "var(--text-0)",
                transition: "background 0.15s, color 0.15s",
              }}
            >
              {v === "map" ? "MAP" : "PLOT"}
            </button>
          ))}
        </div>
      </div>
      {view === "map"
        ? <WeightedMap positions={positions} portfolioColors={portfolioColors} />
        : <ScatterPlot positions={positions} portfolioColors={portfolioColors} />
      }
    </div>
  );
}

// ---------------------------------------------------------------------------
// Aggregate header bar
// ---------------------------------------------------------------------------

function AggregateBar({
  totalEquity, totalCash, totalDayPnl, totalUnrealizedPnl, totalAllTimePnl, totalPositions, portfolioCount, onNewPortfolio,
  onUpdateAll, updatingAll, updateResult,
}: {
  totalEquity: number; totalCash: number; totalDayPnl: number;
  totalUnrealizedPnl: number; totalAllTimePnl: number; totalPositions: number; portfolioCount: number;
  onNewPortfolio: () => void;
  onUpdateAll: () => void;
  updatingAll: boolean;
  updateResult: string | null;
}) {
  // 0 decimals → then format with commas
  const rawCount = useCountUp(totalEquity, 1200, 0);
  const animatedEquity = Number(rawCount).toLocaleString();

  function StatChip({ label, value, color }: { label: string; value: string; color?: string }) {
    return (
      <div className="shrink-0">
        <p style={{ fontSize: "9.5px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", marginBottom: "3px" }}>
          {label}
        </p>
        <p className="font-mono tabular-nums" style={{ fontSize: "15px", fontWeight: 600, color: color ?? "var(--text-3)" }}>
          {value}
        </p>
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-6 px-6 shrink-0"
      style={{ background: "var(--surface-1)", borderBottom: "1px solid var(--border-0)", minHeight: "68px" }}
    >
      <div className="shrink-0">
        <p style={{ fontSize: "9.5px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", marginBottom: "3px" }}>
          Total Equity
        </p>
        <p className="font-mono font-bold tabular-nums" style={{ fontSize: "26px", color: "var(--text-4)", letterSpacing: "-0.02em" }}>
          ${animatedEquity}
        </p>
      </div>
      <div className="h-8 w-px shrink-0" style={{ background: "var(--border-1)" }} />
      <StatChip label="All-Time P&L" value={fmt$(totalAllTimePnl)} color={pnlColor(totalAllTimePnl)} />
      <StatChip label="Unrealized P&L" value={fmt$(totalUnrealizedPnl)} color={pnlColor(totalUnrealizedPnl)} />
      <StatChip label="Day P&L" value={fmt$(totalDayPnl)} color={pnlColor(totalDayPnl)} />
      <StatChip label="Cash" value={`$${totalCash.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
      <StatChip label="Positions" value={String(totalPositions)} />
      <StatChip label="Portfolios" value={String(portfolioCount)} />
      <div style={{ marginLeft: "auto", display: "flex", gap: "8px", alignItems: "center" }}>
        <button
          onClick={onUpdateAll}
          disabled={updatingAll}
          style={{
            display: "inline-flex", alignItems: "center", gap: "5px",
            padding: "0 12px", height: "28px",
            background: "transparent",
            border: "1px solid var(--border-1)",
            borderRadius: "6px",
            color: updatingAll ? "var(--accent)" : "var(--text-1)",
            fontSize: "11px", fontWeight: 600,
            letterSpacing: "0.06em", textTransform: "uppercase",
            cursor: updatingAll ? "not-allowed" : "pointer",
            transition: "border-color 0.15s, color 0.15s",
            opacity: updatingAll ? 0.75 : 1,
          }}
          onMouseEnter={(e) => {
            if (!updatingAll) {
              e.currentTarget.style.borderColor = "var(--accent)";
              e.currentTarget.style.color = "var(--accent)";
            }
          }}
          onMouseLeave={(e) => {
            if (!updatingAll) {
              e.currentTarget.style.borderColor = "var(--border-1)";
              e.currentTarget.style.color = "var(--text-1)";
            }
          }}
        >
          <svg
            width="11" height="11" viewBox="0 0 12 12" fill="none"
            style={{ flexShrink: 0 }}
            className={updatingAll ? "animate-spin" : ""}
          >
            <path
              d="M10 6A4 4 0 1 1 6 2a4 4 0 0 1 2.83 1.17L10 2v4H6"
              stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"
            />
          </svg>
          {updateResult ?? "Update All"}
        </button>
        <button
          onClick={onNewPortfolio}
          style={{
            display: "inline-flex", alignItems: "center", gap: "5px",
            padding: "0 12px", height: "28px",
            background: "transparent",
            border: "1px solid var(--border-1)",
            borderRadius: "6px",
            color: "var(--text-1)",
            fontSize: "11px", fontWeight: 600,
            letterSpacing: "0.06em", textTransform: "uppercase",
            cursor: "pointer", transition: "border-color 0.15s, color 0.15s",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.color = "var(--accent)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-1)"; e.currentTarget.style.color = "var(--text-1)"; }}
        >
          + New Portfolio
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Portfolio card
// ---------------------------------------------------------------------------

function PortfolioCard({ summary, totalEquity }: { summary: PortfolioSummary; totalEquity: number }) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => api.deletePortfolio(summary.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      setConfirmDelete(false);
    },
  });

  const regimeColor =
    summary.regime === "BULL" ? "var(--green)"
    : summary.regime === "BEAR" ? "var(--red)"
    : "var(--amber)";

  const sharePct = totalEquity > 0 ? (summary.equity / totalEquity) * 100 : 0;
  const glow = !summary.error ? cardGlow(summary.total_return_pct ?? 0) : "none";
  const hasSparkline = (summary.sparkline?.length ?? 0) >= 2;

  return (
    <div
      style={{
        position: "relative",
        background: "var(--surface-1)",
        border: "1px solid var(--border-0)",
        borderRadius: "8px",
        boxShadow: glow,
        transition: "box-shadow 0.3s ease, border-color 0.3s ease",
        overflow: "hidden",
      }}
    >
      {/* Delete */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (confirmDelete) deleteMutation.mutate();
          else setConfirmDelete(true);
        }}
        style={{
          position: "absolute", top: "8px", right: "8px", zIndex: 10,
          fontSize: "10px", padding: "2px 6px", background: "none", border: "none",
          color: confirmDelete ? "var(--red)" : "transparent",
          fontWeight: confirmDelete ? 600 : 400, cursor: "pointer",
        }}
        onMouseEnter={(e) => { if (!confirmDelete) e.currentTarget.style.color = "rgba(248,113,113,0.50)"; }}
        onMouseLeave={(e) => { if (!confirmDelete) e.currentTarget.style.color = "transparent"; }}
      >
        {deleteMutation.isPending ? "..." : confirmDelete ? "Confirm?" : "×"}
      </button>

      {/* Clickable body */}
      <button
        onClick={() => setPortfolio(summary.id)}
        style={{ width: "100%", textAlign: "left", padding: "14px 14px 0", background: "none", border: "none", cursor: "pointer" }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "10px", paddingRight: "16px" }}>
          <h3 style={{ flex: 1, fontSize: "13px", fontWeight: 700, color: "var(--text-4)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {summary.name}
          </h3>
          <span style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-0)" }}>
            {summary.universe}
          </span>
          <span style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600, color: summary.paper_mode ? "var(--amber)" : "var(--accent)" }}>
            {summary.paper_mode ? "Paper" : "Live"}
          </span>
        </div>

        {summary.error ? (
          <div style={{ fontSize: "12px", color: "var(--red)", paddingBottom: "14px" }}>{summary.error}</div>
        ) : (
          <>
            {/* Equity + return */}
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginBottom: "6px" }}>
              <span className="font-mono font-semibold tabular-nums" style={{ fontSize: "20px", color: "var(--text-3)" }}>
                ${summary.equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
              <span className="font-mono font-semibold tabular-nums" style={{ fontSize: "12px", color: pnlColor(summary.total_return_pct) }}>
                {fmtPct(summary.total_return_pct)}
              </span>
            </div>

            {/* P&L row */}
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px", fontSize: "11px" }}>
              <span style={{ color: "var(--text-0)" }}>All-time</span>
              <span className="font-mono tabular-nums" style={{ color: pnlColor(summary.all_time_pnl ?? 0), fontWeight: 600 }}>{fmt$(summary.all_time_pnl ?? 0)}</span>
              <span style={{ color: "var(--border-1)" }}>·</span>
              <span style={{ color: "var(--text-0)" }}>Day</span>
              <span className="font-mono tabular-nums" style={{ color: pnlColor(summary.day_pnl) }}>{fmt$(summary.day_pnl)}</span>
              <span style={{ color: "var(--border-1)" }}>·</span>
              <span style={{ color: "var(--text-0)" }}>Open</span>
              <span className="font-mono tabular-nums" style={{ color: pnlColor(summary.unrealized_pnl) }}>{fmt$(summary.unrealized_pnl)}</span>
            </div>
          </>
        )}
      </button>

      {/* Sparkline strip — full-width, below the P&L row */}
      {!summary.error && hasSparkline && (
        <div style={{
          borderTop: "1px solid var(--border-0)",
          borderBottom: "1px solid var(--border-0)",
          background: "var(--surface-0)",
          height: "40px",
          overflow: "hidden",
        }}>
          <EquitySparkline values={summary.sparkline!} returnPct={summary.total_return_pct ?? 0} />
        </div>
      )}

      {/* Bottom stats */}
      {!summary.error && (
        <div
          style={{ padding: "8px 14px 10px", display: "flex", alignItems: "center", gap: "8px", fontSize: "10.5px", color: "var(--text-1)" }}
          onClick={() => setPortfolio(summary.id)}
        >
          {/* Deployment bar */}
          <div style={{ flex: 1, height: "3px", borderRadius: "2px", background: "var(--surface-3)", overflow: "hidden" }}>
            <div style={{
              height: "100%", borderRadius: "2px",
              width: `${Math.min(100, sharePct)}%`,
              background: "linear-gradient(to right, var(--accent), var(--accent-bright))",
            }} />
          </div>
          <span className="tabular-nums">{summary.num_positions}p</span>
          <span style={{ color: "var(--border-2)" }}>·</span>
          <span className="tabular-nums">{summary.deployed_pct.toFixed(0)}% dep</span>
          <span style={{ color: "var(--border-2)" }}>·</span>
          <span className="tabular-nums">${summary.cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
          {summary.regime && (
            <>
              <span style={{ color: "var(--border-2)" }}>·</span>
              <span style={{ color: regimeColor, fontWeight: 600 }}>{summary.regime}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Movers list
// ---------------------------------------------------------------------------

function MoverRow({ mover }: { mover: CrossPortfolioMover }) {
  const color = pnlColor(mover.pnl_pct);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", padding: "5px 0", borderBottom: "1px solid var(--border-0)" }}>
      <span style={{ fontWeight: 700, width: "38px", flexShrink: 0, color: "var(--text-4)", fontFamily: "var(--font-mono)" }}>
        {mover.ticker}
      </span>
      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--text-1)" }}>
        {mover.portfolio_name}
      </span>
      <span className="font-mono tabular-nums" style={{ color, fontWeight: 600 }}>
        {fmtPct(mover.pnl_pct)}
      </span>
      <span className="font-mono tabular-nums" style={{ color, width: "56px", textAlign: "right" }}>
        {fmt$(mover.pnl)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Capital allocation bar
// ---------------------------------------------------------------------------

function AllocationBar({ name, equity, totalEquity }: { name: string; equity: number; totalEquity: number }) {
  const pct = totalEquity > 0 ? (equity / totalEquity) * 100 : 0;
  return (
    <div style={{ marginBottom: "10px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px", fontSize: "10.5px" }}>
        <span style={{ color: "var(--text-2)" }}>{name}</span>
        <span className="font-mono tabular-nums" style={{ color: "var(--text-1)" }}>{pct.toFixed(1)}%</span>
      </div>
      <div style={{ height: "4px", borderRadius: "2px", background: "var(--surface-3)", overflow: "hidden" }}>
        <div style={{
          height: "100%", borderRadius: "2px",
          width: `${Math.min(100, pct)}%`,
          background: "linear-gradient(to right, var(--accent), var(--accent-bright))",
        }} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const sectionLabel: React.CSSProperties = {
  fontSize: "9.5px", fontWeight: 600, textTransform: "uppercase",
  letterSpacing: "0.08em", color: "var(--text-0)", marginBottom: "8px",
};

export default function OverviewPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [updatingAll, setUpdatingAll] = useState(false);
  const [updateResult, setUpdateResult] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { data: overview, isLoading } = useOverview();
  const { data: portfolioList } = usePortfolios();

  const handleUpdateAll = async () => {
    const ids = (portfolioList?.portfolios ?? []).filter((p) => p.active).map((p) => p.id);
    if (ids.length === 0) return;
    setUpdatingAll(true);
    setUpdateResult(null);
    let done = 0;
    setUpdateResult(`0 / ${ids.length}`);
    await Promise.allSettled(
      ids.map((pid) =>
        api.updatePrices(pid).then(() => {
          done += 1;
          setUpdateResult(`${done} / ${ids.length}`);
        })
      )
    );
    queryClient.invalidateQueries({ queryKey: ["overview"] });
    setUpdateResult(`${ids.length} updated`);
    setTimeout(() => setUpdateResult(null), 3000);
    setUpdatingAll(false);
  };

  if (isLoading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--surface-0)" }}>
        <p className="animate-pulse" style={{ color: "var(--text-1)" }}>Loading portfolios...</p>
      </div>
    );
  }

  const summaries = overview?.portfolios ?? [];
  const names = new Map((portfolioList?.portfolios ?? []).map((p) => [p.id, p.name]));
  const enriched = summaries.map((s) => ({ ...s, name: s.name || names.get(s.id) || s.id }));
  const validSummaries = enriched.filter((s) => !s.error);
  const totalEquity = overview?.total_equity ?? 0;
  const topMovers = overview?.top_movers ?? [];
  const bottomMovers = overview?.bottom_movers ?? [];
  const allPositions = overview?.all_positions ?? [];

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--surface-0)" }}>
      <AggregateBar
        totalEquity={totalEquity}
        totalCash={overview?.total_cash ?? 0}
        totalDayPnl={overview?.total_day_pnl ?? 0}
        totalUnrealizedPnl={overview?.total_unrealized_pnl ?? 0}
        totalAllTimePnl={overview?.total_all_time_pnl ?? 0}
        totalPositions={overview?.total_positions ?? 0}
        portfolioCount={enriched.length}
        onNewPortfolio={() => setShowCreate(true)}
        onUpdateAll={handleUpdateAll}
        updatingAll={updatingAll}
        updateResult={updateResult}
      />

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Left: portfolio grid + heatmap */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
          {enriched.length === 0 ? (
            <div style={{ textAlign: "center", padding: "64px 0", color: "var(--text-1)" }}>
              <p style={{ fontSize: "18px", marginBottom: "8px" }}>No portfolios yet</p>
              <p style={{ fontSize: "13px" }}>Create your first portfolio to get started.</p>
            </div>
          ) : (
            <>
              <div style={{ display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
                {enriched.map((s, i) => (
                  <div key={s.id} className={`anim d${Math.min(i + 1, 5)}`}>
                    <PortfolioCard summary={s} totalEquity={totalEquity} />
                  </div>
                ))}
              </div>

              <AllPositionsPanel positions={allPositions} />
            </>
          )}
        </div>

        {/* Right panel */}
        <aside style={{ width: "260px", flexShrink: 0, overflowY: "auto", borderLeft: "1px solid var(--border-0)", padding: "16px", background: "var(--surface-1)" }}>
          {validSummaries.length > 0 && (
            <div style={{ marginBottom: "20px" }}>
              <p style={sectionLabel}>Capital Allocation</p>
              {validSummaries.map((s) => (
                <AllocationBar key={s.id} name={s.name} equity={s.equity} totalEquity={totalEquity} />
              ))}
            </div>
          )}

          {topMovers.length > 0 && (
            <div style={{ marginBottom: "20px" }}>
              <p style={{ ...sectionLabel, color: "var(--green)" }}>Top Movers</p>
              {topMovers.map((m) => (
                <MoverRow key={`${m.portfolio_id}-${m.ticker}`} mover={m} />
              ))}
            </div>
          )}

          {bottomMovers.length > 0 && (
            <div>
              <p style={{ ...sectionLabel, color: "var(--red)" }}>Bottom Movers</p>
              {bottomMovers.map((m) => (
                <MoverRow key={`${m.portfolio_id}-${m.ticker}`} mover={m} />
              ))}
            </div>
          )}

          {topMovers.length === 0 && bottomMovers.length === 0 && validSummaries.length > 0 && (
            <p style={{ fontSize: "11px", color: "var(--text-0)" }}>No open positions to show movers for.</p>
          )}
        </aside>
      </div>

      {showCreate && <CreatePortfolioModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
