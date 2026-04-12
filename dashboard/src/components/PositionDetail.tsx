/** Position detail — two exports:
 *  PositionDetailChart  → right FocusPane (chart view, SELL button, Back)
 *  PositionDetailInfo   → left column below PositionsPanel (compact trade details)
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Position } from "../lib/types";
import { useUIStore, usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import CandlestickChart from "./CandlestickChart";
import CompanyInfoModal from "./CompanyInfoModal";
import SellModal from "./SellModal";

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function DetailRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div
      className="flex items-center justify-between py-1.5"
      style={{ borderBottom: "1px solid var(--border)" }}
    >
      <span
        className="text-xs"
        style={{
          color: "var(--text-dim)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          fontWeight: 500,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "13px",
          fontWeight: 600,
          color: color ?? "var(--text-primary)",
        }}
      >
        {color ? <span style={{ color }}>{value}</span> : value}
      </span>
    </div>
  );
}

function ProgressVisualization({ pos }: { pos: Position }) {
  const range = pos.take_profit - pos.stop_loss;
  const progress = range > 0 ? ((pos.current_price - pos.stop_loss) / range) * 100 : 50;
  const clamped = Math.max(0, Math.min(100, progress));

  return (
    <div className="mt-3 mb-2">
      <div
        className="flex justify-between mb-1"
        style={{ fontSize: "10px", color: "var(--text-muted)" }}
      >
        <span>Stop ${pos.stop_loss.toFixed(2)}</span>
        <span>Target ${pos.take_profit.toFixed(2)}</span>
      </div>
      <div
        className="relative h-3 rounded-full overflow-hidden"
        style={{ background: "var(--bg-elevated)" }}
      >
        {/* Danger zone (0-20%) */}
        <div
          className="absolute left-0 top-0 h-full w-[20%] rounded-l-full"
          style={{ background: "var(--red-dim)" }}
        />
        {/* Target zone (80-100%) */}
        <div
          className="absolute right-0 top-0 h-full w-[20%] rounded-r-full"
          style={{ background: "var(--green-dim)" }}
        />
        {/* Current price marker — accent fill */}
        <div
          className="absolute top-0 h-full w-1.5 rounded-full"
          style={{
            left: `calc(${clamped}% - 3px)`,
            background: "var(--accent)",
            boxShadow: "0 0 6px rgba(139,92,246,0.5)",
          }}
        />
      </div>
      <div className="flex justify-between mt-1" style={{ fontSize: "10px" }}>
        <span style={{ color: "var(--red)" }}>
          {((pos.stop_loss / pos.current_price - 1) * 100).toFixed(1)}%
        </span>
        <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent)" }}>
          ${pos.current_price.toFixed(2)}
        </span>
        <span style={{ color: "var(--green)" }}>
          +{((pos.take_profit / pos.current_price - 1) * 100).toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

function SellButton({ pos }: { pos: Position }) {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className="px-3 py-1 rounded transition-colors"
        style={{
          fontSize: "11px",
          fontWeight: 600,
          border: "1px solid rgba(239,68,68,0.2)",
          color: "var(--red)",
          background: "var(--red-dim)",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "rgba(239,68,68,0.12)";
          e.currentTarget.style.borderColor = "rgba(239,68,68,0.4)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "var(--red-dim)";
          e.currentTarget.style.borderColor = "rgba(239,68,68,0.2)";
        }}
      >
        SELL
      </button>
      {showModal && <SellModal pos={pos} onClose={() => setShowModal(false)} />}
    </>
  );
}

// ---------------------------------------------------------------------------
// PositionDetailChart — shown in the right FocusPane
// ---------------------------------------------------------------------------

export function PositionDetailChart({ pos }: { pos: Position }) {
  const clearSelection = useUIStore((s) => s.selectPosition);
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [range, setRange] = useState("1M");
  const [showCompanyModal, setShowCompanyModal] = useState(false);

  const { data: tickerInfo } = useQuery({
    queryKey: ["tickerInfo", pos.ticker],
    queryFn: () => api.getTickerInfo(portfolioId, pos.ticker),
    staleTime: 24 * 60 * 60 * 1000,
  });

  const pnlColor =
    pos.unrealized_pnl_pct > 0
      ? "var(--green)"
      : pos.unrealized_pnl_pct < 0
        ? "var(--red)"
        : "var(--text-3)";

  const daysHeld = Math.floor(
    (Date.now() - new Date(pos.entry_date).getTime()) / (1000 * 60 * 60 * 24)
  );

  const dayColor = (pos.day_change ?? 0) >= 0 ? "var(--green)" : "var(--red)";
  const dayStr = pos.day_change != null
    ? `${pos.day_change >= 0 ? "+" : "-"}$${Math.abs(pos.day_change).toFixed(2)}`
    : null;

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--bg-void)" }}>

      {/* Row 1 — hero header */}
      <div
        className="flex items-center justify-between px-4 shrink-0"
        style={{ borderBottom: "1px solid var(--border)", minHeight: "52px" }}
      >
        {/* Left: ticker + company name + P&L numbers */}
        <div className="flex items-baseline gap-3">
          <button
            className="flex flex-col leading-none text-left group"
            onClick={() => setShowCompanyModal(true)}
            title="Company info"
          >
            <span
              className="transition-colors group-hover:text-accent"
              style={{ fontFamily: "var(--font-mono)", fontSize: "22px", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.01em" }}
            >
              {pos.ticker}
            </span>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              {tickerInfo?.name && tickerInfo.name !== pos.ticker ? tickerInfo.name : "View company info"}
            </span>
          </button>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "16px", fontWeight: 600, color: pnlColor }}>
            {pos.unrealized_pnl_pct >= 0 ? "+" : ""}{pos.unrealized_pnl_pct.toFixed(2)}%
          </span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "16px", fontWeight: 600, color: pnlColor }}>
            {pos.unrealized_pnl >= 0 ? "+" : ""}${pos.unrealized_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
          {dayStr && (
            <>
              <span style={{ color: "var(--border-hover)" }}>·</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "14px", color: dayColor }}>{dayStr} today</span>
            </>
          )}
          <span style={{ color: "var(--border-hover)" }}>·</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "14px", color: "var(--text-secondary)" }}>
            ${pos.market_value.toLocaleString(undefined, { maximumFractionDigits: 0 })} value
          </span>
        </div>

        {/* Right: range selector + SELL + Back */}
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            {['1D', '5D', '1M', '3M', 'YTD', 'ALL'].map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className="px-2 py-1 text-xs rounded transition-colors"
                style={
                  range === r
                    ? { color: "var(--accent)", background: "var(--bg-elevated)", border: "1px solid var(--border-hover)", fontWeight: 600 }
                    : { color: "var(--text-dim)", background: "transparent", border: "1px solid var(--border)" }
                }
              >
                {r}
              </button>
            ))}
          </div>
          <SellButton pos={pos} />
          <button
            onClick={() => clearSelection(null)}
            className="text-xs rounded transition-colors px-2 py-1"
            style={{ color: "var(--text-secondary)", border: "1px solid var(--border)" }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.color = "var(--accent)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-secondary)"; }}
          >
            Back
          </button>
        </div>
      </div>

      {/* Row 2 — stat chips + progress bar */}
      <div
        className="flex items-center gap-5 px-4 shrink-0"
        style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-surface)", minHeight: "44px" }}
      >
        {[
          { label: "Shares", value: String(pos.shares), color: undefined },
          { label: "Avg Cost", value: `$${pos.avg_cost_basis.toFixed(2)}`, color: undefined },
          { label: "Stop", value: `$${pos.stop_loss.toFixed(2)}`, color: "var(--red)" },
          { label: "Target", value: `$${pos.take_profit.toFixed(2)}`, color: "var(--green)" },
          { label: "Entry", value: pos.entry_date.slice(0, 10), color: undefined },
          { label: "Held", value: `${daysHeld}d`, color: undefined },
        ].map(({ label, value, color }) => (
          <div key={label} className="shrink-0">
            <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-dim)", fontWeight: 500 }}>
              {label}
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "13px", fontWeight: 600, color: color ?? "var(--text-primary)" }}>
              {value}
            </div>
          </div>
        ))}
        {/* Progress bar — flex-1 */}
        <div className="flex-1 min-w-[80px]">
          <ProgressVisualization pos={pos} />
        </div>
      </div>

      {/* Chart — fills all remaining height */}
      <div className="flex-1 min-h-0 p-3">
        <CandlestickChart ticker={pos.ticker} range={range} position={pos} />
      </div>

      {showCompanyModal && (
        <CompanyInfoModal ticker={pos.ticker} onClose={() => setShowCompanyModal(false)} holdingValue={pos.market_value} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PositionDetailInfo — shown in the left column below PositionsPanel
// ---------------------------------------------------------------------------

export function PositionDetailInfo({ pos }: { pos: Position }) {
  const daysHeld = Math.floor(
    (Date.now() - new Date(pos.entry_date).getTime()) / (1000 * 60 * 60 * 24)
  );
  const [showCompanyModal, setShowCompanyModal] = useState(false);

  const pnlColor =
    pos.unrealized_pnl_pct > 0
      ? "var(--green)"
      : pos.unrealized_pnl_pct < 0
        ? "var(--red)"
        : "var(--text-3)";

  return (
    <div className="px-4 py-3">
      {/* Compact header: ticker + P&L% + SELL */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <button
            className="text-sm font-bold transition-colors"
            style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}
            onClick={() => setShowCompanyModal(true)}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
            title="Company info"
          >
            {pos.ticker}
          </button>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", fontWeight: 600, color: pnlColor }}>
            {pos.unrealized_pnl_pct >= 0 ? "+" : ""}
            {pos.unrealized_pnl_pct.toFixed(2)}%
          </span>
        </div>
        <SellButton pos={pos} />
      </div>

      {/* Stop/Target progress bar */}
      <ProgressVisualization pos={pos} />

      {/* Detail rows — 2-column compact grid */}
      <div className="grid grid-cols-2 gap-x-4 mt-2">
        <div className="space-y-0">
          <DetailRow label="Shares" value={`${pos.shares}`} />
          <DetailRow label="Avg Cost" value={`$${pos.avg_cost_basis.toFixed(2)}`} />
          <DetailRow label="Stop Loss" value={`$${pos.stop_loss.toFixed(2)}`} color="var(--red)" />
        </div>
        <div className="space-y-0">
          <DetailRow label="Entry Date" value={pos.entry_date.slice(0, 10)} />
          <DetailRow label="Days Held" value={`${daysHeld}`} />
          <DetailRow label="Take Profit" value={`$${pos.take_profit.toFixed(2)}`} color="var(--green)" />
        </div>
      </div>

      {showCompanyModal && (
        <CompanyInfoModal ticker={pos.ticker} onClose={() => setShowCompanyModal(false)} holdingValue={pos.market_value} />
      )}
    </div>
  );
}
