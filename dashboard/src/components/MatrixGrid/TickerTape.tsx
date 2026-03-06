import { useMemo } from "react";
import type { MatrixPosition } from "./types";

interface TickerTapeProps {
  positions: MatrixPosition[];
}

export default function TickerTape({ positions }: TickerTapeProps) {
  const items = useMemo(() => {
    return [...positions]
      .sort(() => Math.random() - 0.5)
      .slice(0, 30)
      .map((p) => ({ ticker: p.ticker, day: p.day, color: p.portfolioColor }));
  }, [positions]);

  return (
    <div style={{
      overflow: "hidden", whiteSpace: "nowrap",
      borderTop: "1px solid rgba(74,222,128,0.04)",
      borderBottom: "1px solid rgba(74,222,128,0.04)",
      padding: "4px 0",
    }}>
      <div style={{ display: "inline-block", animation: "matrixTicker 40s linear infinite" }}>
        {[...items, ...items].map((item, i) => (
          <span key={i} style={{
            fontSize: 9, letterSpacing: "0.04em", marginRight: 20,
            color: item.day >= 0 ? "#4ade8088" : "#f8717188",
            
          }}>
            <span style={{ color: "#333", marginRight: 4 }}>{item.ticker}</span>
            {item.day >= 0 ? "▲" : "▼"} {item.day >= 0 ? "+" : ""}{item.day.toFixed(2)}%
          </span>
        ))}
      </div>
    </div>
  );
}
