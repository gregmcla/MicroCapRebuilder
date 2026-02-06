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

const reasonBadge: Record<string, { label: string; cls: string }> = {
  STOP_LOSS: { label: "STOP", cls: "bg-loss/15 text-loss" },
  TAKE_PROFIT: { label: "TARGET", cls: "bg-profit/15 text-profit" },
  MANUAL: { label: "MANUAL", cls: "bg-bg-elevated text-text-muted" },
};

function FeedItem({ tx }: { tx: Transaction }) {
  const isBuy = tx.action === "BUY";
  const rowBg = isBuy ? "hover:bg-accent/5" : "hover:bg-warning/5";
  const actionColor = isBuy ? "text-accent" : "text-warning";
  const icon = isBuy ? "\u25B2" : "\u25BC"; // up/down arrow
  const badge = reasonBadge[tx.reason];

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 text-xs border-b border-border/20 transition-colors ${rowBg}`}
    >
      <span className={`${actionColor} w-3 shrink-0 text-center`}>{icon}</span>
      <span className={`font-semibold w-8 shrink-0 ${actionColor}`}>
        {tx.action}
      </span>
      <span className="font-semibold text-text-primary w-12 shrink-0">
        {tx.ticker}
      </span>
      <span className="font-mono text-text-secondary">
        {tx.shares}@${tx.price.toFixed(2)}
      </span>
      <span className="font-mono text-text-muted text-[10px]">
        ${tx.total_value.toLocaleString(undefined, {
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        })}
      </span>
      {badge && (
        <span
          className={`ml-auto text-[9px] font-semibold px-1 py-0.5 rounded tracking-wider ${badge.cls}`}
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
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <h2 className="text-xs font-semibold text-text-secondary tracking-wider uppercase">
          Activity
        </h2>
        <span className="text-[10px] text-text-muted">
          {transactions.length} trades
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {groups.length === 0 ? (
          <div className="p-4 text-center text-text-muted text-sm">
            No recent activity
          </div>
        ) : (
          groups.map(([dateKey, txs]) => (
            <div key={dateKey}>
              {/* Day header */}
              <div className="sticky top-0 px-3 py-1 bg-bg-primary/90 backdrop-blur-sm border-b border-border/30">
                <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">
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
