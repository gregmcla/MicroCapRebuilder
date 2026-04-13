/** Actions tab — ANALYZE results, EXECUTE flow, and pre-flight dashboard. */

import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAnalysisStore, usePortfolioStore } from "../lib/store";
import { play } from "../lib/sounds";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { useMarketIndices } from "../hooks/useMarketIndices";
import { api } from "../lib/api";
import type { ReviewedAction, WatchlistCandidate } from "../lib/types";

function ConfidenceDot({ confidence }: { confidence: number }) {
  const color =
    confidence >= 0.8
      ? "var(--green)"
      : confidence >= 0.5
        ? "var(--amber)"
        : "var(--red)";
  return (
    <span
      style={{ background: color, flexShrink: 0 }}
      className="inline-block w-2 h-2 rounded-full"
      title={`${(confidence * 100).toFixed(0)}% confidence`}
    />
  );
}

function DecisionBadge({ decision }: { decision: string }) {
  const styleMap: Record<string, React.CSSProperties> = {
    APPROVE: {
      background: "var(--green-dim)",
      color: "var(--green)",
    },
    MODIFY: {
      background: "var(--amber-dim)",
      color: "var(--amber)",
    },
    VETO: {
      background: "var(--red-dim)",
      color: "var(--red)",
    },
  };
  const style = styleMap[decision] ?? { background: "rgba(148,163,184,0.08)", color: "var(--text-secondary)" };
  return (
    <span
      style={{
        ...style,
        padding: "2px 6px",
        borderRadius: 4,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.06em",
      }}
    >
      {decision}
    </span>
  );
}

function ActionCard({ action }: { action: ReviewedAction }) {
  const { original, decision, ai_reasoning, confidence } = action;
  const isBuy = original.action_type === "BUY";
  const { data: state } = usePortfolioState();

  // For sell proposals: look up position to compute P/L and days held
  const position = !isBuy ? (state?.positions.find(p => p.ticker === original.ticker) ?? null) : null;
  const pnlPct = position != null
    ? (original.price - position.avg_cost_basis) / position.avg_cost_basis * 100
    : null;
  const isProfit = pnlPct != null ? pnlPct >= 0 : null;
  const daysHeld = position?.entry_date
    ? Math.floor((Date.now() - new Date(position.entry_date).getTime()) / (1000 * 60 * 60 * 24))
    : null;

  return (
    <div
      className="card-hover p-3"
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
      }}
    >
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2">
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "2px 6px",
            borderRadius: 4,
            ...(isBuy
              ? { background: "var(--green-dim)", color: "var(--green)" }
              : { background: "var(--red-dim)", color: "var(--red)" }),
          }}
        >
          {original.action_type}
        </span>
        <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
          {original.ticker}
        </span>
        {/* P/L badge + days held for sells */}
        {!isBuy && isProfit != null && (
          <span
            className="font-bold px-1.5 py-0.5 rounded"
            style={{
              fontSize: "10px",
              background: isProfit ? "rgba(52,211,153,0.15)" : "rgba(248,113,113,0.15)",
              color: isProfit ? "var(--green)" : "var(--red)",
            }}
          >
            {isProfit ? "P" : "L"} {pnlPct != null ? `${pnlPct > 0 ? "+" : ""}${pnlPct.toFixed(1)}%` : ""}
          </span>
        )}
        {!isBuy && daysHeld != null && (
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
            {daysHeld}d held
          </span>
        )}
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-secondary)" }}>
          {action.modified_shares ?? original.shares} shares @
          ${original.price.toFixed(2)}
          <span style={{ color: "var(--text-dim)", marginLeft: "6px" }}>
            ${((action.modified_shares ?? original.shares) * original.price).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </span>
        <div className="flex-1" />
        <ConfidenceDot confidence={confidence} />
        <DecisionBadge decision={decision} />
      </div>

      {/* Quant score + factor breakdown for buys */}
      {isBuy && original.quant_score > 0 && (
        <div className="flex items-center gap-3 mb-2">
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              fontWeight: 600,
              color: "var(--accent)",
            }}
          >
            {original.quant_score.toFixed(0)}/100
          </span>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {Object.entries(original.factor_scores).map(([k, v]) => (
              <span
                key={k}
                style={{
                  fontSize: 9,
                  padding: "1px 5px",
                  borderRadius: 3,
                  background: "var(--bg-void)",
                  color: "var(--text-muted)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {k.slice(0, 3)} {typeof v === "number" ? v.toFixed(0) : v}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Stops — only relevant for buys */}
      {isBuy && (
        <div style={{ display: "flex", gap: 12, marginBottom: 6, fontSize: 11, color: "var(--text-secondary)" }}>
          <span>
            Stop:{" "}
            <span style={{ fontFamily: "var(--font-mono)", color: "var(--red)" }}>
              ${(action.modified_stop ?? original.stop_loss).toFixed(2)}
            </span>
          </span>
          <span>
            Target:{" "}
            <span style={{ fontFamily: "var(--font-mono)", color: "var(--green)" }}>
              ${(action.modified_target ?? original.take_profit).toFixed(2)}
            </span>
          </span>
        </div>
      )}

      {/* AI reasoning */}
      <p style={{ fontSize: 12, color: "var(--text-secondary)", fontStyle: "italic", lineHeight: 1.6 }}>
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
  color: "var(--text-muted)",
};

// ---------------------------------------------------------------------------
// Source badge for watchlist candidates
// ---------------------------------------------------------------------------

const SOURCE_LABELS: Record<string, string> = {
  MOMENTUM_BREAKOUT: "MOM",
  SECTOR_LEADER: "SEC",
  MEAN_REVERSION: "REV",
  VOLUME_SURGE: "VOL",
  RSI_OVERSOLD: "RSI",
  VOLATILITY_CONTRACTION: "VLT",
};

function SourceBadge({ source }: { source: string }) {
  const label = SOURCE_LABELS[source] ?? source.slice(0, 3);
  return (
    <span style={{
      fontSize: 8, fontWeight: 700, letterSpacing: "0.05em",
      padding: "1px 4px", borderRadius: 3,
      background: "var(--accent-dim)", color: "var(--accent)",
    }}>
      {label}
    </span>
  );
}

const HEAT_STYLE: Record<string, { color: string; bg: string; pulse?: boolean }> = {
  WARM:    { color: "#fbbf24",   bg: "rgba(251,191,36,0.12)" },
  HOT:     { color: "#f97316",   bg: "rgba(249,115,22,0.12)" },
  SPIKING: { color: "var(--red)",   bg: "rgba(248,113,113,0.15)", pulse: true },
};

function SocialHeatBadge({ heat }: { heat?: string }) {
  if (!heat || heat === "COLD" || heat === "") return null;
  const style = HEAT_STYLE[heat];
  if (!style) return null;
  return (
    <span
      className={style.pulse ? "animate-pulse" : ""}
      style={{
        fontSize: "9px",
        fontWeight: 600,
        padding: "1px 5px",
        borderRadius: "3px",
        letterSpacing: "0.06em",
        color: style.color,
        background: style.bg,
        marginLeft: "4px",
      }}
    >
      {heat}
    </span>
  );
}

function CandidateRow({ c }: { c: WatchlistCandidate }) {
  const scoreColor = c.score >= 80 ? "var(--green)" : c.score >= 60 ? "var(--amber)" : "var(--text-secondary)";
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 6,
      padding: "5px 0", borderBottom: "1px solid var(--border)",
    }}>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700, color: "var(--text-primary)", width: 36, flexShrink: 0 }}>
        {c.ticker}
      </span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, color: scoreColor, width: 28, flexShrink: 0 }}>
        {c.score}
      </span>
      <SourceBadge source={c.source} />
      <SocialHeatBadge heat={c.social_heat} />
      <span style={{ flex: 1, fontSize: 9.5, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {c.sector}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pre-flight dashboard (shown when no analysis result)
// ---------------------------------------------------------------------------

function PreFlightDashboard({ onAnalyze, lastAnalyzedAt, error }: {
  onAnalyze: () => void;
  lastAnalyzedAt: string | null;
  error: string | null;
}) {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const { data: state } = usePortfolioState();
  const { data: indices } = useMarketIndices();
  const { data: wl } = useQuery({
    queryKey: ["watchlist", portfolioId],
    queryFn: () => api.getWatchlist(portfolioId),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const { data: scanStatus } = useQuery({
    queryKey: ["scanStatus", portfolioId],
    queryFn: () => api.scanStatus(portfolioId),
    staleTime: Infinity,
    retry: false,
  });

  const regime = state?.regime ?? null;
  const cash = state?.cash ?? 0;
  const numPositions = state?.num_positions ?? 0;
  const staleAlerts = state?.stale_alerts ?? [];
  const deployedPct = state && state.total_equity > 0
    ? Math.round(state.positions_value / state.total_equity * 100)
    : 0;

  const regimeColor = regime === "BULL" ? "var(--green)" : regime === "BEAR" ? "var(--red)" : "var(--amber)";
  const candidates = wl?.candidates ?? [];
  const totalCandidates = wl?.total ?? 0;

  function relTime(iso: string | null | undefined): string {
    if (!iso) return "";
    const sec = (Date.now() - new Date(iso).getTime()) / 1000;
    if (sec < 90) return "just now";
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
    return `${Math.floor(sec / 86400)}d ago`;
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 9, fontWeight: 700, textTransform: "uppercase",
    letterSpacing: "0.10em", color: "var(--text-muted)", marginBottom: 8,
  };
  const sectionStyle: React.CSSProperties = {
    padding: "10px 14px",
    borderBottom: "1px solid var(--border)",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflowY: "auto" }}>

      {/* Market context */}
      <div style={sectionStyle}>
        <p style={labelStyle}>Market</p>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          {regime && (
            <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
              <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: regimeColor, flexShrink: 0 }} />
              <span style={{ fontSize: "11px", fontWeight: 700, color: regimeColor }}>{regime}</span>
            </div>
          )}
          {indices?.sp500 && (
            <span style={{ fontSize: 10.5, color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
              S&P <span style={{ color: indices.sp500.change_pct >= 0 ? "var(--green)" : "var(--red)", fontWeight: 600 }}>
                {indices.sp500.change_pct >= 0 ? "+" : ""}{indices.sp500.change_pct.toFixed(2)}%
              </span>
            </span>
          )}
          {indices?.vix && (
            <span style={{ fontSize: 10.5, color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
              VIX <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{indices.vix.value.toFixed(1)}</span>
            </span>
          )}
        </div>
      </div>

      {/* Portfolio capacity */}
      <div style={sectionStyle}>
        <p style={labelStyle}>Portfolio</p>
        <div style={{ display: "flex", gap: 16 }}>
          <div>
            <p style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 2 }}>Positions</p>
            <p style={{ fontSize: 15, fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{numPositions}</p>
          </div>
          <div>
            <p style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 2 }}>Deployed</p>
            <p style={{ fontSize: 15, fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{deployedPct}%</p>
          </div>
          <div>
            <p style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 2 }}>Cash</p>
            <p style={{ fontSize: 15, fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
              ${cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </p>
          </div>
        </div>
        {staleAlerts.length > 0 && (
          <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 4 }}>
            {staleAlerts.slice(0, 6).map((t) => (
              <span key={t} style={{
                fontSize: 9, padding: "2px 6px", borderRadius: 3,
                background: "var(--amber-dim)", color: "var(--amber)",
                fontFamily: "var(--font-mono)", fontWeight: 600,
              }}>
                {t} stale
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Watchlist candidates */}
      <div style={{ ...sectionStyle, flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
          <p style={{ ...labelStyle, marginBottom: 0 }}>Watchlist Candidates</p>
          <span style={{ fontSize: 9, color: "var(--text-muted)" }}>
            {totalCandidates > 0 ? `${totalCandidates} active` : "—"}
            {scanStatus?.status === "complete" && scanStatus.finished_at && (
              <> · {relTime(scanStatus.finished_at)}</>
            )}
          </span>
        </div>

        {candidates.length === 0 ? (
          <p style={{ fontSize: 11, color: "var(--text-muted)" }}>
            No watchlist data. Run SCAN first to discover candidates.
          </p>
        ) : (
          <div>
            <div style={{ display: "flex", gap: 6, marginBottom: 6, fontSize: 9, color: "var(--text-muted)", fontWeight: 600, letterSpacing: "0.05em" }}>
              <span style={{ width: "36px" }}>TICKER</span>
              <span style={{ width: "28px" }}>SCORE</span>
              <span>SRC</span>
              <span style={{ marginLeft: "4px" }}>SECTOR</span>
            </div>
            {candidates.map((c) => <CandidateRow key={c.ticker} c={c} />)}
          </div>
        )}
      </div>

      {/* CTA */}
      <div style={{ padding: "12px 14px", borderTop: "1px solid var(--border)", background: "var(--bg-void)" }}>
        {lastAnalyzedAt && (
          <p style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 8 }}>
            Last run: {lastAnalyzedAt}
          </p>
        )}
        {error && (
          <p style={{ fontSize: 9, color: "var(--red)", marginBottom: 6 }}>{error}</p>
        )}
        <button
          onClick={onAnalyze}
          style={{
            width: "100%", padding: "9px 0", fontSize: "11px", fontWeight: 700,
            letterSpacing: "0.10em", textTransform: "uppercase",
            background: "var(--accent-dim)",
            color: "var(--accent)", border: "none", borderRadius: "6px", cursor: "pointer",
            boxShadow: "0 0 16px rgba(124,92,252,0.35), inset 0 1px 0 rgba(255,255,255,0.15)",
            transition: "box-shadow 0.15s",
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 24px rgba(124,92,252,0.55), inset 0 1px 0 rgba(255,255,255,0.15)"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 16px rgba(124,92,252,0.35), inset 0 1px 0 rgba(255,255,255,0.15)"; }}
        >
          ✦ Analyze
        </button>
      </div>
    </div>
  );
}

export default function ActionsTab() {
  const { result, isAnalyzing, isExecuting, error, lastAnalyzedAt, runAnalysis, runExecute } =
    useAnalysisStore();

  // Detect analyze complete → play sound
  const wasAnalyzing = useRef(false);
  useEffect(() => {
    if (wasAnalyzing.current && !isAnalyzing && result) play("analyzeComplete");
    wasAnalyzing.current = isAnalyzing;
  }, [isAnalyzing, result]);

  const handleAnalyze = () => { play("analyze"); runAnalysis(); };
  const handleExecute = () => { play("execute"); runExecute(); };

  // No analysis yet → show pre-flight dashboard
  if (!result && !isAnalyzing) {
    return <PreFlightDashboard onAnalyze={handleAnalyze} lastAnalyzedAt={lastAnalyzedAt} error={error} />;
  }

  // Analyzing spinner
  if (isAnalyzing) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <div
          className="w-8 h-8 border-2 rounded-full animate-spin"
          style={{
            borderColor: "var(--accent-dim)",
            borderTopColor: "var(--accent)",
          }}
        />
        <p style={{ fontSize: 13, color: "var(--text-primary)" }}>GScott's analyzing the market...</p>
        <p style={{ fontSize: 11, color: "var(--text-secondary)" }}>Scoring candidates, running AI review</p>
      </div>
    );
  }

  if (!result) return null;

  const { approved, modified, vetoed, summary } = result;
  // Deduplicate by ticker+action_type — keep the entry with the richest reasoning
  const allActionable = [...approved, ...modified];
  const seen = new Map<string, ReviewedAction>();
  for (const a of allActionable) {
    const key = `${a.original.ticker}:${a.original.action_type}`;
    const existing = seen.get(key);
    if (!existing || (a.ai_reasoning?.length ?? 0) > (existing.ai_reasoning?.length ?? 0)) {
      seen.set(key, a);
    }
  }
  const actionable = [...seen.values()];

  // Analysis ran but found nothing
  if (summary.total_proposed === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4" style={{ color: "var(--text-secondary)" }}>
        <div className="text-4xl">&#x1F937;</div>
        <p style={{ fontSize: 13, fontWeight: 500, color: "var(--text-secondary)" }}>No opportunities found</p>
        <p style={{ fontSize: 11, textAlign: "center", maxWidth: 260, color: "var(--text-secondary)" }}>
          GScott scanned the watchlist but didn't find any trades worth making right now.
          Try running SCAN first to refresh candidates.
        </p>
        {lastAnalyzedAt && (
          <p style={{ fontSize: 11, color: "var(--text-muted)" }}>
            Analyzed at {lastAnalyzedAt}
          </p>
        )}
        <button
          onClick={handleAnalyze}
          style={{
            padding: "4px 12px",
            fontSize: 11,
            fontWeight: 500,
            borderRadius: "var(--radius)",
            background: "var(--bg-surface)",
            color: "var(--text-secondary)",
            border: "1px solid var(--border)",
            cursor: "pointer",
          }}
          onMouseEnter={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.borderColor = "var(--accent)";
            el.style.color = "var(--accent)";
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.borderColor = "var(--border)";
            el.style.color = "var(--text-secondary)";
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
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "6px 16px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-surface)",
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
          {summary.total_proposed} proposed
        </span>
        <span style={{ fontSize: 11, color: "var(--green)" }}>
          {summary.approved} approved
        </span>
        {summary.modified > 0 && (
          <span style={{ fontSize: 11, color: "var(--amber)" }}>
            {summary.modified} modified
          </span>
        )}
        {summary.vetoed > 0 && (
          <span style={{ fontSize: 11, color: "var(--red)" }}>{summary.vetoed} vetoed</span>
        )}
        {result.ai_mode && (
          <span style={{
            fontSize: "9px",
            fontWeight: 700,
            letterSpacing: "0.08em",
            padding: "2px 8px",
            borderRadius: "3px",
            background: result.ai_mode === "claude"
              ? "rgba(74,222,128,0.12)"
              : "rgba(248,113,113,0.15)",
            color: result.ai_mode === "claude"
              ? "var(--green)"
              : "var(--red)",
            border: `1px solid ${result.ai_mode === "claude"
              ? "rgba(74,222,128,0.25)"
              : "rgba(248,113,113,0.3)"}`,
          }}>
            {result.ai_mode === "claude" ? "AI MODE" : "FALLBACK"}
          </span>
        )}
        <div className="flex-1" />
        {summary.can_execute && (
          <button
            onClick={handleExecute}
            disabled={isExecuting}
            style={{
              padding: "3px 10px",
              fontSize: 11,
              fontWeight: 600,
              borderRadius: "var(--radius)",
              background: "var(--green-dim)",
              color: "var(--green)",
              border: "none",
              cursor: isExecuting ? "default" : "pointer",
              opacity: isExecuting ? 0.5 : 1,
            }}
          >
            {isExecuting ? "Executing..." : `EXECUTE ${actionable.length}`}
          </button>
        )}
        <button
          onClick={handleAnalyze}
          style={{
            padding: "3px 10px",
            fontSize: 11,
            fontWeight: 500,
            borderRadius: "var(--radius)",
            background: "var(--bg-elevated)",
            color: "var(--text-secondary)",
            border: "1px solid var(--border)",
            cursor: "pointer",
          }}
          onMouseEnter={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.borderColor = "var(--accent)";
            el.style.color = "var(--accent)";
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget as HTMLButtonElement;
            el.style.borderColor = "var(--border)";
            el.style.color = "var(--text-secondary)";
          }}
        >
          Re-analyze
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: "6px 16px",
            fontSize: 11,
            color: "var(--red)",
            background: "var(--red-dim)",
            borderBottom: "1px solid rgba(239,68,68,0.2)",
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
