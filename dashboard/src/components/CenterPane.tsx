/** Center panel — equity curve + activity (default) or candlestick chart (position selected). */

import { useUIStore } from "../lib/store";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { EquityCurve } from "./PortfolioSummary";
import { PositionDetailChart } from "./PositionDetail";
import type { Transaction } from "../lib/types";

// ---------------------------------------------------------------------------
// Recent activity feed (shown in default state)
// ---------------------------------------------------------------------------

function ActivityRow({ txn }: { txn: Transaction }) {
  const isBuy = txn.action === "BUY";
  const color = isBuy ? "var(--green)" : "var(--red)";
  return (
    <div
      className="flex items-center gap-3 py-2"
      style={{ borderBottom: "1px solid var(--border-0)" }}
    >
      {/* Buy/Sell badge */}
      <span
        className="shrink-0 font-mono text-[9px] font-bold px-1.5 py-0.5 rounded"
        style={{
          color,
          background: isBuy ? "rgba(52,211,153,0.10)" : "rgba(248,113,113,0.10)",
          letterSpacing: "0.08em",
        }}
      >
        {txn.action}
      </span>

      {/* Ticker */}
      <span className="font-mono font-semibold text-xs w-12 shrink-0" style={{ color: "var(--text-3)" }}>
        {txn.ticker}
      </span>

      {/* Date */}
      <span className="text-[10px] shrink-0" style={{ color: "var(--text-0)" }}>
        {String(txn.date).slice(0, 10)}
      </span>

      {/* Shares @ price */}
      <span className="font-mono text-[10px] flex-1 tabular-nums" style={{ color: "var(--text-1)" }}>
        {txn.shares} × ${Number(txn.price).toFixed(2)}
      </span>

      {/* Total value */}
      <span className="font-mono text-xs tabular-nums shrink-0" style={{ color: "var(--text-2)" }}>
        ${Number(txn.total_value).toLocaleString(undefined, { maximumFractionDigits: 0 })}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Default view: equity curve + recent activity
// ---------------------------------------------------------------------------

function DefaultView() {
  const { data: state } = usePortfolioState();
  const hasSnapshots = (state?.snapshots.length ?? 0) >= 2;
  const recentTxns = (state?.transactions ?? []).slice().reverse().slice(0, 8);

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* Equity curve — flex-1 min-h-0 so it compresses if needed */}
      <div
        className="shrink-0 relative"
        style={{ height: "200px", borderBottom: "1px solid var(--border-0)" }}
      >
        {hasSnapshots ? (
          <>
            <div
              className="absolute top-3 left-4 z-10 pointer-events-none"
              style={{
                fontSize: "9.5px",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--text-0)",
              }}
            >
              30-Day Equity
            </div>
            <EquityCurve snapshots={state!.snapshots} />
          </>
        ) : (
          <div className="flex items-center justify-center h-full">
            <span className="text-sm" style={{ color: "var(--text-0)" }}>No snapshot data yet</span>
          </div>
        )}
      </div>

      {/* Recent activity */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        <p
          className="mb-3"
          style={{
            fontSize: "9.5px",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-0)",
          }}
        >
          Recent Activity
        </p>
        {recentTxns.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--text-0)" }}>No transactions yet.</p>
        ) : (
          recentTxns.map((txn) => (
            <ActivityRow key={txn.transaction_id} txn={txn} />
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CenterPane
// ---------------------------------------------------------------------------

export default function CenterPane() {
  const selectedPosition = useUIStore((s) => s.selectedPosition);

  if (selectedPosition) {
    return (
      <div className="flex flex-col h-full overflow-hidden">
        <PositionDetailChart pos={selectedPosition} />
      </div>
    );
  }

  return <DefaultView />;
}
