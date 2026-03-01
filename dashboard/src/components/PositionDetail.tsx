/** Position detail — two exports:
 *  PositionDetailChart  → right FocusPane (chart view, SELL button, Back)
 *  PositionDetailInfo   → left column below PositionsPanel (compact trade details)
 */

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Position } from "../lib/types";
import { useUIStore, usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import CandlestickChart from "./CandlestickChart";

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
  const queryClient = useQueryClient();
  const selectPosition = useUIStore((s) => s.selectPosition);
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [showConfirm, setShowConfirm] = useState(false);
  const [selling, setSelling] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleSell = async () => {
    setSelling(true);
    setShowConfirm(false);
    try {
      const res = await api.sellPosition(portfolioId, pos.ticker);
      setResult(res.message);
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
      queryClient.invalidateQueries({ queryKey: ["chartData"] });
      setTimeout(() => {
        setResult(null);
        selectPosition(null);
      }, 3000);
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Sell failed");
      setTimeout(() => setResult(null), 5000);
    } finally {
      setSelling(false);
    }
  };

  const pnlColor = pos.unrealized_pnl >= 0 ? "var(--green)" : "var(--red)";

  return (
    <div className="relative">
      {/* Ghost-style SELL button with red tint */}
      <button
        onClick={() => setShowConfirm(true)}
        disabled={selling}
        className="px-3 py-1 rounded transition-colors disabled:opacity-50"
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
        {selling ? "Selling..." : "SELL"}
      </button>

      {result && (
        <span className="ml-2 text-xs" style={{ color: "var(--text-1)" }}>{result}</span>
      )}

      {showConfirm && (
        <div className="fixed inset-0 flex items-center justify-center z-50" style={{ background: "rgba(0,0,0,0.55)" }}>
          <div
            className="rounded-lg p-4 max-w-sm w-full"
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border-1)",
            }}
          >
            <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--text-4)" }}>
              Sell {pos.ticker}?
            </h3>
            <div
              className="rounded p-3 mb-3 space-y-1 text-xs"
              style={{ background: "var(--surface-2)" }}
            >
              <div className="flex justify-between">
                <span style={{ color: "var(--text-1)" }}>Shares</span>
                <span className="font-mono" style={{ color: "var(--text-3)" }}>{pos.shares}</span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: "var(--text-1)" }}>Price</span>
                <span className="font-mono" style={{ color: "var(--text-3)" }}>${pos.current_price.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: "var(--text-1)" }}>Value</span>
                <span className="font-mono" style={{ color: "var(--text-3)" }}>${pos.market_value.toFixed(2)}</span>
              </div>
              <div
                className="flex justify-between pt-1 mt-1"
                style={{ borderTop: "1px solid var(--border-1)" }}
              >
                <span style={{ color: "var(--text-1)" }}>P&L</span>
                <span className="font-mono font-semibold" style={{ color: pnlColor }}>
                  {pos.unrealized_pnl >= 0 ? "+" : ""}${pos.unrealized_pnl.toFixed(2)} ({pos.unrealized_pnl_pct >= 0 ? "+" : ""}{pos.unrealized_pnl_pct.toFixed(1)}%)
                </span>
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-3 py-1 rounded transition-colors text-xs font-semibold"
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
                className="px-3 py-1 rounded transition-colors text-xs font-semibold"
                style={{
                  border: "1px solid rgba(248,113,113,0.30)",
                  color: "rgba(248,113,113,0.80)",
                  background: "rgba(248,113,113,0.08)",
                }}
              >
                Confirm Sell
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PositionDetailChart — shown in the right FocusPane
// ---------------------------------------------------------------------------

export function PositionDetailChart({ pos }: { pos: Position }) {
  const clearSelection = useUIStore((s) => s.selectPosition);
  const [range, setRange] = useState("1M");

  const pnlColor =
    pos.unrealized_pnl_pct > 0
      ? "var(--green)"
      : pos.unrealized_pnl_pct < 0
        ? "var(--red)"
        : "var(--text-3)";

  const daysHeld = Math.floor(
    (Date.now() - new Date(pos.entry_date).getTime()) / (1000 * 60 * 60 * 24)
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2 shrink-0"
        style={{ borderBottom: "1px solid var(--border-0)" }}
      >
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold" style={{ color: "var(--text-4)" }}>{pos.ticker}</h2>
          <span className="font-mono text-sm font-semibold" style={{ color: pnlColor }}>
            {pos.unrealized_pnl_pct >= 0 ? "+" : ""}
            {pos.unrealized_pnl_pct.toFixed(2)}%
          </span>
        </div>
        <div className="flex items-center gap-2">
          <SellButton pos={pos} />
          <button
            onClick={() => clearSelection(null)}
            className="text-xs rounded transition-colors px-2 py-1"
            style={{
              color: "var(--text-1)",
              border: "1px solid var(--border-1)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "var(--accent)";
              e.currentTarget.style.color = "var(--accent)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "var(--border-1)";
              e.currentTarget.style.color = "var(--text-1)";
            }}
          >
            Back
          </button>
        </div>
      </div>

      {/* Stat strip */}
      <div
        className="flex items-center gap-5 px-4 py-2 shrink-0 flex-wrap"
        style={{ borderBottom: "1px solid var(--border-0)", background: "var(--surface-0)" }}
      >
        {[
          { label: "Shares", value: String(pos.shares), color: undefined },
          { label: "Avg Cost", value: `$${pos.avg_cost_basis.toFixed(2)}`, color: undefined },
          { label: "Stop", value: `$${pos.stop_loss.toFixed(2)}`, color: "var(--red)" },
          { label: "Target", value: `$${pos.take_profit.toFixed(2)}`, color: "var(--green)" },
          { label: "Entry", value: pos.entry_date.slice(0, 10), color: undefined },
          { label: "Days", value: String(daysHeld), color: undefined },
        ].map(({ label, value, color }) => (
          <div key={label}>
            <div style={{ fontSize: "9.5px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-0)" }}>
              {label}
            </div>
            <div className="font-mono text-xs font-semibold" style={{ color: color ?? "var(--text-3)" }}>
              {value}
            </div>
          </div>
        ))}
        {/* Progress bar — stop→current→target */}
        <div className="flex-1 min-w-[120px]">
          <ProgressVisualization pos={pos} />
        </div>
      </div>

      {/* P&L summary cards — shrink-0 */}
      <div className="grid grid-cols-2 gap-3 px-4 pt-3 shrink-0">
        <div
          className="rounded-lg p-3"
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border-0)",
            borderRadius: "8px",
          }}
        >
          <p
            className="uppercase tracking-wider mb-0.5"
            style={{ fontSize: "9.5px", color: "var(--text-0)" }}
          >
            Unrealized P&L
          </p>
          <p className="font-mono text-lg font-bold" style={{ color: pnlColor }}>
            {pos.unrealized_pnl >= 0 ? "+" : ""}${pos.unrealized_pnl.toFixed(2)}
          </p>
        </div>
        <div
          className="rounded-lg p-3"
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border-0)",
            borderRadius: "8px",
          }}
        >
          <p
            className="uppercase tracking-wider mb-0.5"
            style={{ fontSize: "9.5px", color: "var(--text-0)" }}
          >
            Market Value
          </p>
          <p className="font-mono text-lg font-bold" style={{ color: "var(--text-3)" }}>
            ${pos.market_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
        </div>
      </div>

      {/* Time Range Selector — shrink-0 */}
      <div className="flex gap-1 px-4 py-2 shrink-0">
        {['1D', '5D', '1M', '3M', 'YTD', 'ALL'].map((r) => (
          <button
            key={r}
            onClick={() => setRange(r)}
            className="px-2 py-1 text-xs rounded transition-colors"
            style={
              range === r
                ? {
                    color: "var(--accent)",
                    background: "rgba(124,92,252,0.12)",
                    border: "1px solid var(--border-2)",
                    fontWeight: 600,
                  }
                : {
                    color: "var(--text-1)",
                    background: "transparent",
                    border: "1px solid var(--border-1)",
                    }
              }
            >
              {r}
            </button>
          ))}
      </div>

      {/* Candlestick Chart — flex-1, fills remaining height */}
      <div className="flex-1 min-h-0 px-4 pb-4">
        <CandlestickChart ticker={pos.ticker} range={range} position={pos} />
      </div>
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
          <span className="text-sm font-bold" style={{ color: "var(--text-4)" }}>{pos.ticker}</span>
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
    </div>
  );
}
