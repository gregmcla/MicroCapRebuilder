/** Context-sensitive focus pane — right rail content. */

import { useUIStore } from "../lib/store";
import type { RightTab } from "../lib/store";
import ActionsTab from "./ActionsTab";
import RiskTab from "./RiskTab";
import PerformanceTab from "./PerformanceTab";
import ReportTab from "./ReportTab";

interface FocusPaneProps {
  className?: string;
}

const TABS: { tab: RightTab; label: string }[] = [
  { tab: "actions", label: "Actions" },
  { tab: "risk", label: "Risk" },
  { tab: "performance", label: "Performance" },
  { tab: "report", label: "Report" },
];

function TabBar() {
  const rightTab = useUIStore((s) => s.rightTab);
  const setRightTab = useUIStore((s) => s.setRightTab);

  return (
    <div
      className="flex items-center shrink-0 border-b"
      style={{ borderColor: "var(--border-0)" }}
    >
      {TABS.map(({ tab, label }) => {
        const active = rightTab === tab;
        return (
          <button
            key={tab}
            onClick={() => setRightTab(tab)}
            className="px-4 py-2.5 text-xs font-medium transition-colors relative"
            style={{
              color: active ? "var(--accent-bright)" : "var(--text-1)",
              background: "none",
              border: "none",
              cursor: "pointer",
            }}
          >
            {label}
            {active && (
              <span
                className="absolute bottom-0 left-0 right-0 h-[2px]"
                style={{ background: "var(--accent)" }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

export default function FocusPane({ className = "" }: FocusPaneProps) {
  const rightTab = useUIStore((s) => s.rightTab);

  return (
    <div className={`flex flex-col h-full ${className}`}>
      <TabBar />
      <div className="flex-1 overflow-y-auto">
        {rightTab === "actions" && <ActionsTab />}
        {rightTab === "risk" && <RiskTab />}
        {rightTab === "performance" && <PerformanceTab />}
        {rightTab === "report" && <ReportTab />}
      </div>
    </div>
  );
}
