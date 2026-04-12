/** Left panel — all positions in compact rows. */

import { useState } from "react";
import type { Position } from "../lib/types";
import { useUIStore } from "../lib/store";

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

const colLabelStyle: React.CSSProperties = {
  fontFamily: "var(--font-sans, sans-serif)",
  fontSize: "9.5px",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "var(--text-dim)",
  fontWeight: 600,
};

function PositionRow({
  pos,
  onClick,
  isSelected,
  isFlagged = false,
}: {
  pos: Position;
  onClick: () => void;
  isSelected: boolean;
  isFlagged?: boolean;
}) {
  const pnlColor =
    pos.unrealized_pnl_pct > 0
      ? "var(--green)"
      : pos.unrealized_pnl_pct < 0
      ? "var(--red)"
      : "var(--text-secondary)";

  const dayColor =
    (pos.day_change ?? 0) > 0
      ? "var(--green)"
      : (pos.day_change ?? 0) < 0
      ? "var(--red)"
      : "var(--text-muted)";

  const range = pos.take_profit - pos.stop_loss;
  const progress = range > 0 ? ((pos.current_price - pos.stop_loss) / range) * 100 : 50;
  const dotColor =
    progress > 60 ? "var(--green)" : progress > 30 ? "#FBBF24" : "var(--red)";

  const dayTotalStr =
    pos.day_change != null
      ? pos.day_change >= 0
        ? `+$${pos.day_change.toFixed(2)}`
        : `-$${Math.abs(pos.day_change).toFixed(2)}`
      : "--";
  const dayPctStr =
    pos.day_change_pct != null
      ? `${pos.day_change_pct >= 0 ? "+" : ""}${pos.day_change_pct.toFixed(2)}%`
      : "";

  const overallPnlStr =
    pos.unrealized_pnl >= 0
      ? `+$${Math.round(pos.unrealized_pnl).toLocaleString("en-US")}`
      : `-$${Math.abs(Math.round(pos.unrealized_pnl)).toLocaleString("en-US")}`;
  const overallPnlPctStr = `${pos.unrealized_pnl_pct >= 0 ? "+" : ""}${pos.unrealized_pnl_pct.toFixed(1)}%`;

  // Left border: accent when selected, red when flagged, transparent otherwise
  const leftBorderColor = isSelected
    ? "var(--accent)"
    : isFlagged
    ? "var(--red)"
    : "transparent";

  return (
    <div
      onClick={onClick}
      className="flex items-center h-8 px-2 gap-1.5 cursor-pointer transition-colors border-b"
      style={{
        borderBottomColor: "var(--border)",
        borderLeft: `3px solid ${leftBorderColor}`,
        backgroundColor: isSelected ? "var(--accent-dim)" : undefined,
      }}
      onMouseEnter={(e) => {
        if (!isSelected) {
          (e.currentTarget as HTMLDivElement).style.backgroundColor =
            "rgba(148,163,184,0.04)";
        }
      }}
      onMouseLeave={(e) => {
        if (!isSelected) {
          (e.currentTarget as HTMLDivElement).style.backgroundColor = "";
        }
      }}
    >
      {/* Ticker — w-11 (44px) */}
      <span
        className="w-11 shrink-0 tabular-nums"
        style={{
          fontFamily: "var(--font-mono)",
          fontWeight: 600,
          fontSize: "12px",
          color: "var(--text-primary)",
        }}
      >
        {pos.ticker}
      </span>

      {/* Price — w-16 (64px) */}
      <span
        className="w-16 text-right tabular-nums shrink-0"
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
          color: "var(--text-muted)",
        }}
      >
        ${pos.current_price.toFixed(2)}
      </span>

      {/* Day P&L — w-[68px] two lines */}
      <div
        className="w-[68px] flex flex-col items-end justify-center shrink-0"
        style={{ color: dayColor }}
      >
        <span
          className="tabular-nums leading-tight"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          {dayTotalStr}
        </span>
        {dayPctStr && (
          <span
            className="tabular-nums leading-tight opacity-80"
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "10px",
            }}
          >
            {dayPctStr}
          </span>
        )}
      </div>

      {/* Overall P&L — w-[68px] two lines */}
      <div
        className="w-[68px] flex flex-col items-end justify-center shrink-0"
        style={{ color: pnlColor }}
      >
        <span
          className="tabular-nums leading-tight"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          {overallPnlStr}
        </span>
        <span
          className="tabular-nums leading-tight"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "10px",
            color: "var(--text-dim)",
          }}
        >
          {overallPnlPctStr}
        </span>
      </div>

      {/* Mini range bar: stop → current → target — w-8 (32px) */}
      <div className="w-8 flex items-center shrink-0">
        <div
          className="relative w-full h-[3px] rounded-full"
          style={{ background: "var(--bg-elevated)" }}
        >
          <div
            className="absolute top-0 left-0 h-full rounded-full"
            style={{
              width: `${Math.max(0, Math.min(100, progress))}%`,
              background: dotColor,
              opacity: 0.3,
            }}
          />
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
  flaggedTickers = [],
}: {
  positions: Position[];
  isLoading?: boolean;
  flaggedTickers?: string[];
}) {
  const [sortKey, setSortKey] = useState<SortKey>("pnl_pct");

  const sorted = sortPositions(positions, sortKey);
  const selectedPosition = useUIStore((s) => s.selectedPosition);
  const selectPosition = useUIStore((s) => s.selectPosition);
  const toggleActivity = useUIStore((s) => s.toggleActivity);

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--bg-surface)" }}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-2 py-2"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <h2
            style={{
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--text-dim)",
              fontWeight: 600,
              fontFamily: "var(--font-sans)",
            }}
          >
            Positions ({positions.length})
          </h2>
          <button
            onClick={toggleActivity}
            className="transition-colors"
            title="Activity Log"
            style={{
              fontSize: 10,
              color: "var(--text-dim)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.color = "var(--text-dim)";
            }}
          >
            LOG
          </button>
        </div>
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
          className="bg-transparent border rounded px-1.5 py-0.5 focus:outline-none"
          style={{
            fontSize: 10,
            color: "var(--text-dim)",
            borderColor: "var(--border)",
          }}
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
        className="flex items-center gap-1.5 px-2 py-1"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <span className="w-11" style={colLabelStyle}>Ticker</span>
        <span className="w-16 text-right" style={colLabelStyle}>Price</span>
        <span className="w-[60px] text-right" style={colLabelStyle}>Day</span>
        <span className="w-[68px] text-right" style={colLabelStyle}>P&L</span>
        <span className="w-8 shrink-0" />
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-px">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center h-8 px-2 gap-1.5"
                style={{ borderBottom: "1px solid var(--border)" }}
              >
                <div
                  className="h-3 w-11 rounded animate-pulse"
                  style={{ background: "var(--bg-elevated)" }}
                />
                <div
                  className="h-3 w-16 rounded animate-pulse"
                  style={{ background: "var(--bg-elevated)" }}
                />
                <div
                  className="h-3 w-[60px] rounded animate-pulse"
                  style={{ background: "var(--bg-elevated)" }}
                />
                <div
                  className="h-4 w-[68px] rounded animate-pulse"
                  style={{ background: "var(--bg-elevated)" }}
                />
                <div className="w-8 flex items-center justify-center">
                  <div
                    className="w-full h-[3px] rounded-full animate-pulse"
                    style={{ background: "var(--bg-elevated)" }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : sorted.length === 0 ? (
          <div
            className="p-4 text-center text-sm"
            style={{ color: "var(--text-muted)" }}
          >
            No positions
          </div>
        ) : (
          sorted.map((pos, i) => (
            <div key={pos.ticker} className={i < 5 ? `anim d${i + 1}` : undefined}>
              <PositionRow
                pos={pos}
                isSelected={selectedPosition?.ticker === pos.ticker}
                isFlagged={flaggedTickers.includes(pos.ticker)}
                onClick={() =>
                  selectPosition(selectedPosition?.ticker === pos.ticker ? null : pos)
                }
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
