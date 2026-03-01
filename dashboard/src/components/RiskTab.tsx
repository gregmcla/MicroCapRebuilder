/** Risk tab — scoreboard, component bars, early warnings. */

import { useRisk, useWarnings } from "../hooks/useRisk";
import { useCountUp } from "../hooks/useCountUp";
import type { RiskComponent, Warning } from "../lib/types";

function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const animatedScore = useCountUp(score, 900, 0);
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (score / 100) * circumference;
  const color =
    score >= 70 ? "var(--green)" : score >= 40 ? "var(--amber)" : "var(--red)";

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--border-1)"
          strokeWidth={4}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={4}
          strokeDasharray={`${filled} ${circumference - filled}`}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className="font-mono text-xl font-bold tabular-nums"
          style={{ color: "var(--text-4)" }}
        >
          {animatedScore}
        </span>
        <span className="text-[10px]" style={{ color: "var(--text-0)" }}>/100</span>
      </div>
    </div>
  );
}

function ComponentBar({ component }: { component: RiskComponent }) {
  const barColor =
    component.status === "OK"
      ? "var(--green)"
      : component.status === "WARNING"
        ? "var(--amber)"
        : "var(--red)";

  return (
    <div className="flex items-center gap-3">
      <span
        className="text-xs w-28 shrink-0 truncate"
        style={{ color: "var(--text-2)" }}
      >
        {component.name}
      </span>
      <div
        className="flex-1 h-2 rounded-full overflow-hidden"
        style={{ background: "rgba(255,255,255,0.06)" }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${Math.max(2, component.score)}%`,
            background: barColor,
          }}
        />
      </div>
      <span
        className="font-mono text-xs w-8 text-right shrink-0 tabular-nums"
        style={{ color: "var(--text-0)" }}
      >
        {Math.round(component.score)}
      </span>
    </div>
  );
}

function WarningCard({ warning }: { warning: Warning }) {
  const borderColor: Record<string, string> = {
    critical: "var(--red)",
    high: "var(--red)",
    medium: "var(--amber)",
    info: "var(--text-1)",
    low: "var(--text-1)",
  };
  const bgColor: Record<string, string> = {
    critical: "rgba(248,113,113,0.05)",
    high: "rgba(248,113,113,0.05)",
    medium: "rgba(251,191,36,0.05)",
    info: "rgba(255,255,255,0.02)",
    low: "rgba(255,255,255,0.02)",
  };
  const badgeBg: Record<string, string> = {
    critical: "rgba(248,113,113,0.15)",
    high: "rgba(248,113,113,0.15)",
    medium: "rgba(251,191,36,0.15)",
    info: "rgba(255,255,255,0.06)",
    low: "rgba(255,255,255,0.06)",
  };
  const badgeColor: Record<string, string> = {
    critical: "var(--red)",
    high: "var(--red)",
    medium: "var(--amber)",
    info: "var(--text-1)",
    low: "var(--text-1)",
  };

  const sev = warning.severity;

  return (
    <div
      className="rounded-lg p-3"
      style={{
        background: bgColor[sev] ?? bgColor.info,
        borderLeft: `3px solid ${borderColor[sev] ?? borderColor.info}`,
        border: `1px solid ${borderColor[sev] ?? borderColor.info}`,
        borderLeftWidth: 3,
      }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider"
          style={{
            background: badgeBg[sev] ?? badgeBg.info,
            color: badgeColor[sev] ?? badgeColor.info,
          }}
        >
          {warning.severity}
        </span>
        <span className="text-xs" style={{ color: "var(--text-0)" }}>{warning.category}</span>
      </div>
      <p className="text-sm font-medium mb-1" style={{ color: "var(--text-4)" }}>
        {warning.title}
      </p>
      <p className="text-xs" style={{ color: "var(--text-2)" }}>{warning.description}</p>
      {warning.action_suggestion && (
        <p className="text-xs mt-1.5 italic" style={{ color: "var(--accent-bright)" }}>
          {warning.action_suggestion}
        </p>
      )}
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

export default function RiskTab() {
  const { data: risk, isLoading: riskLoading, error: riskError } = useRisk();
  const { data: warnings, isLoading: warningsLoading, error: warningsError } = useWarnings();

  if (riskLoading || warningsLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div
          className="w-6 h-6 border-2 rounded-full animate-spin"
          style={{
            borderColor: "rgba(124,92,252,0.3)",
            borderTopColor: "var(--accent)",
          }}
        />
      </div>
    );
  }

  if (riskError || warningsError) {
    return (
      <div className="p-6 text-center" style={{ color: "var(--text-1)" }}>
        <p className="mb-2" style={{ color: "var(--red)" }}>Failed to load risk data</p>
        <button
          onClick={() => window.location.reload()}
          className="text-xs hover:underline"
          style={{ color: "var(--accent-bright)" }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-6">
      {/* Scoreboard header */}
      {risk && (
        <div className="flex items-start gap-6">
          <ScoreRing score={risk.overall_score} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-4)" }}>
                Risk Score
              </h3>
              <span
                className="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider"
                style={{
                  backgroundColor: `${risk.risk_color}22`,
                  color: risk.risk_color,
                }}
              >
                {risk.risk_level}
              </span>
            </div>
            <p className="text-xs leading-relaxed mb-3" style={{ color: "var(--text-2)" }}>
              {risk.narrative}
            </p>

            {/* Component bars */}
            <div className="space-y-2">
              {risk.components.map((c) => (
                <ComponentBar key={c.name} component={c} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Recommended actions */}
      {risk && risk.recommended_actions.length > 0 && (
        <div>
          <h3 style={sectionHeaderStyle} className="mb-2">
            Recommended Actions
          </h3>
          <div className="space-y-1">
            {risk.recommended_actions.map((action, i) => (
              <p
                key={i}
                className="text-xs pl-3"
                style={{
                  color: "var(--text-2)",
                  borderLeft: "2px solid rgba(124,92,252,0.3)",
                }}
              >
                {action}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Early warnings */}
      {warnings && warnings.length > 0 && (
        <div>
          <h3 style={sectionHeaderStyle} className="mb-2">
            Early Warnings ({warnings.length})
          </h3>
          <div className="space-y-2">
            {warnings.map((w) => (
              <WarningCard key={w.id} warning={w} />
            ))}
          </div>
        </div>
      )}

      {warnings && warnings.length === 0 && (
        <div className="text-center text-xs py-4" style={{ color: "var(--text-1)" }}>
          No active warnings. All clear.
        </div>
      )}
    </div>
  );
}
