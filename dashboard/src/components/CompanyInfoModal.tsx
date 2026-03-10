/** Glassmorphic company profile modal — triggered by clicking a ticker. */

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolioStore } from "../lib/store";

function fmt_cap(v: number | null): string {
  if (v == null) return "—";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toLocaleString()}`;
}

function fmt_rating(r: string | null): string {
  if (!r) return "—";
  const map: Record<string, string> = {
    strongbuy: "Strong Buy", buy: "Buy", hold: "Hold",
    underperform: "Underperform", sell: "Sell",
  };
  return map[r.toLowerCase()] ?? r;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="flex flex-col gap-0.5 rounded-lg px-3 py-2"
      style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
    >
      <span style={{ fontSize: "9.5px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)" }}>
        {label}
      </span>
      <span className="font-mono text-sm font-semibold" style={{ color: "var(--text-3)" }}>
        {value}
      </span>
    </div>
  );
}

export default function CompanyInfoModal({
  ticker,
  onClose,
  holdingValue,
}: {
  ticker: string;
  onClose: () => void;
  holdingValue?: number;
}) {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  const { data: info, isLoading } = useQuery({
    queryKey: ["tickerInfo", ticker],
    queryFn: () => api.getTickerInfo(portfolioId, ticker),
    staleTime: 24 * 60 * 60 * 1000,
  });

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const ratingColor = (r: string | null) => {
    if (!r) return "var(--text-2)";
    const l = r.toLowerCase();
    if (l.includes("strongbuy") || l.includes("buy")) return "var(--green)";
    if (l.includes("sell")) return "var(--red)";
    return "var(--text-2)";
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md mx-4 rounded-2xl p-5"
        style={{
          background: "rgba(18,18,28,0.92)",
          border: "1px solid rgba(255,255,255,0.10)",
          boxShadow: "0 24px 64px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.08)",
          backdropFilter: "blur(24px)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-xs rounded-full w-6 h-6 flex items-center justify-center transition-colors"
          style={{ color: "var(--text-1)", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.12)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.06)"; }}
        >
          ✕
        </button>

        {isLoading ? (
          <div className="space-y-3 animate-pulse">
            <div className="h-5 w-24 rounded bg-white/10" />
            <div className="h-3 w-48 rounded bg-white/10" />
            <div className="h-16 w-full rounded bg-white/10" />
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="mb-3 pr-6">
              <div className="flex items-baseline gap-2 mb-0.5">
                <span className="font-mono font-bold text-lg" style={{ color: "var(--text-4)" }}>
                  {ticker}
                </span>
                {info?.analyst_rating && (
                  <span
                    className="text-xs font-semibold px-2 py-0.5 rounded-full"
                    style={{
                      color: ratingColor(info.analyst_rating),
                      background: `${ratingColor(info.analyst_rating)}18`,
                      border: `1px solid ${ratingColor(info.analyst_rating)}30`,
                    }}
                  >
                    {fmt_rating(info.analyst_rating)}
                    {info.analyst_count ? ` · ${info.analyst_count}` : ""}
                  </span>
                )}
              </div>
              <div className="text-sm font-semibold mb-1" style={{ color: "var(--text-3)" }}>
                {info?.name ?? ticker}
              </div>
              {(info?.sector || info?.industry) && (
                <div className="flex gap-1.5 flex-wrap">
                  {info.sector && (
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{ background: "rgba(124,92,252,0.15)", color: "var(--accent)", border: "1px solid rgba(124,92,252,0.25)" }}
                    >
                      {info.sector}
                    </span>
                  )}
                  {info.industry && info.industry !== info.sector && (
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{ background: "rgba(255,255,255,0.05)", color: "var(--text-1)", border: "1px solid rgba(255,255,255,0.08)" }}
                    >
                      {info.industry}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Description */}
            {info?.description && (
              <p className="text-xs leading-relaxed mb-4" style={{ color: "var(--text-1)" }}>
                {info.description}
              </p>
            )}

            {/* Stats grid */}
            <div className="grid grid-cols-3 gap-2 mb-3">
              {holdingValue != null && (
                <Stat label="Holding Value" value={`$${holdingValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
              )}
              <Stat label="Market Cap" value={fmt_cap(info?.market_cap ?? null)} />
              <Stat
                label="P/E (TTM)"
                value={info?.trailing_pe != null ? `${info.trailing_pe.toFixed(1)}×` : "—"}
              />
              <Stat
                label="Fwd P/E"
                value={info?.forward_pe != null ? `${info.forward_pe.toFixed(1)}×` : "—"}
              />
              <Stat
                label="52-Wk Low"
                value={info?.week_52_low != null ? `$${info.week_52_low.toFixed(2)}` : "—"}
              />
              <Stat
                label="52-Wk High"
                value={info?.week_52_high != null ? `$${info.week_52_high.toFixed(2)}` : "—"}
              />
              <Stat
                label="Analyst Target"
                value={info?.analyst_target != null ? `$${info.analyst_target.toFixed(2)}` : "—"}
              />
              <Stat
                label="Beta"
                value={info?.beta != null ? info.beta.toFixed(2) : "—"}
              />
              <Stat
                label="Dividend"
                value={info?.dividend_yield != null ? `${(info.dividend_yield * 100).toFixed(2)}%` : "—"}
              />
              <Stat
                label="Employees"
                value={info?.employees != null ? info.employees.toLocaleString() : "—"}
              />
            </div>

            {/* Website */}
            {info?.website && (
              <a
                href={info.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs transition-colors"
                style={{ color: "var(--text-1)" }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-1)"; }}
              >
                {info.website.replace(/^https?:\/\//, "")} ↗
              </a>
            )}
          </>
        )}
      </div>
    </div>
  );
}
