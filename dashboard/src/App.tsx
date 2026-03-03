/** 3-column layout: positions list | center chart | right analytics. */

import { Component, type ReactNode } from "react";
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
          background: "var(--surface-0)", padding: "40px",
        }}
      >
        <p style={{ fontSize: "13px", fontWeight: 600, color: "var(--red)", marginBottom: "8px" }}>
          Render error
        </p>
        <p style={{ fontSize: "11px", color: "var(--text-1)", marginBottom: "16px", maxWidth: "480px", textAlign: "center" }}>
          {error.message}
        </p>
        <button
          onClick={() => this.setState({ error: null })}
          style={{
            fontSize: "11px", padding: "6px 16px", borderRadius: "6px",
            background: "transparent", border: "1px solid var(--border-1)",
            color: "var(--text-2)", cursor: "pointer",
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
        <ErrorBoundary>
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
