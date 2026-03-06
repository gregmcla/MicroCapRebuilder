/** Shared trade explanation utilities used by ActivityFeed and CenterPane. */

import type { Transaction } from "./types";

export const FACTOR_PLAIN: Record<string, string> = {
  momentum:          "the stock had been climbing steadily",
  relative_strength: "it was beating the broader market",
  mean_reversion:    "it had pulled back to an attractive entry point",
  volume:            "trading volume spiked, confirming interest",
  volatility:        "it was moving calmly relative to its history",
  rsi:               "its momentum readings were favorable",
};

export const REGIME_PLAIN: Record<string, string> = {
  BULL:     "markets were in a strong uptrend",
  BEAR:     "markets were under pressure",
  SIDEWAYS: "markets were flat and rangebound",
};

export function parseFactorScores(raw: string | null | undefined): Record<string, number> {
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

export function convictionLabel(score: number): string {
  if (score >= 85) return "Top-tier pick";
  if (score >= 75) return "Strong pick";
  if (score >= 65) return "Solid pick";
  return "Speculative pick";
}

export function tradeExplanation(tx: Transaction): string {
  if (tx.action === "BUY") {
    const factors = parseFactorScores(tx.factor_scores);
    const top = Object.entries(factors).sort(([, a], [, b]) => b - a).slice(0, 2);
    const parts: string[] = [];

    const label = tx.composite_score ? convictionLabel(tx.composite_score) : null;
    const rankStr = tx.signal_rank ? `, ranking #${Math.round(tx.signal_rank)} in the scan` : "";
    if (label && tx.composite_score) {
      parts.push(`${label}${rankStr} (${tx.composite_score.toFixed(0)}/100).`);
    } else if (tx.signal_rank) {
      parts.push(`Ranked #${Math.round(tx.signal_rank)} in the scan.`);
    }

    const why = top
      .filter(([k]) => FACTOR_PLAIN[k])
      .map(([k]) => FACTOR_PLAIN[k]);
    if (why.length === 2) {
      parts.push(`The system bought it because ${why[0]} and ${why[1]}.`);
    } else if (why.length === 1) {
      parts.push(`The system bought it because ${why[0]}.`);
    }

    const regimePlain = tx.regime_at_entry ? REGIME_PLAIN[tx.regime_at_entry] : null;
    if (regimePlain) {
      parts.push(`At entry, ${regimePlain}.`);
    }

    return parts.join(" ") || "Bought based on multi-factor scan.";
  }

  const map: Record<string, string> = {
    STOP_LOSS:    "Stop loss hit — the stock fell to the downside limit and was closed to protect capital.",
    TAKE_PROFIT:  "Target price reached — the gain was locked in.",
    MANUAL:       "Manually closed.",
    INTELLIGENCE: "AI flagged this for exit after reviewing current conditions.",
    SIGNAL:       "Exited based on a signal from the scoring model.",
  };
  return map[tx.reason] ?? tx.reason ?? "Position closed.";
}
