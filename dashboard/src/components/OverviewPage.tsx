/** Overview page — shown when activePortfolioId === "overview". */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOverview, usePortfolios } from "../hooks/usePortfolios";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import { useCountUp } from "../hooks/useCountUp";
import type { PortfolioSummary } from "../lib/types";
import CreatePortfolioModal from "./CreatePortfolioModal";


function AggregateBar({
  totalEquity,
  totalCash,
  totalDayPnl,
  portfolioCount,
}: {
  totalEquity: number;
  totalCash: number;
  totalDayPnl: number;
  portfolioCount: number;
}) {
  const animatedEquity = useCountUp(totalEquity, 1200, 2);
  const dayColor =
    totalDayPnl > 0 ? "var(--green)" : totalDayPnl < 0 ? "var(--red)" : "var(--text-3)";

  return (
    <div
      className="flex items-center gap-6 px-6 py-4 shrink-0"
      style={{
        background: "var(--surface-1)",
        borderBottom: "1px solid var(--border-0)",
      }}
    >
      <div>
        <p
          className="uppercase tracking-wider"
          style={{ fontSize: "9.5px", color: "var(--text-0)" }}
        >
          Total Equity
        </p>
        <p
          className="font-mono font-bold tabular-nums"
          style={{ fontSize: "22px", color: "var(--text-4)", fontFamily: "var(--font-mono)" }}
        >
          ${animatedEquity}
        </p>
      </div>
      <div>
        <p
          className="uppercase tracking-wider"
          style={{ fontSize: "9.5px", color: "var(--text-0)" }}
        >
          Total Cash
        </p>
        <p
          className="font-mono font-semibold tabular-nums"
          style={{ fontSize: "18px", color: "var(--text-3)", fontFamily: "var(--font-mono)" }}
        >
          ${totalCash.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
        </p>
      </div>
      <div>
        <p
          className="uppercase tracking-wider"
          style={{ fontSize: "9.5px", color: "var(--text-0)" }}
        >
          Day P&L
        </p>
        <p
          className="font-mono font-semibold tabular-nums"
          style={{ fontSize: "18px", color: dayColor, fontFamily: "var(--font-mono)" }}
        >
          {totalDayPnl >= 0 ? "+" : ""}${totalDayPnl.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
        </p>
      </div>
      <div>
        <p
          className="uppercase tracking-wider"
          style={{ fontSize: "9.5px", color: "var(--text-0)" }}
        >
          Portfolios
        </p>
        <p
          className="font-mono font-semibold tabular-nums"
          style={{ fontSize: "18px", color: "var(--text-3)", fontFamily: "var(--font-mono)" }}
        >
          {portfolioCount}
        </p>
      </div>
    </div>
  );
}

function PortfolioCard({ summary }: { summary: PortfolioSummary }) {
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
    summary.regime === "BULL"
      ? "var(--green)"
      : summary.regime === "BEAR"
        ? "var(--red)"
        : "var(--amber)";

  return (
    <div
      className="relative text-left card-hover"
      style={{
        background: "var(--surface-1)",
        border: "1px solid var(--border-0)",
        borderRadius: "8px",
      }}
    >
      {/* Delete button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (confirmDelete) {
            deleteMutation.mutate();
          } else {
            setConfirmDelete(true);
          }
        }}
        className="absolute top-2 right-2 transition-colors"
        style={{
          fontSize: "10px",
          padding: "2px 6px",
          color: confirmDelete ? "var(--red)" : "transparent",
          fontWeight: confirmDelete ? 600 : 400,
        }}
        onMouseEnter={(e) => {
          if (!confirmDelete) e.currentTarget.style.color = "rgba(248,113,113,0.50)";
        }}
        onMouseLeave={(e) => {
          if (!confirmDelete) e.currentTarget.style.color = "transparent";
        }}
      >
        {deleteMutation.isPending ? "..." : confirmDelete ? "Confirm?" : "×"}
      </button>

      {/* Clickable card body */}
      <button onClick={() => setPortfolio(summary.id)} className="w-full text-left p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3 pr-4">
          <h3 className="text-sm font-bold" style={{ color: "var(--text-4)" }}>
            {summary.name}
          </h3>
          <div className="flex items-center gap-2">
            <span
              className="uppercase tracking-wider"
              style={{ fontSize: "10px", color: "var(--text-0)" }}
            >
              {summary.universe}
            </span>
            <span
              className="uppercase tracking-wider font-semibold"
              style={{
                fontSize: "10px",
                color: summary.paper_mode ? "var(--amber)" : "var(--red)",
              }}
            >
              {summary.paper_mode ? "Paper" : "Live"}
            </span>
          </div>
        </div>

        {/* Error state */}
        {summary.error ? (
          <div className="text-xs" style={{ color: "var(--red)" }}>
            {summary.error}
          </div>
        ) : (
          <>
            {/* Equity */}
            <p
              className="font-mono font-semibold tabular-nums mb-2"
              style={{
                fontSize: "20px",
                color: "var(--text-3)",
                fontFamily: "var(--font-mono)",
              }}
            >
              ${summary.equity.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </p>

            {/* Stats row */}
            <div className="flex items-center gap-3" style={{ fontSize: "11px", color: "var(--text-1)" }}>
              <span className="tabular-nums">{summary.num_positions} pos</span>
              <span style={{ color: "var(--border-2)" }}>·</span>
              <span className="tabular-nums">${summary.cash.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} cash</span>
              {summary.regime && (
                <>
                  <span style={{ color: "var(--border-2)" }}>·</span>
                  <span style={{ color: regimeColor }}>{summary.regime}</span>
                </>
              )}
            </div>
          </>
        )}
      </button>
    </div>
  );
}

export default function OverviewPage() {
  const [showCreate, setShowCreate] = useState(false);
  const { data: overview, isLoading: overviewLoading } = useOverview();
  const { data: portfolioList } = usePortfolios();

  if (overviewLoading) {
    return (
      <div
        className="flex-1 flex items-center justify-center"
        style={{ background: "var(--surface-0)" }}
      >
        <p className="animate-pulse" style={{ color: "var(--text-1)" }}>
          Loading portfolios...
        </p>
      </div>
    );
  }

  const summaries = overview?.portfolios ?? [];
  const names = new Map(
    (portfolioList?.portfolios ?? []).map((p) => [p.id, p.name])
  );

  // Enrich summaries with names from registry if missing
  const enriched = summaries.map((s) => ({
    ...s,
    name: s.name || names.get(s.id) || s.id,
  }));

  return (
    <div className="flex-1 flex flex-col overflow-y-auto" style={{ background: "var(--surface-0)" }}>
      <AggregateBar
        totalEquity={overview?.total_equity ?? 0}
        totalCash={overview?.total_cash ?? 0}
        totalDayPnl={overview?.total_day_pnl ?? 0}
        portfolioCount={enriched.length}
      />

      <div className="p-6">
        <h2
          className="uppercase tracking-wider mb-4 font-semibold"
          style={{ fontSize: "11px", color: "var(--text-1)" }}
        >
          Your Portfolios
        </h2>

        {enriched.length === 0 ? (
          <div className="text-center py-12" style={{ color: "var(--text-1)" }}>
            <p className="text-lg mb-2">No portfolios yet</p>
            <p className="text-sm">Create your first portfolio to get started.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-[10px]">
            {enriched.map((s, i) => (
              <div key={s.id} className={`anim d${Math.min(i + 1, 5)}`}>
                <PortfolioCard summary={s} />
              </div>
            ))}

            {/* Add portfolio card */}
            <button
              onClick={() => setShowCreate(true)}
              className="flex flex-col items-center justify-center p-4 card-hover min-h-[120px]"
              style={{
                background: "var(--surface-1)",
                border: "1px solid var(--border-0)",
                borderRadius: "8px",
              }}
            >
              <span className="text-xl mb-1" style={{ color: "var(--text-1)" }}>+</span>
              <span
                className="uppercase tracking-wider"
                style={{ fontSize: "11px", color: "var(--text-1)" }}
              >
                New Portfolio
              </span>
            </button>
          </div>
        )}
      </div>

      {showCreate && <CreatePortfolioModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
