/**
 * ClickHouse Analytics Dashboard
 * Displays live analytics from ClickHouse read models served by
 * backend/internal/app/analytics_routes.go. Response parsing is centralized in
 * ./clickHouseAnalyticsModel so the page matches the backend envelopes exactly.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { BarChart3, Clock, Database, Loader2, PieChart, RefreshCw, TrendingUp } from 'lucide-react';
import api from '../api';
import { formatPct, formatSignedUsd } from '../utils/format';
import { useToastStore } from '../components/ErrorBoundary';
import {
  APIRequestSummaryRow,
  AnalyticsEnvelope,
  PairBreakdown,
  PositionSnapshot,
  TradeSummary,
  WorkerMetric,
  extractAPIRequestSummary,
  extractError,
  extractPairBreakdown,
  extractPositionSnapshots,
  extractTradeSummary,
  extractWorkerMetrics,
} from './clickHouseAnalyticsModel';

const ClickHouseAnalytics: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'positions' | 'trades' | 'pairs' | 'workers' | 'api'>(
    'positions'
  );
  const [instanceId, setInstanceId] = useState<string>('');
  const [hours, setHours] = useState<number>(24);
  const [loading, setLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // Data states
  const [positionHistory, setPositionHistory] = useState<PositionSnapshot[]>([]);
  const [tradeSummary, setTradeSummary] = useState<TradeSummary | null>(null);
  const [pairBreakdown, setPairBreakdown] = useState<PairBreakdown[]>([]);
  const [workerMetrics, setWorkerMetrics] = useState<WorkerMetric[]>([]);
  const [apiSummary, setApiSummary] = useState<APIRequestSummaryRow[]>([]);

  // Error states
  const [positionError, setPositionError] = useState<string | null>(null);
  const [tradeError, setTradeError] = useState<string | null>(null);
  const [pairError, setPairError] = useState<string | null>(null);
  const [workerError, setWorkerError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  const { addToast } = useToastStore();

  const applyEnvelope = <T,>(
    env: AnalyticsEnvelope,
    setter: (value: T) => void,
    fallback: T,
    errorSetter: (msg: string | null) => void,
    extract: (env: AnalyticsEnvelope) => T
  ): boolean => {
    const err = extractError(env);
    if (err) {
      errorSetter(err);
      setter(fallback);
      return false;
    }
    errorSetter(null);
    setter(extract(env));
    return true;
  };

  const fetchData = useCallback(async () => {
    if (!instanceId && activeTab !== 'workers' && activeTab !== 'api') {
      addToast({ type: 'warning', title: 'Warning', message: 'Please enter an instance ID' });
      return;
    }

    setLoading(true);
    setRefreshing(true);

    try {
      if (activeTab === 'positions') {
        const env = (await api.getClickHousePositionHistory(
          instanceId,
          hours
        )) as unknown as AnalyticsEnvelope;
        applyEnvelope<PositionSnapshot[]>(
          env,
          setPositionHistory,
          [],
          setPositionError,
          extractPositionSnapshots
        );
      } else if (activeTab === 'trades') {
        const env = (await api.getClickHouseTradeSummary(
          instanceId
        )) as unknown as AnalyticsEnvelope;
        applyEnvelope<TradeSummary | null>(
          env,
          setTradeSummary,
          null,
          setTradeError,
          extractTradeSummary
        );
      } else if (activeTab === 'pairs') {
        const env = (await api.getClickHousePairBreakdown(
          instanceId
        )) as unknown as AnalyticsEnvelope;
        applyEnvelope<PairBreakdown[]>(
          env,
          setPairBreakdown,
          [],
          setPairError,
          extractPairBreakdown
        );
      } else if (activeTab === 'workers') {
        const env = (await api.getClickHouseWorkerMetrics(
          undefined,
          undefined,
          hours
        )) as unknown as AnalyticsEnvelope;
        applyEnvelope<WorkerMetric[]>(
          env,
          setWorkerMetrics,
          [],
          setWorkerError,
          extractWorkerMetrics
        );
      } else if (activeTab === 'api') {
        const env = (await api.getClickHouseAPIRequestSummary()) as unknown as AnalyticsEnvelope;
        applyEnvelope<APIRequestSummaryRow[]>(
          env,
          setApiSummary,
          [],
          setApiError,
          extractAPIRequestSummary
        );
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      if (activeTab === 'positions') setPositionError(errorMessage);
      else if (activeTab === 'trades') setTradeError(errorMessage);
      else if (activeTab === 'pairs') setPairError(errorMessage);
      else if (activeTab === 'workers') setWorkerError(errorMessage);
      else if (activeTab === 'api') setApiError(errorMessage);
      addToast({
        type: 'error',
        title: 'Error',
        message: `Failed to fetch ${activeTab} data: ${errorMessage}`,
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [instanceId, hours, activeTab, addToast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const winRate = (winning: number, losing: number): number => {
    const decided = winning + losing;
    return decided > 0 ? (winning / decided) * 100 : 0;
  };

  const renderPositionHistory = () => {
    if (loading && !positionHistory.length) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      );
    }
    if (positionError) {
      return (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          <p>{positionError}</p>
          <p className="text-sm mt-2">
            ClickHouse may be disabled or the instance has no position history.
          </p>
        </div>
      );
    }
    if (!positionHistory.length) {
      return (
        <div className="text-center py-12 text-slate-400">
          <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No position history found for this instance</p>
        </div>
      );
    }
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {positionHistory.map((position) => (
            <div
              key={`${position.position_id}-${position.snapshot_time}`}
              className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50"
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <p className="text-sm font-medium text-slate-300">
                    {position.pair1}/{position.pair2}
                  </p>
                  <p className="text-xs text-slate-500 truncate">{position.position_id}</p>
                </div>
                <StatusBadge status={position.status} />
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-slate-400">Entry Price 1</p>
                  <p className="text-white">{position.entry_price1.toFixed(4)}</p>
                </div>
                <div>
                  <p className="text-slate-400">Entry Price 2</p>
                  <p className="text-white">{position.entry_price2.toFixed(4)}</p>
                </div>
                <div>
                  <p className="text-slate-400">Size 1</p>
                  <p className="text-white">{position.entry_size1}</p>
                </div>
                <div>
                  <p className="text-slate-400">Size 2</p>
                  <p className="text-white">{position.entry_size2}</p>
                </div>
                <div className="col-span-2">
                  <p className="text-slate-400">Unrealized P&amp;L</p>
                  <p
                    className={`text-lg ${position.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
                  >
                    {formatSignedUsd(position.unrealized_pnl)} (
                    {formatPct(position.unrealized_pnl_pct, 2)})
                  </p>
                </div>
                <div className="col-span-2">
                  <p className="text-slate-400">Snapshot Time</p>
                  <p className="text-white">{new Date(position.snapshot_time).toLocaleString()}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderTradeSummary = () => {
    if (loading && !tradeSummary) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      );
    }
    if (tradeError) {
      return (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          <p>{tradeError}</p>
          <p className="text-sm mt-2">
            ClickHouse may be disabled or the instance has no trade data.
          </p>
        </div>
      );
    }
    if (!tradeSummary) {
      return (
        <div className="text-center py-12 text-slate-400">
          <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No trade summary found for this instance</p>
        </div>
      );
    }
    const totals = tradeSummary.totals;
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <MetricCard label="Trade Events" value={String(totals.trade_events)} />
          <MetricCard
            label="Opened"
            value={String(totals.trades_opened)}
            valueClass="text-blue-400"
          />
          <MetricCard label="Closed" value={String(totals.trades_closed)} />
          <MetricCard
            label="Winning"
            value={String(totals.winning_trades)}
            valueClass="text-green-400"
          />
          <MetricCard
            label="Losing"
            value={String(totals.losing_trades)}
            valueClass="text-red-400"
          />
          <MetricCard
            label="Win Rate"
            value={`${winRate(totals.winning_trades, totals.losing_trades).toFixed(1)}%`}
            valueClass="text-green-400"
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
            <p className="text-slate-400 text-sm mb-2">Total Realized P&amp;L</p>
            <p
              className={`text-3xl font-bold ${totals.total_realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
            >
              {formatSignedUsd(totals.total_realized_pnl)}
            </p>
            <p className="text-slate-500 text-sm mt-2">
              Realized P&amp;L %: {formatPct(totals.total_realized_pnl_pct, 2)}
            </p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
            <p className="text-slate-400 text-sm mb-2">Order Events</p>
            <p className="text-3xl font-bold text-yellow-400">{tradeSummary.order_events}</p>
          </div>
        </div>
      </div>
    );
  };

  const renderPairBreakdown = () => {
    if (loading && !pairBreakdown.length) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      );
    }
    if (pairError) {
      return (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          <p>{pairError}</p>
          <p className="text-sm mt-2">
            ClickHouse may be disabled or the instance has no pair data.
          </p>
        </div>
      );
    }
    if (!pairBreakdown.length) {
      return (
        <div className="text-center py-12 text-slate-400">
          <PieChart className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No pair breakdown found for this instance</p>
        </div>
      );
    }
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {pairBreakdown.map((pair, index) => (
            <div
              key={`${pair.pair1}-${pair.pair2}-${index}`}
              className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50"
            >
              <div className="flex justify-between items-center mb-4">
                <p className="text-lg font-semibold text-white">
                  {pair.pair1}/{pair.pair2}
                </p>
                <p
                  className={`text-sm ${pair.total_realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
                >
                  {formatSignedUsd(pair.total_realized_pnl)}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-slate-400">Closed Trades</p>
                  <p className="text-white">{pair.trades_closed}</p>
                </div>
                <div>
                  <p className="text-slate-400">Avg P&amp;L %</p>
                  <p className="text-white">{formatPct(pair.avg_realized_pnl_pct, 2)}</p>
                </div>
                <div>
                  <p className="text-slate-400">Win Rate</p>
                  <p className="text-white">
                    {winRate(pair.winning_trades, pair.losing_trades).toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderWorkerMetrics = () => {
    if (loading && !workerMetrics.length) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      );
    }
    if (workerError) {
      return (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          <p>{workerError}</p>
          <p className="text-sm mt-2">
            ClickHouse may be disabled or no worker metrics producer is configured.
          </p>
        </div>
      );
    }
    if (!workerMetrics.length) {
      return (
        <div className="text-center py-12 text-slate-400">
          <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No worker metrics available</p>
        </div>
      );
    }
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {workerMetrics.map((metric, index) => (
            <div
              key={`${metric.worker_id}-${metric.metric_name}-${index}`}
              className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50"
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <p className="text-sm font-medium text-slate-300">{metric.worker_type}</p>
                  <p className="text-xs text-slate-500 truncate">{metric.worker_id}</p>
                </div>
                <p className="text-xs text-slate-400">{metric.queue_name}</p>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-slate-400">Metric</p>
                  <p className="text-white">{metric.metric_name}</p>
                </div>
                <div>
                  <p className="text-slate-400">Value</p>
                  <p className="text-white">{metric.metric_value.toFixed(2)}</p>
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                {new Date(metric.metric_time).toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderAPIRequestSummary = () => {
    if (loading && !apiSummary.length) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      );
    }
    if (apiError) {
      return (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          <p>{apiError}</p>
          <p className="text-sm mt-2">
            ClickHouse may be disabled or API request analytics is not configured.
          </p>
        </div>
      );
    }
    if (!apiSummary.length) {
      return (
        <div className="text-center py-12 text-slate-400">
          <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No API request summary available</p>
        </div>
      );
    }
    const totals = apiSummary.reduce(
      (acc, row) => {
        acc.requests += row.request_count;
        acc.errors += row.error_count;
        return acc;
      },
      { requests: 0, errors: 0 }
    );
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Total Requests" value={totals.requests.toLocaleString()} />
          <MetricCard
            label="Total Errors"
            value={totals.errors.toLocaleString()}
            valueClass="text-red-400"
          />
          <MetricCard label="Routes" value={String(apiSummary.length)} />
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700/50">
                <th className="py-2 pr-4">Method</th>
                <th className="py-2 pr-4">Route</th>
                <th className="py-2 pr-4 text-right">Requests</th>
                <th className="py-2 pr-4 text-right">Avg Latency (ms)</th>
                <th className="py-2 pr-4 text-right">Errors</th>
                <th className="py-2 pr-4 text-right">Rate Limited</th>
              </tr>
            </thead>
            <tbody>
              {apiSummary.map((row, index) => (
                <tr
                  key={`${row.method}-${row.route}-${index}`}
                  className="border-b border-slate-800/50"
                >
                  <td className="py-2 pr-4 text-slate-300">{row.method}</td>
                  <td className="py-2 pr-4 text-white">{row.route}</td>
                  <td className="py-2 pr-4 text-right text-white">
                    {row.request_count.toLocaleString()}
                  </td>
                  <td className="py-2 pr-4 text-right text-white">
                    {row.avg_latency_ms.toFixed(0)}
                  </td>
                  <td className="py-2 pr-4 text-right text-red-400">
                    {row.error_count.toLocaleString()}
                  </td>
                  <td className="py-2 pr-4 text-right text-slate-400">{row.rate_limited}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const StatusBadge = ({ status }: { status: string }) => {
    const statusClasses: Record<string, string> = {
      OPEN: 'bg-green-500/20 text-green-400 border border-green-500/30',
      CLOSED: 'bg-slate-500/20 text-slate-400 border border-slate-500/30',
      LIVE: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
      FAILED: 'bg-red-500/20 text-red-400 border border-red-500/30',
      ERROR: 'bg-red-500/20 text-red-400 border border-red-500/30',
    };
    const key = (status || '').toUpperCase();
    const className =
      statusClasses[key] || 'bg-slate-500/20 text-slate-400 border border-slate-500/30';
    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-md ${className}`}>{status}</span>
    );
  };

  const MetricCard = ({
    label,
    value,
    valueClass = 'text-white',
  }: {
    label: string;
    value: string;
    valueClass?: string;
  }) => (
    <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
      <p className="text-slate-400 text-sm">{label}</p>
      <p className={`text-2xl font-bold ${valueClass}`}>{value}</p>
    </div>
  );

  const renderContent = () => {
    switch (activeTab) {
      case 'positions':
        return renderPositionHistory();
      case 'trades':
        return renderTradeSummary();
      case 'pairs':
        return renderPairBreakdown();
      case 'workers':
        return renderWorkerMetrics();
      case 'api':
        return renderAPIRequestSummary();
      default:
        return renderPositionHistory();
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white">
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center space-x-3">
            <Database className="h-8 w-8 text-blue-400" />
            <div>
              <h2 className="text-2xl font-bold">ClickHouse Analytics</h2>
              <p className="text-sm text-slate-400">Live analytical data from ClickHouse</p>
            </div>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-800/50 disabled:cursor-not-allowed rounded-lg border border-slate-700/50 transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Controls */}
        <div className="bg-slate-800/50 rounded-lg p-4 mb-6 border border-slate-700/50">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-1">
              <label
                className="block text-sm font-medium text-slate-400 mb-2"
                htmlFor="instance-id"
              >
                Instance ID
              </label>
              <input
                id="instance-id"
                type="text"
                value={instanceId}
                onChange={(e) => setInstanceId(e.target.value)}
                placeholder="Enter bot instance ID"
                disabled={activeTab === 'workers' || activeTab === 'api'}
                className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white placeholder:text-slate-500 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              />
            </div>
            <div className="md:col-span-1">
              <label
                className="block text-sm font-medium text-slate-400 mb-2"
                htmlFor="time-range-hours"
              >
                Time Range (hours)
              </label>
              <select
                id="time-range-hours"
                value={hours}
                onChange={(e) => setHours(Number(e.target.value))}
                disabled={activeTab === 'workers' || activeTab === 'api' || activeTab === 'trades'}
                className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              >
                <option value={1}>1 hour</option>
                <option value={6}>6 hours</option>
                <option value={12}>12 hours</option>
                <option value={24}>24 hours</option>
                <option value={48}>48 hours</option>
                <option value={72}>72 hours</option>
                <option value={168}>7 days</option>
              </select>
            </div>
            <div className="md:col-span-1">
              <label className="block text-sm font-medium text-slate-400 mb-2" htmlFor="data-type">
                Data Type
              </label>
              <select
                id="data-type"
                value={activeTab}
                onChange={(e) => setActiveTab(e.target.value as typeof activeTab)}
                className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              >
                <option value="positions">Position History</option>
                <option value="trades">Trade Summary</option>
                <option value="pairs">Pair Breakdown</option>
                <option value="workers">Worker Metrics</option>
                <option value="api">API Requests</option>
              </select>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="bg-slate-800/50 rounded-lg border border-slate-700/50">
          {renderContent()}
        </div>
      </div>
    </div>
  );
};

export default ClickHouseAnalytics;
