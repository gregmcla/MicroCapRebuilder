/** Performance tab — health grade, metrics, attribution, factor learning. */

import { usePerformance, useLearning } from "../hooks/usePerformance";
import type { HealthComponent, FactorAttribution, TradeContribution } from "../lib/types";

function GradeRing({ grade, score }: { grade: string; score: number }) {
  const color =
    score >= 80 ? "text-profit border-profit/40"
      : score >= 60 ? "text-accent border-accent/40"
        : score >= 40 ? "text-warning border-warning/40"
          : "text-loss border-loss/40";

  return (
    <div className={`w-16 h-16 rounded-full border-4 flex items-center justify-center ${color}`}>
      <span className="text-xl font-bold">{grade}</span>
    </div>
  );
}

function ComponentRow({ comp }: { comp: HealthComponent }) {
  const gradeColor =
    comp.score >= 80 ? "text-profit"
      : comp.score >= 60 ? "text-accent"
        : comp.score >= 40 ? "text-warning"
          : "text-loss";

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-text-secondary w-32 shrink-0 truncate">
        {comp.name}
      </span>
      <div className="flex-1 h-1.5 rounded-full bg-bg-primary overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            comp.score >= 80 ? "bg-profit"
              : comp.score >= 60 ? "bg-accent"
                : comp.score >= 40 ? "bg-warning"
                  : "bg-loss"
          }`}
          style={{ width: `${Math.max(2, comp.score)}%` }}
        />
      </div>
      <span className={`font-mono text-xs w-6 text-right shrink-0 font-medium ${gradeColor}`}>
        {comp.grade}
      </span>
    </div>
  );
}

function MetricCard({ label, value, suffix }: { label: string; value: string; suffix?: string }) {
  return (
    <div className="bg-bg-elevated/50 rounded-lg p-2.5 border border-border/50">
      <p className="text-[10px] text-text-muted uppercase tracking-wider mb-0.5">
        {label}
      </p>
      <p className="font-mono text-sm font-semibold text-text-primary">
        {value}
        {suffix && <span className="text-text-muted text-xs">{suffix}</span>}
      </p>
    </div>
  );
}

function AttributionBar({ attr }: { attr: FactorAttribution }) {
  const isPositive = attr.contribution >= 0;
  const color = isPositive ? "bg-profit" : "bg-loss";
  const textColor = isPositive ? "text-profit" : "text-loss";
  const maxWidth = 60; // max % of bar width
  const width = Math.min(maxWidth, Math.abs(attr.contribution_pct));

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-text-secondary w-28 shrink-0 capitalize">
        {attr.factor}
      </span>
      <div className="flex-1 flex items-center">
        {!isPositive && (
          <div className="flex-1 flex justify-end">
            <div className={`h-2 rounded-l-full ${color}`} style={{ width: `${width}%` }} />
          </div>
        )}
        <div className="w-px h-4 bg-border shrink-0" />
        {isPositive && (
          <div className="flex-1">
            <div className={`h-2 rounded-r-full ${color}`} style={{ width: `${width}%` }} />
          </div>
        )}
        {!isPositive && <div className="flex-1" />}
      </div>
      <span className={`font-mono text-xs w-16 text-right shrink-0 ${textColor}`}>
        {isPositive ? "+" : ""}${attr.contribution.toFixed(0)}
      </span>
    </div>
  );
}

function ContributorRow({ trade }: { trade: TradeContribution }) {
  const color = trade.pnl >= 0 ? "text-profit" : "text-loss";
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="font-semibold text-text-primary w-12">{trade.ticker}</span>
      <span className={`font-mono w-16 text-right ${color}`}>
        {trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(0)}
      </span>
      <span className={`font-mono w-14 text-right ${color}`}>
        {trade.pnl_pct >= 0 ? "+" : ""}{trade.pnl_pct.toFixed(1)}%
      </span>
      <span className="text-text-muted text-[10px]">
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
    factor.trend === "improving" ? "text-profit"
      : factor.trend === "declining" ? "text-loss"
        : "text-text-muted";
  const wrColor = factor.win_rate >= 50 ? "text-profit" : "text-loss";

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-text-secondary w-28 shrink-0 capitalize">{factor.factor}</span>
      <span className={`font-mono w-12 text-right ${wrColor}`}>
        {factor.win_rate.toFixed(0)}%
      </span>
      <span className="font-mono text-text-muted w-8 text-right">
        {factor.total_trades}
      </span>
      <span className={`${trendColor} w-4 text-center`}>{trendIcon}</span>
    </div>
  );
}

export default function PerformanceTab() {
  const { data: perf, isLoading: perfLoading } = usePerformance();
  const { data: learning, isLoading: learnLoading } = useLearning();

  if (perfLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
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
              <h3 className="text-sm font-semibold text-text-primary">
                Strategy Health
              </h3>
              {health.pivot_recommended && (
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-warning/15 text-warning uppercase">
                  Pivot {health.pivot_urgency}
                </span>
              )}
            </div>
            <p className="text-xs text-text-secondary mb-3">
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
              <h4 className="text-[10px] font-semibold text-profit uppercase tracking-wider mb-1">
                Working
              </h4>
              {health.what_working.map((w, i) => (
                <p key={i} className="text-xs text-text-secondary leading-relaxed">
                  {w}
                </p>
              ))}
            </div>
          )}
          {health.what_struggling.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold text-loss uppercase tracking-wider mb-1">
                Struggling
              </h4>
              {health.what_struggling.map((w, i) => (
                <p key={i} className="text-xs text-text-secondary leading-relaxed">
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
          <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-2">
            Key Metrics
          </h3>
          <div className="grid grid-cols-4 gap-2">
            <MetricCard label="Sharpe" value={metrics.sharpe_ratio.toFixed(2)} />
            <MetricCard label="Sortino" value={metrics.sortino_ratio.toFixed(2)} />
            <MetricCard label="Max DD" value={`${metrics.max_drawdown_pct.toFixed(1)}`} suffix="%" />
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
          <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-2">
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
              <h4 className="text-[10px] font-semibold text-profit uppercase tracking-wider mb-2">
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
              <h4 className="text-[10px] font-semibold text-loss uppercase tracking-wider mb-2">
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
          <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-2">
            Factor Learning
          </h3>
          <div className="flex items-center gap-2 text-[10px] text-text-muted mb-1 px-0">
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
