/** Context-sensitive focus pane — right rail content. */

import { useUIStore } from "../lib/store";
import type { RightTab } from "../lib/store";
import ActionsTab from "./ActionsTab";
import RiskTab from "./RiskTab";
import PerformanceTab from "./PerformanceTab";
import ReportTab from "./ReportTab";
import { Tabs, type TabItem } from "./ui";

interface FocusPaneProps {
  className?: string;
}

const TABS: ReadonlyArray<TabItem<RightTab>> = [
  { key: "actions", label: "Actions" },
  { key: "risk", label: "Risk" },
  { key: "performance", label: "Performance" },
  { key: "report", label: "Report" },
];

export default function FocusPane({ className = "" }: FocusPaneProps) {
  const rightTab = useUIStore((s) => s.rightTab);
  const setRightTab = useUIStore((s) => s.setRightTab);

  return (
    <div className={`flex flex-col h-full ${className}`}>
      <Tabs items={TABS} value={rightTab} onChange={setRightTab} />
      <div className="flex-1 overflow-y-auto">
        {rightTab === "actions" && <ActionsTab />}
        {rightTab === "risk" && <RiskTab />}
        {rightTab === "performance" && <PerformanceTab />}
        {rightTab === "report" && <ReportTab />}
      </div>
    </div>
  );
}
