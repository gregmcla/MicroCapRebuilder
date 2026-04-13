/** TRADES tab — aggregate stats + filterable closed-trade list + per-trade detail. */

import { useState, useMemo } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { ClosedTrade } from "../../lib/types";

const FONT = "var(--font-mono)";

type ExitReasonFilter = "ALL" | "STOP_LOSS" | "TAKE_PROFIT" | "INTELLIGENCE" | "MANUAL";
type DateRangeFilter = "30d" | "90d" | "all";
type SortKey = "exit_date" | "pnl_pct" | "holding_days" | "ticker";

// ── Exit reason badge ────────────────────────────────────────────────────────

function ExitBadge({ reason }: { reason: string }) {
  const cfg: Record<string, { color: string; label: string }> = {
    STOP_LOSS:    { color: "var(--red)", label: "STOP" },
    TAKE_PROFIT:  { color: "var(--green)", label: "TARGET" },
    INTELLIGENCE: { color: "var(--accent)", label: "AI" },
    MANUAL:       { color: "var(--text-secondary)", label: "MANUAL" },
  };
  const { color, label } = cfg[reason] ?? { color: "#9ca3af", label: reason };
  return (
    <span style={{
      color, fontSize: 9, fontWeight: 700, letterSpacing: "0.05em",
      background: `${color}22`, padding: "1px 6px", borderRadius: 4,
      fontFamily: FONT, whiteSpace: "nowrap",
    }}>
      {label}
    </span>
  );
}

// ── Factor bar ───────────────────────────────────────────────────────────────

function FactorBar({ label, score }: { label: string; score: number }) {
  const pct = Math.min(100, Math.max(0, score));
  const color = pct >= 70 ? "var(--green)" : pct >= 50 ? "var(--amber)" : "var(--red)";
  return (
    <div style={{ marginBottom: 7 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "capitalize", fontFamily: FONT }}>
          {label.replace(/_/g, " ")}
        </span>
        <span style={{ fontSize: 10, color, fontWeight: 600, fontFamily: FONT }}>{Math.round(score)}</span>
      </div>
      <div style={{ height: 3, background: "var(--bg-elevated)", borderRadius: 2 }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.3s" }} />
      </div>
    </div>
  );
}

// ── Aggregate panel ──────────────────────────────────────────────────────────

function AggregatePanel({ trades }: { trades: ClosedTrade[] }) {
  const stats = useMemo(() => {
    if (trades.length === 0) return null;
    const winners = trades.filter(t => (t.pnl_pct ?? 0) > 0);
    const winRate = (winners.length / trades.length) * 100;
    const avgPnl = trades.reduce((s, t) => s + (t.pnl_pct ?? 0), 0) / trades.length;
    const avgHold = trades.reduce((s, t) => s + t.holding_days, 0) / trades.length;

    const byReason: Record<string, { count: number; pnlSum: number }> = {};
    trades.forEach(t => {
      const r = t.exit_reason || "UNKNOWN";
      if (!byReason[r]) byReason[r] = { count: 0, pnlSum: 0 };
      byReason[r].count++;
      byReason[r].pnlSum += t.pnl_pct ?? 0;
    });
    const reasonStats = Object.entries(byReason)
      .map(([reason, d]) => ({ reason, count: d.count, avgPnl: d.pnlSum / d.count, pct: (d.count / trades.length) * 100 }))
      .sort((a, b) => b.count - a.count);

    const byRegime: Record<string, { wins: number; total: number }> = {};
    trades.forEach(t => {
      const r = t.regime_at_entry || "UNKNOWN";
      if (!byRegime[r]) byRegime[r] = { wins: 0, total: 0 };
      byRegime[r].total++;
      if ((t.pnl_pct ?? 0) > 0) byRegime[r].wins++;
    });
    const regimeStats = Object.entries(byRegime)
      .map(([regime, d]) => ({ regime, winRate: (d.wins / d.total) * 100, total: d.total }));

    return { winRate, avgPnl, avgHold, total: trades.length, reasonStats, regimeStats };
  }, [trades]);

  if (!stats) {
    return (
      <div style={{ padding: 20, color: "var(--text-dim)", fontSize: 12, textAlign: "center", fontFamily: FONT }}>
        No closed trades yet
      </div>
    );
  }

  const reasonColor = (r: string) =>
    r === "STOP_LOSS" ? "var(--red)" : r === "TAKE_PROFIT" ? "var(--green)" : r === "INTELLIGENCE" ? "var(--accent)" : "var(--text-secondary)";
  const regimeColor = (r: string) =>
    r === "BULL" ? "var(--green)" : r === "BEAR" ? "var(--red)" : "var(--amber)";

  return (
    <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border)", fontFamily: FONT }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 6, marginBottom: 12 }}>
        {[
          { label: "WIN RATE", value: `${stats.winRate.toFixed(0)}%`, color: stats.winRate >= 50 ? "var(--green)" : "var(--red)" },
          { label: "AVG P&L", value: `${stats.avgPnl >= 0 ? "+" : ""}${stats.avgPnl.toFixed(1)}%`, color: stats.avgPnl >= 0 ? "var(--green)" : "var(--red)" },
          { label: "AVG HOLD", value: `${stats.avgHold.toFixed(1)}d`, color: undefined as string | undefined },
          { label: "TOTAL", value: String(stats.total), color: undefined as string | undefined },
        ].map(chip => (
          <div key={chip.label} style={{
            background: "var(--bg-elevated)", borderRadius: 6, padding: "7px 8px",
            border: "1px solid var(--border)",
          }}>
            <div style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 3, letterSpacing: "0.08em" }}>{chip.label}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: chip.color ?? "var(--text-primary)" }}>{chip.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 6, letterSpacing: "0.08em" }}>BY EXIT</div>
          {stats.reasonStats.map(r => (
            <div key={r.reason} style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 5 }}>
              <div style={{ width: 50, height: 3, background: "var(--border)", borderRadius: 2 }}>
                <div style={{ width: `${r.pct}%`, height: "100%", background: reasonColor(r.reason), borderRadius: 2 }} />
              </div>
              <span style={{ fontSize: 9, color: "var(--text-muted)", flex: 1 }}>
                {r.reason.replace(/_/g, " ")} ({r.count})
              </span>
              <span style={{ fontSize: 9, fontWeight: 600, color: r.avgPnl >= 0 ? "var(--green)" : "var(--red)" }}>
                {r.avgPnl >= 0 ? "+" : ""}{r.avgPnl.toFixed(1)}%
              </span>
            </div>
          ))}
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 8, color: "var(--text-dim)", marginBottom: 6, letterSpacing: "0.08em" }}>BY REGIME</div>
          {stats.regimeStats.map(r => (
            <div key={r.regime} style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 5 }}>
              <div style={{ width: 50, height: 3, background: "var(--border)", borderRadius: 2 }}>
                <div style={{ width: `${r.winRate}%`, height: "100%", background: regimeColor(r.regime), borderRadius: 2 }} />
              </div>
              <span style={{ fontSize: 9, color: "var(--text-muted)", flex: 1 }}>{r.regime} ({r.total})</span>
              <span style={{ fontSize: 9, fontWeight: 600, color: regimeColor(r.regime) }}>
                {r.winRate.toFixed(0)}% W
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Trade list ───────────────────────────────────────────────────────────────

function TradeList({
  trades,
  selectedId,
  onSelect,
}: {
  trades: ClosedTrade[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("exit_date");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);
  const [filterReason, setFilterReason] = useState<ExitReasonFilter>("ALL");
  const [dateRange, setDateRange] = useState<DateRangeFilter>("all");

  const filtered = useMemo(() => {
    let list = [...trades];

    if (dateRange !== "all") {
      const days = dateRange === "30d" ? 30 : 90;
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - days);
      const cutoffStr = cutoff.toISOString().slice(0, 10);
      list = list.filter(t => t.exit_date >= cutoffStr);
    }

    if (filterReason !== "ALL") {
      list = list.filter(t => t.exit_reason === filterReason);
    }

    const getSortVal = (t: ClosedTrade): string | number => {
      switch (sortKey) {
        case "ticker":       return t.ticker;
        case "exit_date":    return t.exit_date;
        case "holding_days": return t.holding_days;
        case "pnl_pct":      return t.pnl_pct ?? (sortDir === 1 ? -Infinity : Infinity);
      }
    };
    list.sort((a, b) => {
      const av = getSortVal(a);
      const bv = getSortVal(b);
      if (av < bv) return -sortDir;
      if (av > bv) return sortDir;
      // Tiebreaker: trade_id for deterministic ordering
      return a.trade_id < b.trade_id ? -1 : a.trade_id > b.trade_id ? 1 : 0;
    });

    return list;
  }, [trades, sortKey, sortDir, filterReason, dateRange]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => (d === 1 ? -1 : 1));
    else { setSortKey(key); setSortDir(-1); }
  };

  const hdr = (key: SortKey, label: string) => (
    <button
      type="button"
      onClick={() => toggleSort(key)}
      style={{
        cursor: "pointer", fontSize: 9, letterSpacing: "0.08em", textTransform: "uppercase",
        fontFamily: FONT, userSelect: "none",
        color: sortKey === key ? "var(--text-primary)" : "var(--text-dim)",
        background: "transparent", border: "none", padding: 0, textAlign: "left",
      }}
      aria-label={`Sort by ${label}`}
      aria-pressed={sortKey === key}
    >
      {label}{sortKey === key ? (sortDir === 1 ? " ↑" : " ↓") : ""}
    </button>
  );

  const reasons: ExitReasonFilter[] = ["ALL", "STOP_LOSS", "TAKE_PROFIT", "INTELLIGENCE", "MANUAL"];
  const btnStyle = (active: boolean): React.CSSProperties => ({
    fontSize: 9, padding: "2px 7px", borderRadius: 4, cursor: "pointer",
    border: "1px solid rgba(255,255,255,0.08)", fontFamily: FONT,
    background: active ? "var(--accent-dim)" : "transparent",
    color: active ? "var(--accent)" : "var(--text-dim)",
    fontWeight: active ? 600 : 400,
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0, fontFamily: FONT }}>
      <div style={{ padding: "7px 14px", borderBottom: "1px solid var(--border)", display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
        {reasons.map(r => (
          <button key={r} onClick={() => setFilterReason(r)} style={btnStyle(filterReason === r)}>
            {r === "ALL" ? "All" : r.replace(/_/g, " ")}
          </button>
        ))}
        <span style={{ flex: 1 }} />
        {(["30d", "90d", "all"] as DateRangeFilter[]).map(d => (
          <button key={d} onClick={() => setDateRange(d)} style={btnStyle(dateRange === d)}>
            {d === "all" ? "All time" : `Last ${d}`}
          </button>
        ))}
      </div>

      <div style={{
        padding: "5px 14px", display: "grid",
        gridTemplateColumns: "52px 80px 36px 56px 68px",
        gap: 6, borderBottom: "1px solid var(--border)",
      }}>
        {hdr("ticker", "Ticker")}
        {hdr("exit_date", "Close")}
        {hdr("holding_days", "Hold")}
        {hdr("pnl_pct", "P&L%")}
        <span style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em", textTransform: "uppercase", fontFamily: FONT }}>Exit</span>
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {filtered.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", color: "var(--text-dim)", fontSize: 11 }}>
            No trades match filters
          </div>
        )}
        {filtered.map(trade => {
          const pnl = trade.pnl_pct ?? 0;
          const isSelected = trade.trade_id === selectedId;
          return (
            <div
              key={trade.trade_id}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              onClick={() => onSelect(trade.trade_id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(trade.trade_id);
                }
              }}
              style={{
                padding: "6px 14px", display: "grid",
                gridTemplateColumns: "52px 80px 36px 56px 68px",
                gap: 6, alignItems: "center", cursor: "pointer",
                borderBottom: "1px solid rgba(255,255,255,0.025)",
                background: isSelected ? "var(--accent-dim)" : "transparent",
                transition: "background 0.12s",
              }}
              onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = "var(--bg-elevated)"; }}
              onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
            >
              <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-primary)", fontFamily: FONT }}>{trade.ticker}</span>
              <span style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: FONT }}>{trade.exit_date}</span>
              <span style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: FONT }}>{trade.holding_days}d</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: pnl >= 0 ? "var(--green)" : "var(--red)", fontFamily: FONT }}>
                {pnl >= 0 ? "+" : ""}{pnl.toFixed(1)}%
              </span>
              <ExitBadge reason={trade.exit_reason} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Trade detail ─────────────────────────────────────────────────────────────

function TradeDetail({ trade, portfolioId }: { trade: ClosedTrade; portfolioId: string }) {
  const [reanalyzed, setReanalyzed] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [prevTradeId, setPrevTradeId] = useState(trade.trade_id);

  // Reset ephemeral state when selected trade changes
  if (trade.trade_id !== prevTradeId) {
    setPrevTradeId(trade.trade_id);
    setReanalyzed(null);
    setAnalyzeError(null);
  }

  const analyzeMutation = useMutation({
    mutationFn: () => api.analyzeTradeReview(portfolioId, trade.trade_id),
    onSuccess: (data) => { setReanalyzed(data.narrative); setAnalyzeError(null); },
    onError: () => setAnalyzeError("Analysis failed — try again"),
  });

  const pnl = trade.pnl_pct ?? 0;
  const pnlColor = pnl >= 0 ? "var(--green)" : "var(--red)";
  const factors = Object.entries(trade.factor_scores || {}).filter(
    (e): e is [string, number] => e[1] != null
  );

  const chip = (label: string, value: string) => (
    <span key={label} style={{ fontSize: 10, color: "var(--text-secondary)", fontFamily: FONT }}>
      <span style={{ color: "var(--text-dim)" }}>{label} </span>{value}
    </span>
  );

  const section = (title: string, extra?: React.ReactNode) => (
    <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--text-dim)", marginBottom: 8, fontFamily: FONT, fontWeight: 600, display: "flex", gap: 8, alignItems: "center" }}>
      {title}{extra}
    </div>
  );

  const divider = <div style={{ height: 1, background: "var(--border)", margin: "2px 0" }} />;

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "14px 16px", display: "flex", flexDirection: "column", gap: 14, fontFamily: FONT }}>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
          <span style={{ fontSize: 17, fontWeight: 800, color: "var(--text-primary)", letterSpacing: "0.04em" }}>{trade.ticker}</span>
          <ExitBadge reason={trade.exit_reason} />
          {trade.regime_at_entry && (
            <span style={{ fontSize: 9, color: "var(--text-dim)", background: "var(--bg-elevated)", padding: "1px 6px", borderRadius: 4 }}>
              {trade.regime_at_entry}
            </span>
          )}
        </div>
        <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 8 }}>
          {trade.entry_date} → {trade.exit_date} · {trade.holding_days}d
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: pnlColor }}>
          {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%
          <span style={{ fontSize: 13, fontWeight: 400, marginLeft: 8, color: pnlColor }}>
            ({pnl >= 0 ? "+" : ""}${(trade.pnl ?? 0).toFixed(0)})
          </span>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 8, flexWrap: "wrap" }}>
          {chip("Entry", `$${trade.entry_price?.toFixed(2) ?? "—"}`)}
          {chip("Exit", `$${trade.exit_price?.toFixed(2) ?? "—"}`)}
          {chip("Shares", String(Math.round(trade.shares ?? 0)))}
          {chip("Stop", `$${trade.stop_loss?.toFixed(2) ?? "—"}`)}
          {chip("Target", `$${trade.take_profit?.toFixed(2) ?? "—"}`)}
        </div>
      </div>

      {divider}

      <div>
        {section("Entry Thesis", reanalyzed ? <span style={{ color: "var(--accent)", fontSize: 8 }}>· Re-analyzed</span> : null)}
        <p style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.75, margin: 0 }}>
          {reanalyzed ?? (trade.entry_ai_reasoning || "No AI reasoning recorded for this trade.")}
        </p>
      </div>

      {factors.length > 0 && (
        <div>
          {section("Factors at Entry")}
          {factors.map(([k, v]) => <FactorBar key={k} label={k} score={v} />)}
        </div>
      )}

      {divider}

      {!reanalyzed && (
        <div>
          {section("Exit Analysis")}
          <p style={{ fontSize: 11, color: trade.exit_ai_reasoning ? "var(--text-secondary)" : "var(--text-dim)", lineHeight: 1.75, margin: "0 0 10px" }}>
            {trade.exit_ai_reasoning || "No AI reasoning recorded."}
          </p>

          {(trade.what_worked || trade.what_failed) && (
            <div style={{ display: "flex", gap: 8 }}>
              {trade.what_worked && (
                <div style={{ flex: 1, background: "var(--green-dim)", border: "1px solid rgba(34,197,94,0.12)", borderRadius: 7, padding: "9px 11px" }}>
                  <div style={{ fontSize: 8, color: "var(--green)", fontWeight: 700, marginBottom: 4, letterSpacing: "0.08em" }}>WORKED</div>
                  <div style={{ fontSize: 10, color: "var(--text-secondary)", lineHeight: 1.65 }}>{trade.what_worked}</div>
                </div>
              )}
              {trade.what_failed && (
                <div style={{ flex: 1, background: "var(--red-dim)", border: "1px solid rgba(239,68,68,0.12)", borderRadius: 7, padding: "9px 11px" }}>
                  <div style={{ fontSize: 8, color: "var(--red)", fontWeight: 700, marginBottom: 4, letterSpacing: "0.08em" }}>FAILED</div>
                  <div style={{ fontSize: 10, color: "var(--text-secondary)", lineHeight: 1.65 }}>{trade.what_failed}</div>
                </div>
              )}
            </div>
          )}

          {trade.recommendation && (
            <div style={{ marginTop: 10, padding: "9px 11px", background: "var(--accent-dim)", border: "1px solid rgba(139,92,246,0.18)", borderRadius: 7 }}>
              <div style={{ fontSize: 8, color: "var(--accent)", fontWeight: 700, marginBottom: 4, letterSpacing: "0.08em" }}>RECOMMENDATION</div>
              <div style={{ fontSize: 10, color: "var(--text-secondary)", lineHeight: 1.65 }}>{trade.recommendation}</div>
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: "auto", paddingTop: 6 }}>
        {analyzeError && (
          <div style={{ fontSize: 10, color: "var(--red)", marginBottom: 6 }}>{analyzeError}</div>
        )}
        <button
          onClick={() => analyzeMutation.mutate()}
          disabled={analyzeMutation.isPending}
          style={{
            width: "100%", padding: "9px 0", borderRadius: 8,
            border: "1px solid rgba(139,92,246,0.3)",
            background: analyzeMutation.isPending ? "rgba(139,92,246,0.04)" : "var(--accent-dim)",
            color: "var(--accent)", fontSize: 11, fontWeight: 600, cursor: analyzeMutation.isPending ? "default" : "pointer",
            fontFamily: FONT, letterSpacing: "0.03em", transition: "all 0.15s",
          }}
        >
          {analyzeMutation.isPending ? "Analyzing…" : reanalyzed ? "Re-analyze Again" : "Re-analyze with Claude"}
        </button>
      </div>
    </div>
  );
}

// ── Main export ──────────────────────────────────────────────────────────────

export default function TradesTab({
  portfolioId,
  initialTradeId,
}: {
  portfolioId: string;
  initialTradeId?: string | null;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(initialTradeId ?? null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["trade-reviews", portfolioId],
    queryFn: () => api.getTradeReviews(portfolioId),
    staleTime: 2 * 60_000,
  });

  const trades = data?.trades ?? [];
  const selectedTrade = trades.find(t => t.trade_id === selectedId) ?? null;

  if (isLoading) {
    return (
      <div style={{ padding: 28, color: "var(--text-dim)", fontSize: 12, fontFamily: FONT }}>
        Loading trade history…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 28, color: "var(--red)", fontSize: 12, fontFamily: FONT }}>
        Failed to load trade reviews.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 0 }}>
      <div style={{
        width: "40%", borderRight: "1px solid var(--border)",
        display: "flex", flexDirection: "column", minHeight: 0,
      }}>
        <AggregatePanel trades={trades} />
        <TradeList trades={trades} selectedId={selectedId} onSelect={setSelectedId} />
      </div>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
        {selectedTrade ? (
          <TradeDetail trade={selectedTrade} portfolioId={portfolioId} />
        ) : (
          <div style={{
            flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
            color: "var(--text-dim)", fontSize: 12, fontFamily: FONT,
          }}>
            Select a trade to review
          </div>
        )}
      </div>
    </div>
  );
}
