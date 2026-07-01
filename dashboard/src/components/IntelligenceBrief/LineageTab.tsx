/** Position Lineage — every event that touched a ticker, oldest to newest.
 *
 * Pick a ticker → vertical timeline of: watchlist add/remove, AI considered,
 * buys/sells, stop adjustments, post-mortems, and material score moves.
 * Events with a trace_id deep-link into DecisionsTab via openBrief("decisions", ...).
 */

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { useBriefStore } from "../../lib/store";
import { usePortfolioState } from "../../hooks/usePortfolioState";
import type { BaseLineageEvent, LineageEventKind } from "../../lib/types";
import { PanelLoading, PanelError } from "./PanelState";
import { errMessage } from "../../lib/toast";

const FONT = "'JetBrains Mono', 'SF Mono', monospace";

interface Props {
  portfolioId: string;
  initialTicker?: string | null;
}

export default function LineageTab({ portfolioId, initialTicker = null }: Props) {
  const { data: state } = usePortfolioState();
  const heldTickers = useMemo(
    () => (state?.positions ?? []).map((p) => p.ticker),
    [state?.positions],
  );

  const [selectedTicker, setSelectedTicker] = useState<string | null>(
    initialTicker ?? (heldTickers[0] ?? null),
  );

  // If initialTicker arrives later (e.g., props update on deep-link), honor it.
  useEffect(() => {
    if (initialTicker && initialTicker !== selectedTicker) {
      setSelectedTicker(initialTicker);
    }
  }, [initialTicker, selectedTicker]);

  // If no selection yet and held tickers loaded, pick the first.
  useEffect(() => {
    if (!selectedTicker && heldTickers.length > 0) {
      setSelectedTicker(heldTickers[0]);
    }
  }, [selectedTicker, heldTickers]);

  return (
    <div style={{ display: "flex", flex: 1, overflow: "hidden", fontFamily: FONT }}>
      {/* LEFT: ticker picker (held positions for the active portfolio) */}
      <div
        style={{
          width: "180px",
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
          Positions
        </div>
        {heldTickers.length === 0 && (
          <div style={{ padding: "12px", color: "#5a5a78", fontSize: "11px" }}>
            No open positions. Pass a ticker via deep-link to view a closed-position lineage.
          </div>
        )}
        {heldTickers.map((t) => {
          const active = t === selectedTicker;
          return (
            <button
              key={t}
              onClick={() => setSelectedTicker(t)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "8px 12px",
                background: active ? "rgba(124,92,252,0.10)" : "transparent",
                borderLeft: active ? "2px solid #7c5cfc" : "2px solid transparent",
                border: "none",
                color: active ? "#e0e0f0" : "#9090b0",
                cursor: "pointer",
                fontFamily: FONT,
                fontWeight: 600,
                fontSize: "12px",
              }}
            >
              {t}
            </button>
          );
        })}
        {selectedTicker && !heldTickers.includes(selectedTicker) && (
          // Closed position deep-linked from elsewhere
          <div
            style={{
              padding: "8px 12px",
              background: "rgba(124,92,252,0.10)",
              borderLeft: "2px solid #7c5cfc",
              color: "#e0e0f0",
              fontWeight: 600,
              fontSize: "12px",
              marginTop: "8px",
            }}
          >
            {selectedTicker} <span style={{ color: "#5a5a78", fontSize: "9px" }}>(closed)</span>
          </div>
        )}
      </div>

      {/* RIGHT: timeline */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
        {selectedTicker ? (
          <Timeline portfolioId={portfolioId} ticker={selectedTicker} />
        ) : (
          <div style={{ color: "#6a6a88", padding: "20px", fontSize: "11px" }}>
            Pick a ticker on the left or deep-link in via openBrief("lineage", null, {`{ ticker }`}).
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Timeline ────────────────────────────────────────────────────────────────

function Timeline({ portfolioId, ticker }: { portfolioId: string; ticker: string }) {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["lineage", portfolioId, ticker],
    queryFn: () => api.getLineage(portfolioId, ticker, { limit: 200 }),
  });
  const { data: summary } = useQuery({
    queryKey: ["lineage-summary", portfolioId, ticker],
    queryFn: () => api.getLineageSummary(portfolioId, ticker),
  });

  // All hooks MUST be called unconditionally — declaring useMemo after an
  // early return causes "Rendered more hooks than during the previous render"
  // when the loading state flips (same bug pattern noted in CLAUDE.md gotchas).
  const groups = useMemo(
    () => (data ? groupByDate(data.events) : []),
    [data],
  );

  if (isError) {
    return <PanelError label={`Couldn’t load lineage for ${ticker}`} detail={errMessage(error)} onRetry={() => refetch()} />;
  }
  if (isLoading || !data) {
    return <PanelLoading label="Loading lineage…" />;
  }

  if (data.events.length === 0) {
    return (
      <div style={{ color: "#6a6a88", padding: "20px", fontSize: "11px" }}>
        No lineage events recorded for {ticker} yet. Events accumulate going forward —
        watchlist add/remove, AI considered, buys, sells, stop adjustments, post-mortems,
        and material score moves.
      </div>
    );
  }

  return (
    <div>
      <header
        style={{
          marginBottom: "16px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          paddingBottom: "10px",
        }}
      >
        <div style={{ color: "#e0e0f0", fontSize: "16px", fontWeight: 700 }}>
          {ticker}
        </div>
        {summary && (
          <div style={{ color: "#9090b0", fontSize: "10px", marginTop: "4px" }}>
            {summary.first_seen && (
              <span>First seen {fmtDate(summary.first_seen)} · </span>
            )}
            {summary.first_bought && (
              <span>First bought {fmtDate(summary.first_bought)} · </span>
            )}
            <span>{summary.total_trades} closed trade(s)</span>
            {summary.total_pnl !== 0 && (
              <span style={{ color: summary.total_pnl >= 0 ? "#34d399" : "#f87171", marginLeft: "6px" }}>
                · realized {summary.total_pnl >= 0 ? "+" : ""}${summary.total_pnl.toLocaleString()}
              </span>
            )}
            <span style={{ marginLeft: "6px" }}>· status: {summary.current_status}</span>
          </div>
        )}
      </header>

      {groups.map(([dateLabel, events]) => (
        <div key={dateLabel} style={{ marginBottom: "20px" }}>
          <div
            style={{
              fontSize: "10px",
              letterSpacing: "0.08em",
              color: "#5a5a78",
              textTransform: "uppercase",
              marginBottom: "8px",
              position: "sticky",
              top: 0,
              background: "rgba(8,8,16,0.92)",
              padding: "4px 0",
              backdropFilter: "blur(8px)",
            }}
          >
            {dateLabel}
          </div>
          {events.map((ev, i) => (
            <EventRow key={i} ev={ev} portfolioId={portfolioId} />
          ))}
        </div>
      ))}
    </div>
  );
}

// ─── Event row ───────────────────────────────────────────────────────────────

function EventRow({ ev, portfolioId }: { ev: BaseLineageEvent; portfolioId: string }) {
  const [open, setOpen] = useState(false);
  const openBrief = useBriefStore((s) => s.openBrief);
  void portfolioId;
  const accent = kindColor(ev.kind);
  const label = kindLabel(ev.kind);
  const traceId = (ev.trace_id as string | undefined) ?? null;
  const proposalId = (ev.proposal_id as string | undefined) ?? null;

  return (
    <div
      style={{
        marginBottom: "6px",
        background: "rgba(255,255,255,0.02)",
        borderLeft: `2px solid ${accent}`,
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
          cursor: "pointer",
          fontFamily: FONT,
          display: "flex",
          alignItems: "center",
          gap: "12px",
        }}
      >
        <span style={{ fontSize: "9px", color: "#5a5a78", letterSpacing: "0.06em", width: "60px" }}>
          {fmtTime(ev.timestamp)}
        </span>
        <span style={{ fontSize: "11px", fontWeight: 700, color: accent, width: "120px" }}>
          {label}
        </span>
        <span style={{ fontSize: "11px", color: "#e0e0f0", flex: 1 }}>
          {oneLineSummary(ev)}
        </span>
        {(traceId || proposalId) && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              openBrief("decisions", null, { traceId, proposalId });
            }}
            title="Open the decision trace for this event"
            style={{
              fontSize: "9px",
              letterSpacing: "0.06em",
              padding: "2px 6px",
              background: "rgba(124,92,252,0.08)",
              border: "1px solid rgba(124,92,252,0.25)",
              color: "#a78bfa",
              borderRadius: 3,
              cursor: "pointer",
              fontFamily: FONT,
            }}
          >
            → TRACE
          </button>
        )}
        <span style={{ fontSize: "9px", color: "#5a5a78" }}>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div style={{ padding: "0 12px 12px 80px" }}>
          <EventDetail ev={ev} />
        </div>
      )}
    </div>
  );
}

function EventDetail({ ev }: { ev: BaseLineageEvent }) {
  switch (ev.kind) {
    case "buy":
      return (
        <div style={{ fontSize: "10px", color: "#9090b0" }}>
          <div>{ev.shares as number} shares @ ${(ev.price as number).toFixed(2)}</div>
          <div>Stop ${(ev.stop_loss as number).toFixed(2)} · Target ${(ev.take_profit as number).toFixed(2)}</div>
          {ev.ai_reasoning_excerpt ? (
            <div style={{ marginTop: "6px", fontStyle: "italic", color: "#c0c0d8" }}>
              "{String(ev.ai_reasoning_excerpt)}"
            </div>
          ) : null}
        </div>
      );
    case "sell":
      return (
        <div style={{ fontSize: "10px", color: "#9090b0" }}>
          <div>{ev.shares as number} shares @ ${(ev.price as number).toFixed(2)} · {String(ev.reason)}</div>
          {ev.realized_pnl != null && (
            <div style={{
              color: (ev.realized_pnl as number) >= 0 ? "#34d399" : "#f87171",
              fontWeight: 600,
            }}>
              Realized {(ev.realized_pnl as number) >= 0 ? "+" : ""}${(ev.realized_pnl as number).toLocaleString()}
              {ev.realized_pnl_pct != null && ` (${(ev.realized_pnl_pct as number).toFixed(2)}%)`}
              {ev.holding_days != null && ` after ${ev.holding_days as number}d`}
            </div>
          )}
          {ev.ai_reasoning_excerpt ? (
            <div style={{ marginTop: "6px", fontStyle: "italic", color: "#c0c0d8" }}>
              "{String(ev.ai_reasoning_excerpt)}"
            </div>
          ) : null}
        </div>
      );
    case "stop_adjusted":
      return (
        <div style={{ fontSize: "10px", color: "#9090b0" }}>
          <code>{String(ev.field_name)}</code>: ${(ev.old_value as number).toFixed(2)} → ${(ev.new_value as number).toFixed(2)}
          <span style={{ marginLeft: "8px", color: "#5a5a78" }}>source: {String(ev.source)}</span>
        </div>
      );
    case "watchlist_added":
      return (
        <div style={{ fontSize: "10px", color: "#9090b0" }}>
          {ev.reason ? `Reason: ${String(ev.reason)}` : ""}
          {ev.source ? ` · Source: ${String(ev.source)}` : ""}
        </div>
      );
    case "watchlist_removed":
      return (
        <div style={{ fontSize: "10px", color: "#9090b0" }}>
          {ev.reason ? `Reason: ${String(ev.reason)}` : "Removed"}
        </div>
      );
    case "scored":
      return (
        <div style={{ fontSize: "10px", color: "#9090b0" }}>
          Composite <strong style={{ color: "#e0e0f0" }}>{(ev.composite as number).toFixed(1)}</strong>
          {ev.score_delta != null && (
            <span style={{
              marginLeft: "6px",
              color: (ev.score_delta as number) >= 0 ? "#34d399" : "#f87171",
            }}>
              ({(ev.score_delta as number) >= 0 ? "+" : ""}{(ev.score_delta as number).toFixed(1)})
            </span>
          )}
          <div style={{ marginTop: "4px", fontSize: "9px", color: "#5a5a78" }}>
            {Object.entries((ev.factor_scores as Record<string, number>) ?? {})
              .filter(([_k, v]) => v != null)
              .map(([k, v]) => `${k.slice(0, 4)} ${Number(v).toFixed(0)}`)
              .join(" · ")}
          </div>
        </div>
      );
    case "ai_considered":
      return (
        <div style={{ fontSize: "10px", color: "#9090b0" }}>
          {ev.action_type ? (
            <>
              Action: <strong style={{ color: "#e0e0f0" }}>{String(ev.action_type)}</strong>
              {ev.accepted != null && (
                <span style={{ marginLeft: "6px", color: ev.accepted ? "#34d399" : "#f87171" }}>
                  ({ev.accepted ? "accepted" : "rejected"})
                </span>
              )}
            </>
          ) : (
            <>Considered but no action proposed</>
          )}
          {!!ev.trace_id && (
            <div style={{ marginTop: "4px", color: "#5a5a78", fontSize: "9px" }}>
              trace {String(ev.trace_id)}
            </div>
          )}
        </div>
      );
    case "post_mortem":
      return (
        <div style={{ fontSize: "10px", color: "#9090b0" }}>
          {ev.summary ? (
            <div style={{ fontStyle: "italic", color: "#c0c0d8" }}>"{String(ev.summary)}"</div>
          ) : null}
          {Array.isArray(ev.what_worked) && (ev.what_worked as string[]).length > 0 && (
            <div style={{ marginTop: "6px" }}>
              <strong style={{ color: "#34d399" }}>Worked:</strong> {(ev.what_worked as string[]).join(" · ")}
            </div>
          )}
          {Array.isArray(ev.what_failed) && (ev.what_failed as string[]).length > 0 && (
            <div>
              <strong style={{ color: "#f87171" }}>Failed:</strong> {(ev.what_failed as string[]).join(" · ")}
            </div>
          )}
          {ev.recommendation ? (
            <div style={{ marginTop: "4px" }}>
              <strong style={{ color: "#a78bfa" }}>Rec:</strong> {String(ev.recommendation)}
            </div>
          ) : null}
        </div>
      );
    default:
      return <pre style={{ fontSize: "10px", color: "#9090b0", whiteSpace: "pre-wrap" }}>{JSON.stringify(ev, null, 2)}</pre>;
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function oneLineSummary(ev: BaseLineageEvent): string {
  switch (ev.kind) {
    case "buy":
      return `BUY ${ev.shares} sh @ $${Number(ev.price).toFixed(2)}`;
    case "sell":
      return `SELL ${ev.shares} sh @ $${Number(ev.price).toFixed(2)} (${String(ev.reason)})`;
    case "stop_adjusted":
      return `${String(ev.field_name)} → $${Number(ev.new_value).toFixed(2)} (${String(ev.source)})`;
    case "watchlist_added":
      return `Entered watchlist${ev.reason ? `: ${String(ev.reason)}` : ""}`;
    case "watchlist_removed":
      return `Left watchlist${ev.reason ? `: ${String(ev.reason)}` : ""}`;
    case "scored":
      return `Composite ${Number(ev.composite).toFixed(1)}${
        ev.score_delta != null && Number(ev.score_delta) !== 0
          ? ` (${Number(ev.score_delta) >= 0 ? "+" : ""}${Number(ev.score_delta).toFixed(1)})`
          : ""
      }`;
    case "ai_considered":
      return ev.action_type
        ? `AI ${String(ev.action_type)}${ev.accepted ? " accepted" : ev.accepted === false ? " rejected" : ""}`
        : "AI considered (no action)";
    case "post_mortem":
      return ev.summary ? String(ev.summary).slice(0, 80) : "Post-mortem recorded";
    default:
      return ev.kind;
  }
}

function kindColor(kind: LineageEventKind | string): string {
  const c: Record<string, string> = {
    watchlist_added: "#60a5fa",
    watchlist_removed: "#94a3b8",
    scored: "#a78bfa",
    ai_considered: "#fbbf24",
    buy: "#34d399",
    sell: "#f87171",
    stop_adjusted: "#fb923c",
    post_mortem: "#7c5cfc",
  };
  return c[kind] ?? "#5a5a78";
}

function kindLabel(kind: LineageEventKind | string): string {
  const l: Record<string, string> = {
    watchlist_added: "WATCHLIST +",
    watchlist_removed: "WATCHLIST −",
    scored: "SCORED",
    ai_considered: "AI CONSIDERED",
    buy: "BUY",
    sell: "SELL",
    stop_adjusted: "STOP ADJ",
    post_mortem: "POST-MORTEM",
  };
  return l[kind] ?? kind.toUpperCase();
}

function groupByDate(events: BaseLineageEvent[]): [string, BaseLineageEvent[]][] {
  const byDate = new Map<string, BaseLineageEvent[]>();
  for (const ev of events) {
    const key = (ev.timestamp || "").slice(0, 10) || "Unknown";
    if (!byDate.has(key)) byDate.set(key, []);
    byDate.get(key)!.push(ev);
  }
  return Array.from(byDate.entries()).map(([k, v]) => [fmtDate(k), v]);
}

function fmtDate(s: string): string {
  if (!s) return "—";
  const d = new Date(s.length > 10 ? s : `${s}T00:00:00`);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function fmtTime(s: string): string {
  if (!s) return "";
  if (s.length <= 10) return ""; // date-only — no time component
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}
