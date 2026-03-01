/** Overview page — shown when activePortfolioId === "overview". */

import { useMemo, useState } from "react";
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
// Heatmap
// ---------------------------------------------------------------------------

function AllPositionsHeatmap({ positions }: { positions: CrossPortfolioMover[] }) {
  // Sort: biggest winners first, then flat, then losers last — classic heatmap order
  const sorted = useMemo(
    () => [...positions].sort((a, b) => b.pnl_pct - a.pnl_pct),
    [positions]
  );

  if (sorted.length === 0) return null;

  function blockBg(pct: number) {
    if (pct >= 12)      return "rgba(52,211,153,0.55)";
    if (pct >= 6)       return "rgba(52,211,153,0.36)";
    if (pct >= 2)       return "rgba(52,211,153,0.20)";
    if (pct >= 0)       return "rgba(52,211,153,0.08)";
    if (pct >= -2)      return "rgba(248,113,113,0.08)";
    if (pct >= -6)      return "rgba(248,113,113,0.20)";
    if (pct >= -12)     return "rgba(248,113,113,0.36)";
    return              "rgba(248,113,113,0.55)";
  }

  function textColor(pct: number) {
    return pct >= 0 ? "var(--green)" : "var(--red)";
  }

  return (
    <div style={{ marginTop: "16px" }}>
      <p style={{
        fontSize: "9.5px", fontWeight: 600, textTransform: "uppercase",
        letterSpacing: "0.08em", color: "var(--text-0)", marginBottom: "7px",
      }}>
        All Positions — {sorted.length}
      </p>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "2px",
          padding: "6px",
          background: "var(--surface-1)",
          border: "1px solid var(--border-0)",
          borderRadius: "7px",
        }}
      >
        {sorted.map((pos) => (
          <div
            key={`${pos.portfolio_id}-${pos.ticker}`}
            title={`${pos.ticker} · ${pos.portfolio_name} · ${fmtPct(pos.pnl_pct)} · $${(pos.market_value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
            style={{
              background: blockBg(pos.pnl_pct),
              border: "1px solid rgba(255,255,255,0.04)",
              borderRadius: "4px",
              padding: "4px 7px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "1px",
              cursor: "default",
              transition: "opacity 0.1s",
              minWidth: "46px",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.75")}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
          >
            <span style={{ fontSize: "9.5px", fontWeight: 700, color: "var(--text-4)", fontFamily: "var(--font-mono)", letterSpacing: "0.03em" }}>
              {pos.ticker}
            </span>
            <span style={{ fontSize: "9px", fontWeight: 600, color: textColor(pos.pnl_pct), fontFamily: "var(--font-mono)" }}>
              {fmtPct(pos.pnl_pct, 1)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Aggregate header bar
// ---------------------------------------------------------------------------

function AggregateBar({
  totalEquity, totalCash, totalDayPnl, totalUnrealizedPnl, totalPositions, portfolioCount,
}: {
  totalEquity: number; totalCash: number; totalDayPnl: number;
  totalUnrealizedPnl: number; totalPositions: number; portfolioCount: number;
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
      <StatChip label="Unrealized P&L" value={fmt$(totalUnrealizedPnl)} color={pnlColor(totalUnrealizedPnl)} />
      <StatChip label="Day P&L" value={fmt$(totalDayPnl)} color={pnlColor(totalDayPnl)} />
      <StatChip label="Cash" value={`$${totalCash.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
      <StatChip label="Positions" value={String(totalPositions)} />
      <StatChip label="Portfolios" value={String(portfolioCount)} />
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

            {/* Day / Open P&L */}
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px", fontSize: "11px" }}>
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
  const { data: overview, isLoading } = useOverview();
  const { data: portfolioList } = usePortfolios();

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
        totalPositions={overview?.total_positions ?? 0}
        portfolioCount={enriched.length}
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

                <button
                  onClick={() => setShowCreate(true)}
                  style={{
                    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                    padding: "16px", minHeight: "148px",
                    background: "var(--surface-1)", border: "1px dashed var(--border-1)", borderRadius: "8px",
                    cursor: "pointer", transition: "border-color 0.15s, opacity 0.15s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--border-2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border-1)")}
                >
                  <span style={{ fontSize: "22px", color: "var(--text-1)", marginBottom: "6px" }}>+</span>
                  <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.10em", color: "var(--text-1)" }}>
                    New Portfolio
                  </span>
                </button>
              </div>

              <AllPositionsHeatmap positions={allPositions} />
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
