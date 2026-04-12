/** Performance tab — health grade, metrics, attribution, factor learning. */

import { usePerformance, useLearning } from "../hooks/usePerformance";
import type { HealthComponent, FactorAttribution, TradeContribution } from "../lib/types";

function gradeColor(score: number): string {
  if (score >= 80) return "var(--green)";   // A/B
  if (score >= 60) return "var(--amber)";   // C
  return "var(--red)";                       // D/F
}

function GradeRing({ grade, score }: { grade: string; score: number }) {
  const color = gradeColor(score);
  const size = 64;
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (score / 100) * circumference;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
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
      <div className="absolute inset-0 flex items-center justify-center">
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 20, fontWeight: 700, color }}>{grade}</span>
      </div>
    </div>
  );
}

function ComponentRow({ comp }: { comp: HealthComponent }) {
  const color = gradeColor(comp.score);

  return (
    <div className="flex items-center gap-2">
      <span
        style={{
          fontSize: 11,
          color: "var(--text-muted)",
          width: 128,
          flexShrink: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {comp.name}
      </span>
      <div
        className="flex-1 h-1.5 rounded-full overflow-hidden"
        style={{ background: "var(--bg-elevated)" }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${Math.max(2, comp.score)}%`,
            background: color,
          }}
        />
      </div>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          width: 24,
          textAlign: "right",
          flexShrink: 0,
          fontWeight: 500,
          color,
        }}
      >
        {comp.grade}
      </span>
    </div>
  );
}

function MetricCard({ label, value, suffix }: { label: string; value: string; suffix?: string }) {
  return (
    <div
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "8px 10px",
      }}
    >
      <p
        style={{
          fontSize: 9,
          textTransform: "uppercase" as const,
          letterSpacing: "0.07em",
          color: "var(--text-muted)",
          marginBottom: 2,
        }}
      >
        {label}
      </p>
      <p style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
        {value}
        {suffix && <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>{suffix}</span>}
      </p>
    </div>
  );
}

function AttributionBar({ attr }: { attr: FactorAttribution }) {
  const isPositive = attr.contribution >= 0;
  const textColor = isPositive ? "var(--green)" : "var(--red)";
  const maxWidth = 60;
  const width = Math.min(maxWidth, Math.abs(attr.contribution_pct));

  return (
    <div className="flex items-center gap-2">
      <span style={{ fontSize: 11, width: 112, flexShrink: 0, textTransform: "capitalize" as const, color: "var(--text-secondary)" }}>
        {attr.factor}
      </span>
      <div className="flex-1 flex items-center">
        {!isPositive && (
          <div className="flex-1 flex justify-end">
            <div
              className="h-2 rounded-l-full"
              style={{ width: `${width}%`, background: "var(--red)" }}
            />
          </div>
        )}
        <div
          className="w-px h-4 shrink-0"
          style={{ background: "var(--border)" }}
        />
        {isPositive && (
          <div className="flex-1">
            <div
              className="h-2 rounded-r-full"
              style={{
                width: `${width}%`,
                background: "var(--accent)",
              }}
            />
          </div>
        )}
        {!isPositive && <div className="flex-1" />}
      </div>
      <span
        style={{ fontFamily: "var(--font-mono)", fontSize: 11, width: 64, textAlign: "right", flexShrink: 0, color: textColor }}
      >
        {isPositive ? "+" : ""}${attr.contribution.toFixed(0)}
      </span>
    </div>
  );
}

function ContributorRow({ trade }: { trade: TradeContribution }) {
  const color = trade.pnl >= 0 ? "var(--green)" : "var(--red)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
      <span style={{ fontWeight: 600, width: 48, color: "var(--text-primary)" }}>{trade.ticker}</span>
      <span style={{ fontFamily: "var(--font-mono)", width: 64, textAlign: "right", color }}>{trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(0)}</span>
      <span style={{ fontFamily: "var(--font-mono)", width: 56, textAlign: "right", color }}>{trade.pnl_pct >= 0 ? "+" : ""}{trade.pnl_pct.toFixed(1)}%</span>
      <span style={{ fontSize: 9, color: "var(--text-muted)" }}>{trade.is_realized ? "closed" : "open"}</span>
    </div>
  );
}

function FactorLearningRow({ factor }: { factor: { factor: string; win_rate: number; total_trades: number; total_contribution: number; trend: string } }) {
  const trendIcon =
    factor.trend === "improving" ? "\u2191"
      : factor.trend === "declining" ? "\u2193"
        : "\u2192";
  const trendColor =
    factor.trend === "improving" ? "var(--green)"
      : factor.trend === "declining" ? "var(--red)"
        : "var(--text-muted)";
  const wrColor = factor.win_rate >= 50 ? "var(--green)" : "var(--red)";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
      <span style={{ width: 112, flexShrink: 0, textTransform: "capitalize" as const, color: "var(--text-secondary)" }}>{factor.factor}</span>
      <span style={{ fontFamily: "var(--font-mono)", width: 48, textAlign: "right", color: wrColor }}>
        {factor.win_rate.toFixed(0)}%
      </span>
      <span style={{ fontFamily: "var(--font-mono)", width: 32, textAlign: "right", color: "var(--text-muted)" }}>
        {factor.total_trades}
      </span>
      <span style={{ width: 16, textAlign: "center", color: trendColor }}>{trendIcon}</span>
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

export default function PerformanceTab() {
  const { data: perf, isLoading: perfLoading, error: perfError } = usePerformance();
  const { data: learning, isLoading: learnLoading } = useLearning();

  if (perfLoading) {
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

  if (perfError) {
    return (
      <div className="p-6 text-center" style={{ color: "var(--text-secondary)" }}>
        <p className="mb-2" style={{ color: "var(--red)" }}>Failed to load performance data</p>
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

  const health = perf?.health;
  const metrics = perf?.metrics;
  const attribution = perf?.attribution;
  const factors = learning?.factor_summary;

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-6">
      {/* Strategy health */}
      {health && (
        <div className="flex items-start gap-4">
          <GradeRing grade={health.grade} score={health.score} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                Strategy Health
              </h3>
              {health.pivot_recommended && (
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    padding: "2px 6px",
                    borderRadius: 4,
                    textTransform: "uppercase" as const,
                    background: "var(--amber-dim)",
                    color: "var(--amber)",
                  }}
                >
                  Pivot {health.pivot_urgency}
                </span>
              )}
            </div>
            <p style={{ fontSize: 11, marginBottom: 10, color: "var(--text-secondary)" }}>
              {health.grade_description}
            </p>
            <div className="space-y-1.5">
              {health.components.map((c) => (
                <ComponentRow key={c.name} comp={c} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Diagnosis */}
      {health && (health.what_working.length > 0 || health.what_struggling.length > 0) && (
        <div className="grid grid-cols-2 gap-3">
          {health.what_working.length > 0 && (
            <div>
              <h4
                style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.07em", marginBottom: 4, color: "var(--green)" }}
              >
                Working
              </h4>
              {health.what_working.map((w, i) => (
                <p key={i} style={{ fontSize: 11, lineHeight: 1.5, color: "var(--text-secondary)" }}>
                  {w}
                </p>
              ))}
            </div>
          )}
          {health.what_struggling.length > 0 && (
            <div>
              <h4
                style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.07em", marginBottom: 4, color: "var(--red)" }}
              >
                Struggling
              </h4>
              {health.what_struggling.map((w, i) => (
                <p key={i} style={{ fontSize: 11, lineHeight: 1.5, color: "var(--text-secondary)" }}>
                  {w}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Key metrics */}
      {metrics && (
        <div>
          <h3 style={sectionHeaderStyle} className="mb-2">
            Key Metrics
          </h3>
          <div className="grid grid-cols-4 gap-2">
            <MetricCard label="Sharpe" value={metrics.sharpe_ratio?.toFixed(2) ?? "N/A"} />
            <MetricCard label="Sortino" value={metrics.sortino_ratio?.toFixed(2) ?? "N/A"} />
            <MetricCard label="Max DD" value={`${metrics.max_drawdown_pct?.toFixed(1) ?? "N/A"}`} suffix={metrics.max_drawdown_pct != null ? "%" : ""} />
            <MetricCard label="Volatility" value={`${metrics.volatility_annual.toFixed(1)}`} suffix="%" />
            <MetricCard label="Return" value={`${metrics.total_return_pct >= 0 ? "+" : ""}${metrics.total_return_pct.toFixed(1)}`} suffix="%" />
            <MetricCard label="Alpha" value={`${metrics.alpha_pct >= 0 ? "+" : ""}${metrics.alpha_pct.toFixed(1)}`} suffix="%" />
            <MetricCard label="Exposure" value={`${metrics.exposure_pct.toFixed(0)}`} suffix="%" />
            <MetricCard label="Tracked" value={`${metrics.days_tracked}d`} />
          </div>
        </div>
      )}

      {/* Attribution by factor */}
      {attribution && attribution.factor_details.length > 0 && (
        <div>
          <h3 style={sectionHeaderStyle} className="mb-2">
            Attribution by Factor
          </h3>
          <div className="space-y-1.5">
            {attribution.factor_details.map((f) => (
              <AttributionBar key={f.factor} attr={f} />
            ))}
          </div>
        </div>
      )}

      {/* Top/bottom contributors */}
      {attribution && (attribution.top_contributors.length > 0 || attribution.bottom_contributors.length > 0) && (
        <div className="grid grid-cols-2 gap-4">
          {attribution.top_contributors.length > 0 && (
            <div>
              <h4
                style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.07em", marginBottom: 6, color: "var(--green)" }}
              >
                Top Contributors
              </h4>
              <div className="space-y-1">
                {attribution.top_contributors.slice(0, 5).map((t) => (
                  <ContributorRow key={t.ticker} trade={t} />
                ))}
              </div>
            </div>
          )}
          {attribution.bottom_contributors.length > 0 && (
            <div>
              <h4
                style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.07em", marginBottom: 6, color: "var(--red)" }}
              >
                Bottom Contributors
              </h4>
              <div className="space-y-1">
                {attribution.bottom_contributors.slice(0, 5).map((t) => (
                  <ContributorRow key={t.ticker} trade={t} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Factor learning */}
      {!learnLoading && factors && factors.status === "ok" && factors.factors.length > 0 && (
        <div>
          <h3 style={sectionHeaderStyle} className="mb-2">
            Factor Learning
          </h3>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 9, marginBottom: 4, color: "var(--text-muted)" }}>
            <span style={{ width: 112 }}>Factor</span>
            <span style={{ width: 48, textAlign: "right" }}>Win%</span>
            <span style={{ width: 32, textAlign: "right" }}>N</span>
            <span style={{ width: 16, textAlign: "center" }}>Trend</span>
          </div>
          <div className="space-y-1">
            {factors.factors.map((f) => (
              <FactorLearningRow key={f.factor} factor={f} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
