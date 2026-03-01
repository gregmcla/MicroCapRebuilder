/** 2-column layout: main | right-rail. */

import { usePortfolioState } from "./hooks/usePortfolioState";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { usePortfolioStore, useUIStore } from "./lib/store";
import MarketTickerBanner from "./components/MarketTickerBanner";
import TopBar from "./components/TopBar";
import PositionsPanel from "./components/PositionsPanel";
import FocusPane from "./components/FocusPane";
import ActivityFeed from "./components/ActivityFeed";
import MommyCoPilot, { MommyStrip } from "./components/MommyCoPilot";
import OverviewPage from "./components/OverviewPage";
import PortfolioSummary from "./components/PortfolioSummary";

export default function App() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const isOverview = portfolioId === "overview";
  const { data: state, isLoading } = usePortfolioState();
  const mommyExpanded = useUIStore((s) => s.mommyExpanded);
  const activityOpen = useUIStore((s) => s.activityOpen);
  const toggleActivity = useUIStore((s) => s.toggleActivity);
  useKeyboardShortcuts();

  return (
    <div className="h-screen flex flex-col bg-bg-primary overflow-hidden">
      <MarketTickerBanner />
      <TopBar state={isOverview ? undefined : state} isLoading={isOverview ? false : isLoading} />

      {/* Deployment bar — thin fill showing % deployed */}
      {!isOverview && state && (
        <div className="h-0.5 bg-bg-elevated shrink-0">
          <div
            className="h-full bg-accent/30 transition-all duration-500"
            style={{
              width: `${Math.min(100, Math.round((state.positions_value / (state.total_equity || 1)) * 100))}%`,
            }}
          />
        </div>
      )}

      {/* Body row */}
      <div className="flex-1 flex overflow-hidden">
        {/* Main content */}
        {isOverview ? (
          <main className="flex-1 flex flex-col overflow-hidden min-w-0">
            <OverviewPage />
          </main>
        ) : (
          <>
            {/* Center column: portfolio summary + positions + position detail */}
            <main className="flex-1 flex flex-col overflow-hidden min-w-0 border-r border-[var(--border-0)] bg-bg-surface">
              {/* Portfolio summary header */}
              <PortfolioSummary />
              {/* Positions */}
              <div className="flex-1 overflow-auto">
                <PositionsPanel
                  positions={state?.positions ?? []}
                  isLoading={isLoading}
                />
              </div>
            </main>

            {/* Right rail: 312px fixed */}
            <aside
              className="flex-shrink-0 flex flex-col overflow-hidden border-l border-border bg-bg-surface"
              style={{ width: "312px" }}
            >
              {mommyExpanded ? (
                <MommyCoPilot />
              ) : (
                <FocusPane className="flex-1 overflow-y-auto" />
              )}
              <MommyStrip />
            </aside>
          </>
        )}
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
