/** 3-column layout: positions list | center chart | right analytics. */

import { Component, useEffect, useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePortfolioState } from "./hooks/usePortfolioState";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { usePortfolioStore, useUIStore } from "./lib/store";
import { api } from "./lib/api";
import TopBar from "./components/TopBar";
import ActivityFeed from "./components/ActivityFeed";
import OverviewPage from "./components/OverviewPage";
import LogsPage from "./components/LogsPage";
import HealthStrip from "./components/HealthStrip";
import PositionsPanel from "./components/PositionsPanel";
import FocusPane from "./components/FocusPane";
import MatrixGrid from "./components/MatrixGrid";
import { buildPortfolioMap, positionToMatrix } from "./components/MatrixGrid/constants";
import type { MatrixPortfolio } from "./components/MatrixGrid/types";
import { useOverview } from "./hooks/usePortfolios";

// ---------------------------------------------------------------------------
// Error boundary — catches render crashes and shows a recovery UI instead of
// going blank. Required because React unmounts everything on an unhandled throw.
// ---------------------------------------------------------------------------
interface EBState { error: Error | null }
class ErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  state: EBState = { error: null };
  static getDerivedStateFromError(error: Error): EBState { return { error }; }
  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error("[ErrorBoundary] render crash:", error, info.componentStack);
  }
  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div
        style={{
          flex: 1, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          background: "var(--bg-surface)", padding: "40px",
        }}
      >
        <p style={{ fontSize: "13px", fontWeight: 600, color: "var(--red)", marginBottom: "8px" }}>
          Render error
        </p>
        <p style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "16px", maxWidth: "480px", textAlign: "center" }}>
          {error.message}
        </p>
        <button
          onClick={() => this.setState({ error: null })}
          style={{
            fontSize: "11px", padding: "6px 16px", borderRadius: "6px",
            background: "var(--accent-dim)", border: "1px solid var(--accent)",
            color: "var(--accent)", cursor: "pointer",
          }}
        >
          Try again
        </button>
      </div>
    );
  }
}

export default function App() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const isOverview = portfolioId === "overview";
  const isLogs = portfolioId === "logs";
  const { data: state, isLoading } = usePortfolioState();
  const activityOpen = useUIStore((s) => s.activityOpen);
  const toggleActivity = useUIStore((s) => s.toggleActivity);
  const theme = useUIStore((s) => s.theme);
  useKeyboardShortcuts();

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const { data: overview } = useOverview();

  const activeMatrixPortfolio = useMemo<MatrixPortfolio | null>(() => {
    if (isOverview || isLogs || !portfolioId) return null;
    const summaries = overview?.portfolios ?? [];
    const ids = summaries.length > 0
      ? summaries.map((s) => ({ id: s.id, name: s.name }))
      : [{ id: portfolioId, name: portfolioId }];
    const map = buildPortfolioMap(ids);
    const base = map.get(portfolioId) ?? null;
    if (!base) return null;
    const equityCurve = state?.snapshots?.map((s) => s.day_pnl_pct) ?? [];
    return equityCurve.length >= 3 ? { ...base, equityCurve } : base;
  }, [isOverview, portfolioId, overview, state?.snapshots]);

  const matrixPositions = useMemo(() => {
    if (!activeMatrixPortfolio || !state?.positions) return [];
    return state.positions.map((pos) => positionToMatrix(pos, activeMatrixPortfolio));
  }, [state?.positions, activeMatrixPortfolio]);

  const { data: watchlistData } = useQuery({
    queryKey: ["watchlist", portfolioId],
    queryFn: () => api.getWatchlist(portfolioId!),
    enabled: !isOverview && !isLogs && !!portfolioId,
    staleTime: 60_000,
  });

  const { data: scanStatus } = useQuery({
    queryKey: ["scanStatus", portfolioId],
    queryFn: () => api.scanStatus(portfolioId!),
    enabled: !isOverview && !isLogs && !!portfolioId,
    refetchInterval: 5000,
  });

  return (
    <div className="h-screen flex flex-col bg-bg-primary overflow-hidden">
      <TopBar state={isOverview || isLogs ? undefined : state} isLoading={isOverview || isLogs ? false : isLoading} />

      {/* Body row */}
      <div className="flex-1 flex overflow-hidden">
        <ErrorBoundary>
        {isLogs ? (
          <main className="flex-1 flex flex-col overflow-hidden min-w-0">
            <LogsPage />
          </main>
        ) : isOverview ? (
          <main className="flex-1 flex flex-col overflow-hidden min-w-0">
            <OverviewPage />
          </main>
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden min-w-0">
            {/* Health strip — position glyphs + health score + clock */}
            <HealthStrip />

            {/* 3-column workspace: positions | center | focus pane */}
            <div style={{ flex: 1, display: "flex", minHeight: 0, overflow: "hidden" }}>

              {/* LEFT: positions list (270px fixed) */}
              <div style={{
                width: 270, flexShrink: 0,
                borderRight: "1px solid var(--border)",
                display: "flex", flexDirection: "column",
                background: "rgba(15,23,42,0.3)",
                overflow: "hidden",
              }}>
                <PositionsPanel
                  positions={state?.positions ?? []}
                  isLoading={isLoading}
                />
              </div>

              {/* CENTER: MatrixGrid (grid/detail/watchlist/activity/history tabs) */}
              <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
                <MatrixGrid
                  key={portfolioId}
                  positions={matrixPositions}
                  portfolios={activeMatrixPortfolio ? [activeMatrixPortfolio] : []}
                  initialFilter={portfolioId ?? undefined}
                  transactions={state?.transactions ?? []}
                  watchlistCandidates={watchlistData?.candidates ?? []}
                  scanStatus={scanStatus}
                  positionRationales={state?.position_rationales ?? {}}
                  snapshots={state?.snapshots ?? []}
                  startingCapital={state?.starting_capital}
                />
              </div>

              {/* RIGHT: Focus pane (310px fixed) */}
              <div style={{
                width: 310, flexShrink: 0,
                borderLeft: "1px solid var(--border)",
                display: "flex", flexDirection: "column",
                background: "rgba(15,23,42,0.3)",
                overflow: "hidden",
              }}>
                <FocusPane />
              </div>

            </div>
          </div>
        )}
        </ErrorBoundary>
      </div>

      {/* Activity feed slide-over */}
      {activityOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/40 z-40"
            onClick={toggleActivity}
          />
          <div className="fixed top-0 left-0 h-full w-72 bg-bg-surface border-r border-border z-50 overflow-y-auto">
            <ActivityFeed transactions={state?.transactions ?? []} />
          </div>
        </>
      )}
    </div>
  );
}
