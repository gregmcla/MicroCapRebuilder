/** DNA Tab — stated vs measured genome overlay + drift summary.
 *
 * Killer feature: the radar overlay surfaces "your DNA says X, you're trading
 * like Y" mismatches at a glance.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { DNA_AXES, type DnaAxis } from "../../lib/types";
import DnaRadar from "./DnaRadar";

const FONT = "'JetBrains Mono', 'SF Mono', monospace";

const AXIS_LABELS: Record<DnaAxis, string> = {
  time_horizon: "Time horizon",
  aggression: "Aggression",
  concentration: "Concentration",
  regime_sensitivity: "Regime sense",
  momentum_bias: "Momentum",
  quality_bias: "Quality",
  catalyst_hunting: "Catalyst",
  drawdown_discipline: "Discipline",
};

export default function DnaTab({ portfolioId }: { portfolioId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["dna", portfolioId],
    queryFn: () => api.getDnaProfile(portfolioId, "all"),
    staleTime: 60_000,
  });

  if (isLoading || !data) {
    return <div style={{ color: "#5a5a78", padding: "20px", fontFamily: FONT }}>Loading DNA…</div>;
  }

  // Top 3 drift axes (largest absolute disagreements)
  const sortedAxes = [...DNA_AXES].sort(
    (a, b) => Math.abs(data.drift[b] ?? 0) - Math.abs(data.drift[a] ?? 0),
  );
  const topDrift = sortedAxes.slice(0, 3);

  return (
    <div style={{ display: "flex", flex: 1, overflow: "hidden", fontFamily: FONT }}>
      {/* LEFT: radar */}
      <div style={{ flex: 1, padding: "20px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ maxWidth: "560px", margin: "0 auto", width: "100%" }}>
          <DnaRadar
            stated={data.stated}
            measured={data.measured}
            drift={data.drift as Record<DnaAxis, number>}
            size={560}
          />
          <div style={{
            display: "flex",
            justifyContent: "center",
            gap: "24px",
            marginTop: "8px",
            fontSize: "10px",
            color: "#9090b0",
          }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "16px", height: "0", borderTop: "1.5px dashed #fbbf24" }} />
              Stated (config)
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "16px", height: "8px", background: "rgba(124,92,252,0.45)", borderTop: "2px solid #a78bfa" }} />
              Measured (last 90d+)
            </span>
          </div>
        </div>
      </div>

      {/* RIGHT: drift summary + per-axis table */}
      <div style={{
        width: "340px",
        borderLeft: "1px solid rgba(255,255,255,0.08)",
        padding: "20px",
        overflowY: "auto",
      }}>
        <div style={{ marginBottom: "16px" }}>
          <div style={{ fontSize: "9px", letterSpacing: "0.12em", color: "#5a5a78", textTransform: "uppercase", marginBottom: "4px" }}>
            DNA Drift Headline
          </div>
          <div style={{ color: "#e0e0f0", fontSize: "12px", lineHeight: 1.5, fontFamily: FONT }}>
            {data.drift_summary || "Stated and measured DNA closely aligned"}
          </div>
        </div>

        <div style={{ marginBottom: "16px" }}>
          <div style={{ fontSize: "9px", letterSpacing: "0.12em", color: "#5a5a78", textTransform: "uppercase", marginBottom: "8px" }}>
            Confidence
          </div>
          <div style={{
            height: "6px",
            background: "rgba(255,255,255,0.05)",
            borderRadius: "3px",
            overflow: "hidden",
            position: "relative",
          }}>
            <div style={{
              width: `${(data.measured.confidence ?? 0) * 100}%`,
              height: "100%",
              background: "linear-gradient(90deg, #7c5cfc, #a78bfa)",
            }} />
          </div>
          <div style={{ fontSize: "10px", color: "#7a7a98", marginTop: "4px" }}>
            {(data.measured.confidence * 100).toFixed(0)}% — measured genome data depth
          </div>
        </div>

        <div>
          <div style={{ fontSize: "9px", letterSpacing: "0.12em", color: "#5a5a78", textTransform: "uppercase", marginBottom: "8px" }}>
            All Axes
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11px" }}>
            <thead>
              <tr style={{ color: "#5a5a78", fontSize: "9px" }}>
                <th style={{ textAlign: "left", padding: "4px 0" }}>Axis</th>
                <th style={{ textAlign: "right", padding: "4px 0" }}>Stated</th>
                <th style={{ textAlign: "right", padding: "4px 0" }}>Meas.</th>
                <th style={{ textAlign: "right", padding: "4px 0" }}>Δ</th>
              </tr>
            </thead>
            <tbody>
              {sortedAxes.map((axis) => {
                const drift = data.drift[axis] ?? 0;
                const driftAbs = Math.abs(drift);
                const isTop = topDrift.includes(axis);
                const color = driftAbs >= 25 ? "#f87171" : driftAbs >= 10 ? "#fbbf24" : "#5a5a78";
                return (
                  <tr key={axis} style={{
                    background: isTop ? "rgba(124,92,252,0.06)" : "transparent",
                    color: "#e0e0f0",
                  }}>
                    <td style={{ padding: "4px 0", fontFamily: FONT }}>{AXIS_LABELS[axis]}</td>
                    <td style={{ textAlign: "right", padding: "4px 4px", color: "#fbbf24" }}>
                      {(data.stated[axis] as number).toFixed(0)}
                    </td>
                    <td style={{ textAlign: "right", padding: "4px 4px", color: "#a78bfa" }}>
                      {(data.measured[axis] as number).toFixed(0)}
                    </td>
                    <td style={{ textAlign: "right", padding: "4px 0", color, fontWeight: 600 }}>
                      {drift > 0 ? "+" : ""}{drift.toFixed(0)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div style={{ marginTop: "16px", fontSize: "9px", color: "#5a5a78", lineHeight: 1.5 }}>
          Δ = stated − measured. Positive = overclaiming (config says you do X, behavior says less). Highlighted rows are the top-3 disagreements.
        </div>
      </div>
    </div>
  );
}
