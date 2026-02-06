/** Cockpit layout — four resizable panels + top bar. */

import { Panel, Group, Separator } from "react-resizable-panels";
import { usePortfolioState } from "./hooks/usePortfolioState";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import TopBar from "./components/TopBar";
import PositionsPanel from "./components/PositionsPanel";
import RightPanel from "./components/RightPanel";
import ActivityFeed from "./components/ActivityFeed";
import MommyCoPilot from "./components/MommyCoPilot";

export default function App() {
  const { data: state, isLoading } = usePortfolioState();
  useKeyboardShortcuts();

  return (
    <div className="h-screen flex flex-col bg-bg-primary">
      <TopBar state={state} isLoading={isLoading} />

      <Group direction="horizontal" className="flex-1">
        {/* Left column */}
        <Panel defaultSize={35} minSize={25}>
          <Group direction="vertical">
            {/* Positions */}
            <Panel defaultSize={65} minSize={30}>
              <div className="h-full bg-bg-surface border-r border-border">
                <PositionsPanel
                  positions={state?.positions ?? []}
                  totalValue={state?.positions_value ?? 0}
                />
              </div>
            </Panel>

            <Separator />

            {/* Activity Feed */}
            <Panel defaultSize={35} minSize={15}>
              <div className="h-full bg-bg-surface border-r border-t border-border">
                <ActivityFeed transactions={state?.transactions ?? []} />
              </div>
            </Panel>
          </Group>
        </Panel>

        <Separator />

        {/* Right column */}
        <Panel defaultSize={65} minSize={35}>
          <Group direction="vertical">
            {/* Context Tabs */}
            <Panel defaultSize={65} minSize={30}>
              <div className="h-full bg-bg-surface">
                <RightPanel />
              </div>
            </Panel>

            <Separator />

            {/* Mommy Co-Pilot */}
            <Panel defaultSize={35} minSize={20}>
              <div className="h-full bg-bg-surface border-t border-border">
                <MommyCoPilot />
              </div>
            </Panel>
          </Group>
        </Panel>
      </Group>
    </div>
  );
}
