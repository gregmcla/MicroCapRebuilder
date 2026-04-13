/** Actions tab — ANALYZE results, EXECUTE flow, and pre-flight dashboard. */

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAnalysisStore, usePortfolioStore } from "../lib/store";
import { play } from "../lib/sounds";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { useMarketIndices } from "../hooks/useMarketIndices";
import { api } from "../lib/api";
import type { ReviewedAction, WatchlistCandidate } from "../lib/types";



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

// ─── Compact expandable action row ────────────────────────────────────────────

function ActionRow({
  action,
  expanded,
  onToggle,
}: {
  action: ReviewedAction;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { original, decision, ai_reasoning, confidence } = action;
  const isBuy = original.action_type === "BUY";
  const { data: state } = usePortfolioState();

  const position = !isBuy ? (state?.positions.find(p => p.ticker === original.ticker) ?? null) : null;
  const pnlPct = position != null
    ? (original.price - position.avg_cost_basis) / position.avg_cost_basis * 100
    : null;

  const decisionColor = decision === "APPROVE" ? "var(--green)"
    : decision === "MODIFY" ? "var(--amber)"
    : "var(--text-dim)";

  const actionColor = isBuy ? "var(--green)" : "var(--red)";
  const actionBg = isBuy ? "var(--green-dim)" : "var(--red-dim)";

  const stop = action.modified_stop ?? original.stop_loss;
  const target = action.modified_target ?? original.take_profit;
  const shares = action.modified_shares ?? original.shares;
  const total = shares * original.price;

  return (
    <div
      style={{
        borderBottom: "1px solid var(--border)",
        background: expanded ? "rgba(255,255,255,0.02)" : "transparent",
        transition: "background 0.1s",
      }}
    >
      {/* Compact row — always visible */}
      <div
        role="button"
        tabIndex={0}
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggle(); } }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "0 12px",
          height: 36,
          cursor: "pointer",
          userSelect: "none",
        }}
        onMouseEnter={e => { if (!expanded) (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.025)"; }}
        onMouseLeave={e => { if (!expanded) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
      >
        {/* Action chip */}
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: "0.06em",
          padding: "1px 5px", borderRadius: 3,
          background: actionBg, color: actionColor, flexShrink: 0,
        }}>
          {original.action_type}
        </span>

        {/* Ticker */}
        <span style={{
          fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700,
          color: "var(--text-primary)", width: 38, flexShrink: 0, letterSpacing: "0.02em",
        }}>
          {original.ticker}
        </span>

        {/* Score for buys */}
        {isBuy && original.quant_score > 0 && (
          <span style={{
            fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 600,
            color: original.quant_score >= 75 ? "var(--green)" : original.quant_score >= 55 ? "var(--amber)" : "var(--text-secondary)",
            width: 24, flexShrink: 0,
          }}>
            {original.quant_score.toFixed(0)}
          </span>
        )}

        {/* P&L for sells */}
        {!isBuy && pnlPct != null && (
          <span style={{
            fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 600,
            color: pnlPct >= 0 ? "var(--green)" : "var(--red)", flexShrink: 0,
          }}>
            {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%
          </span>
        )}

        {/* Shares + price */}
        <span style={{
          fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)",
          flexShrink: 0,
        }}>
          {shares}sh·${original.price.toFixed(2)}
        </span>

        <div style={{ flex: 1 }} />

        {/* Confidence dots */}
        <span style={{ display: "flex", gap: 2, flexShrink: 0 }}>
          {[0, 1, 2].map(i => (
            <span key={i} style={{
              width: 4, height: 4, borderRadius: "50%", flexShrink: 0,
              background: i < Math.round(confidence * 3) ? decisionColor : "var(--border)",
            }} />
          ))}
        </span>

        {/* Decision label */}
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: "0.04em",
          color: decisionColor, flexShrink: 0, width: 44, textAlign: "right",
        }}>
          {decision}
        </span>

        {/* Chevron */}
        <span style={{
          fontSize: 10, color: "var(--text-dim)", flexShrink: 0,
          transform: expanded ? "rotate(180deg)" : "none",
          transition: "transform 0.15s",
          marginLeft: 2,
        }}>
          ▾
        </span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ padding: "0 12px 12px 12px" }}>

          {/* Stops / target for buys */}
          {isBuy && (
            <div style={{
              display: "flex", gap: 10, marginBottom: 8, paddingBottom: 8,
              borderBottom: "1px solid var(--border)",
            }}>
              <div>
                <div style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.08em", marginBottom: 2 }}>STOP</div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, color: "var(--red)" }}>
                  ${stop.toFixed(2)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.08em", marginBottom: 2 }}>TARGET</div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, color: "var(--green)" }}>
                  ${target.toFixed(2)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.08em", marginBottom: 2 }}>TOTAL</div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" }}>
                  ${total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
              </div>
            </div>
          )}

          {/* AI reasoning */}
          {ai_reasoning && (
            <p style={{
              fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.55,
              marginBottom: isBuy && Object.keys(original.factor_scores ?? {}).length > 0 ? 8 : 0,
            }}>
              {ai_reasoning}
            </p>
          )}

          {/* Factor chips — buys only */}
          {isBuy && original.factor_scores && Object.keys(original.factor_scores).length > 0 && (
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
              {Object.entries(original.factor_scores).map(([k, v]) => (
                <span key={k} style={{
                  fontSize: 9, padding: "1px 5px", borderRadius: 3,
                  background: "var(--bg-void)", color: "var(--text-dim)",
                  fontFamily: "var(--font-mono)",
                }}>
                  {k.slice(0, 3)} {typeof v === "number" ? v.toFixed(0) : v}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Section divider ─────────────────────────────────────────────────────────

function SectionDivider({ label, count, right }: { label: string; count: number; right?: React.ReactNode }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "6px 12px",
      background: "var(--bg-void)",
      borderBottom: "1px solid var(--border)",
      borderTop: "1px solid var(--border)",
    }}>
      <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.09em", color: "var(--text-muted)", textTransform: "uppercase" }}>
        {label}
      </span>
      <span style={{
        fontSize: 9, fontWeight: 600, fontFamily: "var(--font-mono)",
        padding: "0 5px", borderRadius: 3, background: "var(--border)", color: "var(--text-dim)",
      }}>
        {count}
      </span>
      {right && <div style={{ marginLeft: "auto" }}>{right}</div>}
    </div>
  );
}

export default function ActionsTab() {
  const { result, isAnalyzing, isExecuting, error, lastAnalyzedAt, runAnalysis, runExecute } =
    useAnalysisStore();
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [showVetoed, setShowVetoed] = useState(false);

  // Detect analyze complete → play sound, auto-expand first actionable
  const wasAnalyzing = useRef(false);
  useEffect(() => {
    if (wasAnalyzing.current && !isAnalyzing && result) {
      play("analyzeComplete");
      setExpandedKey(null);
      setShowVetoed(false);
    }
    wasAnalyzing.current = isAnalyzing;
  }, [isAnalyzing, result]);

  const handleAnalyze = () => { play("analyze"); runAnalysis(); };
  const handleExecute = () => { play("execute"); runExecute(); };

  const toggleRow = (key: string) => setExpandedKey(prev => prev === key ? null : key);

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
          style={{ borderColor: "var(--accent-dim)", borderTopColor: "var(--accent)" }}
        />
        <p style={{ fontSize: 13, color: "var(--text-primary)" }}>GScott's analyzing...</p>
        <p style={{ fontSize: 11, color: "var(--text-secondary)" }}>Scoring candidates, running AI review</p>
      </div>
    );
  }

  if (!result) return null;

  const { approved, modified, vetoed, summary } = result;

  // Deduplicate by ticker+action_type
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
        <p style={{ fontSize: 13, fontWeight: 500 }}>No opportunities</p>
        <p style={{ fontSize: 11, textAlign: "center", maxWidth: 240, color: "var(--text-muted)" }}>
          Nothing worth trading right now. Try running SCAN first.
        </p>
        <button
          onClick={handleAnalyze}
          style={{
            padding: "4px 12px", fontSize: 11, fontWeight: 500,
            borderRadius: "var(--radius)", background: "var(--bg-surface)",
            color: "var(--text-secondary)", border: "1px solid var(--border)", cursor: "pointer",
          }}
        >
          Re-analyze
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      {/* Summary bar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "0 12px", height: 38,
        borderBottom: "1px solid var(--border)",
        background: "var(--bg-surface)", flexShrink: 0,
      }}>
        {/* Counts */}
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--green)" }}>
          {summary.approved + summary.modified}✓
        </span>
        {summary.vetoed > 0 && (
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--red)" }}>
            {summary.vetoed}✗
          </span>
        )}
        {result.ai_mode && (
          <span style={{
            fontSize: 9, fontWeight: 700, letterSpacing: "0.06em",
            padding: "1px 5px", borderRadius: 3,
            background: result.ai_mode === "claude" ? "rgba(74,222,128,0.10)" : "var(--red-dim)",
            color: result.ai_mode === "claude" ? "var(--green)" : "var(--red)",
          }}>
            {result.ai_mode === "claude" ? "AI" : "FB"}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {summary.can_execute && (
          <button
            onClick={handleExecute}
            disabled={isExecuting}
            style={{
              padding: "3px 10px", fontSize: 11, fontWeight: 600,
              borderRadius: "var(--radius)", background: "var(--green-dim)",
              color: "var(--green)", border: "none",
              cursor: isExecuting ? "default" : "pointer",
              opacity: isExecuting ? 0.5 : 1,
            }}
          >
            {isExecuting ? "Executing…" : `Execute ${actionable.length}`}
          </button>
        )}
        <button
          onClick={handleAnalyze}
          style={{
            padding: "3px 8px", fontSize: 11, fontWeight: 500,
            borderRadius: "var(--radius)", background: "transparent",
            color: "var(--text-dim)", border: "1px solid var(--border)", cursor: "pointer",
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)"; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = "var(--text-dim)"; }}
        >
          ↺
        </button>
      </div>

      {error && (
        <div style={{ padding: "6px 12px", fontSize: 11, color: "var(--red)", background: "var(--red-dim)", borderBottom: "1px solid rgba(239,68,68,0.2)", flexShrink: 0 }}>
          {error}
        </div>
      )}

      {/* Action list */}
      <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>

        {/* Actionable rows */}
        {actionable.length > 0 && (
          <>
            <SectionDivider label="Ready to Execute" count={actionable.length} />
            {actionable.map((a) => {
              const key = `${a.original.action_type}:${a.original.ticker}`;
              return (
                <ActionRow
                  key={key}
                  action={a}
                  expanded={expandedKey === key}
                  onToggle={() => toggleRow(key)}
                />
              );
            })}
          </>
        )}

        {/* Vetoed rows — collapsed by default */}
        {vetoed.length > 0 && (
          <>
            <SectionDivider
              label="Vetoed"
              count={vetoed.length}
              right={
                <button
                  onClick={() => setShowVetoed(v => !v)}
                  style={{
                    fontSize: 9, fontWeight: 600, letterSpacing: "0.05em",
                    background: "transparent", border: "none",
                    color: "var(--text-dim)", cursor: "pointer",
                  }}
                >
                  {showVetoed ? "Hide" : "Show"}
                </button>
              }
            />
            {showVetoed && vetoed.map((a) => {
              const key = `VETO:${a.original.action_type}:${a.original.ticker}`;
              return (
                <ActionRow
                  key={key}
                  action={a}
                  expanded={expandedKey === key}
                  onToggle={() => toggleRow(key)}
                />
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
