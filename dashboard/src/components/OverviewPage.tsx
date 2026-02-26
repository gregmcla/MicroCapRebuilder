/** Overview page — shown when activePortfolioId === "overview". */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOverview, usePortfolios } from "../hooks/usePortfolios";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
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
  const dayColor =
    totalDayPnl > 0 ? "text-profit" : totalDayPnl < 0 ? "text-loss" : "text-text-primary";

  return (
    <div className="flex items-center gap-6 px-6 py-4 bg-bg-surface border-b border-border">
      <div>
        <p className="text-[10px] text-text-muted uppercase tracking-wider">Total Equity</p>
        <p className="font-mono text-2xl font-bold text-text-primary">
          ${totalEquity.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
        </p>
      </div>
      <div>
        <p className="text-[10px] text-text-muted uppercase tracking-wider">Total Cash</p>
        <p className="font-mono text-lg font-semibold text-text-primary">
          ${totalCash.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
        </p>
      </div>
      <div>
        <p className="text-[10px] text-text-muted uppercase tracking-wider">Day P&L</p>
        <p className={`font-mono text-lg font-semibold ${dayColor}`}>
          {totalDayPnl >= 0 ? "+" : ""}${totalDayPnl.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
        </p>
      </div>
      <div>
        <p className="text-[10px] text-text-muted uppercase tracking-wider">Portfolios</p>
        <p className="font-mono text-lg font-semibold text-text-primary tabular-nums">{portfolioCount}</p>
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
    summary.regime === "BULL" ? "text-profit"
    : summary.regime === "BEAR" ? "text-loss"
    : "text-warning";

  return (
    <div className="relative text-left bg-bg-surface border border-border hover:border-border-hover transition-colors group">
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
        className={`absolute top-2 right-2 text-[10px] px-1.5 py-0.5 transition-colors ${
          confirmDelete
            ? "text-loss font-semibold"
            : "text-text-muted/0 group-hover:text-text-muted/50 hover:!text-loss"
        }`}
      >
        {deleteMutation.isPending ? "..." : confirmDelete ? "Confirm?" : "\u00D7"}
      </button>

      {/* Clickable card body */}
      <button onClick={() => setPortfolio(summary.id)} className="w-full text-left p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3 pr-4">
          <h3 className="text-sm font-bold text-text-primary">
            {summary.name}
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">
              {summary.universe}
            </span>
            <span className={`text-[10px] font-semibold uppercase tracking-wider ${
              summary.paper_mode ? "text-warning" : "text-loss"
            }`}>
              {summary.paper_mode ? "Paper" : "Live"}
            </span>
          </div>
        </div>

        {/* Error state */}
        {summary.error ? (
          <div className="text-xs text-loss">
            {summary.error}
          </div>
        ) : (
          <>
            {/* Equity */}
            <p className="font-mono text-xl font-semibold text-text-primary tabular-nums mb-2">
              ${summary.equity.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </p>

            {/* Stats row */}
            <div className="flex items-center gap-3 text-[11px] text-text-muted">
              <span className="tabular-nums">{summary.num_positions} pos</span>
              <span className="text-text-muted/40">·</span>
              <span className="tabular-nums">${summary.cash.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} cash</span>
              {summary.regime && (
                <>
                  <span className="text-text-muted/40">·</span>
                  <span className={regimeColor}>{summary.regime}</span>
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
      <div className="flex-1 flex items-center justify-center bg-bg-primary">
        <p className="text-text-muted animate-pulse">Loading portfolios...</p>
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
    <div className="flex-1 flex flex-col bg-bg-primary overflow-y-auto">
      <AggregateBar
        totalEquity={overview?.total_equity ?? 0}
        totalCash={overview?.total_cash ?? 0}
        totalDayPnl={overview?.total_day_pnl ?? 0}
        portfolioCount={enriched.length}
      />

      <div className="p-6">
        <h2 className="text-xs font-semibold text-text-secondary tracking-wider uppercase mb-4">
          Your Portfolios
        </h2>

        {enriched.length === 0 ? (
          <div className="text-center py-12 text-text-muted">
            <p className="text-lg mb-2">No portfolios yet</p>
            <p className="text-sm">Create your first portfolio to get started.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-border">
            {enriched.map((s) => (
              <PortfolioCard key={s.id} summary={s} />
            ))}

            {/* Add portfolio card */}
            <button
              onClick={() => setShowCreate(true)}
              className="flex flex-col items-center justify-center p-4 bg-bg-surface hover:bg-bg-elevated transition-colors min-h-[120px]"
            >
              <span className="text-xl text-text-muted mb-1">+</span>
              <span className="text-[11px] text-text-muted uppercase tracking-wider">New Portfolio</span>
            </button>
          </div>
        )}
      </div>

      {showCreate && <CreatePortfolioModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
