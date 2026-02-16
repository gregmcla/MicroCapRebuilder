/** Overview page — shown when activePortfolioId === "overview". */

import { useOverview, usePortfolios } from "../hooks/usePortfolios";
import { usePortfolioStore } from "../lib/store";
import type { PortfolioSummary } from "../lib/types";

const UNIVERSE_COLORS: Record<string, string> = {
  microcap: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  smallcap: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  midcap: "bg-teal-500/20 text-teal-400 border-teal-500/30",
  largecap: "bg-green-500/20 text-green-400 border-green-500/30",
  custom: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

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
    totalDayPnl > 0 ? "text-green-400" : totalDayPnl < 0 ? "text-red-400" : "text-text-primary";

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
        <p className="font-mono text-lg font-semibold text-accent">{portfolioCount}</p>
      </div>
    </div>
  );
}

function PortfolioCard({ summary }: { summary: PortfolioSummary }) {
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const universeClass = UNIVERSE_COLORS[summary.universe] ?? UNIVERSE_COLORS.custom;

  return (
    <button
      onClick={() => setPortfolio(summary.id)}
      className="text-left bg-bg-surface border border-border rounded-lg p-4 hover:border-accent/50 hover:shadow-[0_0_12px_rgba(34,211,238,0.1)] transition-all group"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-text-primary group-hover:text-accent transition-colors">
          {summary.name}
        </h3>
        <div className="flex items-center gap-1.5">
          <span className={`text-[10px] px-1.5 py-0.5 rounded border ${universeClass}`}>
            {summary.universe}
          </span>
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
              summary.paper_mode
                ? "bg-yellow-500/15 text-yellow-400"
                : "bg-red-500/15 text-red-400"
            }`}
          >
            {summary.paper_mode ? "PAPER" : "LIVE"}
          </span>
        </div>
      </div>

      {/* Error state */}
      {summary.error ? (
        <div className="text-xs text-red-400 bg-red-500/10 rounded p-2">
          {summary.error}
        </div>
      ) : (
        <>
          {/* Equity */}
          <p className="font-mono text-xl font-bold text-text-primary mb-2">
            ${summary.equity.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
          </p>

          {/* Stats row */}
          <div className="flex items-center gap-4 text-xs text-text-muted">
            <span>
              {summary.num_positions} position{summary.num_positions !== 1 ? "s" : ""}
            </span>
            <span>
              Cash: ${summary.cash.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </span>
            {summary.regime && (
              <span
                className={
                  summary.regime === "BULL"
                    ? "text-green-400"
                    : summary.regime === "BEAR"
                      ? "text-red-400"
                      : "text-yellow-400"
                }
              >
                {summary.regime}
              </span>
            )}
          </div>
        </>
      )}
    </button>
  );
}

export default function OverviewPage() {
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {enriched.map((s) => (
              <PortfolioCard key={s.id} summary={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
