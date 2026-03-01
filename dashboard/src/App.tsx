/** 3-column layout: positions list | center chart | right analytics. */

import { usePortfolioState } from "./hooks/usePortfolioState";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { usePortfolioStore, useUIStore } from "./lib/store";
import TopBar from "./components/TopBar";
import PositionsPanel from "./components/PositionsPanel";
import FocusPane from "./components/FocusPane";
import CenterPane from "./components/CenterPane";
import ActivityFeed from "./components/ActivityFeed";
import GScottCoPilot, { GScottStrip } from "./components/GScottCoPilot";
import OverviewPage from "./components/OverviewPage";
import PortfolioSummary from "./components/PortfolioSummary";

export default function App() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const isOverview = portfolioId === "overview";
  const { data: state, isLoading } = usePortfolioState();
  const gscottExpanded = useUIStore((s) => s.gscottExpanded);
  const activityOpen = useUIStore((s) => s.activityOpen);
  const toggleActivity = useUIStore((s) => s.toggleActivity);
  useKeyboardShortcuts();

  return (
    <div className="h-screen flex flex-col bg-bg-primary overflow-hidden">
      <TopBar state={isOverview ? undefined : state} isLoading={isOverview ? false : isLoading} />

      {/* Body row */}
      <div className="flex-1 flex overflow-hidden">
        {isOverview ? (
          <main className="flex-1 flex flex-col overflow-hidden min-w-0">
            <OverviewPage />
          </main>
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden min-w-0">
            {/* Portfolio summary — full width above three columns */}
            <PortfolioSummary />

            {/* Three columns */}
            <div className="flex-1 flex overflow-hidden">
              {/* Left: positions list — 320px */}
              <aside
                className="flex-shrink-0 flex flex-col overflow-hidden border-r bg-bg-surface"
                style={{ width: "320px", borderColor: "var(--border-0)" }}
              >
                <PositionsPanel
                  positions={state?.positions ?? []}
                  isLoading={isLoading}
                />
              </aside>

              {/* Center: chart panel — flex-1 */}
              <main className="flex-1 flex flex-col overflow-hidden min-w-0 bg-bg-surface">
                <CenterPane />
              </main>

              {/* Right: analytics panel — 300px */}
              <aside
                className="flex-shrink-0 flex flex-col overflow-hidden border-l bg-bg-surface"
                style={{ width: "300px", borderColor: "var(--border-0)" }}
              >
                {gscottExpanded ? (
                  <GScottCoPilot />
                ) : (
                  <FocusPane className="flex-1" />
                )}
                <GScottStrip />
              </aside>
            </div>
          </div>
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
