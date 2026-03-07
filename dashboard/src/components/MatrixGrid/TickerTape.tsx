import { useMemo } from "react";
import type { MatrixPosition } from "./types";

interface TickerTapeProps {
  positions: MatrixPosition[];
}

export default function TickerTape({ positions }: TickerTapeProps) {
  const items = useMemo(() => {
    return [...positions]
      .sort(() => Math.random() - 0.5)
      .slice(0, 40)
      .map((p) => ({ ticker: p.ticker, day: p.day, perf: p.perf, color: p.portfolioColor }));
  }, [positions]);

  const doubled = [...items, ...items];

  return (
    <div style={{
      overflow: "hidden", whiteSpace: "nowrap",
      background: "linear-gradient(90deg, #040608 0%, rgba(4,6,8,0) 4%, rgba(4,6,8,0) 96%, #040608 100%), rgba(74,222,128,0.015)",
      borderTop: "1px solid rgba(74,222,128,0.08)",
      borderBottom: "1px solid rgba(74,222,128,0.08)",
      padding: "5px 0",
      position: "relative",
    }}>
      {/* Scanline overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", zIndex: 1,
        background: "repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.06) 2px,rgba(0,0,0,0.06) 4px)",
      }} />
      <div style={{ display: "inline-block", animation: "matrixTicker 30s linear infinite" }}>
        {doubled.map((item, i) => {
          const pos = item.day > 0;
          const dayColor = pos ? "#4ade80" : "#f87171";
          const glow = pos ? "rgba(74,222,128,0.6)" : "rgba(248,113,113,0.6)";
          return (
            <span key={i} style={{ marginRight: 28, display: "inline-flex", alignItems: "baseline", gap: 5 }}>
              {/* Separator */}
              {i > 0 && (
                <span style={{ color: "rgba(74,222,128,0.12)", marginRight: 8, fontSize: 8 }}>◆</span>
              )}
              {/* Ticker in portfolio color */}
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                color: item.color,
                textShadow: `0 0 8px ${item.color}66`,
              }}>
                {item.ticker}
              </span>
              {/* Arrow */}
              <span style={{ fontSize: 8, color: dayColor, textShadow: `0 0 6px ${glow}` }}>
                {pos ? "▲" : "▼"}
              </span>
              {/* Day change */}
              <span style={{
                fontSize: 10, fontWeight: 600, letterSpacing: "0.04em",
                color: dayColor,
                textShadow: `0 0 10px ${glow}`,
              }}>
                {pos ? "+" : ""}{item.day.toFixed(2)}%
              </span>
              {/* All-time (dimmer) */}
              <span style={{ fontSize: 8, color: "rgba(255,255,255,0.2)", letterSpacing: "0.02em" }}>
                ({item.perf > 0 ? "+" : ""}{item.perf.toFixed(1)}%)
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
