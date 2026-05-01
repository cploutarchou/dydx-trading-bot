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

import { AlertCircle, AlertTriangle, BarChart3, Copy, Settings, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import apiClient, { DYDX_CANDLE_RESOLUTION_OPTIONS, normalizeDydxCandleResolution } from '../api';
import { buildStrategyIntelRequest } from '../features/codex/marketIntel';
import { Strategy, useStrategyStore } from '../store/strategies';
import { AIRuntimeDigest } from './AIRuntimeDigest';
import { AIStrategyAdvisor } from './AIStrategyAdvisor';
import { CodexAssetIntelStrip } from './CodexAssetIntelStrip';
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
  runtimeSubaccount?: number;
  capitalAllocationUsd?: number;
}

interface StrategyStartReadiness {
  selected_runtime_network: 'testnet' | 'mainnet';
  selected_subaccount: number;
  configured_selected_markets?: string[];
  valid_selected_markets?: string[];
  key_exists: boolean;
  key_chain_address?: string;
  available_collateral: number;
  equity: number;
  open_positions: number;
  usd_per_trade: number;
  usd_min_collateral: number;
  capital_allocation_usd: number;
  trade_size_to_collateral_ratio?: number | null;
  sufficient_for_trade_size: boolean;
  sufficient_for_min_collateral: boolean;
  wallet_ready: boolean;
  account_exists: boolean;
  ready: boolean;
  blockers: string[];
  warnings: string[];
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

const RUNTIME_STRATEGY_OPTIONS = [
  { value: 'cointegration', label: 'Cointegration' },
  { value: 'mean_reversion', label: 'Mean Reversion' },
];

const needsRuntimeRecreateConfirmation = (message?: string): boolean => {
  const normalized = String(message || '').toLowerCase();
  return (
    normalized.includes('runtime instance missing from bot api') ||
    normalized.includes('instance_id already exists') ||
    normalized.includes('confirm recreate') ||
    normalized.includes('stale runtime instance detected')
  );
};

const hasExplicitMarketSelection = (readiness: StrategyStartReadiness | null): boolean => {
  const configuredMarkets = readiness?.configured_selected_markets;
  return Array.isArray(configuredMarkets) && configuredMarkets.length > 0;
};

export default function StrategyManager() {
  const navigate = useNavigate();
  const { strategies, fetchStrategies, loading, duplicateStrategy, deleteStrategy } =
    useStrategyStore();
  const safeStrategies = useMemo(
    () =>
      (Array.isArray(strategies) ? strategies : []).filter(
        (strategy): strategy is Strategy =>
          Boolean(strategy) && typeof strategy.id === 'number' && Number.isFinite(strategy.id)
      ),
    [strategies]
  );
  const [strategyStatuses, setStrategyStatuses] = useState<Map<number, StrategyStatus>>(new Map());
  const [runtimePending, setRuntimePending] = useState<
    Record<number, 'start' | 'stop' | undefined>
  >({});
  const [editingConfig, setEditingConfig] = useState<Partial<Strategy> | null>(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configErrors, setConfigErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [webSocketConnected, setWebSocketConnected] = useState(false);
  const [runningCount, setRunningCount] = useState(0);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [startDialogStrategy, setStartDialogStrategy] = useState<Strategy | null>(null);
  const [startDialogNetwork, setStartDialogNetwork] = useState<'testnet' | 'mainnet'>('testnet');
  const [startDialogLoading, setStartDialogLoading] = useState(false);
  const [startDialogSubmitting, setStartDialogSubmitting] = useState(false);
  const [startDialogError, setStartDialogError] = useState<string | null>(null);
  const [startDialogReadiness, setStartDialogReadiness] = useState<StrategyStartReadiness | null>(
    null
  );

  const updateEditingConfig = (patch: Partial<Strategy>) => {
    setEditingConfig((current) => (current ? { ...current, ...patch } : current));
  };

  // Load strategies on mount
  useEffect(() => {
    void fetchStrategies();
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
      const running = Array.from(nextMap.values()).filter(
        (status) => status.status === 'running'
      ).length;
      setRunningCount(running);
      return nextMap;
    });
  };

  const toStrategyStatus = (
    strategyId: number,
    runtimeData: Record<string, unknown> | undefined
  ): StrategyStatus => {
    const normalizedStatus =
      typeof runtimeData?.status === 'string' ? runtimeData.status.toLowerCase() : 'stopped';
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
      instanceId:
        typeof runtimeData?.instance_id === 'string' ? runtimeData.instance_id : undefined,
      network: typeof runtimeData?.network === 'string' ? runtimeData.network : undefined,
      runtimeSubaccount:
        typeof runtimeData?.runtime_subaccount === 'number'
          ? runtimeData.runtime_subaccount
          : undefined,
      capitalAllocationUsd:
        typeof runtimeData?.capital_allocation_usd === 'number'
          ? runtimeData.capital_allocation_usd
          : undefined,
    };
  };

  useEffect(() => {
    if (safeStrategies.length === 0) {
      applyStrategyStatuses([]);
      return;
    }

    let cancelled = false;

    const syncStrategyRuntimeStatuses = async () => {
      const settledStatuses = await Promise.allSettled(
        safeStrategies.map(async (strategy) => {
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
          strategyId: safeStrategies[index].id,
          status: 'error' as const,
          lastError: getErrorMessage(result.reason, 'Failed to load runtime status'),
          updatedAt: new Date().toISOString(),
        };
      });

      applyStrategyStatuses(nextStatuses);
    };

    void syncStrategyRuntimeStatuses();

    return () => {
      cancelled = true;
    };
  }, [safeStrategies]);

  useEffect(() => {
    if (!startDialogStrategy) {
      return;
    }

    let cancelled = false;
    const loadReadiness = async () => {
      setStartDialogLoading(true);
      setStartDialogError(null);
      try {
        const response = await apiClient.getStrategyStartReadiness(
          startDialogStrategy.id,
          startDialogNetwork
        );
        if (!cancelled) {
          setStartDialogReadiness(response.data as StrategyStartReadiness);
        }
      } catch (error) {
        if (!cancelled) {
          setStartDialogReadiness(null);
          setStartDialogError(getErrorMessage(error, 'Failed to load runtime readiness'));
        }
      } finally {
        if (!cancelled) {
          setStartDialogLoading(false);
        }
      }
    };

    void loadReadiness();

    return () => {
      cancelled = true;
    };
  }, [startDialogNetwork, startDialogStrategy]);

  // Setup WebSocket for real-time strategy status
  useEffect(() => {
    let ws: WebSocket | null = null;
    let disposed = false;
    let connectTimer: number | null = null;
    let reconnectTimer: number | null = null;
    let connectionGeneration = 0;

    const clearReconnectTimer = () => {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const teardownSocket = (socket: WebSocket | null) => {
      if (!socket) {
        return;
      }
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
    };

    const connectWebSocket = () => {
      if (disposed) return;
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return;
      }

      try {
        clearReconnectTimer();
        const generation = ++connectionGeneration;

        const socket = apiClient.connectStrategyRuntimeSocket
          ? apiClient.connectStrategyRuntimeSocket()
          : null;
        ws = socket;

        if (!socket) return;

        socket.onopen = () => {
          if (disposed || generation !== connectionGeneration || ws !== socket) {
            teardownSocket(socket);
            return;
          }
          setWebSocketConnected(true);
          clearReconnectTimer();
        };

        socket.onmessage = (event) => {
          if (disposed || generation !== connectionGeneration || ws !== socket) {
            return;
          }
          try {
            const payload = JSON.parse(event.data) as {
              type?: string;
              strategyId?: number;
              status?: string;
              data?: Array<Record<string, unknown>>;
            };

            if (payload.type === 'strategy_status_snapshot' && Array.isArray(payload.data)) {
              const snapshotStatuses = payload.data
                .filter(
                  (item): item is Record<string, unknown> =>
                    typeof item?.strategyId === 'number' && typeof item?.status === 'string'
                )
                .map((item) => toStrategyStatus(item.strategyId as number, item));

              if (snapshotStatuses.length > 0) {
                applyStrategyStatuses(snapshotStatuses);
              }
              return;
            }

            if (typeof payload.strategyId === 'number' && typeof payload.status === 'string') {
              mergeStrategyStatus(
                toStrategyStatus(payload.strategyId, payload as Record<string, unknown>)
              );
            }
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        socket.onerror = () => {
          if (disposed || generation !== connectionGeneration || ws !== socket) {
            return;
          }
          setWebSocketConnected(false);
        };

        socket.onclose = () => {
          if (generation !== connectionGeneration || ws !== socket) {
            return;
          }
          ws = null;
          setWebSocketConnected(false);
          if (disposed) return;
          clearReconnectTimer();
          reconnectTimer = window.setTimeout(() => connectWebSocket(), 5000);
        };
      } catch (error) {
        console.error('Failed to connect WebSocket:', error);
      }
    };

    // Delay the initial connect by one tick so React StrictMode's dev-only
    // mount/unmount cycle doesn't immediately create-and-close a socket.
    connectTimer = window.setTimeout(() => connectWebSocket(), 0);

    return () => {
      disposed = true;
      if (connectTimer !== null) {
        window.clearTimeout(connectTimer);
      }
      clearReconnectTimer();
      teardownSocket(ws);
      ws = null;
    };
  }, []);

  const showTransientMessage = (
    nextMessage: { type: 'success' | 'error'; text: string },
    timeoutMs: number
  ) => {
    setMessage(nextMessage);
    setTimeout(() => setMessage(null), timeoutMs);
  };

  const closeStartDialog = (force: boolean = false) => {
    if (startDialogSubmitting && !force) {
      return;
    }
    setStartDialogStrategy(null);
    setStartDialogReadiness(null);
    setStartDialogError(null);
    setStartDialogLoading(false);
  };

  const openStartDialog = (strategy: Strategy) => {
    setStartDialogStrategy(strategy);
    setStartDialogNetwork(strategy.runtime_network ?? 'testnet');
    setStartDialogReadiness(null);
    setStartDialogError(null);
  };

  const executeStrategyStart = async (
    strategy: Strategy,
    runtimeNetwork: 'testnet' | 'mainnet',
    currentStatus: StrategyStatus | undefined
  ) => {
    const confirmRecreate = () =>
      window.confirm(
        `A stale runtime record exists for "${strategy.name}". Recreate the runtime instance and continue?`
      );

    setRuntimePending((prev) => ({
      ...prev,
      [strategy.id]: 'start',
    }));

    mergeStrategyStatus({
      strategyId: strategy.id,
      status: 'starting',
      lastError: undefined,
      updatedAt: new Date().toISOString(),
      instanceId: currentStatus?.instanceId,
      network: runtimeNetwork,
      botStatus: 'starting',
      runtimeSubaccount: startDialogReadiness?.selected_subaccount ?? strategy.runtime_subaccount,
      capitalAllocationUsd: startDialogReadiness?.capital_allocation_usd ?? strategy.initial_amount,
    });

    try {
      let forceRecreate = false;
      if (needsRuntimeRecreateConfirmation(currentStatus?.lastError)) {
        forceRecreate = confirmRecreate();
        if (!forceRecreate) {
          mergeStrategyStatus({
            strategyId: strategy.id,
            status: currentStatus?.status ?? 'stopped',
            lastError: currentStatus?.lastError,
            updatedAt: currentStatus?.updatedAt ?? new Date().toISOString(),
            instanceId: currentStatus?.instanceId,
            network: currentStatus?.network,
            botStatus: currentStatus?.botStatus,
            runtimeSubaccount: currentStatus?.runtimeSubaccount,
            capitalAllocationUsd: currentStatus?.capitalAllocationUsd,
          });
          return;
        }
      }

      let response = await apiClient.startStrategyRuntime(
        strategy.id,
        runtimeNetwork,
        forceRecreate
      );

      if (
        !forceRecreate &&
        needsRuntimeRecreateConfirmation(response?.data?.last_error ?? response?.message)
      ) {
        if (!confirmRecreate()) {
          mergeStrategyStatus({
            strategyId: strategy.id,
            status: currentStatus?.status ?? 'stopped',
            lastError: currentStatus?.lastError,
            updatedAt: currentStatus?.updatedAt ?? new Date().toISOString(),
            instanceId: currentStatus?.instanceId,
            network: currentStatus?.network,
            botStatus: currentStatus?.botStatus,
            runtimeSubaccount: currentStatus?.runtimeSubaccount,
            capitalAllocationUsd: currentStatus?.capitalAllocationUsd,
          });
          return;
        }
        response = await apiClient.startStrategyRuntime(strategy.id, runtimeNetwork, true);
      }

      mergeStrategyStatus(toStrategyStatus(strategy.id, response.data));
      showTransientMessage(
        {
          type: 'success',
          text: `✅ Started strategy "${strategy.name}" on ${runtimeNetwork}${
            forceRecreate ? ' after runtime recovery' : ''
          }`,
        },
        4000
      );
    } catch (error: unknown) {
      let resolvedError = error;

      if (needsRuntimeRecreateConfirmation(getErrorMessage(resolvedError, ''))) {
        const confirmed = confirmRecreate();
        if (confirmed) {
          try {
            const response = await apiClient.startStrategyRuntime(
              strategy.id,
              runtimeNetwork,
              true
            );
            mergeStrategyStatus(toStrategyStatus(strategy.id, response.data));
            showTransientMessage(
              {
                type: 'success',
                text: `✅ Started strategy "${strategy.name}" on ${runtimeNetwork} after runtime recovery`,
              },
              4000
            );
            return;
          } catch (retryError: unknown) {
            resolvedError = retryError;
          }
        }
      }

      mergeStrategyStatus({
        strategyId: strategy.id,
        status: 'error',
        lastError: getErrorMessage(resolvedError, 'Failed to start strategy runtime'),
        updatedAt: new Date().toISOString(),
        instanceId: currentStatus?.instanceId,
        network: runtimeNetwork,
        runtimeSubaccount: currentStatus?.runtimeSubaccount,
        capitalAllocationUsd: currentStatus?.capitalAllocationUsd,
      });
      showTransientMessage(
        {
          type: 'error',
          text: `❌ Failed to start strategy: ${getErrorMessage(error, 'Unknown error')}`,
        },
        6000
      );
      throw resolvedError;
    } finally {
      setRuntimePending((prev) => ({
        ...prev,
        [strategy.id]: undefined,
      }));
    }
  };

  const handleConfirmStrategyStart = async () => {
    if (!startDialogStrategy) {
      return;
    }

    if (!hasExplicitMarketSelection(startDialogReadiness)) {
      const approved = window.confirm(
        'No specific pairs are selected for this strategy. Clicking OK will launch using all active dYdX markets. Continue?'
      );
      if (!approved) {
        return;
      }
    }

    setStartDialogSubmitting(true);
    let launched = false;
    try {
      await executeStrategyStart(
        startDialogStrategy,
        startDialogNetwork,
        strategyStatuses.get(startDialogStrategy.id)
      );
      launched = true;
    } catch {
      // User-facing message already handled in executeStrategyStart.
    } finally {
      setStartDialogSubmitting(false);
      if (launched) {
        closeStartDialog(true);
      }
    }
  };

  const handleRuntimeToggle = async (strategy: Strategy) => {
    const currentStatus = strategyStatuses.get(strategy.id);
    const shouldStop = currentStatus?.status === 'running' || currentStatus?.status === 'starting';

    if (!shouldStop) {
      openStartDialog(strategy);
      return;
    }

    setRuntimePending((prev) => ({
      ...prev,
      [strategy.id]: 'stop',
    }));

    mergeStrategyStatus({
      strategyId: strategy.id,
      status: 'stopping',
      lastError: undefined,
      updatedAt: new Date().toISOString(),
      instanceId: currentStatus?.instanceId,
      network: currentStatus?.network,
      botStatus: 'stopping',
    });

    try {
      const response = await apiClient.stopStrategyRuntime(strategy.id);

      mergeStrategyStatus(toStrategyStatus(strategy.id, response.data));
      showTransientMessage(
        {
          type: 'success',
          text: `✅ Stopped strategy "${strategy.name}"`,
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
          text: `❌ Failed to stop strategy: ${getErrorMessage(error, 'Unknown error')}`,
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

    if (editingConfig.transaction_fee !== undefined && editingConfig.transaction_fee < 0) {
      errors.transaction_fee = 'Transaction fee cannot be negative';
    }

    if (editingConfig.slippage !== undefined && editingConfig.slippage < 0) {
      errors.slippage = 'Slippage cannot be negative';
    }

    if (editingConfig.starting_balance !== undefined && editingConfig.starting_balance < 100) {
      errors.starting_balance = 'Starting balance must be at least $100';
    }

    setConfigErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const buildStrategyUpdatePayload = (strategyConfig: Partial<Strategy>) => ({
    name: strategyConfig.name || 'Untitled Strategy',
    category: strategyConfig.category,
    description: strategyConfig.description,
    is_public: strategyConfig.is_public,
    runtime_strategy: strategyConfig.runtime_strategy || 'cointegration',
    runtime_network: strategyConfig.runtime_network || 'testnet',
    runtime_subaccount: strategyConfig.runtime_subaccount ?? 0,
    selected_markets: strategyConfig.selected_markets || [],
    pair_selection_mode: strategyConfig.pair_selection_mode || 'liquidity',
    resolution: normalizeDydxCandleResolution(
      strategyConfig.candle_resolution || strategyConfig.resolution || '1HOUR'
    ),
    candle_resolution: normalizeDydxCandleResolution(
      strategyConfig.candle_resolution || strategyConfig.resolution || '1HOUR'
    ),
    zscore_threshold: strategyConfig.zscore_threshold,
    stats_window: strategyConfig.stats_window,
    max_half_life: strategyConfig.max_half_life,
    usd_per_trade: strategyConfig.usd_per_trade,
    usd_min_collateral: strategyConfig.usd_min_collateral,
    close_at_zscore_cross: strategyConfig.close_at_zscore_cross,
    find_cointegrated_pairs: strategyConfig.find_cointegrated_pairs,
    manage_exits: strategyConfig.manage_exits,
    place_trades: strategyConfig.place_trades,
    abort_all_positions: strategyConfig.abort_all_positions,
    max_positions: strategyConfig.max_positions,
    max_drawdown_pct: strategyConfig.max_drawdown_pct,
    stop_loss_pct: strategyConfig.stop_loss_pct,
    take_profit_pct: strategyConfig.take_profit_pct,
    trailing_stop_pct: strategyConfig.trailing_stop_pct,
    rebalance_interval_hours: strategyConfig.rebalance_interval_hours,
    position_timeout_hours: strategyConfig.position_timeout_hours,
    transaction_fee: strategyConfig.transaction_fee,
    slippage: strategyConfig.slippage,
    starting_balance: strategyConfig.starting_balance,
    max_history_days: strategyConfig.max_history_days,
    benchmark_symbol: strategyConfig.benchmark_symbol,
    risk_free_rate: strategyConfig.risk_free_rate,
    initial_amount: strategyConfig.initial_amount,
  });

  const handleSaveConfig = async () => {
    if (!editingConfig || !editingConfig.id || !validateConfig()) {
      return;
    }

    try {
      const updatePayload = buildStrategyUpdatePayload(editingConfig);
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

  const handleApplySuggestedParams = async (strategy: Strategy, params: Partial<Strategy>) => {
    const mergedConfig: Partial<Strategy> = {
      ...strategy,
      ...params,
    };
    await apiClient.updateStrategy(strategy.id, buildStrategyUpdatePayload(mergedConfig));
    await fetchStrategies();
    showTransientMessage(
      {
        type: 'success',
        text: `✅ Applied AI suggestions to "${strategy.name}"`,
      },
      4000
    );
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
      const selectedMarkets = Array.isArray(strategy.selected_markets)
        ? strategy.selected_markets
        : [];
      const resolution = normalizeDydxCandleResolution(
        strategy.candle_resolution || strategy.resolution || '1HOUR'
      );
      const pairSelectionMode = strategy.pair_selection_mode || 'liquidity';
      const initialBalance = Number(strategy.starting_balance ?? strategy.initial_amount ?? 1000);

      const response = await apiClient.runBacktest({
        strategy_id: strategy.id,
        name: `${strategy.name} Backtest`,
        description: strategy.description || '',
        start_date: startDate.toISOString().split('T')[0],
        end_date: endDate.toISOString().split('T')[0],
        initial_balance: initialBalance,
        max_pairs: selectedMarkets.length,
        pair_selection_mode: pairSelectionMode,
        ...(selectedMarkets.length > 0 ? { pairs: selectedMarkets } : {}),
        trading_parameters: {
          resolution,
          candle_resolution: resolution,
          zscore_threshold: strategy.zscore_threshold,
          stats_window: strategy.stats_window,
          max_half_life: strategy.max_half_life,
          usd_per_trade: strategy.usd_per_trade,
          usd_min_collateral: strategy.usd_min_collateral,
          close_at_zscore_cross: strategy.close_at_zscore_cross,
          find_cointegrated_pairs: strategy.find_cointegrated_pairs,
          manage_exits: strategy.manage_exits,
          place_trades: strategy.place_trades,
          abort_all_positions: strategy.abort_all_positions,
          max_positions: strategy.max_positions,
          max_drawdown_pct: strategy.max_drawdown_pct,
          stop_loss_pct: strategy.stop_loss_pct,
          take_profit_pct: strategy.take_profit_pct,
          trailing_stop_pct: strategy.trailing_stop_pct,
          rebalance_interval_hours: strategy.rebalance_interval_hours,
          position_timeout_hours: strategy.position_timeout_hours,
          transaction_fee: strategy.transaction_fee,
          slippage: strategy.slippage,
          risk_free_rate: strategy.risk_free_rate,
          benchmark_symbol: strategy.benchmark_symbol || 'BTC-USD',
          max_history_days: strategy.max_history_days,
          pair_selection_mode: pairSelectionMode,
        },
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
    try {
      await deleteStrategy(strategy.id);
      setDeleteConfirmId(null);
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

  // Computed values for AI Runtime Digest
  const digestTotalPnl = useMemo(
    () => Array.from(strategyStatuses.values()).reduce((sum, s) => sum + (s.pnl ?? 0), 0),
    [strategyStatuses]
  );
  const digestErrorCount = useMemo(
    () => Array.from(strategyStatuses.values()).filter((s) => s.status === 'error').length,
    [strategyStatuses]
  );
  const digestActivePairs = useMemo(() => {
    const markets = new Set<string>();
    safeStrategies.forEach((s) => {
      if (s.market_1) markets.add(s.market_1);
      if (s.market_2) markets.add(s.market_2);
    });
    return Math.floor(markets.size / 2);
  }, [safeStrategies]);
  const digestNetwork = useMemo(() => {
    const nets = Array.from(strategyStatuses.values())
      .map((s) => s.network)
      .filter(Boolean);
    return (nets[0] ?? safeStrategies[0]?.runtime_network ?? 'testnet') as string;
  }, [strategyStatuses, safeStrategies]);

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
      <section className="premium-hero px-6 py-7 sm:px-8">
        <div className="premium-orb -right-10 top-0 h-44 w-44 bg-cyan-500/10" />
        <div className="premium-orb -left-8 bottom-0 h-36 w-36 bg-emerald-500/10" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="premium-kicker">Strategy Runtime</div>
            <h1 className="mt-4 text-3xl font-bold text-white sm:text-4xl">
              Operate live strategies with cleaner signal and less operator friction.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
              Start, stop, benchmark, and tune strategies from one premium control surface with
              backend-synced runtime state and market context beside each setup.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-75">
            <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Active</p>
              <p className="mt-1 text-3xl font-semibold text-emerald-300">{runningCount}</p>
            </div>
            <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Strategies</p>
              <p className="mt-1 text-3xl font-semibold text-white">{safeStrategies.length}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[0.9fr,1.3fr]">
        <div
          className={`premium-panel ${
            webSocketConnected ? 'border-emerald-500/20' : 'border-amber-500/20'
          }`}
        >
          <div className="flex items-center gap-3">
            <div
              className={`h-2.5 w-2.5 rounded-full ${
                webSocketConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400 animate-pulse'
              }`}
            />
            <div>
              <p className="text-sm font-semibold text-white">Realtime status</p>
              <p
                className={
                  webSocketConnected ? 'text-sm text-emerald-300' : 'text-sm text-amber-300'
                }
              >
                {webSocketConnected
                  ? 'WebSocket connected and streaming updates'
                  : 'Connecting to live runtime events'}
              </p>
            </div>
          </div>
        </div>

        <div className="premium-panel">
          <p className="text-sm leading-6 text-slate-300">
            Runtime control is live through the backend strategy execution service. An active dYdX
            key is still required before a strategy can start, and statuses are reconciled every 15
            seconds for safety.
          </p>
        </div>
      </section>

      <CodexAssetIntelStrip
        title="Strategy Benchmark Context"
        request={buildStrategyIntelRequest(safeStrategies, 1)}
        compact
      />

      {/* AI Runtime Digest */}
      <AIRuntimeDigest
        runningBots={runningCount}
        totalBots={safeStrategies.length}
        openPositions={0}
        totalPnlUsd={digestTotalPnl}
        activePairs={digestActivePairs}
        errorCount={digestErrorCount}
        network={digestNetwork}
      />

      {/* Messages */}
      {message && (
        <div
          className={`premium-panel ${
            message.type === 'success'
              ? 'border-green-500/20 text-green-200'
              : 'border-red-500/20 text-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Strategies List */}
      <div className="space-y-4">
        {safeStrategies.length === 0 ? (
          <div className="premium-panel p-8 text-center">
            <AlertCircle className="w-12 h-12 text-gray-500 mx-auto mb-4" />
            <p className="text-gray-400 text-lg">No strategies available</p>
          </div>
        ) : (
          safeStrategies.map((strategy) => {
            const status = strategyStatuses.get(strategy.id) || {
              strategyId: strategy.id,
              status: 'stopped' as const,
              updatedAt: new Date().toISOString(),
            };

            return (
              <div
                key={strategy.id}
                className={`premium-panel premium-panel-hover p-6 transition-all duration-300 ${
                  status.status === 'running'
                    ? 'border-green-500/40 shadow-lg shadow-green-900/25'
                    : ''
                }`}
              >
                {/* Strategy Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-xl font-bold text-white">{strategy.name}</h3>
                      <span className="rounded-full border border-slate-700/70 bg-slate-950/45 px-3 py-1 text-xs text-slate-300">
                        {strategy.category}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-400">{strategy.description}</p>
                  </div>

                  {/* Status Badge */}
                  <div
                    className={`flex items-center gap-2 rounded-2xl border px-4 py-2 ${getStatusBg(status.status)}`}
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
                  <div className="mb-4 flex gap-2 rounded-2xl border border-red-700 bg-red-900/30 p-3">
                    <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-red-200 text-sm font-medium">Error</p>
                      <p className="text-red-300 text-xs mt-1">{status.lastError}</p>
                    </div>
                  </div>
                )}

                {/* Key Parameters */}
                <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-2xl border border-slate-700/50 bg-slate-950/45 p-3">
                    <p className="text-gray-400 text-xs uppercase tracking-[0.14em]">
                      Z-Score Threshold
                    </p>
                    <p className="text-white font-semibold">{strategy.zscore_threshold}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-700/50 bg-slate-950/45 p-3">
                    <p className="text-gray-400 text-xs uppercase tracking-[0.14em]">
                      USD Per Trade
                    </p>
                    <p className="text-white font-semibold">${strategy.usd_per_trade}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-700/50 bg-slate-950/45 p-3">
                    <p className="text-gray-400 text-xs uppercase tracking-[0.14em]">
                      Max Positions
                    </p>
                    <p className="text-white font-semibold">{strategy.max_positions}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-700/50 bg-slate-950/45 p-3">
                    <p className="text-gray-400 text-xs uppercase tracking-[0.14em]">
                      Max Drawdown
                    </p>
                    <p className="text-white font-semibold">{strategy.max_drawdown_pct}%</p>
                  </div>
                </div>

                <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-3">
                    <p className="text-cyan-200 text-xs uppercase tracking-[0.14em]">
                      Runtime Network
                    </p>
                    <p className="text-white font-semibold capitalize">
                      {strategy.runtime_network || status.network || 'testnet'}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-3">
                    <p className="text-cyan-200 text-xs uppercase tracking-[0.14em]">Subaccount</p>
                    <p className="text-white font-semibold">
                      #{status.runtimeSubaccount ?? strategy.runtime_subaccount ?? 0}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-3">
                    <p className="text-cyan-200 text-xs uppercase tracking-[0.14em]">
                      Allocated Capital
                    </p>
                    <p className="text-white font-semibold">
                      $
                      {(
                        status.capitalAllocationUsd ??
                        strategy.initial_amount ??
                        strategy.usd_min_collateral ??
                        0
                      ).toLocaleString()}
                    </p>
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
                        className={`flex items-center gap-2 rounded-2xl px-4 py-2 font-medium transition-colors disabled:opacity-80 disabled:cursor-not-allowed ${buttonClass}`}
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
                    className="flex items-center gap-2 rounded-2xl bg-blue-600 px-4 py-2 font-medium text-white transition-colors hover:bg-blue-700"
                  >
                    <Settings className="w-4 h-4" />
                    Configure
                  </button>

                  {/* Backtest Button */}
                  <button
                    onClick={() => handleRunBacktest(strategy)}
                    className="flex items-center gap-2 rounded-2xl bg-indigo-600 px-4 py-2 font-medium text-white transition-colors hover:bg-indigo-700"
                  >
                    <BarChart3 className="w-4 h-4" />
                    Backtest
                  </button>

                  {/* Copy Button */}
                  <button
                    onClick={() => void handleDuplicateStrategy(strategy)}
                    className="flex items-center gap-2 rounded-2xl bg-slate-800 px-4 py-2 font-medium text-white transition-colors hover:bg-slate-700"
                  >
                    <Copy className="w-4 h-4" />
                    Duplicate
                  </button>

                  {/* Delete Button */}
                  {deleteConfirmId === strategy.id ? (
                    <>
                      <button
                        onClick={() => void handleDeleteStrategy(strategy)}
                        className="flex items-center gap-2 rounded-2xl bg-red-600 px-4 py-2 font-medium text-white transition-colors hover:bg-red-500"
                      >
                        <Trash2 className="w-4 h-4" />
                        Confirm Delete
                      </button>
                      <button
                        onClick={() => setDeleteConfirmId(null)}
                        className="flex items-center gap-2 rounded-2xl bg-slate-800 px-4 py-2 font-medium text-white transition-colors hover:bg-slate-700"
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => setDeleteConfirmId(strategy.id)}
                      className="flex items-center gap-2 rounded-2xl bg-slate-800 px-4 py-2 font-medium text-white transition-colors hover:bg-red-900/50"
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete
                    </button>
                  )}
                </div>

                {/* AI Parameter Advisor */}
                <AIStrategyAdvisor
                  strategy={strategy}
                  lastError={status.lastError}
                  onApplyParams={(params) => handleApplySuggestedParams(strategy, params)}
                />
              </div>
            );
          })
        )}
      </div>

      {startDialogStrategy &&
        typeof document !== 'undefined' &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="w-full max-w-3xl rounded-3xl border border-slate-700 bg-slate-900 shadow-2xl shadow-black/40">
              <div className="flex items-center justify-between border-b border-slate-800 px-6 py-5">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Live Launch</p>
                  <h2 className="mt-2 text-2xl font-semibold text-white">
                    Start {startDialogStrategy.name}
                  </h2>
                </div>
                <button
                  onClick={() => closeStartDialog()}
                  className="rounded-full border border-slate-700 px-3 py-1 text-slate-300 transition hover:border-slate-500 hover:text-white"
                >
                  Close
                </button>
              </div>

              <div className="space-y-6 px-6 py-6">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-200">
                      Environment
                    </label>
                    <select
                      value={startDialogNetwork}
                      onChange={(event) =>
                        setStartDialogNetwork(event.target.value as 'testnet' | 'mainnet')
                      }
                      className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-white focus:border-cyan-400 focus:outline-none"
                    >
                      <option value="testnet">dYdX Testnet</option>
                      <option value="mainnet">dYdX Production</option>
                    </select>
                  </div>
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-400">
                      Configured subaccount
                    </p>
                    <p className="mt-2 text-xl font-semibold text-white">
                      #
                      {startDialogReadiness?.selected_subaccount ??
                        startDialogStrategy.runtime_subaccount ??
                        0}
                    </p>
                  </div>
                </div>

                {startDialogNetwork === 'mainnet' ? (
                  <div className="rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                    <p className="font-semibold text-red-200">Mainnet risk notice</p>
                    <p className="mt-1">
                      You are about to launch on production capital. Confirm key ownership,
                      subaccount, collateral, and trade sizing before continuing.
                    </p>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
                    <p className="font-semibold text-cyan-200">Testnet mode</p>
                    <p className="mt-1">
                      Testnet launch is recommended for strategy shakeout and credential
                      verification before production deployment.
                    </p>
                  </div>
                )}

                {startDialogError && (
                  <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                    {startDialogError}
                  </div>
                )}

                {startDialogLoading && (
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-5 text-sm text-slate-300">
                    Checking dYdX key, subaccount, and collateral readiness...
                  </div>
                )}

                {!startDialogLoading && startDialogReadiness && (
                  <>
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <p className="text-xs uppercase tracking-[0.16em] text-slate-400">
                          Key Present
                        </p>
                        <p className="mt-2 text-lg font-semibold text-white">
                          {startDialogReadiness.key_exists ? 'Yes' : 'Missing'}
                        </p>
                        {startDialogReadiness.key_chain_address && (
                          <p className="mt-2 text-xs text-slate-400">
                            {startDialogReadiness.key_chain_address}
                          </p>
                        )}
                      </div>
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <p className="text-xs uppercase tracking-[0.16em] text-slate-400">
                          Free Collateral
                        </p>
                        <p className="mt-2 text-lg font-semibold text-white">
                          ${startDialogReadiness.available_collateral.toFixed(2)}
                        </p>
                      </div>
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <p className="text-xs uppercase tracking-[0.16em] text-slate-400">
                          Trade Size
                        </p>
                        <p className="mt-2 text-lg font-semibold text-white">
                          ${startDialogReadiness.usd_per_trade.toFixed(2)}
                        </p>
                      </div>
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Ready</p>
                        <p
                          className={`mt-2 text-lg font-semibold ${
                            startDialogReadiness.ready ? 'text-emerald-400' : 'text-amber-300'
                          }`}
                        >
                          {startDialogReadiness.ready ? 'Ready to launch' : 'Not ready'}
                        </p>
                      </div>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <p className="text-xs uppercase tracking-[0.16em] text-slate-400">
                          Readiness checks
                        </p>
                        <div className="mt-4 space-y-3 text-sm">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-300">Wallet derivation</span>
                            <span
                              className={
                                startDialogReadiness.wallet_ready
                                  ? 'text-emerald-400'
                                  : 'text-amber-300'
                              }
                            >
                              {startDialogReadiness.wallet_ready ? 'OK' : 'Blocked'}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-300">Subaccount exists</span>
                            <span
                              className={
                                startDialogReadiness.account_exists
                                  ? 'text-emerald-400'
                                  : 'text-amber-300'
                              }
                            >
                              {startDialogReadiness.account_exists ? 'Yes' : 'No'}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-300">Trade size vs collateral</span>
                            <span
                              className={
                                startDialogReadiness.sufficient_for_trade_size
                                  ? 'text-emerald-400'
                                  : 'text-amber-300'
                              }
                            >
                              {startDialogReadiness.sufficient_for_trade_size ? 'OK' : 'Too low'}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-300">Minimum collateral guard</span>
                            <span
                              className={
                                startDialogReadiness.sufficient_for_min_collateral
                                  ? 'text-emerald-400'
                                  : 'text-amber-300'
                              }
                            >
                              {startDialogReadiness.sufficient_for_min_collateral
                                ? 'OK'
                                : 'Too low'}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <p className="text-xs uppercase tracking-[0.16em] text-slate-400">
                          Deployment context
                        </p>
                        <div className="mt-4 space-y-3 text-sm text-slate-300">
                          <div className="flex items-center justify-between">
                            <span>Selected environment</span>
                            <span className="font-medium capitalize text-white">
                              {startDialogReadiness.selected_runtime_network}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span>Subaccount</span>
                            <span className="font-medium text-white">
                              #{startDialogReadiness.selected_subaccount}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span>Capital allocation target</span>
                            <span className="font-medium text-white">
                              ${startDialogReadiness.capital_allocation_usd.toFixed(2)}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span>Min collateral guard</span>
                            <span className="font-medium text-white">
                              ${startDialogReadiness.usd_min_collateral.toFixed(2)}
                            </span>
                          </div>
                          {startDialogReadiness.trade_size_to_collateral_ratio !== null &&
                            startDialogReadiness.trade_size_to_collateral_ratio !== undefined && (
                              <div className="flex items-center justify-between">
                                <span>Trade size / free collateral</span>
                                <span className="font-medium text-white">
                                  {(
                                    startDialogReadiness.trade_size_to_collateral_ratio * 100
                                  ).toFixed(2)}
                                  %
                                </span>
                              </div>
                            )}
                        </div>
                      </div>
                    </div>

                    {Array.isArray(startDialogReadiness.blockers) &&
                      startDialogReadiness.blockers.length > 0 && (
                        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4">
                          <p className="text-sm font-semibold text-amber-200">Launch blockers</p>
                          <ul className="mt-3 space-y-2 text-sm text-amber-100">
                            {startDialogReadiness.blockers.map((blocker) => (
                              <li key={blocker}>• {blocker}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                    {Array.isArray(startDialogReadiness.warnings) &&
                      startDialogReadiness.warnings.length > 0 && (
                        <div className="rounded-2xl border border-cyan-500/30 bg-cyan-500/10 p-4">
                          <p className="text-sm font-semibold text-cyan-100">Warnings</p>
                          <ul className="mt-3 space-y-2 text-sm text-cyan-50">
                            {startDialogReadiness.warnings.map((warning) => (
                              <li key={warning}>• {warning}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                  </>
                )}
              </div>

              <div className="flex items-center justify-between gap-3 border-t border-slate-800 px-6 py-5">
                <p className="text-sm text-slate-400">
                  Frontend launch is gated by backend readiness. The frontend never connects to dYdX
                  directly.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => closeStartDialog()}
                    className="rounded-2xl border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => void handleConfirmStrategyStart()}
                    disabled={
                      startDialogSubmitting ||
                      startDialogLoading ||
                      !startDialogReadiness ||
                      !startDialogReadiness.ready
                    }
                    className="rounded-2xl bg-emerald-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                  >
                    {startDialogSubmitting ? 'Launching...' : 'Launch Runtime'}
                  </button>
                </div>
              </div>
            </div>
          </div>,
          document.body
        )}

      {/* Strategy Config Modal */}
      {showConfigModal &&
        editingConfig &&
        typeof document !== 'undefined' &&
        createPortal(
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
                <section className="space-y-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Identity</p>
                    <h3 className="mt-2 text-lg font-semibold text-white">Strategy profile</h3>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-white font-medium">Name</label>
                      <input
                        type="text"
                        value={editingConfig.name || ''}
                        onChange={(e) => updateEditingConfig({ name: e.target.value })}
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Category</label>
                      <input
                        type="text"
                        value={editingConfig.category || ''}
                        onChange={(e) => updateEditingConfig({ category: e.target.value })}
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="mb-2 block text-white font-medium">Description</label>
                      <textarea
                        value={editingConfig.description || ''}
                        onChange={(e) => updateEditingConfig({ description: e.target.value })}
                        rows={3}
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>
                </section>

                <section className="space-y-4 border-t border-slate-700 pt-6">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Runtime</p>
                    <h3 className="mt-2 text-lg font-semibold text-white">Live bot parameters</h3>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-white font-medium">Runtime strategy</label>
                      <select
                        value={editingConfig.runtime_strategy || 'cointegration'}
                        onChange={(e) => updateEditingConfig({ runtime_strategy: e.target.value })}
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      >
                        {RUNTIME_STRATEGY_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Runtime network</label>
                      <select
                        value={editingConfig.runtime_network ?? 'testnet'}
                        onChange={(e) =>
                          updateEditingConfig({
                            runtime_network: e.target.value as Strategy['runtime_network'],
                          })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="testnet">dYdX Testnet</option>
                        <option value="mainnet">dYdX Mainnet</option>
                      </select>
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">
                        Runtime subaccount
                      </label>
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={editingConfig.runtime_subaccount ?? 0}
                        onChange={(e) =>
                          updateEditingConfig({
                            runtime_subaccount: parseInt(e.target.value, 10) || 0,
                          })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                      <p className="mt-2 text-xs text-slate-400">
                        Separate dYdX subaccounts are the safest way to isolate live margin per
                        strategy.
                      </p>
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Resolution</label>
                      <select
                        value={normalizeDydxCandleResolution(
                          editingConfig.candle_resolution || editingConfig.resolution || '1HOUR'
                        )}
                        onChange={(e) =>
                          updateEditingConfig({
                            resolution: normalizeDydxCandleResolution(e.target.value),
                            candle_resolution: normalizeDydxCandleResolution(e.target.value),
                          })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      >
                        {DYDX_CANDLE_RESOLUTION_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">
                        Z-Score threshold
                        {configErrors.zscore_threshold && (
                          <span className="ml-2 text-sm text-red-400">
                            • {configErrors.zscore_threshold}
                          </span>
                        )}
                      </label>
                      <input
                        type="number"
                        step="0.1"
                        min="0.1"
                        max="5"
                        value={editingConfig.zscore_threshold ?? 1.5}
                        onChange={(e) =>
                          updateEditingConfig({ zscore_threshold: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Stats window</label>
                      <input
                        type="number"
                        min="5"
                        max="365"
                        value={editingConfig.stats_window ?? 21}
                        onChange={(e) =>
                          updateEditingConfig({ stats_window: parseInt(e.target.value, 10) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Max half-life</label>
                      <input
                        type="number"
                        min="1"
                        value={editingConfig.max_half_life ?? 24}
                        onChange={(e) =>
                          updateEditingConfig({ max_half_life: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">
                        USD per trade
                        {configErrors.usd_per_trade && (
                          <span className="ml-2 text-sm text-red-400">
                            • {configErrors.usd_per_trade}
                          </span>
                        )}
                      </label>
                      <input
                        type="number"
                        step="1"
                        min="1"
                        value={editingConfig.usd_per_trade ?? 10}
                        onChange={(e) =>
                          updateEditingConfig({ usd_per_trade: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">
                        USD min collateral
                      </label>
                      <input
                        type="number"
                        step="1"
                        min="0"
                        value={editingConfig.usd_min_collateral ?? 100}
                        onChange={(e) =>
                          updateEditingConfig({ usd_min_collateral: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div className="md:col-span-2 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {[
                        ['place_trades', 'Place trades'],
                        ['manage_exits', 'Manage exits'],
                        ['abort_all_positions', 'Abort all positions on start'],
                        ['find_cointegrated_pairs', 'Find cointegrated pairs'],
                        ['close_at_zscore_cross', 'Close at Z-score cross'],
                      ].map(([field, label]) => (
                        <label
                          key={field}
                          className="flex items-center gap-3 rounded-2xl border border-slate-700/70 bg-slate-950/35 px-4 py-3 text-sm text-slate-200"
                        >
                          <input
                            type="checkbox"
                            checked={Boolean(editingConfig[field as keyof Strategy])}
                            onChange={(e) =>
                              updateEditingConfig({
                                [field]: e.target.checked,
                              } as Partial<Strategy>)
                            }
                            className="h-4 w-4 rounded border-slate-500 bg-slate-800"
                          />
                          <span>{label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </section>

                <section className="space-y-4 border-t border-slate-700 pt-6">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Risk</p>
                    <h3 className="mt-2 text-lg font-semibold text-white">Execution guardrails</h3>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-white font-medium">Max positions</label>
                      <input
                        type="number"
                        min="1"
                        max="100"
                        value={editingConfig.max_positions ?? 5}
                        onChange={(e) =>
                          updateEditingConfig({ max_positions: parseInt(e.target.value, 10) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">
                        Max drawdown %
                        {configErrors.max_drawdown_pct && (
                          <span className="ml-2 text-sm text-red-400">
                            • {configErrors.max_drawdown_pct}
                          </span>
                        )}
                      </label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="100"
                        value={editingConfig.max_drawdown_pct ?? 15}
                        onChange={(e) =>
                          updateEditingConfig({ max_drawdown_pct: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Stop loss %</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        value={editingConfig.stop_loss_pct ?? 2}
                        onChange={(e) =>
                          updateEditingConfig({ stop_loss_pct: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Take profit %</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        value={editingConfig.take_profit_pct ?? 5}
                        onChange={(e) =>
                          updateEditingConfig({ take_profit_pct: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Trailing stop %</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        value={editingConfig.trailing_stop_pct ?? 1}
                        onChange={(e) =>
                          updateEditingConfig({ trailing_stop_pct: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">
                        Rebalance interval (hours)
                      </label>
                      <input
                        type="number"
                        min="1"
                        value={editingConfig.rebalance_interval_hours ?? 24}
                        onChange={(e) =>
                          updateEditingConfig({
                            rebalance_interval_hours: parseInt(e.target.value, 10),
                          })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">
                        Position timeout (hours)
                      </label>
                      <input
                        type="number"
                        min="1"
                        value={editingConfig.position_timeout_hours ?? 72}
                        onChange={(e) =>
                          updateEditingConfig({
                            position_timeout_hours: parseInt(e.target.value, 10),
                          })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>
                </section>

                <section className="space-y-4 border-t border-slate-700 pt-6">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Backtesting</p>
                    <h3 className="mt-2 text-lg font-semibold text-white">Simulation defaults</h3>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-white font-medium">
                        Starting balance
                        {configErrors.starting_balance && (
                          <span className="ml-2 text-sm text-red-400">
                            • {configErrors.starting_balance}
                          </span>
                        )}
                      </label>
                      <input
                        type="number"
                        step="100"
                        min="100"
                        value={
                          editingConfig.starting_balance ?? editingConfig.initial_amount ?? 1000
                        }
                        onChange={(e) =>
                          updateEditingConfig({
                            starting_balance: parseFloat(e.target.value),
                            initial_amount: parseFloat(e.target.value),
                          })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">
                        Transaction fee
                        {configErrors.transaction_fee && (
                          <span className="ml-2 text-sm text-red-400">
                            • {configErrors.transaction_fee}
                          </span>
                        )}
                      </label>
                      <input
                        type="number"
                        step="0.0001"
                        min="0"
                        value={editingConfig.transaction_fee ?? 0.0005}
                        onChange={(e) =>
                          updateEditingConfig({ transaction_fee: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">
                        Slippage
                        {configErrors.slippage && (
                          <span className="ml-2 text-sm text-red-400">
                            • {configErrors.slippage}
                          </span>
                        )}
                      </label>
                      <input
                        type="number"
                        step="0.0001"
                        min="0"
                        value={editingConfig.slippage ?? 0.001}
                        onChange={(e) =>
                          updateEditingConfig({ slippage: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Max history days</label>
                      <input
                        type="number"
                        min="1"
                        max="3650"
                        value={editingConfig.max_history_days ?? 90}
                        onChange={(e) =>
                          updateEditingConfig({ max_history_days: parseInt(e.target.value, 10) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Benchmark symbol</label>
                      <input
                        type="text"
                        value={editingConfig.benchmark_symbol ?? 'BTC-USD'}
                        onChange={(e) => updateEditingConfig({ benchmark_symbol: e.target.value })}
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-white font-medium">Risk-free rate</label>
                      <input
                        type="number"
                        step="0.001"
                        min="0"
                        value={editingConfig.risk_free_rate ?? 0.02}
                        onChange={(e) =>
                          updateEditingConfig({ risk_free_rate: parseFloat(e.target.value) })
                        }
                        className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2 text-white focus:border-transparent focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>
                </section>

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
          </div>,
          document.body
        )}
    </PageContainer>
  );
}
