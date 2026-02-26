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
}

export default function CandlestickChart({ ticker, range, position }: Props) {
  const { data, isLoading, error } = useChartData(ticker, range);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || !data || data.data.length === 0) return;

    // Create main chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#000000' },
        textColor: '#FFFFFF',
      },
      grid: {
        vertLines: { color: 'rgba(0, 212, 136, 0.1)' },
        horzLines: { color: 'rgba(0, 212, 136, 0.1)' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 300,
      crosshair: {
        vertLine: {
          color: '#00D488',
          width: 1,
          style: LineStyle.Dashed,
        },
        horzLine: {
          color: '#00D488',
          width: 1,
          style: LineStyle.Dashed,
        },
      },
    });

    // Add candlestick series
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10B981',
      downColor: '#EF4444',
      borderUpColor: '#10B981',
      borderDownColor: '#EF4444',
      wickUpColor: '#10B981',
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
      color: '#26a69a',
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
      color: candleData[i].close >= candleData[i].open ? '#10B981' : '#EF4444',
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

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data, position, ticker, range]);

  if (isLoading) {
    return (
      <div className="w-full h-[300px] flex items-center justify-center bg-bg-surface rounded">
        <span className="text-text-muted animate-pulse">Loading chart...</span>
      </div>
    );
  }

  if (error || !data || data.data.length === 0) {
    return (
      <div className="w-full h-[300px] flex items-center justify-center bg-bg-surface rounded">
        <span className="text-text-muted">No chart data available</span>
      </div>
    );
  }

  return <div ref={chartContainerRef} className="w-full" />;
}
