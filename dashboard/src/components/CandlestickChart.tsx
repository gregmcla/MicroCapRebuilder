/** Candlestick chart with volume and entry/stop/target lines */

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  LineStyle,
  CandlestickSeries,
  HistogramSeries,
  type IChartApi,
} from "lightweight-charts";
import { useChartData } from "../hooks/useChartData";
import type { Position } from "../lib/types";

interface Props {
  ticker: string;
  range: string;
  position: Position;
  height?: number;
}

export default function CandlestickChart({ ticker, range, position, height }: Props) {
  const { data, isLoading, error } = useChartData(ticker, range);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || !data || data.data.length === 0) return;

    const resolvedHeight = height ?? (chartContainerRef.current.clientHeight || 300);

    // Create main chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#020617' },
        textColor: '#94A3B8',
      },
      grid: {
        vertLines: { color: 'rgba(148,163,184,0.04)' },
        horzLines: { color: 'rgba(148,163,184,0.04)' },
      },
      width: chartContainerRef.current.clientWidth,
      height: resolvedHeight,
      crosshair: {
        vertLine: {
          color: '#8B5CF6',
          width: 1,
          style: LineStyle.Dashed,
        },
        horzLine: {
          color: '#8B5CF6',
          width: 1,
          style: LineStyle.Dashed,
        },
      },
    });

    // Add candlestick series
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22C55E',
      downColor: '#EF4444',
      borderUpColor: '#22C55E',
      borderDownColor: '#EF4444',
      wickUpColor: '#22C55E',
      wickDownColor: '#EF4444',
    });

    // Prepare candle data - convert timestamp to UTCTimestamp (seconds)
    const candleData = data.data.map((d) => ({
      time: Math.floor(d.time) as any,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    candlestickSeries.setData(candleData);

    // Add volume series
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: 'rgba(34,197,94,0.4)',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    const volumeData = data.data.map((d, i) => ({
      time: Math.floor(d.time) as any,
      value: d.volume,
      color: candleData[i].close >= candleData[i].open ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)',
    }));

    volumeSeries.setData(volumeData);

    // Add entry price line
    candlestickSeries.createPriceLine({
      price: position.avg_cost_basis,
      color: '#F59E0B',
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: 'Entry',
    });

    // Add stop loss line
    candlestickSeries.createPriceLine({
      price: position.stop_loss,
      color: '#EF4444',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: 'Stop',
    });

    // Add take profit line
    candlestickSeries.createPriceLine({
      price: position.take_profit,
      color: '#10B981',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: 'Target',
    });

    chart.timeScale().fitContent();
    chartRef.current = chart;

    // Handle resize — update both width and height
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: height ?? (chartContainerRef.current.clientHeight || 300),
        });
      }
    };

    // ResizeObserver for container-driven sizing (when no explicit height)
    let ro: ResizeObserver | null = null;
    if (!height) {
      ro = new ResizeObserver(handleResize);
      ro.observe(chartContainerRef.current);
    }

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      ro?.disconnect();
      chart.remove();
    };
  }, [data, position, ticker, range, height]);

  if (isLoading) {
    return (
      <div className="w-full flex items-center justify-center bg-bg-surface rounded" style={{ height: height ?? 300 }}>
        <span className="text-text-muted animate-pulse">Loading chart...</span>
      </div>
    );
  }

  if (error || !data || data.data.length === 0) {
    return (
      <div className="w-full flex items-center justify-center bg-bg-surface rounded" style={{ height: height ?? 300 }}>
        <span className="text-text-muted">No chart data available</span>
      </div>
    );
  }

  return <div ref={chartContainerRef} className="w-full h-full" />;
}
