/** Context strip — secondary metrics below TopBar.
 *  44px height. Equity, day P&L, and action buttons have moved to TopBar.
 *  This strip shows: Open P&L | All-Time | Return | Cash | Benchmarks | Regime | Risk | Positions
 */

import { useMemo } from "react";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { useRisk } from "../hooks/useRisk";

// ── Sub-components ────────────────────────────────────────────────────────────

function StripDivider() {
  return (
    <div
      style={{
        width: "1px",
        alignSelf: "stretch",
        margin: "10px 0",
        background: "var(--border-hover)",
        flexShrink: 0,
        opacity: 0.5,
      }}
    />
  );
}

function Stat({
  label,
  value,
  colorClass,
}: {
  label: string;
  value: string;
  colorClass?: string;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span
        className={`font-mono tabular-nums font-semibold ${colorClass ?? "text-text-primary"}`}
        style={{ fontSize: "13px", lineHeight: 1 }}
      >
        {value}
      </span>
      <span
        style={{
          fontSize: "9px",
          textTransform: "uppercase",
          letterSpacing: "0.09em",
          color: "var(--text-muted)",
          lineHeight: 1,
        }}
      >
        {label}
      </span>
    </div>
  );
}

// ── Main export ────────────────────────────────────────────────────────────────

export default function PortfolioSummary() {
  const { data: state } = usePortfolioState();
  const { data: risk } = useRisk();

  const openPnl    = state?.positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0) ?? 0;
  const allTimePnl = state?.all_time_pnl ?? 0;
  const returnPct  = state?.total_return_pct ?? 0;
  const cash       = state?.cash ?? 0;

  const c = (v: number) => v >= 0 ? "text-profit" : "text-loss";
  const fmt$ = (v: number) =>
    `${v >= 0 ? "+" : ""}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  const fmtPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

  const benchmarks = state
    ? [
        { label: "SPX", alpha: state.spx_alpha },
        { label: "NDX", alpha: state.ndx_alpha },
        { label: "RUT", alpha: state.rut_alpha },
      ]
    : [];
  const hasBenchmarks = benchmarks.some((b) => b.alpha != null);

  const regimeColor =
    state?.regime === "BULL"
      ? "var(--green)"
      : state?.regime === "BEAR"
      ? "var(--red)"
      : "var(--amber)";

  const riskScore = risk?.overall_score != null ? Math.round(risk.overall_score) : null;
  const riskColor =
    riskScore == null
      ? "var(--text-secondary)"
      : riskScore >= 70
      ? "var(--green)"
      : riskScore >= 40
      ? "var(--amber)"
      : "var(--red)";

  return (
    <div
      className="flex-shrink-0 border-b"
      style={{
        borderColor: "var(--border)",
        background: "var(--bg-surface)",
      }}
    >
      <div style={{ display: "flex", alignItems: "stretch", minHeight: "44px", overflowX: "auto", scrollbarWidth: "none", msOverflowStyle: "none" } as React.CSSProperties}>

        {/* ── P&L metrics ─────────────────────────────────────────────── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "16px",
            padding: "0 18px 0 16px",
            flexShrink: 0,
          }}
        >
          <Stat label="Open P&L"  value={fmt$(openPnl)}    colorClass={c(openPnl)} />
          <Stat label="All-Time"  value={fmt$(allTimePnl)} colorClass={c(allTimePnl)} />
          <Stat label="Return"    value={fmtPct(returnPct)} colorClass={c(returnPct)} />
          <Stat label="Cash"      value={`$${cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
        </div>

        {/* ── Benchmarks ──────────────────────────────────────────────── */}
        {hasBenchmarks && (
          <>
            <StripDivider />
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "14px",
                padding: "0 18px",
                flexShrink: 0,
              }}
            >
              {benchmarks.map(({ label, alpha }) => (
                <div key={label} style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  <span
                    className="font-mono tabular-nums font-semibold"
                    style={{
                      fontSize: "13px",
                      lineHeight: 1,
                      color:
                        alpha == null
                          ? "var(--text-0)"
                          : alpha >= 0
                          ? "var(--green)"
                          : "var(--red)",
                    }}
                  >
                    {alpha == null ? "—" : `${alpha >= 0 ? "+" : ""}${alpha.toFixed(1)}%α`}
                  </span>
                  <span
                    style={{
                      fontSize: "9px",
                      textTransform: "uppercase",
                      letterSpacing: "0.09em",
                      color: "var(--text-muted)",
                      lineHeight: 1,
                    }}
                  >
                    {label}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}

        {/* ── Status ──────────────────────────────────────────────────── */}
        <StripDivider />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "14px",
            padding: "0 18px",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            <span
              className="font-semibold"
              style={{ fontSize: "13px", color: regimeColor, lineHeight: 1 }}
            >
              {state?.regime ?? "—"}
            </span>
            <span
              style={{
                fontSize: "9px",
                textTransform: "uppercase",
                letterSpacing: "0.09em",
                color: "var(--text-muted)",
                lineHeight: 1,
              }}
            >
              Regime
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            <span
              className="font-mono font-semibold"
              style={{ fontSize: "13px", color: riskColor, lineHeight: 1 }}
            >
              {riskScore ?? "—"}
            </span>
            <span
              style={{
                fontSize: "9px",
                textTransform: "uppercase",
                letterSpacing: "0.09em",
                color: "var(--text-muted)",
                lineHeight: 1,
              }}
            >
              Risk
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            <span
              className="font-mono font-semibold"
              style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1 }}
            >
              {state?.positions.length ?? 0}
            </span>
            <span
              style={{
                fontSize: "9px",
                textTransform: "uppercase",
                letterSpacing: "0.09em",
                color: "var(--text-muted)",
                lineHeight: 1,
              }}
            >
              Positions
            </span>
          </div>

          {(state?.stale_alerts.length ?? 0) > 0 && (
            <span
              style={{
                fontSize: "10px",
                color: "var(--amber)",
                fontWeight: 600,
              }}
            >
              ⚠ {state!.stale_alerts.length} stale
            </span>
          )}
        </div>

      </div>
    </div>
  );
}
