/** Left panel — positions list matching the mockup design.
 *  3-column rows: ticker (52px) | price (58px) | P&L (flex, right-aligned)
 *  Left border: 3px accent=selected, red=at-risk, transparent=normal
 */

import { useState } from "react";
import type { Position } from "../lib/types";
import { useUIStore } from "../lib/store";

type SortKey = "pnl_pct" | "ticker" | "weight" | "entry_date" | "day_change";

function sortPositions(positions: Position[], key: SortKey): Position[] {
  const arr = [...positions];
  switch (key) {
    case "pnl_pct":    return arr.sort((a, b) => b.unrealized_pnl_pct - a.unrealized_pnl_pct);
    case "ticker":     return arr.sort((a, b) => a.ticker.localeCompare(b.ticker));
    case "weight":     return arr.sort((a, b) => b.market_value - a.market_value);
    case "entry_date": return arr.sort((a, b) => b.entry_date.localeCompare(a.entry_date));
    case "day_change": return arr.sort((a, b) => (b.day_change_pct ?? 0) - (a.day_change_pct ?? 0));
  }
}

function isAtRisk(pos: Position): boolean {
  const range = pos.take_profit - pos.stop_loss;
  if (range <= 0) return false;
  const progress = ((pos.current_price - pos.stop_loss) / range) * 100;
  return progress < 30;
}

function PositionRow({
  pos,
  isSelected,
  isFlagged,
  onClick,
}: {
  pos: Position;
  isSelected: boolean;
  isFlagged: boolean;
  onClick: () => void;
}) {
  const pnlPct = pos.unrealized_pnl_pct;
  const pnlDollar = pos.unrealized_pnl;

  const pnlColor =
    pnlPct > 0 ? "var(--green)" : pnlPct < 0 ? "var(--red)" : "var(--text-secondary)";

  const leftBorderColor = isSelected
    ? "var(--accent)"
    : isFlagged
    ? "var(--red)"
    : "transparent";

  const pnlPctStr = `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(1)}%`;
  const pnlDolStr =
    pnlDollar >= 0
      ? `+$${Math.round(pnlDollar).toLocaleString("en-US")}`
      : `-$${Math.abs(Math.round(pnlDollar)).toLocaleString("en-US")}`;

  return (
    <div
      onClick={onClick}
      style={{
        display: "grid",
        gridTemplateColumns: "52px 58px 1fr",
        alignItems: "center",
        padding: "10px 16px",
        gap: 8,
        cursor: "pointer",
        borderLeft: `3px solid ${leftBorderColor}`,
        borderBottom: "1px solid var(--border)",
        backgroundColor: isSelected ? "var(--accent-dim)" : undefined,
        transition: "background 0.15s, border-left-color 0.15s",
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
      {/* Ticker */}
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontWeight: 600,
          fontSize: 12,
          color: isFlagged ? "var(--red)" : "var(--text-primary)",
          letterSpacing: "0.01em",
        }}
      >
        {pos.ticker}
      </span>

      {/* Price — right-aligned, muted */}
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--text-muted)",
          textAlign: "right",
        }}
      >
        ${pos.current_price.toFixed(2)}
      </span>

      {/* P&L — right-aligned: big % + small $ below */}
      <div style={{ textAlign: "right" }}>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            fontWeight: 600,
            color: pnlColor,
            lineHeight: 1.2,
          }}
        >
          {pnlPctStr}
        </div>
        <div
          style={{
            fontSize: 10,
            color: "var(--text-dim)",
            lineHeight: 1.2,
            marginTop: 1,
          }}
        >
          {pnlDolStr}
        </div>
      </div>
    </div>
  );
}

const SORT_LABELS: Record<SortKey, string> = {
  pnl_pct:    "P&L %",
  day_change: "Day",
  ticker:     "A–Z",
  weight:     "Size",
  entry_date: "Entry",
};

export default function PositionsPanel({
  positions,
  isLoading = false,
}: {
  positions: Position[];
  isLoading?: boolean;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("pnl_pct");
  const [sortMenuOpen, setSortMenuOpen] = useState(false);

  const sorted = sortPositions(positions, sortKey);
  const selectedPosition = useUIStore((s) => s.selectedPosition);
  const selectPosition = useUIStore((s) => s.selectPosition);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "transparent" }}>

      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-dim)",
            fontWeight: 600,
            fontFamily: "var(--font-sans)",
          }}
        >
          Positions ({positions.length})
        </span>

        {/* Sort button */}
        <div style={{ position: "relative" }}>
          <button
            onClick={() => setSortMenuOpen((o) => !o)}
            style={{
              fontSize: 10,
              color: "var(--text-dim)",
              cursor: "pointer",
              padding: "2px 6px",
              borderRadius: 4,
              background: "transparent",
              border: "none",
              transition: "all 0.15s",
              fontFamily: "var(--font-sans)",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "rgba(148,163,184,0.08)";
              (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "transparent";
              (e.currentTarget as HTMLButtonElement).style.color = "var(--text-dim)";
            }}
          >
            {SORT_LABELS[sortKey]} ▾
          </button>
          {sortMenuOpen && (
            <>
              <div
                style={{ position: "fixed", inset: 0, zIndex: 40 }}
                onClick={() => setSortMenuOpen(false)}
              />
              <div
                style={{
                  position: "absolute",
                  top: "100%",
                  right: 0,
                  zIndex: 50,
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  padding: "4px",
                  minWidth: 100,
                  marginTop: 4,
                }}
              >
                {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
                  <button
                    key={k}
                    onClick={() => { setSortKey(k); setSortMenuOpen(false); }}
                    style={{
                      display: "block",
                      width: "100%",
                      padding: "5px 10px",
                      textAlign: "left",
                      fontSize: 11,
                      color: k === sortKey ? "var(--text-primary)" : "var(--text-muted)",
                      background: k === sortKey ? "var(--accent-dim)" : "transparent",
                      border: "none",
                      borderRadius: 4,
                      cursor: "pointer",
                      fontFamily: "var(--font-sans)",
                    }}
                  >
                    {SORT_LABELS[k]}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Position rows */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {isLoading ? (
          // Skeleton rows
          Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              style={{
                display: "grid",
                gridTemplateColumns: "52px 58px 1fr",
                alignItems: "center",
                padding: "10px 16px",
                gap: 8,
                borderBottom: "1px solid var(--border)",
                borderLeft: "3px solid transparent",
              }}
            >
              <div style={{ height: 12, width: 36, borderRadius: 3, background: "var(--bg-elevated)", opacity: 0.6 }} />
              <div style={{ height: 11, width: 48, borderRadius: 3, background: "var(--bg-elevated)", opacity: 0.4, marginLeft: "auto" }} />
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3 }}>
                <div style={{ height: 12, width: 40, borderRadius: 3, background: "var(--bg-elevated)", opacity: 0.5 }} />
                <div style={{ height: 10, width: 32, borderRadius: 3, background: "var(--bg-elevated)", opacity: 0.3 }} />
              </div>
            </div>
          ))
        ) : sorted.length === 0 ? (
          <div
            style={{
              padding: 24,
              textAlign: "center",
              fontSize: 12,
              color: "var(--text-muted)",
              fontFamily: "var(--font-mono)",
              letterSpacing: "0.06em",
            }}
          >
            NO POSITIONS
          </div>
        ) : (
          sorted.map((pos) => (
            <PositionRow
              key={pos.ticker}
              pos={pos}
              isSelected={selectedPosition?.ticker === pos.ticker}
              isFlagged={isAtRisk(pos)}
              onClick={() =>
                selectPosition(
                  selectedPosition?.ticker === pos.ticker ? null : pos
                )
              }
            />
          ))
        )}
      </div>
    </div>
  );
}
