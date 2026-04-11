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
      style={{ borderBottom: "1px solid var(--border-0)" }}
    >
      <span className="text-xs" style={{ color: "var(--text-1)" }}>{label}</span>
      <span
        className="font-mono text-sm"
        style={{ color: color ? undefined : "var(--text-3)" }}
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
        style={{ fontSize: "10px", color: "var(--text-1)" }}
      >
        <span>Stop ${pos.stop_loss.toFixed(2)}</span>
        <span>Target ${pos.take_profit.toFixed(2)}</span>
      </div>
      <div
        className="relative h-3 rounded-full overflow-hidden"
        style={{ background: "var(--surface-2)" }}
      >
        {/* Danger zone (0-20%) */}
        <div
          className="absolute left-0 top-0 h-full w-[20%] rounded-l-full"
          style={{ background: "rgba(248,113,113,0.10)" }}
        />
        {/* Target zone (80-100%) */}
        <div
          className="absolute right-0 top-0 h-full w-[20%] rounded-r-full"
          style={{ background: "rgba(52,211,153,0.10)" }}
        />
        {/* Current price marker — accent fill */}
        <div
          className="absolute top-0 h-full w-1.5 rounded-full"
          style={{
            left: `calc(${clamped}% - 3px)`,
            background: "var(--accent)",
            boxShadow: "0 0 6px rgba(124,92,252,0.5)",
          }}
        />
      </div>
      <div className="flex justify-between mt-1" style={{ fontSize: "10px" }}>
        <span style={{ color: "var(--red)" }}>
          {((pos.stop_loss / pos.current_price - 1) * 100).toFixed(1)}%
        </span>
        <span className="font-mono" style={{ color: "var(--accent)" }}>
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
          border: "1px solid rgba(248,113,113,0.30)",
          color: "rgba(248,113,113,0.70)",
          background: "transparent",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "rgba(248,113,113,0.08)";
          e.currentTarget.style.borderColor = "rgba(248,113,113,0.50)";
          e.currentTarget.style.color = "var(--red)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.borderColor = "rgba(248,113,113,0.30)";
          e.currentTarget.style.color = "rgba(248,113,113,0.70)";
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
    <div className="flex flex-col h-full">

      {/* Row 1 — hero header */}
      <div
        className="flex items-center justify-between px-4 shrink-0"
        style={{ borderBottom: "1px solid var(--border-0)", minHeight: "52px" }}
      >
        {/* Left: ticker + company name + P&L numbers */}
        <div className="flex items-baseline gap-3">
          <button
            className="flex flex-col leading-none text-left group"
            onClick={() => setShowCompanyModal(true)}
            title="Company info"
          >
            <span
              className="font-mono font-bold transition-colors group-hover:text-accent"
              style={{ fontSize: "22px", color: "var(--text-4)", letterSpacing: "-0.01em" }}
            >
              {pos.ticker}
            </span>
            <span style={{ fontSize: "11px", color: "var(--text-1)", marginTop: "2px" }}>
              {tickerInfo?.name && tickerInfo.name !== pos.ticker ? tickerInfo.name : "View company info"}
            </span>
          </button>
          <span className="font-mono text-base font-semibold" style={{ color: pnlColor }}>
            {pos.unrealized_pnl_pct >= 0 ? "+" : ""}{pos.unrealized_pnl_pct.toFixed(2)}%
          </span>
          <span className="font-mono text-base font-semibold" style={{ color: pnlColor }}>
            {pos.unrealized_pnl >= 0 ? "+" : ""}${pos.unrealized_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
          {dayStr && (
            <>
              <span style={{ color: "var(--border-2)" }}>·</span>
              <span className="font-mono text-sm" style={{ color: dayColor }}>{dayStr} today</span>
            </>
          )}
          <span style={{ color: "var(--border-2)" }}>·</span>
          <span className="font-mono text-sm" style={{ color: "var(--text-1)" }}>
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
                    ? { color: "var(--accent)", background: "rgba(124,92,252,0.12)", border: "1px solid var(--border-2)", fontWeight: 600 }
                    : { color: "var(--text-1)", background: "transparent", border: "1px solid var(--border-1)" }
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
            style={{ color: "var(--text-1)", border: "1px solid var(--border-1)" }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.color = "var(--accent)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-1)"; e.currentTarget.style.color = "var(--text-1)"; }}
          >
            Back
          </button>
        </div>
      </div>

      {/* Row 2 — stat chips + progress bar */}
      <div
        className="flex items-center gap-5 px-4 shrink-0"
        style={{ borderBottom: "1px solid var(--border-0)", background: "var(--surface-0)", minHeight: "44px" }}
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
            <div style={{ fontSize: "9.5px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)" }}>
              {label}
            </div>
            <div className="font-mono text-sm font-semibold" style={{ color: color ?? "var(--text-3)" }}>
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
            style={{ color: "var(--text-4)" }}
            onClick={() => setShowCompanyModal(true)}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-4)"; }}
            title="Company info"
          >
            {pos.ticker}
          </button>
          <span className="font-mono text-xs font-semibold" style={{ color: pnlColor }}>
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
