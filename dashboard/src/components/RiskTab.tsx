/** Risk tab — scoreboard, component bars, early warnings. */

import { useRisk, useWarnings } from "../hooks/useRisk";
import type { RiskComponent, Warning } from "../lib/types";

function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (score / 100) * circumference;
  const color =
    score >= 70 ? "var(--color-profit)" : score >= 40 ? "var(--color-warning)" : "var(--color-loss)";

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-border)"
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
        <span className="font-mono text-xl font-bold text-text-primary">
          {Math.round(score)}
        </span>
        <span className="text-[10px] text-text-muted">/100</span>
      </div>
    </div>
  );
}

function ComponentBar({ component }: { component: RiskComponent }) {
  const barColor =
    component.status === "OK"
      ? "bg-profit"
      : component.status === "WARNING"
        ? "bg-warning"
        : "bg-loss";

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-text-secondary w-28 shrink-0 truncate">
        {component.name}
      </span>
      <div className="flex-1 h-2 rounded-full bg-bg-primary overflow-hidden">
        <div
          className={`h-full rounded-full ${barColor} transition-all duration-500`}
          style={{ width: `${Math.max(2, component.score)}%` }}
        />
      </div>
      <span className="font-mono text-xs text-text-muted w-8 text-right shrink-0">
        {Math.round(component.score)}
      </span>
    </div>
  );
}

function WarningCard({ warning }: { warning: Warning }) {
  const severityStyles: Record<string, string> = {
    critical: "border-loss/40 bg-loss/5",
    high: "border-warning/40 bg-warning/5",
    medium: "border-accent/30 bg-accent/5",
    info: "border-border bg-bg-elevated/30",
  };
  const severityBadge: Record<string, string> = {
    critical: "bg-loss/15 text-loss",
    high: "bg-warning/15 text-warning",
    medium: "bg-accent/15 text-accent",
    info: "bg-bg-elevated text-text-muted",
  };

  const style = severityStyles[warning.severity] ?? severityStyles.info;
  const badge = severityBadge[warning.severity] ?? severityBadge.info;

  return (
    <div className={`border rounded-lg p-3 ${style}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider ${badge}`}>
          {warning.severity}
        </span>
        <span className="text-xs text-text-muted">{warning.category}</span>
      </div>
      <p className="text-sm font-medium text-text-primary mb-1">
        {warning.title}
      </p>
      <p className="text-xs text-text-secondary">{warning.description}</p>
      {warning.action_suggestion && (
        <p className="text-xs text-accent mt-1.5 italic">
          {warning.action_suggestion}
        </p>
      )}
    </div>
  );
}

export default function RiskTab() {
  const { data: risk, isLoading: riskLoading, error: riskError } = useRisk();
  const { data: warnings, isLoading: warningsLoading, error: warningsError } = useWarnings();

  if (riskLoading || warningsLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (riskError || warningsError) {
    return (
      <div className="p-6 text-center text-text-muted">
        <p className="text-loss mb-2">Failed to load risk data</p>
        <button onClick={() => window.location.reload()} className="text-xs text-accent hover:underline">Retry</button>
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
              <h3 className="text-sm font-semibold text-text-primary">
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
            <p className="text-xs text-text-secondary leading-relaxed mb-3">
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
          <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-2">
            Recommended Actions
          </h3>
          <div className="space-y-1">
            {risk.recommended_actions.map((action, i) => (
              <p key={i} className="text-xs text-text-secondary pl-3 border-l-2 border-accent/30">
                {action}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Early warnings */}
      {warnings && warnings.length > 0 && (
        <div>
          <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-2">
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
        <div className="text-center text-text-muted text-xs py-4">
          No active warnings. All clear.
        </div>
      )}
    </div>
  );
}
