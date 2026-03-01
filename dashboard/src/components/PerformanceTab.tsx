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

  return (
    <div
      className="w-16 h-16 rounded-full border-4 flex items-center justify-center shrink-0"
      style={{
        borderColor: color,
        color: color,
      }}
    >
      <span className="text-xl font-bold">{grade}</span>
    </div>
  );
}

function ComponentRow({ comp }: { comp: HealthComponent }) {
  const color = gradeColor(comp.score);

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs w-32 shrink-0 truncate" style={{ color: "var(--text-2)" }}>
        {comp.name}
      </span>
      <div
        className="flex-1 h-1.5 rounded-full overflow-hidden"
        style={{ background: "rgba(255,255,255,0.06)" }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${Math.max(2, comp.score)}%`,
            background: `linear-gradient(to right, var(--accent), var(--accent-bright))`,
          }}
        />
      </div>
      <span
        className="font-mono text-xs w-6 text-right shrink-0 font-medium tabular-nums"
        style={{ color }}
      >
        {comp.grade}
      </span>
    </div>
  );
}

function MetricCard({ label, value, suffix }: { label: string; value: string; suffix?: string }) {
  return (
    <div
      className="rounded-lg p-2.5"
      style={{
        background: "var(--surface-1)",
        border: "1px solid var(--border-0)",
        borderRadius: 8,
      }}
    >
      <p
        className="text-[10px] uppercase tracking-wider mb-0.5"
        style={{ color: "var(--text-0)" }}
      >
        {label}
      </p>
      <p className="font-mono text-sm font-semibold tabular-nums" style={{ color: "var(--text-4)" }}>
        {value}
        {suffix && <span className="text-xs" style={{ color: "var(--text-1)" }}>{suffix}</span>}
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
      <span className="text-xs w-28 shrink-0 capitalize" style={{ color: "var(--text-2)" }}>
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
          style={{ background: "var(--border-0)" }}
        />
        {isPositive && (
          <div className="flex-1">
            <div
              className="h-2 rounded-r-full"
              style={{
                width: `${width}%`,
                background: "linear-gradient(to right, var(--accent), var(--accent-bright))",
              }}
            />
          </div>
        )}
        {!isPositive && <div className="flex-1" />}
      </div>
      <span
        className="font-mono text-xs w-16 text-right shrink-0 tabular-nums"
        style={{ color: textColor }}
      >
        {isPositive ? "+" : ""}${attr.contribution.toFixed(0)}
      </span>
    </div>
  );
}

function ContributorRow({ trade }: { trade: TradeContribution }) {
  const color = trade.pnl >= 0 ? "var(--green)" : "var(--red)";
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="font-semibold w-12" style={{ color: "var(--text-4)" }}>{trade.ticker}</span>
      <span className="font-mono w-16 text-right tabular-nums" style={{ color }}>
        {trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(0)}
      </span>
      <span className="font-mono w-14 text-right tabular-nums" style={{ color }}>
        {trade.pnl_pct >= 0 ? "+" : ""}{trade.pnl_pct.toFixed(1)}%
      </span>
      <span className="text-[10px]" style={{ color: "var(--text-0)" }}>
        {trade.is_realized ? "closed" : "open"}
      </span>
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
        : "var(--text-0)";
  const wrColor = factor.win_rate >= 50 ? "var(--green)" : "var(--red)";

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 shrink-0 capitalize" style={{ color: "var(--text-2)" }}>{factor.factor}</span>
      <span className="font-mono w-12 text-right tabular-nums" style={{ color: wrColor }}>
        {factor.win_rate.toFixed(0)}%
      </span>
      <span className="font-mono w-8 text-right tabular-nums" style={{ color: "var(--text-0)" }}>
        {factor.total_trades}
      </span>
      <span className="w-4 text-center" style={{ color: trendColor }}>{trendIcon}</span>
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

export default function PerformanceTab() {
  const { data: perf, isLoading: perfLoading, error: perfError } = usePerformance();
  const { data: learning, isLoading: learnLoading } = useLearning();

  if (perfLoading) {
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

  if (perfError) {
    return (
      <div className="p-6 text-center" style={{ color: "var(--text-1)" }}>
        <p className="mb-2" style={{ color: "var(--red)" }}>Failed to load performance data</p>
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
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-4)" }}>
                Strategy Health
              </h3>
              {health.pivot_recommended && (
                <span
                  className="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase"
                  style={{
                    background: "rgba(251,191,36,0.15)",
                    color: "var(--amber)",
                  }}
                >
                  Pivot {health.pivot_urgency}
                </span>
              )}
            </div>
            <p className="text-xs mb-3" style={{ color: "var(--text-2)" }}>
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
                className="text-[10px] font-semibold uppercase tracking-wider mb-1"
                style={{ color: "var(--green)" }}
              >
                Working
              </h4>
              {health.what_working.map((w, i) => (
                <p key={i} className="text-xs leading-relaxed" style={{ color: "var(--text-2)" }}>
                  {w}
                </p>
              ))}
            </div>
          )}
          {health.what_struggling.length > 0 && (
            <div>
              <h4
                className="text-[10px] font-semibold uppercase tracking-wider mb-1"
                style={{ color: "var(--red)" }}
              >
                Struggling
              </h4>
              {health.what_struggling.map((w, i) => (
                <p key={i} className="text-xs leading-relaxed" style={{ color: "var(--text-2)" }}>
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
            <MetricCard label="Days" value={`${metrics.days_tracked}`} />
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
                className="text-[10px] font-semibold uppercase tracking-wider mb-2"
                style={{ color: "var(--green)" }}
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
                className="text-[10px] font-semibold uppercase tracking-wider mb-2"
                style={{ color: "var(--red)" }}
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
          <div className="flex items-center gap-2 text-[10px] mb-1 px-0" style={{ color: "var(--text-0)" }}>
            <span className="w-28">Factor</span>
            <span className="w-12 text-right">Win%</span>
            <span className="w-8 text-right">N</span>
            <span className="w-4 text-center">Trend</span>
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
