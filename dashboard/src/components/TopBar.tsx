/** Top bar — always pinned, key metrics + action buttons. */

import type { PortfolioState } from "../lib/types";
import { useAnalysisStore } from "../lib/store";
import { useRisk } from "../hooks/useRisk";

function MetricPill({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="flex items-center gap-1.5 px-3 py-1 rounded bg-bg-surface">
      <span className="text-xs text-text-muted">{label}</span>
      <span className={`font-mono text-sm font-semibold ${color ?? "text-text-primary"}`}>
        {value}
      </span>
    </div>
  );
}

function RegimeBadge({ regime }: { regime: string }) {
  const cfg: Record<string, { icon: string; cls: string }> = {
    BULL: { icon: "\u{1F402}", cls: "bg-profit/15 text-profit" },
    BEAR: { icon: "\u{1F43B}", cls: "bg-loss/15 text-loss" },
    SIDEWAYS: { icon: "\u{2194}\u{FE0F}", cls: "bg-warning/15 text-warning" },
  };
  const { icon, cls } = cfg[regime] ?? cfg.SIDEWAYS;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {icon} {regime}
    </span>
  );
}

function RiskBadge() {
  const { data: risk } = useRisk();
  const score = risk?.overall_score;
  const color =
    score == null
      ? "text-text-muted border-border"
      : score >= 70
        ? "text-profit border-profit/40"
        : score >= 40
          ? "text-warning border-warning/40"
          : "text-loss border-loss/40";

  return (
    <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${color}`}>
      <span className="text-xs text-text-muted">Risk</span>
      <span className="font-mono text-sm font-semibold">
        {score != null ? Math.round(score) : "--"}
      </span>
    </div>
  );
}

function AnalyzeExecuteButtons() {
  const { result, isAnalyzing, isExecuting, runAnalysis, runExecute } =
    useAnalysisStore();

  const actionCount = result
    ? result.summary.approved + result.summary.modified
    : 0;

  return (
    <div className="flex items-center gap-1.5">
      <button
        onClick={runAnalysis}
        disabled={isAnalyzing}
        className="px-3 py-1 text-xs font-semibold bg-accent/15 text-accent rounded hover:bg-accent/25 disabled:opacity-50 transition-colors"
      >
        {isAnalyzing ? "Analyzing..." : "ANALYZE"}
      </button>
      {actionCount > 0 && (
        <button
          onClick={runExecute}
          disabled={isExecuting}
          className="px-3 py-1 text-xs font-semibold bg-profit/15 text-profit rounded hover:bg-profit/25 disabled:opacity-50 transition-colors"
        >
          {isExecuting ? "Executing..." : `EXECUTE ${actionCount}`}
        </button>
      )}
    </div>
  );
}

export default function TopBar({
  state,
  isLoading,
}: {
  state: PortfolioState | undefined;
  isLoading: boolean;
}) {
  if (isLoading || !state) {
    return (
      <header className="h-12 flex items-center px-4 bg-bg-surface border-b border-border shrink-0">
        <span className="font-semibold text-accent tracking-tight">M</span>
        <span className="ml-1 text-sm font-semibold text-text-secondary tracking-widest">
          MOMMY
        </span>
        <span className="ml-4 text-xs text-text-muted animate-pulse">
          Loading...
        </span>
      </header>
    );
  }

  const pnlColor =
    state.day_pnl > 0
      ? "text-profit"
      : state.day_pnl < 0
        ? "text-loss"
        : "text-text-primary";

  const returnColor =
    state.total_return_pct > 0
      ? "text-profit"
      : state.total_return_pct < 0
        ? "text-loss"
        : "text-text-primary";

  return (
    <header className="h-12 flex items-center gap-3 px-4 bg-bg-surface border-b border-border shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-1 mr-2">
        <span className="text-lg font-bold text-accent">M</span>
        <span className="text-xs font-semibold text-text-secondary tracking-widest">
          MOMMY
        </span>
      </div>

      {/* Metrics */}
      <MetricPill
        label="Equity"
        value={`$${state.total_equity.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
      />
      <MetricPill
        label="Day P&L"
        value={`${state.day_pnl >= 0 ? "+" : ""}$${state.day_pnl.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
        color={pnlColor}
      />
      <MetricPill
        label="Return"
        value={`${state.total_return_pct >= 0 ? "+" : ""}${state.total_return_pct.toFixed(1)}%`}
        color={returnColor}
      />

      {/* Risk badge */}
      <RiskBadge />

      {/* Regime */}
      <RegimeBadge regime={state.regime ?? "SIDEWAYS"} />

      {/* Action buttons */}
      <AnalyzeExecuteButtons />

      {/* Spacer */}
      <div className="flex-1" />

      {/* Warnings */}
      {state.stale_alerts.length > 0 && (
        <span className="text-xs px-2 py-0.5 rounded bg-warning/15 text-warning font-medium">
          {state.stale_alerts.length} stale
        </span>
      )}
      {state.price_failures.length > 0 && (
        <span className="text-xs px-2 py-0.5 rounded bg-loss/15 text-loss font-medium">
          {state.price_failures.length} failed
        </span>
      )}

      {/* Mode */}
      <span
        className={`text-xs px-2 py-0.5 rounded font-semibold tracking-wider ${
          state.paper_mode
            ? "bg-warning/15 text-warning"
            : "bg-loss/15 text-loss"
        }`}
      >
        {state.paper_mode ? "PAPER" : "LIVE"}
      </span>
    </header>
  );
}
