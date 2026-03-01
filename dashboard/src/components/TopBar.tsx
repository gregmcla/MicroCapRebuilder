/** Top bar — brand + portfolio left | market indices center | action buttons right. */

import { useState, useRef, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { PortfolioState } from "../lib/types";
import { useAnalysisStore, useFreshnessStore, usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import { useMarketIndices } from "../hooks/useMarketIndices";
import FreshnessIndicator from "./FreshnessIndicator";
import PortfolioSwitcher from "./PortfolioSwitcher";

// ── Shared button style constants ────────────────────────────────────────────

const primaryBtn =
  "inline-flex items-center justify-center px-3.5 text-xs font-semibold text-white rounded-[6px] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
  + " bg-[var(--accent)] shadow-[0_0_12px_rgba(124,92,252,0.3)]"
  + " hover:bg-[var(--accent-bright)] hover:shadow-[0_0_18px_rgba(124,92,252,0.45)]";

const ghostBtn =
  "inline-flex items-center justify-center px-3.5 text-xs font-semibold rounded-[6px] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
  + " border border-[var(--border-1)] bg-transparent"
  + " text-[var(--text-1)]"
  + " hover:border-[var(--border-2)]";

const BTN_H = "h-[32px]";

// ── Market indices (center) ───────────────────────────────────────────────────

function IndexTile({ label, value, changePct, sparkline }: {
  label: string; value: number; changePct: number; sparkline: number[];
}) {
  const W = 52; const H = 20;
  const up = changePct >= 0;
  const color = up ? "var(--green)" : "var(--red)";

  const points = useMemo(() => {
    if (sparkline.length < 2) return "";
    const min = Math.min(...sparkline);
    const max = Math.max(...sparkline);
    const range = max - min || 1;
    return sparkline.map((v, i) => {
      const x = (i / (sparkline.length - 1)) * W;
      const y = H - 1 - ((v - min) / range) * (H - 3);
      return `${x},${y}`;
    }).join(" ");
  }, [sparkline]);

  return (
    <div className="flex items-center gap-2">
      <span
        style={{
          fontSize: "11px",
          textTransform: "uppercase",
          letterSpacing: "0.07em",
          color: "var(--text-0)",
          fontFamily: "var(--font-sans)",
        }}
      >
        {label}
      </span>
      <span className="font-mono tabular-nums" style={{ fontSize: "13.5px", color: "var(--text-3)" }}>
        {value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
      <span className="font-mono tabular-nums font-semibold" style={{ fontSize: "11.5px", color }}>
        {up ? "+" : ""}{changePct.toFixed(2)}%
      </span>
      {points && (
        <svg width={W} height={H} style={{ display: "block", flexShrink: 0 }}>
          <polyline
            points={points}
            fill="none"
            stroke={color}
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      )}
    </div>
  );
}

function MarketIndices() {
  const { data, isError } = useMarketIndices();

  const items = [
    { key: "sp500" as const,       label: "S&P 500"      },
    { key: "russell2000" as const, label: "Russell 2000" },
    { key: "vix" as const,         label: "VIX"          },
  ];

  return (
    <div className="flex items-center gap-8">
      {items.map(({ key, label }) => {
        const d = data?.[key];
        if (!d || isError) {
          return (
            <div key={key} className="flex items-center gap-2">
              <span style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--text-0)" }}>
                {label}
              </span>
              <span style={{ fontSize: "13px", color: "var(--text-0)" }}>—</span>
            </div>
          );
        }
        return (
          <IndexTile
            key={key}
            label={label}
            value={d.value}
            changePct={d.change_pct}
            sparkline={d.sparkline}
          />
        );
      })}
    </div>
  );
}

// ── Action buttons ────────────────────────────────────────────────────────────

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
      setResult(`Updated ${res.num_positions}`);
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
      queryClient.invalidateQueries({ queryKey: ["chartData"] });
      setTimeout(() => setResult(null), 3000);
    } catch (e) {
      setResult("Failed");
      setTimeout(() => setResult(null), 5000);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="flex items-center gap-1.5">
      <button onClick={handleUpdate} disabled={updating} className={`${ghostBtn} ${BTN_H}`}>
        {updating ? "Updating..." : "UPDATE"}
      </button>
      {result && <span className="text-[10px]" style={{ color: "var(--text-0)" }}>{result}</span>}
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
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
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
    const startedAt = Date.now();
    const MAX_POLL_MS = 10 * 60 * 1000;
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.scanStatus(portfolioId);
        if (status.status === "complete" && status.result) {
          stopPolling(); setScanning(false);
          setResult(`Found ${status.result.discovered}, added ${status.result.added}`);
          queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
          setTimeout(() => setResult(null), 5000);
        } else if (status.status === "error") {
          stopPolling(); setScanning(false);
          setResult(status.error ?? "Scan failed");
          setTimeout(() => setResult(null), 5000);
        } else if (status.status === "idle" || Date.now() - startedAt > MAX_POLL_MS) {
          stopPolling(); setScanning(false);
          setTimeout(() => setResult(null), 5000);
        }
      } catch { /* keep polling */ }
    }, 10_000);
  };

  return (
    <div className="flex items-center gap-1.5">
      <button onClick={handleScan} disabled={scanning} className={`${ghostBtn} ${BTN_H}`}>
        {scanning ? "Scanning..." : "SCAN"}
      </button>
      {result && <span className="text-[10px]" style={{ color: "var(--text-0)" }}>{result}</span>}
    </div>
  );
}

function AnalyzeExecuteButtons() {
  const { result, isAnalyzing, isExecuting, runAnalysis, runExecute } = useAnalysisStore();
  const actionCount = result ? result.summary.approved + result.summary.modified : 0;

  return (
    <>
      <button onClick={runAnalysis} disabled={isAnalyzing} className={`${primaryBtn} ${BTN_H}`}>
        {isAnalyzing ? "Analyzing..." : "ANALYZE"}
      </button>
      {actionCount > 0 && (
        <button onClick={runExecute} disabled={isExecuting} className={`${primaryBtn} ${BTN_H}`}>
          {isExecuting ? "Executing..." : `EXECUTE ${actionCount}`}
        </button>
      )}
    </>
  );
}

function EmergencyClose({ positions }: { positions: PortfolioState["positions"] }) {
  const queryClient = useQueryClient();
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [showConfirm, setShowConfirm] = useState(false);
  const [closing, setClosing] = useState(false);

  const handleClose = async () => {
    setClosing(true);
    setShowConfirm(false);
    try {
      await api.closeAll(portfolioId);
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
    } catch { /* noop */ } finally {
      setClosing(false);
    }
  };

  if (!positions || positions.length === 0) return null;
  const totalValue = positions.reduce((sum, p) => sum + p.market_value, 0);

  const closeBtn =
    `${BTN_H} inline-flex items-center justify-center px-3.5 text-xs font-semibold rounded-[6px] transition-all disabled:opacity-50`
    + " border border-[rgba(248,113,113,0.30)] bg-transparent text-[rgba(248,113,113,0.70)]"
    + " hover:border-[rgba(248,113,113,0.50)] hover:text-[var(--red)]";

  return (
    <>
      <button onClick={() => setShowConfirm(true)} disabled={closing} className={closeBtn}>
        {closing ? "..." : "CLOSE ALL"}
      </button>
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-bg-elevated border border-border rounded-lg p-4 max-w-md">
            <h3 className="text-sm font-semibold text-loss mb-2">Emergency Close All Positions?</h3>
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
                  <span>Total</span><span>${totalValue.toFixed(2)}</span>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowConfirm(false)} className="px-3 py-1 text-xs font-semibold bg-bg-surface text-text-secondary rounded hover:bg-border transition-colors">Cancel</button>
              <button onClick={handleClose} className="px-3 py-1 text-xs font-semibold bg-loss/15 text-loss rounded hover:bg-loss/25 transition-colors">Yes, Close All</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function ModeToggle({ paperMode }: { paperMode: boolean }) {
  const queryClient = useQueryClient();
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [showConfirm, setShowConfirm] = useState(false);
  const [toggling, setToggling] = useState(false);

  const handleToggle = async () => {
    setToggling(true);
    setShowConfirm(false);
    try {
      await api.toggleMode(portfolioId);
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
    } catch { /* noop */ } finally {
      setToggling(false);
    }
  };

  const targetMode = paperMode ? "LIVE" : "PAPER";

  return (
    <>
      <button
        onClick={() => setShowConfirm(true)}
        disabled={toggling}
        className={`${ghostBtn} ${BTN_H}`}
        style={{ color: paperMode ? "var(--text-1)" : "var(--accent)" }}
      >
        {toggling ? "..." : paperMode ? "PAPER" : "LIVE"}
      </button>
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-bg-elevated border border-border rounded-lg p-4 max-w-sm">
            <h3 className="text-sm font-semibold text-text-primary mb-2">Switch to {targetMode} Mode?</h3>
            <p className="text-xs text-text-muted mb-4">
              {targetMode === "LIVE"
                ? "This will enable LIVE trading with real money. Are you sure?"
                : "This will switch to paper trading mode (simulated)."}
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowConfirm(false)} className="px-3 py-1 text-xs font-semibold bg-bg-surface text-text-primary rounded hover:bg-border transition-colors">Cancel</button>
              <button onClick={handleToggle} className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${targetMode === "LIVE" ? "bg-loss/15 text-loss hover:bg-loss/25" : "bg-warning/15 text-warning hover:bg-warning/25"}`}>
                Switch to {targetMode}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── Main TopBar ───────────────────────────────────────────────────────────────

export default function TopBar({
  state,
  isLoading,
}: {
  state: PortfolioState | undefined;
  isLoading: boolean;
}) {
  return (
    <header
      className="flex items-center gap-4 px-4 shrink-0 border-b"
      style={{
        height: "52px",
        background: "var(--surface-0)",
        borderColor: "var(--border-0)",
      }}
    >
      {/* Left: brand + portfolio switcher */}
      <div className="flex items-center gap-3 shrink-0">
        <button
          onClick={() => usePortfolioStore.getState().setPortfolio("overview")}
          className="flex items-center gap-1.5 hover:opacity-70 transition-opacity"
        >
          <span className="font-mono font-bold" style={{ fontSize: "15px", color: "var(--accent)" }}>M</span>
          <span className="font-semibold tracking-widest uppercase" style={{ fontSize: "11px", color: "var(--accent)" }}>
            MOMMY
          </span>
        </button>
        <span style={{ color: "var(--border-1)", fontSize: "16px", fontWeight: 300 }}>|</span>
        <PortfolioSwitcher />
        <FreshnessIndicator />
      </div>

      {/* Center: market indices */}
      <div className="flex-1 flex justify-center min-w-0">
        <MarketIndices />
      </div>

      {/* Right: action buttons */}
      <div className="flex items-center gap-2 shrink-0">
        {(state?.stale_alerts.length ?? 0) > 0 && (
          <span className="text-[10px] text-warning">{state!.stale_alerts.length} stale</span>
        )}
        {(state?.price_failures.length ?? 0) > 0 && (
          <span className="text-[10px] text-loss">{state!.price_failures.length} failed</span>
        )}
        {isLoading && (
          <span className="text-[10px] text-text-muted animate-pulse">Loading...</span>
        )}
        <UpdatePricesButton />
        <ScanButton />
        <span style={{ width: "1px", height: "20px", background: "var(--border-1)", flexShrink: 0 }} />
        <AnalyzeExecuteButtons />
        {state && <EmergencyClose positions={state.positions} />}
        {state && <ModeToggle paperMode={state.paper_mode} />}
      </div>
    </header>
  );
}
