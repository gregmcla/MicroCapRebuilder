/** Mini sparkline for position rows - 20-day price history */

import { useChartData } from "../hooks/useChartData";

export default function PositionRowSparkline({ ticker }: { ticker: string }) {
  const { data } = useChartData(ticker, "20D");

  if (!data || data.data.length === 0) {
    return <div className="w-[60px] h-[30px] bg-bg-surface rounded" />;
  }

  const prices = data.data.map((d: any) => d.close);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const range = maxPrice - minPrice || 1;

  const points = prices.map((price: number, i: number) => {
    const x = (i / (prices.length - 1)) * 60;
    const y = 30 - ((price - minPrice) / range) * 25;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width="60" height="30" className="opacity-80 group-hover:opacity-100 transition-opacity">
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
        points={`0,30 ${points} 60,30`}
        fill={`url(#sparkline-${ticker})`}
      />
    </svg>
  );
}
