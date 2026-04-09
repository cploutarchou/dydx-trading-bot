/**
 * CumulativePnlChart
 * Responsive cumulative-PnL chart with a reliable SVG renderer.
 */

import React, { useId, useMemo } from 'react';
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

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
  const gradientId = useId().replace(/:/g, '-');

  const normalizedData = useMemo(
    () =>
      [...data]
        .filter((point) => Number.isFinite(point.value) && typeof point.time === 'string')
        .sort((a, b) => a.time.localeCompare(b.time))
        .map((point) => ({
          ...point,
          label: new Date(`${point.time}T00:00:00`).toLocaleDateString([], {
            month: 'short',
            day: 'numeric',
          }),
        })),
    [data]
  );

  const lastValue = normalizedData[normalizedData.length - 1]?.value ?? 0;
  const strokeColor = lastValue >= 0 ? positiveColor : negativeColor;
  const values = normalizedData.map((point) => point.value);
  const minValue = values.length > 0 ? Math.min(...values, 0) : 0;
  const maxValue = values.length > 0 ? Math.max(...values, 0) : 0;
  const valuePadding = Math.max((maxValue - minValue) * 0.15, 100);
  const yDomain: [number, number] = [minValue - valuePadding, maxValue + valuePadding];

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

  return (
    <div style={{ width: '100%' }}>
      <ResponsiveContainer width="100%" height={height} minWidth={280} minHeight={220}>
        <AreaChart data={normalizedData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={strokeColor} stopOpacity={0.35} />
              <stop offset="100%" stopColor={strokeColor} stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            stroke="#64748b"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            stroke="#64748b"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={72}
            domain={yDomain}
            tickFormatter={(value: number) => `$${Math.round(value).toLocaleString('en-US')}`}
          />
          <ReferenceLine y={0} stroke="#334155" strokeDasharray="4 4" />
          <Tooltip
            contentStyle={{
              backgroundColor: '#0f172a',
              border: '1px solid #334155',
              borderRadius: '0.75rem',
              color: '#e2e8f0',
            }}
            labelStyle={{ color: '#cbd5e1', marginBottom: '0.25rem' }}
            formatter={(value: unknown) => {
              const numericValue = Number(value ?? 0);
              return [
                `${numericValue >= 0 ? '+' : '-'}$${Math.abs(numericValue).toLocaleString('en-US', {
                  maximumFractionDigits: 2,
                })}`,
                'Cumulative P&L',
              ];
            }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={strokeColor}
            strokeWidth={3}
            fill={`url(#${gradientId})`}
            isAnimationActive={false}
            activeDot={{ r: 5, stroke: strokeColor, strokeWidth: 2, fill: '#0f172a' }}
            dot={normalizedData.length <= 2 ? { r: 3, fill: strokeColor, strokeWidth: 0 } : false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

