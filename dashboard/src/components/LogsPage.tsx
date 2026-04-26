/**
 * LogsPage — system health + pipeline status + Claude daily briefing.
 * Activated when activePortfolioId === "logs".
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSystemLogs, useSystemNarrative, useRegenerateNarrative } from "../hooks/useSystemLogs";
import { api } from "../lib/api";
import type { DayLog, PipelineJob, LogEvent, ModelComparisonResponse, ModelCohortStats, PerPortfolioModelStats } from "../lib/types";

// ── Badge colours ─────────────────────────────────────────────────────────────

const EVENT_BADGE: Record<LogEvent["type"], string> = {
  scan:        "bg-blue-900/60 text-blue-300 border border-blue-700/40",
  execute:     "bg-green-900/60 text-green-300 border border-green-700/40",
  update:      "bg-teal-900/60 text-teal-300 border border-teal-700/40",
  api_restart: "bg-amber-900/60 text-amber-300 border border-amber-700/40",
  failed:      "bg-red-900/60 text-red-400 border border-red-700/40",
};

const EVENT_LABEL: Record<LogEvent["type"], string> = {
  scan:        "SCAN",
  execute:     "EXECUTE",
  update:      "UPDATE",
  api_restart: "RESTART",
  failed:      "FAILED",
};

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusCell({ job }: { job: PipelineJob }) {
  if (job.status === "missing") {
    return <span className="text-zinc-600 font-mono text-xs">—</span>;
  }
  const total = job.ok + job.failed;
  if (job.status === "failed" && total === 0) {
    return <span className="text-red-400 font-mono text-xs">✗</span>;
  }
  const hasFailures = job.failed > 0;
  const color = hasFailures ? "text-amber-400" : "text-green-400";
  const icon = hasFailures ? "⚠" : "✓";
  return (
    <span className={`${color} font-mono text-xs`}>
      {icon} {job.ok}/{total}
    </span>
  );
}

function WatchdogCell({ restarts }: { restarts: number }) {
  if (restarts === 0) {
    return <span className="text-zinc-600 font-mono text-xs">0</span>;
  }
  return (
    <span className="text-amber-400 font-mono text-xs">
      ⚡ {restarts}
    </span>
  );
}

function NarrativeSection() {
  const { data, isLoading } = useSystemNarrative();
  const regenerateMutation = useRegenerateNarrative();

  return (
    <section className="mb-8 border border-zinc-800 rounded-lg p-5 bg-zinc-900/40">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-mono tracking-widest text-zinc-500 uppercase">
          Today's Briefing
        </h2>
        <button
          onClick={() => regenerateMutation.mutate()}
          disabled={regenerateMutation.isPending}
          className="text-xs text-zinc-600 hover:text-zinc-300 transition-colors font-mono disabled:opacity-40"
        >
          {regenerateMutation.isPending ? "Generating…" : "Regenerate ↺"}
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {[100, 90, 95, 80].map((w, i) => (
            <div key={i} className="h-3 bg-zinc-800 rounded" style={{ width: `${w}%` }} />
          ))}
        </div>
      ) : data?.narrative ? (
        <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap font-mono">
          {data.narrative}
        </p>
      ) : (
        <p className="text-sm text-zinc-600 italic">
          {data?.error
            ? "Narrative unavailable — Claude call failed."
            : "No briefing yet. Check back after the first cron run."}
        </p>
      )}
    </section>
  );
}

function PipelineGrid({ days }: { days: DayLog[] }) {
  const today = new Date().toISOString().slice(0, 10);
  const visible = days.slice(0, 14);

  return (
    <section className="mb-8">
      <h2 className="text-xs font-mono tracking-widest text-zinc-500 uppercase mb-3">
        Pipeline Status
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono border-collapse">
          <thead>
            <tr className="text-zinc-600 border-b border-zinc-800">
              <th className="text-left py-2 pr-6 font-normal">DATE</th>
              <th className="text-center py-2 px-3 font-normal">SCAN 6:30</th>
              <th className="text-center py-2 px-3 font-normal">EXECUTE 9:35</th>
              <th className="text-center py-2 px-3 font-normal">UPDATE 12:00</th>
              <th className="text-center py-2 px-3 font-normal">UPDATE 4:15</th>
              <th className="text-center py-2 px-3 font-normal">WATCHDOG</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((day) => {
              const isToday = day.date === today;
              return (
                <tr
                  key={day.date}
                  className={`border-b border-zinc-800/50 ${isToday ? "bg-zinc-800/30" : ""}`}
                >
                  <td className={`py-2 pr-6 ${isToday ? "text-zinc-300" : "text-zinc-500"}`}>
                    {day.date}
                  </td>
                  <td className="py-2 px-3 text-center">
                    <StatusCell job={day.pipeline.scan} />
                  </td>
                  <td className="py-2 px-3 text-center">
                    <StatusCell job={day.pipeline.execute} />
                  </td>
                  <td className="py-2 px-3 text-center">
                    <StatusCell job={day.pipeline.update_midday} />
                  </td>
                  <td className="py-2 px-3 text-center">
                    <StatusCell job={day.pipeline.update_close} />
                  </td>
                  <td className="py-2 px-3 text-center">
                    <WatchdogCell restarts={day.watchdog_restarts} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TimelineDay({ day, defaultOpen }: { day: DayLog; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const label = new Date(day.date + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric",
  });

  return (
    <div className="border-b border-zinc-800/50">
      <button
        className="w-full flex items-center gap-2 py-2 text-xs font-mono text-zinc-500 hover:text-zinc-300 transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        <span>{open ? "▼" : "▶"}</span>
        <span>{label}</span>
        {day.events.length > 0 && (
          <span className="text-zinc-700">({day.events.length} events)</span>
        )}
      </button>

      {open && (
        <div className="pb-3 space-y-1.5 pl-4">
          {day.events.length === 0 ? (
            <p className="text-xs text-zinc-700 font-mono">No events recorded.</p>
          ) : (
            day.events.map((evt, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className="text-zinc-600 font-mono text-xs w-10 shrink-0">{evt.time}</span>
                <span className={`text-xs font-mono px-1.5 py-0.5 rounded shrink-0 ${EVENT_BADGE[evt.type]}`}>
                  {EVENT_LABEL[evt.type]}
                </span>
                <span className="text-zinc-400 font-mono text-xs">{evt.detail}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function EventTimeline({ days }: { days: DayLog[] }) {
  return (
    <section>
      <h2 className="text-xs font-mono tracking-widest text-zinc-500 uppercase mb-3">
        Event Timeline
      </h2>
      <div>
        {days.map((day, i) => (
          <TimelineDay key={day.date} day={day} defaultOpen={i === 0} />
        ))}
      </div>
    </section>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function ModelCohortPanel({
  cohort,
  label,
  isActive,
}: {
  cohort: ModelCohortStats;
  label: string;
  isActive: boolean;
}) {
  const winRateColor = cohort.win_rate_pct >= 50 ? "text-green-400" : cohort.win_rate_pct >= 40 ? "text-amber-400" : "text-red-400";
  const pnlClass = (v: number) => v > 0 ? "text-green-400" : v < 0 ? "text-red-400" : "text-zinc-400";
  const fmt$ = (v: number) => `${v >= 0 ? "+" : "-"}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  return (
    <div className={`flex-1 rounded border p-4 ${isActive ? "border-emerald-700/60 bg-emerald-950/20" : "border-zinc-800 bg-zinc-900/40"}`}>
      <div className="flex items-baseline justify-between mb-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.1em] text-zinc-500">{label}</p>
          <p className="font-mono text-sm text-zinc-200">{cohort.model}</p>
        </div>
        {isActive && <span className="text-[9px] uppercase tracking-wider text-emerald-400 border border-emerald-800 rounded px-1.5 py-0.5">ACTIVE</span>}
      </div>

      {/* Counts row */}
      <div className="grid grid-cols-3 gap-x-4 text-xs font-mono mb-3">
        <div>
          <p className="text-zinc-500 text-[10px] uppercase">Buys</p>
          <p className="text-zinc-200">{cohort.buys}</p>
        </div>
        <div>
          <p className="text-zinc-500 text-[10px] uppercase">Closed / Open</p>
          <p className="text-zinc-200">{cohort.closed} / {cohort.open}</p>
        </div>
        <div>
          <p className="text-zinc-500 text-[10px] uppercase">Avg Held</p>
          <p className="text-zinc-200">{cohort.avg_holding_days.toFixed(1)}d</p>
        </div>
      </div>

      {/* Quality signals */}
      <div className="border-t border-zinc-800 pt-2 mb-2">
        <div className="grid grid-cols-2 gap-x-4 text-xs font-mono">
          <div>
            <p className="text-zinc-500 text-[10px] uppercase">Win Rate</p>
            <p className={winRateColor}>
              {cohort.win_rate_pct.toFixed(1)}%
              <span className="text-zinc-600 text-[10px] ml-1">({cohort.wins}W/{cohort.losses}L)</span>
            </p>
          </div>
          <div>
            <p className="text-zinc-500 text-[10px] uppercase">Avg Per-Trade Return</p>
            <p className={pnlClass(cohort.avg_per_trade_return_pct)}>
              {cohort.avg_per_trade_return_pct > 0 ? "+" : ""}{cohort.avg_per_trade_return_pct.toFixed(2)}%
            </p>
          </div>
        </div>
      </div>

      {/* P&L breakdown */}
      <div className="border-t border-zinc-800 pt-2 mb-2">
        <div className="grid grid-cols-2 gap-x-4 text-xs font-mono">
          <div>
            <p className="text-zinc-500 text-[10px] uppercase">Realized P&L</p>
            <p className={pnlClass(cohort.realized_pnl)}>{fmt$(cohort.realized_pnl)}</p>
          </div>
          <div>
            <p className="text-zinc-500 text-[10px] uppercase">Unrealized P&L</p>
            <p className={pnlClass(cohort.unrealized_pnl)}>{fmt$(cohort.unrealized_pnl)}</p>
          </div>
        </div>
      </div>

      {/* Combined total */}
      <div className="border-t border-zinc-700 pt-2">
        <p className="text-zinc-400 text-[10px] uppercase tracking-wider mb-1">
          Total P&L Contributed <span className="text-zinc-600 normal-case tracking-normal">(vs starting capital)</span>
        </p>
        <div className="flex items-baseline gap-3">
          <span className={`text-lg font-semibold ${pnlClass(cohort.total_pnl)}`}>
            {fmt$(cohort.total_pnl)}
          </span>
          <span className={`text-sm font-semibold ${pnlClass(cohort.total_pnl_pct)}`}>
            {cohort.total_pnl_pct > 0 ? "+" : ""}{cohort.total_pnl_pct.toFixed(2)}%
          </span>
        </div>
      </div>
    </div>
  );
}

function PerPortfolioTable({ rows }: { rows: PerPortfolioModelStats[] }) {
  if (rows.length === 0) return null;
  const pnlClass = (v: number) => v > 0 ? "text-green-400" : v < 0 ? "text-red-400" : "text-zinc-500";
  const fmt$ = (v: number) => `${v >= 0 ? "+" : "-"}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  const fmtPct = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;

  return (
    <div className="mt-4 rounded border border-zinc-800 bg-zinc-900/30">
      <div className="px-3 py-2 border-b border-zinc-800">
        <p className="text-[10px] uppercase tracking-[0.1em] text-zinc-500 font-mono">
          By Portfolio
        </p>
      </div>
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-[9px] uppercase tracking-wider text-zinc-600 border-b border-zinc-800/60">
            <th className="text-left px-3 py-2 font-normal">Portfolio</th>
            <th colSpan={4} className="text-left px-3 py-2 font-normal border-l border-zinc-800/60">Baseline (4.6)</th>
            <th colSpan={4} className="text-left px-3 py-2 font-normal border-l border-zinc-800/60">Challenger (4.7)</th>
          </tr>
          <tr className="text-[9px] uppercase tracking-wider text-zinc-700 border-b border-zinc-800/60">
            <th className="text-left px-3 py-1 font-normal"></th>
            <th className="text-left px-3 py-1 font-normal border-l border-zinc-800/60">C/O</th>
            <th className="text-left px-3 py-1 font-normal">Win%</th>
            <th className="text-left px-3 py-1 font-normal">Avg%</th>
            <th className="text-right px-3 py-1 font-normal">Total P&L</th>
            <th className="text-left px-3 py-1 font-normal border-l border-zinc-800/60">C/O</th>
            <th className="text-left px-3 py-1 font-normal">Win%</th>
            <th className="text-left px-3 py-1 font-normal">Avg%</th>
            <th className="text-right px-3 py-1 font-normal">Total P&L</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const b = r.baseline;
            const c = r.challenger;
            return (
              <tr key={r.portfolio_id} className="border-b border-zinc-800/40 last:border-b-0 hover:bg-zinc-800/20">
                <td className="px-3 py-2 text-zinc-300">{r.portfolio_id}</td>
                <td className="px-3 py-2 text-zinc-400 border-l border-zinc-800/60">{b.closed}/{b.open}</td>
                <td className="px-3 py-2 text-zinc-400">{b.closed > 0 ? `${b.win_rate_pct.toFixed(0)}%` : "—"}</td>
                <td className={`px-3 py-2 ${b.closed > 0 ? pnlClass(b.avg_per_trade_return_pct) : "text-zinc-600"}`}>
                  {b.closed > 0 ? fmtPct(b.avg_per_trade_return_pct) : "—"}
                </td>
                <td className={`px-3 py-2 text-right ${pnlClass(b.total_pnl)}`}>
                  {fmt$(b.total_pnl)}
                  <span className={`ml-2 text-[10px] ${pnlClass(b.total_pnl_pct)}`}>
                    ({b.total_pnl_pct > 0 ? "+" : ""}{b.total_pnl_pct.toFixed(1)}%)
                  </span>
                </td>
                <td className="px-3 py-2 text-zinc-400 border-l border-zinc-800/60">
                  {c.buys === 0 ? "—" : `${c.closed}/${c.open}`}
                </td>
                <td className="px-3 py-2 text-zinc-400">{c.closed > 0 ? `${c.win_rate_pct.toFixed(0)}%` : "—"}</td>
                <td className={`px-3 py-2 ${c.closed > 0 ? pnlClass(c.avg_per_trade_return_pct) : "text-zinc-600"}`}>
                  {c.closed > 0 ? fmtPct(c.avg_per_trade_return_pct) : "—"}
                </td>
                <td className={`px-3 py-2 text-right ${c.total_pnl !== 0 ? pnlClass(c.total_pnl) : "text-zinc-600"}`}>
                  {c.total_pnl !== 0 ? (
                    <>
                      {fmt$(c.total_pnl)}
                      <span className={`ml-2 text-[10px] ${pnlClass(c.total_pnl_pct)}`}>
                        ({c.total_pnl_pct > 0 ? "+" : ""}{c.total_pnl_pct.toFixed(1)}%)
                      </span>
                    </>
                  ) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ModelExperimentSection() {
  const [attribution, setAttribution] = useState<"sell" | "buy">("sell");
  const { data, isLoading } = useQuery<ModelComparisonResponse>({
    queryKey: ["model-comparison", attribution],
    queryFn: () => api.getModelComparison(attribution),
    refetchInterval: 60_000,
  });

  if (isLoading || !data) return null;

  const { baseline, challenger, switch_date, end_date, days_remaining, portfolios_included } = data;

  const toggleBtn = (mode: "sell" | "buy", label: string, tip: string) => (
    <button
      onClick={() => setAttribution(mode)}
      title={tip}
      className={`px-2 py-0.5 text-[9px] uppercase tracking-wider font-mono border transition-colors ${
        attribution === mode
          ? "border-emerald-700/70 bg-emerald-950/50 text-emerald-300"
          : "border-zinc-800 bg-zinc-900/40 text-zinc-500 hover:text-zinc-300"
      }`}
    >
      {label}
    </button>
  );

  return (
    <section className="mb-6">
      <div className="flex items-baseline justify-between mb-3">
        <div className="flex items-baseline gap-3">
          <h2 className="text-[11px] font-mono tracking-widest text-zinc-400 uppercase">
            Model Experiment · 4.6 vs 4.7
          </h2>
          <div className="flex gap-0 rounded overflow-hidden">
            {toggleBtn("sell", "By Sell", "Realized P&L credited to SELL cohort (exit decision)")}
            {toggleBtn("buy", "By Buy", "All P&L credited to BUY cohort (entry decision)")}
          </div>
        </div>
        <div className="flex items-baseline gap-3 text-[10px] font-mono text-zinc-500">
          <span>switched {switch_date}</span>
          <span className="text-zinc-700">·</span>
          <span>ends {end_date}</span>
          <span className="text-zinc-700">·</span>
          <span className={days_remaining <= 3 ? "text-amber-400" : "text-zinc-300"}>
            {days_remaining}d left
          </span>
        </div>
      </div>
      <div className="flex gap-3">
        <ModelCohortPanel cohort={baseline} label="Baseline" isActive={false} />
        <ModelCohortPanel cohort={challenger} label="Challenger" isActive={true} />
      </div>
      <PerPortfolioTable rows={data.by_portfolio} />
      <p className="text-[9px] font-mono text-zinc-600 mt-2">
        across {portfolios_included.length} active portfolios · cohort inferred from ai_model tag (falling back to trade date) · C/O = closed / open lots ·{" "}
        {attribution === "sell"
          ? "realized → SELL cohort, unrealized → BUY cohort"
          : "all P&L → BUY cohort"}
      </p>
    </section>
  );
}

export default function LogsPage() {
  const { data, isLoading } = useSystemLogs();
  const updatedAt = new Date().toLocaleTimeString("en-US", {
    hour: "numeric", minute: "2-digit",
  });

  return (
    <main className="flex-1 overflow-y-auto p-6 min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xs font-mono tracking-widest text-zinc-400 uppercase">
          System Logs
        </h1>
        <span className="text-xs font-mono text-zinc-600">
          last updated {updatedAt}
        </span>
      </div>

      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-6 bg-zinc-800 rounded w-full" />
          ))}
        </div>
      ) : !data || data.days.every((d) => d.events.length === 0 && d.watchdog_restarts === 0) ? (
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <p className="text-zinc-500 font-mono text-sm mb-1">No logs yet</p>
          <p className="text-zinc-700 font-mono text-xs">
            Pipeline activity will appear here after the first cron run (6:30 AM tomorrow).
          </p>
        </div>
      ) : (
        <>
          <NarrativeSection />
          <ModelExperimentSection />
          <PipelineGrid days={data.days} />
          <EventTimeline days={data.days} />
        </>
      )}
    </main>
  );
}
