/** Market ticker banner - S&P 500, Russell 2000, VIX with sparklines */

import { useMemo } from "react";
import { useMarketIndices } from "../hooks/useMarketIndices";
import type { MarketIndex } from "../lib/types";

// Constants for SVG dimensions (48×16 per spec)
const SPARKLINE_WIDTH = 48;
const SPARKLINE_HEIGHT = 16;
const SPARKLINE_PADDING = 2;

function IndexCard({
  name,
  data,
  isError
}: {
  name: string;
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
      <div className="flex items-center gap-2">
        <span
          className="uppercase font-sans text-[10px] tracking-[0.08em]"
          style={{ color: "var(--text-0)" }}
        >
          {name}
        </span>
        <span className="text-[10px]" style={{ color: "var(--red)" }}>Error</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center gap-2">
        <span
          className="uppercase font-sans text-[10px] tracking-[0.08em]"
          style={{ color: "var(--text-0)" }}
        >
          {name}
        </span>
        <span className="text-[10px]" style={{ color: "var(--text-0)" }}>—</span>
      </div>
    );
  }

  const isPositive = data.change_pct >= 0;
  const changeSign = isPositive ? "+" : "";
  const directionColor = isPositive ? "var(--green)" : "var(--red)";

  return (
    <div className="flex items-center gap-2">
      {/* Index name */}
      <span
        className="uppercase font-sans text-[10px] tracking-[0.08em]"
        style={{ color: "var(--text-0)" }}
      >
        {name}
      </span>

      {/* Price */}
      <span
        className="font-mono text-[12px] tabular-nums"
        style={{ color: "var(--text-3)" }}
      >
        {data.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>

      {/* Change % */}
      <span
        className="font-mono text-[10.5px] tabular-nums"
        style={{ color: directionColor }}
      >
        <span className="sr-only">Change: </span>
        {changeSign}{data.change_pct.toFixed(2)}%
      </span>

      {/* Sparkline — 48×16, no fill, stroke matches direction */}
      {data.sparkline.length > 0 && (
        <svg
          width={SPARKLINE_WIDTH}
          height={SPARKLINE_HEIGHT}
          role="img"
          gscott-label={`${name} intraday trend sparkline`}
        >
          <title>{`${name} price trend`}</title>
          <polyline
            points={sparklinePoints}
            fill="none"
            stroke={directionColor}
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      )}
    </div>
  );
}

export default function MarketTickerBanner() {
  const { data, isError } = useMarketIndices();

  return (
    <div
      className="h-9 flex items-center overflow-hidden shrink-0"
      style={{
        background: "var(--surface-0)",
        borderBottom: "1px solid var(--border-0)",
      }}
      role="region"
      gscott-label="Market indices ticker"
    >
      {/* Inner row: horizontally scrollable, centered, gap-[40px] */}
      <div className="flex items-center gap-[40px] px-4 w-full justify-center overflow-x-auto scrollbar-none">
        <IndexCard name="S&P 500" data={data?.sp500} isError={isError} />
        <IndexCard name="Russell 2000" data={data?.russell2000} isError={isError} />
        <IndexCard name="VIX" data={data?.vix} isError={isError} />
      </div>
    </div>
  );
}
