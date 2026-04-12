/** Top bar — 48px mission control strip.
 *  Left: logo | portfolio switcher | equity | day P&L
 *  Center: market indices (condensed)
 *  Right: ANALYZE | EXECUTE | UPDATE | SCAN | LOGS | CLOSE ALL | mode
 */

import { useState, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { PortfolioState } from "../lib/types";
import { usePortfolioStore, useUIStore, useBriefStore } from "../lib/store";
import { api } from "../lib/api";
import { useMarketIndices } from "../hooks/useMarketIndices";
import FreshnessIndicator from "./FreshnessIndicator";
import PortfolioSwitcher from "./PortfolioSwitcher";
import PortfolioSettingsModal from "./PortfolioSettingsModal";
import IntelligenceBrief from "./IntelligenceBrief";
import GScottLogo from "./GScottLogo";
import { UpdateButton, ScanButton, AnalyzeExecute } from "./CommandBar";
import BuyModal from "./BuyModal";

// ── Shared ─────────────────────────────────────────────────────────────────────

function VDivider() {
  return (
    <div
      style={{
        width: "1px",
        height: "24px",
        background: "var(--border)",
        flexShrink: 0,
        opacity: 0.5,
      }}
    />
  );
}

// ── Market indices (condensed — no sparklines) ─────────────────────────────────

function IndexPill({ label, value, changePct, isVix }: {
  label: string; value: number; changePct: number; isVix?: boolean;
}) {
  const up = changePct >= 0;
  // VIX rising = fear increasing = bad → invert sentiment colors
  const color = isVix
    ? (up ? "var(--red)" : "var(--green)")
    : (up ? "var(--green)" : "var(--red)");
  return (
    <div
      style={{
        fontSize: 10,
        color: "var(--text-dim)",
        padding: "4px 8px",
        background: "rgba(148,163,184,0.04)",
        borderRadius: 6,
        display: "flex",
        alignItems: "baseline",
        gap: "6px",
      }}
    >
      <span
        style={{
          fontSize: "9px",
          textTransform: "uppercase" as const,
          letterSpacing: "0.08em",
          // VIX label in amber — signals it's a fear gauge not a price index
          color: isVix ? "var(--amber)" : "var(--text-dim)",
          fontFamily: "var(--font-sans)",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: "12px",
          // VIX value also in amber (subdued) to reinforce it's a different register
          color: isVix ? "rgba(245,158,11,0.65)" : "var(--text-secondary)",
          letterSpacing: "-0.01em",
          fontFamily: "var(--font-mono)",
        }}
      >
        {value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
      <span
        style={{ fontSize: "10px", color, fontFamily: "var(--font-mono)", fontWeight: 600 }}
      >
        {up ? "+" : ""}{changePct.toFixed(2)}%
      </span>
    </div>
  );
}

function MarketIndices() {
  const { data, isError } = useMarketIndices();
  const items = [
    { key: "sp500" as const,       label: "S&P",  isVix: false },
    { key: "russell2000" as const, label: "RUT",  isVix: false },
    { key: "vix" as const,         label: "VIX",  isVix: true  },
  ];
  return (
    <div className="flex items-center gap-1">
      {items.map(({ key, label, isVix }, i) => {
        const d = data?.[key];
        return (
          <div key={key} className="flex items-center">
            {i > 0 && <VDivider />}
            {!d || isError ? (
              <div
                style={{
                  fontSize: 10,
                  color: "var(--text-dim)",
                  padding: "4px 8px",
                  background: "rgba(148,163,184,0.04)",
                  borderRadius: 6,
                  display: "flex",
                  alignItems: "baseline",
                  gap: "6px",
                }}
              >
                <span style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: "0.08em", color: isVix ? "var(--amber)" : "var(--text-dim)", fontFamily: "var(--font-sans)" }}>{label}</span>
                <span style={{ fontSize: "12px", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>—</span>
              </div>
            ) : (
              <IndexPill label={label} value={d.value} changePct={d.change_pct} isVix={isVix} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Portfolio equity + day P&L (inline in TopBar) ─────────────────────────────

function PortfolioStats({ state }: { state: PortfolioState | undefined }) {
  if (!state) return null;
  const equity = state.total_equity ?? 0;
  const dayPnl = state.day_pnl ?? 0;
  const dayColor = dayPnl >= 0 ? "var(--green)" : "var(--red)";
  const sign = dayPnl >= 0 ? "+" : "";

  return (
    <div className="flex items-baseline gap-2 px-3 shrink-0">
      <span
        style={{ fontSize: "14px", color: "var(--text-primary)", letterSpacing: "-0.02em", fontFamily: "var(--font-mono)", fontWeight: 500 }}
      >
        ${equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      </span>
      <span
        style={{ fontSize: "11px", color: dayColor, fontFamily: "var(--font-mono)", fontWeight: 600 }}
      >
        {sign}${Math.abs(dayPnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
      </span>
    </div>
  );
}

// ── Emergency close ────────────────────────────────────────────────────────────

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

  return (
    <>
      <button
        onClick={() => setShowConfirm(true)}
        disabled={closing}
        className="inline-flex items-center justify-center rounded transition-all disabled:opacity-50"
        style={{
          height: "30px",
          padding: "0 12px",
          borderRadius: 6,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.06em",
          border: "1px solid",
          borderColor: "rgba(239,68,68,0.2)",
          background: "var(--red-dim)",
          color: "rgba(239,68,68,0.6)",
          cursor: "pointer",
          transition: "all 150ms ease",
          fontFamily: "var(--font-mono)",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(239,68,68,0.4)";
          (e.currentTarget as HTMLButtonElement).style.color = "var(--red)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(239,68,68,0.2)";
          (e.currentTarget as HTMLButtonElement).style.color = "rgba(239,68,68,0.6)";
        }}
      >
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
    </>
  );
}

// ── Mode toggle ────────────────────────────────────────────────────────────────

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
        className="inline-flex items-center gap-1.5 px-2.5 rounded-full transition-all disabled:opacity-40 cursor-pointer"
        style={{
          height: "22px",
          fontSize: "9px",
          fontWeight: 700,
          letterSpacing: "0.08em",
          fontFamily: "var(--font-mono)",
          background: paperMode ? "rgba(255,255,255,0.03)" : "var(--green-dim)",
          border: paperMode ? "1px solid var(--border)" : "1px solid rgba(34,197,94,0.30)",
          color: paperMode ? "var(--text-secondary)" : "var(--green)",
        }}
      >
        {!paperMode && (
          <span
            style={{
              width: "5px",
              height: "5px",
              borderRadius: "50%",
              background: "var(--green)",
              flexShrink: 0,
              boxShadow: "0 0 5px var(--green)",
            }}
            className="animate-pulse"
          />
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
              <button
                onClick={() => setShowConfirm(false)}
                className="px-3 py-1 text-xs font-semibold bg-bg-surface text-text-primary rounded hover:bg-border transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleToggle}
                className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${targetMode === "LIVE" ? "bg-loss/15 text-loss hover:bg-loss/25" : "bg-warning/15 text-warning hover:bg-warning/25"}`}
              >
                Switch to {targetMode}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── Logs button ────────────────────────────────────────────────────────────────

function LogsButton() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const isActive = portfolioId === "logs";

  return (
    <button
      onClick={() => setPortfolio(isActive ? "overview" : "logs")}
      className="inline-flex items-center justify-center rounded transition-all"
      style={{
        height: "30px",
        padding: "0 12px",
        borderRadius: 6,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: "0.06em",
        fontFamily: "var(--font-mono)",
        border: isActive
          ? "1px solid rgba(139,92,246,0.25)"
          : "1px solid var(--border)",
        background: isActive ? "var(--accent-dim)" : "rgba(148,163,184,0.04)",
        color: isActive ? "var(--accent)" : "var(--text-secondary)",
        cursor: "pointer",
        transition: "all 150ms ease",
      }}
      onMouseEnter={(e) => {
        if (!isActive) {
          (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border-hover)";
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-primary)";
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)";
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
        }
      }}
    >
      LOGS
    </button>
  );
}

// ── Buy button ─────────────────────────────────────────────────────────────────

function BuyButton() {
  const [showModal, setShowModal] = useState(false);
  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className="inline-flex items-center justify-center"
        style={{
          height: "30px",
          padding: "0 12px",
          borderRadius: 6,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.06em",
          border: "1px solid rgba(34,197,94,0.25)",
          background: "var(--green-dim)",
          color: "var(--green)",
          cursor: "pointer",
          transition: "all 150ms ease",
          fontFamily: "var(--font-mono)",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(34,197,94,0.5)";
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(34,197,94,0.14)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(34,197,94,0.25)";
          (e.currentTarget as HTMLButtonElement).style.background = "var(--green-dim)";
        }}
      >
        + BUY
      </button>
      {showModal && <BuyModal onClose={() => setShowModal(false)} />}
    </>
  );
}

// ── Main TopBar ────────────────────────────────────────────────────────────────

export default function TopBar({
  state,
  isLoading,
}: {
  state: PortfolioState | undefined;
  isLoading: boolean;
}) {
  const [showSettings, setShowSettings] = useState(false);
  const [logoAnimKey, setLogoAnimKey]   = useState(0);
  const briefOpen = useBriefStore(s => s.briefOpen);
  const briefInitialTab = useBriefStore(s => s.briefInitialTab);
  const briefInitialTradeId = useBriefStore(s => s.briefInitialTradeId);
  const openBrief = useBriefStore(s => s.openBrief);
  const closeBrief = useBriefStore(s => s.closeBrief);
  const isOverviewOrLogs = !state;
  const activePortfolioId = usePortfolioStore((s) => s.activePortfolioId);

  const theme = useUIStore((s) => s.theme);
  const toggleTheme = useUIStore((s) => s.toggleTheme);

  const actionButtons = (
    <>
      {(state?.stale_alerts.length ?? 0) > 0 && (
        <span style={{ fontSize: "9px", color: "var(--amber)", letterSpacing: "0.04em", fontWeight: 600, fontFamily: "var(--font-mono)" }}>
          ⚠ {state!.stale_alerts.length}
        </span>
      )}
      {(state?.price_failures.length ?? 0) > 0 && (
        <span style={{ fontSize: "9px", color: "var(--red)", letterSpacing: "0.04em", fontFamily: "var(--font-mono)" }}>
          {state!.price_failures.length} failed
        </span>
      )}
      {isLoading && (
        <span className="animate-pulse-slow" style={{ fontSize: "9px", color: "var(--text-muted)", fontFamily: "var(--font-sans)" }}>
          syncing
        </span>
      )}
      {!isOverviewOrLogs && (
        <>
          <UpdateButton />
          <ScanButton />
          <BuyButton />
          <div style={{ width: "1px", height: "18px", background: "var(--border)", flexShrink: 0 }} />
          <AnalyzeExecute />
          <div style={{ width: "1px", height: "18px", background: "var(--border)", flexShrink: 0 }} />
        </>
      )}
      <LogsButton />
      {state && <EmergencyClose positions={state.positions} />}
      {state && <ModeToggle paperMode={state.paper_mode} />}
      <button
        onClick={toggleTheme}
        title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        className="inline-flex items-center justify-center rounded transition-all"
        style={{
          width: "30px", height: "30px",
          borderRadius: 6,
          fontSize: "12px",
          border: "1px solid var(--border)",
          background: "rgba(148,163,184,0.04)",
          color: "var(--text-secondary)",
          cursor: "pointer",
          transition: "all 150ms ease",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.borderColor = "var(--border-hover)";
          (e.currentTarget as HTMLElement).style.color = "var(--text-primary)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
          (e.currentTarget as HTMLElement).style.color = "var(--text-secondary)";
        }}
      >
        {theme === "dark" ? "☀" : "☾"}
      </button>
    </>
  );

  return (
    <header
      className="shrink-0 topbar-root"
      style={{
        background: "var(--bg-surface)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      {/* Row 1: Logo + switcher + (desktop: stats + indices + buttons) */}
      <div className="flex items-center overflow-visible" style={{ height: "48px" }}>
        <button
          onClick={() => {
            usePortfolioStore.getState().setPortfolio("overview");
            setLogoAnimKey(k => k + 1);
          }}
          className="flex items-center justify-center hover:opacity-70 transition-opacity shrink-0"
          style={{ height: "48px", padding: "0 16px 0 14px", cursor: "pointer" }}
        >
          <GScottLogo height={34} animKey={logoAnimKey} />
        </button>

        <VDivider />

        <div className="flex items-center gap-2 shrink-0 px-3">
          <PortfolioSwitcher />
          {/* Intelligence Brief button — shown for any non-overview portfolio */}
          {!isOverviewOrLogs && (
            <button
              onClick={() => openBrief()}
              title="Portfolio Intelligence Brief"
              style={{
                background: "rgba(148,163,184,0.04)",
                border: "1px solid rgba(139,92,246,0.15)",
                borderRadius: "6px",
                color: "var(--text-muted)",
                cursor: "pointer",
                width: "30px", height: "30px",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "11px", lineHeight: 1, transition: "all 150ms ease",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.color = "var(--accent)";
                (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.color = "var(--text-muted)";
                (e.currentTarget as HTMLElement).style.borderColor = "rgba(139,92,246,0.15)";
              }}
            >
              ◈
            </button>
          )}
          {state?.ai_driven && (
            <button
              onClick={() => setShowSettings(true)}
              title="Strategy DNA"
              style={{
                background: "rgba(148,163,184,0.04)",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                color: "var(--text-muted)",
                cursor: "pointer",
                width: "30px", height: "30px",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "11px", lineHeight: 1, transition: "all 150ms ease",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.color = "var(--accent)";
                (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.color = "var(--text-muted)";
                (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
              }}
            >
              ⚙
            </button>
          )}
        </div>

        {/* Desktop only: equity stats + market indices + buttons */}
        {state && (
          <div className="hidden-mobile flex items-center">
            <VDivider />
            <PortfolioStats state={state} />
            <div className="shrink-0 px-2"><FreshnessIndicator /></div>
          </div>
        )}

        <div className="hidden-mobile flex-1 flex justify-center items-center min-w-0 overflow-hidden">
          <VDivider />
          <MarketIndices />
        </div>

        <div className="hidden-mobile flex items-center gap-2 shrink-0 px-3">
          <VDivider />
          {actionButtons}
        </div>
      </div>

      {/* Row 2: mobile-only action button strip */}
      <div
        className="show-mobile flex items-center gap-2 px-3"
        style={{
          height: "36px",
          overflowX: "auto",
          scrollbarWidth: "none",
          borderTop: "1px solid var(--border)",
          whiteSpace: "nowrap",
        } as React.CSSProperties}
      >
        {actionButtons}
      </div>

      {showSettings && state?.ai_driven && (
        <PortfolioSettingsModal onClose={() => setShowSettings(false)} />
      )}
      {briefOpen && activePortfolioId && !isOverviewOrLogs && (
        <IntelligenceBrief
          portfolioId={activePortfolioId}
          portfolioName={state?.config?.name as string ?? activePortfolioId}
          initialTab={briefInitialTab}
          initialTradeId={briefInitialTradeId}
          onClose={closeBrief}
        />
      )}
    </header>
  );
}
