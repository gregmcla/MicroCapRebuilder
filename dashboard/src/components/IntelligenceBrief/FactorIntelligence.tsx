/** Factor Intelligence: full FACTORS tab — performance table, weight suggestions, designed empty state. */

import type { IntelligenceBriefData } from "../../lib/types";

const DATA_FONT = "'JetBrains Mono', 'SF Mono', monospace";
const PROSE_FONT = "-apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif";

const FACTOR_COLORS: Record<string, string> = {
  price_momentum: "#7c5cfc",
  earnings_growth: "#34d399",
  quality: "#5ce0d6",
  volume: "#fbbf24",
  volatility: "#f87171",
  value_timing: "#a78bfa",
};

const FACTORS_ORDER = [
  "price_momentum", "earnings_growth", "quality",
  "volume", "volatility", "value_timing",
];

const REGIME_BADGE: Record<string, { bg: string; color: string; border: string }> = {
  BULL:     { bg: "rgba(52,211,153,0.12)",  color: "#34d399", border: "1px solid rgba(52,211,153,0.2)" },
  BEAR:     { bg: "rgba(248,113,113,0.12)", color: "#f87171", border: "1px solid rgba(248,113,113,0.2)" },
  SIDEWAYS: { bg: "rgba(251,191,36,0.12)",  color: "#fbbf24", border: "1px solid rgba(251,191,36,0.2)" },
  ALL:      { bg: "rgba(167,139,250,0.12)", color: "#a78bfa", border: "1px solid rgba(167,139,250,0.2)" },
};

function SectionHeader({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" }}>
      <span style={{
        fontSize: "10px",
        fontFamily: PROSE_FONT,
        fontWeight: 600,
        letterSpacing: "0.1em",
        color: "#5a5a78",
        textTransform: "uppercase" as const,
        whiteSpace: "nowrap" as const,
      }}>
        {label}
      </span>
      <div style={{ flex: 1, height: "1px", background: "linear-gradient(90deg, rgba(255,255,255,0.08) 0%, transparent 100%)" }} />
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
      bg: "rgba(52,211,153,0.12)",
      color: "#34d399",
      border: "1px solid rgba(52,211,153,0.2)",
    };
  }
  if (trend === "declining") {
    return {
      label: "\u25BC",
      bg: "rgba(248,113,113,0.12)",
      color: "#f87171",
      border: "1px solid rgba(248,113,113,0.2)",
    };
  }
  return {
    label: "\u2192",
    bg: "rgba(255,255,255,0.06)",
    color: "rgba(255,255,255,0.4)",
    border: "1px solid rgba(255,255,255,0.1)",
  };
}

function confidenceBadge(confidence: string) {
  const c = confidence.toUpperCase();
  if (c === "HIGH") {
    return {
      bg: "rgba(52,211,153,0.12)",
      color: "#34d399",
      border: "1px solid rgba(52,211,153,0.2)",
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
    bg: "rgba(255,255,255,0.06)",
    color: "rgba(255,255,255,0.4)",
    border: "1px solid rgba(255,255,255,0.1)",
  };
}

interface Props { brief?: IntelligenceBriefData }

export default function FactorIntelligence({ brief }: Props) {
  const factors = brief?.factor_summary?.factors ?? [];
  const suggestions = brief?.weight_suggestions ?? [];
  const defaultWeights = (brief?.config as any)?.scoring?.default_weights ?? {};
  const regimeWeights = (brief?.config as any)?.scoring?.regime_weights ?? {};
  const observations = brief?.observations ?? [];
  const currentRegime = (brief?.regime ?? "").toUpperCase();

  const bullMax = Math.max(0, ...Object.values(regimeWeights.BULL ?? {}).map(Number));
  const bearMax = Math.max(0, ...Object.values(regimeWeights.BEAR ?? {}).map(Number));
  const sidewaysMax = Math.max(0, ...Object.values(regimeWeights.SIDEWAYS ?? {}).map(Number));
  const hasRegimeWeights = !!(regimeWeights.BULL || regimeWeights.BEAR || regimeWeights.SIDEWAYS);

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
            color: "rgba(255,255,255,0.4)",
            fontFamily: PROSE_FONT,
            fontWeight: 600,
          }}>
            FACTOR ANALYSIS UNLOCKS AFTER 5+ TRADES
          </span>
          <span style={{
            fontSize: "12px",
            color: "rgba(255,255,255,0.25)",
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
          background: "rgba(255,255,255,0.028)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderTop: "1px solid rgba(255,255,255,0.11)",
          borderRadius: "8px",
          padding: "16px 20px",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 4px rgba(0,0,0,0.35)",
        }}>
          <SectionHeader label="Factor Performance" />

          {/* Table header */}
          <div style={{
            display: "grid",
            gridTemplateColumns: TABLE_COLS,
            gap: "8px",
            background: "rgba(255,255,255,0.03)",
            padding: "10px 16px",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            borderRadius: "4px 4px 0 0",
          }}>
            {HEADER_LABELS.map(h => (
              <span key={h} style={{
                fontSize: "9px",
                letterSpacing: "0.12em",
                color: "rgba(255,255,255,0.3)",
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
            const winColor = f.win_rate >= 0.6 ? "#34d399" : f.win_rate >= 0.45 ? "#fbbf24" : "#f87171";
            const tp = trendPill(f.trend);
            const weight = defaultWeights[f.factor];
            return (
              <div key={f.factor} style={{
                display: "grid",
                gridTemplateColumns: TABLE_COLS,
                gap: "8px",
                padding: "10px 16px",
                borderBottom: "1px solid rgba(255,255,255,0.04)",
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
                    color: "#e2e2f0",
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
                  color: "rgba(255,255,255,0.5)",
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
                  color: "rgba(255,255,255,0.4)",
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
        background: "rgba(255,255,255,0.028)",
        border: "1px solid rgba(255,255,255,0.07)",
        borderTop: "1px solid rgba(255,255,255,0.11)",
        borderRadius: "8px",
        padding: "16px 20px",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 4px rgba(0,0,0,0.35)",
      }}>
        <SectionHeader label="Weight Suggestions" />

        {suggestions.length === 0 ? (
          <span style={{
            fontSize: "12px",
            fontFamily: PROSE_FONT,
            color: "rgba(255,255,255,0.25)",
            fontStyle: "italic" as const,
          }}>
            No adjustments suggested yet
          </span>
        ) : (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {suggestions.map(s => {
              const fColor = FACTOR_COLORS[s.factor] ?? "#888";
              const isIncrease = s.change_pct > 0;
              const changeColor = isIncrease ? "#34d399" : "#f87171";
              const cb = confidenceBadge(s.confidence);
              return (
                <div key={s.factor} style={{
                  padding: "10px 0",
                  borderBottom: "1px solid rgba(255,255,255,0.04)",
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
                        color: "#e2e2f0",
                      }}>
                        {s.factor.replace(/_/g, " ")}
                      </span>
                    </div>

                    {/* Current weight */}
                    <span style={{
                      fontSize: "12px",
                      fontFamily: DATA_FONT,
                      color: "rgba(255,255,255,0.5)",
                    }}>
                      {(s.current_weight * 100).toFixed(0)}%
                    </span>

                    {/* Arrow */}
                    <span style={{ color: "rgba(255,255,255,0.2)", fontSize: "12px" }}>{"\u2192"}</span>

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
                      background: isIncrease ? "rgba(52,211,153,0.12)" : "rgba(248,113,113,0.12)",
                      color: changeColor,
                      border: `1px solid ${isIncrease ? "rgba(52,211,153,0.2)" : "rgba(248,113,113,0.2)"}`,
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
                      color: "rgba(255,255,255,0.4)",
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

      {/* Section 3: Bayesian Weights by Regime */}
      {hasRegimeWeights && (
        <div style={{
          background: "rgba(255,255,255,0.028)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderTop: "1px solid rgba(255,255,255,0.11)",
          borderRadius: "8px",
          padding: "16px 20px",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 4px rgba(0,0,0,0.35)",
        }}>
          <SectionHeader label="Bayesian Weights by Regime" />

          {/* Column headers */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "2fr 1fr 1fr 1fr",
            gap: "8px",
            background: "rgba(255,255,255,0.03)",
            padding: "10px 16px",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            borderRadius: "4px 4px 0 0",
          }}>
            <span style={{ fontSize: "9px", letterSpacing: "0.12em", color: "rgba(255,255,255,0.3)", fontFamily: PROSE_FONT, fontWeight: 600, textTransform: "uppercase" as const }}>
              FACTOR
            </span>
            {(["BULL", "BEAR", "SIDEWAYS"] as const).map(r => {
              const isActive = currentRegime === r;
              const badge = REGIME_BADGE[r];
              return (
                <span key={r} style={{
                  fontSize: "9px", letterSpacing: "0.12em",
                  color: isActive ? badge.color : "rgba(255,255,255,0.3)",
                  fontFamily: PROSE_FONT, fontWeight: 600, textTransform: "uppercase" as const,
                }}>
                  {isActive ? "▸ " : ""}{r}
                </span>
              );
            })}
          </div>

          {/* Factor rows */}
          {FACTORS_ORDER.map(f => {
            const fColor = FACTOR_COLORS[f] ?? "#888";
            const bullW = (regimeWeights.BULL ?? {})[f] as number | undefined;
            const bearW = (regimeWeights.BEAR ?? {})[f] as number | undefined;
            const sidewaysW = (regimeWeights.SIDEWAYS ?? {})[f] as number | undefined;
            const weights = [
              { val: bullW, max: bullMax, regime: "BULL" as const },
              { val: bearW, max: bearMax, regime: "BEAR" as const },
              { val: sidewaysW, max: sidewaysMax, regime: "SIDEWAYS" as const },
            ];
            return (
              <div key={f} style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 1fr 1fr",
                gap: "8px",
                padding: "9px 16px",
                borderBottom: "1px solid rgba(255,255,255,0.04)",
                alignItems: "center",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ width: "3px", height: "14px", borderRadius: "2px", background: fColor, flexShrink: 0 }} />
                  <span style={{ fontSize: "11px", fontFamily: DATA_FONT, color: "rgba(226,226,240,0.8)" }}>
                    {f.replace(/_/g, " ")}
                  </span>
                </div>
                {weights.map(({ val, max, regime }) => {
                  const isDominant = val !== undefined && val >= max - 0.0005;
                  const isActive = currentRegime === regime;
                  const badge = REGIME_BADGE[regime];
                  return (
                    <span key={regime} style={{
                      fontSize: "12px",
                      fontFamily: DATA_FONT,
                      fontWeight: isDominant ? 700 : 400,
                      color: isDominant ? badge.color : isActive ? "rgba(255,255,255,0.6)" : "rgba(255,255,255,0.35)",
                    }}>
                      {val != null ? `${(val * 100).toFixed(0)}%` : "—"}
                    </span>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      {/* Section 4: Opus Observations */}
      <div style={{
        background: "rgba(255,255,255,0.028)",
        border: "1px solid rgba(255,255,255,0.07)",
        borderTop: "1px solid rgba(255,255,255,0.11)",
        borderRadius: "8px",
        padding: "16px 20px",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 4px rgba(0,0,0,0.35)",
      }}>
        <SectionHeader label="Opus Observations" />

        {observations.length === 0 ? (
          <span style={{ fontSize: "12px", fontFamily: PROSE_FONT, color: "rgba(255,255,255,0.25)", fontStyle: "italic" as const }}>
            No observations yet — builds after execute cycles with trades.
          </span>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {[...observations]
              .sort((a, b) => (b.sample_size ?? 0) - (a.sample_size ?? 0))
              .map(obs => {
                const regimeKey = (obs.regime ?? "ALL").toUpperCase();
                const badge = REGIME_BADGE[regimeKey] ?? REGIME_BADGE.ALL;
                const winColor = (obs.win_rate ?? 0) >= 0.6 ? "#34d399" : (obs.win_rate ?? 0) >= 0.45 ? "#fbbf24" : "#f87171";
                return (
                  <div key={obs.id} style={{
                    padding: "10px 12px",
                    background: "rgba(255,255,255,0.02)",
                    border: "1px solid rgba(255,255,255,0.06)",
                    borderRadius: "6px",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px", flexWrap: "wrap" as const }}>
                      <span style={{
                        fontSize: "9px", padding: "2px 8px", borderRadius: "4px",
                        background: badge.bg, color: badge.color, border: badge.border,
                        fontFamily: PROSE_FONT, fontWeight: 600, letterSpacing: "0.06em",
                        textTransform: "uppercase" as const,
                      }}>
                        {obs.regime}
                      </span>
                      <span style={{ fontSize: "11px", fontFamily: DATA_FONT, color: "rgba(255,255,255,0.4)" }}>
                        n={obs.sample_size}
                      </span>
                      <span style={{ fontSize: "11px", fontFamily: DATA_FONT, color: winColor, fontWeight: 600 }}>
                        win={(((obs.win_rate ?? 0) * 100).toFixed(0))}%
                      </span>
                    </div>
                    <p style={{
                      fontSize: "11px", fontFamily: PROSE_FONT,
                      color: "rgba(255,255,255,0.6)", lineHeight: 1.6, margin: 0,
                    }}>
                      {obs.claim}
                    </p>
                  </div>
                );
              })}
          </div>
        )}
      </div>
    </div>
  );
}
