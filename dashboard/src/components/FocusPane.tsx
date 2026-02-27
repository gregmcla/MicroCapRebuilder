/** Context-sensitive focus pane — replaces tab-based RightPanel. */

import { useUIStore, useAnalysisStore } from "../lib/store";
import ActionsTab from "./ActionsTab";
import RiskTab from "./RiskTab";
import PerformanceTab from "./PerformanceTab";
import { PositionDetailChart } from "./PositionDetail";
import PortfolioSummary from "./PortfolioSummary";

interface FocusPaneProps {
  className?: string;
}

export default function FocusPane({ className = "" }: FocusPaneProps) {
  const selectedPosition = useUIStore((s) => s.selectedPosition);
  const rightTab = useUIStore((s) => s.rightTab);
  const setRightTab = useUIStore((s) => s.setRightTab);
  const { result, isAnalyzing } = useAnalysisStore();

  if (selectedPosition) {
    return (
      <div className={`overflow-y-auto ${className}`}>
        <PositionDetailChart pos={selectedPosition} />
      </div>
    );
  }

  if (isAnalyzing || result) {
    return (
      <div className={`overflow-y-auto ${className}`}>
        <ActionsTab />
      </div>
    );
  }

  if (rightTab === "risk") {
    return (
      <div className={`overflow-y-auto ${className}`}>
        <div className="flex items-center gap-2 px-4 pt-3 pb-1">
          <button
            onClick={() => setRightTab("summary")}
            className="text-[10px] text-text-muted hover:text-text-secondary uppercase tracking-wider transition-colors"
          >
            ← Summary
          </button>
          <span className="text-[10px] text-text-muted uppercase tracking-wider">/ Risk</span>
        </div>
        <RiskTab />
      </div>
    );
  }

  if (rightTab === "performance") {
    return (
      <div className={`overflow-y-auto ${className}`}>
        <div className="flex items-center gap-2 px-4 pt-3 pb-1">
          <button
            onClick={() => setRightTab("summary")}
            className="text-[10px] text-text-muted hover:text-text-secondary uppercase tracking-wider transition-colors"
          >
            ← Summary
          </button>
          <span className="text-[10px] text-text-muted uppercase tracking-wider">/ Performance</span>
        </div>
        <PerformanceTab />
      </div>
    );
  }

  return (
    <div className={`overflow-y-auto ${className}`}>
      <PortfolioSummary />
    </div>
  );
}
