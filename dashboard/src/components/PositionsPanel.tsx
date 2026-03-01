/** Left panel — all positions in compact rows. */

import { useState } from "react";
import type { Position } from "../lib/types";
import { useUIStore } from "../lib/store";
import PositionRowSparkline from "./PositionRowSparkline";

type SortKey = "pnl_pct" | "ticker" | "weight" | "entry_date" | "day_change";

function sortPositions(positions: Position[], key: SortKey): Position[] {
  const sorted = [...positions];
  switch (key) {
    case "pnl_pct":
      return sorted.sort((a, b) => b.unrealized_pnl_pct - a.unrealized_pnl_pct);
    case "ticker":
      return sorted.sort((a, b) => a.ticker.localeCompare(b.ticker));
    case "weight":
      return sorted.sort((a, b) => b.market_value - a.market_value);
    case "entry_date":
      return sorted.sort((a, b) => b.entry_date.localeCompare(a.entry_date));
    case "day_change":
      return sorted.sort((a, b) => (b.day_change ?? 0) - (a.day_change ?? 0));
  }
}


function PositionRow({ pos, onClick, isSelected }: { pos: Position; onClick: () => void; isSelected: boolean }) {
  const pnlColor = pos.unrealized_pnl_pct > 0 ? "text-profit" : pos.unrealized_pnl_pct < 0 ? "text-loss" : "text-text-secondary";
  const dayColor = (pos.day_change ?? 0) > 0 ? "text-profit" : (pos.day_change ?? 0) < 0 ? "text-loss" : "text-text-muted";

  const range = pos.take_profit - pos.stop_loss;
  const progress = range > 0 ? ((pos.current_price - pos.stop_loss) / range) * 100 : 50;
  const dotColor = progress > 60 ? "#4ADE80" : progress > 30 ? "#FBBF24" : "#F87171";

  const dayTotalStr = pos.day_change != null
    ? pos.day_change >= 0 ? `+$${pos.day_change.toFixed(2)}` : `-$${Math.abs(pos.day_change).toFixed(2)}`
    : "--";
  const dayPctStr = pos.day_change_pct != null
    ? `${pos.day_change_pct >= 0 ? "+" : ""}${pos.day_change_pct.toFixed(1)}%`
    : "--";

  const overallPnlStr = pos.unrealized_pnl >= 0
    ? `+$${Math.round(pos.unrealized_pnl).toLocaleString("en-US")}`
    : `-$${Math.abs(Math.round(pos.unrealized_pnl)).toLocaleString("en-US")}`;
  const overallPnlPctStr = `${pos.unrealized_pnl_pct >= 0 ? "+" : ""}${pos.unrealized_pnl_pct.toFixed(1)}%`;

  return (
    <div
      onClick={onClick}
      className={`flex items-center h-8 px-3 gap-2 cursor-pointer transition-colors border-b ${
        isSelected ? "" : "hover:bg-[rgba(255,255,255,0.012)]"
      }`}
      style={{
        borderBottomColor: "var(--border-0)",
        backgroundColor: isSelected ? "rgba(124,92,252,0.03)" : undefined,
        boxShadow: isSelected ? "inset 3px 0 0 var(--accent)" : undefined,
      }}
    >
      {/* Ticker */}
      <span
        className="w-12 shrink-0 tabular-nums"
        style={{
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontWeight: 500,
          fontSize: "11px",
          color: "var(--text-3)",
        }}
      >
        {pos.ticker}
      </span>

      {/* Sparkline — stretches to fill dead space */}
      <div className="flex-1 min-w-0">
        <PositionRowSparkline ticker={pos.ticker} height={22} />
      </div>

      {/* Current price */}
      <span className="w-20 font-mono text-[13px] text-text-primary text-right tabular-nums shrink-0">
        ${pos.current_price.toFixed(2)}
      </span>

      {/* Day P&L — two lines */}
      <div className={`w-24 flex flex-col items-end justify-center shrink-0 ${dayColor}`}>
        <span className="font-mono text-[12px] tabular-nums leading-tight">{dayTotalStr}</span>
        <span className="font-mono text-[10px] tabular-nums leading-tight opacity-80">{dayPctStr}</span>
      </div>

      {/* Overall P&L — two lines */}
      <div className={`w-20 flex flex-col items-end justify-center shrink-0 ${pnlColor}`}>
        <span className="font-mono text-[12px] font-semibold tabular-nums leading-tight">{overallPnlStr}</span>
        <span className="font-mono text-[10px] tabular-nums leading-tight opacity-80">{overallPnlPctStr}</span>
      </div>

      {/* Mini range bar: stop → current → target */}
      <div className="w-9 flex items-center shrink-0">
        <div
          className="relative w-full h-[3px] rounded-full"
          style={{ background: "var(--surface-3)" }}
        >
          {/* Fill: stop → current */}
          <div
            className="absolute top-0 left-0 h-full rounded-full"
            style={{
              width: `${Math.max(0, Math.min(100, progress))}%`,
              background: dotColor,
              opacity: 0.3,
            }}
          />
          {/* Marker at current */}
          <div
            className="absolute top-1/2 -translate-y-1/2 w-[2px] h-[7px] rounded-full"
            style={{
              left: `calc(${Math.max(0, Math.min(100, progress))}% - 1px)`,
              background: dotColor,
            }}
          />
        </div>
      </div>
    </div>
  );
}

export default function PositionsPanel({
  positions,
  isLoading = false,
}: {
  positions: Position[];
  isLoading?: boolean;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("pnl_pct");

  const sorted = sortPositions(positions, sortKey);
  const selectedPosition = useUIStore((s) => s.selectedPosition);
  const selectPosition = useUIStore((s) => s.selectPosition);
  const toggleActivity = useUIStore((s) => s.toggleActivity);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-semibold text-text-secondary tracking-wider uppercase">
            Positions ({positions.length})
          </h2>
          <button
            onClick={toggleActivity}
            className="text-[10px] text-text-muted hover:text-text-secondary transition-colors uppercase tracking-wider"
            title="Activity Log"
          >
            LOG
          </button>
        </div>
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
          className="text-xs bg-bg-primary text-text-secondary border border-border rounded px-1.5 py-0.5 focus:outline-none focus:border-accent"
        >
          <option value="pnl_pct">P&L %</option>
          <option value="day_change">Day P&L</option>
          <option value="ticker">Ticker</option>
          <option value="weight">Weight</option>
          <option value="entry_date">Entry</option>
        </select>
      </div>

      {/* Column headers */}
      <div
        className="flex items-center gap-2 px-3 py-1 border-b"
        style={{ borderBottomColor: "var(--border-0)" }}
      >
        <span
          className="w-12"
          style={{
            fontFamily: "var(--font-sans, sans-serif)",
            fontSize: "9.5px",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-0)",
          }}
        >
          Ticker
        </span>
        <span
          className="flex-1"
          style={{
            fontFamily: "var(--font-sans, sans-serif)",
            fontSize: "9.5px",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-0)",
          }}
        >
          Trend
        </span>
        <span
          className="w-20 text-right"
          style={{
            fontFamily: "var(--font-sans, sans-serif)",
            fontSize: "9.5px",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-0)",
          }}
        >
          Price
        </span>
        <span
          className="w-24 text-right"
          style={{
            fontFamily: "var(--font-sans, sans-serif)",
            fontSize: "9.5px",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-0)",
          }}
        >
          Day P&L
        </span>
        <span
          className="w-20 text-right"
          style={{
            fontFamily: "var(--font-sans, sans-serif)",
            fontSize: "9.5px",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-0)",
          }}
        >
          P&L
        </span>
        <span className="w-9 shrink-0" />
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-px">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center h-8 px-3 gap-2 border-b"
                style={{ borderBottomColor: "var(--border-0)" }}
              >
                <div className="h-3 w-12 bg-bg-elevated rounded animate-pulse" />
                <div className="flex-1 h-3 bg-bg-elevated rounded animate-pulse" />
                <div className="h-3 w-20 bg-bg-elevated rounded animate-pulse" />
                <div className="h-4 w-24 bg-bg-elevated rounded animate-pulse" />
                <div className="h-4 w-20 bg-bg-elevated rounded animate-pulse" />
                <div className="w-9 flex items-center justify-center">
                  <div className="w-full h-[3px] rounded-full bg-bg-elevated animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        ) : sorted.length === 0 ? (
          <div className="p-4 text-center text-text-muted text-sm">
            No positions
          </div>
        ) : (
          sorted.map((pos, i) => (
            <div key={pos.ticker} className={i < 5 ? `anim d${i + 1}` : undefined}>
              <PositionRow
                pos={pos}
                isSelected={selectedPosition?.ticker === pos.ticker}
                onClick={() => selectPosition(selectedPosition?.ticker === pos.ticker ? null : pos)}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
