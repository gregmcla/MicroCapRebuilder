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
  tradingStyle: _tradingStyle,
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
    <div
      className="space-y-3"
      style={{
        background: "var(--surface-1)",
        border: "1px solid var(--border-0)",
        borderRadius: "8px",
        padding: "12px",
      }}
    >
      {/* Sectors */}
      <div>
        <label
          className="block uppercase tracking-wider mb-1"
          style={{ fontSize: "10px", color: "var(--text-1)" }}
        >
          Sectors
        </label>
        <div className="flex flex-wrap gap-1">
          {sectors.length === 11 || sectors.length === 0 ? (
            <span
              className="px-2 py-0.5 text-xs rounded"
              style={{ background: "rgba(124,92,252,0.10)", color: "var(--accent)" }}
            >
              All Sectors
            </span>
          ) : (
            sectors.map((s) => (
              <span
                key={s}
                className="px-2 py-0.5 text-xs rounded"
                style={{ background: "rgba(124,92,252,0.10)", color: "var(--accent)" }}
              >
                {s}
              </span>
            ))
          )}
        </div>
      </div>

      {/* Trading Style */}
      <div>
        <label
          className="block uppercase tracking-wider mb-1"
          style={{ fontSize: "10px", color: "var(--text-1)" }}
        >
          Trading Style
        </label>
        <span className="text-sm font-medium" style={{ color: "var(--text-3)" }}>
          {tradingStyleLabel}
        </span>
      </div>

      {/* Scoring Weights */}
      <div>
        <label
          className="block uppercase tracking-wider mb-1"
          style={{ fontSize: "10px", color: "var(--text-1)" }}
        >
          Factor Weights
        </label>
        <div className="grid grid-cols-3 gap-x-4 gap-y-1">
          {Object.entries(scoringWeights).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between text-xs">
              <span style={{ color: "var(--text-1)" }}>{WEIGHT_LABELS[k] ?? k}</span>
              <span className="font-mono" style={{ color: "var(--text-3)" }}>
                {(v * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Risk Params */}
      <div>
        <label
          className="block uppercase tracking-wider mb-1"
          style={{ fontSize: "10px", color: "var(--text-1)" }}
        >
          Risk Parameters
        </label>
        <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-xs">
          <div className="flex justify-between">
            <span style={{ color: "var(--text-1)" }}>Stop Loss</span>
            <span className="font-mono" style={{ color: "var(--text-3)" }}>{stopLoss}%</span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: "var(--text-1)" }}>Risk/Trade</span>
            <span className="font-mono" style={{ color: "var(--text-3)" }}>{riskPerTrade}%</span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: "var(--text-1)" }}>Max Pos</span>
            <span className="font-mono" style={{ color: "var(--text-3)" }}>{maxPosition}%</span>
          </div>
        </div>
      </div>

      {/* Enabled Scans */}
      <div>
        <label
          className="block uppercase tracking-wider mb-1"
          style={{ fontSize: "10px", color: "var(--text-1)" }}
        >
          Discovery Scans
        </label>
        <div className="flex flex-wrap gap-1">
          {enabledScans.map((s) => (
            <span
              key={s}
              className="px-2 py-0.5 text-xs rounded"
              style={{
                background: "var(--surface-3)",
                color: "var(--text-2)",
              }}
            >
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* AI Rationale */}
      {rationale && (
        <div>
          <label
            className="block uppercase tracking-wider mb-1"
            style={{ fontSize: "10px", color: "var(--text-1)" }}
          >
            AI Rationale
          </label>
          <p className="text-xs italic leading-relaxed" style={{ color: "var(--text-2)" }}>
            {rationale}
          </p>
        </div>
      )}
    </div>
  );
}
