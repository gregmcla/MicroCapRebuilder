/** HealthStrip — 34px bar between TopBar and workspace.
 *  Shows: portfolio health score | position glyphs (ticker + day %) | clock + day P&L
 */

import { useState, useEffect } from "react";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { useRisk } from "../hooks/useRisk";
import { usePortfolioStore } from "../lib/store";

export default function HealthStrip() {
  const [clock, setClock] = useState("");
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const { data: state } = usePortfolioState();
  const { data: risk } = useRisk();

  useEffect(() => {
    const tick = () =>
      setClock(new Date().toLocaleTimeString("en-US", { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  if (!portfolioId || portfolioId === "overview" || portfolioId === "logs") return null;

  const positions = state?.positions ?? [];
  const dayPnl = state?.day_pnl ?? 0;
  const healthScore = risk ? Math.round(risk.overall_score) : null;

  // Sort by day change descending (best performers first in glyph row)
  const sorted = [...positions].sort(
    (a, b) => (b.day_change_pct ?? 0) - (a.day_change_pct ?? 0)
  );

  const wins = positions.filter((p) => (p.day_change_pct ?? 0) > 0).length;
  const healthColor =
    healthScore == null
      ? "var(--text-muted)"
      : healthScore >= 70
      ? "var(--green)"
      : healthScore >= 50
      ? "var(--amber)"
      : "var(--red)";

  return (
    <div
      style={{
        height: 34,
        display: "flex",
        alignItems: "center",
        padding: "0 16px",
        background: "rgba(15,23,42,0.5)",
        borderBottom: "1px solid var(--border)",
        flexShrink: 0,
        gap: 0,
        overflow: "hidden",
      }}
    >
      {/* Health section */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          paddingRight: 16,
          borderRight: "1px solid var(--border)",
          flexShrink: 0,
          fontSize: 11,
        }}
      >
        <span
          style={{
            fontSize: 9,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-dim)",
          }}
        >
          Health
        </span>
        {healthScore !== null && (
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              fontFamily: "var(--font-mono)",
              color: healthColor,
            }}
          >
            {healthScore}
          </span>
        )}
        {positions.length > 0 && (
          <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
            <span style={{ color: "var(--green)" }}>{wins}</span>
            <span style={{ color: "var(--text-dim)" }}>/{positions.length}</span>
            {" "}
            <span style={{ color: "var(--text-dim)" }}>up</span>
          </span>
        )}
      </div>

      {/* Position glyphs — scrollable */}
      <div
        style={{
          display: "flex",
          gap: 2,
          flex: 1,
          overflow: "hidden",
          padding: "0 12px",
        }}
      >
        {sorted.map((pos) => {
          const pct = pos.day_change_pct;
          const color =
            pct == null
              ? "var(--text-muted)"
              : pct > 0
              ? "var(--green)"
              : pct < 0
              ? "var(--red)"
              : "var(--text-muted)";

          // At-risk: within 30% of stop-loss range
          const range = pos.take_profit - pos.stop_loss;
          const progress =
            range > 0
              ? ((pos.current_price - pos.stop_loss) / range) * 100
              : 100;
          const isAtRisk = progress < 30;

          return (
            <div
              key={pos.ticker}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                padding: "2px 7px",
                borderRadius: 4,
                whiteSpace: "nowrap",
                background: isAtRisk ? "var(--red-dim)" : undefined,
                transition: "background 0.15s",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontWeight: 500,
                  color: "var(--text-secondary)",
                  fontSize: 10,
                }}
              >
                {pos.ticker}
              </span>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  fontWeight: 500,
                  color,
                }}
              >
                {pct != null
                  ? `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}`
                  : "--"}
              </span>
            </div>
          );
        })}
      </div>

      {/* Clock + market status + day P&L */}
      <div
        style={{
          marginLeft: "auto",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--text-muted)",
          display: "flex",
          alignItems: "center",
          gap: 10,
          flexShrink: 0,
          paddingLeft: 16,
          borderLeft: "1px solid var(--border)",
        }}
      >
        <span
          style={{
            color: "var(--green)",
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: "0.06em",
          }}
        >
          ● LIVE
        </span>
        <span style={{ color: "var(--text-dim)" }}>{clock}</span>
        {dayPnl !== 0 && (
          <span
            style={{
              color: dayPnl > 0 ? "var(--green)" : "var(--red)",
              fontWeight: 600,
            }}
          >
            {dayPnl > 0 ? "+" : "-"}$
            {Math.abs(dayPnl).toLocaleString("en-US", {
              maximumFractionDigits: 0,
            })}
          </span>
        )}
      </div>
    </div>
  );
}
