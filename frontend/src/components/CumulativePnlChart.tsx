/**
 * CumulativePnlChart
 * Uses TradingView lightweight-charts v5 to render an interactive
 * cumulative-PnL area/line chart with dark theme styling.
 */

import { ColorType, createChart, LineSeries } from 'lightweight-charts';
import React, { useEffect, useRef } from 'react';

export interface PnlPoint {
  time: string; // "YYYY-MM-DD"
  value: number;
}

interface CumulativePnlChartProps {
  data: PnlPoint[];
  height?: number;
  positiveColor?: string;
  negativeColor?: string;
}

export const CumulativePnlChart: React.FC<CumulativePnlChartProps> = ({
  data,
  height = 300,
  positiveColor = '#22c55e',
  negativeColor = '#ef4444',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<any>(null);

  /* ── Mount: create chart and series ──────────────────────── */
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#94a3b8',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: {
        borderColor: '#334155',
        textColor: '#94a3b8',
      },
      timeScale: {
        borderColor: '#334155',
        timeVisible: true,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      width: container.clientWidth,
      height,
    });

    chartRef.current = chart;
    seriesRef.current = chart.addSeries(LineSeries, {
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    const handleResize = () => {
      if (container && chartRef.current) {
        chartRef.current.applyOptions({ width: container.clientWidth });
      }
    };

    const observer = new ResizeObserver(handleResize);
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height]); // intentionally omit data — handled by the second effect

  /* ── Update: push new data without recreating chart ──────── */
  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;

    if (data.length === 0) {
      series.setData([]);
      return;
    }

    const lastValue = data[data.length - 1].value;
    const color = lastValue >= 0 ? positiveColor : negativeColor;

    series.applyOptions({ color });
    series.setData(data);
    chart.timeScale().fitContent();
  }, [data, positiveColor, negativeColor]);

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-slate-500 text-sm italic"
        style={{ height }}
      >
        No completed backtests yet — run one to see your equity curve.
      </div>
    );
  }

  return <div ref={containerRef} style={{ width: '100%', height }} />;
};

