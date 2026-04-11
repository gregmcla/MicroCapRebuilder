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
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className="rounded-xl p-5 w-full"
        style={{
          maxWidth: "400px",
          background: "var(--surface-1)",
          border: "1px solid var(--border-2)",
          boxShadow: "0 24px 48px rgba(0,0,0,0.5)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <span className="font-mono font-bold" style={{ fontSize: "18px", color: "var(--text-4)" }}>
            {quote ? `Buy ${quote.ticker}` : "Manual Buy"}
          </span>
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
            <span className="text-sm font-medium" style={{ color: result.success ? "var(--green)" : "var(--red)" }}>
              {result.message}
            </span>
          </div>
        ) : !quote ? (
          <div>
            <label
              className="block mb-1.5"
              style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-1)" }}
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
              className="w-full font-mono text-sm rounded px-3 py-2 outline-none transition-colors mb-3"
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border-1)",
                color: "var(--text-4)",
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-1)"; }}
            />
            {error && (
              <div className="text-xs mb-3" style={{ color: "var(--red)" }}>{error}</div>
            )}
            <button
              onClick={fetchQuote}
              disabled={!tickerInput.trim() || loading}
              className="w-full py-2 rounded text-xs font-semibold transition-colors disabled:opacity-40"
              style={{
                background: "rgba(74,222,128,0.10)",
                color: "rgba(74,222,128,0.90)",
                border: "1px solid rgba(74,222,128,0.35)",
              }}
              onMouseEnter={(e) => {
                if (!e.currentTarget.disabled) {
                  e.currentTarget.style.background = "rgba(74,222,128,0.18)";
                  e.currentTarget.style.borderColor = "rgba(74,222,128,0.55)";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "rgba(74,222,128,0.10)";
                e.currentTarget.style.borderColor = "rgba(74,222,128,0.35)";
              }}
            >
              {loading ? "Looking up..." : "Get Quote"}
            </button>
          </div>
        ) : (
          <>
            <div
              className="rounded-lg p-3 mb-3"
              style={{ background: "var(--surface-2)", border: "1px solid var(--border-0)" }}
            >
              <div className="flex items-baseline justify-between">
                <div>
                  <span className="font-mono font-bold text-sm" style={{ color: "var(--text-4)" }}>{quote.ticker}</span>
                  <span className="text-xs ml-2" style={{ color: "var(--text-1)" }}>{quote.name}</span>
                </div>
                <span className="font-mono font-bold text-sm" style={{ color: "var(--green)" }}>${quote.price.toFixed(2)}</span>
              </div>
              {quote.sector && (
                <div className="text-xs mt-1" style={{ color: "var(--text-0)" }}>{quote.sector}</div>
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
                style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-1)" }}
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
                  className="flex-1 font-mono text-sm rounded px-3 py-2 outline-none transition-colors"
                  style={{
                    background: "var(--surface-2)",
                    border: "1px solid var(--border-1)",
                    color: "var(--text-4)",
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-1)"; }}
                />
                <span className="flex items-center text-xs font-mono" style={{ color: "var(--text-1)" }}>
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
                  className="w-full font-mono text-sm rounded px-3 py-2 outline-none transition-colors"
                  style={{
                    background: "var(--surface-2)",
                    border: "1px solid rgba(248,113,113,0.20)",
                    color: "var(--text-4)",
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
                  className="w-full font-mono text-sm rounded px-3 py-2 outline-none transition-colors"
                  style={{
                    background: "var(--surface-2)",
                    border: "1px solid rgba(74,222,128,0.20)",
                    color: "var(--text-4)",
                  }}
                />
              </div>
            </div>

            {isValid && (
              <div
                className="rounded-lg p-3 mb-4 space-y-1.5"
                style={{ background: "var(--surface-2)", border: "1px solid var(--border-0)" }}
              >
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-1)" }}>Total Cost</span>
                  <span className="font-mono" style={{ color: "var(--text-3)" }}>
                    ${totalCost.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-1)" }}>% of Cash</span>
                  <span className="font-mono" style={{ color: "var(--text-3)" }}>
                    {((totalCost / quote.available_cash) * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--red)" }}>Stop</span>
                  <span className="font-mono" style={{ color: "var(--red)" }}>
                    ${stopPrice.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--green)" }}>Target</span>
                  <span className="font-mono" style={{ color: "var(--green)" }}>
                    ${targetPrice.toFixed(2)}
                  </span>
                </div>
                <div
                  className="flex justify-between text-xs pt-1.5 mt-1.5"
                  style={{ borderTop: "1px solid var(--border-1)" }}
                >
                  <span style={{ color: "var(--text-1)" }}>Remaining Cash</span>
                  <span className="font-mono" style={{ color: "var(--text-3)" }}>
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
                  background: "var(--surface-3)",
                  color: "var(--text-2)",
                  border: "1px solid var(--border-1)",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleBuy}
                disabled={!isValid || buying}
                className="flex-1 py-2 rounded text-xs font-semibold transition-colors disabled:opacity-40"
                style={{
                  background: "rgba(74,222,128,0.10)",
                  color: "rgba(74,222,128,0.90)",
                  border: "1px solid rgba(74,222,128,0.35)",
                }}
                onMouseEnter={(e) => {
                  if (!e.currentTarget.disabled) {
                    e.currentTarget.style.background = "rgba(74,222,128,0.18)";
                    e.currentTarget.style.borderColor = "rgba(74,222,128,0.55)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "rgba(74,222,128,0.10)";
                  e.currentTarget.style.borderColor = "rgba(74,222,128,0.35)";
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
