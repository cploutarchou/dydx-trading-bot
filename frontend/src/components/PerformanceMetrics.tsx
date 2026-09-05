/**
 * Performance Metrics Component - Task 19
 *
 * Displays comprehensive performance analytics for a backtest:
 * - Win rate, trade counts, PnL metrics
 * - Risk metrics (Sharpe ratio, max drawdown)
 * - Trade duration statistics
 */

import React from 'react';
import { useBacktestMetrics } from '../api/hooks';

interface PerformanceData {
  run_id: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  average_pnl: number;
  max_win: number;
  max_loss: number;
  sharpe_ratio: number;
  max_drawdown: number;
  average_duration: number;
}

interface PerformanceMetricsProps {
  runId: string;
}

type MetricCardProps = {
  label: string;
  value: string | number;
  unit?: string;
  highlight?: boolean;
};

const MetricCard: React.FC<MetricCardProps> = ({ label, value, unit, highlight = false }) => (
  <div
    className={`p-4 rounded-lg border ${highlight ? 'bg-blue-900 border-blue-700' : 'bg-slate-700 border-slate-600'}`}
  >
    <p className="text-gray-400 text-sm font-medium">{label}</p>
    <p className={`text-2xl font-bold mt-2 ${highlight ? 'text-blue-400' : 'text-white'}`}>
      {value}
      {unit && <span className="text-lg ml-1">{unit}</span>}
    </p>
  </div>
);

export const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({ runId }) => {
  const performanceQuery = useBacktestMetrics(runId);
  const metrics = performanceQuery.data as unknown as PerformanceData | undefined;
  const loading = performanceQuery.isLoading;
  const error =
    performanceQuery.error instanceof Error
      ? performanceQuery.error.message
      : performanceQuery.isError
        ? 'Failed to load performance metrics'
        : null;

  if (loading) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-slate-700 rounded w-1/4"></div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-20 bg-slate-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{error}</div>
    );
  }

  if (!metrics) {
    return <div className="text-gray-400">No performance data available</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Performance Metrics</h2>
        <p className="text-gray-400">Comprehensive analytics for this backtest run</p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Total Trades" value={metrics.total_trades} highlight />
        <MetricCard label="Winning Trades" value={metrics.winning_trades} />
        <MetricCard label="Losing Trades" value={metrics.losing_trades} />
        <MetricCard label="Win Rate" value={metrics.win_rate.toFixed(1)} unit="%" />
      </div>

      {/* Profitability Metrics */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h3 className="text-lg font-bold text-white mb-4">Profitability</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-sm">Total P&L</p>
            <p
              className={`text-2xl font-bold mt-2 ${metrics.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
            >
              ${metrics.total_pnl.toFixed(2)}
            </p>
          </div>
          <div className="p-4 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-sm">Average P&L per Trade</p>
            <p
              className={`text-2xl font-bold mt-2 ${metrics.average_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
            >
              ${metrics.average_pnl.toFixed(2)}
            </p>
          </div>
          <div className="p-4 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-sm">Best Trade</p>
            <p className="text-2xl font-bold mt-2 text-green-400">${metrics.max_win.toFixed(2)}</p>
          </div>
        </div>
      </div>

      {/* Risk Metrics */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h3 className="text-lg font-bold text-white mb-4">Risk Analysis</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-sm">Worst Trade</p>
            <p className="text-2xl font-bold mt-2 text-red-400">${metrics.max_loss.toFixed(2)}</p>
          </div>
          <div className="p-4 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-sm">Max Drawdown</p>
            <p className="text-2xl font-bold mt-2 text-yellow-400">
              ${metrics.max_drawdown.toFixed(2)}
            </p>
          </div>
          <div className="p-4 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-sm">Sharpe Ratio</p>
            <p
              className={`text-2xl font-bold mt-2 ${metrics.sharpe_ratio >= 1 ? 'text-green-400' : 'text-yellow-400'}`}
            >
              {metrics.sharpe_ratio.toFixed(2)}
            </p>
          </div>
        </div>
        <div className="mt-4 text-xs text-gray-400">
          <p>📊 Sharpe Ratio &gt; 1: Good | &gt; 2: Excellent</p>
          <p>⚠️ Max Drawdown: Peak-to-trough decline during backtest</p>
        </div>
      </div>

      {/* Trade Duration */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h3 className="text-lg font-bold text-white mb-4">Trade Duration</h3>
        <div className="p-4 bg-slate-700 rounded-lg border border-slate-600">
          <p className="text-gray-400 text-sm">Average Duration</p>
          <p className="text-3xl font-bold mt-2 text-blue-400">
            {metrics.average_duration.toFixed(1)} hours
          </p>
        </div>
      </div>

      {/* Interpretation Guide */}
      <div className="bg-blue-900 bg-opacity-50 border border-blue-700 rounded-lg p-4">
        <h3 className="text-sm font-bold text-blue-300 mb-2">📈 How to Read These Metrics</h3>
        <ul className="text-xs text-blue-200 space-y-1">
          <li>
            • <strong>Win Rate:</strong> Percentage of profitable trades (higher is better)
          </li>
          <li>
            • <strong>Sharpe Ratio:</strong> Risk-adjusted return (higher is better, &gt;2 is
            excellent)
          </li>
          <li>
            • <strong>Max Drawdown:</strong> Largest peak-to-trough decline (lower is better)
          </li>
          <li>
            • <strong>Average Duration:</strong> How long positions are held on average
          </li>
        </ul>
      </div>
    </div>
  );
};

export default PerformanceMetrics;
