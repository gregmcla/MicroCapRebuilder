/** Overview page — shown when activePortfolioId === "overview". */

import { useMemo, useState, useRef, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOverview, usePortfolios } from "../hooks/usePortfolios";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import { useCountUp } from "../hooks/useCountUp";
import type { PortfolioSummary, CrossPortfolioMover } from "../lib/types";
import type { ScanJobStatus } from "../lib/types";
import CreatePortfolioModal from "./CreatePortfolioModal";
import MatrixGrid from "./MatrixGrid";
import { buildPortfolioMap, crossMoverToMatrix } from "./MatrixGrid/constants";
import type { MatrixPortfolio } from "./MatrixGrid/types";

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
// Aggregate header bar
// ---------------------------------------------------------------------------

function AggregateBar({
  totalEquity, totalCash, totalDayPnl, totalUnrealizedPnl, totalAllTimePnl, totalPositions, portfolioCount, onNewPortfolio,
  onUpdateAll, updatingAll, updateResult,
  onScanAll, scanAllRunning, scanAllLabel,
}: {
  totalEquity: number; totalCash: number; totalDayPnl: number;
  totalUnrealizedPnl: number; totalAllTimePnl: number; totalPositions: number; portfolioCount: number;
  onNewPortfolio: () => void;
  onUpdateAll: () => void;
  updatingAll: boolean;
  updateResult: string | null;
  onScanAll: () => void;
  scanAllRunning: boolean;
  scanAllLabel: string | null;
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
          onClick={onScanAll}
          disabled={scanAllRunning}
          style={{
            display: "inline-flex", alignItems: "center", gap: "5px",
            padding: "0 12px", height: "28px",
            background: "transparent",
            border: "1px solid var(--border-1)",
            borderRadius: "6px",
            color: scanAllRunning ? "var(--accent)" : "var(--text-1)",
            fontSize: "11px", fontWeight: 600,
            letterSpacing: "0.06em", textTransform: "uppercase",
            cursor: scanAllRunning ? "not-allowed" : "pointer",
            transition: "border-color 0.15s, color 0.15s",
            opacity: scanAllRunning ? 0.75 : 1,
            whiteSpace: "nowrap",
          }}
          onMouseEnter={(e) => {
            if (!scanAllRunning) {
              e.currentTarget.style.borderColor = "var(--accent)";
              e.currentTarget.style.color = "var(--accent)";
            }
          }}
          onMouseLeave={(e) => {
            if (!scanAllRunning) {
              e.currentTarget.style.borderColor = "var(--border-1)";
              e.currentTarget.style.color = "var(--text-1)";
            }
          }}
        >
          <span
            style={{
              width: "6px", height: "6px", borderRadius: "50%",
              background: "currentColor", opacity: scanAllRunning ? 1 : 0.6, flexShrink: 0,
              animation: scanAllRunning ? "pulse 1s ease-in-out infinite" : "none",
            }}
          />
          {scanAllLabel ?? "Scan All"}
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

function PortfolioCard({ summary, totalEquity, scanResult }: {
  summary: PortfolioSummary;
  totalEquity: number;
  scanResult?: ScanAllPortfolioResult;
}) {
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

      {/* Scan badge — only visible when scan-all has state for this card */}
      {scanResult && (
        <div
          style={{
            padding: "5px 14px 7px",
            borderTop: "1px solid var(--border-0)",
            display: "flex", alignItems: "center", gap: "6px",
            fontSize: "10px", color: "var(--text-1)",
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
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);

  const [scanAll, setScanAll] = useState<ScanAllState>({
    running: false,
    currentId: null,
    results: {},
  });
  const scanCancelledRef = useRef(false);

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

  const handleScanAll = async () => {
    const ids = (portfolioList?.portfolios ?? [])
      .filter((p) => p.active)
      .map((p) => p.id);
    if (ids.length === 0) return;

    scanCancelledRef.current = false;
    setScanAll({ running: true, currentId: ids[0], results: {} });

    for (const id of ids) {
      if (scanCancelledRef.current) break;

      // Mark this portfolio as running
      setScanAll((prev) => ({
        ...prev,
        currentId: id,
        results: {
          ...prev.results,
          [id]: { status: "running", added: 0, active: 0, error: null },
        },
      }));

      try {
        // Fire the scan
        await api.scan(id);

        // Poll until complete or timeout (9 min frontend guard)
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
          // Refresh overview data so card stats update live
          queryClient.invalidateQueries({ queryKey: ["overview"] });
        } else {
          // Timeout or backend error — non-fatal, continue chain
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

    // Chain complete
    setScanAll((prev) => ({ ...prev, running: false, currentId: null }));
    // Clear results after 5s
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

  const portfolios = portfolioList?.portfolios ?? [];

  const matrixPortfolios = useMemo<MatrixPortfolio[]>(() => {
    if (!portfolios?.length) return [];
    const ids = portfolios.map((p: any) => ({ id: p.id, name: p.name }));
    const map = buildPortfolioMap(ids);
    return ids.map((p: { id: string; name: string }) => map.get(p.id)!).filter(Boolean);
  }, [portfolios]);

  const matrixPositions = useMemo(() => {
    if (!overview?.all_positions?.length || !matrixPortfolios.length) return [];
    const map = buildPortfolioMap(matrixPortfolios.map((p) => ({ id: p.id, name: p.name })));
    return overview.all_positions.map((m) => crossMoverToMatrix(m, map));
  }, [overview?.all_positions, matrixPortfolios]);

  if (isLoading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--surface-0)" }}>
        <p className="animate-pulse" style={{ color: "var(--text-1)" }}>Loading portfolios...</p>
      </div>
    );
  }

  const summaries = overview?.portfolios ?? [];
  const enriched = summaries.map((s) => ({ ...s, name: s.name || names.get(s.id) || s.id }));
  const validSummaries = enriched.filter((s) => !s.error);
  const totalEquity = overview?.total_equity ?? 0;
  const topMovers = overview?.top_movers ?? [];
  const bottomMovers = overview?.bottom_movers ?? [];

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
        onScanAll={handleScanAll}
        scanAllRunning={scanAll.running}
        scanAllLabel={scanAllLabel}
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
                    <PortfolioCard
                      summary={s}
                      totalEquity={totalEquity}
                      scanResult={scanAll.results[s.id]}
                    />
                  </div>
                ))}
              </div>

              {matrixPositions.length > 0 && (
                <div style={{ flex: 1, minHeight: 400, marginTop: 16 }}>
                  <MatrixGrid
                    positions={matrixPositions}
                    portfolios={matrixPortfolios}
                    onPositionClick={(pos) => setPortfolio(pos.portfolioId)}
                    showSecondaryTabs={false}
                  />
                </div>
              )}
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
