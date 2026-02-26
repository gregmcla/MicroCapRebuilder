/** Signal layout — 55/45 fixed split, context-sensitive focus pane. */

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

      {isOverview ? (
        <OverviewPage />
      ) : (
        <div className="flex flex-1 overflow-hidden relative">
          {/* Left: positions, fixed 55% */}
          <div className="w-[55%] border-r border-border bg-bg-surface overflow-hidden flex flex-col">
            <PositionsPanel
              positions={state?.positions ?? []}
              isLoading={isLoading}
            />
          </div>

          {/* Right: focus pane + mommy strip, remaining 45% */}
          <div className="flex-1 flex flex-col bg-bg-surface overflow-hidden">
            {mommyExpanded ? (
              <MommyCoPilot />
            ) : (
              <FocusPane className="flex-1 overflow-y-auto" />
            )}
            <MommyStrip />
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
      )}
    </div>
  );
}
