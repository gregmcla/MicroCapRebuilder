/** Risk Pulse: full RISK tab — score hero, components grid, warnings, near-stop, recommendations. */

import type { IntelligenceBriefData } from "../../lib/types";

const DATA_FONT = "var(--font-mono)";
const PROSE_FONT = "var(--font-sans)";

const SEVERITY_COLOR: Record<string, string> = {
  critical: "var(--red)",
  high: "#f97316",
  medium: "var(--amber)",
  low: "#60a5fa",
  info: "#60a5fa",
};

function scoreColor(score: number): string {
  if (score <= 30) return "var(--green)";
  if (score <= 60) return "var(--amber)";
  return "var(--red)";
}

function scoreTint(score: number): string {
  if (score <= 30) return "var(--green-dim)";
  if (score <= 60) return "var(--amber-dim)";
  return "var(--red-dim)";
}

function scoreLabel(score: number): string {
  if (score <= 30) return "LOW RISK";
  if (score <= 60) return "MODERATE";
  return "HIGH RISK";
}

function statusColor(status: string): string {
  if (status === "OK") return "var(--green)";
  if (status === "WARNING") return "var(--amber)";
  return "var(--red)";
}

function SectionHeader({ label, color, badge }: { label: string; color?: string; badge?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" }}>
      <span style={{
        fontSize: "10px",
        fontFamily: PROSE_FONT,
        fontWeight: 600,
        letterSpacing: "0.1em",
        color: color ?? "var(--text-dim)",
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
          background: "var(--bg-elevated)",
          color: "var(--text-muted)",
        }}>
          {badge}
        </span>
      )}
      <div style={{ flex: 1, height: "1px", background: "linear-gradient(90deg, var(--border) 0%, transparent 100%)" }} />
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
          color: "var(--text-dim)",
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
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  borderTop: "1px solid var(--border-hover)",
                  borderRadius: "var(--radius)",
                  padding: "16px 20px",
                  boxShadow: "0 1px 4px rgba(0,0,0,0.35)",
                }}>
                  <div style={{
                    fontSize: "11px",
                    fontFamily: PROSE_FONT,
                    color: "var(--text-secondary)",
                    marginBottom: "10px",
                  }}>
                    {comp.name}
                  </div>
                  <div style={{
                    height: "4px",
                    background: "var(--bg-elevated)",
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
          background: "var(--green-dim)",
          border: "1px solid rgba(34,197,94,0.12)",
        }}>
          <span style={{ fontSize: "12px", fontFamily: PROSE_FONT, color: "var(--green)" }}>
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
                  background: "var(--red-dim)",
                  border: "1px solid rgba(239,68,68,0.2)",
                  borderTop: "1px solid rgba(239,68,68,0.3)",
                  borderLeft: "3px solid rgba(239,68,68,0.7)",
                  borderRadius: "var(--radius)",
                  padding: "14px 18px",
                } : {
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  borderTop: "1px solid var(--border-hover)",
                  borderRadius: "var(--radius)",
                  padding: "14px 18px",
                  boxShadow: "0 1px 4px rgba(0,0,0,0.35)",
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
                      color: "var(--text-primary)",
                    }}>
                      {w.title}
                    </span>
                  </div>
                  <div style={{
                    fontSize: "11px",
                    color: "var(--text-secondary)",
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
                background: "var(--amber-dim)",
                color: "var(--amber)",
                border: "1px solid rgba(245,158,11,0.2)",
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
                borderLeft: "2px solid rgba(139,92,246,0.3)",
                fontSize: "12px",
                fontFamily: PROSE_FONT,
                color: "var(--text-secondary)",
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
