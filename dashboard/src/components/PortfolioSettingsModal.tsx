/**
 * PortfolioSettingsModal — DNA editor for AI-driven portfolios.
 * Shows the strategy_dna textarea; saves via PUT /api/{id}/config.
 */

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolioStore } from "../lib/store";

export default function PortfolioSettingsModal({ onClose }: { onClose: () => void }) {
  const portfolioId = usePortfolioStore(s => s.activePortfolioId);
  const queryClient = useQueryClient();
  const [dna, setDna] = useState<string>("");
  const [saved, setSaved] = useState(false);

  const { data: rawConfig, isLoading } = useQuery({
    queryKey: ["portfolioConfig", portfolioId],
    queryFn: () => api.getPortfolioConfig(portfolioId),
    staleTime: 0,
  });

  useEffect(() => {
    if (rawConfig) {
      // strategy_dna may live at top level or nested under strategy
      const d =
        rawConfig.strategy_dna ??
        rawConfig.strategy?.strategy_dna ??
        "";
      setDna(d);
    }
  }, [rawConfig]);

  const mutation = useMutation({
    mutationFn: () => api.updatePortfolioConfig(portfolioId, { strategy_dna: dna }),
    onSuccess: () => {
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["portfolioConfig", portfolioId] });
      setTimeout(() => {
        setSaved(false);
        onClose();
      }, 1200);
    },
  });

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: "rgba(2,6,23,0.6)", backdropFilter: "blur(8px)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          width: "600px",
          background: "var(--bg-surface)",
          border: "1px solid var(--border-hover)",
          borderRadius: "var(--radius-lg)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 24px 48px rgba(0,0,0,0.5)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "14px 18px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-primary)" }}>
              Strategy DNA
            </div>
            <div style={{
              fontSize: "11px",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--text-dim)",
              marginTop: "2px",
            }}>
              Claude uses this thesis when picking and sizing positions.
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--text-muted)",
              fontSize: "18px",
              lineHeight: 1,
              padding: "2px 4px",
            }}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "16px 18px", background: "var(--bg-surface)" }}>
          {isLoading ? (
            <div
              style={{
                height: "160px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "12px",
                color: "var(--text-dim)",
              }}
              className="animate-pulse"
            >
              Loading…
            </div>
          ) : (
            <>
              <textarea
                value={dna}
                onChange={e => setDna(e.target.value)}
                rows={10}
                style={{
                  width: "100%",
                  resize: "vertical",
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  padding: "10px 12px",
                  fontSize: "12px",
                  fontFamily: "var(--font-mono)",
                  color: "var(--text-primary)",
                  lineHeight: 1.6,
                  outline: "none",
                  boxSizing: "border-box",
                  transition: "border-color 0.15s",
                }}
                onFocus={e => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                onBlur={e => { e.currentTarget.style.borderColor = "var(--border)"; }}
                placeholder="Describe the investment thesis — sectors, catalysts, macro view, position sizing philosophy…"
              />
              <div
                style={{
                  fontSize: "10px",
                  color: "var(--text-dim)",
                  textAlign: "right",
                  marginTop: "4px",
                }}
              >
                {dna.length} chars
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 18px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "var(--bg-elevated)",
          }}
        >
          <span style={{ fontSize: "10px", color: mutation.isError ? "var(--red)" : "var(--text-dim)" }}>
            {mutation.isError
              ? "Save failed — check API logs"
              : saved
              ? ""
              : "Takes effect on next ANALYZE run."}
          </span>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              style={{
                padding: "6px 14px",
                fontSize: "11px",
                fontWeight: 600,
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                color: "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || saved || isLoading}
              style={{
                padding: "6px 18px",
                fontSize: "11px",
                fontWeight: 700,
                background: saved ? "var(--green-dim)" : "var(--green-dim)",
                border: saved
                  ? "1px solid rgba(34,197,94,0.2)"
                  : "1px solid rgba(34,197,94,0.2)",
                borderRadius: "var(--radius)",
                color: "var(--green)",
                cursor: mutation.isPending ? "wait" : "pointer",
                opacity: mutation.isPending ? 0.7 : 1,
                transition: "background 0.2s",
              }}
            >
              {mutation.isPending ? "Saving…" : saved ? "Saved ✓" : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
