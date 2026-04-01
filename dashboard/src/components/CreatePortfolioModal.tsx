/** Create Portfolio Modal — 2-step AI-driven flow. */

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

export default function CreatePortfolioModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const setActivePortfolio = usePortfolioStore((s) => s.setPortfolio);

  // Step 1 state
  const [step, setStep] = useState(1);
  const [capital, setCapital] = useState(1_000_000);
  const [dna, setDna] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Step 2 state
  const [suggestion, setSuggestion] = useState<SuggestConfigResponse | null>(null);
  const [editedName, setEditedName] = useState("");

  // Suggest config mutation
  const suggestMutation = useMutation({
    mutationFn: () => api.suggestConfig({ strategy_dna: dna, starting_capital: capital }),
    onSuccess: (data) => {
      setSuggestion(data);
      setEditedName(data.name);
      setError(null);
      setStep(2);
    },
    onError: (err: Error) => {
      setError(err.message || "Failed to generate config");
    },
  });

  // Create portfolio mutation
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
          stop_loss_pct: suggestion.stop_loss_pct,
          take_profit_pct: suggestion.take_profit_pct,
          risk_per_trade_pct: suggestion.risk_per_trade_pct,
          max_position_pct: suggestion.max_position_pct,
          max_positions: suggestion.max_positions,
          etf_sources: suggestion.etfs,
        },
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      setActivePortfolio(data.portfolio.id);
      onClose();
    },
    onError: (err: Error) => {
      setError(err.message || "Failed to create portfolio");
    },
  });

  const labelStyle: React.CSSProperties = {
    fontSize: "9px",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.10em",
    color: "var(--text-0)",
    marginBottom: "6px",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    fontSize: "13px",
    fontFamily: "var(--font-mono)",
    background: "var(--void)",
    border: "1px solid var(--border-1)",
    borderRadius: "6px",
    color: "var(--text-3)",
    outline: "none",
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
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(4px)",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "480px",
          maxHeight: "85vh",
          overflowY: "auto",
          background: "var(--surface-0)",
          border: "1px solid var(--border-1)",
          borderRadius: "12px",
          padding: "24px",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <h2 style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-4)", margin: 0 }}>
            {step === 1 ? "New Portfolio" : "Review & Create"}
          </h2>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--text-1)",
              fontSize: "18px",
              cursor: "pointer",
              padding: "4px",
            }}
          >
            ×
          </button>
        </div>

        {step === 1 && (
          <>
            {/* Starting Capital */}
            <div style={{ marginBottom: "16px" }}>
              <p style={labelStyle}>Starting Capital</p>
              <input
                type="number"
                value={capital}
                onChange={(e) => setCapital(Number(e.target.value))}
                style={inputStyle}
              />
            </div>

            {/* Strategy DNA */}
            <div style={{ marginBottom: "20px" }}>
              <p style={labelStyle}>Strategy DNA</p>
              <textarea
                value={dna}
                onChange={(e) => setDna(e.target.value)}
                rows={7}
                placeholder="Describe your investment thesis..."
                style={{
                  ...inputStyle,
                  resize: "vertical",
                  fontFamily: "var(--font-sans)",
                  lineHeight: 1.5,
                }}
              />
            </div>

            {/* Error */}
            {error && (
              <p style={{ fontSize: "11px", color: "var(--red)", marginBottom: "12px" }}>{error}</p>
            )}

            {/* Next button */}
            <button
              onClick={() => {
                setError(null);
                suggestMutation.mutate();
              }}
              disabled={!dna.trim() || suggestMutation.isPending}
              style={{
                width: "100%",
                padding: "10px 0",
                fontSize: "12px",
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                background: !dna.trim() || suggestMutation.isPending
                  ? "var(--surface-1)"
                  : "linear-gradient(135deg, #7c5cfc 0%, #9b7eff 100%)",
                color: !dna.trim() || suggestMutation.isPending ? "var(--text-0)" : "#fff",
                border: "none",
                borderRadius: "6px",
                cursor: !dna.trim() || suggestMutation.isPending ? "not-allowed" : "pointer",
              }}
            >
              {suggestMutation.isPending ? "Generating..." : "Next"}
            </button>
          </>
        )}

        {step === 2 && suggestion && (
          <>
            {/* Suggestion card */}
            <div
              style={{
                background: "var(--surface-1)",
                border: "1px solid var(--border-0)",
                borderRadius: "8px",
                padding: "16px",
                marginBottom: "16px",
              }}
            >
              <div style={{ marginBottom: "12px" }}>
                <p style={labelStyle}>Name</p>
                <input
                  type="text"
                  value={editedName}
                  onChange={(e) => setEditedName(e.target.value)}
                  style={{
                    ...inputStyle,
                    fontSize: "14px",
                    fontWeight: 600,
                    fontFamily: "var(--font-sans)",
                    padding: "7px 10px",
                  }}
                />
                <p style={{ fontSize: "10px", color: "var(--text-0)", marginTop: "4px", fontFamily: "var(--font-mono)" }}>
                  id: {slugify(editedName.trim() || suggestion.name)}
                </p>
              </div>

              <div style={{ display: "flex", gap: "24px", marginBottom: "12px" }}>
                <div>
                  <p style={labelStyle}>Universe</p>
                  <p style={{ fontSize: "12px", color: "var(--text-3)", margin: 0, fontWeight: 600 }}>
                    {suggestion.universe}
                  </p>
                </div>
                <div>
                  <p style={labelStyle}>Capital</p>
                  <p style={{ fontSize: "12px", color: "var(--text-3)", margin: 0, fontFamily: "var(--font-mono)" }}>
                    ${capital.toLocaleString()}
                  </p>
                </div>
              </div>

              <div style={{ marginBottom: "12px" }}>
                <p style={labelStyle}>ETFs</p>
                <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                  {suggestion.etfs.map((etf) => (
                    <span
                      key={etf}
                      style={{
                        fontSize: "10px",
                        fontWeight: 600,
                        fontFamily: "var(--font-mono)",
                        padding: "2px 6px",
                        borderRadius: "3px",
                        background: "rgba(124,92,252,0.15)",
                        color: "var(--accent-bright)",
                      }}
                    >
                      {etf}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <p style={labelStyle}>Risk</p>
                <p style={{ fontSize: "11px", color: "var(--text-2)", margin: 0, fontFamily: "var(--font-mono)" }}>
                  {suggestion.stop_loss_pct}% stop · {suggestion.take_profit_pct}% target · {suggestion.risk_per_trade_pct}% risk/trade · {suggestion.max_position_pct}% max pos · {suggestion.max_positions} max positions
                </p>
              </div>
            </div>

            {/* DNA preview */}
            <div style={{ marginBottom: "16px" }}>
              <p style={labelStyle}>Strategy DNA</p>
              <p
                style={{
                  fontSize: "11px",
                  color: "var(--text-2)",
                  lineHeight: 1.5,
                  fontStyle: "italic",
                  margin: 0,
                  maxHeight: "80px",
                  overflow: "hidden",
                }}
              >
                {dna}
              </p>
            </div>

            {/* Error */}
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
                  background: "var(--surface-1)",
                  color: "var(--text-2)",
                  border: "1px solid var(--border-0)",
                  borderRadius: "6px",
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
                    ? "var(--surface-1)"
                    : "linear-gradient(135deg, #7c5cfc 0%, #9b7eff 100%)",
                  color: createMutation.isPending ? "var(--text-0)" : "#fff",
                  border: "none",
                  borderRadius: "6px",
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
