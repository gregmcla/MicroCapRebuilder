/**
 * WatchlistPanel — extracted from MatrixGrid.tsx (Fix 18).
 *
 * Pure presentational: takes scored watchlist candidates + a ticker click
 * handler. No hooks, no context. Sorts candidates by score descending and
 * renders a 7-column grid (ticker / notes / score / sector / source / added /
 * heat). Empty state shows "RUN SCAN TO POPULATE".
 *
 * The HEAT_COLOR map and MATRIX_FONT constant live in ./constants now so this
 * file doesn't depend on MatrixGrid.tsx internals.
 */
import { HEAT_COLOR, MATRIX_FONT } from "./constants";
import type { WatchlistCandidate } from "./types";

export function WatchlistPanel({
  candidates,
  onTickerClick,
}: {
  candidates: WatchlistCandidate[];
  onTickerClick: (ticker: string) => void;
}) {
  const sorted = [...candidates].sort((a, b) => b.score - a.score);
  if (sorted.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#555",
          fontSize: 10,
          fontFamily: MATRIX_FONT,
          letterSpacing: "0.1em",
        }}
      >
        NO WATCHLIST DATA — RUN SCAN TO POPULATE
      </div>
    );
  }
  return (
    <div style={{ flex: 1, overflow: "auto", minHeight: 0 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "80px 1fr 60px 80px 120px 65px 80px",
          padding: "5px 20px",
          fontSize: 9,
          color: "#444",
          letterSpacing: "0.09em",
          borderBottom: "1px solid rgba(74,222,128,0.04)",
          position: "sticky",
          top: 0,
          background: "#040608",
          zIndex: 2,
        }}
      >
        <span>TICKER</span>
        <span>NOTES</span>
        <span>SCORE</span>
        <span>SECTOR</span>
        <span>SOURCE</span>
        <span>ADDED</span>
        <span>HEAT</span>
      </div>
      {sorted.map((c, i) => (
        <div
          key={`${c.ticker}-${i}`}
          style={{
            display: "grid",
            gridTemplateColumns: "80px 1fr 60px 80px 120px 65px 80px",
            padding: "5px 20px",
            borderBottom: "1px solid rgba(255,255,255,0.02)",
            fontSize: 11,
            fontFamily: MATRIX_FONT,
            alignItems: "center",
          }}
        >
          <span
            onClick={() => onTickerClick(c.ticker)}
            style={{
              color: "#e8ffe8",
              fontWeight: 700,
              letterSpacing: "0.04em",
              cursor: "pointer",
              textDecoration: "underline",
              textDecorationColor: "rgba(74,222,128,0.3)",
            }}
          >
            {c.ticker}
          </span>
          <span
            style={{
              color: "#666",
              fontSize: 10,
              overflow: "hidden",
              whiteSpace: "nowrap",
              textOverflow: "ellipsis",
              paddingRight: 8,
            }}
          >
            {c.notes || "—"}
          </span>
          <span
            style={{
              color: c.score >= 70 ? "#4ade80" : c.score >= 50 ? "#facc15" : "#888",
              fontWeight: 600,
            }}
          >
            {c.score.toFixed(0)}
          </span>
          <span style={{ color: "#666", fontSize: 10 }}>{c.sector || "—"}</span>
          <span style={{ color: "#555", fontSize: 10 }}>{c.source || "—"}</span>
          <span style={{ color: "#555", fontSize: 10 }}>
            {c.added_date
              ? new Date(c.added_date + "T00:00:00").toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                })
              : "—"}
          </span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.06em",
              color: c.social_heat ? HEAT_COLOR[c.social_heat] ?? "#555" : "#333",
            }}
          >
            {c.social_heat ?? "—"}
          </span>
        </div>
      ))}
    </div>
  );
}
