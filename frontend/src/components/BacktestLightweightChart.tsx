import {
    AreaSeries,
    createSeriesMarkers,
    type HistogramData,
    HistogramSeries,
    type IChartApi,
    type ISeriesApi,
    type LineData,
    type MouseEventParams,
    type SeriesMarker,
    type Time,
} from 'lightweight-charts';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useUIPreferencesStore } from '../store/uiPreferences';
import { createTradingChart } from './charts/lightweightTheme';

export interface BacktestChartPoint {
  time: string;
  value: number;
  pnl: number;
  trades: number;
}

export interface BacktestChartMarker {
  time: string;
  pair: string;
  pnl: number;
  count?: number;
}

interface BacktestLightweightChartProps {
  data: BacktestChartPoint[];
  markers?: BacktestChartMarker[];
  height?: number;
  title?: string;
  resetKey?: string;
}

const toBusinessDay = (value: string): string => value.slice(0, 10);

const formatSignedCurrency = (value: number): string => {
  const sign = value >= 0 ? '+' : '-';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
};

const formatDateLabel = (value: string): string => {
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
};

export const BacktestLightweightChart: React.FC<BacktestLightweightChartProps> = ({
  data,
  markers = [],
  height = 420,
  title = 'Portfolio Equity',
  resetKey,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const areaSeriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const histogramSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const markerApiRef = useRef<ReturnType<typeof createSeriesMarkers<Time>> | null>(null);
  const latestDataRef = useRef<BacktestChartPoint[]>([]);
  const hasFittedContentRef = useRef(false);
  const [hoverPoint, setHoverPoint] = useState<BacktestChartPoint | null>(null);
  const resolvedTheme = useUIPreferencesStore((state) => state.resolvedTheme);

  const normalizedData = useMemo(() => {
    const byDay = new Map<string, BacktestChartPoint>();
    data.forEach((point) => {
      if (!Number.isFinite(point.value)) {
        return;
      }
      const time = toBusinessDay(point.time);
      byDay.set(time, {
        time,
        value: point.value,
        pnl: point.pnl,
        trades: point.trades,
      });
    });
    return Array.from(byDay.values()).sort((a, b) => a.time.localeCompare(b.time));
  }, [data]);

  const normalizedMarkers = useMemo<SeriesMarker<Time>[]>(() => {
    const byDay = new Map<string, BacktestChartMarker[]>();
    markers.forEach((marker) => {
      const time = toBusinessDay(marker.time);
      const current = byDay.get(time) || [];
      current.push({ ...marker, time });
      byDay.set(time, current);
    });

    return Array.from(byDay.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([time, grouped]) => {
        const netPnl = grouped.reduce((sum, item) => sum + item.pnl, 0);
        const count = grouped.reduce((sum, item) => sum + (item.count || 1), 0);
        const primaryPair = grouped[0]?.pair || 'Pair';
        return {
          time,
          position: netPnl >= 0 ? 'aboveBar' : 'belowBar',
          shape: netPnl >= 0 ? 'arrowUp' : 'arrowDown',
          color: netPnl >= 0 ? '#22c55e' : '#ef4444',
          text: count > 1 ? `${count}T` : primaryPair.split('/')[0] || 'T',
        };
      });
  }, [markers]);

  useEffect(() => {
    latestDataRef.current = normalizedData;
    setHoverPoint(normalizedData[normalizedData.length - 1] ?? null);
  }, [normalizedData]);

  useEffect(() => {
    hasFittedContentRef.current = false;
  }, [resetKey]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const chart = createTradingChart(container, height, {
      leftPriceScale: {
        visible: true,
      },
    });

    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor: '#38bdf8',
      topColor: 'rgba(56, 189, 248, 0.28)',
      bottomColor: 'rgba(56, 189, 248, 0.03)',
      priceLineColor: '#38bdf8',
      lastValueVisible: true,
      priceLineVisible: true,
    });
    areaSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.08,
        bottom: 0.34,
      },
    });

    const histogramSeries = chart.addSeries(HistogramSeries, {
      priceScaleId: 'left',
      color: 'rgba(148, 163, 184, 0.55)',
      priceFormat: { type: 'volume' },
    });
    histogramSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.74,
        bottom: 0,
      },
    });

    const markerApi = createSeriesMarkers(areaSeries, []);

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      const areaSeriesApi = areaSeriesRef.current;
      if (!areaSeriesApi || !param.time) {
        setHoverPoint(latestDataRef.current[latestDataRef.current.length - 1] ?? null);
        return;
      }

      const areaData = param.seriesData.get(areaSeriesApi) as LineData<Time> | undefined;
      const pointTime = areaData?.time ? String(areaData.time) : String(param.time);
      const matched = latestDataRef.current.find((point) => point.time === pointTime);
      setHoverPoint(matched ?? latestDataRef.current[latestDataRef.current.length - 1] ?? null);
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);

    const resizeObserver = new ResizeObserver((entries) => {
      const nextWidth = entries[0]?.contentRect.width;
      if (!nextWidth) {
        return;
      }
      chart.applyOptions({ width: nextWidth, height });
    });
    resizeObserver.observe(container);

    chartRef.current = chart;
    areaSeriesRef.current = areaSeries;
    histogramSeriesRef.current = histogramSeries;
    markerApiRef.current = markerApi;

    return () => {
      resizeObserver.disconnect();
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      markerApiRef.current = null;
      areaSeriesRef.current = null;
      histogramSeriesRef.current = null;
      chartRef.current = null;
      chart.remove();
    };
  }, [height, resolvedTheme]);

  useEffect(() => {
    const areaSeries = areaSeriesRef.current;
    const histogramSeries = histogramSeriesRef.current;
    const chart = chartRef.current;
    if (!areaSeries || !histogramSeries || !chart) {
      return;
    }

    const areaData: LineData<Time>[] = normalizedData.map((point) => ({
      time: point.time,
      value: point.value,
    }));
    const histogramData: HistogramData<Time>[] = normalizedData.map((point) => ({
      time: point.time,
      value: point.trades,
      color: point.pnl >= 0 ? 'rgba(34, 197, 94, 0.6)' : 'rgba(239, 68, 68, 0.6)',
    }));

    areaSeries.setData(areaData);
    histogramSeries.setData(histogramData);
    markerApiRef.current?.setMarkers(normalizedMarkers);
    if (!hasFittedContentRef.current) {
      chart.timeScale().fitContent();
      hasFittedContentRef.current = true;
    }
  }, [normalizedData, normalizedMarkers]);

  if (normalizedData.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-slate-700 bg-slate-900/40 text-sm text-slate-400"
        style={{ height }}
      >
        No equity data available yet.
      </div>
    );
  }

  const activePoint = hoverPoint ?? normalizedData[normalizedData.length - 1];

  if (!activePoint) return null;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/80">
      <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-xl border border-slate-800/90 bg-slate-950/85 px-3 py-2 backdrop-blur">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-300/80">
          {title}
        </p>
        <div className="mt-1 flex items-end gap-3">
          <span className="text-lg font-semibold text-slate-100">
            {formatSignedCurrency(activePoint.value)}
          </span>
          <span className="text-xs text-slate-400">
            {formatDateLabel(activePoint.time)} · {activePoint.trades} trades
          </span>
        </div>
      </div>
      <div className="pointer-events-none absolute right-4 top-4 z-10 rounded-xl border border-slate-800/90 bg-slate-950/85 px-3 py-2 text-right backdrop-blur">
        <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Daily PnL</p>
        <p
          className={`text-sm font-medium ${activePoint.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}
        >
          {formatSignedCurrency(activePoint.pnl)}
        </p>
      </div>
      <div ref={containerRef} style={{ height }} />
    </div>
  );
};

