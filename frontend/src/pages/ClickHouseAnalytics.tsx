/**
 * ClickHouse Analytics Dashboard
 * Displays live analytics from ClickHouse read models
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  BarChart3,
  Clock,
  Database,
  Loader2,
  PieChart,
  RefreshCw,
  TrendingUp,
} from 'lucide-react';
import api from '../api';
import { useToastStore } from '../components/ErrorBoundary';

interface PositionSnapshot {
  position_id: string;
  bot_id: string;
  instance_id: string;
  snapshot_time: string;
  pair1: string;
  pair2: string;
  market: string;
  side1: string;
  side2: string;
  status: string;
  event_kind: string;
  entry_price1: number;
  entry_price2: number;
  current_price1: number | null;
  current_price2: number | null;
  entry_size1: number;
  entry_size2: number;
  current_size1: number | null;
  current_size2: number | null;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
  realized_pnl_pct: number;
  strategy_id: number | null;
  strategy_name: string;
  exchange_position_id: string;
  fee_accrued: number;
  leverage: number | null;
  margin_used: number | null;
}

interface TradeSummary {
  instance_id: string;
  bot_id: string;
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  winning_trades: number;
  losing_trades: number;
  total_pnl: number;
  avg_pnl: number;
  win_rate: number;
  total_fees: number;
  total_volume: number;
}

interface PairBreakdown {
  instance_id: string;
  pair1: string;
  pair2: string;
  trade_count: number;
  total_pnl: number;
  win_rate: number;
  avg_pnl: number;
}

interface WorkerMetrics {
  worker_id: string;
  worker_type: string;
  queue_name: string;
  metric_time: string;
  metric_name: string;
  metric_value: number;
}

interface APIRequestSummary {
  total_requests: number;
  success_count: number;
  error_count: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
}

const ClickHouseAnalytics: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'positions' | 'trades' | 'pairs' | 'workers' | 'api'>('positions');
  const [instanceId, setInstanceId] = useState<string>('');
  const [hours, setHours] = useState<number>(24);
  const [loading, setLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // Data states
  const [positionHistory, setPositionHistory] = useState<PositionSnapshot[]>([]);
  const [tradeSummary, setTradeSummary] = useState<TradeSummary | null>(null);
  const [pairBreakdown, setPairBreakdown] = useState<PairBreakdown[]>([]);
  const [workerMetrics, setWorkerMetrics] = useState<WorkerMetrics[]>([]);
  const [apiSummary, setApiSummary] = useState<APIRequestSummary | null>(null);

  // Error states
  const [positionError, setPositionError] = useState<string | null>(null);
  const [tradeError, setTradeError] = useState<string | null>(null);
  const [pairError, setPairError] = useState<string | null>(null);
  const [workerError, setWorkerError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  const { addToast } = useToastStore();

  const fetchData = useCallback(async () => {
    if (!instanceId && activeTab !== 'workers' && activeTab !== 'api') {
      addToast({ type: 'warning', title: 'Warning', message: 'Please enter an instance ID' });
      return;
    }

    setLoading(true);
    setRefreshing(true);

    try {
      if (activeTab === 'positions') {
        setPositionError(null);
        const response = await api.getClickHousePositionHistory(instanceId, hours);
        if (response.success && response.data) {
          setPositionHistory((response.data as { positions?: PositionSnapshot[] }).positions || []);
        } else {
          setPositionError(response.message || 'Failed to fetch position history');
        }
      } else if (activeTab === 'trades') {
        setTradeError(null);
        const response = await api.getClickHouseTradeSummary(instanceId);
        if (response.success && response.data) {
          setTradeSummary((response.data as { summary?: TradeSummary }).summary || null);
        } else {
          setTradeError(response.message || 'Failed to fetch trade summary');
        }
      } else if (activeTab === 'pairs') {
        setPairError(null);
        const response = await api.getClickHousePairBreakdown(instanceId);
        if (response.success && response.data) {
          setPairBreakdown((response.data as { breakdown?: PairBreakdown[] }).breakdown || []);
        } else {
          setPairError(response.message || 'Failed to fetch pair breakdown');
        }
      } else if (activeTab === 'workers') {
        setWorkerError(null);
        const response = await api.getClickHouseWorkerMetricsSummary();
        if (response.success && response.data) {
          setWorkerMetrics((response.data as { metrics?: WorkerMetrics[] }).metrics || []);
        } else {
          setWorkerError(response.message || 'Failed to fetch worker metrics');
        }
      } else if (activeTab === 'api') {
        setApiError(null);
        const response = await api.getClickHouseAPIRequestSummary();
        if (response.success && response.data) {
          setApiSummary((response.data as { summary?: APIRequestSummary }).summary || null);
        } else {
          setApiError(response.message || 'Failed to fetch API request summary');
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      if (activeTab === 'positions') setPositionError(errorMessage);
      else if (activeTab === 'trades') setTradeError(errorMessage);
      else if (activeTab === 'pairs') setPairError(errorMessage);
      else if (activeTab === 'workers') setWorkerError(errorMessage);
      else if (activeTab === 'api') setApiError(errorMessage);
      addToast({ type: 'error', title: 'Error', message: `Failed to fetch ${activeTab} data: ${errorMessage}` });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [instanceId, hours, activeTab, addToast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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
          <p className="text-sm mt-2">ClickHouse may be disabled or the instance has no position history.</p>
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
            <div key={`${position.position_id}-${position.snapshot_time}`} className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <p className="text-sm font-medium text-slate-300">{position.pair1}/{position.pair2}</p>
                  <p className="text-xs text-slate-500 truncate">{position.position_id}</p>
                </div>
                <StatusBadge status={position.status} />
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-slate-400">Entry Price 1</p>
                  <p className="text-white">${position.entry_price1.toFixed(4)}</p>
                </div>
                <div>
                  <p className="text-slate-400">Entry Price 2</p>
                  <p className="text-white">${position.entry_price2.toFixed(4)}</p>
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
                  <p className="text-slate-400">Unrealized P&L</p>
                  <p className={`text-lg ${position.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${position.unrealized_pnl.toFixed(2)} ({position.unrealized_pnl_pct.toFixed(2)}%)
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
          <p className="text-sm mt-2">ClickHouse may be disabled or the instance has no trade data.</p>
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

    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
            <p className="text-slate-400 text-sm">Total Trades</p>
            <p className="text-2xl font-bold text-white">{tradeSummary.total_trades}</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
            <p className="text-slate-400 text-sm">Open Trades</p>
            <p className="text-2xl font-bold text-blue-400">{tradeSummary.open_trades}</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
            <p className="text-slate-400 text-sm">Closed Trades</p>
            <p className="text-2xl font-bold text-slate-300">{tradeSummary.closed_trades}</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
            <p className="text-slate-400 text-sm">Winning Trades</p>
            <p className="text-2xl font-bold text-green-400">{tradeSummary.winning_trades}</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
            <p className="text-slate-400 text-sm">Losing Trades</p>
            <p className="text-2xl font-bold text-red-400">{tradeSummary.losing_trades}</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
            <p className="text-slate-400 text-sm">Win Rate</p>
            <p className="text-2xl font-bold text-green-400">{tradeSummary.win_rate.toFixed(1)}%</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
            <p className="text-slate-400 text-sm mb-2">Total P&L</p>
            <p className={`text-3xl font-bold ${tradeSummary.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${tradeSummary.total_pnl.toFixed(2)}
            </p>
            <p className="text-slate-500 text-sm mt-2">Avg P&L: ${tradeSummary.avg_pnl.toFixed(2)}</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
            <p className="text-slate-400 text-sm mb-2">Total Fees</p>
            <p className="text-3xl font-bold text-yellow-400">${tradeSummary.total_fees.toFixed(2)}</p>
            <p className="text-slate-500 text-sm mt-2">Total Volume: ${tradeSummary.total_volume.toFixed(2)}</p>
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
          <p className="text-sm mt-2">ClickHouse may be disabled or the instance has no pair data.</p>
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
            <div key={`${pair.pair1}-${pair.pair2}-${index}`} className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
              <div className="flex justify-between items-center mb-4">
                <p className="text-lg font-semibold text-white">{pair.pair1}/{pair.pair2}</p>
                <p className={`text-sm ${pair.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  ${pair.total_pnl.toFixed(2)}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-slate-400">Trades</p>
                  <p className="text-white">{pair.trade_count}</p>
                </div>
                <div>
                  <p className="text-slate-400">Avg P&L</p>
                  <p className="text-white">${pair.avg_pnl.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-slate-400">Win Rate</p>
                  <p className="text-white">{pair.win_rate.toFixed(1)}%</p>
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
          <p className="text-sm mt-2">ClickHouse may be disabled.</p>
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
            <div key={`${metric.worker_id}-${metric.metric_name}-${index}`} className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
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
              <p className="text-xs text-slate-500 mt-2">{new Date(metric.metric_time).toLocaleString()}</p>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderAPIRequestSummary = () => {
    if (loading && !apiSummary) {
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
          <p className="text-sm mt-2">ClickHouse may be disabled.</p>
        </div>
      );
    }

    if (!apiSummary) {
      return (
        <div className="text-center py-12 text-slate-400">
          <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No API request summary available</p>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
            <p className="text-slate-400 text-sm">Total Requests</p>
            <p className="text-2xl font-bold text-white">{apiSummary.total_requests.toLocaleString()}</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
            <p className="text-slate-400 text-sm">Success Rate</p>
            <p className="text-2xl font-bold text-green-400">
              {((apiSummary.success_count / apiSummary.total_requests) * 100).toFixed(1)}%
            </p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
            <p className="text-slate-400 text-sm">Avg Latency</p>
            <p className="text-2xl font-bold text-blue-400">{apiSummary.avg_latency_ms.toFixed(0)}ms</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 text-center border border-slate-700/50">
            <p className="text-slate-400 text-sm">P95 Latency</p>
            <p className="text-2xl font-bold text-purple-400">{apiSummary.p95_latency_ms.toFixed(0)}ms</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
            <p className="text-slate-400 text-sm mb-2">Errors</p>
            <p className="text-3xl font-bold text-red-400">{apiSummary.error_count.toLocaleString()}</p>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
            <p className="text-slate-400 text-sm mb-2">P99 Latency</p>
            <p className="text-3xl font-bold text-orange-400">{apiSummary.p99_latency_ms.toFixed(0)}ms</p>
          </div>
        </div>
      </div>
    );
  };

  const StatusBadge = ({ status }: { status: string }) => {
    const statusClasses = {
      OPEN: 'bg-green-500/20 text-green-400 border border-green-500/30',
      CLOSED: 'bg-slate-500/20 text-slate-400 border border-slate-500/30',
      LIVE: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
      FAILED: 'bg-red-500/20 text-red-400 border border-red-500/30',
      ERROR: 'bg-red-500/20 text-red-400 border border-red-500/30',
    };

    const className = statusClasses[status.toUpperCase() as keyof typeof statusClasses] ||
      'bg-slate-500/20 text-slate-400 border border-slate-500/30';

    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-md ${className}`}>
        {status}
      </span>
    );
  };

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
              <h1 className="text-2xl font-bold">ClickHouse Analytics</h1>
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
              <label className="block text-sm font-medium text-slate-400 mb-2">Instance ID</label>
              <input
                type="text"
                value={instanceId}
                onChange={(e) => setInstanceId(e.target.value)}
                placeholder="Enter bot instance ID"
                disabled={activeTab === 'workers' || activeTab === 'api'}
                className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white placeholder:text-slate-500 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              />
            </div>
            <div className="md:col-span-1">
              <label className="block text-sm font-medium text-slate-400 mb-2">Time Range (hours)</label>
              <select
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
              <label className="block text-sm font-medium text-slate-400 mb-2">Data Type</label>
              <select
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