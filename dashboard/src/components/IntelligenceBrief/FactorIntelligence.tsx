/** Factor Intelligence: full FACTORS tab — performance table, weight suggestions, designed empty state. */

import type { IntelligenceBriefData } from "../../lib/types";

const DATA_FONT = "var(--font-mono)";
const PROSE_FONT = "var(--font-sans)";

const FACTOR_COLORS: Record<string, string> = {
  price_momentum: "var(--accent)",
  earnings_growth: "var(--green)",
  quality: "#5ce0d6",
  volume: "var(--amber)",
  volatility: "var(--red)",
  value_timing: "#a78bfa",
};

function SectionHeader({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" }}>
      <span style={{
        fontSize: "10px",
        fontFamily: PROSE_FONT,
        fontWeight: 600,
        letterSpacing: "0.1em",
        color: "var(--text-dim)",
        textTransform: "uppercase" as const,
        whiteSpace: "nowrap" as const,
      }}>
        {label}
      </span>
      <div style={{ flex: 1, height: "1px", background: "linear-gradient(90deg, var(--border) 0%, transparent 100%)" }} />
    </div>
  );
}

function GridIcon() {
  // 3x3 grid SVG, 2 squares filled with accent color, rest unfilled
  return (
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="4" y="4" width="11" height="11" rx="2" fill="rgba(124,92,252,0.5)" />
      <rect x="19" y="4" width="11" height="11" rx="2" fill="rgba(255,255,255,0.08)" />
      <rect x="34" y="4" width="11" height="11" rx="2" fill="rgba(255,255,255,0.08)" />
      <rect x="4" y="19" width="11" height="11" rx="2" fill="rgba(255,255,255,0.08)" />
      <rect x="19" y="19" width="11" height="11" rx="2" fill="rgba(124,92,252,0.5)" />
      <rect x="34" y="19" width="11" height="11" rx="2" fill="rgba(255,255,255,0.08)" />
      <rect x="4" y="34" width="11" height="11" rx="2" fill="rgba(255,255,255,0.08)" />
      <rect x="19" y="34" width="11" height="11" rx="2" fill="rgba(255,255,255,0.08)" />
      <rect x="34" y="34" width="11" height="11" rx="2" fill="rgba(255,255,255,0.08)" />
    </svg>
  );
}

function trendPill(trend: string) {
  if (trend === "improving") {
    return {
      label: "\u25B2",
      bg: "var(--green-dim)",
      color: "var(--green)",
      border: "1px solid rgba(34,197,94,0.2)",
    };
  }
  if (trend === "declining") {
    return {
      label: "\u25BC",
      bg: "var(--red-dim)",
      color: "var(--red)",
      border: "1px solid rgba(239,68,68,0.2)",
    };
  }
  return {
    label: "\u2192",
    bg: "var(--bg-elevated)",
    color: "var(--text-muted)",
    border: "1px solid var(--border)",
  };
}

function confidenceBadge(confidence: string) {
  const c = confidence.toUpperCase();
  if (c === "HIGH") {
    return {
      bg: "var(--green-dim)",
      color: "var(--green)",
      border: "1px solid rgba(34,197,94,0.2)",
    };
  }
  if (c === "MEDIUM") {
    return {
      bg: "rgba(96,165,250,0.15)",
      color: "#60a5fa",
      border: "1px solid rgba(96,165,250,0.2)",
    };
  }
  return {
    bg: "var(--bg-elevated)",
    color: "var(--text-muted)",
    border: "1px solid var(--border)",
  };
}

interface Props { brief?: IntelligenceBriefData }

export default function FactorIntelligence({ brief }: Props) {
  const factors = brief?.factor_summary?.factors ?? [];
  const suggestions = brief?.weight_suggestions ?? [];
  const defaultWeights = (brief?.config as any)?.scoring?.default_weights ?? {};

  const TABLE_COLS = "2fr 80px 70px 70px 70px";
  const HEADER_LABELS = ["FACTOR", "WIN RATE", "TRADES", "TREND", "WEIGHT"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px", padding: "4px 0" }}>

      {/* Empty state */}
      {factors.length === 0 && (
        <div style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          gap: "16px",
          padding: "48px 20px",
        }}>
          <GridIcon />
          <span style={{
            fontSize: "11px",
            letterSpacing: "0.12em",
            color: "var(--text-muted)",
            fontFamily: PROSE_FONT,
            fontWeight: 600,
          }}>
            FACTOR ANALYSIS UNLOCKS AFTER 5+ TRADES
          </span>
          <span style={{
            fontSize: "12px",
            color: "var(--text-dim)",
            textAlign: "center" as const,
            maxWidth: "340px",
            lineHeight: 1.6,
            fontFamily: PROSE_FONT,
          }}>
            As your portfolio completes trades, GScott analyzes which factors drive returns and suggests weight adjustments.
          </span>
        </div>
      )}

      {/* Section 1: Factor Performance Table */}
      {factors.length > 0 && (
        <div style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border)",
          borderTop: "1px solid var(--border-hover)",
          borderRadius: "var(--radius)",
          padding: "16px 20px",
          boxShadow: "0 1px 4px rgba(0,0,0,0.35)",
        }}>
          <SectionHeader label="Factor Performance" />

          {/* Table header */}
          <div style={{
            display: "grid",
            gridTemplateColumns: TABLE_COLS,
            gap: "8px",
            background: "var(--bg-elevated)",
            padding: "10px 16px",
            borderBottom: "1px solid var(--border)",
            borderRadius: "4px 4px 0 0",
          }}>
            {HEADER_LABELS.map(h => (
              <span key={h} style={{
                fontSize: "9px",
                letterSpacing: "0.12em",
                color: "var(--text-dim)",
                fontFamily: PROSE_FONT,
                fontWeight: 600,
                textTransform: "uppercase" as const,
              }}>
                {h}
              </span>
            ))}
          </div>

          {/* Table rows */}
          {factors.map(f => {
            const fColor = FACTOR_COLORS[f.factor] ?? "#888";
            const winColor = f.win_rate >= 0.6 ? "var(--green)" : f.win_rate >= 0.45 ? "var(--amber)" : "var(--red)";
            const tp = trendPill(f.trend);
            const weight = defaultWeights[f.factor];
            return (
              <div key={f.factor} style={{
                display: "grid",
                gridTemplateColumns: TABLE_COLS,
                gap: "8px",
                padding: "10px 16px",
                borderBottom: "1px solid var(--border)",
                alignItems: "center",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{
                    width: "3px",
                    height: "16px",
                    borderRadius: "2px",
                    background: fColor,
                    flexShrink: 0,
                  }} />
                  <span style={{
                    fontSize: "12px",
                    fontFamily: DATA_FONT,
                    fontWeight: 600,
                    color: "var(--text-primary)",
                  }}>
                    {f.factor.replace(/_/g, " ")}
                  </span>
                </div>
                <span style={{
                  fontSize: "13px",
                  fontFamily: DATA_FONT,
                  fontWeight: 600,
                  color: winColor,
                }}>
                  {(f.win_rate * 100).toFixed(0)}%
                </span>
                <span style={{
                  fontSize: "12px",
                  fontFamily: DATA_FONT,
                  color: "var(--text-secondary)",
                }}>
                  {f.total_trades}
                </span>
                <span style={{
                  fontSize: "10px",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  background: tp.bg,
                  color: tp.color,
                  border: tp.border,
                  display: "inline-block",
                  textAlign: "center" as const,
                  width: "fit-content",
                }}>
                  {tp.label}
                </span>
                <span style={{
                  fontSize: "12px",
                  fontFamily: DATA_FONT,
                  color: "var(--text-muted)",
                }}>
                  {weight != null ? `${(weight * 100).toFixed(0)}%` : "\u2014"}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Section 2: Weight Suggestions */}
      <div style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderTop: "1px solid var(--border-hover)",
        borderRadius: "var(--radius)",
        padding: "16px 20px",
        boxShadow: "0 1px 4px rgba(0,0,0,0.35)",
      }}>
        <SectionHeader label="Weight Suggestions" />

        {suggestions.length === 0 ? (
          <span style={{
            fontSize: "12px",
            fontFamily: PROSE_FONT,
            color: "var(--text-dim)",
            fontStyle: "italic" as const,
          }}>
            No adjustments suggested yet
          </span>
        ) : (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {suggestions.map(s => {
              const fColor = FACTOR_COLORS[s.factor] ?? "#888";
              const isIncrease = s.change_pct > 0;
              const changeColor = isIncrease ? "var(--green)" : "var(--red)";
              const cb = confidenceBadge(s.confidence);
              return (
                <div key={s.factor} style={{
                  padding: "10px 0",
                  borderBottom: "1px solid var(--border)",
                }}>
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "16px",
                    flexWrap: "wrap" as const,
                  }}>
                    {/* Factor name + color bar */}
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: "140px" }}>
                      <div style={{
                        width: "3px",
                        height: "16px",
                        borderRadius: "2px",
                        background: fColor,
                        flexShrink: 0,
                      }} />
                      <span style={{
                        fontSize: "12px",
                        fontFamily: DATA_FONT,
                        fontWeight: 600,
                        color: "var(--text-primary)",
                      }}>
                        {s.factor.replace(/_/g, " ")}
                      </span>
                    </div>

                    {/* Current weight */}
                    <span style={{
                      fontSize: "12px",
                      fontFamily: DATA_FONT,
                      color: "var(--text-secondary)",
                    }}>
                      {(s.current_weight * 100).toFixed(0)}%
                    </span>

                    {/* Arrow */}
                    <span style={{ color: "var(--text-dim)", fontSize: "12px" }}>{"\u2192"}</span>

                    {/* Suggested weight */}
                    <span style={{
                      fontSize: "12px",
                      fontFamily: DATA_FONT,
                      color: changeColor,
                      fontWeight: 600,
                    }}>
                      {(s.suggested_weight * 100).toFixed(0)}%
                    </span>

                    {/* Change pill */}
                    <span style={{
                      fontSize: "10px",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      background: isIncrease ? "var(--green-dim)" : "var(--red-dim)",
                      color: changeColor,
                      border: `1px solid ${isIncrease ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`,
                      fontFamily: DATA_FONT,
                    }}>
                      {isIncrease ? "+" : ""}{s.change_pct.toFixed(1)}%
                    </span>

                    {/* Confidence badge */}
                    <span style={{
                      fontSize: "10px",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      background: cb.bg,
                      color: cb.color,
                      border: cb.border,
                      fontFamily: PROSE_FONT,
                      fontWeight: 600,
                      letterSpacing: "0.06em",
                      textTransform: "uppercase" as const,
                    }}>
                      {s.confidence}
                    </span>
                  </div>

                  {/* Reason — full width second line */}
                  {s.reason && (
                    <div style={{
                      fontSize: "11px",
                      fontFamily: PROSE_FONT,
                      color: "var(--text-muted)",
                      marginTop: "4px",
                      lineHeight: 1.5,
                      paddingLeft: "11px",
                    }}>
                      {s.reason}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
