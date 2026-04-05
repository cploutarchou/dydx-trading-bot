/**
 * Strategy Manager Component
 *
 * Manages multiple strategies with:
 * - List of active strategies
 * - Enable/Disable toggles (async, non-blocking)
 * - Status indicators (running, stopped, error)
 * - Parameter editing modal
 * - Run backtest button
 * - Thread-safe execution
 */

import {
    AlertCircle,
    AlertTriangle,
    BarChart3,
    Copy,
    Settings,
    Trash2,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api';
import { Strategy, useStrategyStore } from '../store/strategies';
import { PageContainer } from './PageContainer';

interface StrategyStatus {
  strategyId: number;
  status: 'stopped' | 'starting' | 'running' | 'stopping' | 'paused' | 'error';
  lastError?: string;
  tradesExecuted?: number;
  pnl?: number;
  updatedAt: string;
  botStatus?: string;
  instanceId?: string;
  network?: string;
}

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error) return error.message;
  if (typeof error === 'object' && error !== null) {
    const err = error as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    return err.response?.data?.detail || err.message || fallback;
  }
  return fallback;
};

export default function StrategyManager() {
  const navigate = useNavigate();
  const { strategies, fetchStrategies, loading, duplicateStrategy, deleteStrategy } = useStrategyStore();
  const [strategyStatuses, setStrategyStatuses] = useState<Map<number, StrategyStatus>>(new Map());
  const [runtimePending, setRuntimePending] = useState<Record<number, 'start' | 'stop' | undefined>>({});
  const [editingConfig, setEditingConfig] = useState<Partial<Strategy> | null>(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configErrors, setConfigErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [webSocketConnected, setWebSocketConnected] = useState(false);
  const [runningCount, setRunningCount] = useState(0);

  // Load strategies on mount
  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  const applyStrategyStatuses = (nextStatuses: StrategyStatus[]) => {
    setStrategyStatuses(() => {
      const nextMap = new Map<number, StrategyStatus>();
      nextStatuses.forEach((status) => {
        nextMap.set(status.strategyId, status);
      });
      const running = nextStatuses.filter((status) => status.status === 'running').length;
      setRunningCount(running);
      return nextMap;
    });
  };

  const mergeStrategyStatus = (nextStatus: StrategyStatus) => {
    setStrategyStatuses((prev) => {
      const nextMap = new Map(prev);
      nextMap.set(nextStatus.strategyId, nextStatus);
      const running = Array.from(nextMap.values()).filter((status) => status.status === 'running').length;
      setRunningCount(running);
      return nextMap;
    });
  };

  const toStrategyStatus = (strategyId: number, runtimeData: Record<string, unknown> | undefined): StrategyStatus => {
    const normalizedStatus = typeof runtimeData?.status === 'string' ? runtimeData.status.toLowerCase() : 'stopped';
    const status =
      normalizedStatus === 'running' ||
      normalizedStatus === 'starting' ||
      normalizedStatus === 'stopping' ||
      normalizedStatus === 'paused' ||
      normalizedStatus === 'error'
        ? normalizedStatus
        : 'stopped';

    return {
      strategyId,
      status,
      lastError: typeof runtimeData?.last_error === 'string' ? runtimeData.last_error : undefined,
      updatedAt:
        typeof runtimeData?.last_synced_at === 'string'
          ? runtimeData.last_synced_at
          : typeof runtimeData?.updated_at === 'string'
            ? runtimeData.updated_at
            : new Date().toISOString(),
      botStatus: typeof runtimeData?.bot_status === 'string' ? runtimeData.bot_status : undefined,
      instanceId: typeof runtimeData?.instance_id === 'string' ? runtimeData.instance_id : undefined,
      network: typeof runtimeData?.network === 'string' ? runtimeData.network : undefined,
    };
  };

  useEffect(() => {
    if (strategies.length === 0) {
      applyStrategyStatuses([]);
      return;
    }

    let cancelled = false;

    const syncStrategyRuntimeStatuses = async () => {
      const settledStatuses = await Promise.allSettled(
        strategies.map(async (strategy) => {
          const response = await apiClient.getStrategyRuntime(strategy.id);
          return toStrategyStatus(strategy.id, response.data);
        })
      );

      if (cancelled) {
        return;
      }

      const nextStatuses = settledStatuses.map((result, index) => {
        if (result.status === 'fulfilled') {
          return result.value;
        }

        return {
          strategyId: strategies[index].id,
          status: 'error' as const,
          lastError: getErrorMessage(result.reason, 'Failed to load runtime status'),
          updatedAt: new Date().toISOString(),
        };
      });

      applyStrategyStatuses(nextStatuses);
    };

    void syncStrategyRuntimeStatuses();
    const intervalId = window.setInterval(() => {
      void syncStrategyRuntimeStatuses();
    }, 15000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [strategies]);

  // Setup WebSocket for real-time strategy status
  useEffect(() => {
    let ws: WebSocket | null = null;

    const connectWebSocket = () => {
      try {
        const token = localStorage.getItem('access_token');
        if (!token) return;

        // Use centralized api helper to build WebSocket URL
        ws = apiClient.connectSocket ? apiClient.connectSocket('/ws/strategies', token) : null;

        if (!ws) return;

        ws.onopen = () => {
          setWebSocketConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const update: StrategyStatus = JSON.parse(event.data);
            setStrategyStatuses((prev) => {
              const newMap = new Map(prev);
              newMap.set(update.strategyId, update);
              // Count running strategies
              const running = Array.from(newMap.values()).filter(
                (s: StrategyStatus) => s.status === 'running'
              ).length;
              setRunningCount(running);
              return newMap;
            });
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        ws.onerror = () => {
          setWebSocketConnected(false);
        };

        ws.onclose = () => {
          setWebSocketConnected(false);
          setTimeout(() => connectWebSocket(), 5000);
        };
      } catch (error) {
        console.error('Failed to connect WebSocket:', error);
      }
    };

    connectWebSocket();

    return () => {
      if (ws) ws.close();
    };
  }, []);

  const showTransientMessage = (nextMessage: { type: 'success' | 'error'; text: string }, timeoutMs: number) => {
    setMessage(nextMessage);
    setTimeout(() => setMessage(null), timeoutMs);
  };

  const handleRuntimeToggle = async (strategy: Strategy) => {
    const currentStatus = strategyStatuses.get(strategy.id);
    const shouldStop = currentStatus?.status === 'running' || currentStatus?.status === 'starting';

    setRuntimePending((prev) => ({
      ...prev,
      [strategy.id]: shouldStop ? 'stop' : 'start',
    }));

    mergeStrategyStatus({
      strategyId: strategy.id,
      status: shouldStop ? 'stopping' : 'starting',
      lastError: undefined,
      updatedAt: new Date().toISOString(),
      instanceId: currentStatus?.instanceId,
      network: currentStatus?.network,
      botStatus: shouldStop ? 'stopping' : 'starting',
    });

    try {
      const response = shouldStop
        ? await apiClient.stopStrategyRuntime(strategy.id)
        : await apiClient.startStrategyRuntime(strategy.id);

      mergeStrategyStatus(toStrategyStatus(strategy.id, response.data));
      showTransientMessage(
        {
          type: 'success',
          text: shouldStop
            ? `✅ Stopped strategy "${strategy.name}"`
            : `✅ Started strategy "${strategy.name}"`,
        },
        4000
      );
    } catch (error: unknown) {
      mergeStrategyStatus({
        strategyId: strategy.id,
        status: 'error',
        lastError: getErrorMessage(error, 'Failed to update strategy runtime'),
        updatedAt: new Date().toISOString(),
        instanceId: currentStatus?.instanceId,
        network: currentStatus?.network,
      });
      showTransientMessage(
        {
          type: 'error',
          text: shouldStop
            ? `❌ Failed to stop strategy: ${getErrorMessage(error, 'Unknown error')}`
            : `❌ Failed to start strategy: ${getErrorMessage(error, 'Unknown error')}`,
        },
        6000
      );
    } finally {
      setRuntimePending((prev) => ({
        ...prev,
        [strategy.id]: undefined,
      }));
    }
  };

  const validateConfig = (): boolean => {
    if (!editingConfig) return false;

    const errors: Record<string, string> = {};

    if (editingConfig.zscore_threshold && editingConfig.zscore_threshold < 0.1) {
      errors.zscore_threshold = 'Z-score threshold must be > 0.1';
    }

    if (editingConfig.usd_per_trade && editingConfig.usd_per_trade < 1) {
      errors.usd_per_trade = 'USD per trade must be >= $1';
    }

    if (editingConfig.max_drawdown_pct && editingConfig.max_drawdown_pct > 100) {
      errors.max_drawdown_pct = 'Max drawdown cannot exceed 100%';
    }

    setConfigErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSaveConfig = async () => {
    if (!editingConfig || !editingConfig.id || !validateConfig()) {
      return;
    }

    try {
      const updatePayload = {
        name: editingConfig.name || 'Untitled Strategy',
        description: editingConfig.description,
        zscore_threshold: editingConfig.zscore_threshold,
        max_half_life: editingConfig.max_half_life,
        usd_per_trade: editingConfig.usd_per_trade,
      };
      await apiClient.updateStrategy(editingConfig.id, updatePayload);

      showTransientMessage({ type: 'success', text: '✅ Strategy configuration updated' }, 4000);

      setShowConfigModal(false);
      setEditingConfig(null);
      await fetchStrategies();
    } catch (error: unknown) {
      showTransientMessage(
        {
          type: 'error',
          text: `❌ Failed to save configuration: ${getErrorMessage(error, 'Unknown error')}`,
        },
        6000
      );
    }
  };

  const handleEditConfig = (strategy: Strategy) => {
    setEditingConfig({ ...strategy });
    setConfigErrors({});
    setShowConfigModal(true);
  };

  const handleRunBacktest = async (strategy: Strategy) => {
    try {
      const endDate = new Date();
      const startDate = new Date(endDate);
      startDate.setDate(startDate.getDate() - 30);

      const response = await apiClient.runBacktest({
        strategy_id: strategy.id,
        start_date: startDate.toISOString().split('T')[0],
        end_date: endDate.toISOString().split('T')[0],
      });

      const runId = response.data?.run_id;
      if (response.success || runId) {
        showTransientMessage(
          {
            type: 'success',
            text: `✅ Backtest started for "${strategy.name}"`,
          },
          4000
        );
        if (typeof runId === 'string' && runId.length > 0) {
          navigate(`/backtest/${runId}`);
        }
      }
    } catch (error: unknown) {
      showTransientMessage(
        {
          type: 'error',
          text: `❌ Failed to start backtest: ${getErrorMessage(error, 'Unknown error')}`,
        },
        6000
      );
    }
  };

  const handleDuplicateStrategy = async (strategy: Strategy) => {
    try {
      await duplicateStrategy(strategy);
      showTransientMessage(
        { type: 'success', text: `✅ Duplicated strategy "${strategy.name}"` },
        4000
      );
    } catch (error: unknown) {
      showTransientMessage(
        {
          type: 'error',
          text: `❌ Failed to duplicate strategy: ${getErrorMessage(error, 'Unknown error')}`,
        },
        6000
      );
    }
  };

  const handleDeleteStrategy = async (strategy: Strategy) => {
    if (!window.confirm(`Delete strategy "${strategy.name}"? This cannot be undone.`)) {
      return;
    }

    try {
      await deleteStrategy(strategy.id);
      showTransientMessage(
        { type: 'success', text: `✅ Deleted strategy "${strategy.name}"` },
        4000
      );
    } catch (error: unknown) {
      showTransientMessage(
        {
          type: 'error',
          text: `❌ Failed to delete strategy: ${getErrorMessage(error, 'Unknown error')}`,
        },
        6000
      );
    }
  };

  const getStatusColor = (status: StrategyStatus['status']) => {
    switch (status) {
      case 'running':
        return 'text-green-400';
      case 'starting':
      case 'stopping':
      case 'paused':
        return 'text-yellow-400';
      case 'error':
        return 'text-red-400';
      default:
        return 'text-gray-400';
    }
  };

  const getStatusBg = (status: StrategyStatus['status']) => {
    switch (status) {
      case 'running':
        return 'bg-green-900/30 border-green-700';
      case 'starting':
      case 'stopping':
      case 'paused':
        return 'bg-yellow-900/30 border-yellow-700';
      case 'error':
        return 'bg-red-900/30 border-red-700';
      default:
        return 'bg-slate-700/30 border-slate-600';
    }
  };

  if (loading) {
    return (
      <PageContainer size="wide" className="flex h-96 items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-400">Loading strategies...</p>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer size="wide" className="space-y-6">
      {/* Header */}
      <div className="bg-linear-to-r from-slate-900 to-slate-800 rounded-lg border border-slate-700 p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white">🎯 Strategy Manager</h1>
            <p className="text-gray-400 mt-2">Run and manage multiple strategies simultaneously</p>
          </div>
          <div className="text-left sm:text-right">
            <div className="text-4xl font-bold text-green-400">{runningCount}</div>
            <div className="text-sm text-gray-400">Active Strategies</div>
          </div>
        </div>
      </div>

      {/* WebSocket Status */}
      <div
        className={`p-3 rounded-lg border ${
          webSocketConnected
            ? 'bg-green-900/20 border-green-700 text-green-200'
            : 'bg-yellow-900/20 border-yellow-700 text-yellow-200'
        }`}
      >
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${webSocketConnected ? 'bg-green-400' : 'bg-yellow-400'}`}
          />
          {webSocketConnected ? '✅ Real-time updates enabled' : '⏳ Connecting...'}
        </div>
      </div>

      <div className="p-4 rounded-lg border bg-blue-900/20 border-blue-700 text-blue-200">
        Runtime control is live through the backend strategy execution service.
        An active dYdX key is still required before a strategy can start, and statuses are reconciled every 15 seconds.
      </div>

      {/* Messages */}
      {message && (
        <div
          className={`p-4 rounded-lg border ${
            message.type === 'success'
              ? 'bg-green-900/30 border-green-700 text-green-200'
              : 'bg-red-900/30 border-red-700 text-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Strategies List */}
      <div className="space-y-4">
        {strategies.length === 0 ? (
          <div className="bg-slate-800 rounded-lg border border-slate-700 p-8 text-center">
            <AlertCircle className="w-12 h-12 text-gray-500 mx-auto mb-4" />
            <p className="text-gray-400 text-lg">No strategies available</p>
          </div>
        ) : (
          strategies.map((strategy) => {
            const status = strategyStatuses.get(strategy.id) || {
              strategyId: strategy.id,
              status: 'stopped' as const,
              updatedAt: new Date().toISOString(),
            };

            return (
              <div
                key={strategy.id}
                className={`bg-slate-800 rounded-lg border transition-all duration-300 p-6 ${
                  status.status === 'running'
                    ? 'border-green-600 shadow-lg shadow-green-900/50'
                    : 'border-slate-700'
                }`}
              >
                {/* Strategy Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-xl font-bold text-white">{strategy.name}</h3>
                      <span className="px-3 py-1 bg-slate-700 text-slate-300 text-xs rounded-full">
                        {strategy.category}
                      </span>
                    </div>
                    <p className="text-gray-400 text-sm mt-1">{strategy.description}</p>
                  </div>

                  {/* Status Badge */}
                  <div
                    className={`px-4 py-2 rounded-lg border ${getStatusBg(status.status)} flex items-center gap-2`}
                  >
                    <div
                      className={`w-2 h-2 rounded-full ${
                        status.status === 'running'
                          ? 'bg-green-400 animate-pulse'
                          : status.status === 'starting' || status.status === 'stopping'
                            ? 'bg-yellow-400 animate-pulse'
                          : status.status === 'error'
                            ? 'bg-red-400'
                            : 'bg-gray-400'
                      }`}
                    />
                    <span className={`text-sm font-medium ${getStatusColor(status.status)}`}>
                      {status.status.toUpperCase()}
                    </span>
                  </div>
                </div>

                {/* Error Display */}
                {status.lastError && (
                  <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg flex gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-red-200 text-sm font-medium">Error</p>
                      <p className="text-red-300 text-xs mt-1">{status.lastError}</p>
                    </div>
                  </div>
                )}

                {/* Key Parameters */}
                <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="bg-slate-900/50 rounded p-3">
                    <p className="text-gray-400 text-xs">Z-Score Threshold</p>
                    <p className="text-white font-semibold">{strategy.zscore_threshold}</p>
                  </div>
                  <div className="bg-slate-900/50 rounded p-3">
                    <p className="text-gray-400 text-xs">USD Per Trade</p>
                    <p className="text-white font-semibold">${strategy.usd_per_trade}</p>
                  </div>
                  <div className="bg-slate-900/50 rounded p-3">
                    <p className="text-gray-400 text-xs">Max Positions</p>
                    <p className="text-white font-semibold">{strategy.max_positions}</p>
                  </div>
                  <div className="bg-slate-900/50 rounded p-3">
                    <p className="text-gray-400 text-xs">Max Drawdown</p>
                    <p className="text-white font-semibold">{strategy.max_drawdown_pct}%</p>
                  </div>
                </div>

                {/* Stats */}
                {status.tradesExecuted !== undefined && (
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    <div className="bg-blue-900/20 border border-blue-700 rounded p-3">
                      <p className="text-blue-300 text-xs">Trades</p>
                      <p className="text-blue-100 font-bold text-lg">{status.tradesExecuted}</p>
                    </div>
                    <div
                      className={`border rounded p-3 ${
                        status.pnl && status.pnl > 0
                          ? 'bg-green-900/20 border-green-700'
                          : 'bg-red-900/20 border-red-700'
                      }`}
                    >
                      <p
                        className={status.pnl && status.pnl > 0 ? 'text-green-300' : 'text-red-300'}
                      >
                        P&L
                      </p>
                      <p
                        className={`font-bold text-lg ${
                          status.pnl && status.pnl > 0 ? 'text-green-100' : 'text-red-100'
                        }`}
                      >
                        {status.pnl ? `$${status.pnl.toFixed(2)}` : '-'}
                      </p>
                    </div>
                    <div className="bg-slate-700/20 border border-slate-600 rounded p-3">
                      <p className="text-slate-300 text-xs">Last Updated</p>
                      <p className="text-slate-100 font-mono text-sm">
                        {new Date(status.updatedAt).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex flex-wrap gap-2">
                  {/* Toggle Button */}
                  {(() => {
                    const pendingAction = runtimePending[strategy.id];
                    const isRunning = status.status === 'running' || status.status === 'starting';
                    const buttonLabel =
                      pendingAction === 'start'
                        ? 'Starting...'
                        : pendingAction === 'stop'
                          ? 'Stopping...'
                          : isRunning
                            ? 'Stop Strategy'
                            : 'Start Strategy';
                    const buttonClass =
                      pendingAction === 'start' || pendingAction === 'stop'
                        ? 'bg-slate-700 text-slate-200 cursor-wait'
                        : isRunning
                          ? 'bg-red-600 hover:bg-red-700 text-white'
                          : 'bg-green-600 hover:bg-green-700 text-white';

                    return (
                      <button
                        onClick={() => void handleRuntimeToggle(strategy)}
                        disabled={pendingAction !== undefined}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-80 disabled:cursor-not-allowed ${buttonClass}`}
                        title={
                          status.network
                            ? `Runtime network: ${status.network}`
                            : 'Requires an active dYdX key before startup'
                        }
                      >
                        {buttonLabel}
                      </button>
                    );
                  })()}

                  {/* Configure Button */}
                  <button
                    onClick={() => handleEditConfig(strategy)}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                  >
                    <Settings className="w-4 h-4" />
                    Configure
                  </button>

                  {/* Backtest Button */}
                  <button
                    onClick={() => handleRunBacktest(strategy)}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors"
                  >
                    <BarChart3 className="w-4 h-4" />
                    Backtest
                  </button>

                  {/* Copy Button */}
                  <button
                    onClick={() => void handleDuplicateStrategy(strategy)}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors"
                  >
                    <Copy className="w-4 h-4" />
                    Duplicate
                  </button>

                  {/* Delete Button */}
                  <button
                    onClick={() => void handleDeleteStrategy(strategy)}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-red-900/50 text-white rounded-lg font-medium transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Strategy Config Modal */}
      {showConfigModal && editingConfig && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-lg border border-slate-700 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="sticky top-0 bg-slate-800 border-b border-slate-700 p-6 flex items-center justify-between">
              <h2 className="text-2xl font-bold text-white">⚙️ Configure Strategy</h2>
              <button
                onClick={() => {
                  setShowConfigModal(false);
                  setEditingConfig(null);
                  setConfigErrors({});
                }}
                className="text-gray-400 hover:text-white text-2xl"
              >
                ✕
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-6">
              {/* Z-Score Threshold */}
              <div>
                <label className="block text-white font-medium mb-2">
                  Z-Score Threshold
                  {configErrors.zscore_threshold && (
                    <span className="text-red-400 text-sm ml-2">
                      • {configErrors.zscore_threshold}
                    </span>
                  )}
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="5"
                  value={editingConfig.zscore_threshold || 1.5}
                  onChange={(e) =>
                    setEditingConfig({
                      ...editingConfig,
                      zscore_threshold: parseFloat(e.target.value),
                    })
                  }
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-gray-400 text-xs mt-1">
                  Entry trigger when |Z-score| exceeds this
                </p>
              </div>

              {/* USD Per Trade */}
              <div>
                <label className="block text-white font-medium mb-2">
                  USD Per Trade
                  {configErrors.usd_per_trade && (
                    <span className="text-red-400 text-sm ml-2">
                      • {configErrors.usd_per_trade}
                    </span>
                  )}
                </label>
                <input
                  type="number"
                  step="1"
                  min="1"
                  value={editingConfig.usd_per_trade || 10}
                  onChange={(e) =>
                    setEditingConfig({
                      ...editingConfig,
                      usd_per_trade: parseFloat(e.target.value),
                    })
                  }
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-gray-400 text-xs mt-1">Position size per paired trade</p>
              </div>

              {/* Max Positions */}
              <div>
                <label className="block text-white font-medium mb-2">
                  Max Concurrent Positions
                </label>
                <input
                  type="number"
                  step="1"
                  min="1"
                  max="100"
                  value={editingConfig.max_positions || 5}
                  onChange={(e) =>
                    setEditingConfig({
                      ...editingConfig,
                      max_positions: parseInt(e.target.value),
                    })
                  }
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-gray-400 text-xs mt-1">Maximum open pair positions</p>
              </div>

              {/* Max Drawdown */}
              <div>
                <label className="block text-white font-medium mb-2">
                  Max Drawdown %
                  {configErrors.max_drawdown_pct && (
                    <span className="text-red-400 text-sm ml-2">
                      • {configErrors.max_drawdown_pct}
                    </span>
                  )}
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  value={editingConfig.max_drawdown_pct || 10}
                  onChange={(e) =>
                    setEditingConfig({
                      ...editingConfig,
                      max_drawdown_pct: parseFloat(e.target.value),
                    })
                  }
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-gray-400 text-xs mt-1">
                  Stop if account drawdown exceeds this %
                </p>
              </div>

              {/* Take Profit */}
              <div>
                <label className="block text-white font-medium mb-2">Take Profit %</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  value={editingConfig.take_profit_pct || 5}
                  onChange={(e) =>
                    setEditingConfig({
                      ...editingConfig,
                      take_profit_pct: parseFloat(e.target.value),
                    })
                  }
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-gray-400 text-xs mt-1">Close position when P&L reaches this %</p>
              </div>

              {/* Buttons */}
              <div className="flex gap-3 pt-4 border-t border-slate-700">
                <button
                  onClick={handleSaveConfig}
                  className="flex-1 px-4 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors"
                >
                  ✅ Save Configuration
                </button>
                <button
                  onClick={() => {
                    setShowConfigModal(false);
                    setEditingConfig(null);
                    setConfigErrors({});
                  }}
                  className="flex-1 px-4 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
