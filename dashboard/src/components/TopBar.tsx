/** Top bar — always pinned, key metrics + action buttons. */

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { PortfolioState } from "../lib/types";
import { useAnalysisStore, useFreshnessStore } from "../lib/store";
import { useRisk } from "../hooks/useRisk";
import { api } from "../lib/api";
import FreshnessIndicator from "./FreshnessIndicator";

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

function UpdatePricesButton() {
  const queryClient = useQueryClient();
  const updateTimestamp = useFreshnessStore((s) => s.updateTimestamp);
  const [updating, setUpdating] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleUpdate = async () => {
    setUpdating(true);
    setResult(null);
    try {
      const res = await api.updatePrices();
      updateTimestamp("positions");
      setResult(`Updated ${res.num_positions} positions`);
      // Invalidate state query to refetch with new prices
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
      // Also invalidate chart data to refresh sparklines
      queryClient.invalidateQueries({ queryKey: ["chartData"] });
      setTimeout(() => setResult(null), 3000);
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Update failed");
      setTimeout(() => setResult(null), 5000);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="flex items-center gap-1.5">
      <button
        onClick={handleUpdate}
        disabled={updating}
        className="px-3 py-1 text-xs font-semibold bg-bg-elevated text-text-primary rounded hover:bg-border disabled:opacity-50 transition-colors"
      >
        {updating ? "Updating..." : "UPDATE"}
      </button>
      {result && (
        <span className="text-xs text-text-muted">{result}</span>
      )}
    </div>
  );
}

function ModeToggle({ paperMode }: { paperMode: boolean }) {
  const queryClient = useQueryClient();
  const [showConfirm, setShowConfirm] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleToggle = async () => {
    setToggling(true);
    setResult(null);
    setShowConfirm(false);
    try {
      const res = await api.toggleMode();
      setResult(res.message);
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
      setTimeout(() => setResult(null), 3000);
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Toggle failed");
      setTimeout(() => setResult(null), 5000);
    } finally {
      setToggling(false);
    }
  };

  const targetMode = paperMode ? "LIVE" : "PAPER";

  return (
    <div className="relative flex items-center gap-1.5">
      <button
        onClick={() => setShowConfirm(true)}
        disabled={toggling}
        className={`text-xs px-2 py-0.5 rounded font-semibold tracking-wider transition-colors disabled:opacity-50 ${
          paperMode
            ? "bg-warning/15 text-warning hover:bg-warning/25"
            : "bg-loss/15 text-loss hover:bg-loss/25"
        }`}
      >
        {toggling ? "..." : paperMode ? "PAPER" : "LIVE"}
      </button>
      {result && (
        <span className="text-xs text-text-muted absolute left-full ml-2 whitespace-nowrap">
          {result}
        </span>
      )}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-bg-elevated border border-border rounded-lg p-4 max-w-sm">
            <h3 className="text-sm font-semibold text-text-primary mb-2">
              Switch to {targetMode} Mode?
            </h3>
            <p className="text-xs text-text-muted mb-4">
              {targetMode === "LIVE"
                ? "This will enable LIVE trading with real money. Are you sure?"
                : "This will switch to paper trading mode (simulated)."}
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-3 py-1 text-xs font-semibold bg-bg-surface text-text-primary rounded hover:bg-border transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleToggle}
                className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${
                  targetMode === "LIVE"
                    ? "bg-loss/15 text-loss hover:bg-loss/25"
                    : "bg-warning/15 text-warning hover:bg-warning/25"
                }`}
              >
                Switch to {targetMode}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function EmergencyClose({ positions }: { positions: PortfolioState["positions"] }) {
  const queryClient = useQueryClient();
  const [showConfirm, setShowConfirm] = useState(false);
  const [closing, setClosing] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleClose = async () => {
    setClosing(true);
    setResult(null);
    setShowConfirm(false);
    try {
      const res = await api.closeAll();
      setResult(res.message);
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
      setTimeout(() => setResult(null), 5000);
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Emergency close failed");
      setTimeout(() => setResult(null), 5000);
    } finally {
      setClosing(false);
    }
  };

  if (!positions || positions.length === 0) return null;

  const totalValue = positions.reduce((sum, p) => sum + p.market_value, 0);

  return (
    <div className="relative flex items-center gap-1.5">
      <button
        onClick={() => setShowConfirm(true)}
        disabled={closing}
        className="text-xs px-2 py-0.5 rounded font-semibold tracking-wider bg-loss/15 text-loss hover:bg-loss/25 transition-colors disabled:opacity-50"
      >
        {closing ? "..." : "CLOSE ALL"}
      </button>
      {result && (
        <span className="text-xs text-text-muted absolute left-full ml-2 whitespace-nowrap">
          {result}
        </span>
      )}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-bg-elevated border border-border rounded-lg p-4 max-w-md">
            <h3 className="text-sm font-semibold text-loss mb-2">
              Emergency Close All Positions?
            </h3>
            <p className="text-xs text-text-muted mb-3">
              You sure, sweetheart? Mommy will close everything if that's what you need. I've got you.
            </p>
            <div className="bg-bg-surface rounded p-2 mb-3 max-h-32 overflow-y-auto">
              <div className="text-xs space-y-1">
                {positions.map((p) => (
                  <div key={p.ticker} className="flex justify-between items-center">
                    <span className="font-semibold">{p.ticker}</span>
                    <span className="text-text-muted">
                      {p.shares} @ ${p.current_price.toFixed(2)} = ${p.market_value.toFixed(2)}
                      <span className={p.unrealized_pnl >= 0 ? "text-profit ml-1" : "text-loss ml-1"}>
                        ({p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl_pct.toFixed(1)}%)
                      </span>
                    </span>
                  </div>
                ))}
                <div className="border-t border-border mt-2 pt-1 flex justify-between font-semibold">
                  <span>Total</span>
                  <span>${totalValue.toFixed(2)}</span>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-3 py-1 text-xs font-semibold bg-bg-surface text-text-secondary rounded hover:bg-border transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleClose}
                className="px-3 py-1 text-xs font-semibold bg-loss/15 text-loss rounded hover:bg-loss/25 transition-colors"
              >
                Yes, Close All
              </button>
            </div>
          </div>
        </div>
      )}
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
      <FreshnessIndicator />
      <UpdatePricesButton />
      <button
        onClick={runAnalysis}
        disabled={isAnalyzing}
        className="px-3 py-1 text-xs font-semibold bg-accent/15 text-accent rounded hover:bg-accent/25 shadow-[0_0_8px_rgba(34,211,238,0.5)] disabled:opacity-50 transition-colors"
      >
        {isAnalyzing ? "Analyzing..." : "ANALYZE"}
      </button>
      {actionCount > 0 && (
        <button
          onClick={runExecute}
          disabled={isExecuting}
          className="px-3 py-1 text-xs font-semibold bg-profit/15 text-profit rounded hover:bg-profit/25 shadow-[0_0_8px_rgba(16,185,129,0.5)] disabled:opacity-50 transition-colors"
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

      {/* Emergency Close */}
      <EmergencyClose positions={state.positions} />

      {/* Mode Toggle */}
      <ModeToggle paperMode={state.paper_mode} />
    </header>
  );
}
