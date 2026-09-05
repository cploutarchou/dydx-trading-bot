import {
  AreaSeries,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type MouseEventParams,
  type Time,
} from 'lightweight-charts';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useUIPreferencesStore } from '../store/uiPreferences';
import { createTradingChart } from './charts/lightweightTheme';

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

export const CumulativePnlChart: React.FC<CumulativePnlChartProps> = ({
  data,
  height = 300,
  positiveColor = '#22c55e',
  negativeColor = '#ef4444',
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const areaSeriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const latestDataRef = useRef<PnlPoint[]>([]);
  const hasFittedContentRef = useRef(false);
  const [hoverPoint, setHoverPoint] = useState<PnlPoint | null>(null);
  const resolvedTheme = useUIPreferencesStore((state) => state.resolvedTheme);

  const normalizedData = useMemo(
    () =>
      [...data]
        .filter((point) => Number.isFinite(point.value) && typeof point.time === 'string')
        .sort((a, b) => a.time.localeCompare(b.time)),
    [data]
  );

  const lastValue = normalizedData[normalizedData.length - 1]?.value ?? 0;
  const strokeColor = lastValue >= 0 ? positiveColor : negativeColor;

  useEffect(() => {
    latestDataRef.current = normalizedData;
    setHoverPoint(normalizedData[normalizedData.length - 1] ?? null);
  }, [normalizedData]);

  useEffect(() => {
    hasFittedContentRef.current = false;
  }, [data]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const chart = createTradingChart(container, height, {
      leftPriceScale: { visible: false },
      rightPriceScale: { visible: true },
      timeScale: {
        timeVisible: false,
        secondsVisible: false,
      },
    });

    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor: strokeColor,
      topColor: `${strokeColor}55`,
      bottomColor: `${strokeColor}08`,
      lineWidth: 3,
      priceLineColor: strokeColor,
      lastValueVisible: true,
      priceLineVisible: true,
    });

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

    // autoSize:true (set via createTradingChart) owns the ResizeObserver internally —
    // no manual observer needed here.

    chartRef.current = chart;
    areaSeriesRef.current = areaSeries;

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      areaSeriesRef.current = null;
      chartRef.current = null;
      chart.remove();
    };
    // Initial series color is a snapshot; the applyOptions effect below keeps
    // it in sync, so a sign flip must not rebuild the whole chart.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [height, resolvedTheme]);

  useEffect(() => {
    const areaSeries = areaSeriesRef.current;
    if (!areaSeries) {
      return;
    }

    areaSeries.applyOptions({
      lineColor: strokeColor,
      topColor: `${strokeColor}55`,
      bottomColor: `${strokeColor}08`,
      priceLineColor: strokeColor,
    });
  }, [strokeColor]);

  useEffect(() => {
    const chart = chartRef.current;
    const areaSeries = areaSeriesRef.current;
    if (!chart || !areaSeries) {
      return;
    }

    const areaData: LineData<Time>[] = normalizedData.map((point) => ({
      time: point.time,
      value: point.value,
    }));

    areaSeries.setData(areaData);

    // fitContent after a rAF so autoSize has already set the real chart width.
    // Without this the chart draws into a zero-width viewport and appears blank.
    if (!hasFittedContentRef.current) {
      requestAnimationFrame(() => {
        chartRef.current?.timeScale().fitContent();
        hasFittedContentRef.current = true;
      });
    }
  }, [normalizedData]);

  if (normalizedData.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-slate-500 text-sm italic"
        style={{ height }}
      >
        No completed backtests yet — run one to see your equity curve.
      </div>
    );
  }

  const activePoint = hoverPoint ?? normalizedData[normalizedData.length - 1];

  if (!activePoint) return null;

  return (
    <div className="relative w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-950/80">
      <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-lg border border-slate-800/90 bg-slate-950/85 px-3 py-2 backdrop-blur">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-300/80">
          Cumulative P&amp;L
        </p>
        <div className="mt-1 flex items-end gap-3">
          <span
            className={`text-lg font-semibold ${activePoint.value >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}
          >
            {formatSignedCurrency(activePoint.value)}
          </span>
          <span className="text-xs text-slate-400">{formatDateLabel(activePoint.time)}</span>
        </div>
      </div>
      <div ref={containerRef} style={{ height }} />
    </div>
  );
};
