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
          stroke="var(--bg-elevated)"
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
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 22,
            fontWeight: 700,
            color: "var(--text-primary)",
            lineHeight: 1,
          }}
        >
          {animatedScore}
        </span>
        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>/100</span>
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
        style={{
          fontSize: 11,
          color: "var(--text-muted)",
          width: 112,
          flexShrink: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {component.name}
      </span>
      <div
        className="flex-1 h-2 rounded-full overflow-hidden"
        style={{ background: "var(--bg-elevated)" }}
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
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          width: 32,
          textAlign: "right",
          flexShrink: 0,
          color: "var(--text-secondary)",
        }}
      >
        {Math.round(component.score)}
      </span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styleMap: Record<string, { bg: string; color: string }> = {
    OK:     { bg: "var(--green-dim)",  color: "var(--green)" },
    WARN:   { bg: "var(--amber-dim)",  color: "var(--amber)" },
    WARNING:{ bg: "var(--amber-dim)",  color: "var(--amber)" },
    DANGER: { bg: "var(--red-dim)",    color: "var(--red)" },
  };
  const s = styleMap[status] ?? { bg: "rgba(148,163,184,0.08)", color: "var(--text-secondary)" };
  return (
    <span
      style={{
        fontSize: 9,
        fontWeight: 700,
        padding: "2px 6px",
        borderRadius: 4,
        letterSpacing: "0.07em",
        textTransform: "uppercase" as const,
        background: s.bg,
        color: s.color,
      }}
    >
      {status}
    </span>
  );
}

function WarningCard({ warning }: { warning: Warning }) {
  const isCritical = warning.severity === "critical" || warning.severity === "high";
  const isMedium = warning.severity === "medium";

  const bg = isCritical ? "var(--red-dim)" : isMedium ? "var(--amber-dim)" : "rgba(148,163,184,0.04)";
  const borderColor = isCritical ? "var(--red)" : isMedium ? "var(--amber)" : "var(--border)";
  const badgeBg = isCritical ? "rgba(239,68,68,0.15)" : isMedium ? "rgba(245,158,11,0.15)" : "rgba(148,163,184,0.1)";
  const badgeColor = isCritical ? "var(--red)" : isMedium ? "var(--amber)" : "var(--text-secondary)";

  return (
    <div
      style={{
        borderRadius: "var(--radius)",
        padding: "10px 12px",
        background: bg,
        border: `1px solid ${borderColor}`,
      }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            padding: "2px 6px",
            borderRadius: 4,
            textTransform: "uppercase" as const,
            letterSpacing: "0.07em",
            background: badgeBg,
            color: badgeColor,
          }}
        >
          {warning.severity}
        </span>
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>{warning.category}</span>
      </div>
      <p style={{ fontSize: 12, fontWeight: 500, color: "var(--text-primary)", marginBottom: 2 }}>
        {warning.title}
      </p>
      <p style={{ fontSize: 11, color: "var(--text-secondary)" }}>{warning.description}</p>
      {warning.action_suggestion && (
        <p style={{ fontSize: 11, marginTop: 6, fontStyle: "italic", color: "var(--accent)" }}>
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
  color: "var(--text-muted)",
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
            borderColor: "var(--accent-dim)",
            borderTopColor: "var(--accent)",
          }}
        />
      </div>
    );
  }

  if (riskError || warningsError) {
    return (
      <div className="p-6 text-center" style={{ color: "var(--text-secondary)" }}>
        <p className="mb-2" style={{ color: "var(--red)" }}>Failed to load risk data</p>
        <button
          onClick={() => window.location.reload()}
          className="text-xs hover:underline"
          style={{ color: "var(--accent)" }}
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
              <h3 style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                Risk Score
              </h3>
              <StatusBadge status={risk.risk_level} />
            </div>
            <p style={{ fontSize: 11, lineHeight: 1.6, marginBottom: 10, color: "var(--text-secondary)" }}>
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
                style={{
                  fontSize: 11,
                  paddingLeft: 10,
                  color: "var(--text-secondary)",
                  borderLeft: "2px solid var(--accent-dim)",
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
        <div style={{ textAlign: "center", fontSize: 11, padding: "16px 0", color: "var(--text-muted)" }}>
          No active warnings. All clear.
        </div>
      )}
    </div>
  );
}
