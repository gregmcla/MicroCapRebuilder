/** Market ticker banner - S&P 500, Russell 2000, VIX with sparklines */

import { useMarketIndices } from "../hooks/useMarketIndices";
import type { MarketIndex } from "../lib/types";

function IndexCard({ name, symbol, data }: { name: string; symbol: string; data: MarketIndex | undefined }) {
  if (!data) {
    return (
      <div className="flex-1 flex items-center justify-center gap-3 px-4">
        <span className="text-xs text-text-muted">{name}</span>
        <span className="text-sm text-text-muted">Loading...</span>
      </div>
    );
  }

  const changeColor = data.change_pct >= 0 ? "text-profit" : "text-loss";
  const sparklinePoints = data.sparkline.map((val, i) => {
    const x = (i / (data.sparkline.length - 1)) * 40;
    const minVal = Math.min(...data.sparkline);
    const maxVal = Math.max(...data.sparkline);
    const range = maxVal - minVal || 1;
    const y = 30 - ((val - minVal) / range) * 25;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="flex-1 flex items-center justify-center gap-3 px-4">
      <div className="flex flex-col items-start">
        <span className="text-[10px] text-text-muted uppercase tracking-wider">{name}</span>
        <span className="font-mono text-sm font-semibold text-text-primary">
          {data.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      </div>

      <span className={`font-mono text-xs font-medium ${changeColor}`}>
        {data.change_pct >= 0 ? '+' : ''}{data.change_pct.toFixed(2)}%
      </span>

      {data.sparkline.length > 0 && (
        <svg width="40" height="30" className="opacity-70">
          <defs>
            <linearGradient id={`gradient-${symbol}`} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#22D3EE" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#22D3EE" stopOpacity="0" />
            </linearGradient>
          </defs>
          <polyline
            points={sparklinePoints}
            fill="none"
            stroke="#22D3EE"
            strokeWidth="1.5"
            className="drop-shadow-[0_0_2px_rgba(34,211,238,0.5)]"
          />
          <polygon
            points={`0,30 ${sparklinePoints} 40,30`}
            fill={`url(#gradient-${symbol})`}
          />
        </svg>
      )}
    </div>
  );
}

export default function MarketTickerBanner() {
  const { data, isLoading } = useMarketIndices();

  return (
    <div className="h-[60px] bg-bg-primary border-b border-cyber-cyan/20 shadow-glow-cyan flex items-center">
      <IndexCard name="S&P 500" symbol="sp500" data={data?.sp500} />

      <div className="h-8 w-px bg-cyber-magenta shadow-glow-magenta" />

      <IndexCard name="Russell 2000" symbol="rut" data={data?.russell2000} />

      <div className="h-8 w-px bg-cyber-magenta shadow-glow-magenta" />

      <IndexCard name="VIX" symbol="vix" data={data?.vix} />
    </div>
  );
}
