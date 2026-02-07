/** Left panel — all positions in compact rows. */

import { useState } from "react";
import type { Position } from "../lib/types";
import { useUIStore } from "../lib/store";
import PositionRowSparkline from "./PositionRowSparkline";

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

function PositionRow({ pos, onClick }: { pos: Position; onClick: () => void }) {
  const pnlColor =
    pos.unrealized_pnl_pct > 0
      ? "text-green-400"
      : pos.unrealized_pnl_pct < 0
        ? "text-red-400"
        : "text-white";

  // Progress: 0% at stop loss, 100% at take profit
  const range = pos.take_profit - pos.stop_loss;
  const progress =
    range > 0 ? ((pos.current_price - pos.stop_loss) / range) * 100 : 50;

  // Calculate days held
  const daysHeld = Math.floor(
    (Date.now() - new Date(pos.entry_date).getTime()) / (1000 * 60 * 60 * 24)
  );

  // Calculate annualized return (APR)
  const pnlPct = pos.unrealized_pnl_pct ?? 0;
  const apr = daysHeld > 0
    ? (pnlPct / daysHeld) * 365
    : 0;

  const aprColor = apr > 100 ? "text-purple-400" : pnlColor;

  return (
    <div onClick={onClick} className="group px-3 py-2 cursor-pointer hover:bg-bg-elevated/50 hover:shadow-[0_0_12px_rgba(34,211,238,0.4)] transition-all border-b border-border/50">
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
          <span className="font-mono text-sm text-text-primary">
            ${pos.current_price.toFixed(2)}
          </span>
          <span className="font-mono text-[10px] text-text-muted">
            (Entry: ${pos.avg_cost_basis.toFixed(2)})
          </span>
        </div>

        <span className={`font-mono text-sm font-semibold ${pnlColor} w-16 text-right`}>
          {(pos.unrealized_pnl_pct ?? 0) >= 0 ? "+" : ""}
          {(pos.unrealized_pnl_pct ?? 0).toFixed(1)}%
        </span>

        <span className={`font-mono text-xs ${aprColor} text-right w-16`}>
          {(apr ?? 0) >= 0 ? "+" : ""}
          {(apr ?? 0).toFixed(0)}% APR
        </span>

        <span className="font-mono text-xs text-gray-400 text-right w-10">
          {daysHeld ?? 0}d
        </span>
      </div>

      <ProgressBar pct={progress} />
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
        <span className="w-16 text-right">APR</span>
        <span className="w-10 text-right">Days</span>
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
              onClick={() => selectPosition(pos)}
            />
          ))
        )}
      </div>
    </div>
  );
}
