/** Strategy review card — shows assembled config before portfolio creation. */

const WEIGHT_LABELS: Record<string, string> = {
  momentum: "Momentum",
  volatility: "Volatility",
  volume: "Volume",
  relative_strength: "Rel Strength",
  mean_reversion: "Mean Rev",
  rsi: "RSI",
};

interface Props {
  sectors: string[];
  tradingStyle: string | null;
  tradingStyleLabel: string;
  scoringWeights: Record<string, number>;
  stopLoss: number;
  riskPerTrade: number;
  maxPosition: number;
  scanTypes: Record<string, boolean>;
  rationale?: string;
}

export default function StrategyReviewCard({
  sectors,
  tradingStyle,
  tradingStyleLabel,
  scoringWeights,
  stopLoss,
  riskPerTrade,
  maxPosition,
  scanTypes,
  rationale,
}: Props) {
  const enabledScans = Object.entries(scanTypes)
    .filter(([, v]) => v)
    .map(([k]) => k.replace(/_/g, " "));

  return (
    <div className="space-y-3">
      {/* Sectors */}
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
          Sectors
        </label>
        <div className="flex flex-wrap gap-1">
          {sectors.length === 11 || sectors.length === 0 ? (
            <span className="px-2 py-0.5 text-xs bg-accent/10 text-accent rounded">
              All Sectors
            </span>
          ) : (
            sectors.map((s) => (
              <span
                key={s}
                className="px-2 py-0.5 text-xs bg-accent/10 text-accent rounded"
              >
                {s}
              </span>
            ))
          )}
        </div>
      </div>

      {/* Trading Style */}
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
          Trading Style
        </label>
        <span className="text-sm text-text-primary font-medium">
          {tradingStyleLabel}
        </span>
      </div>

      {/* Scoring Weights */}
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
          Factor Weights
        </label>
        <div className="grid grid-cols-3 gap-x-4 gap-y-1">
          {Object.entries(scoringWeights).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between text-xs">
              <span className="text-text-muted">{WEIGHT_LABELS[k] ?? k}</span>
              <span className="font-mono text-text-primary">
                {(v * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Risk Params */}
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
          Risk Parameters
        </label>
        <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-text-muted">Stop Loss</span>
            <span className="font-mono text-text-primary">{stopLoss}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">Risk/Trade</span>
            <span className="font-mono text-text-primary">{riskPerTrade}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">Max Pos</span>
            <span className="font-mono text-text-primary">{maxPosition}%</span>
          </div>
        </div>
      </div>

      {/* Enabled Scans */}
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
          Discovery Scans
        </label>
        <div className="flex flex-wrap gap-1">
          {enabledScans.map((s) => (
            <span
              key={s}
              className="px-2 py-0.5 text-xs bg-bg-surface text-text-secondary rounded"
            >
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* AI Rationale */}
      {rationale && (
        <div>
          <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
            AI Rationale
          </label>
          <p className="text-xs text-text-secondary italic leading-relaxed">
            {rationale}
          </p>
        </div>
      )}
    </div>
  );
}
