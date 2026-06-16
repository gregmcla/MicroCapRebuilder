/** Actions tab — ANALYZE results, EXECUTE flow, and pre-flight dashboard. */

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAnalysisStore, usePortfolioStore, type AnalysisMode } from "../lib/store";
import { play } from "../lib/sounds";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { useMarketIndices } from "../hooks/useMarketIndices";
import { api } from "../lib/api";
import type { ReviewedAction, WatchlistCandidate } from "../lib/types";
import { HeatBadge, SourceBadge } from "./ui";

const MODE_BUTTONS: { mode: AnalysisMode; label: string }[] = [
  { mode: "full", label: "FULL" },
  { mode: "buys_only", label: "BUYS ONLY" },
  { mode: "sells_only", label: "SELLS ONLY" },
];

function ModeSwitcher({
  activeMode,
  setActiveMode,
  countFor,
}: {
  activeMode: AnalysisMode;
  setActiveMode: (m: AnalysisMode) => void;
  countFor: (mode: AnalysisMode) => number;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 2,
        padding: "8px 12px 4px 12px",
        fontSize: 10,
      }}
    >
      {MODE_BUTTONS.map(({ mode, label }) => {
        const isActive = activeMode === mode;
        const count = countFor(mode);
        return (
          <button
            key={mode}
            onClick={() => setActiveMode(mode)}
            style={{
              padding: "4px 10px",
              border: `1px solid ${isActive ? "rgba(255,255,255,0.4)" : "rgba(255,255,255,0.1)"}`,
              background: isActive ? "rgba(255,255,255,0.1)" : "transparent",
              color: isActive ? "#fff" : "rgba(255,255,255,0.5)",
              cursor: "pointer",
              letterSpacing: "0.05em",
              fontWeight: 600,
            }}
          >
            {label}
            {count > 0 ? ` (${count})` : ""}
          </button>
        );
      })}
    </div>
  );
}

function modeEmptyCopy(mode: AnalysisMode): string {
  switch (mode) {
    case "buys_only":
      return "No buys-only analysis run yet. Click ANALYZE BUYS above.";
    case "sells_only":
      return "No sells-only analysis run yet. Click ANALYZE SELLS above.";
    case "full":
    default:
      return "No analysis run yet. Click ANALYZE above.";
  }
}

function executeLabel(mode: AnalysisMode, count: number, totalCount: number, isExecuting: boolean): string {
  if (isExecuting) return "Executing...";
  const suffix = mode !== "full" && count !== totalCount ? `${count} / ${totalCount}` : String(count);
  switch (mode) {
    case "buys_only":  return `EXECUTE BUYS (${suffix})`;
    case "sells_only": return `EXECUTE SELLS (${suffix})`;
    default:           return `EXECUTE (${suffix})`;
  }
}

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
          <span className="text-xs" style={{ color: "var(--text-0)" }}>
            {daysHeld}d held
          </span>
        )}
        <span className="font-mono text-xs" style={{ color: "var(--text-1)" }}>
          {action.modified_shares ?? original.shares} shares @
          ${original.price.toFixed(2)}
          <span style={{ color: "var(--text-0)", marginLeft: "6px" }}>
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

      {/* Stops — only relevant for buys */}
      {isBuy && (
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
      )}

      {/* AI reasoning */}
      <p className="text-xs leading-relaxed" style={{ color: "var(--text-2)", lineHeight: 1.65 }}>
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

// Source labels + heat tones now live in ./ui/Badge.tsx (SourceBadge, HeatBadge).
// SOURCE_LABELS is kept here as the domain-specific label map passed to the
// shared SourceBadge.

function CandidateRow({ c }: { c: WatchlistCandidate }) {
  const scoreColor = c.score >= 80 ? "var(--green)" : c.score >= 60 ? "var(--amber)" : "var(--text-1)";
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: "6px",
      padding: "5px 0", borderBottom: "1px solid var(--border-0)",
    }}>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px", fontWeight: 700, color: "var(--text-4)", width: "36px", flexShrink: 0 }}>
        {c.ticker}
      </span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px", fontWeight: 600, color: scoreColor, width: "28px", flexShrink: 0 }}>
        {c.score}
      </span>
      <SourceBadge source={c.source} labels={SOURCE_LABELS} />
      <HeatBadge heat={c.social_heat} />
      <span style={{ flex: 1, fontSize: "9.5px", color: "var(--text-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
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
    fontSize: "9px", fontWeight: 700, textTransform: "uppercase",
    letterSpacing: "0.10em", color: "var(--text-0)", marginBottom: "8px",
  };
  const sectionStyle: React.CSSProperties = {
    padding: "10px 14px",
    borderBottom: "1px solid var(--border-0)",
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
            <span style={{ fontSize: "10.5px", color: "var(--text-1)", fontFamily: "var(--font-mono)" }}>
              S&P <span style={{ color: indices.sp500.change_pct >= 0 ? "var(--green)" : "var(--red)", fontWeight: 600 }}>
                {indices.sp500.change_pct >= 0 ? "+" : ""}{indices.sp500.change_pct.toFixed(2)}%
              </span>
            </span>
          )}
          {indices?.vix && (
            <span style={{ fontSize: "10.5px", color: "var(--text-1)", fontFamily: "var(--font-mono)" }}>
              VIX <span style={{ fontWeight: 600, color: "var(--text-3)" }}>{indices.vix.value.toFixed(1)}</span>
            </span>
          )}
        </div>
      </div>

      {/* Portfolio capacity */}
      <div style={sectionStyle}>
        <p style={labelStyle}>Portfolio</p>
        <div style={{ display: "flex", gap: "16px" }}>
          <div>
            <p style={{ fontSize: "9px", color: "var(--text-0)", marginBottom: "2px" }}>Positions</p>
            <p style={{ fontSize: "15px", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--text-3)" }}>{numPositions}</p>
          </div>
          <div>
            <p style={{ fontSize: "9px", color: "var(--text-0)", marginBottom: "2px" }}>Deployed</p>
            <p style={{ fontSize: "15px", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--text-3)" }}>{deployedPct}%</p>
          </div>
          <div>
            <p style={{ fontSize: "9px", color: "var(--text-0)", marginBottom: "2px" }}>Cash</p>
            <p style={{ fontSize: "15px", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--text-3)" }}>
              ${cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </p>
          </div>
        </div>
        {staleAlerts.length > 0 && (
          <div style={{ marginTop: "8px", display: "flex", flexWrap: "wrap", gap: "4px" }}>
            {staleAlerts.slice(0, 6).map((t) => (
              <span key={t} style={{
                fontSize: "9px", padding: "2px 6px", borderRadius: "3px",
                background: "rgba(251,191,36,0.12)", color: "var(--amber)",
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
          <span style={{ fontSize: "9px", color: "var(--text-0)" }}>
            {totalCandidates > 0 ? `${totalCandidates} active` : "—"}
            {scanStatus?.status === "complete" && scanStatus.finished_at && (
              <> · {relTime(scanStatus.finished_at)}</>
            )}
          </span>
        </div>

        {candidates.length === 0 ? (
          <p style={{ fontSize: "11px", color: "var(--text-0)" }}>
            No watchlist data. Run SCAN first to discover candidates.
          </p>
        ) : (
          <div>
            <div style={{ display: "flex", gap: "6px", marginBottom: "6px", fontSize: "9px", color: "var(--text-0)", fontWeight: 600, letterSpacing: "0.05em" }}>
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
      <div style={{ padding: "12px 14px", borderTop: "1px solid var(--border-0)", background: "var(--surface-0)" }}>
        {lastAnalyzedAt && (
          <p style={{ fontSize: "9px", color: "var(--text-0)", marginBottom: "8px" }}>
            Last run: {lastAnalyzedAt}
          </p>
        )}
        {error && (
          <p style={{ fontSize: "9px", color: "var(--red)", marginBottom: "6px" }}>{error}</p>
        )}
        <button
          onClick={onAnalyze}
          style={{
            width: "100%", padding: "9px 0", fontSize: "11px", fontWeight: 700,
            letterSpacing: "0.10em", textTransform: "uppercase",
            background: "linear-gradient(135deg, #7c5cfc 0%, #9b7eff 100%)",
            color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer",
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
  const activeMode = useAnalysisStore((s) => s.activeMode);
  const setActiveMode = useAnalysisStore((s) => s.setActiveMode);
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const slots = useAnalysisStore((s) => s.portfolioAnalyses[portfolioId]);
  const countFor = (mode: AnalysisMode) => slots?.[mode]?.result?.approved?.length ?? 0;

  // Detect analyze complete → play sound
  const wasAnalyzing = useRef(false);
  useEffect(() => {
    if (wasAnalyzing.current && !isAnalyzing && result) play("analyzeComplete");
    wasAnalyzing.current = isAnalyzing;
  }, [isAnalyzing, result]);

  // Per-trade selection is available in every mode (incl. full) so a single
  // questionable proposal can be unchecked without vetoing the whole batch.
  // Defaults to all-selected; the backend cherry-picks via selected_tickers.
  const isSelectable = true;

  // Per-trade selection state.
  // Key format: "TICKER:ACTION_TYPE" — mirrors the dedup key used in actionable list.
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(() => new Set());

  // Reset to all-selected whenever the result or mode changes.
  useEffect(() => {
    if (!result || !isSelectable) { setSelectedKeys(new Set()); return; }
    const keys = new Set<string>();
    for (const a of [...result.approved, ...result.modified]) {
      keys.add(`${a.original.ticker}:${a.original.action_type}`);
    }
    setSelectedKeys(keys);
  }, [result, activeMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleKey = (key: string) => {
    setSelectedKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const handleAnalyze = () => { play("analyze"); runAnalysis(activeMode); };
  const handleExecute = () => {
    play("execute");
    if (isSelectable && selectedKeys.size > 0) {
      runExecute(activeMode, [...selectedKeys].map(k => k.split(":")[0]));
    } else {
      runExecute(activeMode);
    }
  };

  // No analysis yet for the active mode → show pre-flight dashboard with mode switcher + per-mode empty copy
  if (!result && !isAnalyzing) {
    return (
      <div className="flex flex-col h-full">
        <ModeSwitcher activeMode={activeMode} setActiveMode={setActiveMode} countFor={countFor} />
        <p
          style={{
            fontSize: 11,
            color: "var(--text-0)",
            padding: "0 14px 8px 14px",
          }}
        >
          {modeEmptyCopy(activeMode)}
        </p>
        <div className="flex-1 min-h-0">
          <PreFlightDashboard onAnalyze={handleAnalyze} lastAnalyzedAt={lastAnalyzedAt} error={error} />
        </div>
      </div>
    );
  }

  // Analyzing spinner
  if (isAnalyzing) {
    return (
      <div className="flex flex-col h-full">
        <ModeSwitcher activeMode={activeMode} setActiveMode={setActiveMode} countFor={countFor} />
        <div className="flex flex-col items-center justify-center flex-1 gap-3">
          <div
            className="w-8 h-8 border-2 rounded-full animate-spin"
            style={{
              borderColor: "rgba(124,92,252,0.3)",
              borderTopColor: "var(--accent)",
            }}
          />
          <p className="text-sm" style={{ color: "var(--text-4)" }}>GScott's analyzing the market...</p>
          <p className="text-xs" style={{ color: "var(--text-2)" }}>Scoring candidates, running AI review</p>
        </div>
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

  // Selection helpers (only used in selectable modes)
  const actionableKeys = new Set(actionable.map(a => `${a.original.ticker}:${a.original.action_type}`));
  const allSelected = actionableKeys.size > 0 && [...actionableKeys].every(k => selectedKeys.has(k));
  const selectedCount = isSelectable ? [...actionableKeys].filter(k => selectedKeys.has(k)).length : actionable.length;
  const toggleAll = () => setSelectedKeys(allSelected ? new Set() : new Set(actionableKeys));

  // Analysis ran but found nothing
  if (summary.total_proposed === 0) {
    return (
      <div className="flex flex-col h-full">
        <ModeSwitcher activeMode={activeMode} setActiveMode={setActiveMode} countFor={countFor} />
        <div className="flex flex-col items-center justify-center flex-1 gap-4" style={{ color: "var(--text-1)" }}>
        <div className="text-4xl">&#x1F937;</div>
        <p className="text-sm font-medium" style={{ color: "var(--text-2)" }}>No opportunities found</p>
        <p className="text-xs text-center max-w-xs">
          GScott scanned the watchlist but didn't find any trades worth making right now.
          Try running SCAN first to refresh candidates.
        </p>
        {lastAnalyzedAt && (
          <p className="text-xs" style={{ color: "var(--text-0)" }}>
            Analyzed at {lastAnalyzedAt}
          </p>
        )}
        <button
          onClick={handleAnalyze}
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
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <ModeSwitcher activeMode={activeMode} setActiveMode={setActiveMode} countFor={countFor} />
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
        {isSelectable && actionable.length > 0 && (
          <button
            onClick={toggleAll}
            className="px-2 py-1 text-xs rounded transition-colors"
            style={{
              background: "transparent",
              border: "1px solid var(--border-0)",
              color: "var(--text-1)",
              cursor: "pointer",
            }}
          >
            {allSelected ? "None" : "All"}
          </button>
        )}
        {summary.can_execute && (
          <button
            onClick={handleExecute}
            disabled={isExecuting || (isSelectable && selectedCount === 0)}
            className="px-3 py-1 text-xs font-semibold rounded transition-all disabled:opacity-50"
            style={{
              background: "rgba(52,211,153,0.15)",
              color: "var(--green)",
            }}
          >
            {executeLabel(activeMode, selectedCount, actionable.length, isExecuting)}
          </button>
        )}
        <button
          onClick={handleAnalyze}
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
            {actionable.map((a, i) => {
              const key = `${a.original.ticker}:${a.original.action_type}`;
              return (
                <div key={`${a.original.ticker}-${i}`} className="flex items-start gap-2">
                  {isSelectable && (
                    <input
                      type="checkbox"
                      checked={selectedKeys.has(key)}
                      onChange={() => toggleKey(key)}
                      style={{
                        marginTop: "11px",
                        cursor: "pointer",
                        accentColor: "var(--accent)",
                        width: "14px",
                        height: "14px",
                        flexShrink: 0,
                      }}
                    />
                  )}
                  <div className="flex-1">
                    <ActionCard action={a} />
                  </div>
                </div>
              );
            })}
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
