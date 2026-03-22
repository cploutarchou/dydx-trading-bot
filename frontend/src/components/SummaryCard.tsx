/**
 * Summary Card Component - Task 19
 *
 * High-level summary of backtest run:
 * - Status and timestamps
 * - Total trade count
 * - Date range tested
 * - Configuration used
 */

import React, { useEffect, useState } from 'react';
import apiClient from '../api';

interface SummaryData {
  run_id: string;
  status: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  total_trades: number;
  earliest_trade_date?: string;
  latest_trade_date?: string;
  configuration: {
    num_pairs: number;
    zscore_threshold: number;
    stats_window: number;
    usd_per_trade: number;
  };
}

interface SummaryCardProps {
  runId: string;
}

export const SummaryCard: React.FC<SummaryCardProps> = ({ runId }) => {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSummary();
  }, [runId]);

  const fetchSummary = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getBacktestSummary(runId);
      if (response.success && response.data) {
        setSummary(response.data as unknown as SummaryData);
      } else {
        setError(response.message || 'Failed to load summary');
      }
    } catch (err: any) {
      setError(err.message || 'Error loading summary');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) {
      return 'N/A';
    }
    const date = new Date(dateString);
    return (
      date.toLocaleDateString() +
      ' ' +
      date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    );
  };

  const formatDateRange = (start: string, end: string) => {
    const startDate = new Date(start);
    const endDate = new Date(end);
    return `${startDate.toLocaleDateString()} to ${endDate.toLocaleDateString()}`;
  };

  if (loading) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-700 rounded w-1/3"></div>
          <div className="space-y-3">
            <div className="h-4 bg-slate-700 rounded"></div>
            <div className="h-4 bg-slate-700 rounded"></div>
            <div className="h-4 bg-slate-700 rounded"></div>
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

  if (!summary) {
    return <div className="text-gray-400">No summary data available</div>;
  }

  const statusColorClass =
    {
      completed: 'text-green-400 bg-green-900 bg-opacity-50',
      running: 'text-yellow-400 bg-yellow-900 bg-opacity-50',
      failed: 'text-red-400 bg-red-900 bg-opacity-50',
    }[summary.status.toLowerCase()] || 'text-gray-400 bg-gray-900 bg-opacity-50';

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 space-y-6">
      {/* Header with Status */}
      <div>
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-2xl font-bold text-white">Backtest Summary</h2>
            <p className="text-gray-400 text-sm mt-1">Run ID: {summary.run_id}</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${statusColorClass}`}>
            {summary.status.charAt(0).toUpperCase() + summary.status.slice(1)}
          </span>
        </div>
      </div>

      {/* Timestamps */}
      <div className="border-t border-slate-700 pt-4">
        <h3 className="text-sm font-bold text-gray-300 uppercase mb-3">Execution Timeline</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between text-gray-400">
            <span>Created:</span>
            <span className="text-white font-mono">{formatDate(summary.created_at)}</span>
          </div>
          <div className="flex justify-between text-gray-400">
            <span>Started:</span>
            <span className="text-white font-mono">{formatDate(summary.started_at)}</span>
          </div>
          <div className="flex justify-between text-gray-400">
            <span>Completed:</span>
            <span className="text-white font-mono">{formatDate(summary.completed_at)}</span>
          </div>
        </div>
      </div>

      {/* Trade Information */}
      <div className="border-t border-slate-700 pt-4">
        <h3 className="text-sm font-bold text-gray-300 uppercase mb-3">Trade Information</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-xs">Total Trades</p>
            <p className="text-2xl font-bold text-blue-400 mt-1">{summary.total_trades}</p>
          </div>
          <div className="p-3 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-xs">Date Range Tested</p>
            <p className="text-sm font-mono text-white mt-1">
              {summary.earliest_trade_date && summary.latest_trade_date
                ? formatDateRange(summary.earliest_trade_date, summary.latest_trade_date)
                : 'N/A'}
            </p>
          </div>
        </div>
      </div>

      {/* Configuration */}
      <div className="border-t border-slate-700 pt-4">
        <h3 className="text-sm font-bold text-gray-300 uppercase mb-3">Configuration</h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="p-3 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-xs">Pairs Analyzed</p>
            <p className="text-lg font-bold text-white mt-1">{summary.configuration.num_pairs}</p>
          </div>
          <div className="p-3 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-xs">Z-Score Threshold</p>
            <p className="text-lg font-bold text-white mt-1">
              ±{summary.configuration.zscore_threshold.toFixed(1)}
            </p>
          </div>
          <div className="p-3 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-xs">Stats Window</p>
            <p className="text-lg font-bold text-white mt-1">
              {summary.configuration.stats_window} days
            </p>
          </div>
          <div className="p-3 bg-slate-700 rounded-lg border border-slate-600">
            <p className="text-gray-400 text-xs">USD Per Trade</p>
            <p className="text-lg font-bold text-white mt-1">
              ${summary.configuration.usd_per_trade.toFixed(0)}
            </p>
          </div>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-900 bg-opacity-50 border border-blue-700 rounded-lg p-3">
        <p className="text-blue-300 text-xs">
          📊 This backtest analyzed {summary.configuration.num_pairs} market pairs over{' '}
          {summary.total_trades} trades using the configured strategy parameters.
        </p>
      </div>
    </div>
  );
};

export default SummaryCard;
