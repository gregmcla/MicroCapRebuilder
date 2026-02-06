/** Left panel — all positions in compact rows. */

import { useState } from "react";
import type { Position } from "../lib/types";

type SortKey = "pnl_pct" | "ticker" | "weight" | "entry_date";

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
  }
}

function ProgressBar({ pct }: { pct: number }) {
  // Progress from stop loss (0%) to take profit (100%)
  const clamped = Math.max(0, Math.min(100, pct));
  const color =
    clamped > 60 ? "bg-profit" : clamped > 30 ? "bg-accent" : "bg-loss";
  return (
    <div className="w-16 h-1.5 rounded-full bg-bg-primary overflow-hidden">
      <div
        className={`h-full rounded-full ${color}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

function PositionRow({ pos, totalValue }: { pos: Position; totalValue: number }) {
  const pnlColor =
    pos.unrealized_pnl_pct > 0
      ? "text-profit"
      : pos.unrealized_pnl_pct < 0
        ? "text-loss"
        : "text-text-primary";

  // Progress: 0% at stop loss, 100% at take profit
  const range = pos.take_profit - pos.stop_loss;
  const progress =
    range > 0 ? ((pos.current_price - pos.stop_loss) / range) * 100 : 50;

  const weight = totalValue > 0 ? (pos.market_value / totalValue) * 100 : 0;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-bg-elevated/50 transition-colors text-sm border-b border-border/50">
      <span className="font-semibold text-text-primary w-14 shrink-0">
        {pos.ticker}
      </span>
      <span className="font-mono text-text-secondary w-10 text-right shrink-0">
        {pos.shares}
      </span>
      <span className="font-mono text-text-muted w-16 text-right shrink-0">
        ${pos.current_price.toFixed(2)}
      </span>
      <span className={`font-mono w-16 text-right shrink-0 font-medium ${pnlColor}`}>
        {pos.unrealized_pnl_pct >= 0 ? "+" : ""}
        {pos.unrealized_pnl_pct.toFixed(1)}%
      </span>
      <ProgressBar pct={progress} />
      <span className="font-mono text-text-muted w-12 text-right shrink-0 text-xs">
        {weight.toFixed(1)}%
      </span>
    </div>
  );
}

export default function PositionsPanel({
  positions,
  totalValue,
}: {
  positions: Position[];
  totalValue: number;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("pnl_pct");

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
          <option value="ticker">Ticker</option>
          <option value="weight">Weight</option>
          <option value="entry_date">Entry</option>
        </select>
      </div>

      {/* Column headers */}
      <div className="flex items-center gap-2 px-3 py-1 text-[10px] text-text-muted uppercase tracking-wider border-b border-border/50">
        <span className="w-14">Ticker</span>
        <span className="w-10 text-right">Qty</span>
        <span className="w-16 text-right">Price</span>
        <span className="w-16 text-right">P&L</span>
        <span className="w-16">Progress</span>
        <span className="w-12 text-right">Wt</span>
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <div className="p-4 text-center text-text-muted text-sm">
            No positions
          </div>
        ) : (
          sorted.map((pos) => (
            <PositionRow
              key={pos.ticker}
              pos={pos}
              totalValue={totalValue}
            />
          ))
        )}
      </div>
    </div>
  );
}
