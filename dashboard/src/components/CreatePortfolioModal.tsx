/** Create Portfolio Modal — redesigned 2-step AI-driven flow with DNA builder. */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import type { SuggestConfigResponse } from "../lib/types";

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function formatCapital(val: number): string {
  return val.toLocaleString("en-US");
}

// ── DNA Builder options ──────────────────────────────────────────────────────

const STYLES = ["Momentum", "Value", "Growth", "Income", "Contrarian", "Thematic"] as const;
const AGGRESSION = ["Conservative", "Moderate", "Aggressive", "YOLO"] as const;
const CAPS = [
  { label: "Micro", range: "$50M-$2B" },
  { label: "Small", range: "$300M-$5B" },
  { label: "Mid", range: "$500M-$15B" },
  { label: "Large", range: "$5B+" },
  { label: "All", range: "All caps" },
] as const;
const HOLDS = ["Day Trade", "Swing (1-5d)", "Position (1-4w)", "Long-term"] as const;
const CONCENTRATIONS = [
  { label: "Diversified", detail: "10+" },
  { label: "Focused", detail: "5-10" },
  { label: "Concentrated", detail: "1-4" },
] as const;
const SECTORS = [
  "Technology", "Healthcare", "Energy", "Industrials", "Financial Services",
  "Consumer Cyclical", "Consumer Defensive", "Basic Materials",
  "Real Estate", "Utilities", "Communication Services",
] as const;

function buildObjective(style: string | null, aggression: string | null): string {
  const map: Record<string, Record<string, string>> = {
    Momentum: {
      Conservative: "Steady trend-following with tight risk management",
      Moderate: "Capture momentum swings with balanced risk/reward",
      Aggressive: "Maximum short-term alpha from momentum breakouts",
      YOLO: "Full send on the strongest movers — ride or die",
    },
    Value: {
      Conservative: "Steady compounding with downside protection",
      Moderate: "Buy quality at a discount, patient accumulation",
      Aggressive: "Deep value contrarian bets with asymmetric upside",
      YOLO: "Distressed turnarounds — buy the blood",
    },
    Growth: {
      Conservative: "Quality growth compounders with proven revenue",
      Moderate: "High-growth companies at reasonable valuations",
      Aggressive: "Hypergrowth names — revenue acceleration over profitability",
      YOLO: "Pre-revenue rockets with 10x potential",
    },
    Income: {
      Conservative: "Stable dividends with capital preservation",
      Moderate: "High yield with moderate growth potential",
      Aggressive: "Maximum yield — chase the highest payers",
      YOLO: "Leveraged income plays and special dividends",
    },
    Contrarian: {
      Conservative: "Carefully selected out-of-favor quality names",
      Moderate: "Buy what everyone else is selling — with discipline",
      Aggressive: "Catch falling knives that are about to bounce",
      YOLO: "Maximum pain trades — peak fear is the entry",
    },
    Thematic: {
      Conservative: "Broad exposure to a structural theme",
      Moderate: "Focused thematic picks with quality filters",
      Aggressive: "Pure-play bets on an emerging theme",
      YOLO: "All-in on a single conviction theme",
    },
  };
  return map[style ?? "Momentum"]?.[aggression ?? "Moderate"] ?? "Generate alpha through disciplined stock selection";
}

function assembleDna(
  style: string | null,
  aggression: string | null,
  cap: string | null,
  hold: string | null,
  concentration: string | null,
  sectors: string[],
): string {
  const lines: string[] = [];
  if (style) lines.push(`Style: ${style}${aggression ? ` | Aggression: ${aggression}` : ""}`);
  else if (aggression) lines.push(`Aggression: ${aggression}`);
  if (cap) {
    const capObj = CAPS.find((c) => c.label === cap);
    lines.push(`Cap: ${cap} (${capObj?.range ?? ""})`);
  }
  if (hold) lines.push(`Hold: ${hold}`);
  if (concentration) {
    const concObj = CONCENTRATIONS.find((c) => c.label === concentration);
    lines.push(`Concentration: ${concObj?.detail ?? ""} positions`);
  }
  if (sectors.length > 0) lines.push(`Sectors: ${sectors.join(", ")}`);
  lines.push(`Objective: ${buildObjective(style, aggression)}`);
  return lines.join("\n");
}

// ── Chip component ───────────────────────────────────────────────────────────

function Chip({
  label,
  selected,
  onClick,
  small,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
  small?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: small ? "2px 8px" : "4px 10px",
        fontSize: small ? "9px" : "10px",
        fontWeight: 600,
        letterSpacing: "0.04em",
        borderRadius: "4px",
        cursor: "pointer",
        transition: "all 0.15s",
        border: selected ? "1px solid rgba(139,92,246,0.2)" : "1px solid var(--border)",
        background: selected ? "var(--accent-dim)" : "var(--bg-elevated)",
        color: selected ? "var(--accent)" : "var(--text-secondary)",
      }}
    >
      {label}
    </button>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export default function CreatePortfolioModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const setActivePortfolio = usePortfolioStore((s) => s.setPortfolio);

  // Step state
  const [step, setStep] = useState(1);
  const [capital, setCapital] = useState(1_000_000);
  const [dna, setDna] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Step 2 state
  const [suggestion, setSuggestion] = useState<SuggestConfigResponse | null>(null);
  const [editedName, setEditedName] = useState("");
  const [editedStopLoss, setEditedStopLoss] = useState(0);
  const [editedTakeProfit, setEditedTakeProfit] = useState(0);
  const [editedRiskPerTrade, setEditedRiskPerTrade] = useState(0);
  const [editedMaxPosition, setEditedMaxPosition] = useState(0);
  const [editedMaxPositions, setEditedMaxPositions] = useState(0);
  const [editedRefinementEnabled, setEditedRefinementEnabled] = useState(false);
  const [editedRefinementPrompt, setEditedRefinementPrompt] = useState("");
  const [editedSectors, setEditedSectors] = useState<string[]>([]);
  const [editedIndustries, setEditedIndustries] = useState<string[]>([]);
  const [showDna, setShowDna] = useState(false);

  // DNA Builder state
  const [showBuilder, setShowBuilder] = useState(false);
  const [bStyle, setBStyle] = useState<string | null>(null);
  const [bAggression, setBAggression] = useState<string | null>(null);
  const [bCap, setBCap] = useState<string | null>(null);
  const [bHold, setBHold] = useState<string | null>(null);
  const [bConcentration, setBConcentration] = useState<string | null>(null);
  const [bSectors, setBSectors] = useState<string[]>([]);

  // Mutations
  const randomMutation = useMutation({
    mutationFn: () => api.randomDna(),
    onSuccess: (data) => setDna(data.dna),
  });

  const suggestMutation = useMutation({
    mutationFn: () => api.suggestConfig({ strategy_dna: dna, starting_capital: capital }),
    onSuccess: (data) => {
      setSuggestion(data);
      setEditedName(data.name);
      setEditedStopLoss(data.stop_loss_pct);
      setEditedTakeProfit(data.take_profit_pct);
      setEditedRiskPerTrade(data.risk_per_trade_pct);
      setEditedMaxPosition(data.max_position_pct);
      setEditedMaxPositions(data.max_positions);
      setEditedRefinementEnabled(data.ai_refinement?.enabled ?? false);
      setEditedRefinementPrompt(data.ai_refinement?.prompt ?? "");
      setEditedSectors(data.screener?.sectors ?? []);
      setEditedIndustries(data.screener?.industries ?? []);
      setError(null);
      setStep(2);
    },
    onError: (err: Error) => setError(err.message || "Failed to generate config"),
  });

  const createMutation = useMutation({
    mutationFn: () => {
      if (!suggestion) throw new Error("No suggestion");
      const finalName = editedName.trim() || suggestion.name;
      return api.createPortfolio({
        id: slugify(finalName),
        name: finalName,
        universe: suggestion.universe,
        starting_capital: capital,
        ai_driven: true,
        strategy_dna: dna,
        ai_config: {
          stop_loss_pct: editedStopLoss,
          take_profit_pct: editedTakeProfit,
          risk_per_trade_pct: editedRiskPerTrade,
          max_position_pct: editedMaxPosition,
          max_positions: editedMaxPositions,
          etf_sources: suggestion.etfs,
          screener: {
            ...suggestion.screener,
            sectors: editedSectors,
            industries: editedIndustries,
          },
          ai_refinement: {
            enabled: editedRefinementEnabled,
            prompt: editedRefinementPrompt,
          },
        },
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      setActivePortfolio(data.portfolio.id);
      onClose();
    },
    onError: (err: Error) => setError(err.message || "Failed to create portfolio"),
  });

  const labelStyle: React.CSSProperties = {
    fontSize: "11px",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "var(--text-dim)",
    marginBottom: "6px",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    fontSize: "13px",
    fontFamily: "var(--font-mono)",
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    color: "var(--text-primary)",
    outline: "none",
    boxSizing: "border-box",
  };

  const smallInputStyle: React.CSSProperties = {
    ...inputStyle,
    padding: "6px 8px",
    fontSize: "12px",
    textAlign: "center" as const,
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(2,6,23,0.6)",
        backdropFilter: "blur(8px)",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        width: "520px",
        maxHeight: "90vh",
        overflowY: "auto",
        background: "var(--bg-surface)",
        border: "1px solid var(--border-hover)",
        borderRadius: "var(--radius-lg)",
        padding: "24px",
        boxShadow: "0 24px 48px rgba(0,0,0,0.5)",
      }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <h2 style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
              {step === 1 ? "New Portfolio" : "Review & Create"}
            </h2>
            {/* Step indicators */}
            <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
              <span style={{
                width: "20px", height: "20px", borderRadius: "50%",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "10px", fontWeight: 700,
                background: step === 1 ? "var(--accent)" : "var(--bg-elevated)",
                color: step === 1 ? "#fff" : "var(--text-dim)",
                border: step === 1 ? "none" : "1px solid var(--border)",
              }}>1</span>
              <span style={{ width: "16px", height: "1px", background: "var(--border)" }} />
              <span style={{
                width: "20px", height: "20px", borderRadius: "50%",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "10px", fontWeight: 700,
                background: step === 2 ? "var(--accent)" : "var(--bg-elevated)",
                color: step === 2 ? "#fff" : "var(--text-dim)",
                border: step === 2 ? "none" : "1px solid var(--border)",
              }}>2</span>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "none",
            border: "none",
            color: "var(--text-muted)",
            fontSize: "18px",
            cursor: "pointer",
            padding: "4px",
          }}>×</button>
        </div>

        {/* ═══════════ STEP 1 ═══════════ */}
        {step === 1 && (
          <>
            {/* Starting Capital */}
            <div style={{ marginBottom: "16px" }}>
              <p style={labelStyle}>Starting Capital</p>
              <div style={{ position: "relative" }}>
                <span style={{
                  position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)",
                  color: "var(--text-secondary)", fontSize: "13px", fontFamily: "var(--font-mono)",
                }}>$</span>
                <input
                  type="text"
                  value={formatCapital(capital)}
                  onChange={(e) => {
                    const raw = e.target.value.replace(/[^0-9]/g, "");
                    setCapital(Number(raw) || 0);
                  }}
                  style={{ ...inputStyle, paddingLeft: "24px" }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
                />
              </div>
            </div>

            {/* Strategy DNA */}
            <div style={{ marginBottom: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <p style={{ ...labelStyle, marginBottom: 0 }}>Strategy DNA</p>
                <div style={{ display: "flex", gap: "6px" }}>
                  <button
                    onClick={() => randomMutation.mutate()}
                    disabled={randomMutation.isPending}
                    style={{
                      padding: "3px 10px",
                      fontSize: "9px",
                      fontWeight: 600,
                      borderRadius: "4px",
                      cursor: "pointer",
                      border: "1px solid var(--border)",
                      background: "var(--bg-elevated)",
                      color: randomMutation.isPending ? "var(--text-dim)" : "var(--text-secondary)",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {randomMutation.isPending ? "cooking..." : "🎲 Random"}
                  </button>
                  <button
                    onClick={() => setShowBuilder(!showBuilder)}
                    style={{
                      padding: "3px 10px",
                      fontSize: "9px",
                      fontWeight: 600,
                      borderRadius: "4px",
                      cursor: "pointer",
                      border: showBuilder ? "1px solid rgba(139,92,246,0.2)" : "1px solid var(--border)",
                      background: showBuilder ? "var(--accent-dim)" : "var(--bg-elevated)",
                      color: showBuilder ? "var(--accent)" : "var(--text-secondary)",
                      letterSpacing: "0.04em",
                    }}
                  >
                    🔧 Builder
                  </button>
                </div>
              </div>

              {/* DNA Builder Panel */}
              {showBuilder && (
                <div style={{
                  background: "var(--bg-void)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  padding: "12px",
                  marginBottom: "8px",
                }}>
                  {/* Style */}
                  <div style={{ marginBottom: "8px" }}>
                    <p style={{ ...labelStyle, fontSize: "9px", marginBottom: "4px" }}>Style</p>
                    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                      {STYLES.map((s) => (
                        <Chip key={s} label={s} selected={bStyle === s}
                          onClick={() => setBStyle(bStyle === s ? null : s)} />
                      ))}
                    </div>
                  </div>

                  {/* Aggression */}
                  <div style={{ marginBottom: "8px" }}>
                    <p style={{ ...labelStyle, fontSize: "9px", marginBottom: "4px" }}>Aggression</p>
                    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                      {AGGRESSION.map((a) => (
                        <Chip key={a} label={a} selected={bAggression === a}
                          onClick={() => setBAggression(bAggression === a ? null : a)} />
                      ))}
                    </div>
                  </div>

                  {/* Cap + Hold */}
                  <div style={{ display: "flex", gap: "16px", marginBottom: "8px" }}>
                    <div style={{ flex: 1 }}>
                      <p style={{ ...labelStyle, fontSize: "9px", marginBottom: "4px" }}>Market Cap</p>
                      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                        {CAPS.map((c) => (
                          <Chip key={c.label} label={c.label} selected={bCap === c.label} small
                            onClick={() => setBCap(bCap === c.label ? null : c.label)} />
                        ))}
                      </div>
                    </div>
                    <div style={{ flex: 1 }}>
                      <p style={{ ...labelStyle, fontSize: "9px", marginBottom: "4px" }}>Hold Period</p>
                      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                        {HOLDS.map((h) => (
                          <Chip key={h} label={h} selected={bHold === h} small
                            onClick={() => setBHold(bHold === h ? null : h)} />
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Concentration */}
                  <div style={{ marginBottom: "8px" }}>
                    <p style={{ ...labelStyle, fontSize: "9px", marginBottom: "4px" }}>Concentration</p>
                    <div style={{ display: "flex", gap: "4px" }}>
                      {CONCENTRATIONS.map((c) => (
                        <Chip key={c.label} label={`${c.label} (${c.detail})`}
                          selected={bConcentration === c.label}
                          onClick={() => setBConcentration(bConcentration === c.label ? null : c.label)} />
                      ))}
                    </div>
                  </div>

                  {/* Sectors */}
                  <div style={{ marginBottom: "10px" }}>
                    <p style={{ ...labelStyle, fontSize: "9px", marginBottom: "4px" }}>Sectors</p>
                    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                      {SECTORS.map((s) => (
                        <Chip key={s} label={s} small
                          selected={bSectors.includes(s)}
                          onClick={() => setBSectors(
                            bSectors.includes(s) ? bSectors.filter((x) => x !== s) : [...bSectors, s]
                          )} />
                      ))}
                    </div>
                  </div>

                  {/* Build DNA button */}
                  <button
                    onClick={() => {
                      setDna(assembleDna(bStyle, bAggression, bCap, bHold, bConcentration, bSectors));
                      setShowBuilder(false);
                    }}
                    disabled={!bStyle && !bAggression && !bCap}
                    style={{
                      width: "100%",
                      padding: "6px 0",
                      fontSize: "10px",
                      fontWeight: 700,
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                      background: (!bStyle && !bAggression && !bCap)
                        ? "var(--bg-elevated)" : "var(--accent-dim)",
                      color: (!bStyle && !bAggression && !bCap)
                        ? "var(--text-dim)" : "var(--accent)",
                      border: "1px solid var(--border)",
                      borderRadius: "4px",
                      cursor: (!bStyle && !bAggression && !bCap) ? "not-allowed" : "pointer",
                    }}
                  >
                    Build DNA
                  </button>
                </div>
              )}

              <textarea
                value={dna}
                onChange={(e) => setDna(e.target.value)}
                rows={7}
                placeholder="Describe your investment thesis, or use the builder above..."
                style={{
                  ...inputStyle,
                  resize: "vertical",
                  fontFamily: "var(--font-mono)",
                  lineHeight: 1.5,
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
              />
            </div>

            {error && (
              <p style={{ fontSize: "11px", color: "var(--red)", marginBottom: "12px" }}>{error}</p>
            )}

            {/* Generate Config button */}
            <button
              onClick={() => { setError(null); suggestMutation.mutate(); }}
              disabled={!dna.trim() || suggestMutation.isPending}
              style={{
                width: "100%",
                padding: "12px 0",
                fontSize: "12px",
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                background: !dna.trim() || suggestMutation.isPending
                  ? "var(--bg-elevated)"
                  : "var(--accent-dim)",
                color: !dna.trim() || suggestMutation.isPending ? "var(--text-dim)" : "var(--accent)",
                border: !dna.trim() || suggestMutation.isPending
                  ? "1px solid var(--border)"
                  : "1px solid rgba(139,92,246,0.2)",
                borderRadius: "var(--radius)",
                cursor: !dna.trim() || suggestMutation.isPending ? "not-allowed" : "pointer",
              }}
            >
              {suggestMutation.isPending ? (
                <span className="animate-pulse-slow">GScott is analyzing your strategy...</span>
              ) : (
                "Generate Config"
              )}
            </button>
          </>
        )}

        {/* ═══════════ STEP 2 ═══════════ */}
        {step === 2 && suggestion && (
          <>
            {/* Name + Universe */}
            <div style={{ marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                <p style={{ ...labelStyle, marginBottom: 0, flex: 1 }}>Name</p>
                <span style={{
                  fontSize: "9px",
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: "3px",
                  letterSpacing: "0.08em",
                  background: "var(--accent-dim)",
                  color: "var(--accent)",
                  border: "1px solid rgba(139,92,246,0.2)",
                  textTransform: "uppercase",
                }}>
                  {suggestion.universe}
                </span>
              </div>
              <input
                type="text"
                value={editedName}
                onChange={(e) => setEditedName(e.target.value)}
                style={{ ...inputStyle, fontSize: "14px", fontWeight: 600, fontFamily: "var(--font-sans)" }}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
              />
              <p style={{ fontSize: "10px", color: "var(--text-dim)", marginTop: "4px", fontFamily: "var(--font-mono)" }}>
                id: {slugify(editedName.trim() || suggestion.name)}
              </p>
            </div>

            {/* Universe & Discovery */}
            {(editedSectors.length > 0 || editedIndustries.length > 0) && (
              <div style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                padding: "12px",
                marginBottom: "16px",
              }}>
                <p style={labelStyle}>Universe Filters</p>

                {editedSectors.length > 0 && (
                  <div style={{ marginBottom: "8px" }}>
                    <p style={{ ...labelStyle, fontSize: "9px", marginBottom: "4px" }}>Sectors</p>
                    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                      {editedSectors.map((s) => (
                        <span key={s} style={{
                          fontSize: "10px",
                          fontWeight: 600,
                          padding: "2px 8px",
                          borderRadius: "3px",
                          background: "var(--accent-dim)",
                          color: "var(--accent)",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          border: "1px solid rgba(139,92,246,0.2)",
                        }}>
                          {s}
                          <button onClick={() => setEditedSectors(editedSectors.filter((x) => x !== s))}
                            style={{
                              background: "none",
                              border: "none",
                              color: "var(--text-muted)",
                              cursor: "pointer",
                              fontSize: "10px",
                              padding: 0,
                              lineHeight: 1,
                            }}>×</button>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {editedIndustries.length > 0 && (
                  <div>
                    <p style={{ ...labelStyle, fontSize: "9px", marginBottom: "4px" }}>Industries</p>
                    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                      {editedIndustries.map((ind) => (
                        <span key={ind} style={{
                          fontSize: "9px",
                          fontWeight: 500,
                          padding: "2px 6px",
                          borderRadius: "3px",
                          background: "var(--bg-void)",
                          color: "var(--text-secondary)",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          border: "1px solid var(--border)",
                        }}>
                          {ind}
                          <button onClick={() => setEditedIndustries(editedIndustries.filter((x) => x !== ind))}
                            style={{
                              background: "none",
                              border: "none",
                              color: "var(--text-dim)",
                              cursor: "pointer",
                              fontSize: "9px",
                              padding: 0,
                              lineHeight: 1,
                            }}>×</button>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* AI Refinement toggle */}
            <div style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: "12px",
              marginBottom: "16px",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: editedRefinementEnabled ? "8px" : 0 }}>
                <p style={{ ...labelStyle, marginBottom: 0 }}>Claude Universe Refinement</p>
                <button
                  onClick={() => setEditedRefinementEnabled(!editedRefinementEnabled)}
                  style={{
                    width: "36px",
                    height: "20px",
                    borderRadius: "10px",
                    cursor: "pointer",
                    border: "none",
                    position: "relative",
                    transition: "background 0.2s",
                    background: editedRefinementEnabled ? "var(--accent)" : "var(--bg-void)",
                  }}
                >
                  <span style={{
                    position: "absolute",
                    top: "2px",
                    left: editedRefinementEnabled ? "18px" : "2px",
                    width: "16px",
                    height: "16px",
                    borderRadius: "50%",
                    background: "#fff",
                    transition: "left 0.2s",
                  }} />
                </button>
              </div>
              {editedRefinementEnabled && (
                <textarea
                  value={editedRefinementPrompt}
                  onChange={(e) => setEditedRefinementPrompt(e.target.value)}
                  rows={3}
                  placeholder="Describe what to include/exclude from screener results..."
                  style={{
                    ...inputStyle,
                    fontSize: "11px",
                    resize: "vertical",
                    fontFamily: "var(--font-mono)",
                    lineHeight: 1.4,
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
                />
              )}
            </div>

            {/* Risk & Sizing */}
            <div style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: "12px",
              marginBottom: "16px",
            }}>
              <p style={labelStyle}>Risk & Sizing</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px" }}>
                {[
                  { label: "Stop Loss %", value: editedStopLoss, set: setEditedStopLoss },
                  { label: "Take Profit %", value: editedTakeProfit, set: setEditedTakeProfit },
                  { label: "Risk/Trade %", value: editedRiskPerTrade, set: setEditedRiskPerTrade },
                  { label: "Max Position %", value: editedMaxPosition, set: setEditedMaxPosition },
                  { label: "Max Positions", value: editedMaxPositions, set: setEditedMaxPositions },
                  { label: "Capital", value: capital, set: setCapital },
                ].map(({ label, value, set }) => (
                  <div key={label}>
                    <p style={{ ...labelStyle, fontSize: "9px", marginBottom: "3px" }}>{label}</p>
                    <input
                      type="number"
                      value={value}
                      onChange={(e) => set(Number(e.target.value))}
                      style={smallInputStyle}
                      onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                      onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Strategy DNA (collapsible) */}
            <div style={{ marginBottom: "16px" }}>
              <button
                onClick={() => setShowDna(!showDna)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontSize: "9px",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.10em",
                  color: "var(--text-dim)",
                  padding: 0,
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                }}
              >
                {showDna ? "▾" : "▸"} Strategy DNA
              </button>
              {showDna && (
                <p style={{
                  fontSize: "11px",
                  color: "var(--text-secondary)",
                  lineHeight: 1.5,
                  fontStyle: "italic",
                  margin: "6px 0 0",
                  whiteSpace: "pre-wrap",
                  fontFamily: "var(--font-mono)",
                  background: "var(--bg-void)",
                  padding: "10px 12px",
                  borderRadius: "var(--radius)",
                  border: "1px solid var(--border)",
                }}>
                  {dna}
                </p>
              )}
            </div>

            {error && (
              <p style={{ fontSize: "11px", color: "var(--red)", marginBottom: "12px" }}>{error}</p>
            )}

            {/* Buttons */}
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                onClick={() => { setStep(1); setError(null); }}
                style={{
                  flex: 1,
                  padding: "10px 0",
                  fontSize: "12px",
                  fontWeight: 600,
                  background: "var(--bg-elevated)",
                  color: "var(--text-secondary)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  cursor: "pointer",
                }}
              >
                Back
              </button>
              <button
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending}
                style={{
                  flex: 2,
                  padding: "10px 0",
                  fontSize: "12px",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  background: createMutation.isPending
                    ? "var(--bg-elevated)"
                    : "var(--accent-dim)",
                  color: createMutation.isPending ? "var(--text-dim)" : "var(--accent)",
                  border: createMutation.isPending
                    ? "1px solid var(--border)"
                    : "1px solid rgba(139,92,246,0.2)",
                  borderRadius: "var(--radius)",
                  cursor: createMutation.isPending ? "not-allowed" : "pointer",
                }}
              >
                {createMutation.isPending ? "Creating..." : "Create Portfolio"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
