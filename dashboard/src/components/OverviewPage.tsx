/** Overview page — shown when activePortfolioId === "overview". */

import { useMemo, useState, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOverview, usePortfolios } from "../hooks/usePortfolios";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import { useCountUp } from "../hooks/useCountUp";
import type { PortfolioSummary, CrossPortfolioMover } from "../lib/types";
import CreatePortfolioModal from "./CreatePortfolioModal";
import PerformanceChart from "./PerformanceChart";
import ConstellationMap from "./ConstellationMap";

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

// ---------------------------------------------------------------------------
// Portfolio color palette
// ---------------------------------------------------------------------------

const PORTFOLIO_COLORS = [
  "#5ce0d6", // teal
  "#7c5cfc", // indigo
  "#fbbf24", // amber
  "#6b9bd2", // steel blue
  "#b8a9c9", // lavender
  "#7dba89", // sage
  "#d4889e", // dusty rose
  "#8b95a5", // slate
];

// ---------------------------------------------------------------------------
// Equity sparkline — accepts optional height prop
// ---------------------------------------------------------------------------

function EquitySparkline({ values, returnPct, height = 36 }: { values: number[]; returnPct: number; height?: number }) {
  const W = 200; const H = height;
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
  }, [values, H]);

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
// HeroStrip — replaces AggregateBar
// ---------------------------------------------------------------------------

function HeroStrip({
  totalEquity, totalCash, totalDayPnl, totalUnrealizedPnl, totalAllTimePnl,
  totalPositions, portfolioCount, onNewPortfolio, onUpdateAll, updatingAll, updateResult,
}: {
  totalEquity: number; totalCash: number; totalDayPnl: number;
  totalUnrealizedPnl: number; totalAllTimePnl: number;
  totalPositions: number; portfolioCount: number;
  onNewPortfolio: () => void; onUpdateAll: () => void;
  updatingAll: boolean; updateResult: string | null;
}) {
  const rawCount = useCountUp(totalEquity, 1200, 0);
  const animatedEquity = Number(rawCount).toLocaleString();

  return (
    <div
      style={{
        padding: "0 24px",
        minHeight: 72,
        background: "var(--surface-1)",
        borderBottom: "1px solid var(--border-0)",
        display: "flex",
        alignItems: "center",
        gap: 20,
        flexShrink: 0,
      }}
    >
      {/* Total Equity */}
      <div className="shrink-0">
        <p style={{ fontSize: "9.5px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", marginBottom: "3px" }}>
          Total Equity
        </p>
        <p className="font-mono font-bold tabular-nums" style={{ fontSize: "26px", color: "var(--text-4)", letterSpacing: "-0.02em" }}>
          ${animatedEquity}
        </p>
      </div>

      {/* Separator */}
      <div style={{ width: 1, height: 36, background: "var(--border-1)", flexShrink: 0 }} />

      {/* TODAY */}
      <div className="shrink-0">
        <p style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", marginBottom: "2px" }}>Today</p>
        <p className="font-mono font-semibold tabular-nums" style={{ fontSize: "17px", color: pnlColor(totalDayPnl) }}>{fmt$(totalDayPnl)}</p>
      </div>

      {/* OPEN P&L */}
      <div className="shrink-0">
        <p style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", marginBottom: "2px" }}>Open P&L</p>
        <p className="font-mono font-semibold tabular-nums" style={{ fontSize: "17px", color: pnlColor(totalUnrealizedPnl) }}>{fmt$(totalUnrealizedPnl)}</p>
      </div>

      {/* ALL-TIME */}
      <div className="shrink-0">
        <p style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)", marginBottom: "2px" }}>All-Time</p>
        <p className="font-mono font-semibold tabular-nums" style={{ fontSize: "17px", color: pnlColor(totalAllTimePnl) }}>{fmt$(totalAllTimePnl)}</p>
      </div>

      {/* Separator */}
      <div style={{ width: 1, height: 36, background: "var(--border-1)", flexShrink: 0 }} />

      {/* Right cluster */}
      <div style={{ marginLeft: "auto", display: "flex", gap: 12, alignItems: "center" }}>
        <span style={{ fontSize: "9.5px", color: "var(--text-0)", whiteSpace: "nowrap" }}>
          ${(totalCash / 1000).toFixed(0)}k cash · {totalPositions} positions · {portfolioCount} portfolios
        </span>

        {/* Update All button */}
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

        {/* New Portfolio button */}
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
// PortfolioRow — single row in the portfolio table
// ---------------------------------------------------------------------------

function PortfolioRow({ summary, totalEquity, colorIndex, colorMap }: {
  summary: PortfolioSummary; totalEquity: number; colorIndex: number; colorMap: Map<string, string>;
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

  const dotColor = colorMap.get(summary.id) ?? PORTFOLIO_COLORS[colorIndex % 8];
  const allocPct = totalEquity > 0 ? (summary.equity / totalEquity) * 100 : 0;

  // Error state
  if (summary.error) {
    return (
      <div
        style={{
          height: 48, display: "flex", alignItems: "center", gap: 12,
          padding: "0 12px", borderBottom: "1px solid var(--border-0)",
          cursor: "pointer",
          background: hovered ? "var(--surface-2)" : "transparent",
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={() => setPortfolio(summary.id)}
      >
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: dotColor, flexShrink: 0 }} />
        <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-4)" }}>{summary.name}</span>
        <span style={{ fontSize: "11px", color: "var(--red)", flex: 1 }}>{summary.error}</span>
      </div>
    );
  }

  return (
    <div
      style={{
        height: 48, display: "flex", alignItems: "center", gap: 12,
        padding: "0 12px", borderBottom: "1px solid var(--border-0)",
        cursor: "pointer",
        background: hovered ? "var(--surface-2)" : "transparent",
        transition: "background 0.1s",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => setPortfolio(summary.id)}
    >
      {/* 1. Color dot */}
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: dotColor, flexShrink: 0 }} />

      {/* 2. Name + badges */}
      <div style={{ minWidth: 160, flexShrink: 0 }}>
        <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-4)" }}>{summary.name}</span>
        <span style={{ fontSize: "8.5px", textTransform: "uppercase", color: "var(--text-0)", marginLeft: 6 }}>{summary.universe}</span>
        <span style={{
          fontSize: "8.5px", fontWeight: 600, textTransform: "uppercase", marginLeft: 4,
          color: summary.paper_mode ? "var(--amber)" : "var(--green)",
        }}>
          {summary.paper_mode ? "Paper" : "Live"}
        </span>
      </div>

      {/* 3. Equity + Return */}
      <div style={{ width: 120, flexShrink: 0 }}>
        <p className="font-mono font-bold tabular-nums" style={{ fontSize: "14px", color: "var(--text-3)", margin: 0 }}>
          ${summary.equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </p>
        <p className="font-mono tabular-nums" style={{ fontSize: "11px", color: pnlColor(summary.total_return_pct), fontWeight: 600, margin: 0 }}>
          {fmtPct(summary.total_return_pct)}
        </p>
      </div>

      {/* 4. Allocation bar */}
      <div style={{ width: 80, flexShrink: 0 }}>
        <div style={{ height: 3, borderRadius: 2, background: "var(--surface-3)", marginBottom: 3 }}>
          <div style={{
            height: "100%", borderRadius: 2,
            width: `${Math.min(100, allocPct)}%`,
            background: "linear-gradient(to right, var(--accent), var(--accent-bright))",
          }} />
        </div>
        <span style={{ fontSize: "9.5px", color: "var(--text-0)" }}>{allocPct.toFixed(1)}%</span>
      </div>

      {/* 5. Sparkline */}
      {(summary.sparkline?.length ?? 0) >= 2
        ? (
          <div style={{ width: 80, height: 28, flexShrink: 0 }}>
            <EquitySparkline values={summary.sparkline!} returnPct={summary.total_return_pct ?? 0} height={28} />
          </div>
        )
        : <div style={{ width: 80, flexShrink: 0 }} />
      }

      {/* 6. Day P&L */}
      <div style={{ width: 80, flexShrink: 0 }}>
        <p style={{ fontSize: "9px", textTransform: "uppercase", color: "var(--text-0)", marginBottom: 1, margin: 0 }}>Day</p>
        <p className="font-mono tabular-nums" style={{ fontSize: "12px", fontWeight: 600, color: pnlColor(summary.day_pnl), margin: 0 }}>
          {fmt$(summary.day_pnl)}
        </p>
      </div>

      {/* 7. Stats */}
      <div style={{ flex: 1, display: "flex", gap: 6, fontSize: "10px", color: "var(--text-0)", alignItems: "center" }}>
        <span>{summary.num_positions}p</span>
        <span style={{ color: "var(--border-2)" }}>·</span>
        <span>{summary.deployed_pct.toFixed(0)}% dep</span>
        <span style={{ color: "var(--border-2)" }}>·</span>
        <span>${summary.cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
      </div>

      {/* 8. Regime */}
      {summary.regime && (
        <span style={{
          fontSize: "9px", textTransform: "uppercase", fontWeight: 600,
          width: 65, flexShrink: 0,
          color: summary.regime === "BULL" ? "var(--green)" : summary.regime === "BEAR" ? "var(--red)" : "var(--amber)",
        }}>
          {summary.regime}
        </span>
      )}
      {!summary.regime && <div style={{ width: 65, flexShrink: 0 }} />}

      {/* 9. Delete button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (confirmDelete) deleteMutation.mutate();
          else setConfirmDelete(true);
        }}
        style={{
          fontSize: "11px", padding: "2px 6px", background: "none", border: "none",
          color: confirmDelete ? "var(--red)" : "transparent",
          fontWeight: confirmDelete ? 600 : 400, cursor: "pointer",
          flexShrink: 0,
        }}
        onMouseEnter={(e) => { if (!confirmDelete) e.currentTarget.style.color = "rgba(248,113,113,0.50)"; }}
        onMouseLeave={(e) => { if (!confirmDelete) e.currentTarget.style.color = "transparent"; }}
      >
        {deleteMutation.isPending ? "..." : confirmDelete ? "Confirm?" : "×"}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PortfolioTable
// ---------------------------------------------------------------------------

function PortfolioTable({ summaries, totalEquity, colorMap }: {
  summaries: PortfolioSummary[]; totalEquity: number; colorMap: Map<string, string>;
}) {
  return (
    <div>
      {summaries.map((s, i) => (
        <PortfolioRow
          key={s.id}
          summary={s}
          totalEquity={totalEquity}
          colorIndex={i}
          colorMap={colorMap}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// MoverRow
// ---------------------------------------------------------------------------

function MoverRow({ mover, dotColor }: { mover: CrossPortfolioMover; dotColor?: string }) {
  const color = pnlColor(mover.pnl_pct);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "11px", padding: "5px 0", borderBottom: "1px solid var(--border-0)" }}>
      {dotColor && <div style={{ width: 6, height: 6, borderRadius: "50%", background: dotColor, flexShrink: 0 }} />}
      <span style={{ fontWeight: 700, width: 38, flexShrink: 0, color: "var(--text-4)", fontFamily: "var(--font-mono)" }}>{mover.ticker}</span>
      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--text-1)", fontSize: "10px" }}>
        {mover.portfolio_name}
      </span>
      <span className="font-mono tabular-nums" style={{ color, fontWeight: 600 }}>{fmtPct(mover.pnl_pct)}</span>
      <span className="font-mono tabular-nums" style={{ color, width: 56, textAlign: "right" }}>{fmt$(mover.pnl)}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MoversPanel
// ---------------------------------------------------------------------------

function MoversPanel({
  topMovers, bottomMovers, portfolioColors,
}: { topMovers: CrossPortfolioMover[]; bottomMovers: CrossPortfolioMover[]; portfolioColors: Map<string, string> }) {
  return (
    <div style={{ padding: 0 }}>
      {topMovers.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <p style={{ fontSize: "9.5px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--green)", marginBottom: 6 }}>
            Top Movers
          </p>
          {topMovers.map((m) => (
            <MoverRow key={`${m.portfolio_id}-${m.ticker}`} mover={m} dotColor={portfolioColors.get(m.portfolio_id)} />
          ))}
        </div>
      )}
      {bottomMovers.length > 0 && (
        <div>
          <p style={{ fontSize: "9.5px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--red)", marginBottom: 6 }}>
            Bottom Movers
          </p>
          {bottomMovers.map((m) => (
            <MoverRow key={`${m.portfolio_id}-${m.ticker}`} mover={m} dotColor={portfolioColors.get(m.portfolio_id)} />
          ))}
        </div>
      )}
      {topMovers.length === 0 && bottomMovers.length === 0 && (
        <p style={{ fontSize: "11px", color: "var(--text-0)" }}>No open positions.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// VisualizationStage
// ---------------------------------------------------------------------------

function VisualizationStage({ positions, portfolios }: { positions: CrossPortfolioMover[]; portfolios: PortfolioSummary[] }) {
  const [view, setView] = useState<"map" | "chart">("map");

  if (positions.length === 0) return null;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
      {/* Toggle header */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", marginBottom: 6, flexShrink: 0 }}>
        <div style={{ display: "flex", gap: 2, background: "var(--surface-1)", border: "1px solid var(--border-0)", borderRadius: 5, padding: 2 }}>
          {(["map", "chart"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              style={{
                fontSize: "9px", fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase",
                padding: "3px 10px", borderRadius: 3, border: "none", cursor: "pointer",
                background: view === v ? "var(--accent)" : "transparent",
                color: view === v ? "white" : "var(--text-0)",
                transition: "background 0.15s, color 0.15s",
              }}
            >
              {v === "map" ? "MAP" : "CHART"}
            </button>
          ))}
        </div>
      </div>
      {/* Visualization */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {view === "map"
          ? <ConstellationMap positions={positions} portfolios={portfolios} />
          : <PerformanceChart portfolios={portfolios} />
        }
      </div>
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
  const queryClient = useQueryClient();
  const { data: overview, isLoading } = useOverview();
  const { data: portfolioList } = usePortfolios();
  const doneRef = useRef(0);

  const handleUpdateAll = async () => {
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
  const sorted = [...enriched].sort((a, b) => (b.equity ?? 0) - (a.equity ?? 0));
  const totalEquity = overview?.total_equity ?? 0;
  const topMovers = overview?.top_movers ?? [];
  const bottomMovers = overview?.bottom_movers ?? [];
  const allPositions = overview?.all_positions ?? [];

  // Build portfolio color map (by portfolio id)
  const portfolioColorMap = new Map<string, string>();
  sorted.forEach((s, i) => portfolioColorMap.set(s.id, PORTFOLIO_COLORS[i % 8]));

  // Suppress unused variable warning — validSummaries used by pattern matching above
  void validSummaries;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--surface-0)" }}>
      <HeroStrip
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

      {enriched.length === 0 ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ textAlign: "center", color: "var(--text-1)" }}>
            <p style={{ fontSize: "18px", marginBottom: 8 }}>No portfolios yet</p>
            <p style={{ fontSize: "13px" }}>Create your first portfolio to get started.</p>
          </div>
        </div>
      ) : (
        <>
          {/* Middle band: portfolio table + movers */}
          <div style={{ display: "flex", flexShrink: 0, borderBottom: "1px solid var(--border-0)" }}>
            <div style={{ flex: 1, overflowX: "auto", padding: "8px 20px" }}>
              <PortfolioTable summaries={sorted} totalEquity={totalEquity} colorMap={portfolioColorMap} />
            </div>
            <aside style={{ width: 220, flexShrink: 0, borderLeft: "1px solid var(--border-0)", padding: "12px 16px", overflowY: "auto" }}>
              <MoversPanel topMovers={topMovers} bottomMovers={bottomMovers} portfolioColors={portfolioColorMap} />
            </aside>
          </div>

          {/* Bottom band: visualization stage */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: "8px 20px 12px" }}>
            <VisualizationStage positions={allPositions} portfolios={enriched} />
          </div>
        </>
      )}

      {showCreate && <CreatePortfolioModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
