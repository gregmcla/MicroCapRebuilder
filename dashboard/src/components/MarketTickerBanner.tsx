/** Market ticker banner - S&P 500, Russell 2000, VIX with sparklines */

import { useMemo } from "react";
import { useMarketIndices } from "../hooks/useMarketIndices";
import type { MarketIndex } from "../lib/types";

// Constants for SVG dimensions
const SPARKLINE_WIDTH = 40;
const SPARKLINE_HEIGHT = 30;
const SPARKLINE_PADDING = 5;

function IndexCard({
  name,
  symbol,
  data,
  isError
}: {
  name: string;
  symbol: string;
  data: MarketIndex | undefined;
  isError?: boolean;
}) {
  // Memoize sparkline calculations
  const sparklinePoints = useMemo(() => {
    if (!data || data.sparkline.length === 0) return "";

    return data.sparkline.map((val, i) => {
      const x = (i / (data.sparkline.length - 1)) * SPARKLINE_WIDTH;
      const minVal = Math.min(...data.sparkline);
      const maxVal = Math.max(...data.sparkline);
      const range = maxVal - minVal || 1;
      const y = SPARKLINE_HEIGHT - ((val - minVal) / range) * (SPARKLINE_HEIGHT - SPARKLINE_PADDING);
      return `${x},${y}`;
    }).join(' ');
  }, [data]);

  if (isError) {
    return (
      <div className="flex-1 flex items-center justify-center gap-3 px-4">
        <span className="text-xs text-text-muted">{name}</span>
        <span className="text-sm text-loss">Error</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex-1 flex items-center justify-center gap-3 px-4">
        <span className="text-xs text-text-muted">{name}</span>
        <span className="text-sm text-text-muted">Loading...</span>
      </div>
    );
  }

  const changeColor = data.change_pct >= 0 ? "text-profit" : "text-loss";
  const changeSign = data.change_pct >= 0 ? "+" : "";

  return (
    <div className="flex-1 flex items-center justify-center gap-3 px-4">
      <div className="flex flex-col items-start">
        <span className="text-[10px] text-text-muted uppercase tracking-wider">{name}</span>
        <span className="font-mono text-sm font-semibold text-text-primary">
          {data.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      </div>

      <span className={`font-mono text-xs font-medium ${changeColor}`}>
        <span className="sr-only">Change: </span>
        {changeSign}{data.change_pct.toFixed(2)}%
      </span>

      {data.sparkline.length > 0 && (
        <svg
          width={SPARKLINE_WIDTH}
          height={SPARKLINE_HEIGHT}
          className="opacity-70"
          role="img"
          aria-label={`${name} intraday trend sparkline`}
        >
          <title>{`${name} price trend`}</title>
          <defs>
            <linearGradient id={`gradient-${symbol}`} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" className="[stop-color:var(--color-accent)]" stopOpacity="0.3" />
              <stop offset="100%" className="[stop-color:var(--color-accent)]" stopOpacity="0" />
            </linearGradient>
          </defs>
          <polyline
            points={sparklinePoints}
            fill="none"
            className="[stroke:var(--color-accent)]"
            strokeWidth="1.5"
          />
          <polygon
            points={`0,${SPARKLINE_HEIGHT} ${sparklinePoints} ${SPARKLINE_WIDTH},${SPARKLINE_HEIGHT}`}
            fill={`url(#gradient-${symbol})`}
          />
        </svg>
      )}
    </div>
  );
}

export default function MarketTickerBanner() {
  const { data, isError } = useMarketIndices();

  return (
    <div className="h-[60px] bg-bg-primary border-b border-accent/25 flex items-center" role="region" aria-label="Market indices ticker">
      <IndexCard name="S&P 500" symbol="sp500" data={data?.sp500} isError={isError} />

      <div className="h-8 w-px bg-border" />

      <IndexCard name="Russell 2000" symbol="rut" data={data?.russell2000} isError={isError} />

      <div className="h-8 w-px bg-border" />

      <IndexCard name="VIX" symbol="vix" data={data?.vix} isError={isError} />
    </div>
  );
}
