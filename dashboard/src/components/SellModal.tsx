/** SellModal — full or partial sell with share count input + trade preview. */

import { useState, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Position } from "../lib/types";
import { useUIStore, usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";

interface SellModalProps {
  pos: Position;
  onClose: () => void;
}

export default function SellModal({ pos, onClose }: SellModalProps) {
  const queryClient = useQueryClient();
  const selectPosition = useUIStore((s) => s.selectPosition);
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  const [shares, setShares] = useState(String(pos.shares));
  const [selling, setSelling] = useState(false);
  const [result, setResult] = useState<{ message: string; success: boolean } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const numShares = Math.floor(Number(shares) || 0);
  const isAll = numShares >= pos.shares;
  const isValid = numShares > 0 && numShares <= pos.shares;
  const sellValue = numShares * pos.current_price;
  const sellPnl = numShares * (pos.current_price - pos.avg_cost_basis);
  const sellPnlPct = pos.avg_cost_basis > 0
    ? ((pos.current_price - pos.avg_cost_basis) / pos.avg_cost_basis) * 100
    : 0;

  useEffect(() => {
    inputRef.current?.select();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const handleSell = async () => {
    if (!isValid) return;
    setSelling(true);
    try {
      const res = await api.sellPosition(portfolioId, pos.ticker, isAll ? undefined : numShares);
      setResult({ message: res.message, success: true });
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
      queryClient.invalidateQueries({ queryKey: ["chartData"] });
      setTimeout(() => {
        onClose();
        if (isAll) selectPosition(null);
      }, 2000);
    } catch (e) {
      setResult({ message: e instanceof Error ? e.message : "Sell failed", success: false });
    } finally {
      setSelling(false);
    }
  };

  const pnlColor = sellPnl >= 0 ? "var(--green)" : "var(--red)";

  const presetPcts = [25, 50, 75, 100] as const;

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: "rgba(2,6,23,0.6)", backdropFilter: "blur(8px)" }}
      onClick={onClose}
    >
      <div
        className="rounded-xl p-5 w-full"
        style={{
          maxWidth: "380px",
          background: "var(--bg-surface)",
          border: "1px solid var(--border-hover)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "0 24px 48px rgba(0,0,0,0.5)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span
              style={{ fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 600, color: "var(--text-primary)" }}
            >
              Sell {pos.ticker}
            </span>
            <span
              style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", fontWeight: 600, color: pnlColor }}
            >
              {sellPnlPct >= 0 ? "+" : ""}{sellPnlPct.toFixed(1)}%
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-xs rounded px-2 py-1 transition-colors"
            style={{ color: "var(--text-dim)", border: "1px solid var(--border)" }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-dim)"; }}
          >
            ESC
          </button>
        </div>

        {result ? (
          <div
            className="rounded-lg p-4 text-center"
            style={{
              background: result.success ? "var(--green-dim)" : "var(--red-dim)",
              border: `1px solid ${result.success ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`,
            }}
          >
            <span
              className="text-sm font-medium"
              style={{ fontFamily: "var(--font-mono)", color: result.success ? "var(--green)" : "var(--red)" }}
            >
              {result.message}
            </span>
          </div>
        ) : (
          <>
            {/* Share count input */}
            <div className="mb-3">
              <label
                className="block mb-1.5"
                style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)" }}
              >
                Shares to sell
              </label>
              <div className="flex gap-2">
                <input
                  ref={inputRef}
                  type="number"
                  min={1}
                  max={pos.shares}
                  value={shares}
                  onChange={(e) => setShares(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSell(); }}
                  className="flex-1 text-sm rounded px-3 py-2 outline-none transition-colors"
                  style={{
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                    fontFamily: "var(--font-mono)",
                    color: "var(--text-primary)",
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
                />
                <span
                  className="flex items-center text-xs"
                  style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}
                >
                  / {pos.shares.toLocaleString()}
                </span>
              </div>
            </div>

            {/* Preset buttons */}
            <div className="flex gap-1.5 mb-4">
              {presetPcts.map((pct) => {
                const pctShares = pct === 100 ? pos.shares : Math.floor(pos.shares * pct / 100);
                const active = numShares === pctShares;
                return (
                  <button
                    key={pct}
                    onClick={() => setShares(String(pctShares))}
                    className="flex-1 py-1.5 rounded text-xs font-semibold transition-colors"
                    style={
                      active
                        ? {
                            background: pct === 100 ? "var(--red-dim)" : "var(--accent-dim)",
                            border: `1px solid ${pct === 100 ? "rgba(239,68,68,0.2)" : "rgba(139,92,246,0.2)"}`,
                            color: pct === 100 ? "var(--red)" : "var(--accent)",
                          }
                        : {
                            background: "var(--bg-elevated)",
                            border: "1px solid var(--border)",
                            color: "var(--text-secondary)",
                          }
                    }
                  >
                    {pct === 100 ? "ALL" : `${pct}%`}
                  </button>
                );
              })}
            </div>

            {/* Trade preview */}
            {isValid && (
              <div
                className="rounded-lg p-3 mb-4 space-y-1.5"
                style={{ background: "var(--bg-void)", border: "1px solid var(--border)" }}
              >
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-secondary)" }}>Shares</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                    {numShares.toLocaleString()}{isAll ? "" : ` of ${pos.shares.toLocaleString()}`}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-secondary)" }}>Price</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                    ${pos.current_price.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-secondary)" }}>Total Value</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                    ${sellValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div
                  className="flex justify-between text-xs pt-1.5 mt-1.5"
                  style={{ borderTop: "1px solid var(--border)" }}
                >
                  <span style={{ color: "var(--text-secondary)" }}>P&L</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: pnlColor }}>
                    {sellPnl >= 0 ? "+" : ""}${sellPnl.toLocaleString(undefined, { maximumFractionDigits: 2 })} ({sellPnlPct >= 0 ? "+" : ""}{sellPnlPct.toFixed(1)}%)
                  </span>
                </div>
                {!isAll && (
                  <div className="flex justify-between text-xs" style={{ color: "var(--text-secondary)" }}>
                    <span>Remaining</span>
                    <span style={{ fontFamily: "var(--font-mono)" }}>
                      {(pos.shares - numShares).toLocaleString()} shares · ${((pos.shares - numShares) * pos.current_price).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2">
              <button
                onClick={onClose}
                className="flex-1 py-2 rounded text-xs font-semibold transition-colors"
                style={{
                  background: "var(--bg-elevated)",
                  color: "var(--text-secondary)",
                  border: "1px solid var(--border)",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSell}
                disabled={!isValid || selling}
                className="flex-1 py-2 rounded text-xs font-semibold transition-colors disabled:opacity-40"
                style={{
                  background: "var(--red-dim)",
                  color: "var(--red)",
                  border: "1px solid rgba(239,68,68,0.2)",
                }}
                onMouseEnter={(e) => {
                  if (!e.currentTarget.disabled) {
                    e.currentTarget.style.background = "rgba(239,68,68,0.12)";
                    e.currentTarget.style.borderColor = "rgba(239,68,68,0.35)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "var(--red-dim)";
                  e.currentTarget.style.borderColor = "rgba(239,68,68,0.2)";
                }}
              >
                {selling ? "Selling..." : isAll ? `Sell All ${pos.ticker}` : `Sell ${numShares.toLocaleString()} ${pos.ticker}`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
