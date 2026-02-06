/** Right panel — context tabs (Actions, Risk, Performance). */

import { useState } from "react";
import ActionsTab from "./ActionsTab";
import RiskTab from "./RiskTab";
import PerformanceTab from "./PerformanceTab";

type Tab = "actions" | "risk" | "performance";

function TabButton({
  tab,
  active,
  onClick,
}: {
  tab: Tab;
  active: boolean;
  onClick: () => void;
}) {
  const labels: Record<Tab, string> = {
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
  const [activeTab, setActiveTab] = useState<Tab>("actions");

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex items-center gap-1 px-3 pt-1 border-b border-border">
        {(["actions", "risk", "performance"] as Tab[]).map((tab) => (
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
