/** Bottom left — activity feed with day grouping, type icons, color-coded rows. */

import { useState } from "react";
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

const FACTOR_NAMES: Record<string, string> = {
  momentum: "momentum",
  relative_strength: "relative strength",
  mean_reversion: "mean reversion",
  volume: "volume",
  volatility: "volatility",
  rsi: "RSI",
};

function parseFactorScores(raw: string | null | undefined): Record<string, number> {
  if (!raw) return {};
  try {
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    return Object.fromEntries(
      Object.entries(parsed).filter(([k]) => k !== "composite")
    ) as Record<string, number>;
  } catch {
    return {};
  }
}

function reasonText(tx: Transaction): string {
  if (tx.action === "BUY") {
    const factors = parseFactorScores(tx.factor_scores);
    const top = Object.entries(factors).sort(([, a], [, b]) => b - a).slice(0, 2);
    const parts: string[] = [];

    if (tx.signal_rank && tx.composite_score) {
      parts.push(`Ranked #${Math.round(tx.signal_rank)} in the scan with a composite score of ${tx.composite_score.toFixed(0)}/100.`);
    } else if (tx.signal_rank) {
      parts.push(`Ranked #${Math.round(tx.signal_rank)} in the scan.`);
    } else if (tx.composite_score) {
      parts.push(`Composite score of ${tx.composite_score.toFixed(0)}/100.`);
    }

    if (top.length >= 2) {
      parts.push(`${FACTOR_NAMES[top[0][0]] ?? top[0][0]} (${top[0][1].toFixed(0)}) and ${FACTOR_NAMES[top[1][0]] ?? top[1][0]} (${top[1][1].toFixed(0)}) were the standout signals.`);
    } else if (top.length === 1) {
      parts.push(`${FACTOR_NAMES[top[0][0]] ?? top[0][0]} (${top[0][1].toFixed(0)}) was the standout signal.`);
    }

    if (tx.regime_at_entry) {
      parts.push(`Entered in a ${tx.regime_at_entry.toLowerCase()} market.`);
    }

    return parts.join(" ") || "Entry based on multi-factor scan.";
  }

  const map: Record<string, string> = {
    STOP_LOSS: "Stop loss triggered — position closed to limit downside.",
    TAKE_PROFIT: "Take profit target reached — gain locked in.",
    MANUAL: "Manually closed.",
    INTELLIGENCE: "AI-reviewed exit — closed based on analysis.",
    SIGNAL: "Signal-based exit.",
  };
  return map[tx.reason] ?? tx.reason ?? "Exit.";
}

function ExpandedDetail({ tx }: { tx: Transaction }) {
  return (
    <div
      className="px-3 py-2 text-xs"
      style={{
        background: "var(--surface-1)",
        borderBottom: "1px solid var(--border-1)",
        borderLeft: "2px solid var(--accent)",
      }}
    >
      <p style={{ color: "var(--text-2)", lineHeight: "1.6" }}>
        {reasonText(tx)}
      </p>
    </div>
  );
}

function FeedItem({
  tx,
  expanded,
  onToggle,
}: {
  tx: Transaction;
  expanded: boolean;
  onToggle: () => void;
}) {
  const isBuy = tx.action === "BUY";
  const actionColor = isBuy ? "var(--accent)" : "var(--amber)";
  const icon = isBuy ? "▲" : "▼";
  const badge = reasonBadge[tx.reason];

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
                />
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
