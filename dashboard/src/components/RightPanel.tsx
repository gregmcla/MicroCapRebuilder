/** Right panel — context tabs, or position detail when a position is selected. */

import ActionsTab from "./ActionsTab";
import RiskTab from "./RiskTab";
import PerformanceTab from "./PerformanceTab";
import PositionDetail from "./PositionDetail";
import { useUIStore, type RightTab } from "../lib/store";

function TabButton({
  tab,
  active,
  onClick,
}: {
  tab: RightTab;
  active: boolean;
  onClick: () => void;
}) {
  const labels: Record<RightTab, string> = {
    actions: "Actions",
    risk: "Risk",
    performance: "Performance",
  };
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-medium transition-colors rounded-t ${
        active
          ? "text-accent border-b-2 border-accent bg-bg-surface"
          : "text-text-muted hover:text-text-secondary"
      }`}
    >
      {labels[tab]}
    </button>
  );
}

export default function RightPanel() {
  const activeTab = useUIStore((s) => s.rightTab);
  const setActiveTab = useUIStore((s) => s.setRightTab);
  const selectedPosition = useUIStore((s) => s.selectedPosition);

  // Position detail view takes over the right panel
  if (selectedPosition) {
    return <PositionDetail pos={selectedPosition} />;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex items-center gap-1 px-3 pt-1 border-b border-border">
        {(["actions", "risk", "performance"] as RightTab[]).map((tab) => (
          <TabButton
            key={tab}
            tab={tab}
            active={activeTab === tab}
            onClick={() => setActiveTab(tab)}
          />
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === "actions" && <ActionsTab />}
        {activeTab === "risk" && <RiskTab />}
        {activeTab === "performance" && <PerformanceTab />}
      </div>
    </div>
  );
}
