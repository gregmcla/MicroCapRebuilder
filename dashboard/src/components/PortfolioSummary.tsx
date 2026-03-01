/** Horizontal summary strip at the top of the main column. */

import { useMemo, useEffect, useRef } from "react";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { useRisk } from "../hooks/useRisk";
import { useCountUp } from "../hooks/useCountUp";
import type { Snapshot } from "../lib/types";

export function EquityCurve({ snapshots }: { snapshots: Snapshot[] }) {
  const W = 400;
  const H = 64;
  const PAD = 2;
  const polylineRef = useRef<SVGPolylineElement>(null);

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

  // Stroke-dashoffset mount animation — draw the line over 2s
  useEffect(() => {
    const el = polylineRef.current;
    if (!el || !points) return;
    const length = el.getTotalLength?.() ?? 0;
    if (length === 0) return;
    el.style.strokeDasharray = `${length}`;
    el.style.strokeDashoffset = `${length}`;
    // Force reflow so transition starts from the beginning
    void el.getBoundingClientRect();
    el.style.transition = "stroke-dashoffset 2s cubic-bezier(0.16, 1, 0.3, 1)";
    el.style.strokeDashoffset = "0";
    return () => {
      el.style.transition = "";
      el.style.strokeDasharray = "";
      el.style.strokeDashoffset = "";
    };
  }, [points]);

  if (!points) return null;

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ display: "block", height: "100%" }}>
      <defs>
        <linearGradient id="equity-fill" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="rgba(124,92,252,0.15)" stopOpacity="1" />
          <stop offset="100%" stopColor="rgba(124,92,252,0)" stopOpacity="1" />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${H} ${points} ${W},${H}`}
        fill="url(#equity-fill)"
      />
      <polyline
        ref={polylineRef}
        points={points}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export default function PortfolioSummary() {
  const { data: state } = usePortfolioState();
  const { data: risk } = useRisk();

  const overallPnl = state?.positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0) ?? 0;
  const overallColor = overallPnl >= 0 ? "text-profit" : "text-loss";
  const dayColor = (state?.day_pnl ?? 0) >= 0 ? "text-profit" : "text-loss";
  const returnColor = (state?.total_return_pct ?? 0) >= 0 ? "text-profit" : "text-loss";

  const animatedEquity = useCountUp(state?.total_equity ?? 0, 1200, 2);

  // Shared label style for metric labels
  const labelStyle: React.CSSProperties = {
    fontSize: "9.5px",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "var(--text-0)",
    fontFamily: "var(--font-sans)",
    marginTop: "2px",
  };

  return (
    <div
      className="flex-shrink-0 border-b"
      style={{ borderColor: "var(--border-0)", background: "var(--surface-0)" }}
    >
      <div className="flex items-stretch" style={{ minHeight: "84px" }}>

        {/* Left: metrics */}
        <div className="flex-1 flex items-center gap-6 px-4 py-3 min-w-0">

          {/* Hero equity */}
          <div className="shrink-0 anim d1">
            <div className="font-mono tabular-nums leading-none" style={{ fontSize: "22px", fontWeight: 300, color: "var(--text-4)" }}>
              ${animatedEquity}
            </div>
            <div style={labelStyle}>Portfolio Equity</div>
          </div>

          {/* Divider */}
          <div style={{ width: "1px", height: "28px", background: "var(--border-1)", flexShrink: 0 }} />

          {/* P&L metrics row */}
          <div className="flex items-center gap-5 flex-wrap anim d2">
            {/* Total P&L */}
            <div>
              <div className={`font-mono text-sm tabular-nums font-semibold ${overallColor}`}>
                {overallPnl >= 0 ? "+" : ""}${overallPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div style={labelStyle}>Total P&L</div>
            </div>
            {/* Today */}
            <div>
              <div className={`font-mono text-sm tabular-nums font-semibold ${dayColor}`}>
                {(state?.day_pnl ?? 0) >= 0 ? "+" : ""}${(state?.day_pnl ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div style={labelStyle}>Today</div>
            </div>
            {/* Return */}
            <div>
              <div className={`font-mono text-sm tabular-nums font-semibold ${returnColor}`}>
                {(state?.total_return_pct ?? 0) >= 0 ? "+" : ""}{(state?.total_return_pct ?? 0).toFixed(1)}%
              </div>
              <div style={labelStyle}>Return</div>
            </div>
            {/* Cash */}
            <div>
              <div className="font-mono text-sm tabular-nums text-text-primary">
                ${(state?.cash ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div style={labelStyle}>Cash</div>
            </div>
          </div>

          {/* Status chips */}
          <div className="flex items-center gap-2 ml-auto shrink-0 anim d3" style={{ fontSize: "10px" }}>
            <span className={state?.regime === "BULL" ? "text-profit" : state?.regime === "BEAR" ? "text-loss" : "text-warning"} style={{ fontWeight: 600 }}>
              {state?.regime ?? "—"}
            </span>
            <span style={{ color: "var(--border-2)" }}>·</span>
            <span style={{ color: "var(--text-1)" }}>
              Risk{" "}
              <span className={`font-mono font-semibold ${(risk?.overall_score ?? 0) >= 70 ? "text-profit" : (risk?.overall_score ?? 0) >= 40 ? "text-warning" : "text-loss"}`}>
                {risk?.overall_score != null ? Math.round(risk.overall_score) : "—"}
              </span>
            </span>
            <span style={{ color: "var(--border-2)" }}>·</span>
            <span style={{ color: "var(--text-1)" }}>
              <span className="font-mono text-text-primary">{state?.positions.length ?? 0}</span> pos
            </span>
            {(state?.stale_alerts.length ?? 0) > 0 && (
              <span className="text-warning">&#9888; {state!.stale_alerts.length}</span>
            )}
          </div>

        </div>

      </div>
    </div>
  );
}
