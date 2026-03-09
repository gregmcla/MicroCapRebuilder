/** Shared trade explanation utilities used by ActivityFeed and CenterPane. */

import type { Transaction } from "./types";

export const FACTOR_PLAIN: Record<string, string> = {
  price_momentum:   "the stock had strong momentum and was outperforming the market",
  earnings_growth:  "earnings and revenue were growing",
  quality:          "the business had strong margins and low debt",
  volume:           "trading volume spiked, confirming interest",
  volatility:       "it was moving calmly relative to its history",
  value_timing:     "it was near a value entry point with favorable RSI",
  // legacy keys for old transaction records
  momentum:         "the stock had been climbing steadily",
  relative_strength:"it was beating the broader market",
  mean_reversion:   "it had pulled back to an attractive entry point",
  rsi:              "its momentum readings were favorable",
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

  if (tx.reason === "STOP_LOSS") {
    const stopStr = tx.stop_loss ? ` at $${tx.stop_loss.toFixed(2)}` : "";
    return `Stop loss hit — the stock fell to the downside limit${stopStr} and was closed to protect capital.`;
  }

  if (tx.reason === "TAKE_PROFIT") {
    const targetStr = tx.take_profit ? ` at $${tx.take_profit.toFixed(2)}` : "";
    return `Target price reached${targetStr} — the gain was locked in.`;
  }

  if (tx.reason === "INTELLIGENCE") {
    return "AI reviewed current conditions and flagged this position for exit — either the thesis weakened or a better opportunity needed the capital.";
  }

  if (tx.reason === "SIGNAL") {
    return "The scoring model signaled an exit — the position's factor scores deteriorated or a risk threshold was crossed.";
  }

  if (tx.reason === "MANUAL") {
    const price = tx.price;
    const stop = tx.stop_loss;
    const target = tx.take_profit;

    // Infer context from where price landed relative to stop/target
    if (stop && price <= stop * 1.05) {
      return `Manually closed at $${price.toFixed(2)} — the position was at or near the stop loss level ($${stop.toFixed(2)}). Exited to protect capital.`;
    }
    if (target && price >= target * 0.95) {
      return `Manually closed at $${price.toFixed(2)} — the position was at or near the target price ($${target.toFixed(2)}). Gains locked in.`;
    }
    if (stop && target) {
      return `Manually closed at $${price.toFixed(2)}. The stop loss was $${stop.toFixed(2)} and the target was $${target.toFixed(2)}.`;
    }
    if (stop) {
      return `Manually closed at $${price.toFixed(2)}. The stop loss was set at $${stop.toFixed(2)}.`;
    }
    return `Manually closed at $${price.toFixed(2)}.`;
  }

  return tx.reason ?? "Position closed.";
}
