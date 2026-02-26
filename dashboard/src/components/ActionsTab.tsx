/** Actions tab — ANALYZE results, EXECUTE flow. */

import { useAnalysisStore } from "../lib/store";
import type { ReviewedAction } from "../lib/types";

function ConfidenceDot({ confidence }: { confidence: number }) {
  const color =
    confidence >= 0.8
      ? "bg-profit"
      : confidence >= 0.5
        ? "bg-warning"
        : "bg-loss";
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${color}`}
      title={`${(confidence * 100).toFixed(0)}% confidence`}
    />
  );
}

function DecisionBadge({ decision }: { decision: string }) {
  const styles: Record<string, string> = {
    APPROVE: "bg-profit/15 text-profit",
    MODIFY: "bg-warning/15 text-warning",
    VETO: "bg-loss/15 text-loss",
  };
  return (
    <span
      className={`px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider ${styles[decision] ?? "bg-bg-elevated text-text-muted"}`}
    >
      {decision}
    </span>
  );
}

function ActionCard({ action }: { action: ReviewedAction }) {
  const { original, decision, ai_reasoning, confidence } = action;
  const isBuy = original.action_type === "BUY";

  return (
    <div className="border border-border rounded-lg p-3 bg-bg-elevated/50">
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`text-xs font-bold px-1.5 py-0.5 rounded ${
            isBuy ? "bg-accent/15 text-accent" : "bg-warning/15 text-warning"
          }`}
        >
          {original.action_type}
        </span>
        <span className="font-semibold text-text-primary">
          {original.ticker}
        </span>
        <span className="font-mono text-xs text-text-secondary">
          {action.modified_shares ?? original.shares} shares @
          ${original.price.toFixed(2)}
        </span>
        <div className="flex-1" />
        <ConfidenceDot confidence={confidence} />
        <DecisionBadge decision={decision} />
      </div>

      {/* Quant score + factor breakdown for buys */}
      {isBuy && original.quant_score > 0 && (
        <div className="flex items-center gap-3 mb-2">
          <span className="font-mono text-sm font-semibold text-accent">
            {original.quant_score.toFixed(0)}/100
          </span>
          <div className="flex gap-1.5 text-[10px] text-text-muted">
            {Object.entries(original.factor_scores).map(([k, v]) => (
              <span key={k} className="px-1 py-0.5 rounded bg-bg-primary">
                {k.slice(0, 3)} {typeof v === "number" ? v.toFixed(0) : v}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Stops */}
      <div className="flex gap-3 mb-2 text-xs text-text-muted">
        <span>
          Stop: <span className="font-mono text-loss">${(action.modified_stop ?? original.stop_loss).toFixed(2)}</span>
        </span>
        <span>
          Target: <span className="font-mono text-profit">${(action.modified_target ?? original.take_profit).toFixed(2)}</span>
        </span>
      </div>

      {/* AI reasoning */}
      <p className="text-xs text-text-secondary leading-relaxed italic">
        {ai_reasoning}
      </p>
    </div>
  );
}

export default function ActionsTab() {
  const { result, isAnalyzing, isExecuting, error, lastAnalyzedAt, runAnalysis, runExecute } =
    useAnalysisStore();

  // No analysis yet
  if (!result && !isAnalyzing) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-text-muted">
        <div className="text-4xl">&#x1F50D;</div>
        <p className="text-sm">Run ANALYZE to see recommendations</p>
        <p className="text-xs">
          Mommy will score watchlist candidates and propose trades
        </p>
        {lastAnalyzedAt && (
          <p className="text-xs text-text-muted">
            Last run: {lastAnalyzedAt}
          </p>
        )}
        <button
          onClick={runAnalysis}
          className="px-4 py-2 text-sm font-medium bg-accent/15 text-accent rounded-lg hover:bg-accent/25 transition-colors"
        >
          ANALYZE
        </button>
        {error && (
          <p className="text-xs text-loss">{error}</p>
        )}
      </div>
    );
  }

  // Analyzing spinner
  if (isAnalyzing) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-text-muted">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        <p className="text-sm">Mommy's analyzing the market...</p>
        <p className="text-xs">Scoring candidates, running AI review</p>
      </div>
    );
  }

  if (!result) return null;

  const { approved, modified, vetoed, summary } = result;
  const actionable = [...approved, ...modified];

  // Analysis ran but found nothing
  if (summary.total_proposed === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-text-muted">
        <div className="text-4xl">&#x1F937;</div>
        <p className="text-sm font-medium text-text-secondary">No opportunities found</p>
        <p className="text-xs text-center max-w-xs">
          Mommy scanned the watchlist but didn't find any trades worth making right now.
          Try running SCAN first to refresh candidates.
        </p>
        {lastAnalyzedAt && (
          <p className="text-xs text-text-muted">
            Analyzed at {lastAnalyzedAt}
          </p>
        )}
        <button
          onClick={runAnalysis}
          className="px-3 py-1 text-xs font-medium bg-bg-surface text-text-secondary border border-border rounded hover:border-accent hover:text-accent transition-colors"
        >
          Re-analyze
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Summary bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-bg-elevated/30">
        <span className="text-xs text-text-secondary">
          {summary.total_proposed} proposed
        </span>
        <span className="text-xs text-profit">
          {summary.approved} approved
        </span>
        {summary.modified > 0 && (
          <span className="text-xs text-warning">
            {summary.modified} modified
          </span>
        )}
        {summary.vetoed > 0 && (
          <span className="text-xs text-loss">{summary.vetoed} vetoed</span>
        )}
        <div className="flex-1" />
        {summary.can_execute && (
          <button
            onClick={runExecute}
            disabled={isExecuting}
            className="px-3 py-1 text-xs font-semibold bg-profit/15 text-profit rounded hover:bg-profit/25 disabled:opacity-50 transition-colors"
          >
            {isExecuting ? "Executing..." : `EXECUTE ${actionable.length}`}
          </button>
        )}
        <button
          onClick={runAnalysis}
          className="px-3 py-1 text-xs font-medium bg-bg-surface text-text-secondary border border-border rounded hover:border-accent hover:text-accent transition-colors"
        >
          Re-analyze
        </button>
      </div>

      {error && (
        <div className="px-4 py-2 text-xs text-loss bg-loss/10 border-b border-loss/20">
          {error}
        </div>
      )}

      {/* Action cards */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {actionable.length > 0 && (
          <>
            <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">
              Ready to execute
            </h3>
            {actionable.map((a, i) => (
              <ActionCard key={`${a.original.ticker}-${i}`} action={a} />
            ))}
          </>
        )}
        {vetoed.length > 0 && (
          <>
            <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mt-4">
              Vetoed
            </h3>
            {vetoed.map((a, i) => (
              <ActionCard key={`veto-${a.original.ticker}-${i}`} action={a} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
