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

/** Breadcrumb nav row shared by sub-tabs (Risk, Performance). */
function BreadcrumbNav({ section }: { section: string }) {
  const setRightTab = useUIStore((s) => s.setRightTab);
  return (
    <div
      className="flex items-center gap-2 px-4 pt-3 pb-1"
      style={{ borderBottom: `1px solid var(--border-0)` }}
    >
      <button
        onClick={() => setRightTab("summary")}
        className="transition-colors"
        style={{
          fontSize: "9.5px",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--text-1)",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: "2px 0",
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--text-2)"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--text-1)"; }}
      >
        Summary
      </button>
      <span style={{ fontSize: "9.5px", color: "var(--text-0)" }}>/</span>
      <span
        style={{
          fontSize: "9.5px",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--accent-bright)",
          padding: "2px 5px",
          borderRadius: "3px",
          background: "rgba(124,92,252,0.06)",
        }}
      >
        {section}
      </span>
    </div>
  );
}

export default function FocusPane({ className = "" }: FocusPaneProps) {
  const selectedPosition = useUIStore((s) => s.selectedPosition);
  const rightTab = useUIStore((s) => s.rightTab);
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
        <BreadcrumbNav section="Risk" />
        <RiskTab />
      </div>
    );
  }

  if (rightTab === "performance") {
    return (
      <div className={`overflow-y-auto ${className}`}>
        <BreadcrumbNav section="Performance" />
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
