/**
 * LogsPage — system health + pipeline status + Claude daily briefing.
 * Activated when activePortfolioId === "logs".
 */

import { useState } from "react";
import { useSystemLogs, useSystemNarrative, useRegenerateNarrative } from "../hooks/useSystemLogs";
import type { DayLog, PipelineJob, LogEvent } from "../lib/types";

// ── Badge colours (inline styles using design tokens) ─────────────────────────

const EVENT_BADGE_STYLE: Record<LogEvent["type"], React.CSSProperties> = {
  scan:        { background: "rgba(96,165,250,0.12)", color: "#60A5FA", border: "1px solid rgba(96,165,250,0.2)" },
  execute:     { background: "var(--green-dim)",      color: "var(--green)", border: "1px solid rgba(34,197,94,0.2)" },
  update:      { background: "rgba(45,212,191,0.10)", color: "#2DD4BF", border: "1px solid rgba(45,212,191,0.2)" },
  api_restart: { background: "var(--amber-dim)",      color: "var(--amber)", border: "1px solid rgba(245,158,11,0.2)" },
  failed:      { background: "var(--red-dim)",        color: "var(--red)",   border: "1px solid rgba(239,68,68,0.2)" },
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
    return <span style={{ color: "var(--text-dim)", fontFamily: "var(--font-mono)", fontSize: "12px" }}>—</span>;
  }
  const total = job.ok + job.failed;
  if (job.status === "failed" && total === 0) {
    return <span style={{ color: "var(--red)", fontFamily: "var(--font-mono)", fontSize: "12px" }}>✗</span>;
  }
  const hasFailures = job.failed > 0;
  const color = hasFailures ? "var(--amber)" : "var(--green)";
  const icon = hasFailures ? "⚠" : "✓";
  return (
    <span style={{ color, fontFamily: "var(--font-mono)", fontSize: "12px" }}>
      {icon} {job.ok}/{total}
    </span>
  );
}

function WatchdogCell({ restarts }: { restarts: number }) {
  if (restarts === 0) {
    return <span style={{ color: "var(--text-dim)", fontFamily: "var(--font-mono)", fontSize: "12px" }}>0</span>;
  }
  return (
    <span style={{ color: "var(--amber)", fontFamily: "var(--font-mono)", fontSize: "12px" }}>
      ⚡ {restarts}
    </span>
  );
}

function NarrativeSection() {
  const { data, isLoading } = useSystemNarrative();
  const regenerateMutation = useRegenerateNarrative();

  return (
    <section
      className="mb-8 rounded-lg p-5"
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <h2
          style={{
            fontSize: "10px",
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--text-muted)",
          }}
        >
          Today's Briefing
        </h2>
        <button
          onClick={() => regenerateMutation.mutate()}
          disabled={regenerateMutation.isPending}
          style={{
            fontSize: "11px",
            fontFamily: "var(--font-mono)",
            color: regenerateMutation.isPending ? "var(--text-dim)" : "var(--text-muted)",
            background: "none",
            border: "none",
            cursor: regenerateMutation.isPending ? "not-allowed" : "pointer",
            opacity: regenerateMutation.isPending ? 0.4 : 1,
            transition: "color 0.15s",
          }}
          onMouseEnter={(e) => { if (!regenerateMutation.isPending) (e.currentTarget as HTMLButtonElement).style.color = "var(--text-primary)"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--text-muted)"; }}
        >
          {regenerateMutation.isPending ? "Generating…" : "Regenerate ↺"}
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {[100, 90, 95, 80].map((w, i) => (
            <div key={i} className="h-3 rounded" style={{ width: `${w}%`, background: "var(--bg-elevated)" }} />
          ))}
        </div>
      ) : data?.narrative ? (
        <p
          style={{
            fontSize: "13px",
            color: "var(--text-secondary)",
            lineHeight: "1.7",
            whiteSpace: "pre-wrap",
            fontFamily: "var(--font-mono)",
          }}
        >
          {data.narrative}
        </p>
      ) : (
        <p style={{ fontSize: "13px", color: "var(--text-muted)", fontStyle: "italic" }}>
          {data?.error
            ? "Narrative unavailable — Claude call failed."
            : "No briefing yet. Check back after the first cron run (6:30 AM tomorrow)."}
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
      <h2
        style={{
          fontSize: "10px",
          fontFamily: "var(--font-mono)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--text-muted)",
          marginBottom: "12px",
        }}
      >
        Pipeline Status
      </h2>
      <div className="overflow-x-auto">
        <table style={{ width: "100%", fontSize: "12px", fontFamily: "var(--font-mono)", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "var(--text-dim)", borderBottom: "1px solid var(--border)" }}>
              <th style={{ textAlign: "left", paddingTop: "8px", paddingBottom: "8px", paddingRight: "24px", fontWeight: "normal" }}>DATE</th>
              <th style={{ textAlign: "center", padding: "8px 12px", fontWeight: "normal" }}>SCAN 6:30</th>
              <th style={{ textAlign: "center", padding: "8px 12px", fontWeight: "normal" }}>EXECUTE 9:35</th>
              <th style={{ textAlign: "center", padding: "8px 12px", fontWeight: "normal" }}>UPDATE 12:00</th>
              <th style={{ textAlign: "center", padding: "8px 12px", fontWeight: "normal" }}>UPDATE 4:15</th>
              <th style={{ textAlign: "center", padding: "8px 12px", fontWeight: "normal" }}>WATCHDOG</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((day) => {
              const isToday = day.date === today;
              return (
                <tr
                  key={day.date}
                  style={{
                    borderBottom: "1px solid rgba(148,163,184,0.05)",
                    background: isToday ? "var(--bg-elevated)" : "transparent",
                  }}
                >
                  <td style={{ paddingTop: "8px", paddingBottom: "8px", paddingRight: "24px", color: isToday ? "var(--text-primary)" : "var(--text-muted)" }}>
                    {day.date}
                  </td>
                  <td style={{ padding: "8px 12px", textAlign: "center" }}>
                    <StatusCell job={day.pipeline.scan} />
                  </td>
                  <td style={{ padding: "8px 12px", textAlign: "center" }}>
                    <StatusCell job={day.pipeline.execute} />
                  </td>
                  <td style={{ padding: "8px 12px", textAlign: "center" }}>
                    <StatusCell job={day.pipeline.update_midday} />
                  </td>
                  <td style={{ padding: "8px 12px", textAlign: "center" }}>
                    <StatusCell job={day.pipeline.update_close} />
                  </td>
                  <td style={{ padding: "8px 12px", textAlign: "center" }}>
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
    <div style={{ borderBottom: "1px solid rgba(148,163,184,0.05)" }}>
      <button
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "8px 0",
          fontSize: "12px",
          fontFamily: "var(--font-mono)",
          color: "var(--text-muted)",
          background: "none",
          border: "none",
          cursor: "pointer",
          transition: "color 0.15s",
          textAlign: "left",
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--text-muted)"; }}
        onClick={() => setOpen((o) => !o)}
      >
        <span>{open ? "▼" : "▶"}</span>
        <span>{label}</span>
        {day.events.length > 0 && (
          <span style={{ color: "var(--text-dim)" }}>({day.events.length} events)</span>
        )}
      </button>

      {open && (
        <div style={{ paddingBottom: "12px", paddingLeft: "16px" }} className="space-y-1.5">
          {day.events.length === 0 ? (
            <p style={{ fontSize: "12px", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>No events recorded.</p>
          ) : (
            day.events.map((evt, i) => (
              <div key={i} className="flex items-center gap-3">
                <span style={{ color: "var(--text-dim)", fontFamily: "var(--font-mono)", fontSize: "12px", width: "40px", flexShrink: 0 }}>{evt.time}</span>
                <span
                  style={{
                    fontSize: "11px",
                    fontFamily: "var(--font-mono)",
                    padding: "2px 6px",
                    borderRadius: "4px",
                    flexShrink: 0,
                    ...EVENT_BADGE_STYLE[evt.type],
                  }}
                >
                  {EVENT_LABEL[evt.type]}
                </span>
                <span style={{ color: "var(--text-secondary)", fontFamily: "var(--font-mono)", fontSize: "12px" }}>{evt.detail}</span>
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
      <h2
        style={{
          fontSize: "10px",
          fontFamily: "var(--font-mono)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--text-muted)",
          marginBottom: "12px",
        }}
      >
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
        <h1
          style={{
            fontSize: "11px",
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--text-secondary)",
          }}
        >
          System Logs
        </h1>
        <span style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--text-dim)" }}>
          last updated {updatedAt}
        </span>
      </div>

      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-6 rounded w-full" style={{ background: "var(--bg-elevated)" }} />
          ))}
        </div>
      ) : !data || data.days.every((d) => d.events.length === 0 && d.watchdog_restarts === 0) ? (
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <p style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "14px", marginBottom: "4px" }}>No logs yet</p>
          <p style={{ color: "var(--text-dim)", fontFamily: "var(--font-mono)", fontSize: "12px" }}>
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
