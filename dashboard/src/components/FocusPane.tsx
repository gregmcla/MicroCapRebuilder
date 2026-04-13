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
      className="flex items-center shrink-0"
      style={{
        borderBottom: "1px solid var(--border)",
        height: 38,
        padding: "0 8px",
      }}
    >
      {TABS.map(({ tab, label }) => {
        const active = rightTab === tab;
        return (
          <button
            key={tab}
            onClick={() => setRightTab(tab)}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 500,
              color: active ? "var(--text-primary)" : "var(--text-muted)",
              background: active ? "var(--accent-dim)" : "none",
              border: "none",
              cursor: "pointer",
              transition: "color 0.15s, background 0.15s",
            }}
          >
            {label}
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
