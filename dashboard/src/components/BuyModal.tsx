/** BuyModal — manual buy with ticker input, auto-suggested shares, editable stop/target. */

import { useState, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";

interface QuoteData {
  ticker: string;
  price: number;
  name: string;
  sector: string;
  prev_close: number | null;
  available_cash: number;
  risk_per_trade_pct: number;
  default_stop_loss_pct: number;
  default_take_profit_pct: number;
  suggested_shares: number;
}

interface BuyModalProps {
  onClose: () => void;
}

export default function BuyModal({ onClose }: BuyModalProps) {
  const queryClient = useQueryClient();
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  const [tickerInput, setTickerInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tickerRef = useRef<HTMLInputElement>(null);

  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [shares, setShares] = useState("");
  const [stopPct, setStopPct] = useState("");
  const [takePct, setTakePct] = useState("");
  const [buying, setBuying] = useState(false);
  const [result, setResult] = useState<{ message: string; success: boolean } | null>(null);

  useEffect(() => { tickerRef.current?.focus(); }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const fetchQuote = async () => {
    const ticker = tickerInput.trim().toUpperCase();
    if (!ticker) return;
    setLoading(true);
    setError(null);
    try {
      const q = await api.getQuote(portfolioId, ticker);
      setQuote(q);
      setShares(String(q.suggested_shares));
      setStopPct(String(q.default_stop_loss_pct));
      setTakePct(String(q.default_take_profit_pct));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch quote");
    } finally {
      setLoading(false);
    }
  };

  const numShares = Math.floor(Number(shares) || 0);
  const totalCost = quote ? numShares * quote.price : 0;
  const isValid = quote != null && numShares > 0 && totalCost <= quote.available_cash;
  const stopPrice = quote ? quote.price * (1 - (Number(stopPct) || 0) / 100) : 0;
  const targetPrice = quote ? quote.price * (1 + (Number(takePct) || 0) / 100) : 0;

  const handleBuy = async () => {
    if (!isValid || !quote) return;
    setBuying(true);
    try {
      const res = await api.buyPosition(portfolioId, {
        ticker: quote.ticker,
        shares: numShares,
        stop_loss_pct: Number(stopPct) || undefined,
        take_profit_pct: Number(takePct) || undefined,
      });
      setResult({ message: res.message, success: true });
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
      queryClient.invalidateQueries({ queryKey: ["chartData"] });
      setTimeout(() => onClose(), 2000);
    } catch (e) {
      setResult({ message: e instanceof Error ? e.message : "Buy failed", success: false });
    } finally {
      setBuying(false);
    }
  };

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: "rgba(2,6,23,0.6)", backdropFilter: "blur(8px)" }}
      onClick={onClose}
    >
      <div
        className="rounded-xl p-5 w-full"
        style={{
          maxWidth: "400px",
          background: "var(--bg-surface)",
          border: "1px solid var(--border-hover)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "0 24px 48px rgba(0,0,0,0.5)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <span style={{ fontFamily: "var(--font-sans)", fontSize: 18, fontWeight: 600, color: "var(--text-primary)" }}>
            {quote ? `Buy ${quote.ticker}` : "Manual Buy"}
          </span>
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
            <span className="text-sm font-medium" style={{ color: result.success ? "var(--green)" : "var(--red)", fontFamily: "var(--font-mono)" }}>
              {result.message}
            </span>
          </div>
        ) : !quote ? (
          <div>
            <label
              className="block mb-1.5"
              style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)" }}
            >
              Ticker
            </label>
            <input
              ref={tickerRef}
              type="text"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => { if (e.key === "Enter") fetchQuote(); }}
              placeholder="e.g. AAPL"
              className="w-full text-sm rounded px-3 py-2 outline-none transition-colors mb-3"
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
            {error && (
              <div className="text-xs mb-3" style={{ color: "var(--red)" }}>{error}</div>
            )}
            <button
              onClick={fetchQuote}
              disabled={!tickerInput.trim() || loading}
              className="w-full py-2 rounded text-xs font-semibold transition-colors disabled:opacity-40"
              style={{
                background: "var(--green-dim)",
                color: "var(--green)",
                border: "1px solid rgba(34,197,94,0.2)",
              }}
              onMouseEnter={(e) => {
                if (!e.currentTarget.disabled) {
                  e.currentTarget.style.background = "rgba(34,197,94,0.14)";
                  e.currentTarget.style.borderColor = "rgba(34,197,94,0.35)";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--green-dim)";
                e.currentTarget.style.borderColor = "rgba(34,197,94,0.2)";
              }}
            >
              {loading ? "Looking up..." : "Get Quote"}
            </button>
          </div>
        ) : (
          <>
            <div
              className="rounded-lg p-3 mb-3"
              style={{ background: "var(--bg-void)", border: "1px solid var(--border)" }}
            >
              <div className="flex items-baseline justify-between">
                <div>
                  <span className="font-bold text-sm" style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{quote.ticker}</span>
                  <span className="text-xs ml-2" style={{ color: "var(--text-secondary)" }}>{quote.name}</span>
                </div>
                <span className="font-bold text-sm" style={{ fontFamily: "var(--font-mono)", color: "var(--green)" }}>${quote.price.toFixed(2)}</span>
              </div>
              {quote.sector && (
                <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{quote.sector}</div>
              )}
              <button
                onClick={() => { setQuote(null); setError(null); }}
                className="text-xs mt-1"
                style={{ color: "var(--accent)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
              >
                Change ticker
              </button>
            </div>

            <div className="mb-3">
              <label
                className="block mb-1.5"
                style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)" }}
              >
                Shares
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  min={1}
                  value={shares}
                  onChange={(e) => setShares(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleBuy(); }}
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
                <span className="flex items-center text-xs" style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                  suggested: {quote.suggested_shares.toLocaleString()}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label
                  className="block mb-1.5"
                  style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--red)" }}
                >
                  Stop Loss %
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={stopPct}
                  onChange={(e) => setStopPct(e.target.value)}
                  className="w-full text-sm rounded px-3 py-2 outline-none transition-colors"
                  style={{
                    background: "var(--bg-elevated)",
                    border: "1px solid rgba(239,68,68,0.2)",
                    borderRadius: 6,
                    fontFamily: "var(--font-mono)",
                    color: "var(--text-primary)",
                  }}
                />
              </div>
              <div>
                <label
                  className="block mb-1.5"
                  style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--green)" }}
                >
                  Take Profit %
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={takePct}
                  onChange={(e) => setTakePct(e.target.value)}
                  className="w-full text-sm rounded px-3 py-2 outline-none transition-colors"
                  style={{
                    background: "var(--bg-elevated)",
                    border: "1px solid rgba(34,197,94,0.2)",
                    borderRadius: 6,
                    fontFamily: "var(--font-mono)",
                    color: "var(--text-primary)",
                  }}
                />
              </div>
            </div>

            {isValid && (
              <div
                className="rounded-lg p-3 mb-4 space-y-1.5"
                style={{ background: "var(--bg-void)", border: "1px solid var(--border)" }}
              >
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-secondary)" }}>Total Cost</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                    ${totalCost.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-secondary)" }}>% of Cash</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                    {((totalCost / quote.available_cash) * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--red)" }}>Stop</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--red)" }}>
                    ${stopPrice.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--green)" }}>Target</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--green)" }}>
                    ${targetPrice.toFixed(2)}
                  </span>
                </div>
                <div
                  className="flex justify-between text-xs pt-1.5 mt-1.5"
                  style={{ borderTop: "1px solid var(--border)" }}
                >
                  <span style={{ color: "var(--text-secondary)" }}>Remaining Cash</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                    ${(quote.available_cash - totalCost).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </span>
                </div>
              </div>
            )}

            {totalCost > quote.available_cash && numShares > 0 && (
              <div className="text-xs mb-3" style={{ color: "var(--red)" }}>
                Insufficient cash: need ${totalCost.toLocaleString(undefined, { maximumFractionDigits: 0 })}, have ${quote.available_cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
            )}

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
                onClick={handleBuy}
                disabled={!isValid || buying}
                className="flex-1 py-2 rounded text-xs font-semibold transition-colors disabled:opacity-40"
                style={{
                  background: "var(--green-dim)",
                  color: "var(--green)",
                  border: "1px solid rgba(34,197,94,0.2)",
                }}
                onMouseEnter={(e) => {
                  if (!e.currentTarget.disabled) {
                    e.currentTarget.style.background = "rgba(34,197,94,0.14)";
                    e.currentTarget.style.borderColor = "rgba(34,197,94,0.35)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "var(--green-dim)";
                  e.currentTarget.style.borderColor = "rgba(34,197,94,0.2)";
                }}
              >
                {buying ? "Buying..." : `Buy ${numShares.toLocaleString()} ${quote.ticker}`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
