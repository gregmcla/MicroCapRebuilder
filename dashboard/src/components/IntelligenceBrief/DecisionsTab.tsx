/** Decision Trace browser — per-analyze-cycle structured decision tree.
 *
 * Three modes:
 *   1. Deep-link by proposalId or traceId → opens that trace's detail view.
 *   2. Browse mode → list of recent traces, click to inspect.
 *   3. Diff mode → side-by-side structural diff between any two traces.
 */

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type {
  DecisionTrace,
  DecisionStep,
  DecisionDiff,
} from "../../lib/types";

const FONT = "'JetBrains Mono', 'SF Mono', monospace";

interface Props {
  portfolioId: string;
  initialProposalId?: string | null;
  initialTraceId?: string | null;
}

export default function DecisionsTab({
  portfolioId,
  initialProposalId = null,
  initialTraceId = null,
}: Props) {
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(
    initialTraceId,
  );
  const [diffOtherId, setDiffOtherId] = useState<string | null>(null);

  // If a proposal_id was passed in, resolve it to a trace_id (one-shot).
  const { data: resolved } = useQuery({
    queryKey: ["decision-resolve", portfolioId, initialProposalId],
    queryFn: () => api.resolveDecisionByProposal(portfolioId, initialProposalId!),
    enabled: !!initialProposalId && !initialTraceId,
    retry: false,
  });
  useEffect(() => {
    if (resolved?.trace_id && !selectedTraceId) {
      setSelectedTraceId(resolved.trace_id);
    }
  }, [resolved, selectedTraceId]);

  // Recent list — always fetched (used in browse + as the "pick second" picker for diff).
  const { data: recent } = useQuery({
    queryKey: ["decisions-recent", portfolioId],
    queryFn: () => api.getRecentDecisions(portfolioId, 30),
    staleTime: 60_000,
  });

  return (
    <div style={{ display: "flex", flex: 1, overflow: "hidden", fontFamily: FONT }}>
      {/* LEFT: recent traces list */}
      <div
        style={{
          width: "260px",
          borderRight: "1px solid rgba(255,255,255,0.08)",
          overflowY: "auto",
          padding: "8px 0",
        }}
      >
        <div
          style={{
            fontSize: "9px",
            letterSpacing: "0.12em",
            color: "#5a5a78",
            padding: "8px 12px",
            textTransform: "uppercase",
          }}
        >
          Recent Cycles
        </div>
        {(recent?.traces ?? []).map((t) => {
          const active = t.trace_id === selectedTraceId;
          const otherInDiff = t.trace_id === diffOtherId;
          const ts = new Date(t.timestamp);
          return (
            <button
              key={t.trace_id}
              onClick={() => setSelectedTraceId(t.trace_id)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "8px 12px",
                background: active
                  ? "rgba(124,92,252,0.10)"
                  : otherInDiff
                    ? "rgba(96,165,250,0.08)"
                    : "transparent",
                borderLeft: active
                  ? "2px solid #7c5cfc"
                  : otherInDiff
                    ? "2px solid #60a5fa"
                    : "2px solid transparent",
                border: "none",
                color: active ? "#e0e0f0" : "#9090b0",
                cursor: "pointer",
                fontFamily: FONT,
              }}
            >
              <div style={{ fontSize: "11px", fontWeight: 600 }}>
                {ts.toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
              <div style={{ fontSize: "9px", color: "#5a5a78", marginTop: "2px" }}>
                {t.mode} · ✅ {t.approved} ✏️ {t.modified} 🚫 {t.vetoed}
              </div>
              {t.tickers.length > 0 && (
                <div
                  style={{
                    fontSize: "9px",
                    color: "#6a6a88",
                    marginTop: "2px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {t.tickers.slice(0, 6).join(" ")}
                  {t.tickers.length > 6 ? " …" : ""}
                </div>
              )}
            </button>
          );
        })}
        {(recent?.traces ?? []).length === 0 && (
          <div style={{ padding: "12px", color: "#5a5a78", fontSize: "11px" }}>
            No traces yet — run /analyze to produce one.
          </div>
        )}
      </div>

      {/* RIGHT: detail view (or diff view) */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
        {selectedTraceId ? (
          diffOtherId ? (
            <DiffView
              portfolioId={portfolioId}
              traceA={selectedTraceId}
              traceB={diffOtherId}
              onExit={() => setDiffOtherId(null)}
            />
          ) : (
            <DetailView
              portfolioId={portfolioId}
              traceId={selectedTraceId}
              recentTraces={recent?.traces ?? []}
              onPickDiff={setDiffOtherId}
              highlightProposalId={initialProposalId ?? null}
            />
          )
        ) : (
          <EmptyState />
        )}
      </div>
    </div>
  );
}

// ─── Detail view ─────────────────────────────────────────────────────────────

function DetailView({
  portfolioId,
  traceId,
  recentTraces,
  onPickDiff,
  highlightProposalId,
}: {
  portfolioId: string;
  traceId: string;
  recentTraces: Array<{ trace_id: string; timestamp: string }>;
  onPickDiff: (id: string) => void;
  highlightProposalId: string | null;
}) {
  const { data: trace, isLoading } = useQuery({
    queryKey: ["decision-trace", portfolioId, traceId],
    queryFn: () => api.getDecisionTrace(portfolioId, traceId),
  });

  const otherOptions = useMemo(
    () => recentTraces.filter((t) => t.trace_id !== traceId).slice(0, 10),
    [recentTraces, traceId],
  );

  if (isLoading || !trace) {
    return <div style={{ color: "#5a5a78" }}>Loading trace…</div>;
  }

  return (
    <div>
      <header
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: "16px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          paddingBottom: "10px",
        }}
      >
        <div>
          <div style={{ color: "#e0e0f0", fontSize: "14px", fontWeight: 600 }}>
            {trace.portfolio_name} · {trace.analyze_mode} · {trace.branch}
          </div>
          <div style={{ color: "#6a6a88", fontSize: "10px", marginTop: "4px" }}>
            {new Date(trace.started_at).toLocaleString()} · {trace.duration_ms}ms · {trace.trace_id}
          </div>
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <span style={{ fontSize: "10px", color: "#5a5a78", letterSpacing: "0.08em" }}>
            DIFF vs:
          </span>
          <select
            onChange={(e) => e.target.value && onPickDiff(e.target.value)}
            defaultValue=""
            style={{
              fontFamily: FONT,
              fontSize: "10px",
              background: "rgba(255,255,255,0.05)",
              color: "#e0e0f0",
              border: "1px solid rgba(255,255,255,0.1)",
              padding: "4px 8px",
              cursor: "pointer",
            }}
          >
            <option value="">(pick a trace)</option>
            {otherOptions.map((t) => (
              <option key={t.trace_id} value={t.trace_id}>
                {new Date(t.timestamp).toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </option>
            ))}
          </select>
        </div>
      </header>

      <SummaryBar trace={trace} />

      <div style={{ marginTop: "16px" }}>
        {trace.steps.map((step, i) => (
          <StepCard
            key={i}
            step={step}
            highlightProposalId={highlightProposalId}
            defaultOpen={shouldDefaultOpen(step, highlightProposalId)}
          />
        ))}
        {trace.execute_step && (
          <StepCard
            step={trace.execute_step}
            highlightProposalId={highlightProposalId}
            defaultOpen={true}
          />
        )}
      </div>
    </div>
  );
}

function SummaryBar({ trace }: { trace: DecisionTrace }) {
  const summary = trace.final_summary as {
    approved?: number;
    modified?: number;
    vetoed?: number;
    can_execute?: boolean;
  };
  return (
    <div
      style={{
        display: "flex",
        gap: "16px",
        padding: "10px 12px",
        background: "rgba(255,255,255,0.03)",
        borderRadius: "4px",
        fontSize: "11px",
        color: "#9090b0",
      }}
    >
      <span>
        ✅ Approved: <strong style={{ color: "#34d399" }}>{summary?.approved ?? 0}</strong>
      </span>
      <span>
        ✏️ Modified: <strong style={{ color: "#fbbf24" }}>{summary?.modified ?? 0}</strong>
      </span>
      <span>
        🚫 Vetoed: <strong style={{ color: "#f87171" }}>{summary?.vetoed ?? 0}</strong>
      </span>
      <span style={{ marginLeft: "auto" }}>
        Steps: {trace.steps.length}
        {trace.execute_step ? " (+execute)" : ""}
      </span>
    </div>
  );
}

function shouldDefaultOpen(step: DecisionStep, highlightProposalId: string | null): boolean {
  if (!highlightProposalId) {
    // Default: open key high-signal steps.
    return ["ai_allocator_validate", "result_assemble", "execute"].includes(step.step_type);
  }
  // When highlighting a proposal, open any step that touched it.
  const validations = (step as unknown as { validations?: Array<{ proposal_id?: string }> })
    .validations;
  if (validations?.some((v) => v.proposal_id === highlightProposalId)) return true;
  const drops = (step as unknown as { drops?: Array<{ proposal_id?: string }> }).drops;
  if (drops?.some((d) => d.proposal_id === highlightProposalId)) return true;
  const txns = (step as unknown as { transactions_written?: Array<{ proposal_id?: string }> })
    .transactions_written;
  if (txns?.some((t) => t.proposal_id === highlightProposalId)) return true;
  return false;
}

function StepCard({
  step,
  highlightProposalId,
  defaultOpen,
}: {
  step: DecisionStep;
  highlightProposalId: string | null;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const hasContent = Object.keys(step).filter(
    (k) => !["step_name", "step_type", "started_at", "duration_ms", "error"].includes(k),
  ).length > 0;

  return (
    <div
      style={{
        marginBottom: "8px",
        background: "rgba(255,255,255,0.02)",
        borderLeft: `2px solid ${stepAccentColor(step.step_type)}`,
        borderRadius: "3px",
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%",
          textAlign: "left",
          padding: "8px 12px",
          background: "transparent",
          border: "none",
          color: "#e0e0f0",
          cursor: hasContent ? "pointer" : "default",
          fontFamily: FONT,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
        disabled={!hasContent}
      >
        <span style={{ fontSize: "11px", fontWeight: 600 }}>
          {hasContent ? (open ? "▾" : "▸") : "·"} {stepLabel(step.step_type)}
        </span>
        <span style={{ fontSize: "9px", color: "#5a5a78" }}>{step.duration_ms}ms</span>
      </button>
      {open && hasContent && (
        <div style={{ padding: "0 12px 12px 24px" }}>
          <StepBody step={step} highlightProposalId={highlightProposalId} />
        </div>
      )}
    </div>
  );
}

function StepBody({
  step,
  highlightProposalId,
}: {
  step: DecisionStep;
  highlightProposalId: string | null;
}) {
  // Type-specific rendering for high-information steps; JSON-ish fallback for the rest.
  switch (step.step_type) {
    case "ai_allocator_prompt":
      return <PromptStepBody step={step} />;
    case "ai_allocator_call":
      return <CallStepBody step={step} />;
    case "ai_allocator_validate":
      return <ValidateStepBody step={step} highlightProposalId={highlightProposalId} />;
    case "watchlist_scoring":
      return <ScoringStepBody step={step} />;
    case "layer1_risk":
      return <Layer1StepBody step={step} highlightProposalId={highlightProposalId} />;
    case "regime_detection":
      return <RegimeStepBody step={step} />;
    case "execute":
      return <ExecuteStepBody step={step} highlightProposalId={highlightProposalId} />;
    default:
      return <JsonFallback step={step} />;
  }
}

function PromptStepBody({ step }: { step: DecisionStep }) {
  const [showPrompt, setShowPrompt] = useState(false);
  const blocks = (step.blocks_included as string[]) ?? [];
  return (
    <div style={{ fontSize: "10px", color: "#9090b0" }}>
      <div>Blocks: {blocks.join(" · ")}</div>
      <div style={{ marginTop: "4px" }}>
        Candidates: {String(step.candidate_count)} · Held: {String(step.held_count)} ·
        Prompt: {Number(step.prompt_char_count).toLocaleString()} chars
      </div>
      <button
        onClick={() => setShowPrompt(!showPrompt)}
        style={{
          marginTop: "8px",
          fontSize: "9px",
          background: "rgba(255,255,255,0.04)",
          color: "#9090b0",
          border: "1px solid rgba(255,255,255,0.08)",
          padding: "3px 8px",
          cursor: "pointer",
          fontFamily: FONT,
        }}
      >
        {showPrompt ? "Hide" : "Show"} full prompt
      </button>
      {showPrompt && (
        <pre
          style={{
            marginTop: "8px",
            padding: "8px",
            background: "rgba(0,0,0,0.3)",
            fontSize: "10px",
            whiteSpace: "pre-wrap",
            maxHeight: "400px",
            overflowY: "auto",
            color: "#a0a0c0",
          }}
        >
          {String(step.prompt_text ?? "")}
        </pre>
      )}
    </div>
  );
}

function CallStepBody({ step }: { step: DecisionStep }) {
  const [showResponse, setShowResponse] = useState(false);
  return (
    <div style={{ fontSize: "10px", color: "#9090b0" }}>
      <div>
        Model: <code>{String(step.model)}</code> · stop_reason: {String(step.finish_reason)}
      </div>
      <div style={{ marginTop: "4px" }}>
        Response: {Number(step.response_char_count).toLocaleString()} chars
        {step.response_token_count ? ` · ${step.response_token_count} tokens` : ""}
      </div>
      <button
        onClick={() => setShowResponse(!showResponse)}
        style={{
          marginTop: "8px",
          fontSize: "9px",
          background: "rgba(255,255,255,0.04)",
          color: "#9090b0",
          border: "1px solid rgba(255,255,255,0.08)",
          padding: "3px 8px",
          cursor: "pointer",
          fontFamily: FONT,
        }}
      >
        {showResponse ? "Hide" : "Show"} Claude's raw response
      </button>
      {showResponse && (
        <pre
          style={{
            marginTop: "8px",
            padding: "8px",
            background: "rgba(0,0,0,0.3)",
            fontSize: "10px",
            whiteSpace: "pre-wrap",
            maxHeight: "400px",
            overflowY: "auto",
            color: "#a0a0c0",
          }}
        >
          {String(step.raw_response ?? "")}
        </pre>
      )}
    </div>
  );
}

function ValidateStepBody({
  step,
  highlightProposalId,
}: {
  step: DecisionStep;
  highlightProposalId: string | null;
}) {
  const validations = (step.validations as Array<Record<string, unknown>>) ?? [];
  return (
    <div style={{ fontSize: "10px" }}>
      {validations.length === 0 ? (
        <div style={{ color: "#6a6a88" }}>No validations.</div>
      ) : (
        validations.map((v, i) => {
          const hl = v.proposal_id === highlightProposalId;
          return (
            <div
              key={i}
              style={{
                padding: "4px 8px",
                marginBottom: "2px",
                background: hl ? "rgba(124,92,252,0.15)" : "rgba(255,255,255,0.02)",
                borderLeft: hl ? "2px solid #7c5cfc" : "2px solid transparent",
                color: "#e0e0f0",
              }}
            >
              <strong style={{ color: v.action_type === "BUY" ? "#34d399" : "#f87171" }}>
                {String(v.action_type)}
              </strong>{" "}
              {String(v.ticker)} — {String(v.shares)} @ ${Number(v.price).toFixed(2)} ·
              stop ${Number(v.stop_loss).toFixed(2)} · TP ${Number(v.take_profit).toFixed(2)}
              <span style={{ color: "#5a5a78", marginLeft: "8px" }}>
                #{String(v.proposal_id ?? "")}
              </span>
            </div>
          );
        })
      )}
    </div>
  );
}

function ScoringStepBody({ step }: { step: DecisionStep }) {
  const candidates = (step.candidates as Array<Record<string, unknown>>) ?? [];
  const top = candidates.slice(0, 15);
  return (
    <div style={{ fontSize: "10px", color: "#9090b0" }}>
      <div style={{ marginBottom: "6px" }}>
        Scored {String(step.total_scored)} · threshold {String(step.threshold_applied)} ·
        top {String(step.top_n_selected)} selected
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "10px" }}>
        <thead>
          <tr style={{ color: "#5a5a78" }}>
            <th style={{ textAlign: "left", padding: "2px 4px" }}>Ticker</th>
            <th style={{ textAlign: "right", padding: "2px 4px" }}>Score</th>
            <th style={{ textAlign: "right", padding: "2px 4px" }}>Data</th>
          </tr>
        </thead>
        <tbody>
          {top.map((c, i) => (
            <tr key={i} style={{ color: "#e0e0f0" }}>
              <td style={{ padding: "2px 4px" }}>{String(c.ticker)}</td>
              <td style={{ textAlign: "right", padding: "2px 4px" }}>
                {Number(c.score ?? 0).toFixed(1)}
              </td>
              <td style={{ textAlign: "right", padding: "2px 4px", color: "#6a6a88" }}>
                {c.data_completeness != null ? `${c.data_completeness}/6` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {candidates.length > top.length && (
        <div style={{ color: "#5a5a78", marginTop: "4px" }}>
          + {candidates.length - top.length} more
        </div>
      )}
    </div>
  );
}

function Layer1StepBody({
  step,
  highlightProposalId,
}: {
  step: DecisionStep;
  highlightProposalId: string | null;
}) {
  const flagged = (step.flagged as Array<Record<string, unknown>>) ?? [];
  const notFlagged = (step.not_flagged as string[]) ?? [];
  return (
    <div style={{ fontSize: "10px", color: "#9090b0" }}>
      <div style={{ marginBottom: "6px" }}>
        Reviewed {String(step.positions_reviewed)} positions · {flagged.length} flagged
      </div>
      {flagged.map((f, i) => {
        const hl = f.proposal_id === highlightProposalId;
        return (
          <div
            key={i}
            style={{
              padding: "3px 6px",
              marginBottom: "2px",
              background: hl ? "rgba(124,92,252,0.15)" : "rgba(248,113,113,0.06)",
              borderLeft: hl ? "2px solid #7c5cfc" : "2px solid transparent",
              color: "#e0e0f0",
            }}
          >
            🔴 {String(f.ticker)} — {String(f.reason)}
            <span style={{ color: "#5a5a78", marginLeft: "8px" }}>
              urgency {String(f.urgency)} · #{String(f.proposal_id ?? "")}
            </span>
          </div>
        );
      })}
      {notFlagged.length > 0 && (
        <div style={{ color: "#5a5a78", marginTop: "6px" }}>
          Not flagged: {notFlagged.join(" ")}
        </div>
      )}
    </div>
  );
}

function RegimeStepBody({ step }: { step: DecisionStep }) {
  return (
    <div style={{ fontSize: "10px", color: "#9090b0" }}>
      <div>
        Benchmark: <code>{String(step.benchmark_symbol)}</code> ·
        Regime: <strong style={{ color: "#e0e0f0" }}>{String(step.regime)}</strong>
      </div>
      <div style={{ marginTop: "4px" }}>
        SMA50: {Number(step.sma_50).toFixed(2)} · SMA200: {Number(step.sma_200).toFixed(2)} ·
        Position multiplier: {Number(step.position_size_factor).toFixed(2)}×
      </div>
    </div>
  );
}

function ExecuteStepBody({
  step,
  highlightProposalId,
}: {
  step: DecisionStep;
  highlightProposalId: string | null;
}) {
  const txns = (step.transactions_written as Array<Record<string, unknown>>) ?? [];
  const drops = (step.drops as Array<Record<string, unknown>>) ?? [];
  return (
    <div style={{ fontSize: "10px", color: "#9090b0" }}>
      <div style={{ marginBottom: "6px" }}>
        Processed {((step.proposal_ids_processed as string[]) ?? []).length} proposals ·
        Wrote {txns.length} · Dropped {drops.length}
      </div>
      {txns.map((t, i) => {
        const hl = t.proposal_id === highlightProposalId;
        return (
          <div
            key={i}
            style={{
              padding: "3px 6px",
              marginBottom: "2px",
              background: hl ? "rgba(124,92,252,0.15)" : "rgba(52,211,153,0.06)",
              borderLeft: hl ? "2px solid #7c5cfc" : "2px solid transparent",
              color: "#e0e0f0",
            }}
          >
            ✅ {String(t.action)} {String(t.ticker)} — {String(t.shares)} @ ${Number(t.price).toFixed(2)}
            <span style={{ color: "#5a5a78", marginLeft: "8px" }}>
              tx={String(t.transaction_id)} · #{String(t.proposal_id ?? "")}
            </span>
          </div>
        );
      })}
      {drops.map((d, i) => {
        const hl = d.proposal_id === highlightProposalId;
        return (
          <div
            key={`d${i}`}
            style={{
              padding: "3px 6px",
              marginBottom: "2px",
              background: hl ? "rgba(124,92,252,0.15)" : "rgba(248,113,113,0.06)",
              borderLeft: hl ? "2px solid #7c5cfc" : "2px solid transparent",
              color: "#e0e0f0",
            }}
          >
            ⛔ {String(d.ticker)} — {String(d.reason)}
            <span style={{ color: "#5a5a78", marginLeft: "8px" }}>
              dropped at {String(d.dropped_at ?? "?")} · #{String(d.proposal_id ?? "")}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function JsonFallback({ step }: { step: DecisionStep }) {
  const { step_name, step_type, started_at, duration_ms, error, ...rest } = step;
  void step_name; void step_type; void started_at; void duration_ms; void error;
  return (
    <pre
      style={{
        fontSize: "10px",
        color: "#9090b0",
        whiteSpace: "pre-wrap",
        margin: 0,
      }}
    >
      {JSON.stringify(rest, null, 2)}
    </pre>
  );
}

// ─── Diff view ───────────────────────────────────────────────────────────────

function DiffView({
  portfolioId,
  traceA,
  traceB,
  onExit,
}: {
  portfolioId: string;
  traceA: string;
  traceB: string;
  onExit: () => void;
}) {
  const { data: diff, isLoading } = useQuery<DecisionDiff>({
    queryKey: ["decision-diff", portfolioId, traceA, traceB],
    queryFn: () => api.diffDecisions(portfolioId, traceA, traceB),
  });

  return (
    <div>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: "16px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          paddingBottom: "10px",
        }}
      >
        <div style={{ color: "#e0e0f0", fontSize: "14px", fontWeight: 600 }}>
          Decision Diff
        </div>
        <button
          onClick={onExit}
          style={{
            fontSize: "10px",
            background: "rgba(255,255,255,0.05)",
            color: "#9090b0",
            border: "1px solid rgba(255,255,255,0.1)",
            padding: "4px 10px",
            cursor: "pointer",
            fontFamily: FONT,
          }}
        >
          ✕ exit diff
        </button>
      </header>

      {isLoading || !diff ? (
        <div style={{ color: "#5a5a78" }}>Computing diff…</div>
      ) : (
        <>
          <div style={{ color: "#9090b0", fontSize: "11px", marginBottom: "12px" }}>
            <div>
              <strong>A:</strong> {diff.trace_a.trace_id}{" "}
              <span style={{ color: "#5a5a78" }}>
                ({new Date(diff.trace_a.timestamp).toLocaleString()})
              </span>
            </div>
            <div>
              <strong>B:</strong> {diff.trace_b.trace_id}{" "}
              <span style={{ color: "#5a5a78" }}>
                ({new Date(diff.trace_b.timestamp).toLocaleString()})
              </span>
            </div>
          </div>

          {diff.deltas.length === 0 ? (
            <div style={{ color: "#6a6a88", padding: "12px" }}>
              No structural deltas between these traces.
            </div>
          ) : (
            diff.deltas.map((d, i) => (
              <div
                key={i}
                style={{
                  padding: "8px 12px",
                  marginBottom: "6px",
                  background: "rgba(255,255,255,0.03)",
                  borderLeft: `2px solid ${stepAccentColor(d.step_type)}`,
                  fontSize: "11px",
                  color: "#e0e0f0",
                  fontFamily: FONT,
                }}
              >
                <div style={{ color: "#9090b0", fontSize: "9px", letterSpacing: "0.08em" }}>
                  {stepLabel(d.step_type)} · {d.kind.toUpperCase()}
                </div>
                <div style={{ marginTop: "2px" }}>
                  {renderDeltaBody(d)}
                </div>
              </div>
            ))
          )}
        </>
      )}
    </div>
  );
}

function renderDeltaBody(d: Record<string, unknown>): string {
  // Concise prose for each delta kind
  if (d.field) {
    return `${String(d.field)}: ${String(d.from ?? "—")} → ${String(d.to ?? "—")}`;
  }
  if (d.ticker && d.from != null && d.to != null) {
    return `${String(d.ticker)}: ${String(d.from)} → ${String(d.to)}`;
  }
  if (d.ticker) {
    return String(d.ticker);
  }
  if (d.block) {
    return String(d.block);
  }
  return JSON.stringify({ ...d, step_type: undefined, kind: undefined });
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function stepAccentColor(stepType: string): string {
  const c: Record<string, string> = {
    regime_detection: "#60a5fa",
    layer1_risk: "#f87171",
    watchlist_scoring: "#a78bfa",
    ai_allocator_prompt: "#34d399",
    ai_allocator_call: "#34d399",
    ai_allocator_parse: "#fbbf24",
    ai_allocator_validate: "#fbbf24",
    result_assemble: "#7c5cfc",
    execute: "#7c5cfc",
  };
  return c[stepType] ?? "#5a5a78";
}

function stepLabel(stepType: string): string {
  const labels: Record<string, string> = {
    regime_detection: "Regime detection",
    layer1_risk: "Layer 1 — risk review",
    watchlist_scoring: "Watchlist scoring",
    ai_allocator_prompt: "AI prompt build",
    ai_allocator_call: "AI call (Claude)",
    ai_allocator_parse: "AI response parse",
    ai_allocator_validate: "AI validation",
    result_assemble: "Result assemble",
    execute: "Execute",
  };
  return labels[stepType] ?? stepType;
}

function EmptyState() {
  return (
    <div style={{ color: "#6a6a88", fontFamily: FONT, fontSize: "11px", padding: "20px" }}>
      Pick a trace on the left to view its decision tree.
    </div>
  );
}
