/** Default focus pane state — portfolio hero metrics + nav. */

import { useMemo } from "react";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { useRisk } from "../hooks/useRisk";
import { useUIStore } from "../lib/store";
import type { Snapshot } from "../lib/types";

function EquityCurve({ snapshots }: { snapshots: Snapshot[] }) {
  const W = 400;
  const H = 64;
  const PAD = 2;

  const points = useMemo(() => {
    if (snapshots.length < 2) return null;
    // Last 30 days
    const recent = snapshots.slice(-30);
    const equities = recent.map((s) => s.total_equity ?? s.cash + s.positions_value);
    const min = Math.min(...equities);
    const max = Math.max(...equities);
    const range = max - min || 1;
    return recent.map((_, i) => {
      const x = (i / (recent.length - 1)) * W;
      const y = H - PAD - ((equities[i] - min) / range) * (H - PAD * 2);
      return `${x},${y}`;
    }).join(" ");
  }, [snapshots]);

  if (!points) return null;

  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="block">
      <defs>
        <linearGradient id="equity-fill" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#4ADE80" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#4ADE80" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${H} ${points} ${W},${H}`}
        fill="url(#equity-fill)"
      />
      <polyline
        points={points}
        fill="none"
        stroke="#4ADE80"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function NavLink({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-[10px] uppercase tracking-wider transition-colors pb-1 border-b ${
        active
          ? "text-text-primary font-semibold border-accent"
          : "text-text-muted hover:text-text-secondary border-transparent"
      }`}
    >
      {label}
    </button>
  );
}

export default function PortfolioSummary() {
  const { data: state } = usePortfolioState();
  const { data: risk } = useRisk();
  const rightTab = useUIStore((s) => s.rightTab);
  const setRightTab = useUIStore((s) => s.setRightTab);

  const overallPnl = state?.positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0) ?? 0;
  const overallColor = overallPnl >= 0 ? "text-profit" : "text-loss";
  const dayColor = (state?.day_pnl ?? 0) >= 0 ? "text-profit" : "text-loss";
  const returnColor = (state?.total_return_pct ?? 0) >= 0 ? "text-profit" : "text-loss";

  return (
    <div className="flex flex-col h-full p-4 gap-4">
      {/* Nav links */}
      <div className="flex items-center gap-4">
        <NavLink label="Summary" active={rightTab === "summary"} onClick={() => setRightTab("summary")} />
        <NavLink label="Risk" active={rightTab === "risk"} onClick={() => setRightTab("risk")} />
        <NavLink label="Performance" active={rightTab === "performance"} onClick={() => setRightTab("performance")} />
      </div>

      {/* Hero equity */}
      <div>
        <div className="font-mono text-[32px] font-semibold text-text-primary leading-none tabular-nums">
          ${(state?.total_equity ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </div>
        <div className="text-[10px] text-text-muted uppercase tracking-wider mt-1">
          Portfolio Equity
        </div>
      </div>

      {/* P&L row */}
      <div className="flex items-center gap-6">
        <div>
          <div className={`font-mono text-sm tabular-nums font-semibold ${overallColor}`}>
            {overallPnl >= 0 ? "+" : ""}${overallPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">Total P&L</div>
        </div>
        <div>
          <div className={`font-mono text-sm tabular-nums font-semibold ${dayColor}`}>
            {(state?.day_pnl ?? 0) >= 0 ? "+" : ""}${(state?.day_pnl ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">Today</div>
        </div>
        <div>
          <div className={`font-mono text-sm tabular-nums font-semibold ${returnColor}`}>
            {(state?.total_return_pct ?? 0) >= 0 ? "+" : ""}{(state?.total_return_pct ?? 0).toFixed(1)}%
          </div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">Return</div>
        </div>
        <div>
          <div className="font-mono text-sm tabular-nums text-text-primary">
            ${(state?.cash ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">Cash</div>
        </div>
      </div>

      {/* 30-day equity curve */}
      {(state?.snapshots.length ?? 0) >= 2 && (
        <div className="w-full overflow-hidden">
          <EquityCurve snapshots={state!.snapshots} />
        </div>
      )}

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Status row */}
      <div className="flex items-center gap-3 text-xs flex-wrap">
        <span className={`font-semibold ${
          state?.regime === "BULL" ? "text-profit"
          : state?.regime === "BEAR" ? "text-loss"
          : "text-warning"
        }`}>
          {state?.regime ?? "—"}
        </span>
        <span className="text-text-muted">·</span>
        <span className="text-text-secondary">
          Risk{" "}
          <span className={`font-mono font-semibold ${
            (risk?.overall_score ?? 0) >= 70 ? "text-profit"
            : (risk?.overall_score ?? 0) >= 40 ? "text-warning"
            : "text-loss"
          }`}>
            {risk?.overall_score != null ? Math.round(risk.overall_score) : "—"}
          </span>
        </span>
        <span className="text-text-muted">·</span>
        <span className="text-text-secondary">
          <span className="font-mono font-semibold text-text-primary">{state?.positions.length ?? 0}</span> positions
        </span>
        <span className="text-text-muted">·</span>
        <span className={state?.paper_mode ? "text-warning text-[10px] uppercase tracking-wider" : "text-loss text-[10px] uppercase tracking-wider font-bold"}>
          {state?.paper_mode ? "Paper" : "Live"}
        </span>
      </div>

      {/* Warnings if any */}
      {(state?.stale_alerts.length ?? 0) > 0 && (
        <div className="text-[11px] text-warning">
          {state!.stale_alerts.length} stale alert{state!.stale_alerts.length > 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}
