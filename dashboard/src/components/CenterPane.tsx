/** Center panel — equity curve (default) or candlestick chart (position selected). */

import { useUIStore } from "../lib/store";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { EquityCurve } from "./PortfolioSummary";
import { PositionDetailChart } from "./PositionDetail";

export default function CenterPane() {
  const selectedPosition = useUIStore((s) => s.selectedPosition);
  const { data: state } = usePortfolioState();

  if (selectedPosition) {
    return (
      <div className="flex flex-col h-full overflow-hidden">
        <PositionDetailChart pos={selectedPosition} />
      </div>
    );
  }

  // Default: large equity curve
  const hasSnapshots = (state?.snapshots.length ?? 0) >= 2;

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: "var(--bg-primary)" }}>
      {hasSnapshots ? (
        <div className="flex-1 relative overflow-hidden">
          {/* Label overlay */}
          <div
            className="absolute top-3 left-4 z-10 pointer-events-none"
            style={{
              fontSize: "9.5px",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--text-0)",
              fontFamily: "var(--font-sans, sans-serif)",
            }}
          >
            30-Day Equity
          </div>
          <EquityCurve snapshots={state!.snapshots} />
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <span className="text-sm" style={{ color: "var(--text-0)" }}>
            No snapshot data yet
          </span>
        </div>
      )}
    </div>
  );
}
