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


function PositionRow({ pos, onClick }: { pos: Position; onClick: () => void }) {
  const pnlColor =
    pos.unrealized_pnl_pct > 0
      ? "text-profit"
      : pos.unrealized_pnl_pct < 0
        ? "text-loss"
        : "text-white";

  // Progress: 0% at stop loss, 100% at take profit
  const range = pos.take_profit - pos.stop_loss;
  const progress =
    range > 0 ? ((pos.current_price - pos.stop_loss) / range) * 100 : 50;

  // Calculate days held
  const daysHeld = Math.floor(
    (Date.now() - new Date(pos.entry_date).getTime()) / (1000 * 60 * 60 * 24)
  );

  // Day change
  const dayChange = pos.day_change ?? 0;
  const dayChangePct = pos.day_change_pct ?? 0;
  const dayColor =
    dayChange > 0
      ? "text-profit"
      : dayChange < 0
        ? "text-loss"
        : "text-text-muted";

  return (
    <div
      onClick={onClick}
      className="group px-3 py-2 cursor-pointer hover:bg-bg-elevated transition-colors"
      style={{ borderBottom: `1px solid ${progress > 60 ? 'rgba(0,212,136,0.5)' : progress > 30 ? '#1E1E1E' : 'rgba(255,68,88,0.4)'}` }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="font-bold text-sm text-text-primary w-14">
          {pos.ticker}
        </span>

        <div className="flex-1">
          <PositionRowSparkline ticker={pos.ticker} />
        </div>

        <span className="font-mono text-xs text-gray-400 text-right w-10">
          {pos.shares}
        </span>

        <div className="flex flex-col items-end w-20">
          <span className="font-mono text-sm text-text-primary tabular-nums">
            ${pos.current_price.toFixed(2)}
          </span>
          <span className="font-mono text-[10px] text-text-muted tabular-nums">
            (Entry: ${pos.avg_cost_basis.toFixed(2)})
          </span>
        </div>

        <span className={`font-mono text-sm font-semibold tabular-nums ${pnlColor} w-16 text-right`}>
          {(pos.unrealized_pnl_pct ?? 0) >= 0 ? "+" : ""}
          {(pos.unrealized_pnl_pct ?? 0).toFixed(1)}%
        </span>

        <div className={`flex flex-col items-end w-20 ${dayColor}`}>
          <span className="font-mono text-xs font-semibold tabular-nums">
            {dayChange >= 0 ? "+" : ""}${dayChange.toFixed(0)}
          </span>
          <span className="font-mono text-[10px] tabular-nums">
            {dayChangePct >= 0 ? "+" : ""}{dayChangePct.toFixed(1)}%
          </span>
        </div>

        <span className="font-mono text-xs text-gray-400 text-right w-10">
          {daysHeld ?? 0}d
        </span>
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
  const selectPosition = useUIStore((s) => s.selectPosition);

  const sorted = sortPositions(positions, sortKey);

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
      <div className="flex items-center gap-2 px-3 py-1 text-[10px] text-text-muted uppercase tracking-wider border-b border-border/50">
        <span className="w-14">Ticker</span>
        <span className="flex-1">Trend</span>
        <span className="w-10 text-right">Qty</span>
        <span className="w-20 text-right">Price</span>
        <span className="w-16 text-right">P&L</span>
        <span className="w-20 text-right">Day</span>
        <span className="w-10 text-right">Days</span>
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-px">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-3 py-2 border-b border-border/50 animate-pulse">
                <div className="flex items-center gap-2 mb-1">
                  <div className="h-4 w-14 bg-bg-elevated rounded" />
                  <div className="flex-1 h-[30px] bg-bg-elevated rounded" />
                  <div className="h-4 w-10 bg-bg-elevated rounded" />
                  <div className="h-4 w-20 bg-bg-elevated rounded" />
                  <div className="h-4 w-16 bg-bg-elevated rounded" />
                  <div className="h-4 w-20 bg-bg-elevated rounded" />
                  <div className="h-4 w-10 bg-bg-elevated rounded" />
                </div>
                <div className="h-1.5 w-full bg-bg-elevated rounded-full" />
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
              onClick={() => selectPosition(pos)}
            />
          ))
        )}
      </div>
    </div>
  );
}
