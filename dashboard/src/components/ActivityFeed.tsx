/** Bottom left — activity feed with day grouping, type icons, color-coded rows. */

import { useState } from "react";
import type { Transaction } from "../lib/types";
import { tradeExplanation, parseTradeRationale } from "../lib/tradeUtils";

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
    const key = tx.date.slice(0, 10);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(tx);
  }
  return Array.from(groups.entries());
}

const reasonBadge: Record<string, { label: string; bg: string; color: string }> = {
  STOP_LOSS: { label: "STOP", bg: "rgba(248,113,113,0.12)", color: "var(--red)" },
  TAKE_PROFIT: { label: "TARGET", bg: "rgba(52,211,153,0.12)", color: "var(--green)" },
  MANUAL: { label: "MANUAL", bg: "var(--surface-3)", color: "var(--text-1)" },
  INTELLIGENCE: { label: "AI", bg: "rgba(139,92,246,0.12)", color: "var(--accent)" },
};


function ExpandedDetail({ tx }: { tx: Transaction }) {
  const rationale = parseTradeRationale(tx);
  const aiText = rationale?.ai_reasoning;
  const quantText = rationale?.quant_reason;
  const isBuy = tx.action === "BUY";
  const label = isBuy ? "BUY REASONING" : "SELL REASONING";
  return (
    <div
      className="px-3 py-2 text-xs"
      style={{
        background: "var(--surface-1)",
        borderBottom: "1px solid var(--border-1)",
        borderLeft: "2px solid var(--accent)",
      }}
    >
      {(aiText || tradeExplanation(tx)) && (
        <>
          <p style={{ fontSize: "9px", fontWeight: 600, letterSpacing: "0.08em", color: "var(--text-0)", marginBottom: "4px", textTransform: "uppercase" }}>
            {label}
          </p>
          <p style={{ color: "var(--text-2)", lineHeight: "1.6" }}>
            {aiText || tradeExplanation(tx)}
          </p>
        </>
      )}
      {aiText && quantText && (
        <p style={{ color: "var(--text-3)", lineHeight: "1.5", marginTop: "4px", fontSize: "10px", opacity: 0.7 }}>
          {quantText.split(" | ")[0]}
        </p>
      )}
    </div>
  );
}

function formatPnl(pnl: number, pct: number): string {
  const sign = pnl >= 0 ? "+" : "";
  const abs = Math.abs(pnl);
  const dolStr = abs >= 1000 ? `${sign}$${(pnl / 1000).toFixed(1)}k` : `${sign}$${pnl.toFixed(0)}`;
  return `${dolStr} (${sign}${pct.toFixed(1)}%)`;
}

function getDaysHeld(tx: Transaction, allTxs: Transaction[]): number | null {
  const sellDate = tx.date.slice(0, 10);
  const matchingBuy = [...allTxs]
    .filter(t => t.ticker === tx.ticker && t.action === "BUY" && t.date.slice(0, 10) <= sellDate)
    .pop();
  if (!matchingBuy) return null;
  const buyDate = new Date(matchingBuy.date.slice(0, 10));
  const sellDateObj = new Date(sellDate);
  return Math.floor((sellDateObj.getTime() - buyDate.getTime()) / (1000 * 60 * 60 * 24));
}

function FeedItem({
  tx,
  expanded,
  onToggle,
  allTxs,
}: {
  tx: Transaction;
  expanded: boolean;
  onToggle: () => void;
  allTxs: Transaction[];
}) {
  const isBuy = tx.action === "BUY";
  const actionColor = isBuy ? "var(--accent)" : "var(--amber)";
  const icon = isBuy ? "▲" : "▼";
  const badge = reasonBadge[tx.reason];
  const hasPnl = !isBuy && tx.realized_pnl != null && tx.realized_pnl_pct != null;
  const hasEntry = !isBuy && tx.entry_price != null;
  const pnlColor = hasPnl ? (tx.realized_pnl! >= 0 ? "var(--green)" : "var(--red)") : undefined;
  const daysHeld = !isBuy ? getDaysHeld(tx, allTxs) : null;

  return (
    <>
      <div
        className="flex items-center gap-2 px-3 py-1.5 text-xs transition-colors cursor-pointer"
        style={{
          borderBottom: expanded ? "none" : "1px solid var(--border-0)",
          background: expanded ? "var(--surface-1)" : undefined,
        }}
        onClick={onToggle}
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

        {/* SELL: entry → sell price */}
        {!isBuy && hasEntry ? (
          <span className="font-mono" style={{ color: "var(--text-2)" }}>
            ${tx.entry_price!.toFixed(2)}
            <span style={{ color: "var(--text-0)", margin: "0 2px" }}>→</span>
            ${tx.price.toFixed(2)}
          </span>
        ) : (
          <span className="font-mono" style={{ color: "var(--text-2)" }}>
            {tx.shares}@${tx.price.toFixed(2)}
          </span>
        )}

        {/* P&L for sells, total cost for buys */}
        {hasPnl ? (
          <span
            className="font-mono font-semibold"
            style={{ fontSize: "10px", color: pnlColor, fontFamily: "var(--font-mono)" }}
          >
            {formatPnl(tx.realized_pnl!, tx.realized_pnl_pct!)}
          </span>
        ) : (
          <span
            className="font-mono"
            style={{ fontSize: "10px", color: "var(--text-0)", fontFamily: "var(--font-mono)" }}
          >
            ${tx.total_value.toLocaleString(undefined, {
              minimumFractionDigits: 0,
              maximumFractionDigits: 0,
            })}
          </span>
        )}

        {/* P/L badge for sells */}
        {hasPnl && (
          <span
            className="font-bold px-1 py-0.5 rounded shrink-0"
            style={{
              fontSize: "9px",
              background: tx.realized_pnl! >= 0 ? "rgba(52,211,153,0.15)" : "rgba(248,113,113,0.15)",
              color: tx.realized_pnl! >= 0 ? "var(--green)" : "var(--red)",
            }}
          >
            {tx.realized_pnl! >= 0 ? "P" : "L"}
          </span>
        )}
        {/* Days held for sells */}
        {daysHeld != null && (
          <span className="shrink-0" style={{ fontSize: "9px", color: "var(--text-0)" }}>
            {daysHeld}d
          </span>
        )}
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
        {tx.date.length > 10 && (
          <span style={{ color: "var(--text-0)", fontSize: "9px", fontFamily: "var(--font-mono)" }}>
            {tx.date.slice(11, 16)}
          </span>
        )}
        <span
          className="shrink-0"
          style={{
            color: "var(--text-0)",
            fontSize: "9px",
            marginLeft: badge ? "4px" : "auto",
          }}
        >
          {expanded ? "▲" : "▼"}
        </span>
      </div>
      {expanded && <ExpandedDetail tx={tx} />}
    </>
  );
}

export default function ActivityFeed({
  transactions,
}: {
  transactions: Transaction[];
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const recent = [...transactions].reverse().slice(0, 50);
  const groups = groupByDate(recent);

  function toggle(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

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
                <FeedItem
                  key={tx.transaction_id}
                  tx={tx}
                  expanded={expandedId === tx.transaction_id}
                  onToggle={() => toggle(tx.transaction_id)}
                  allTxs={transactions}
                />
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
