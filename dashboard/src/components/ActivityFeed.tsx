/** Bottom left — live activity feed of recent transactions. */

import type { Transaction } from "../lib/types";

function FeedItem({ tx }: { tx: Transaction }) {
  const issBuy = tx.action === "BUY";
  const color = issBuy ? "text-accent" : "text-warning";
  const date = new Date(tx.date);
  const timeStr = date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-xs border-b border-border/30">
      <span className="text-text-muted w-14 shrink-0">{timeStr}</span>
      <span className={`font-semibold w-8 shrink-0 ${color}`}>
        {tx.action}
      </span>
      <span className="font-semibold text-text-primary w-12 shrink-0">
        {tx.ticker}
      </span>
      <span className="font-mono text-text-secondary">
        {tx.shares}@${tx.price.toFixed(2)}
      </span>
      {tx.reason && tx.reason !== "SIGNAL" && (
        <span className="ml-auto text-text-muted text-[10px] uppercase">
          {tx.reason}
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
  // Show most recent first, limit to 30
  const recent = [...transactions].reverse().slice(0, 30);

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-border">
        <h2 className="text-xs font-semibold text-text-secondary tracking-wider uppercase">
          Activity
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        {recent.length === 0 ? (
          <div className="p-4 text-center text-text-muted text-sm">
            No recent activity
          </div>
        ) : (
          recent.map((tx) => <FeedItem key={tx.transaction_id} tx={tx} />)
        )}
      </div>
    </div>
  );
}
