/**
 * PositionInlineDetail — full inline detail view for the DETAIL tab.
 * Matches the mockup layout: header → 6 metric cards → chart → progress bar → thesis.
 * NOT absolutely positioned — fills the flex container naturally.
 */

import { useState, useEffect } from "react";
import type { MatrixPosition, TradeRationale, Transaction } from "./types";
import type { TickerInfo, ChartDataPoint } from "../../lib/types";
import { api } from "../../lib/api";
import { pc } from "./constants";
import InteractiveSparkline from "./InteractiveSparkline";
import SellModal from "../SellModal";
import CompanyInfoModal from "../CompanyInfoModal";

type ChartRange = "1M" | "3M" | "1Y";

function matrixToSellPos(mp: MatrixPosition) {
  return {
    ticker: mp.ticker,
    shares: mp.shares ?? 0,
    avg_cost_basis: mp.avgCost ?? 0,
    current_price: mp.currentPrice ?? 0,
    market_value: mp.value,
    unrealized_pnl: mp.unrealizedPnl ?? 0,
    unrealized_pnl_pct: mp.perf,
    stop_loss: mp.stopLoss ?? 0,
    take_profit: mp.takeProfit ?? 0,
    entry_date: mp.entryDate ?? "",
    day_change: mp.dayChangeDollar,
    day_change_pct: mp.day,
  };
}

interface Props {
  pos: MatrixPosition;
  portfolioId?: string;
  rationale?: TradeRationale | null;
  buyTx?: Transaction | null;
  sellReasoning?: string | null;
}

export default function PositionInlineDetail({ pos, portfolioId, rationale = null, buyTx = null, sellReasoning = null }: Props) {
  const [info, setInfo] = useState<TickerInfo | null>(null);
  const [chartPts, setChartPts] = useState<ChartDataPoint[]>([]);
  const [chartRange, setChartRange] = useState<ChartRange>("3M");
  const [showSell, setShowSell] = useState(false);
  const [showCompany, setShowCompany] = useState(false);

  const pid = portfolioId ?? pos.portfolioId;

  // Fetch ticker info
  useEffect(() => {
    if (!pos.ticker) return;
    setInfo(null);
    api.getTickerInfo(pid, pos.ticker).then(setInfo).catch(() => setInfo(null));
  }, [pos.ticker, pid]);

  // Fetch chart data
  useEffect(() => {
    if (!pos.ticker) return;
    setChartPts([]);
    api.getChartData(pos.ticker, chartRange)
      .then(d => setChartPts(d.data ?? []))
      .catch(() => setChartPts([]));
  }, [pos.ticker, chartRange]);

  // Computed values
  const stop = pos.stopLoss ?? 0;
  const target = pos.takeProfit ?? 0;
  const current = pos.currentPrice ?? 0;
  const entry = pos.avgCost ?? 0;
  const priceRange = target - stop;
  const progressPct = priceRange > 0 ? Math.max(0, Math.min(100, ((current - stop) / priceRange) * 100)) : 0;
  const entryPct    = priceRange > 0 ? Math.max(0, Math.min(100, ((entry  - stop) / priceRange) * 100)) : 0;

  const pnlPct = pos.perf;
  const pnlDollar = pos.unrealizedPnl ?? 0;
  const pnlColor = pc(pnlPct);

  const entryDaysAgo = pos.entryDate
    ? Math.floor((Date.now() - new Date(pos.entryDate).getTime()) / 86_400_000)
    : null;

  // Score: prefer composite_score from buy tx, else average of factor scores
  const score = buyTx?.composite_score != null
    ? Math.round(buyTx.composite_score)
    : rationale?.top_factors?.length
      ? Math.round(rationale.top_factors.reduce((s, f) => s + f.score, 0) / rationale.top_factors.length)
      : null;

  const scoreColor = score != null ? (score >= 70 ? "var(--green)" : score >= 50 ? "var(--amber)" : "var(--red)") : "var(--text-muted)";
  const scoreLabel = score != null ? (score >= 70 ? "Strong" : score >= 50 ? "Moderate" : "Weak") : "—";

  const chartValues = chartPts.map(d => d.close);
  const chartTimestamps = chartPts.map(d => d.time * 1000);

  const companySubtitle = [info?.name, info?.sector, info?.industry]
    .filter(Boolean)
    .join(" · ");

  const accentColor = pos.portfolioColor ?? "var(--accent)";

  return (
    <div style={{
      flex: 1,
      overflowY: "auto",
      padding: "20px 20px 28px",
      display: "flex",
      flexDirection: "column",
      gap: 20,
    }}>

      {/* ── HEADER ─────────────────────────────────────────── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{
            fontFamily: "var(--font-mono)",
            fontSize: 24,
            fontWeight: 700,
            color: "var(--text-primary)",
            letterSpacing: "-0.03em",
            lineHeight: 1.1,
          }}>
            {pos.ticker}
          </div>
          <div style={{
            fontSize: 12,
            color: "var(--text-muted)",
            marginTop: 4,
            lineHeight: 1.3,
          }}>
            {companySubtitle || pos.portfolioName || "—"}
          </div>
        </div>

        <div style={{ display: "flex", gap: 6, flexShrink: 0, marginLeft: 12 }}>
          {/* Company info button */}
          <button
            onClick={() => setShowCompany(true)}
            style={{
              height: 30, padding: "0 12px",
              borderRadius: 6, fontSize: 11, fontWeight: 500,
              cursor: "pointer", border: "1px solid var(--border)",
              background: "rgba(148,163,184,0.04)",
              color: "var(--text-secondary)",
              fontFamily: "var(--font-sans)",
              transition: "all 0.15s",
            }}
          >
            Company
          </button>
          {/* Sell button */}
          {(pos.shares ?? 0) > 0 && (
            <button
              onClick={() => setShowSell(true)}
              style={{
                height: 30, padding: "0 12px",
                borderRadius: 6, fontSize: 11, fontWeight: 500,
                cursor: "pointer",
                border: "1px solid rgba(239,68,68,0.2)",
                background: "rgba(239,68,68,0.06)",
                color: "var(--red)",
                fontFamily: "var(--font-sans)",
                transition: "all 0.15s",
              }}
            >
              Sell
            </button>
          )}
        </div>
      </div>

      {/* ── 6 METRIC CARDS ─────────────────────────────────── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(6, 1fr)",
        gap: 8,
      }}>
        <MetricCard
          label="Entry"
          value={entry > 0 ? `$${entry.toFixed(2)}` : "—"}
          sub={entryDaysAgo != null ? `${entryDaysAgo}d ago` : "—"}
          valueColor="var(--text-muted)"
        />
        <MetricCard
          label="Current"
          value={current > 0 ? `$${current.toFixed(2)}` : "—"}
          sub={current > entry && entry > 0 ? `+$${(current - entry).toFixed(2)}` : entry > 0 && current > 0 ? `-$${(entry - current).toFixed(2)}` : "—"}
        />
        <MetricCard
          label="P&L"
          value={pnlDollar !== 0 ? `${pnlDollar >= 0 ? "+" : ""}$${Math.round(Math.abs(pnlDollar)).toLocaleString()}` : "—"}
          sub={`${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(1)}%`}
          valueColor={pnlColor}
          subColor={pnlColor}
        />
        <MetricCard
          label="Day Change"
          value={pos.day !== 0 ? `${pos.day >= 0 ? "+" : ""}${pos.day.toFixed(1)}%` : "—"}
          sub={pos.dayChangeDollar != null
            ? `${pos.dayChangeDollar >= 0 ? "+" : ""}$${Math.abs(Math.round(pos.dayChangeDollar)).toLocaleString()}`
            : "—"}
          valueColor={pc(pos.day)}
          subColor={pc(pos.day)}
        />
        <MetricCard
          label="Shares"
          value={pos.shares != null ? pos.shares.toString() : "—"}
          sub={pos.value > 0 ? `$${Math.round(pos.value).toLocaleString()} value` : "—"}
        />
        <MetricCard
          label="Score"
          value={score != null ? score.toString() : "—"}
          sub={scoreLabel}
          valueColor={scoreColor}
        />
      </div>

      {/* ── CHART ──────────────────────────────────────────── */}
      <div style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        height: 200,
        position: "relative",
        overflow: "hidden",
      }}>
        {/* Period tabs */}
        <div style={{
          position: "absolute", top: 10, right: 12, zIndex: 2,
          display: "flex", gap: 2,
          background: "rgba(148,163,184,0.04)",
          borderRadius: 6, padding: 2,
        }}>
          {(["1M", "3M", "1Y"] as ChartRange[]).map(r => (
            <button
              key={r}
              onClick={() => setChartRange(r)}
              style={{
                padding: "3px 10px", borderRadius: 5, fontSize: 10,
                fontWeight: 500, cursor: "pointer",
                border: "none",
                color: chartRange === r ? "var(--text-primary)" : "var(--text-dim)",
                background: chartRange === r ? "var(--bg-elevated)" : "transparent",
                fontFamily: "var(--font-sans)",
                transition: "all 0.15s",
              }}
            >
              {r}
            </button>
          ))}
        </div>

        {chartValues.length > 2 ? (
          <div style={{ position: "absolute", inset: 0 }}>
            <InteractiveSparkline
              data={chartValues}
              color={accentColor}
              h={200}
              timestamps={chartTimestamps}
            />
          </div>
        ) : (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 11, color: "var(--text-dim)",
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.05em",
          }}>
            {chartValues.length === 0 ? "LOADING CHART..." : "INSUFFICIENT DATA"}
          </div>
        )}
      </div>

      {/* ── PROGRESS BAR (Stop → Entry → Target) ───────────── */}
      {priceRange > 0 && (
        <div>
          <div style={{
            display: "flex", justifyContent: "space-between",
            fontSize: 10, color: "var(--text-dim)",
            fontFamily: "var(--font-mono)",
            marginBottom: 6,
          }}>
            <span>Stop ${stop.toFixed(2)}</span>
            <span>Entry ${entry.toFixed(2)}</span>
            <span>Target ${target.toFixed(2)}</span>
          </div>
          <div style={{
            height: 6, background: "var(--bg-elevated)",
            borderRadius: 3, position: "relative",
          }}>
            {/* Fill gradient: red-dim → green-dim */}
            <div style={{
              position: "absolute", left: 0, top: 0, bottom: 0,
              width: `${progressPct}%`,
              borderRadius: 3,
              background: "linear-gradient(90deg, rgba(239,68,68,0.15), var(--green-dim, rgba(34,197,94,0.12)))",
            }} />
            {/* Entry price marker (slim, muted) */}
            {entryPct > 0 && (
              <div style={{
                position: "absolute",
                top: -2, left: `${entryPct}%`,
                width: 2, height: 10,
                background: "var(--text-dim)",
                borderRadius: 1,
                transform: "translateX(-50%)",
              }} />
            )}
            {/* Current price marker (accent, glowing) */}
            <div style={{
              position: "absolute",
              top: -3, left: `${progressPct}%`,
              width: 3, height: 12,
              background: "var(--accent)",
              borderRadius: 2,
              transform: "translateX(-50%)",
              boxShadow: "0 0 8px rgba(139,92,246,0.5)",
            }} />
          </div>
          <div style={{
            display: "flex", justifyContent: "flex-end",
            fontSize: 9, color: "var(--text-dim)",
            fontFamily: "var(--font-mono)",
            marginTop: 4,
          }}>
            {progressPct.toFixed(0)}% to target
          </div>
        </div>
      )}

      {/* ── PENDING SELL ALERT ─────────────────────────────── */}
      {sellReasoning && (
        <div style={{
          background: "rgba(239,68,68,0.06)",
          border: "1px solid rgba(239,68,68,0.18)",
          borderRadius: 8,
          padding: "12px 14px",
        }}>
          <div style={{
            fontSize: 10, textTransform: "uppercase" as const,
            letterSpacing: "0.06em", color: "var(--red)",
            marginBottom: 6, fontWeight: 600, fontFamily: "var(--font-sans)",
          }}>
            Pending Exit · AI Reasoning
          </div>
          <div style={{
            fontSize: 12, color: "var(--text-secondary)",
            lineHeight: 1.65, fontFamily: "var(--font-sans)",
          }}>
            {sellReasoning}
          </div>
        </div>
      )}

      {/* ── AI THESIS ───────────────────────────────────────── */}
      <div style={{
        background: "rgba(139,92,246,0.04)",
        border: "1px solid rgba(139,92,246,0.1)",
        borderRadius: 10,
        padding: "14px 16px",
      }}>
        <div style={{
          fontSize: 10,
          textTransform: "uppercase" as const,
          letterSpacing: "0.06em",
          color: "var(--accent)",
          marginBottom: 8,
          fontWeight: 600,
          fontFamily: "var(--font-sans)",
        }}>
          AI Thesis
          {rationale && " · Entry"}
        </div>
        {rationale?.ai_reasoning ? (
          <div style={{
            fontSize: 12,
            color: "var(--text-secondary)",
            lineHeight: 1.65,
            fontFamily: "var(--font-sans)",
          }}>
            {rationale.ai_reasoning}
          </div>
        ) : (
          <div style={{
            fontSize: 12,
            color: "var(--text-dim)",
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.04em",
          }}>
            No thesis available — run ANALYZE to generate AI reasoning.
          </div>
        )}

        {/* Factor bars if available */}
        {rationale?.top_factors && rationale.top_factors.length > 0 && (
          <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 4 }}>
            {rationale.top_factors.map(f => {
              const label = ({
                price_momentum: "MOMENTUM",
                earnings_growth: "EARNINGS",
                quality: "QUALITY",
                volume: "VOLUME",
                volatility: "VOLATILITY",
                value_timing: "VALUE",
              } as Record<string, string>)[f.name] ?? f.name.toUpperCase().slice(0, 8);
              return (
                <div key={f.name} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{
                    fontSize: 9, color: "var(--text-dim)",
                    letterSpacing: "0.06em", width: 64, flexShrink: 0,
                    fontFamily: "var(--font-mono)",
                  }}>
                    {label}
                  </div>
                  <div style={{
                    flex: 1, height: 2,
                    background: "rgba(255,255,255,0.05)",
                    borderRadius: 1,
                    overflow: "hidden",
                  }}>
                    <div style={{
                      height: "100%",
                      width: `${Math.min(f.score, 100)}%`,
                      background: "var(--accent)",
                      opacity: 0.4 + (f.score / 100) * 0.5,
                    }} />
                  </div>
                  <div style={{
                    fontSize: 9, color: "var(--text-dim)",
                    width: 22, textAlign: "right", flexShrink: 0,
                    fontFamily: "var(--font-mono)",
                  }}>
                    {f.score.toFixed(0)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Sell modal */}
      {showSell && (pos.shares ?? 0) > 0 && (
        <SellModal pos={matrixToSellPos(pos)} onClose={() => setShowSell(false)} />
      )}

      {/* Company info modal */}
      {showCompany && (
        <CompanyInfoModal
          ticker={pos.ticker}
          onClose={() => setShowCompany(false)}
          holdingValue={pos.value}
        />
      )}
    </div>
  );
}

// ── Metric Card ────────────────────────────────────────────────────────────────
function MetricCard({
  label,
  value,
  sub,
  valueColor = "var(--text-primary)",
  subColor = "var(--text-dim)",
}: {
  label: string;
  value: string;
  sub?: string;
  valueColor?: string;
  subColor?: string;
}) {
  return (
    <div style={{
      background: "var(--bg-surface)",
      border: "1px solid var(--border)",
      borderRadius: 8,
      padding: "10px 12px",
    }}>
      <div style={{
        fontSize: 9,
        textTransform: "uppercase" as const,
        letterSpacing: "0.06em",
        color: "var(--text-dim)",
        marginBottom: 4,
        fontWeight: 500,
        fontFamily: "var(--font-sans)",
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: "var(--font-mono)",
        fontSize: 14,
        fontWeight: 600,
        letterSpacing: "-0.02em",
        color: valueColor,
        lineHeight: 1.2,
      }}>
        {value}
      </div>
      {sub && (
        <div style={{
          fontSize: 9,
          color: subColor,
          marginTop: 3,
          fontFamily: "var(--font-mono)",
        }}>
          {sub}
        </div>
      )}
    </div>
  );
}
