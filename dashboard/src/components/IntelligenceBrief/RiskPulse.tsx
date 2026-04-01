/** Risk Pulse: full RISK tab — score hero, components grid, warnings, near-stop, recommendations. */

import type { IntelligenceBriefData } from "../../lib/types";

const DATA_FONT = "'JetBrains Mono', 'SF Mono', monospace";
const PROSE_FONT = "-apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif";

const SEVERITY_COLOR: Record<string, string> = {
  critical: "#f87171",
  high: "#f97316",
  medium: "#fbbf24",
  low: "#60a5fa",
  info: "#60a5fa",
};

function scoreColor(score: number): string {
  if (score <= 30) return "#34d399";
  if (score <= 60) return "#fbbf24";
  return "#f87171";
}

function scoreTint(score: number): string {
  if (score <= 30) return "rgba(52,211,153,0.04)";
  if (score <= 60) return "rgba(251,191,36,0.04)";
  return "rgba(248,113,113,0.04)";
}

function scoreLabel(score: number): string {
  if (score <= 30) return "LOW RISK";
  if (score <= 60) return "MODERATE";
  return "HIGH RISK";
}

function statusColor(status: string): string {
  if (status === "OK") return "#34d399";
  if (status === "WARNING") return "#fbbf24";
  return "#f87171";
}

function SectionHeader({ label, color, badge }: { label: string; color?: string; badge?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" }}>
      <span style={{
        fontSize: "10px",
        fontFamily: PROSE_FONT,
        fontWeight: 600,
        letterSpacing: "0.1em",
        color: color ?? "#5a5a78",
        textTransform: "uppercase" as const,
        whiteSpace: "nowrap" as const,
      }}>
        {label}
      </span>
      {badge && (
        <span style={{
          fontSize: "9px",
          fontFamily: DATA_FONT,
          fontWeight: 600,
          padding: "1px 6px",
          borderRadius: "3px",
          background: "rgba(255,255,255,0.06)",
          color: "rgba(255,255,255,0.4)",
        }}>
          {badge}
        </span>
      )}
      <div style={{ flex: 1, height: "1px", background: "linear-gradient(90deg, rgba(255,255,255,0.08) 0%, transparent 100%)" }} />
    </div>
  );
}

interface Props { brief?: IntelligenceBriefData }

export default function RiskPulse({ brief }: Props) {
  const risk = brief?.risk;
  const score = risk?.overall_score ?? 0;
  const components = risk?.components ?? [];
  const warnings = brief?.warnings ?? [];
  const nearStop = brief?.positions_near_stop ?? [];
  const recommendations = brief?.health?.recommendations ?? [];
  const color = scoreColor(score);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px", padding: "4px 0" }}>

      {/* 1. Risk Score Hero */}
      <div style={{
        background: scoreTint(score),
        border: `1px solid ${color}33`,
        borderTop: `1px solid ${color}55`,
        borderLeft: `4px solid ${color}`,
        borderRadius: "10px",
        padding: "28px 32px",
        boxShadow: `inset 0 1px 0 ${color}33, 0 4px 20px rgba(0,0,0,0.5), 0 0 40px ${color}14`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "4px",
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: "4px" }}>
          <span style={{
            fontSize: "56px",
            fontFamily: DATA_FONT,
            fontWeight: 700,
            color,
            lineHeight: 1,
          }}>
            {score.toFixed(0)}
          </span>
          <span style={{
            fontSize: "18px",
            fontFamily: DATA_FONT,
            color,
            opacity: 0.4,
          }}>
            /100
          </span>
        </div>
        <span style={{
          fontSize: "10px",
          fontFamily: PROSE_FONT,
          fontWeight: 500,
          letterSpacing: "0.08em",
          color: "#4a4a68",
          textTransform: "uppercase" as const,
        }}>
          RISK SCORE
        </span>
        <span style={{
          fontSize: "11px",
          fontFamily: PROSE_FONT,
          fontWeight: 600,
          letterSpacing: "0.1em",
          color,
          marginTop: "4px",
        }}>
          {scoreLabel(score)}
        </span>
      </div>

      {/* 2. Risk Components Grid */}
      {components.length > 0 && (
        <div>
          <SectionHeader label="Risk Components" />
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
            gap: "12px",
          }}>
            {components.map(comp => {
              const cColor = statusColor(comp.status);
              const pct = Math.max(0, Math.min(100, comp.score));
              return (
                <div key={comp.name} style={{
                  background: "rgba(255,255,255,0.028)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderTop: "1px solid rgba(255,255,255,0.11)",
                  borderRadius: "8px",
                  padding: "16px 20px",
                  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 4px rgba(0,0,0,0.35)",
                }}>
                  <div style={{
                    fontSize: "11px",
                    fontFamily: PROSE_FONT,
                    color: "#9090b0",
                    marginBottom: "10px",
                  }}>
                    {comp.name}
                  </div>
                  <div style={{
                    height: "4px",
                    background: "rgba(255,255,255,0.06)",
                    borderRadius: "2px",
                    marginBottom: "8px",
                  }}>
                    <div style={{
                      height: "100%",
                      borderRadius: "2px",
                      width: `${pct}%`,
                      background: cColor,
                      transition: "width 300ms ease",
                    }} />
                  </div>
                  <span style={{
                    fontSize: "18px",
                    fontFamily: DATA_FONT,
                    fontWeight: 600,
                    color: cColor,
                  }}>
                    {comp.score.toFixed(0)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* No-warnings banner */}
      {warnings.length === 0 && (
        <div style={{
          padding: "10px 14px",
          borderRadius: "6px",
          background: "rgba(52,211,153,0.05)",
          border: "1px solid rgba(52,211,153,0.12)",
        }}>
          <span style={{ fontSize: "12px", fontFamily: PROSE_FONT, color: "rgba(52,211,153,0.7)" }}>
            &#10003; No active warnings
          </span>
        </div>
      )}

      {/* 3. Active Warnings */}
      {warnings.length > 0 && (
        <div>
          <SectionHeader label="Active Warnings" badge={String(warnings.length)} />
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {warnings.map(w => {
              const sColor = SEVERITY_COLOR[w.severity] ?? "#888";
              const isDanger = w.severity === "critical" || w.severity === "high";
              return (
                <div key={w.id} style={isDanger ? {
                  background: "rgba(248,113,113,0.05)",
                  border: "1px solid rgba(248,113,113,0.2)",
                  borderTop: "1px solid rgba(248,113,113,0.3)",
                  borderLeft: "3px solid rgba(248,113,113,0.7)",
                  borderRadius: "8px",
                  padding: "14px 18px",
                } : {
                  background: "rgba(255,255,255,0.028)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderTop: "1px solid rgba(255,255,255,0.11)",
                  borderRadius: "8px",
                  padding: "14px 18px",
                  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 4px rgba(0,0,0,0.35)",
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                    <span style={{
                      fontSize: "8px",
                      letterSpacing: "0.12em",
                      fontWeight: 700,
                      textTransform: "uppercase" as const,
                      color: sColor,
                    }}>
                      {w.severity.toUpperCase()}
                    </span>
                    <span style={{
                      fontSize: "12px",
                      fontWeight: 600,
                      color: "#e8e8f8",
                    }}>
                      {w.title}
                    </span>
                  </div>
                  <div style={{
                    fontSize: "11px",
                    color: "rgba(255,255,255,0.5)",
                    lineHeight: 1.5,
                  }}>
                    {w.description}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 4. Near-Stop Positions */}
      {nearStop.length > 0 && (
        <div>
          <SectionHeader label="Positions Near Stop-Loss" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {nearStop.map(ticker => (
              <span key={ticker} style={{
                fontSize: "10px",
                padding: "2px 8px",
                borderRadius: "4px",
                background: "rgba(249,115,22,0.12)",
                color: "#f97316",
                border: "1px solid rgba(249,115,22,0.2)",
                fontFamily: DATA_FONT,
                fontWeight: 600,
              }}>
                {ticker}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 5. Recommendations */}
      {recommendations.length > 0 && (
        <div>
          <SectionHeader label="Recommendations" />
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {recommendations.map((r, i) => (
              <div key={i} style={{
                padding: "10px 14px",
                borderLeft: "2px solid rgba(124,92,252,0.3)",
                fontSize: "12px",
                fontFamily: PROSE_FONT,
                color: "rgba(255,255,255,0.6)",
                lineHeight: 1.6,
              }}>
                {r}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
