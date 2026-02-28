/** Actions tab — ANALYZE results, EXECUTE flow. */

import { useAnalysisStore } from "../lib/store";
import type { ReviewedAction } from "../lib/types";

function ConfidenceDot({ confidence }: { confidence: number }) {
  const color =
    confidence >= 0.8
      ? "var(--green)"
      : confidence >= 0.5
        ? "var(--amber)"
        : "var(--red)";
  return (
    <span
      style={{ background: color }}
      className="inline-block w-2 h-2 rounded-full"
      title={`${(confidence * 100).toFixed(0)}% confidence`}
    />
  );
}

function DecisionBadge({ decision }: { decision: string }) {
  const styleMap: Record<string, React.CSSProperties> = {
    APPROVE: {
      background: "rgba(124,92,252,0.15)",
      color: "var(--accent-bright)",
    },
    MODIFY: {
      background: "rgba(251,191,36,0.15)",
      color: "var(--amber)",
    },
    VETO: {
      background: "rgba(248,113,113,0.15)",
      color: "var(--red)",
    },
  };
  const style = styleMap[decision] ?? { background: "rgba(255,255,255,0.06)", color: "var(--text-1)" };
  return (
    <span
      style={style}
      className="px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider"
    >
      {decision}
    </span>
  );
}

function ActionCard({ action }: { action: ReviewedAction }) {
  const { original, decision, ai_reasoning, confidence } = action;
  const isBuy = original.action_type === "BUY";

  return (
    <div
      className="card-hover p-3"
      style={{
        background: "var(--surface-1)",
        border: "1px solid var(--border-0)",
        borderRadius: 8,
      }}
    >
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className="text-xs font-bold px-1.5 py-0.5 rounded"
          style={
            isBuy
              ? { background: "rgba(124,92,252,0.15)", color: "var(--accent-bright)" }
              : { background: "rgba(251,191,36,0.15)", color: "var(--amber)" }
          }
        >
          {original.action_type}
        </span>
        <span className="font-semibold" style={{ color: "var(--text-4)" }}>
          {original.ticker}
        </span>
        <span className="font-mono text-xs" style={{ color: "var(--text-1)" }}>
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
          <span
            className="font-mono text-sm font-semibold tabular-nums"
            style={{ color: "var(--accent-bright)" }}
          >
            {original.quant_score.toFixed(0)}/100
          </span>
          <div className="flex gap-1.5 text-[10px]" style={{ color: "var(--text-0)" }}>
            {Object.entries(original.factor_scores).map(([k, v]) => (
              <span
                key={k}
                className="px-1 py-0.5 rounded"
                style={{ background: "var(--void)" }}
              >
                {k.slice(0, 3)} {typeof v === "number" ? v.toFixed(0) : v}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Stops */}
      <div className="flex gap-3 mb-2 text-xs" style={{ color: "var(--text-1)" }}>
        <span>
          Stop:{" "}
          <span className="font-mono tabular-nums" style={{ color: "var(--red)" }}>
            ${(action.modified_stop ?? original.stop_loss).toFixed(2)}
          </span>
        </span>
        <span>
          Target:{" "}
          <span className="font-mono tabular-nums" style={{ color: "var(--green)" }}>
            ${(action.modified_target ?? original.take_profit).toFixed(2)}
          </span>
        </span>
      </div>

      {/* AI reasoning */}
      <p className="text-xs leading-relaxed italic" style={{ color: "var(--text-2)" }}>
        {ai_reasoning}
      </p>
    </div>
  );
}

const sectionHeaderStyle: React.CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "9.5px",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: "var(--text-0)",
};

export default function ActionsTab() {
  const { result, isAnalyzing, isExecuting, error, lastAnalyzedAt, runAnalysis, runExecute } =
    useAnalysisStore();

  // No analysis yet
  if (!result && !isAnalyzing) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4" style={{ color: "var(--text-1)" }}>
        <div className="text-4xl">&#x1F50D;</div>
        <p className="text-sm">Run ANALYZE to see recommendations</p>
        <p className="text-xs" style={{ color: "var(--text-0)" }}>
          Mommy will score watchlist candidates and propose trades
        </p>
        {lastAnalyzedAt && (
          <p className="text-xs" style={{ color: "var(--text-0)" }}>
            Last run: {lastAnalyzedAt}
          </p>
        )}
        <button
          onClick={runAnalysis}
          className="px-4 py-2 text-sm font-medium rounded-lg transition-all"
          style={{
            background: "var(--accent)",
            color: "#fff",
            boxShadow: "0 0 12px rgba(124,92,252,0.3)",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 20px rgba(124,92,252,0.5)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 12px rgba(124,92,252,0.3)";
          }}
        >
          ANALYZE
        </button>
        {error && (
          <p className="text-xs" style={{ color: "var(--red)" }}>{error}</p>
        )}
      </div>
    );
  }

  // Analyzing spinner
  if (isAnalyzing) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <div
          className="w-8 h-8 border-2 rounded-full animate-spin"
          style={{
            borderColor: "rgba(124,92,252,0.3)",
            borderTopColor: "var(--accent)",
          }}
        />
        <p className="text-sm" style={{ color: "var(--text-4)" }}>Mommy's analyzing the market...</p>
        <p className="text-xs" style={{ color: "var(--text-2)" }}>Scoring candidates, running AI review</p>
      </div>
    );
  }

  if (!result) return null;

  const { approved, modified, vetoed, summary } = result;
  const actionable = [...approved, ...modified];

  // Analysis ran but found nothing
  if (summary.total_proposed === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4" style={{ color: "var(--text-1)" }}>
        <div className="text-4xl">&#x1F937;</div>
        <p className="text-sm font-medium" style={{ color: "var(--text-2)" }}>No opportunities found</p>
        <p className="text-xs text-center max-w-xs">
          Mommy scanned the watchlist but didn't find any trades worth making right now.
          Try running SCAN first to refresh candidates.
        </p>
        {lastAnalyzedAt && (
          <p className="text-xs" style={{ color: "var(--text-0)" }}>
            Analyzed at {lastAnalyzedAt}
          </p>
        )}
        <button
          onClick={runAnalysis}
          className="px-3 py-1 text-xs font-medium rounded transition-colors"
          style={{
            background: "var(--surface-1)",
            color: "var(--text-2)",
            border: "1px solid var(--border-0)",
          }}
          onMouseEnter={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.borderColor = "var(--accent)";
            el.style.color = "var(--accent-bright)";
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.borderColor = "var(--border-0)";
            el.style.color = "var(--text-2)";
          }}
        >
          Re-analyze
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Summary bar */}
      <div
        className="flex items-center gap-3 px-4 py-2"
        style={{
          borderBottom: "1px solid var(--border-0)",
          background: "rgba(20,20,22,0.3)",
        }}
      >
        <span className="text-xs" style={{ color: "var(--text-1)" }}>
          {summary.total_proposed} proposed
        </span>
        <span className="text-xs" style={{ color: "var(--green)" }}>
          {summary.approved} approved
        </span>
        {summary.modified > 0 && (
          <span className="text-xs" style={{ color: "var(--amber)" }}>
            {summary.modified} modified
          </span>
        )}
        {summary.vetoed > 0 && (
          <span className="text-xs" style={{ color: "var(--red)" }}>{summary.vetoed} vetoed</span>
        )}
        <div className="flex-1" />
        {summary.can_execute && (
          <button
            onClick={runExecute}
            disabled={isExecuting}
            className="px-3 py-1 text-xs font-semibold rounded transition-all disabled:opacity-50"
            style={{
              background: "rgba(52,211,153,0.15)",
              color: "var(--green)",
            }}
          >
            {isExecuting ? "Executing..." : `EXECUTE ${actionable.length}`}
          </button>
        )}
        <button
          onClick={runAnalysis}
          className="px-3 py-1 text-xs font-medium rounded transition-colors"
          style={{
            background: "var(--surface-1)",
            color: "var(--text-2)",
            border: "1px solid var(--border-0)",
          }}
          onMouseEnter={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.borderColor = "var(--accent)";
            el.style.color = "var(--accent-bright)";
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.borderColor = "var(--border-0)";
            el.style.color = "var(--text-2)";
          }}
        >
          Re-analyze
        </button>
      </div>

      {error && (
        <div
          className="px-4 py-2 text-xs"
          style={{
            color: "var(--red)",
            background: "rgba(248,113,113,0.1)",
            borderBottom: "1px solid rgba(248,113,113,0.2)",
          }}
        >
          {error}
        </div>
      )}

      {/* Action cards */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {actionable.length > 0 && (
          <>
            <h3 style={sectionHeaderStyle} className="mb-2">
              Ready to execute
            </h3>
            {actionable.map((a, i) => (
              <ActionCard key={`${a.original.ticker}-${i}`} action={a} />
            ))}
          </>
        )}
        {vetoed.length > 0 && (
          <>
            <h3 style={sectionHeaderStyle} className="mt-4 mb-2">
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
