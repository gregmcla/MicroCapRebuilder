/** Top bar — brand + portfolio left | market indices center | action buttons right. */

import { useState, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { PortfolioState } from "../lib/types";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import { useMarketIndices } from "../hooks/useMarketIndices";
import FreshnessIndicator from "./FreshnessIndicator";
import PortfolioSwitcher from "./PortfolioSwitcher";
import PortfolioSettingsModal from "./PortfolioSettingsModal";
import GScottLogo from "./GScottLogo";

// ── Shared button style constants ────────────────────────────────────────────


const ghostBtn =
  "inline-flex items-center justify-center px-3.5 text-xs font-semibold rounded-[6px] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
  + " border border-[var(--border-1)] bg-transparent"
  + " text-[var(--text-1)]"
  + " hover:border-[var(--border-2)]";

const BTN_H = "h-[32px]";

// ── Market indices (center) ───────────────────────────────────────────────────

function VDivider() {
  return <div style={{ width: "1px", height: "28px", background: "var(--border-1)", flexShrink: 0, opacity: 0.6 }} />;
}

function IndexTile({ label, value, changePct, sparkline }: {
  label: string; value: number; changePct: number; sparkline: number[];
}) {
  const W = 56; const H = 22;
  const up = changePct >= 0;
  const color = up ? "var(--green)" : "var(--red)";

  const points = useMemo(() => {
    if (sparkline.length < 2) return "";
    const min = Math.min(...sparkline);
    const max = Math.max(...sparkline);
    const range = max - min || 1;
    return sparkline.map((v, i) => {
      const x = (i / (sparkline.length - 1)) * W;
      const y = H - 2 - ((v - min) / range) * (H - 4);
      return `${x},${y}`;
    }).join(" ");
  }, [sparkline]);

  return (
    <div className="flex items-center gap-3 px-5">
      <div className="flex flex-col gap-0.5">
        <span style={{
          fontSize: "9px",
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          color: "var(--text-0)",
          fontFamily: "var(--font-sans)",
          lineHeight: 1,
        }}>
          {label}
        </span>
        <div className="flex items-baseline gap-2">
          <span className="font-mono tabular-nums" style={{ fontSize: "14px", color: "var(--text-3)", letterSpacing: "-0.02em", lineHeight: 1 }}>
            {value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          <span className="font-mono tabular-nums font-semibold" style={{ fontSize: "11px", color, lineHeight: 1 }}>
            {up ? "+" : ""}{changePct.toFixed(2)}%
          </span>
        </div>
      </div>
      {points && (
        <svg width={W} height={H} style={{ display: "block", flexShrink: 0, opacity: 0.85 }}>
          <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
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
    <div className="flex items-center">
      {items.map(({ key, label }, i) => {
        const d = data?.[key];
        return (
          <div key={key} className="flex items-center">
            {i > 0 && <VDivider />}
            {!d || isError ? (
              <div className="flex flex-col gap-0.5 px-5">
                <span style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-0)" }}>{label}</span>
                <span style={{ fontSize: "14px", color: "var(--text-0)", fontFamily: "var(--font-mono)" }}>—</span>
              </div>
            ) : (
              <IndexTile label={label} value={d.value} changePct={d.change_pct} sparkline={d.sparkline} />
            )}
          </div>
        );
      })}
    </div>
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
              You sure, sweetheart? GScott will close everything if that's what you need. I've got you.
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
        className="inline-flex items-center gap-1.5 px-3 rounded-full transition-all disabled:opacity-40 cursor-pointer"
        style={{
          height: "26px",
          fontSize: "11px",
          fontWeight: 600,
          letterSpacing: "0.06em",
          background: paperMode ? "rgba(255,255,255,0.04)" : "rgba(34,197,94,0.10)",
          border: paperMode ? "1px solid rgba(255,255,255,0.10)" : "1px solid rgba(34,197,94,0.30)",
          color: paperMode ? "var(--text-1)" : "#22c55e",
        }}
      >
        {!paperMode && (
          <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#22c55e", flexShrink: 0, boxShadow: "0 0 6px #22c55e" }} className="animate-pulse" />
        )}
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

function LogsButton() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const isActive = portfolioId === "logs";

  return (
    <button
      onClick={() => setPortfolio(isActive ? "overview" : "logs")}
      className={`${BTN_H} px-3 rounded font-mono text-xs tracking-wider transition-colors ${
        isActive
          ? "bg-zinc-700 text-zinc-200"
          : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
      }`}
    >
      LOGS
    </button>
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
  const [showSettings, setShowSettings] = useState(false);

  return (
    <header
      className="flex items-center shrink-0 overflow-visible"
      style={{
        height: "72px",
        background: "linear-gradient(180deg, #0e0e1a 0%, #080810 100%)",
        borderBottom: "1px solid rgba(124,92,252,0.14)",
      }}
    >
      {/* Left: logo */}
      <button
        onClick={() => usePortfolioStore.getState().setPortfolio("overview")}
        className="flex items-center justify-center hover:opacity-75 transition-opacity shrink-0"
        style={{ height: "72px", padding: "0 20px 0 16px", cursor: "pointer" }}
      >
        <GScottLogo height={52} />
      </button>

      {/* Divider */}
      <VDivider />

      {/* Portfolio + freshness */}
      <div className="flex flex-col justify-center gap-1 shrink-0 px-4">
        <div className="flex items-center gap-2">
          <PortfolioSwitcher />
          {state?.ai_driven && (
            <button
              onClick={() => setShowSettings(true)}
              title="Strategy DNA"
              className="transition-colors"
              style={{
                background: "none",
                border: "1px solid var(--border-1)",
                borderRadius: "5px",
                color: "var(--text-0)",
                cursor: "pointer",
                width: "22px",
                height: "22px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "12px",
                lineHeight: 1,
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = "var(--accent)"; (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)"; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = "var(--text-0)"; (e.currentTarget as HTMLElement).style.borderColor = "var(--border-1)"; }}
            >
              ⚙
            </button>
          )}
        </div>
        <FreshnessIndicator />
      </div>
      {showSettings && state?.ai_driven && <PortfolioSettingsModal onClose={() => setShowSettings(false)} />}

      {/* Divider */}
      <VDivider />

      {/* Center: market indices */}
      <div className="flex-1 flex justify-center items-center min-w-0">
        <MarketIndices />
      </div>

      {/* Divider */}
      <VDivider />

      {/* Right: alerts + controls */}
      <div className="flex items-center gap-3 shrink-0 px-4">
        {(state?.stale_alerts.length ?? 0) > 0 && (
          <span style={{ fontSize: "10px", color: "var(--amber)", letterSpacing: "0.04em" }}>
            {state!.stale_alerts.length} stale
          </span>
        )}
        {(state?.price_failures.length ?? 0) > 0 && (
          <span style={{ fontSize: "10px", color: "var(--red)", letterSpacing: "0.04em" }}>
            {state!.price_failures.length} failed
          </span>
        )}
        {isLoading && (
          <span className="animate-pulse" style={{ fontSize: "10px", color: "var(--text-0)" }}>syncing</span>
        )}
        <LogsButton />
        {state && <EmergencyClose positions={state.positions} />}
        {state && <ModeToggle paperMode={state.paper_mode} />}
      </div>
    </header>
  );
}
