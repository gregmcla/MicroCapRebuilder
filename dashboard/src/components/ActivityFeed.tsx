/** Bottom left — activity feed with day grouping, type icons, color-coded rows. */

import type { Transaction } from "../lib/types";

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor(
    (now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24)
  );
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function groupByDate(txs: Transaction[]): [string, Transaction[]][] {
  const groups = new Map<string, Transaction[]>();
  for (const tx of txs) {
    const key = tx.date.slice(0, 10); // YYYY-MM-DD
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(tx);
  }
  return Array.from(groups.entries());
}

const reasonBadge: Record<string, { label: string; bg: string; color: string }> = {
  STOP_LOSS: { label: "STOP", bg: "rgba(248,113,113,0.12)", color: "var(--red)" },
  TAKE_PROFIT: { label: "TARGET", bg: "rgba(52,211,153,0.12)", color: "var(--green)" },
  MANUAL: { label: "MANUAL", bg: "var(--surface-3)", color: "var(--text-1)" },
};

function FeedItem({ tx }: { tx: Transaction }) {
  const isBuy = tx.action === "BUY";
  const actionColor = isBuy ? "var(--accent)" : "var(--amber)";
  const icon = isBuy ? "▲" : "▼";
  const badge = reasonBadge[tx.reason];

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 text-xs transition-colors"
      style={{ borderBottom: "1px solid var(--border-0)" }}
    >
      <span className="w-3 shrink-0 text-center" style={{ color: actionColor }}>
        {icon}
      </span>
      <span className="font-semibold w-8 shrink-0" style={{ color: actionColor }}>
        {tx.action}
      </span>
      <span className="font-semibold w-12 shrink-0" style={{ color: "var(--text-3)" }}>
        {tx.ticker}
      </span>
      <span className="font-mono" style={{ color: "var(--text-2)" }}>
        {tx.shares}@${tx.price.toFixed(2)}
      </span>
      <span
        className="font-mono"
        style={{ fontSize: "10px", color: "var(--text-0)", fontFamily: "var(--font-mono)" }}
      >
        ${tx.total_value.toLocaleString(undefined, {
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        })}
      </span>
      {badge && (
        <span
          className="ml-auto font-semibold px-1 py-0.5 rounded tracking-wider"
          style={{
            fontSize: "9px",
            background: badge.bg,
            color: badge.color,
          }}
        >
          {badge.label}
        </span>
      )}
    </div>
  );
}

export default function ActivityFeed({
  transactions,
}: {
  transactions: Transaction[];
}) {
  const recent = [...transactions].reverse().slice(0, 50);
  const groups = groupByDate(recent);

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--surface-0)" }}>
      <div
        className="flex items-center justify-between px-3 py-2 shrink-0"
        style={{ borderBottom: "1px solid var(--border-0)" }}
      >
        <h2
          className="uppercase tracking-wider font-semibold"
          style={{ fontSize: "11px", color: "var(--text-2)" }}
        >
          Activity
        </h2>
        <span style={{ fontSize: "10px", color: "var(--text-0)", fontFamily: "var(--font-mono)" }}>
          {transactions.length} trades
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {groups.length === 0 ? (
          <div className="p-4 text-center text-sm" style={{ color: "var(--text-1)" }}>
            No recent activity
          </div>
        ) : (
          groups.map(([dateKey, txs]) => (
            <div key={dateKey}>
              {/* Day header */}
              <div
                className="sticky top-0 px-3 py-1 backdrop-blur-sm"
                style={{
                  background: "rgba(14,14,16,0.90)",
                  borderBottom: "1px solid var(--border-0)",
                }}
              >
                <span
                  className="uppercase tracking-wider font-semibold"
                  style={{
                    fontSize: "10px",
                    color: "var(--text-0)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {formatDate(dateKey)}
                </span>
              </div>
              {txs.map((tx) => (
                <FeedItem key={tx.transaction_id} tx={tx} />
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
