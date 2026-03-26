/**
 * LogsPage — system health + pipeline status + Claude daily briefing.
 * Activated when activePortfolioId === "logs".
 */

import { useSystemLogs, useSystemNarrative, useRegenerateNarrative } from "../hooks/useSystemLogs";
import type { DayLog, PipelineJob, LogEvent } from "../lib/types";
import { useState } from "react";

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
          <PipelineGrid days={data.days} />
          <EventTimeline days={data.days} />
        </>
      )}
    </main>
  );
}
