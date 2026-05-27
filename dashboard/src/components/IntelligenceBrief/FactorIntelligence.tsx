/** Factor Intelligence: Bayesian weight learner + Opus observation memory. */

import type { IntelligenceBriefData } from "../../lib/types";

const DATA_FONT = "'JetBrains Mono', 'SF Mono', monospace";
const PROSE_FONT = "-apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif";

const FACTOR_COLORS: Record<string, string> = {
  price_momentum:  "#7c5cfc",
  earnings_growth: "#34d399",
  quality:         "#5ce0d6",
  volume:          "#fbbf24",
  volatility:      "#f87171",
  value_timing:    "#a78bfa",
};

const FACTORS_ORDER = [
  "price_momentum", "earnings_growth", "quality",
  "volume", "volatility", "value_timing",
];

const REGIME_BADGE: Record<string, { bg: string; color: string; border: string }> = {
  BULL:     { bg: "rgba(52,211,153,0.12)",  color: "#34d399", border: "1px solid rgba(52,211,153,0.25)" },
  BEAR:     { bg: "rgba(248,113,113,0.12)", color: "#f87171", border: "1px solid rgba(248,113,113,0.25)" },
  SIDEWAYS: { bg: "rgba(251,191,36,0.12)",  color: "#fbbf24", border: "1px solid rgba(251,191,36,0.25)" },
  ALL:      { bg: "rgba(167,139,250,0.12)", color: "#a78bfa", border: "1px solid rgba(167,139,250,0.25)" },
};

const CARD: React.CSSProperties = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.07)",
  borderTop: "1px solid rgba(255,255,255,0.10)",
  borderRadius: "8px",
  padding: "16px 18px",
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04), 0 1px 4px rgba(0,0,0,0.3)",
};

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <span style={{
      fontSize: "9px", fontFamily: PROSE_FONT, fontWeight: 700,
      letterSpacing: "0.12em", color: "#4a4a68",
      textTransform: "uppercase" as const, whiteSpace: "nowrap" as const,
    }}>
      {children}
    </span>
  );
}

function Rule() {
  return (
    <div style={{
      flex: 1, height: "1px",
      background: "linear-gradient(90deg, rgba(255,255,255,0.07) 0%, transparent 100%)",
    }} />
  );
}

interface Props { brief?: IntelligenceBriefData }

export default function FactorIntelligence({ brief }: Props) {
  const defaultWeights  = (brief?.config as any)?.scoring?.default_weights  ?? {};
  const regimeWeights   = (brief?.config as any)?.scoring?.regime_weights   ?? {};
  const observations    = brief?.observations ?? [];
  const currentRegime   = (brief?.regime ?? "").toUpperCase();

  const activeRegimeData = currentRegime && regimeWeights[currentRegime];
  const activeWeights    = activeRegimeData ? regimeWeights[currentRegime] : defaultWeights;
  const isCalibrated     = !!activeRegimeData;
  const hasAnyRegime     = !!(regimeWeights.BULL || regimeWeights.BEAR || regimeWeights.SIDEWAYS);

  const maxW = Math.max(0.001, ...FACTORS_ORDER.map(f => Number(activeWeights[f] ?? 0)));

  const regimePeaks: Record<string, number> = {};
  for (const r of ["BULL", "BEAR", "SIDEWAYS"]) {
    regimePeaks[r] = Math.max(0, ...Object.values((regimeWeights[r] ?? {}) as Record<string, number>).map(Number));
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "18px", padding: "4px 0" }}>

      {/* ── Section 1: Active Factor Weights ─────────────────────────── */}
      <div style={CARD}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
          <SectionLabel>Factor Weights</SectionLabel>

          {/* Regime pill */}
          {currentRegime && (() => {
            const b = REGIME_BADGE[currentRegime];
            return b ? (
              <span style={{
                fontSize: "9px", padding: "1px 7px", borderRadius: "3px",
                background: b.bg, color: b.color, border: b.border,
                fontFamily: PROSE_FONT, fontWeight: 700, letterSpacing: "0.08em",
              }}>
                {currentRegime}
              </span>
            ) : null;
          })()}

          {/* Calibration status */}
          <span style={{
            fontSize: "9px", fontFamily: PROSE_FONT, fontWeight: 600,
            letterSpacing: "0.1em",
            color: isCalibrated ? "rgba(167,139,250,0.65)" : "rgba(255,255,255,0.18)",
          }}>
            {isCalibrated ? "BAYESIAN" : "DEFAULT · CALIBRATING"}
          </span>

          <Rule />
        </div>

        {/* Bar chart */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1px" }}>
          {FACTORS_ORDER.map(f => {
            const w   = Number(activeWeights[f] ?? 0);
            const pct = (w / maxW) * 100;
            const col = FACTOR_COLORS[f] ?? "#888";
            return (
              <div key={f} style={{ display: "flex", alignItems: "center", gap: "10px", padding: "5px 0" }}>
                <div style={{ width: "3px", height: "14px", background: col, borderRadius: "2px", flexShrink: 0 }} />
                <span style={{
                  width: "110px", fontSize: "11px", fontFamily: DATA_FONT,
                  color: "rgba(210,210,228,0.7)", flexShrink: 0,
                }}>
                  {f.replace(/_/g, " ")}
                </span>
                <div style={{
                  flex: 1, height: "5px", background: "rgba(255,255,255,0.05)",
                  borderRadius: "3px", overflow: "hidden",
                }}>
                  <div style={{
                    width: `${pct}%`, height: "100%", borderRadius: "3px",
                    background: `linear-gradient(90deg, ${col}88, ${col}bb)`,
                    transition: "width 0.4s ease",
                  }} />
                </div>
                <span style={{
                  width: "30px", fontSize: "12px", fontFamily: DATA_FONT,
                  fontWeight: 600, color: "#e0e0f0",
                  textAlign: "right" as const, flexShrink: 0,
                }}>
                  {(w * 100).toFixed(0)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Section 2: Regime Calibration ────────────────────────────── */}
      <div style={CARD}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: hasAnyRegime ? "14px" : "10px" }}>
          <SectionLabel>Regime Calibration</SectionLabel>
          <span style={{
            fontSize: "9px", fontFamily: PROSE_FONT, fontWeight: 700,
            letterSpacing: "0.08em",
            color: hasAnyRegime ? "rgba(52,211,153,0.6)" : "rgba(255,255,255,0.18)",
          }}>
            {hasAnyRegime ? "ACTIVE" : "PENDING"}
          </span>
          <Rule />
        </div>

        {!hasAnyRegime ? (
          <p style={{
            margin: 0, fontSize: "11px", fontFamily: PROSE_FONT, lineHeight: 1.65,
            color: "rgba(255,255,255,0.22)", fontStyle: "italic" as const,
          }}>
            Bayesian calibration runs automatically after 10+ closed trades. Until then, factor weights apply equally across BULL, BEAR, and SIDEWAYS regimes.
          </p>
        ) : (
          <>
            {/* Column headers */}
            <div style={{
              display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: "4px",
              padding: "8px 12px",
              background: "rgba(255,255,255,0.025)",
              borderRadius: "5px 5px 0 0",
              borderBottom: "1px solid rgba(255,255,255,0.055)",
            }}>
              <span style={{
                fontSize: "9px", fontFamily: PROSE_FONT, fontWeight: 600,
                letterSpacing: "0.1em", color: "rgba(255,255,255,0.2)",
                textTransform: "uppercase" as const,
              }}>
                FACTOR
              </span>
              {(["BULL", "BEAR", "SIDEWAYS"] as const).map(r => {
                const isActive = currentRegime === r;
                const b = REGIME_BADGE[r];
                return (
                  <span key={r} style={{
                    fontSize: "9px", fontFamily: PROSE_FONT, fontWeight: 700,
                    letterSpacing: "0.1em", textTransform: "uppercase" as const,
                    color: isActive ? b.color : "rgba(255,255,255,0.2)",
                  }}>
                    {isActive ? "▸ " : ""}{r}
                  </span>
                );
              })}
            </div>

            {/* Factor rows */}
            {FACTORS_ORDER.map((f, i) => {
              const fColor = FACTOR_COLORS[f] ?? "#888";
              const wBull = Number(((regimeWeights.BULL ?? {}) as any)[f] ?? 0);
              const wBear = Number(((regimeWeights.BEAR ?? {}) as any)[f] ?? 0);
              const wSide = Number(((regimeWeights.SIDEWAYS ?? {}) as any)[f] ?? 0);
              const entries = [
                { r: "BULL" as const,     w: wBull },
                { r: "BEAR" as const,     w: wBear },
                { r: "SIDEWAYS" as const, w: wSide },
              ];
              return (
                <div key={f} style={{
                  display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: "4px",
                  padding: "8px 12px", alignItems: "center",
                  background: i % 2 === 0 ? "rgba(255,255,255,0.01)" : "transparent",
                  borderBottom: "1px solid rgba(255,255,255,0.03)",
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "7px" }}>
                    <div style={{ width: "3px", height: "12px", borderRadius: "2px", background: fColor, flexShrink: 0 }} />
                    <span style={{ fontSize: "11px", fontFamily: DATA_FONT, color: "rgba(200,200,218,0.65)" }}>
                      {f.replace(/_/g, " ")}
                    </span>
                  </div>
                  {entries.map(({ r, w }) => {
                    const isDominant = w > 0 && w >= regimePeaks[r] - 0.0005;
                    const isActive   = currentRegime === r;
                    const b = REGIME_BADGE[r];
                    return (
                      <span key={r} style={{
                        fontSize: "12px", fontFamily: DATA_FONT,
                        fontWeight: isDominant ? 700 : 400,
                        color: isDominant
                          ? b.color
                          : isActive
                            ? "rgba(255,255,255,0.5)"
                            : "rgba(255,255,255,0.25)",
                      }}>
                        {w > 0 ? `${(w * 100).toFixed(0)}%` : "—"}
                      </span>
                    );
                  })}
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* ── Section 3: Opus Observations ─────────────────────────────── */}
      <div style={CARD}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
          <SectionLabel>Learned Observations</SectionLabel>

          {observations.length > 0 && (
            <span style={{
              fontSize: "9px", padding: "1px 7px", borderRadius: "3px",
              background: "rgba(167,139,250,0.12)", color: "#a78bfa",
              border: "1px solid rgba(167,139,250,0.22)",
              fontFamily: PROSE_FONT, fontWeight: 700, letterSpacing: "0.06em",
            }}>
              {observations.length}
            </span>
          )}

          <Rule />

          <span style={{
            fontSize: "9px", fontFamily: PROSE_FONT, fontWeight: 600,
            letterSpacing: "0.1em", color: "rgba(255,255,255,0.13)",
          }}>
            OPUS-CURATED
          </span>
        </div>

        {observations.length === 0 ? (
          <p style={{
            margin: 0, fontSize: "11px", fontFamily: PROSE_FONT, lineHeight: 1.65,
            color: "rgba(255,255,255,0.22)", fontStyle: "italic" as const,
          }}>
            No observations yet. After each execute cycle with trades, Opus reviews prior decisions and surfaces falsifiable statistical patterns here.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {[...observations]
              .sort((a, b) => (b.sample_size ?? 0) - (a.sample_size ?? 0))
              .map(obs => {
                const rk    = (obs.regime ?? "ALL").toUpperCase();
                const badge = REGIME_BADGE[rk] ?? REGIME_BADGE.ALL;
                const wr    = obs.win_rate ?? 0;
                const winColor = wr >= 0.6 ? "#34d399" : wr >= 0.45 ? "#fbbf24" : "#f87171";
                return (
                  <div key={obs.id} style={{
                    padding: "11px 13px",
                    background: "rgba(255,255,255,0.016)",
                    border: "1px solid rgba(255,255,255,0.05)",
                    borderRadius: "6px",
                  }}>
                    {/* Meta row */}
                    <div style={{
                      display: "flex", alignItems: "center", gap: "8px",
                      marginBottom: "7px", flexWrap: "wrap" as const,
                    }}>
                      <span style={{
                        fontSize: "9px", padding: "2px 7px", borderRadius: "3px",
                        background: badge.bg, color: badge.color, border: badge.border,
                        fontFamily: PROSE_FONT, fontWeight: 700, letterSpacing: "0.08em",
                        textTransform: "uppercase" as const,
                      }}>
                        {obs.regime}
                      </span>
                      <span style={{ fontSize: "10px", fontFamily: DATA_FONT, color: "rgba(255,255,255,0.3)" }}>
                        n={obs.sample_size}
                      </span>
                      <span style={{ fontSize: "10px", fontFamily: DATA_FONT, color: winColor, fontWeight: 600 }}>
                        {(wr * 100).toFixed(0)}% win
                      </span>
                      {obs.evidence_tickers && obs.evidence_tickers.length > 0 && (
                        <span style={{ fontSize: "10px", fontFamily: DATA_FONT, color: "rgba(255,255,255,0.2)" }}>
                          {obs.evidence_tickers.slice(0, 5).join(" · ")}
                        </span>
                      )}
                    </div>
                    {/* Claim */}
                    <p style={{
                      margin: 0, fontSize: "11px", fontFamily: PROSE_FONT,
                      color: "rgba(220,220,238,0.62)", lineHeight: 1.65,
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
