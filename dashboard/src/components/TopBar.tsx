/** Top bar — always pinned, key metrics + action buttons. */

import { useState, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { PortfolioState } from "../lib/types";
import { useAnalysisStore, useFreshnessStore, usePortfolioStore } from "../lib/store";
import { useRisk } from "../hooks/useRisk";
import { api } from "../lib/api";
import FreshnessIndicator from "./FreshnessIndicator";
import PortfolioSwitcher from "./PortfolioSwitcher";

function RegimeBadge({ regime }: { regime: string }) {
  const cfg: Record<string, { icon: string; cls: string }> = {
    BULL: { icon: "🐂", cls: "text-profit" },
    BEAR: { icon: "🐻", cls: "text-loss" },
    SIDEWAYS: { icon: "↔️", cls: "text-warning" },
  };
  const { icon, cls } = cfg[regime] ?? cfg.SIDEWAYS;
  return (
    <span className={`text-xs font-semibold ${cls}`}>
      {icon} {regime}
    </span>
  );
}

function RiskBadge() {
  const { data: risk } = useRisk();
  const score = risk?.overall_score;
  const color =
    score == null ? "text-text-muted"
    : score >= 70 ? "text-profit"
    : score >= 40 ? "text-warning"
    : "text-loss";
  return (
    <span className={`font-mono text-xs ${color}`}>
      {score != null ? Math.round(score) : "--"}
    </span>
  );
}

function UpdatePricesButton() {
  const queryClient = useQueryClient();
  const updateTimestamp = useFreshnessStore((s) => s.updateTimestamp);
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [updating, setUpdating] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleUpdate = async () => {
    setUpdating(true);
    setResult(null);
    try {
      const res = await api.updatePrices(portfolioId);
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
        className="px-2.5 py-0.5 text-xs font-semibold border border-border text-text-secondary hover:border-border-hover hover:text-text-primary rounded-sm transition-colors disabled:opacity-40"
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
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [showConfirm, setShowConfirm] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleToggle = async () => {
    setToggling(true);
    setResult(null);
    setShowConfirm(false);
    try {
      const res = await api.toggleMode(portfolioId);
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
        className={`text-xs px-2 py-0.5 rounded-sm font-semibold tracking-wider transition-colors disabled:opacity-50 ${
          paperMode
            ? "text-warning hover:text-warning/80"
            : "text-loss hover:text-loss/80"
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
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [showConfirm, setShowConfirm] = useState(false);
  const [closing, setClosing] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleClose = async () => {
    setClosing(true);
    setResult(null);
    setShowConfirm(false);
    try {
      const res = await api.closeAll(portfolioId);
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
        className="text-xs px-2 py-0.5 rounded-sm font-semibold tracking-wider border border-loss/40 text-loss hover:bg-loss/10 transition-colors disabled:opacity-50"
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

function ScanButton() {
  const queryClient = useQueryClient();
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const handleScan = async () => {
    setScanning(true);
    setResult(null);
    try {
      await api.scan(portfolioId);
    } catch (e) {
      setScanning(false);
      setResult(e instanceof Error ? e.message : "Scan failed");
      setTimeout(() => setResult(null), 5000);
      return;
    }

    // Poll for completion every 10s, max 10 minutes
    const startedAt = Date.now();
    const MAX_POLL_MS = 10 * 60 * 1000;
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.scanStatus(portfolioId);
        if (status.status === "complete" && status.result) {
          stopPolling();
          setScanning(false);
          setResult(`Found ${status.result.discovered}, added ${status.result.added}`);
          queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
          setTimeout(() => setResult(null), 5000);
        } else if (status.status === "error") {
          stopPolling();
          setScanning(false);
          setResult(status.error ?? "Scan failed");
          setTimeout(() => setResult(null), 5000);
        } else if (status.status === "idle" || Date.now() - startedAt > MAX_POLL_MS) {
          // Server restarted (lost job state) or timed out
          stopPolling();
          setScanning(false);
          setResult(Date.now() - startedAt > MAX_POLL_MS ? "Scan timed out" : "Scan lost (server restarted)");
          setTimeout(() => setResult(null), 5000);
        }
      } catch {
        // network hiccup — keep polling
      }
    }, 10_000);
  };

  return (
    <div className="flex items-center gap-1.5">
      <button
        onClick={handleScan}
        disabled={scanning}
        className="px-2.5 py-0.5 text-xs font-semibold border border-border text-text-secondary hover:border-border-hover hover:text-text-primary rounded-sm transition-colors disabled:opacity-50"
      >
        {scanning ? "Scanning..." : "SCAN"}
      </button>
      {result && (
        <span className="text-xs text-text-muted">{result}</span>
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
      <button
        onClick={runAnalysis}
        disabled={isAnalyzing}
        className="px-4 py-1 text-xs font-bold bg-accent text-black rounded-sm hover:bg-accent/90 disabled:opacity-40 transition-colors"
      >
        {isAnalyzing ? "Analyzing..." : "ANALYZE"}
      </button>
      {actionCount > 0 && (
        <button
          onClick={runExecute}
          disabled={isExecuting}
          className="px-3 py-1 text-xs font-semibold border border-accent/40 text-accent rounded-sm hover:bg-accent/10 disabled:opacity-40 transition-colors"
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
      <header className="h-9 flex items-center gap-3 px-4 bg-bg-surface border-b border-border shrink-0">
        <button
          onClick={() => usePortfolioStore.getState().setPortfolio("overview")}
          className="flex items-center gap-1.5 shrink-0 hover:opacity-70 transition-opacity"
        >
          <span className="text-sm font-bold text-accent font-mono">M</span>
          <span className="text-[10px] font-semibold text-text-secondary tracking-widest uppercase">MOMMY</span>
        </button>
        <span className="text-border text-xs">|</span>
        <PortfolioSwitcher />
        {isLoading && <span className="text-[10px] text-text-muted animate-pulse">Loading...</span>}
      </header>
    );
  }

  const pnlColor = state.day_pnl >= 0 ? "text-profit" : "text-loss";

  return (
    <header className="h-9 flex items-center gap-3 px-4 bg-bg-surface border-b border-border shrink-0">
      <button
        onClick={() => usePortfolioStore.getState().setPortfolio("overview")}
        className="flex items-center gap-1.5 shrink-0 hover:opacity-70 transition-opacity"
      >
        <span className="text-sm font-bold text-accent font-mono">M</span>
        <span className="text-[10px] font-semibold text-text-secondary tracking-widest uppercase">MOMMY</span>
      </button>
      <span className="text-text-muted text-xs">|</span>
      <PortfolioSwitcher />
      <span className="text-text-muted text-xs">·</span>
      <span className="font-mono text-xs text-text-primary tabular-nums">
        ${state.total_equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      </span>
      <span className="text-[9px] text-text-muted">eq</span>
      <span className={`font-mono text-xs tabular-nums ${pnlColor}`}>
        {state.day_pnl >= 0 ? "+" : ""}${state.day_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      </span>
      <span className="text-[9px] text-text-muted">day</span>
      <span className="text-text-muted text-xs">·</span>
      <RegimeBadge regime={state.regime ?? "SIDEWAYS"} />
      <RiskBadge />
      <span className="text-text-muted text-xs">·</span>
      <span className="font-mono text-[10px] text-text-muted tabular-nums">
        {Math.round((state.positions_value / (state.total_equity || 1)) * 100)}% dep
      </span>
      <span className="text-text-muted text-xs">·</span>
      <FreshnessIndicator />
      <div className="flex-1" />
      {state.stale_alerts.length > 0 && (
        <span className="text-[10px] text-warning">{state.stale_alerts.length} stale</span>
      )}
      {state.price_failures.length > 0 && (
        <span className="text-[10px] text-loss">{state.price_failures.length} failed</span>
      )}
      {/* Action buttons */}
      <div className="flex items-center gap-2 border-l border-border pl-3">
        <div className="flex items-center gap-2">
          <UpdatePricesButton />
          <ScanButton />
        </div>
        <span className="text-border text-xs">|</span>
        <AnalyzeExecuteButtons />
      </div>
      <EmergencyClose positions={state.positions} />
      <ModeToggle paperMode={state.paper_mode} />
    </header>
  );
}
