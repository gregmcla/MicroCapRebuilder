/** Mini sparkline for position rows - 20-day price history */

import { useMemo } from "react";
import { useChartData } from "../hooks/useChartData";

// Constants for dimensions
const WIDTH = 60;
const HEIGHT = 30;
const PADDING = 5;

interface PositionRowSparklineProps {
  ticker: string;
}

function PositionRowSparkline({ ticker }: PositionRowSparklineProps) {
  const { data, isLoading, error } = useChartData(ticker, "20D");

  console.log(`Sparkline ${ticker}:`, {
    isLoading,
    error: error?.message,
    hasData: !!data,
    dataLength: data?.data?.length,
    dataKeys: data ? Object.keys(data) : [],
    actualData: data
  });

  // Calculate sparkline points
  const points = useMemo(() => {
    if (!data || data.data.length === 0) return null;

    const prices = data.data.map((d) => d.close);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const range = maxPrice - minPrice;

    // Handle flat prices (range === 0)
    if (range === 0) {
      const centerY = HEIGHT / 2;
      return prices.map((_, i) => {
        const x = (i / (prices.length - 1)) * WIDTH;
        return `${x},${centerY}`;
      }).join(' ');
    }

    return prices.map((price, i) => {
      const x = (i / (prices.length - 1)) * WIDTH;
      const y = HEIGHT - ((price - minPrice) / range) * (HEIGHT - PADDING * 2) - PADDING;
      return `${x},${y}`;
    }).join(' ');
  }, [data]);

  // Loading state
  if (isLoading) {
    return (
      <div className="w-[60px] h-[30px] bg-bg-surface rounded animate-pulse" />
    );
  }

  // Error state
  if (error) {
    return (
      <div className="w-[60px] h-[30px] bg-bg-surface rounded opacity-40" />
    );
  }

  // No data state
  if (!points) {
    return (
      <div className="w-[60px] h-[30px] bg-bg-surface rounded opacity-40" />
    );
  }

  return (
    <svg
      width={WIDTH}
      height={HEIGHT}
      className="opacity-80 group-hover:opacity-100 transition-opacity"
      role="img"
      aria-label={`20-day price history for ${ticker}`}
    >
      <defs>
        <linearGradient id={`sparkline-${ticker}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#22D3EE" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#22D3EE" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={points}
        fill="none"
        stroke="#22D3EE"
        strokeWidth="1.5"
        className="drop-shadow-[0_0_1px_rgba(34,211,238,0.4)]"
      />
      <polygon
        points={`0,${HEIGHT} ${points} ${WIDTH},${HEIGHT}`}
        fill={`url(#sparkline-${ticker})`}
      />
    </svg>
  );
}

export default PositionRowSparkline;
