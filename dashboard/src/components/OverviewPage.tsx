/** Overview page — shown when activePortfolioId === "overview". */

import { useMemo, useState, useRef, useEffect, lazy, Suspense } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOverview, usePortfolios } from "../hooks/usePortfolios";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import { useCountUp } from "../hooks/useCountUp";
import type { PortfolioSummary, CrossPortfolioMover } from "../lib/types";
import type { ScanJobStatus } from "../lib/types";
import CreatePortfolioModal from "./CreatePortfolioModal";
import { play } from "../lib/sounds";

const ConstellationMap = lazy(() => import("./ConstellationMap"));
const PerformanceChart = lazy(() => import("./PerformanceChart"));

// ---------------------------------------------------------------------------
// Scan-all types
// ---------------------------------------------------------------------------

interface ScanAllPortfolioResult {
  status: "running" | "complete" | "error";
  added: number;
  active: number;
  error: string | null;
}

interface ScanAllState {
  running: boolean;
  currentId: string | null;
  results: Record<string, ScanAllPortfolioResult>;
}

type SortKey = "day_pnl" | "total_return_pct" | "equity" | "deployed_pct" | "name";
type ViewMode = "grid" | "map" | "chart";

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

function EquitySparkline({ values, returnPct, id }: { values: number[]; returnPct: number; id: string }) {
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
  const gradId = `sparkgrad-${id}`;

  return (
    <svg
      width="100%" height={H}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      style={{ display: "block" }}
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={color} stopOpacity="0.01" />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${H} ${points} ${W},${H}`}
        fill={`url(#${gradId})`}
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
// Morning Briefing headline + stats row
// ---------------------------------------------------------------------------

function MorningBriefing({
  totalEquity, totalDayPnl, totalReturnPct, totalPositions, portfolioCount,
  onNewPortfolio, onUpdateAll, updatingAll, updateResult, onScanAll, scanAllRunning, scanAllLabel,
}: {
  totalEquity: number; totalDayPnl: number; totalReturnPct: number;
  totalPositions: number; portfolioCount: number;
  onNewPortfolio: () => void;
  onUpdateAll: () => void;
  updatingAll: boolean;
  updateResult: string | null;
  onScanAll: () => void;
  scanAllRunning: boolean;
  scanAllLabel: string | null;
}) {
  const rawCount = useCountUp(totalEquity, 1200, 0);
  const animatedEquity = Number(rawCount).toLocaleString();

  const dayColor = pnlColor(totalDayPnl);
  const daySign  = totalDayPnl >= 0 ? "+" : "";
  const dayPct   = totalEquity > 0 ? (totalDayPnl / totalEquity) * 100 : 0;

  // Headline narrative
  const headline = portfolioCount === 0
    ? "No portfolios yet. Create one to get started."
    : `${portfolioCount} portfolio${portfolioCount !== 1 ? "s" : ""}, ${totalPositions} position${totalPositions !== 1 ? "s" : ""} · $${Number(rawCount).toLocaleString()} total equity`;

  return (
    <div style={{
      background: "var(--bg-surface)",
      borderBottom: "1px solid var(--border)",
      padding: "16px 20px 12px",
      flexShrink: 0,
    }}>
      {/* Narrative headline */}
      <div style={{ marginBottom: "14px" }}>
        <p style={{
          fontSize: "20px", fontWeight: 600, color: "var(--text-primary)",
          fontFamily: "var(--font-sans)", lineHeight: 1.2, marginBottom: "3px",
        }}>
          Morning Briefing
        </p>
        <p style={{ fontSize: "13px", color: "var(--text-secondary)", fontFamily: "var(--font-sans)" }}>
          {headline}
          {totalDayPnl !== 0 && totalEquity > 0 && (
            <span style={{ color: dayColor, marginLeft: "8px", fontFamily: "var(--font-mono)" }}>
              {daySign}${Math.abs(totalDayPnl).toLocaleString(undefined, { maximumFractionDigits: 0 })} ({daySign}{Math.abs(dayPct).toFixed(1)}%) today
            </span>
          )}
        </p>
      </div>

      {/* Stats row */}
      <div style={{ display: "flex", gap: "10px", alignItems: "stretch", flexWrap: "wrap" }}>
        {/* Total Equity */}
        <div style={{
          background: "var(--bg-elevated)", border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)", padding: "16px 20px", minWidth: "140px",
        }}>
          <p style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-dim)", fontWeight: 500, marginBottom: "6px" }}>
            Total Equity
          </p>
          <p className="font-mono tabular-nums" style={{ fontSize: "24px", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", lineHeight: 1 }}>
            ${animatedEquity}
          </p>
        </div>

        {/* Today's P&L */}
        <div style={{
          background: totalDayPnl > 0 ? "var(--green-dim)" : totalDayPnl < 0 ? "var(--red-dim)" : "var(--bg-elevated)",
          border: `1px solid ${totalDayPnl > 0 ? "rgba(34,197,94,0.18)" : totalDayPnl < 0 ? "rgba(239,68,68,0.18)" : "var(--border)"}`,
          borderRadius: "var(--radius-lg)", padding: "16px 20px", minWidth: "130px",
        }}>
          <p style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-dim)", fontWeight: 500, marginBottom: "6px" }}>
            Today's P&L
          </p>
          <p className="font-mono tabular-nums" style={{ fontSize: "24px", fontWeight: 700, color: dayColor, letterSpacing: "-0.02em", lineHeight: 1 }}>
            {fmt$(totalDayPnl)}
          </p>
        </div>

        {/* Total Positions */}
        <div style={{
          background: "var(--bg-elevated)", border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)", padding: "16px 20px", minWidth: "100px",
        }}>
          <p style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-dim)", fontWeight: 500, marginBottom: "6px" }}>
            Positions
          </p>
          <p className="font-mono tabular-nums" style={{ fontSize: "24px", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", lineHeight: 1 }}>
            {totalPositions}
          </p>
        </div>

        {/* Portfolios */}
        <div style={{
          background: "var(--bg-elevated)", border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)", padding: "16px 20px", minWidth: "100px",
        }}>
          <p style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-dim)", fontWeight: 500, marginBottom: "6px" }}>
            Portfolios
          </p>
          <p className="font-mono tabular-nums" style={{ fontSize: "24px", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", lineHeight: 1 }}>
            {portfolioCount}
          </p>
        </div>

        {/* Return */}
        <div style={{
          background: "var(--bg-elevated)", border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)", padding: "16px 20px", minWidth: "110px",
        }}>
          <p style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-dim)", fontWeight: 500, marginBottom: "6px" }}>
            All-Time Return
          </p>
          <p className="font-mono tabular-nums" style={{ fontSize: "24px", fontWeight: 700, color: pnlColor(totalReturnPct), letterSpacing: "-0.02em", lineHeight: 1 }}>
            {fmtPct(totalReturnPct)}
          </p>
        </div>

        {/* Action buttons — flush right */}
        <div style={{
          marginLeft: "auto",
          display: "flex", gap: "8px", alignItems: "center",
        }}>
          <ActionBtn onClick={onUpdateAll} disabled={updatingAll} spinning={updatingAll}>
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none" style={{ flexShrink: 0 }} className={updatingAll ? "animate-spin" : ""}>
              <path d="M10 6A4 4 0 1 1 6 2a4 4 0 0 1 2.83 1.17L10 2v4H6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {updateResult ?? "Update All"}
          </ActionBtn>
          <ActionBtn onClick={onScanAll} disabled={scanAllRunning}>
            <span style={{
              width: "6px", height: "6px", borderRadius: "50%",
              background: "currentColor", opacity: scanAllRunning ? 1 : 0.6, flexShrink: 0,
              animation: scanAllRunning ? "pulse 1s ease-in-out infinite" : "none",
            }} />
            {scanAllLabel ?? "Scan All"}
          </ActionBtn>
          <ActionBtn onClick={onNewPortfolio}>
            + New
          </ActionBtn>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Aggregate header bar (kept for backwards compat reference — not rendered)
// ---------------------------------------------------------------------------

function AggregateBar({
  totalEquity, totalCash, totalDayPnl, totalAllTimePnl, totalReturnPct, totalPositions, portfolioCount,
  portfoliosUp, portfoliosDown, deployedPct,
  onNewPortfolio, onUpdateAll, updatingAll, updateResult, onScanAll, scanAllRunning, scanAllLabel,
}: {
  totalEquity: number; totalCash: number; totalDayPnl: number;
  totalAllTimePnl: number; totalReturnPct: number; totalPositions: number; portfolioCount: number;
  portfoliosUp: number; portfoliosDown: number; deployedPct: number;
  onNewPortfolio: () => void;
  onUpdateAll: () => void;
  updatingAll: boolean;
  updateResult: string | null;
  onScanAll: () => void;
  scanAllRunning: boolean;
  scanAllLabel: string | null;
}) {
  const rawCount = useCountUp(totalEquity, 1200, 0);
  const animatedEquity = Number(rawCount).toLocaleString();

  /** Secondary stat — clearly subordinate to the hero numbers */
  function SecondaryChip({ label, value, color }: { label: string; value: string; color?: string }) {
    return (
      <div className="shrink-0" style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: "1px" }}>
        <p style={{ fontSize: "8px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", lineHeight: 1 }}>
          {label}
        </p>
        <p className="font-mono tabular-nums" style={{ fontSize: "11px", fontWeight: 500, color: color ?? "var(--text-2)", lineHeight: 1.2 }}>
          {value}
        </p>
      </div>
    );
  }

  const dayColor = pnlColor(totalDayPnl);
  const atColor  = pnlColor(totalAllTimePnl);

  return (
    <div
      className="flex items-center gap-4 px-4 shrink-0 flex-wrap"
      style={{ background: "var(--surface-1)", borderBottom: "1px solid var(--border-0)", minHeight: "48px", height: "48px" }}
    >
      {/* Hero 1: Total Equity */}
      <div className="shrink-0" style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: "1px" }}>
        <p style={{ fontSize: "8px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", lineHeight: 1 }}>
          Total Equity
        </p>
        <p className="font-mono font-bold tabular-nums" style={{ fontSize: "20px", color: "var(--text-4)", letterSpacing: "-0.02em", lineHeight: 1.1 }}>
          ${animatedEquity}
        </p>
      </div>

      <div className="w-px shrink-0" style={{ height: "28px", background: "var(--border-1)" }} />

      {/* Hero 2: Day P&L — tinted inline chip */}
      <div
        className="shrink-0"
        style={{
          display: "flex", flexDirection: "column", justifyContent: "center", gap: "1px",
          padding: "3px 8px",
          borderRadius: "5px",
          background: totalDayPnl > 0
            ? "rgba(52,211,153,0.07)"
            : totalDayPnl < 0
              ? "rgba(248,113,113,0.07)"
              : "var(--surface-2)",
          border: `1px solid ${totalDayPnl > 0 ? "rgba(52,211,153,0.15)" : totalDayPnl < 0 ? "rgba(248,113,113,0.15)" : "var(--border-0)"}`,
        }}
      >
        <p style={{ fontSize: "8px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", lineHeight: 1 }}>Day P&L</p>
        <p className="font-mono tabular-nums" style={{ fontSize: "16px", fontWeight: 800, color: dayColor, letterSpacing: "-0.01em", lineHeight: 1.15 }}>
          {fmt$(totalDayPnl)}
        </p>
      </div>

      <div className="w-px shrink-0" style={{ height: "28px", background: "var(--border-1)" }} />

      {/* Secondary tier — clearly smaller */}
      <SecondaryChip label="All-Time" value={`${fmt$(totalAllTimePnl)} (${fmtPct(totalReturnPct)})`} color={atColor} />

      {/* Portfolio Up/Down — renamed from "Today" */}
      <div className="shrink-0" style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: "1px" }}>
        <p style={{ fontSize: "8px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", lineHeight: 1 }}>Portfolios</p>
        <p className="font-mono tabular-nums" style={{ fontSize: "11px", fontWeight: 500, lineHeight: 1.2 }}>
          <span style={{ color: "var(--green)" }}>{portfoliosUp}↑</span>
          {" "}
          <span style={{ color: "var(--text-0)" }}>/</span>
          {" "}
          <span style={{ color: portfoliosDown > 0 ? "var(--red)" : "var(--text-0)" }}>{portfoliosDown}↓</span>
        </p>
      </div>

      {/* Deployed % */}
      <div className="shrink-0" style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: "1px" }}>
        <p style={{ fontSize: "8px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", lineHeight: 1 }}>Deployed</p>
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <p className="font-mono tabular-nums" style={{ fontSize: "11px", fontWeight: 500, color: "var(--text-2)", lineHeight: 1.2 }}>
            {deployedPct.toFixed(0)}%
          </p>
          <div style={{ width: "36px", height: "3px", borderRadius: "2px", background: "var(--surface-3)", overflow: "hidden" }}>
            <div style={{
              height: "100%", borderRadius: "2px",
              width: `${Math.min(100, deployedPct)}%`,
              background: "linear-gradient(to right, var(--accent), var(--accent-bright))",
            }} />
          </div>
        </div>
      </div>

      <SecondaryChip label="Cash" value={`$${totalCash.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
      <SecondaryChip label="Positions" value={String(totalPositions)} />

      {/* Actions — clearly separated from the data surface */}
      <div style={{
        marginLeft: "auto",
        display: "flex", gap: "8px", alignItems: "center",
        paddingLeft: "16px",
        borderLeft: "1px solid var(--border-1)",
      }}>
        <ActionBtn onClick={onUpdateAll} disabled={updatingAll} spinning={updatingAll}>
          <svg width="11" height="11" viewBox="0 0 12 12" fill="none" style={{ flexShrink: 0 }} className={updatingAll ? "animate-spin" : ""}>
            <path d="M10 6A4 4 0 1 1 6 2a4 4 0 0 1 2.83 1.17L10 2v4H6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {updateResult ?? "Update All"}
        </ActionBtn>
        <ActionBtn onClick={onScanAll} disabled={scanAllRunning}>
          <span style={{
            width: "6px", height: "6px", borderRadius: "50%",
            background: "currentColor", opacity: scanAllRunning ? 1 : 0.6, flexShrink: 0,
            animation: scanAllRunning ? "pulse 1s ease-in-out infinite" : "none",
          }} />
          {scanAllLabel ?? "Scan All"}
        </ActionBtn>
        <ActionBtn onClick={onNewPortfolio}>
          + New
        </ActionBtn>
      </div>
    </div>
  );
}

function ActionBtn({ onClick, disabled, spinning, children }: {
  onClick: () => void;
  disabled?: boolean;
  spinning?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "inline-flex", alignItems: "center", gap: "5px",
        padding: "0 12px", height: "28px",
        background: "transparent",
        border: "1px solid var(--border-1)",
        borderRadius: "6px",
        color: (disabled && !spinning) ? "var(--accent)" : "var(--text-1)",
        fontSize: "11px", fontWeight: 600,
        letterSpacing: "0.06em", textTransform: "uppercase",
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "border-color 0.15s, color 0.15s",
        opacity: disabled ? 0.75 : 1,
        whiteSpace: "nowrap",
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.borderColor = "var(--accent)";
          e.currentTarget.style.color = "var(--accent)";
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          e.currentTarget.style.borderColor = "var(--border-1)";
          e.currentTarget.style.color = "var(--text-1)";
        }
      }}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Sort + View controls bar
// ---------------------------------------------------------------------------

function ControlsBar({
  sortKey, onSort, viewMode, onView,
}: {
  sortKey: SortKey;
  onSort: (k: SortKey) => void;
  viewMode: ViewMode;
  onView: (v: ViewMode) => void;
}) {
  const sortOptions: { key: SortKey; label: string }[] = [
    { key: "day_pnl",          label: "Day P&L" },
    { key: "total_return_pct", label: "Return" },
    { key: "equity",           label: "Equity" },
    { key: "deployed_pct",     label: "Deployed" },
    { key: "name",             label: "Name" },
  ];
  const viewOptions: { key: ViewMode; label: string }[] = [
    { key: "grid",  label: "Grid" },
    { key: "map",   label: "Map" },
    { key: "chart", label: "Chart" },
  ];

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: "12px",
      padding: "8px 20px",
      background: "var(--bg-void)",
      borderBottom: "1px solid var(--border)",
      flexShrink: 0,
    }}>
      {/* Sort controls */}
      <span style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)" }}>Sort</span>
      <div style={{ display: "flex", gap: "4px" }}>
        {sortOptions.map((opt) => (
          <button
            key={opt.key}
            onClick={() => onSort(opt.key)}
            style={{
              padding: "3px 9px",
              borderRadius: "4px",
              fontSize: "10px", fontWeight: sortKey === opt.key ? 700 : 500,
              color: sortKey === opt.key ? "var(--accent)" : "var(--text-secondary)",
              background: sortKey === opt.key ? "rgba(124,92,252,0.10)" : "transparent",
              border: sortKey === opt.key ? "1px solid rgba(124,92,252,0.25)" : "1px solid transparent",
              cursor: "pointer",
              transition: "all 0.15s",
            }}
          >
            {opt.label}{sortKey === opt.key && opt.key !== "name" ? " ↓" : ""}
          </button>
        ))}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* View toggle */}
      <span style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)" }}>View</span>
      <div style={{ display: "flex", gap: "2px", background: "var(--bg-elevated)", borderRadius: "6px", padding: "2px" }}>
        {viewOptions.map((opt) => (
          <button
            key={opt.key}
            onClick={() => onView(opt.key)}
            style={{
              padding: "3px 12px",
              borderRadius: "4px",
              fontSize: "10px", fontWeight: viewMode === opt.key ? 700 : 500,
              color: viewMode === opt.key ? "var(--text-primary)" : "var(--text-secondary)",
              background: viewMode === opt.key ? "var(--accent-dim)" : "transparent",
              border: "none",
              cursor: "pointer",
              transition: "all 0.15s",
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Portfolio card
// ---------------------------------------------------------------------------

function PortfolioCard({ summary, totalEquity, scanResult, topHoldings }: {
  summary: PortfolioSummary;
  totalEquity: number;
  scanResult?: ScanAllPortfolioResult;
  topHoldings: CrossPortfolioMover[];
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [hovered, setHovered] = useState(false);
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

  const glow = !summary.error ? cardGlow(summary.total_return_pct ?? 0) : "none";
  const hasSparkline = (summary.sparkline?.length ?? 0) >= 2;

  const cardBg = hovered ? "var(--bg-elevated)" : "var(--bg-surface)";
  const cardBorder = hovered ? "var(--border-hover)" : "var(--border)";

  return (
    <div
      style={{
        position: "relative",
        background: cardBg,
        border: `1px solid ${cardBorder}`,
        borderRadius: "var(--radius-lg)",
        boxShadow: hovered ? `${glow !== "none" ? glow + ", " : ""}0 4px 16px rgba(0,0,0,0.3)` : glow,
        transition: "background 0.2s ease, border-color 0.2s ease, box-shadow 0.25s ease, transform 0.2s ease",
        transform: hovered ? "translateY(-1px)" : "translateY(0)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        cursor: "pointer",
      }}
      onClick={() => setPortfolio(summary.id)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Delete */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (confirmDelete) deleteMutation.mutate();
          else setConfirmDelete(true);
        }}
        style={{
          position: "absolute", top: "6px", right: "6px", zIndex: 10,
          fontSize: "10px", padding: "2px 5px", background: "none", border: "none",
          color: confirmDelete ? "var(--red)" : "transparent",
          fontWeight: confirmDelete ? 600 : 400, cursor: "pointer",
          transition: "color 0.15s",
        }}
        onMouseEnter={(e) => { e.stopPropagation(); if (!confirmDelete) e.currentTarget.style.color = "rgba(248,113,113,0.50)"; }}
        onMouseLeave={(e) => { e.stopPropagation(); if (!confirmDelete) e.currentTarget.style.color = "transparent"; }}
      >
        {deleteMutation.isPending ? "..." : confirmDelete ? "Confirm?" : "×"}
      </button>

      {/* Card body */}
      <div style={{ padding: "18px 20px" }}>
        {/* Header row */}
        <div style={{ display: "flex", alignItems: "center", gap: "5px", marginBottom: "6px", paddingRight: "14px" }}>
          <h3 style={{ flex: 1, fontSize: "14px", fontWeight: 500, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {summary.name}
          </h3>
          <span style={{ fontSize: "8.5px", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)" }}>
            {summary.universe}
          </span>
          <span style={{ fontSize: "8.5px", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600, color: summary.paper_mode ? "var(--amber)" : "var(--accent)" }}>
            {summary.paper_mode ? "Paper" : "Live"}
          </span>
        </div>

        {summary.error ? (
          <div style={{ fontSize: "11px", color: "var(--red)", paddingBottom: "10px" }}>{summary.error}</div>
        ) : (
          <>
            {/* Equity + all-time return */}
            <div style={{ display: "flex", alignItems: "baseline", gap: "7px", marginBottom: "5px" }}>
              <span className="font-mono font-semibold tabular-nums" style={{ fontSize: "17px", color: "var(--text-secondary)" }}>
                ${summary.equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </span>
              <span className="font-mono font-semibold tabular-nums" style={{ fontSize: "11px", color: pnlColor(summary.total_return_pct) }}>
                {fmtPct(summary.total_return_pct)}
              </span>
            </div>

            {/* Day P&L — dominant element */}
            <div style={{
              display: "flex", alignItems: "center", gap: "7px", marginBottom: "7px",
              padding: "4px 7px",
              borderRadius: "5px",
              background: summary.day_pnl > 0
                ? "rgba(52,211,153,0.06)"
                : summary.day_pnl < 0
                  ? "rgba(248,113,113,0.06)"
                  : "transparent",
            }}>
              <span className="font-mono tabular-nums" style={{
                fontSize: "15px", fontWeight: 800, letterSpacing: "-0.01em",
                color: pnlColor(summary.day_pnl),
              }}>
                {fmt$(summary.day_pnl)}
              </span>
              <span className="font-mono tabular-nums" style={{ fontSize: "11px", fontWeight: 600, color: pnlColor(summary.day_pnl), opacity: 0.80 }}>
                {summary.day_pnl !== 0 && summary.equity > 0
                  ? fmtPct((summary.day_pnl / summary.equity) * 100)
                  : ""}
              </span>
              <span style={{ flex: 1 }} />
              <span className="font-mono tabular-nums" style={{ fontSize: "9.5px", color: pnlColor(summary.unrealized_pnl), opacity: 0.60 }}>
                <span style={{ color: "var(--text-0)", fontFamily: "var(--font-sans)", marginRight: "2px" }}>unrl.</span>
                {fmt$(summary.unrealized_pnl)}
              </span>
            </div>
          </>
        )}
      </div>

      {/* Sparkline strip */}
      {!summary.error && hasSparkline && (
        <div style={{
          borderTop: "1px solid var(--border)",
          background: "var(--bg-void)",
          flex: 1,
          minHeight: "28px",
          overflow: "hidden",
        }}>
          <EquitySparkline values={summary.sparkline!} returnPct={summary.total_return_pct ?? 0} id={summary.id} />
        </div>
      )}

      {/* Top holdings */}
      {!summary.error && topHoldings.length > 0 && (
        <div style={{ padding: "6px 10px 0" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
            {topHoldings.map((h) => (
              <div key={h.ticker} style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "10px" }}>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--text-primary)", width: "40px", flexShrink: 0 }}>
                  {h.ticker}
                </span>
                <div style={{ flex: 1, height: "2px", background: "var(--surface-3)", borderRadius: "1px", overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: "1px",
                    width: `${Math.min(100, Math.abs(h.pnl_pct) * 2)}%`,
                    background: h.pnl_pct >= 0 ? "var(--green)" : "var(--red)",
                    opacity: 0.55,
                  }} />
                </div>
                <span className="font-mono tabular-nums" style={{ color: pnlColor(h.pnl_pct), width: "40px", textAlign: "right", flexShrink: 0 }}>
                  {fmtPct(h.pnl_pct)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bottom stats */}
      {!summary.error && (
        <div
          style={{ padding: "5px 10px 7px", display: "flex", alignItems: "center", gap: "5px", fontSize: "9.5px", color: "var(--text-secondary)", borderTop: "1px solid var(--border)", marginTop: "6px" }}
        >
          <span
            className="tabular-nums"
            style={{
              color: regimeColor,
              fontWeight: 700,
              fontSize: "8px",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              padding: "1px 5px",
              borderRadius: "3px",
              background: summary.regime === "BEAR"
                ? "rgba(248,113,113,0.10)"
                : summary.regime === "BULL"
                  ? "rgba(52,211,153,0.08)"
                  : "rgba(251,191,36,0.08)",
            }}
          >{summary.regime ?? "—"}</span>
          <span style={{ color: "var(--text-muted)" }}>·</span>
          <span className="tabular-nums">{summary.num_positions}p</span>
          <span style={{ color: "var(--text-muted)" }}>·</span>
          <span className="tabular-nums">{summary.deployed_pct.toFixed(0)}%</span>
          <div style={{ flex: 1, height: "2px", borderRadius: "1px", background: "var(--surface-3)", overflow: "hidden", margin: "0 3px" }}>
            <div style={{
              height: "100%", borderRadius: "1px",
              width: `${Math.min(100, summary.deployed_pct)}%`,
              background: "linear-gradient(to right, var(--accent), var(--accent-bright))",
            }} />
          </div>
          <span style={{ color: "var(--text-0)" }}>cash</span>
          <span className="font-mono tabular-nums" style={{ color: "var(--text-2)", fontWeight: 600 }}>${summary.cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
        </div>
      )}

      {/* Scan badge */}
      {scanResult && (
        <div
          style={{
            padding: "5px 14px 7px",
            borderTop: "1px solid var(--border)",
            display: "flex", alignItems: "center", gap: "6px",
            fontSize: "10px", color: "var(--text-secondary)",
          }}
        >
          <span
            style={{
              width: "6px", height: "6px", borderRadius: "50%", flexShrink: 0,
              background:
                scanResult.status === "complete" ? "var(--green)"
                : scanResult.status === "error"   ? "var(--red)"
                : "var(--amber)",
              animation: scanResult.status === "running"
                ? "pulse 1s ease-in-out infinite"
                : "none",
            }}
          />
          {scanResult.status === "running" && (
            <span style={{ color: "var(--amber)" }}>Scanning…</span>
          )}
          {scanResult.status === "complete" && (
            <span style={{ color: "var(--green)" }}>
              +{scanResult.added} added · {scanResult.active} active
            </span>
          )}
          {scanResult.status === "error" && (
            <span style={{ color: "var(--red)" }}>
              Scan error{scanResult.error ? ` — ${scanResult.error.slice(0, 40)}` : ""}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Attention panel
// ---------------------------------------------------------------------------

function AttentionPanel({ portfolios, onNavigate }: {
  portfolios: PortfolioSummary[];
  onNavigate: (id: string) => void;
}) {
  const items = useMemo(() => {
    const result: { id: string; name: string; reason: string; severity: "error" | "warn" }[] = [];
    for (const p of portfolios) {
      if (p.error) {
        result.push({ id: p.id, name: p.name, reason: p.error.slice(0, 48), severity: "error" });
      } else if (p.num_positions === 0 && p.deployed_pct === 0) {
        result.push({ id: p.id, name: p.name, reason: "No positions", severity: "warn" });
      } else if (p.deployed_pct < 25) {
        result.push({ id: p.id, name: p.name, reason: `${p.deployed_pct.toFixed(0)}% deployed — high idle cash`, severity: "warn" });
      }
    }
    return result;
  }, [portfolios]);

  if (items.length === 0) {
    return (
      <div style={{ padding: "12px 14px" }}>
        <SideHeader>Attention</SideHeader>
        <div style={{ marginTop: "10px", fontSize: "10px", color: "var(--text-muted)", fontStyle: "italic" }}>
          All portfolios nominal
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "12px 14px" }}>
      <SideHeader>Attention ({items.length})</SideHeader>
      <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "4px" }}>
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            style={{
              display: "block", width: "100%", textAlign: "left",
              padding: "6px 8px",
              background: item.severity === "error" ? "rgba(248,113,113,0.06)" : "rgba(251,191,36,0.05)",
              border: `1px solid ${item.severity === "error" ? "rgba(248,113,113,0.18)" : "rgba(251,191,36,0.15)"}`,
              borderRadius: "5px",
              cursor: "pointer",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = item.severity === "error" ? "rgba(248,113,113,0.10)" : "rgba(251,191,36,0.08)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = item.severity === "error" ? "rgba(248,113,113,0.06)" : "rgba(251,191,36,0.05)"; }}
          >
            <div style={{ fontSize: "10px", fontWeight: 700, color: item.severity === "error" ? "var(--red)" : "var(--amber)", marginBottom: "1px" }}>
              {item.name}
            </div>
            <div style={{ fontSize: "9.5px", color: "var(--text-secondary)" }}>{item.reason}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Movers panel
// ---------------------------------------------------------------------------

function MoversPanel({ topMovers, bottomMovers, onNavigate }: {
  topMovers: CrossPortfolioMover[];
  bottomMovers: CrossPortfolioMover[];
  onNavigate: (id: string) => void;
}) {
  function MoverRow({ m, positive }: { m: CrossPortfolioMover; positive: boolean }) {
    const pct = m.day_change_pct ?? m.pnl_pct;
    const pnlVal = m.pnl;
    return (
      <button
        onClick={() => onNavigate(m.portfolio_id)}
        style={{
          display: "flex", alignItems: "center", gap: "6px",
          width: "100%", textAlign: "left",
          padding: "5px 6px",
          background: "transparent",
          border: "none",
          borderRadius: "4px",
          cursor: "pointer",
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-elevated)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
      >
        <span className="font-mono" style={{ fontSize: "10px", fontWeight: 700, color: "var(--text-primary)", width: "36px", flexShrink: 0 }}>
          {m.ticker}
        </span>
        <span style={{ fontSize: "9px", color: "var(--text-muted)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {m.portfolio_name}
        </span>
        <span className="font-mono tabular-nums" style={{ fontSize: "10px", fontWeight: 600, color: positive ? "var(--green)" : "var(--red)", flexShrink: 0 }}>
          {pct >= 0 ? "+" : ""}{pct.toFixed(1)}%
        </span>
        <span className="font-mono tabular-nums" style={{ fontSize: "9px", color: positive ? "var(--green)" : "var(--red)", opacity: 0.7, flexShrink: 0, marginLeft: "2px" }}>
          {pnlVal >= 0 ? "+" : ""}${Math.abs(pnlVal).toFixed(0)}
        </span>
      </button>
    );
  }

  const hasMovers = topMovers.length > 0 || bottomMovers.length > 0;

  return (
    <div style={{ padding: "12px 14px" }}>
      <SideHeader>Movers</SideHeader>
      {!hasMovers ? (
        <div style={{ marginTop: "10px", fontSize: "10px", color: "var(--text-muted)", fontStyle: "italic" }}>No position data</div>
      ) : (
        <>
          {topMovers.length > 0 && (
            <div style={{ marginTop: "8px" }}>
              <div style={{ fontSize: "8.5px", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--green)", opacity: 0.7, marginBottom: "3px" }}>Top</div>
              {topMovers.slice(0, 5).map((m) => (
                <MoverRow key={`${m.ticker}:${m.portfolio_id}`} m={m} positive={true} />
              ))}
            </div>
          )}
          {bottomMovers.length > 0 && (
            <div style={{ marginTop: topMovers.length > 0 ? "10px" : "8px" }}>
              <div style={{ fontSize: "8.5px", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--red)", opacity: 0.7, marginBottom: "3px" }}>Bottom</div>
              {bottomMovers.slice(0, 5).map((m) => (
                <MoverRow key={`${m.ticker}:${m.portfolio_id}`} m={m} positive={false} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SideHeader({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: "9px", textTransform: "uppercase", letterSpacing: "0.10em",
      color: "var(--text-muted)", fontWeight: 700,
      paddingBottom: "6px",
      borderBottom: "1px solid var(--border)",
    }}>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function OverviewPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [updatingAll, setUpdatingAll] = useState(false);
  const [updateResult, setUpdateResult] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("day_pnl");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const queryClient = useQueryClient();
  const { data: overview, isLoading } = useOverview();
  const { data: portfolioList } = usePortfolios();
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deletePortfolio(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });
  void deleteMutation;

  const [scanAll, setScanAll] = useState<ScanAllState>({
    running: false,
    currentId: null,
    results: {},
  });
  const scanCancelledRef = useRef(false);

  const wasScanAllRunning = useRef(false);
  useEffect(() => {
    if (wasScanAllRunning.current && !scanAll.running) play("scanComplete");
    wasScanAllRunning.current = scanAll.running;
  }, [scanAll.running]);

  const doneRef = useRef(0);
  const handleUpdateAll = async () => {
    play("update");
    const ids = (portfolioList?.portfolios ?? []).filter((p) => p.active).map((p) => p.id);
    if (ids.length === 0) return;
    setUpdatingAll(true);
    setUpdateResult(null);
    doneRef.current = 0;
    setUpdateResult(`0 / ${ids.length}`);
    const withTimeout = (p: Promise<unknown>, ms: number) =>
      Promise.race([p, new Promise<never>((_, rej) => setTimeout(() => rej(new Error("timeout")), ms))]);

    try {
      await Promise.allSettled(
        ids.map((pid) =>
          withTimeout(api.updatePrices(pid), 30_000)
            .then(() => { doneRef.current += 1; setUpdateResult(`${doneRef.current} / ${ids.length}`); })
            .catch(() => { doneRef.current += 1; setUpdateResult(`${doneRef.current} / ${ids.length}`); })
        )
      );
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      setUpdateResult(`${ids.length} updated`);
      setTimeout(() => setUpdateResult(null), 3000);
    } finally {
      setUpdatingAll(false);
    }
  };

  const handleScanAll = async () => {
    play("scan");
    const ids = (portfolioList?.portfolios ?? [])
      .filter((p) => p.active)
      .map((p) => p.id);
    if (ids.length === 0) return;

    scanCancelledRef.current = false;
    setScanAll({ running: true, currentId: ids[0], results: {} });

    for (const id of ids) {
      if (scanCancelledRef.current) break;

      setScanAll((prev) => ({
        ...prev,
        currentId: id,
        results: {
          ...prev.results,
          [id]: { status: "running", added: 0, active: 0, error: null },
        },
      }));

      try {
        await api.scan(id);

        const FRONTEND_TIMEOUT_MS = 9 * 60 * 1000;
        const POLL_INTERVAL_MS = 3000;
        const deadline = Date.now() + FRONTEND_TIMEOUT_MS;

        let finalStatus: ScanJobStatus = { status: "running" };
        while (Date.now() < deadline && !scanCancelledRef.current) {
          await new Promise((res) => setTimeout(res, POLL_INTERVAL_MS));
          finalStatus = await api.scanStatus(id);
          if (finalStatus.status !== "running") break;
        }

        if (finalStatus.status === "complete" && finalStatus.result) {
          setScanAll((prev) => ({
            ...prev,
            results: {
              ...prev.results,
              [id]: {
                status: "complete",
                added: finalStatus.result!.added,
                active: finalStatus.result!.total_active,
                error: null,
              },
            },
          }));
          queryClient.invalidateQueries({ queryKey: ["overview"] });
        } else {
          setScanAll((prev) => ({
            ...prev,
            results: {
              ...prev.results,
              [id]: {
                status: "error",
                added: 0,
                active: 0,
                error: finalStatus.error ?? "Scan timed out",
              },
            },
          }));
        }
      } catch (err) {
        setScanAll((prev) => ({
          ...prev,
          results: {
            ...prev.results,
            [id]: {
              status: "error",
              added: 0,
              active: 0,
              error: err instanceof Error ? err.message : "Unknown error",
            },
          },
        }));
      }
    }

    setScanAll((prev) => ({ ...prev, running: false, currentId: null }));
    setTimeout(() => {
      if (!scanCancelledRef.current) {
        setScanAll({ running: false, currentId: null, results: {} });
      }
    }, 5000);
  };

  useEffect(() => {
    return () => { scanCancelledRef.current = true; };
  }, []);

  const names = new Map((portfolioList?.portfolios ?? []).map((p) => [p.id, p.name]));

  // sorted MUST stay above the isLoading early return — hooks can't be called after a conditional return
  const sorted = useMemo(() => {
    const summaries = overview?.portfolios ?? [];
    const enriched = summaries.map((s) => ({ ...s, name: s.name || names.get(s.id) || s.id }));
    return [...enriched].sort((a, b) => {
      switch (sortKey) {
        case "day_pnl":          return (b.day_pnl ?? 0) - (a.day_pnl ?? 0);
        case "total_return_pct": return (b.total_return_pct ?? 0) - (a.total_return_pct ?? 0);
        case "equity":           return (b.equity ?? 0) - (a.equity ?? 0);
        case "deployed_pct":     return (b.deployed_pct ?? 0) - (a.deployed_pct ?? 0);
        case "name":             return (a.name ?? "").localeCompare(b.name ?? "");
        default:                 return 0;
      }
    });
  }, [overview?.portfolios, sortKey, names]);

  const scanAllLabel = useMemo(() => {
    if (!scanAll.running && Object.keys(scanAll.results).length > 0) {
      const totalAdded = Object.values(scanAll.results).reduce((sum, r) => sum + r.added, 0);
      const n = Object.keys(scanAll.results).length;
      return `+${totalAdded} added · ${n} scanned`;
    }
    if (scanAll.running && scanAll.currentId) {
      const name = names.get(scanAll.currentId) ?? scanAll.currentId;
      return `Scanning ${name}…`;
    }
    return null;
  }, [scanAll, names]);

  const holdingsMap = useMemo(() => {
    const map = new Map<string, CrossPortfolioMover[]>();
    const all = overview?.all_positions ?? [];
    for (const pos of all) {
      const arr = map.get(pos.portfolio_id) ?? [];
      arr.push(pos);
      map.set(pos.portfolio_id, arr);
    }
    map.forEach((arr, id) => {
      map.set(id, [...arr].sort((a, b) => (b.market_value ?? 0) - (a.market_value ?? 0)).slice(0, 3));
    });
    return map;
  }, [overview?.all_positions]);

  if (isLoading) {
    return (
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--bg-void)" }}>
        {/* Skeleton aggregate bar */}
        <div style={{ background: "var(--bg-surface)", borderBottom: "1px solid var(--border)", minHeight: "68px", display: "flex", alignItems: "center", padding: "0 20px", gap: "24px" }}>
          <SkeletonBlock width={140} height={26} />
          <SkeletonBlock width={90} height={20} />
          <SkeletonBlock width={100} height={20} />
          <SkeletonBlock width={60} height={20} />
          <SkeletonBlock width={80} height={20} />
        </div>
        {/* Skeleton controls bar */}
        <div style={{ background: "var(--bg-void)", borderBottom: "1px solid var(--border)", minHeight: "36px", display: "flex", alignItems: "center", padding: "0 20px", gap: "8px" }}>
          <SkeletonBlock width={32} height={12} />
          <SkeletonBlock width={220} height={22} />
        </div>
        {/* Skeleton grid */}
        <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
          <div style={{ width: "220px", flexShrink: 0, borderRight: "1px solid var(--border)", background: "var(--bg-surface)", padding: "14px" }}>
            <SkeletonBlock width={80} height={10} style={{ marginBottom: 12 }} />
            <SkeletonBlock width="100%" height={52} style={{ marginBottom: 6 }} />
            <SkeletonBlock width="100%" height={52} style={{ marginBottom: 6 }} />
          </div>
          <div style={{ flex: 1, padding: "14px 16px", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))", gap: "10px", alignContent: "start" }}>
            {Array.from({ length: 9 }).map((_, i) => (
              <SkeletonBlock key={i} width="100%" height={160} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const summaries = overview?.portfolios ?? [];
  const enriched = summaries.map((s) => ({ ...s, name: s.name || names.get(s.id) || s.id }));
  const totalEquity = overview?.total_equity ?? 0;
  const totalCash   = overview?.total_cash ?? 0;

  // Computed aggregates
  const portfoliosUp   = enriched.filter((s) => s.day_pnl > 0).length;
  const portfoliosDown = enriched.filter((s) => s.day_pnl < 0).length;
  const deployedPct    = totalEquity > 0 ? ((totalEquity - totalCash) / totalEquity) * 100 : 0;


  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--bg-void)" }}>
      {/* Morning Briefing headline + stats */}
      <MorningBriefing
        totalEquity={totalEquity}
        totalDayPnl={overview?.total_day_pnl ?? 0}
        totalReturnPct={overview?.total_return_pct ?? 0}
        totalPositions={overview?.total_positions ?? 0}
        portfolioCount={enriched.length}
        onNewPortfolio={() => setShowCreate(true)}
        onUpdateAll={handleUpdateAll}
        updatingAll={updatingAll}
        updateResult={updateResult}
        onScanAll={handleScanAll}
        scanAllRunning={scanAll.running}
        scanAllLabel={scanAllLabel}
      />

      {/* Controls bar: sort + view toggle */}
      <ControlsBar
        sortKey={sortKey}
        onSort={setSortKey}
        viewMode={viewMode}
        onView={setViewMode}
      />

      {/* Body */}
      {enriched.length === 0 ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-1)" }}>
          <div style={{ textAlign: "center" }}>
            <p style={{ fontSize: "16px", marginBottom: "10px", color: "var(--text-3)", fontWeight: 600 }}>No portfolios yet</p>
            <p style={{ fontSize: "12px", color: "var(--text-1)" }}>Create your first portfolio to get started.</p>
            <button
              onClick={() => setShowCreate(true)}
              style={{
                marginTop: "20px",
                padding: "8px 20px",
                background: "var(--accent-dim)",
                border: "1px solid var(--accent-border)",
                borderRadius: "6px",
                color: "var(--accent-bright)",
                fontSize: "11px", fontWeight: 600,
                cursor: "pointer",
                letterSpacing: "0.06em", textTransform: "uppercase",
              }}
            >
              + New Portfolio
            </button>
          </div>
        </div>
      ) : viewMode === "grid" ? (
        <div key="grid" style={{ flex: 1, overflow: "hidden", display: "flex", animation: "fadeIn 0.15s ease" }}>
          {/* Left side panel: attention + movers */}
          <div style={{
            width: "220px",
            flexShrink: 0,
            overflowY: "auto",
            borderRight: "1px solid var(--border)",
            background: "var(--bg-surface)",
            display: "flex",
            flexDirection: "column",
          }}>
            <AttentionPanel portfolios={enriched} onNavigate={setPortfolio} />
            <div style={{ height: "1px", background: "var(--border)" }} />
            <MoversPanel
              topMovers={overview?.top_movers ?? []}
              bottomMovers={overview?.bottom_movers ?? []}
              onNavigate={setPortfolio}
            />
          </div>

          {/* Portfolio grid */}
          <div style={{ flex: 1, overflow: "auto", padding: "14px 16px" }}>
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))",
              gap: "10px",
            }}>
              {sorted.map((s) => (
                <PortfolioCard
                  key={s.id}
                  summary={s}
                  totalEquity={totalEquity}
                  scanResult={scanAll.results[s.id]}
                  topHoldings={holdingsMap.get(s.id) ?? []}
                />
              ))}
            </div>
          </div>
        </div>
      ) : viewMode === "map" ? (
        <div key="map" style={{ flex: 1, overflow: "auto", padding: "16px 20px", animation: "fadeIn 0.15s ease" }}>
          <Suspense fallback={<LoadingPane text="Loading map…" />}>
            <ConstellationMap
              positions={overview?.all_positions ?? []}
              portfolios={enriched}
            />
          </Suspense>
        </div>
      ) : (
        <div key="chart" style={{ flex: 1, overflow: "auto", padding: "16px 20px", animation: "fadeIn 0.15s ease" }}>
          <Suspense fallback={<LoadingPane text="Loading chart…" />}>
            <PerformanceChart portfolios={enriched} height={480} />
          </Suspense>
        </div>
      )}

      {showCreate && <CreatePortfolioModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}

function LoadingPane({ text }: { text: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-1)", fontSize: "12px" }}>
      {text}
    </div>
  );
}

function SkeletonBlock({ width, height, style }: { width: number | string; height: number; style?: React.CSSProperties }) {
  return (
    <div
      className="animate-pulse-slow"
      style={{
        width: typeof width === "number" ? `${width}px` : width,
        height: `${height}px`,
        borderRadius: "5px",
        background: "var(--surface-3)",
        flexShrink: 0,
        ...style,
      }}
    />
  );
}
