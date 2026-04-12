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
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "2px",
        borderRadius: "var(--radius)",
        padding: "8px 12px",
        background: "var(--bg-void)",
        border: "1px solid var(--border)",
      }}
    >
      <span style={{
        fontSize: "9.5px",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        color: "var(--text-dim)",
      }}>
        {label}
      </span>
      <span style={{
        fontFamily: "var(--font-mono)",
        fontSize: "13px",
        fontWeight: 600,
        color: "var(--text-primary)",
      }}>
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
    if (!r) return "var(--text-secondary)";
    const l = r.toLowerCase();
    if (l.includes("strongbuy") || l.includes("buy")) return "var(--green)";
    if (l.includes("sell")) return "var(--red)";
    return "var(--text-secondary)";
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(2,6,23,0.7)", backdropFilter: "blur(12px)" }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md mx-4"
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border-hover)",
          borderRadius: "var(--radius-lg)",
          padding: "20px",
          boxShadow: "0 24px 64px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.04)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-xs rounded-full w-6 h-6 flex items-center justify-center transition-colors"
          style={{
            color: "var(--text-muted)",
            background: "var(--bg-elevated)",
            border: "1px solid var(--border)",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--border-hover)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-elevated)"; }}
        >
          ✕
        </button>

        {isLoading ? (
          <div className="space-y-3 animate-pulse">
            <div className="h-5 w-24 rounded" style={{ background: "var(--bg-elevated)" }} />
            <div className="h-3 w-48 rounded" style={{ background: "var(--bg-elevated)" }} />
            <div className="h-16 w-full rounded" style={{ background: "var(--bg-elevated)" }} />
          </div>
        ) : (
          <>
            {/* Header */}
            <div style={{ marginBottom: "12px", paddingRight: "24px" }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginBottom: "2px" }}>
                <span style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "24px",
                  fontWeight: 700,
                  color: "var(--text-primary)",
                }}>
                  {ticker}
                </span>
                {info?.analyst_rating && (
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      padding: "2px 8px",
                      borderRadius: "4px",
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
              <div style={{
                fontFamily: "var(--font-sans)",
                fontSize: "16px",
                fontWeight: 600,
                color: "var(--text-primary)",
                marginBottom: "6px",
              }}>
                {info?.name ?? ticker}
              </div>
              {(info?.sector || info?.industry) && (
                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                  {info.sector && (
                    <span
                      style={{
                        fontSize: "11px",
                        padding: "3px 8px",
                        borderRadius: "4px",
                        background: "var(--bg-elevated)",
                        color: "var(--text-secondary)",
                        border: "1px solid var(--border)",
                      }}
                    >
                      {info.sector}
                    </span>
                  )}
                  {info.industry && info.industry !== info.sector && (
                    <span
                      style={{
                        fontSize: "11px",
                        padding: "3px 8px",
                        borderRadius: "4px",
                        background: "var(--bg-elevated)",
                        color: "var(--text-secondary)",
                        border: "1px solid var(--border)",
                      }}
                    >
                      {info.industry}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Description */}
            {info?.description && (
              <p style={{
                fontSize: "13px",
                color: "var(--text-secondary)",
                lineHeight: 1.6,
                marginBottom: "16px",
              }}>
                {info.description}
              </p>
            )}

            {/* Stats grid */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "8px",
              marginBottom: "12px",
            }}>
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
                style={{ fontSize: "12px", color: "var(--text-secondary)", transition: "color 0.15s" }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; }}
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
