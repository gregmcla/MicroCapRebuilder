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
  const dotColor = progress > 60 ? "#4ADE80" : progress > 30 ? "#282828" : "#F87171";

  const dayChangeStr = pos.day_change != null
    ? pos.day_change >= 0
      ? `+$${pos.day_change.toFixed(2)}`
      : `-$${Math.abs(pos.day_change).toFixed(2)}`
    : "--";
  const dayChangePctStr = pos.day_change_pct != null
    ? `${pos.day_change_pct >= 0 ? "+" : ""}${pos.day_change_pct.toFixed(1)}%`
    : "--";

  const dayPnlVal = (pos.day_change ?? 0) * pos.shares;
  const dayPnlStr = dayPnlVal >= 0
    ? `+$${dayPnlVal.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : `-$${Math.abs(dayPnlVal).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const overallPnlStr = pos.unrealized_pnl >= 0
    ? `+$${Math.round(pos.unrealized_pnl).toLocaleString("en-US")}`
    : `-$${Math.abs(Math.round(pos.unrealized_pnl)).toLocaleString("en-US")}`;
  const overallPnlPctStr = `${pos.unrealized_pnl_pct >= 0 ? "+" : ""}${pos.unrealized_pnl_pct.toFixed(1)}%`;

  return (
    <div
      onClick={onClick}
      className={`flex items-center h-10 px-3 gap-2 cursor-pointer transition-colors ${
        isSelected
          ? "bg-bg-elevated border-l-2 border-accent"
          : "hover:bg-bg-elevated border-l-2 border-transparent"
      }`}
    >
      {/* Ticker */}
      <span className="w-12 font-mono text-[13px] font-bold text-text-primary shrink-0">
        {pos.ticker}
      </span>

      {/* Sparkline */}
      <div className="flex-1 min-w-0">
        <PositionRowSparkline ticker={pos.ticker} height={28} />
      </div>

      {/* Entry price */}
      <span className="w-16 font-mono text-[11px] text-text-muted text-right tabular-nums shrink-0">
        ${pos.avg_cost_basis.toFixed(2)}
      </span>

      {/* Current price */}
      <span className="w-16 font-mono text-[13px] text-text-primary text-right tabular-nums shrink-0">
        ${pos.current_price.toFixed(2)}
      </span>

      {/* Day change — two lines */}
      <div className={`w-24 flex flex-col items-end justify-center shrink-0 ${dayColor}`}>
        <span className="font-mono text-[12px] tabular-nums leading-tight">{dayChangeStr}</span>
        <span className="font-mono text-[10px] tabular-nums leading-tight opacity-80">{dayChangePctStr}</span>
      </div>

      {/* Day P&L $ */}
      <span className={`w-16 font-mono text-[12px] text-right tabular-nums shrink-0 ${
        dayPnlVal > 0 ? "text-profit" : dayPnlVal < 0 ? "text-loss" : "text-text-muted"
      }`}>
        {dayPnlStr}
      </span>

      {/* Overall P&L — two lines */}
      <div className={`w-20 flex flex-col items-end justify-center shrink-0 ${pnlColor}`}>
        <span className="font-mono text-[12px] font-semibold tabular-nums leading-tight">{overallPnlStr}</span>
        <span className="font-mono text-[10px] tabular-nums leading-tight opacity-80">{overallPnlPctStr}</span>
      </div>

      {/* Dot */}
      <div className="w-3 flex items-center justify-center shrink-0">
        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: dotColor }} />
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

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <h2 className="text-xs font-semibold text-text-secondary tracking-wider uppercase">
          Positions ({positions.length})
        </h2>
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
      <div className="flex items-center gap-2 px-3 py-1 text-[10px] text-text-muted uppercase tracking-wider border-b border-border">
        <span className="w-12">Ticker</span>
        <span className="flex-1">Trend</span>
        <span className="w-16 text-right">Entry</span>
        <span className="w-16 text-right">Price</span>
        <span className="w-24 text-right">Day Chg</span>
        <span className="w-16 text-right">Day P&L</span>
        <span className="w-20 text-right">P&L</span>
        <span className="w-3" />
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-px">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center h-10 px-3 gap-2 border-l-2 border-transparent">
                <div className="h-3 w-12 bg-bg-elevated rounded animate-pulse" />
                <div className="flex-1 h-4 bg-bg-elevated rounded animate-pulse" />
                <div className="h-3 w-16 bg-bg-elevated rounded animate-pulse" />
                <div className="h-3 w-16 bg-bg-elevated rounded animate-pulse" />
                <div className="h-6 w-24 bg-bg-elevated rounded animate-pulse" />
                <div className="h-3 w-16 bg-bg-elevated rounded animate-pulse" />
                <div className="h-6 w-20 bg-bg-elevated rounded animate-pulse" />
                <div className="w-3 flex items-center justify-center">
                  <div className="w-1.5 h-1.5 rounded-full bg-bg-elevated animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        ) : sorted.length === 0 ? (
          <div className="p-4 text-center text-text-muted text-sm">
            No positions
          </div>
        ) : (
          sorted.map((pos) => (
            <PositionRow
              key={pos.ticker}
              pos={pos}
              isSelected={selectedPosition?.ticker === pos.ticker}
              onClick={() => selectPosition(selectedPosition?.ticker === pos.ticker ? null : pos)}
            />
          ))
        )}
      </div>
    </div>
  );
}
