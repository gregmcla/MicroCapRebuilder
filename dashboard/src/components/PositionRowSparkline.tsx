/** Mini sparkline for position rows - 20-day price history */

import { useMemo } from "react";
import { useChartData } from "../hooks/useChartData";

// Constants for dimensions
const WIDTH = 60;
const PADDING = 2;

interface PositionRowSparklineProps {
  ticker: string;
  height?: number;
}

function PositionRowSparkline({ ticker, height = 30 }: PositionRowSparklineProps) {
  const HEIGHT = height;
  const { data, isLoading, error } = useChartData(ticker, "20D");

  // Calculate sparkline points
  const { linePoints, lastPoint } = useMemo(() => {
    if (!data || data.data.length === 0) return { linePoints: null, lastPoint: null };

    const prices = data.data.map((d) => d.close);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const range = maxPrice - minPrice;

    // Handle flat prices (range === 0)
    if (range === 0) {
      const centerY = HEIGHT / 2;
      const pts = prices.map((_, i) => {
        const x = prices.length > 1 ? (i / (prices.length - 1)) * WIDTH : WIDTH / 2;
        return `${x},${centerY}`;
      }).join(' ');
      const lastX = prices.length > 1 ? WIDTH : WIDTH / 2;
      return { linePoints: pts, lastPoint: { x: lastX, y: centerY } };
    }

    const coordPairs = prices.map((price, i) => {
      const x = prices.length > 1 ? (i / (prices.length - 1)) * WIDTH : WIDTH / 2;
      const y = HEIGHT - ((price - minPrice) / range) * (HEIGHT - PADDING * 2) - PADDING;
      return { x, y };
    });

    const pts = coordPairs.map(({ x, y }) => `${x},${y}`).join(' ');
    const last = coordPairs[coordPairs.length - 1];
    return { linePoints: pts, lastPoint: last };
  }, [data, HEIGHT]);

  // Unique gradient ID per ticker to avoid SVG ID conflicts
  const gradientId = `sparkline-grad-${ticker.replace(/[^a-zA-Z0-9]/g, '_')}`;

  // Loading state
  if (isLoading) {
    return (
      <div className="w-full bg-bg-surface rounded animate-pulse" style={{ height }} />
    );
  }

  // Error state
  if (error) {
    return (
      <div className="w-full bg-bg-surface rounded opacity-30 border border-loss/30" style={{ height }} />
    );
  }

  // No data state
  if (!linePoints || !lastPoint) {
    return (
      <div className="w-full bg-bg-surface rounded opacity-40" style={{ height }} />
    );
  }

  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      preserveAspectRatio="none"
      style={{ display: "block" }}
      className="opacity-70"
      role="img"
      gscott-label={`20-day price history for ${ticker}`}
    >
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="rgba(124,92,252,0.15)" stopOpacity="1" />
          <stop offset="100%" stopColor="rgba(124,92,252,0)" stopOpacity="1" />
        </linearGradient>
      </defs>
      {/* Filled area under the line */}
      <polygon
        points={`0,${HEIGHT} ${linePoints} ${WIDTH},${HEIGHT}`}
        fill={`url(#${gradientId})`}
      />
      {/* Sparkline stroke */}
      <polyline
        points={linePoints}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      {/* Last data point dot with glow */}
      <circle
        cx={lastPoint.x}
        cy={lastPoint.y}
        r={2}
        fill="var(--accent)"
        filter="drop-shadow(0 0 3px rgba(124,92,252,0.6))"
      />
    </svg>
  );
}

export default PositionRowSparkline;
