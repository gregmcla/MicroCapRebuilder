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
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className="rounded-xl p-5 w-full"
        style={{
          maxWidth: "380px",
          background: "var(--surface-1)",
          border: "1px solid var(--border-2)",
          boxShadow: "0 24px 48px rgba(0,0,0,0.5)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span
              className="font-mono font-bold"
              style={{ fontSize: "18px", color: "var(--text-4)" }}
            >
              Sell {pos.ticker}
            </span>
            <span
              className="font-mono text-xs font-semibold"
              style={{ color: pnlColor }}
            >
              {sellPnlPct >= 0 ? "+" : ""}{sellPnlPct.toFixed(1)}%
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-xs rounded px-2 py-1 transition-colors"
            style={{ color: "var(--text-1)", border: "1px solid var(--border-1)" }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-1)"; }}
          >
            ESC
          </button>
        </div>

        {result ? (
          <div
            className="rounded-lg p-4 text-center"
            style={{
              background: result.success ? "rgba(74,222,128,0.08)" : "rgba(248,113,113,0.08)",
              border: `1px solid ${result.success ? "rgba(74,222,128,0.25)" : "rgba(248,113,113,0.25)"}`,
            }}
          >
            <span
              className="text-sm font-medium"
              style={{ color: result.success ? "var(--green)" : "var(--red)" }}
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
                style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-1)" }}
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
                  className="flex-1 font-mono text-sm rounded px-3 py-2 outline-none transition-colors"
                  style={{
                    background: "var(--surface-2)",
                    border: "1px solid var(--border-1)",
                    color: "var(--text-4)",
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-1)"; }}
                />
                <span
                  className="flex items-center text-xs font-mono"
                  style={{ color: "var(--text-1)" }}
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
                            background: pct === 100 ? "rgba(248,113,113,0.12)" : "rgba(124,92,252,0.12)",
                            border: `1px solid ${pct === 100 ? "rgba(248,113,113,0.40)" : "var(--border-2)"}`,
                            color: pct === 100 ? "var(--red)" : "var(--accent)",
                          }
                        : {
                            background: "var(--surface-2)",
                            border: "1px solid var(--border-1)",
                            color: "var(--text-2)",
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
                style={{ background: "var(--surface-2)", border: "1px solid var(--border-0)" }}
              >
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-1)" }}>Shares</span>
                  <span className="font-mono" style={{ color: "var(--text-3)" }}>
                    {numShares.toLocaleString()}{isAll ? "" : ` of ${pos.shares.toLocaleString()}`}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-1)" }}>Price</span>
                  <span className="font-mono" style={{ color: "var(--text-3)" }}>
                    ${pos.current_price.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-1)" }}>Total Value</span>
                  <span className="font-mono" style={{ color: "var(--text-3)" }}>
                    ${sellValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div
                  className="flex justify-between text-xs pt-1.5 mt-1.5"
                  style={{ borderTop: "1px solid var(--border-1)" }}
                >
                  <span style={{ color: "var(--text-1)" }}>P&L</span>
                  <span className="font-mono font-semibold" style={{ color: pnlColor }}>
                    {sellPnl >= 0 ? "+" : ""}${sellPnl.toLocaleString(undefined, { maximumFractionDigits: 2 })} ({sellPnlPct >= 0 ? "+" : ""}{sellPnlPct.toFixed(1)}%)
                  </span>
                </div>
                {!isAll && (
                  <div className="flex justify-between text-xs" style={{ color: "var(--text-1)" }}>
                    <span>Remaining</span>
                    <span className="font-mono">
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
                  background: "var(--surface-3)",
                  color: "var(--text-2)",
                  border: "1px solid var(--border-1)",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSell}
                disabled={!isValid || selling}
                className="flex-1 py-2 rounded text-xs font-semibold transition-colors disabled:opacity-40"
                style={{
                  background: "rgba(248,113,113,0.10)",
                  color: "rgba(248,113,113,0.90)",
                  border: "1px solid rgba(248,113,113,0.35)",
                }}
                onMouseEnter={(e) => {
                  if (!e.currentTarget.disabled) {
                    e.currentTarget.style.background = "rgba(248,113,113,0.18)";
                    e.currentTarget.style.borderColor = "rgba(248,113,113,0.55)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "rgba(248,113,113,0.10)";
                  e.currentTarget.style.borderColor = "rgba(248,113,113,0.35)";
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
