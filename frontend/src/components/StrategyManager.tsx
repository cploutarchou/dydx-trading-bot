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

import { useQueryClient } from '@tanstack/react-query';
import { AlertCircle, AlertTriangle, BarChart3, Copy, Settings, Trash2, X } from 'lucide-react';
import {
    type KeyboardEvent as ReactKeyboardEvent,
    useEffect,
    useMemo,
    useRef,
    useState,
} from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import apiClient, {
    type AIBacktestSummary,
    DYDX_CANDLE_RESOLUTION_OPTIONS,
    normalizeDydxCandleResolution,
    toAIBacktestSummary,
} from '../api';
import {
    useStartStrategyRuntimeMutation,
    useStopStrategyRuntimeMutation,
    useStrategies,
    useStrategyBacktests,
    useStrategyRuntimes,
    useStrategyStartReadiness,
} from '../api/hooks';
import { extractBacktestRuns, isActiveBacktestRun } from '../features/backtests/intelligence';
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
  winRate?: number;
  openPositions?: number;
  uptimeSeconds?: number;
  startedAt?: string;
  runtimeUpdatedAt?: string;
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

interface StrategyActivityEntry {
  label: 'Runtime started' | 'Runtime stopped' | 'Backtest started';
  at: string;
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

const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const toPositiveInteger = (value: unknown): number | null => {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};

const extractUserBacktestQuota = (payload: unknown): number | null => {
  const root = toRecord(payload);
  const data = toRecord(root.data);
  return (
    toPositiveInteger(data.max_active_backtests) ?? toPositiveInteger(root.max_active_backtests)
  );
};

const countActiveBacktests = (payload: unknown): number =>
  extractBacktestRuns(payload).filter((run) => isActiveBacktestRun(run)).length;

const asNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

const formatRuntimeDuration = (seconds?: number): string => {
  if (seconds === undefined || Number.isNaN(seconds) || seconds < 0) return '—';

  const totalSeconds = Math.floor(seconds);
  const days = Math.floor(totalSeconds / 86_400);
  const hours = Math.floor((totalSeconds % 86_400) / 3_600);
  const minutes = Math.floor((totalSeconds % 3_600) / 60);

  if (days > 0) {
    return `${days}d ${hours}h`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
};

const formatRuntimeTime = (value?: string): string => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleTimeString();
};

const formatRelativeTime = (value?: string): string => {
  if (!value) return 'No update yet';

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'No update yet';

  const secondsAgo = Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 1000));
  if (secondsAgo < 60) {
    return `${secondsAgo}s ago`;
  }

  const minutesAgo = Math.floor(secondsAgo / 60);
  if (minutesAgo < 60) {
    return `${minutesAgo}m ago`;
  }

  const hoursAgo = Math.floor(minutesAgo / 60);
  return `${hoursAgo}h ago`;
};

const HEARTBEAT_LIVE_THRESHOLD_MS = 30_000;
const HEARTBEAT_DELAYED_THRESHOLD_MS = 120_000;
const HEARTBEAT_TREND_MAX_POINTS = 14;
const HEARTBEAT_TREND_MAX_SECONDS = 180;

type HeartbeatTone = 'live' | 'delayed' | 'stale' | 'unknown';

const resolveHeartbeatTone = (
  heartbeatAt: string | undefined,
  webSocketConnected: boolean
): { tone: HeartbeatTone; label: string } => {
  if (!heartbeatAt) {
    return {
      tone: webSocketConnected ? 'unknown' : 'delayed',
      label: webSocketConnected ? 'Awaiting first heartbeat' : 'Waiting for stream',
    };
  }

  const parsed = new Date(heartbeatAt);
  if (Number.isNaN(parsed.getTime())) {
    return { tone: 'unknown', label: 'Invalid heartbeat timestamp' };
  }

  const ageMs = Date.now() - parsed.getTime();
  if (ageMs <= HEARTBEAT_LIVE_THRESHOLD_MS && webSocketConnected) {
    return { tone: 'live', label: 'Live updates healthy' };
  }

  if (ageMs <= HEARTBEAT_DELAYED_THRESHOLD_MS) {
    return { tone: 'delayed', label: 'Updates slightly delayed' };
  }

  return { tone: 'stale', label: 'Updates stale, check runtime' };
};

const toHeartbeatAgeSeconds = (heartbeatAt?: string): number | null => {
  if (!heartbeatAt) {
    return null;
  }

  const parsed = new Date(heartbeatAt);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 1000));
};

const buildSparklinePoints = (values: number[], width: number, height: number): string => {
  if (values.length === 0) {
    return '';
  }

  const max = HEARTBEAT_TREND_MAX_SECONDS;
  const stepX = values.length > 1 ? width / (values.length - 1) : width;

  return values
    .map((value, index) => {
      const clamped = Math.min(Math.max(value, 0), max);
      const x = index * stepX;
      const y = (clamped / max) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
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
  const queryClient = useQueryClient();
  const { duplicateStrategy, deleteStrategy } = useStrategyStore();
  const strategiesQuery = useStrategies(0, 100, true);
  const strategies = strategiesQuery.data;
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
  const [startDialogSubmitting, setStartDialogSubmitting] = useState(false);
  const [viewPreset, setViewPreset] = useState<'operator' | 'analyst'>('analyst');
  const [focusedCardId, setFocusedCardId] = useState<number | null>(null);
  // startDialogReadiness, startDialogLoading, startDialogError are now derived from useStrategyStartReadiness
  const [strategyActivity, setStrategyActivity] = useState<Map<number, StrategyActivityEntry>>(
    new Map()
  );
  const [heartbeatTrend, setHeartbeatTrend] = useState<Map<number, number[]>>(new Map());
  const [strategyBacktests, setStrategyBacktests] = useState<Map<number, AIBacktestSummary[]>>(
    new Map()
  );
  const lastFocusedElementRef = useRef<HTMLElement | null>(null);
  const startDialogNetworkRef = useRef<HTMLSelectElement | null>(null);
  const configNameInputRef = useRef<HTMLInputElement | null>(null);

  const compactCards = viewPreset === 'operator';
  const startRuntimeMutation = useStartStrategyRuntimeMutation();
  const stopRuntimeMutation = useStopStrategyRuntimeMutation();
  const strategyBacktestsQuery = useStrategyBacktests(
    focusedCardId ?? 0,
    5,
    focusedCardId !== null
  );

  useEffect(() => {
    if (focusedCardId === null || !strategyBacktestsQuery.data) {
      return;
    }

    const items = Array.isArray(strategyBacktestsQuery.data.data?.backtests)
      ? strategyBacktestsQuery.data.data.backtests
      : [];

    const summaries: AIBacktestSummary[] = items
      .map((backtest) => toAIBacktestSummary(backtest))
      .filter((summary): summary is AIBacktestSummary => summary !== null);

    setStrategyBacktests((prev) => {
      const next = new Map(prev);
      next.set(focusedCardId, summaries);
      return next;
    });
  }, [focusedCardId, strategyBacktestsQuery.data]);

  const recordSuccessfulAction = (
    strategyId: number,
    label: StrategyActivityEntry['label'],
    at: string = new Date().toISOString()
  ) => {
    setStrategyActivity((prev) => {
      const next = new Map(prev);
      next.set(strategyId, { label, at });
      return next;
    });
  };

  const updateEditingConfig = (patch: Partial<Strategy>) => {
    setEditingConfig((current) => (current ? { ...current, ...patch } : current));
  };

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

    setHeartbeatTrend((prev) => {
      const next = new Map(prev);
      nextStatuses.forEach((status) => {
        const ageSeconds = toHeartbeatAgeSeconds(status.runtimeUpdatedAt || status.updatedAt);
        if (ageSeconds === null) {
          return;
        }

        const existing = next.get(status.strategyId) || [];
        next.set(status.strategyId, [...existing, ageSeconds].slice(-HEARTBEAT_TREND_MAX_POINTS));
      });
      return next;
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

    setHeartbeatTrend((prev) => {
      const next = new Map(prev);
      const ageSeconds = toHeartbeatAgeSeconds(nextStatus.runtimeUpdatedAt || nextStatus.updatedAt);
      if (ageSeconds === null) {
        return next;
      }

      const existing = next.get(nextStatus.strategyId) || [];
      next.set(nextStatus.strategyId, [...existing, ageSeconds].slice(-HEARTBEAT_TREND_MAX_POINTS));
      return next;
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

    const startedAt =
      typeof runtimeData?.started_at === 'string' ? runtimeData.started_at : undefined;
    const rawPnl = asNumber(runtimeData?.pnl);
    const rawTrades = asNumber(runtimeData?.trades_executed);
    const rawOpenPositions = asNumber(runtimeData?.open_positions);
    const rawWinRate = asNumber(runtimeData?.win_rate);
    const rawUptimeSeconds = asNumber(runtimeData?.uptime_seconds);

    const computedUptimeSeconds =
      rawUptimeSeconds !== undefined
        ? rawUptimeSeconds
        : startedAt && status === 'running'
          ? Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000))
          : undefined;

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
      runtimeUpdatedAt:
        typeof runtimeData?.runtime_updated_at === 'string'
          ? runtimeData.runtime_updated_at
          : typeof runtimeData?.last_synced_at === 'string'
            ? runtimeData.last_synced_at
            : typeof runtimeData?.updated_at === 'string'
              ? runtimeData.updated_at
              : undefined,
      startedAt,
      tradesExecuted: rawTrades !== undefined ? Math.max(0, Math.floor(rawTrades)) : undefined,
      pnl: rawPnl,
      winRate:
        rawWinRate !== undefined ? (rawWinRate <= 1 ? rawWinRate * 100 : rawWinRate) : undefined,
      openPositions:
        rawOpenPositions !== undefined ? Math.max(0, Math.floor(rawOpenPositions)) : undefined,
      uptimeSeconds:
        computedUptimeSeconds !== undefined
          ? Math.max(0, Math.floor(computedUptimeSeconds))
          : undefined,
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

  // ── Runtime status: use React Query instead of manual useEffect polling ─────
  const strategyIds = useMemo(() => safeStrategies.map((s) => s.id), [safeStrategies]);
  const runtimeQueries = useStrategyRuntimes(strategyIds);

  // Derive strategyStatuses / runningCount / heartbeatTrend from React Query results
  useEffect(() => {
    if (strategyIds.length === 0) {
      applyStrategyStatuses([]);
      return;
    }

    const nextStatuses = runtimeQueries.map((query, index) => {
      if (query.isSuccess && query.data) {
        return toStrategyStatus(
          strategyIds[index],
          query.data.data as Record<string, unknown> | undefined
        );
      }
      return {
        strategyId: strategyIds[index],
        status: 'error' as const,
        lastError: query.error
          ? getErrorMessage(query.error, 'Failed to load runtime status')
          : 'Loading...',
        updatedAt: new Date().toISOString(),
      };
    });

    applyStrategyStatuses(nextStatuses);
  }, [runtimeQueries.map((q) => q.dataUpdatedAt).join(','), strategyIds.join(',')]);
  // ─────────────────────────────────────────────────────────────────────────────

  // ── Start-dialog readiness: React Query (only fetches when dialog is open) ──
  const readinessQuery = useStrategyStartReadiness(
    startDialogStrategy?.id ?? null,
    startDialogNetwork,
    Boolean(startDialogStrategy)
  );
  const startDialogReadiness =
    (readinessQuery.data?.data as StrategyStartReadiness | undefined) ?? null;
  const startDialogLoading = readinessQuery.isLoading;
  const startDialogError = readinessQuery.error
    ? getErrorMessage(readinessQuery.error, 'Failed to load runtime readiness')
    : null;
  // ─────────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!startDialogStrategy) {
      return;
    }

    const focusTimer = window.setTimeout(() => startDialogNetworkRef.current?.focus(), 0);
    return () => window.clearTimeout(focusTimer);
  }, [startDialogStrategy]);

  useEffect(() => {
    if (!showConfigModal || !editingConfig) {
      return;
    }

    const focusTimer = window.setTimeout(() => configNameInputRef.current?.focus(), 0);
    return () => window.clearTimeout(focusTimer);
  }, [editingConfig, showConfigModal]);

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
    window.setTimeout(() => lastFocusedElementRef.current?.focus(), 0);
  };

  const openStartDialog = (strategy: Strategy) => {
    lastFocusedElementRef.current =
      typeof document !== 'undefined' ? (document.activeElement as HTMLElement | null) : null;
    setStartDialogStrategy(strategy);
    setStartDialogNetwork(strategy.runtime_network ?? 'testnet');
  };

  const closeConfigDialog = () => {
    setShowConfigModal(false);
    setEditingConfig(null);
    setConfigErrors({});
    window.setTimeout(() => lastFocusedElementRef.current?.focus(), 0);
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

      let response = await startRuntimeMutation.mutateAsync({
        strategyId: strategy.id,
        network: runtimeNetwork,
        forceRecreate,
      });

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
        response = await startRuntimeMutation.mutateAsync({
          strategyId: strategy.id,
          network: runtimeNetwork,
          forceRecreate: true,
        });
      }

      mergeStrategyStatus(toStrategyStatus(strategy.id, response.data));
      recordSuccessfulAction(strategy.id, 'Runtime started');
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
            const response = await startRuntimeMutation.mutateAsync({
              strategyId: strategy.id,
              network: runtimeNetwork,
              forceRecreate: true,
            });
            mergeStrategyStatus(toStrategyStatus(strategy.id, response.data));
            recordSuccessfulAction(strategy.id, 'Runtime started');
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
      showTransientMessage(
        {
          type: 'error',
          text: 'Select at least two dYdX markets for this strategy before starting runtime.',
        },
        5000
      );
      return;
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
      const response = await stopRuntimeMutation.mutateAsync({ strategyId: strategy.id });

      mergeStrategyStatus(toStrategyStatus(strategy.id, response.data));
      recordSuccessfulAction(strategy.id, 'Runtime stopped');
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

      closeConfigDialog();
      await queryClient.invalidateQueries({ queryKey: ['strategies'] });
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
    const editableKeys = new Set<keyof Strategy>([
      'zscore_threshold',
      'stats_window',
      'max_half_life',
      'usd_per_trade',
      'usd_min_collateral',
      'max_positions',
      'max_drawdown_pct',
      'stop_loss_pct',
      'take_profit_pct',
      'trailing_stop_pct',
      'rebalance_interval_hours',
      'position_timeout_hours',
      'transaction_fee',
      'slippage',
      'max_history_days',
      'risk_free_rate',
      'resolution',
      'candle_resolution',
    ]);
    const appliedKeys = (Object.keys(params) as Array<keyof Strategy>).filter((key) =>
      editableKeys.has(key)
    );
    if (appliedKeys.length === 0) {
      throw new Error('No editable strategy parameters were provided by AI suggestions.');
    }

    const mergedConfig: Partial<Strategy> = {
      ...strategy,
      ...params,
    };
    try {
      await apiClient.updateStrategy(strategy.id, buildStrategyUpdatePayload(mergedConfig));
      await queryClient.invalidateQueries({ queryKey: ['strategies'] });
      showTransientMessage(
        {
          type: 'success',
          text: `✅ Applied AI suggestions to "${strategy.name}"`,
        },
        4000
      );
      return appliedKeys;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to apply AI suggestions';
      showTransientMessage({ type: 'error', text: `❌ ${msg}` }, 6000);
      throw err; // re-throw so AIStrategyAdvisor can show applyError
    }
  };

  const handleEditConfig = (strategy: Strategy) => {
    lastFocusedElementRef.current =
      typeof document !== 'undefined' ? (document.activeElement as HTMLElement | null) : null;
    setEditingConfig({ ...strategy });
    setConfigErrors({});
    setShowConfigModal(true);
  };

  const handleRunBacktest = async (strategy: Strategy) => {
    try {
      const [currentUserResponse, backtestListResponse] = await Promise.all([
        apiClient.getCurrentUser(),
        apiClient.listBacktests(0, 250),
      ]);
      const userQuota = extractUserBacktestQuota(currentUserResponse);
      if (userQuota !== null) {
        const activeBacktests = countActiveBacktests(backtestListResponse);
        if (activeBacktests >= userQuota) {
          showTransientMessage(
            {
              type: 'error',
              text: `⚠️ Active backtest limit reached (${activeBacktests}/${userQuota}). Wait for an active run to complete before starting another one.`,
            },
            6000
          );
          return;
        }
      }

      const endDate = new Date();
      const startDate = new Date(endDate);
      startDate.setDate(startDate.getDate() - 30);
      const selectedMarkets = Array.isArray(strategy.selected_markets)
        ? strategy.selected_markets
        : [];
      if (selectedMarkets.length < 2) {
        showTransientMessage(
          {
            type: 'error',
            text: 'Select at least two dYdX markets for this strategy before running a backtest.',
          },
          6000
        );
        return;
      }
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
        recordSuccessfulAction(strategy.id, 'Backtest started');
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
      await queryClient.invalidateQueries({ queryKey: ['strategies'] });
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
      await queryClient.invalidateQueries({ queryKey: ['strategies'] });
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

  const handleStrategyCardKeyDown = (
    event: ReactKeyboardEvent<HTMLDivElement>,
    strategy: Strategy,
    status: StrategyStatus
  ) => {
    if (event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }

    const key = event.key.toLowerCase();

    if (key === 's') {
      event.preventDefault();
      void handleRuntimeToggle(strategy);
      return;
    }

    if (key === 'c') {
      event.preventDefault();
      handleEditConfig(strategy);
      return;
    }

    if (key === 'b') {
      event.preventDefault();
      void handleRunBacktest(strategy);
      return;
    }

    if (key === 'd') {
      event.preventDefault();
      void handleDuplicateStrategy(strategy);
      return;
    }

    if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault();
      if (deleteConfirmId === strategy.id) {
        void handleDeleteStrategy(strategy);
      } else {
        setDeleteConfirmId(strategy.id);
      }
      return;
    }

    if (event.key === 'Escape' && deleteConfirmId === strategy.id) {
      event.preventDefault();
      setDeleteConfirmId(null);
      return;
    }

    if (key === 'r' && status.status === 'running') {
      event.preventDefault();
      void handleRuntimeToggle(strategy);
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
    safeStrategies.forEach((strategy) => {
      if (Array.isArray(strategy.selected_markets)) {
        strategy.selected_markets.forEach((market) => {
          if (typeof market === 'string' && market.length > 0) {
            markets.add(market);
          }
        });
      }
    });
    return Math.floor(markets.size / 2);
  }, [safeStrategies]);
  const digestNetwork = useMemo(() => {
    const nets = Array.from(strategyStatuses.values())
      .map((s) => s.network)
      .filter(Boolean);
    return (nets[0] ?? safeStrategies[0]?.runtime_network ?? 'testnet') as string;
  }, [strategyStatuses, safeStrategies]);
  const digestOpenPositions = useMemo(
    () => Array.from(strategyStatuses.values()).reduce((sum, s) => sum + (s.openPositions ?? 0), 0),
    [strategyStatuses]
  );

  const runtimeHealthSummary = useMemo(() => {
    const statuses = Array.from(strategyStatuses.values());
    const activeStatuses = statuses.filter(
      (status) => status.status === 'running' || status.status === 'starting'
    );
    const targetStatuses = activeStatuses.length > 0 ? activeStatuses : statuses;

    const hasPnlData = targetStatuses.some((status) => status.pnl !== undefined);
    const hasOpenPositionData = targetStatuses.some((status) => status.openPositions !== undefined);
    const hasUptimeData = targetStatuses.some((status) => status.uptimeSeconds !== undefined);

    const totalPnl = targetStatuses.reduce((sum, status) => sum + (status.pnl ?? 0), 0);
    const totalOpenPositions = targetStatuses.reduce(
      (sum, status) => sum + (status.openPositions ?? 0),
      0
    );
    const longestUptimeSeconds = targetStatuses.reduce(
      (max, status) => Math.max(max, status.uptimeSeconds ?? 0),
      0
    );

    const latestUpdateMs = targetStatuses.reduce<number | null>((latest, status) => {
      const candidate = status.runtimeUpdatedAt || status.updatedAt;
      if (!candidate) return latest;
      const parsedMs = new Date(candidate).getTime();
      if (Number.isNaN(parsedMs)) return latest;
      if (latest === null || parsedMs > latest) return parsedMs;
      return latest;
    }, null);

    return {
      scopedCount: targetStatuses.length,
      totalPnl: hasPnlData ? totalPnl : undefined,
      totalOpenPositions: hasOpenPositionData ? totalOpenPositions : undefined,
      longestUptimeSeconds: hasUptimeData ? longestUptimeSeconds : undefined,
      latestRuntimeUpdate:
        latestUpdateMs !== null ? new Date(latestUpdateMs).toISOString() : undefined,
      staleRuntimeCount: activeStatuses.filter((status) => {
        const candidate = status.runtimeUpdatedAt || status.updatedAt;
        if (!candidate) {
          return true;
        }
        const parsedMs = new Date(candidate).getTime();
        if (Number.isNaN(parsedMs)) {
          return true;
        }
        return Date.now() - parsedMs > HEARTBEAT_DELAYED_THRESHOLD_MS;
      }).length,
    };
  }, [strategyStatuses]);

  const heartbeatTone = useMemo(
    () => resolveHeartbeatTone(runtimeHealthSummary.latestRuntimeUpdate, webSocketConnected),
    [runtimeHealthSummary.latestRuntimeUpdate, webSocketConnected]
  );
  const attentionCount = digestErrorCount + runtimeHealthSummary.staleRuntimeCount;

  if (strategiesQuery.isLoading) {
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
            <div className="col-span-2 rounded-2xl border border-slate-700/70 bg-slate-950/55 p-2">
              <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Density preset
              </p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setViewPreset('operator')}
                  aria-pressed={viewPreset === 'operator'}
                  className={`rounded-xl px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.14em] transition ${
                    viewPreset === 'operator'
                      ? 'border border-cyan-500/40 bg-cyan-500/20 text-cyan-100'
                      : 'border border-slate-700 bg-slate-900/60 text-slate-300 hover:border-cyan-500/30 hover:text-cyan-200'
                  }`}
                >
                  Operator
                </button>
                <button
                  type="button"
                  onClick={() => setViewPreset('analyst')}
                  aria-pressed={viewPreset === 'analyst'}
                  className={`rounded-xl px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.14em] transition ${
                    viewPreset === 'analyst'
                      ? 'border border-cyan-500/40 bg-cyan-500/20 text-cyan-100'
                      : 'border border-slate-700 bg-slate-900/60 text-slate-300 hover:border-cyan-500/30 hover:text-cyan-200'
                  }`}
                >
                  Analyst
                </button>
              </div>
            </div>
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
              <p className="mt-1 text-xs text-slate-400">
                {attentionCount > 0
                  ? `${attentionCount} runtime signal${attentionCount === 1 ? '' : 's'} need attention`
                  : 'No runtime attention flags right now'}
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

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div
          className={`premium-panel border ${
            runtimeHealthSummary.totalPnl !== undefined
              ? runtimeHealthSummary.totalPnl >= 0
                ? 'border-emerald-500/25'
                : 'border-rose-500/25'
              : 'border-slate-700/70'
          }`}
        >
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Runtime P&amp;L</p>
          <p
            className={`mt-1 text-2xl font-semibold ${
              runtimeHealthSummary.totalPnl !== undefined
                ? runtimeHealthSummary.totalPnl >= 0
                  ? 'text-emerald-300'
                  : 'text-rose-300'
                : 'text-slate-200'
            }`}
          >
            {runtimeHealthSummary.totalPnl !== undefined
              ? `$${runtimeHealthSummary.totalPnl.toFixed(2)}`
              : '—'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Scope: {runtimeHealthSummary.scopedCount > 0 ? runtimeHealthSummary.scopedCount : 0}{' '}
            runtime{runtimeHealthSummary.scopedCount === 1 ? '' : 's'}
          </p>
        </div>

        <div className="premium-panel border border-slate-700/70">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Open Positions</p>
          <p className="mt-1 text-2xl font-semibold text-cyan-200">
            {runtimeHealthSummary.totalOpenPositions !== undefined
              ? runtimeHealthSummary.totalOpenPositions
              : '—'}
          </p>
          <p className="mt-1 text-xs text-slate-500">Aggregated across active runtime scope</p>
        </div>

        <div className="premium-panel border border-slate-700/70">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Longest Uptime</p>
          <p className="mt-1 text-2xl font-semibold text-white">
            {formatRuntimeDuration(runtimeHealthSummary.longestUptimeSeconds)}
          </p>
          <p className="mt-1 text-xs text-slate-500">Longest live runtime currently tracked</p>
        </div>

        <div
          className={`premium-panel border ${
            heartbeatTone.tone === 'live'
              ? 'border-emerald-500/30'
              : heartbeatTone.tone === 'delayed'
                ? 'border-amber-500/30'
                : heartbeatTone.tone === 'stale'
                  ? 'border-rose-500/30'
                  : 'border-slate-700/70'
          }`}
        >
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Last Heartbeat</p>
          <p className="mt-1 text-2xl font-semibold text-white">
            {formatRuntimeTime(runtimeHealthSummary.latestRuntimeUpdate)}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {formatRelativeTime(runtimeHealthSummary.latestRuntimeUpdate)}
          </p>
          <p
            className={`mt-1 text-xs font-medium ${
              heartbeatTone.tone === 'live'
                ? 'text-emerald-300'
                : heartbeatTone.tone === 'delayed'
                  ? 'text-amber-300'
                  : heartbeatTone.tone === 'stale'
                    ? 'text-rose-300'
                    : 'text-slate-400'
            }`}
          >
            {heartbeatTone.label}
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
        openPositions={digestOpenPositions}
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
            const strategyHeartbeatAt = status.runtimeUpdatedAt || status.updatedAt;
            const strategyHeartbeat = resolveHeartbeatTone(strategyHeartbeatAt, webSocketConnected);
            const showStaleHeartbeatBadge =
              (status.status === 'running' || status.status === 'starting') &&
              strategyHeartbeat.tone === 'stale';
            const lastAction = strategyActivity.get(strategy.id);
            const trendPoints = heartbeatTrend.get(strategy.id) || [];
            const trendSvgPoints = buildSparklinePoints(trendPoints, 76, 18);
            const lastActionLabel = lastAction
              ? `${lastAction.label} · ${formatRelativeTime(lastAction.at)}`
              : status.startedAt
                ? `Runtime started · ${formatRelativeTime(status.startedAt)}`
                : 'No successful action recorded';

            return (
              <div
                key={strategy.id}
                tabIndex={0}
                onFocus={() => {
                  setFocusedCardId(strategy.id);
                }}
                onBlur={() => setFocusedCardId(null)}
                onKeyDown={(event) => handleStrategyCardKeyDown(event, strategy, status)}
                className={`premium-panel premium-panel-hover ${compactCards ? 'p-4' : 'p-6'} transition-all duration-300 focus:outline-none ${
                  status.status === 'running'
                    ? 'border-emerald-500/40 shadow-lg shadow-emerald-900/20'
                    : ''
                } ${
                  focusedCardId === strategy.id
                    ? 'ring-2 ring-cyan-400/60 shadow-lg shadow-cyan-900/30'
                    : ''
                }`}
              >
                {/* Strategy Header */}
                <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <h3 className="text-2xl font-bold tracking-tight text-white">
                        {strategy.name}
                      </h3>
                      <span className="rounded-full border border-slate-700/70 bg-slate-950/45 px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide text-slate-300">
                        {strategy.category}
                      </span>
                    </div>
                    {!compactCards && (
                      <p className="mt-1 text-sm text-slate-400">{strategy.description}</p>
                    )}
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

                <div
                  className={`mb-4 flex flex-wrap items-center gap-2 ${compactCards ? '' : 'mt-1'}`}
                >
                  {showStaleHeartbeatBadge && (
                    <span className="rounded-full border border-rose-500/40 bg-rose-500/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-rose-200">
                      Stale heartbeat
                    </span>
                  )}
                  {strategyHeartbeat.tone === 'delayed' &&
                    (status.status === 'running' || status.status === 'starting') && (
                      <span className="rounded-full border border-amber-500/35 bg-amber-500/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-200">
                        Delayed heartbeat
                      </span>
                    )}
                  <span className="rounded-full border border-slate-700/70 bg-slate-950/55 px-2.5 py-1 text-[11px] font-medium text-slate-300">
                    {lastActionLabel}
                  </span>
                  <span
                    className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 ${
                      strategyHeartbeat.tone === 'live'
                        ? 'border-emerald-500/35 bg-emerald-500/10'
                        : strategyHeartbeat.tone === 'delayed'
                          ? 'border-amber-500/35 bg-amber-500/10'
                          : strategyHeartbeat.tone === 'stale'
                            ? 'border-rose-500/35 bg-rose-500/10'
                            : 'border-slate-700/70 bg-slate-950/55'
                    }`}
                    title="Heartbeat freshness trend (newest point is right-most)"
                  >
                    <svg
                      viewBox="0 0 76 18"
                      className="h-3.5 w-19"
                      role="img"
                      aria-label="Heartbeat latency trend"
                    >
                      <line x1="0" y1="17.5" x2="76" y2="17.5" stroke="rgba(148,163,184,0.24)" />
                      {trendSvgPoints ? (
                        <>
                          <polyline
                            fill="none"
                            stroke={
                              strategyHeartbeat.tone === 'live'
                                ? 'rgba(74,222,128,0.95)'
                                : strategyHeartbeat.tone === 'delayed'
                                  ? 'rgba(251,191,36,0.95)'
                                  : strategyHeartbeat.tone === 'stale'
                                    ? 'rgba(251,113,133,0.95)'
                                    : 'rgba(148,163,184,0.85)'
                            }
                            strokeWidth="1.8"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            points={trendSvgPoints}
                          />
                          {trendPoints.map((point, index) => {
                            const clamped = Math.min(
                              Math.max(point, 0),
                              HEARTBEAT_TREND_MAX_SECONDS
                            );
                            const stepX =
                              trendPoints.length > 1 ? 76 / (trendPoints.length - 1) : 76;
                            const x = index * stepX;
                            const y = (clamped / HEARTBEAT_TREND_MAX_SECONDS) * 18;

                            return (
                              <circle
                                key={`${strategy.id}-trend-${index}`}
                                cx={x}
                                cy={y}
                                r="1.7"
                                fill="rgba(248,250,252,0.95)"
                                opacity="0.92"
                              >
                                <title>{`Heartbeat sample ${index + 1}: ${clamped}s latency`}</title>
                              </circle>
                            );
                          })}
                        </>
                      ) : null}
                    </svg>
                    <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-300">
                      {strategyHeartbeat.tone}
                    </span>
                  </span>
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
                <div
                  className={`grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 ${compactCards ? 'mb-4' : 'mb-6'}`}
                >
                  <div className="rounded-2xl border border-slate-700/50 bg-slate-950/45 p-3.5">
                    <p className="text-slate-500 text-[11px] uppercase tracking-[0.16em]">
                      Z-Score Threshold
                    </p>
                    <p className="mt-1 text-lg font-semibold text-white">
                      {strategy.zscore_threshold}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-700/50 bg-slate-950/45 p-3.5">
                    <p className="text-slate-500 text-[11px] uppercase tracking-[0.16em]">
                      USD Per Trade
                    </p>
                    <p className="mt-1 text-lg font-semibold text-white">
                      ${strategy.usd_per_trade}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-700/50 bg-slate-950/45 p-3.5">
                    <p className="text-slate-500 text-[11px] uppercase tracking-[0.16em]">
                      Max Positions
                    </p>
                    <p className="mt-1 text-lg font-semibold text-white">
                      {strategy.max_positions}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-700/50 bg-slate-950/45 p-3.5">
                    <p className="text-slate-500 text-[11px] uppercase tracking-[0.16em]">
                      Max Drawdown
                    </p>
                    <p className="mt-1 text-lg font-semibold text-white">
                      {strategy.max_drawdown_pct}%
                    </p>
                  </div>
                </div>

                <div
                  className={`grid grid-cols-1 gap-4 sm:grid-cols-3 ${compactCards ? 'mb-4' : 'mb-6'}`}
                >
                  <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-3.5">
                    <p className="text-cyan-200 text-[11px] uppercase tracking-[0.16em]">
                      Runtime Network
                    </p>
                    <p className="mt-1 text-lg font-semibold capitalize text-white">
                      {strategy.runtime_network || status.network || 'testnet'}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-3.5">
                    <p className="text-cyan-200 text-[11px] uppercase tracking-[0.16em]">
                      Subaccount
                    </p>
                    <p className="mt-1 text-lg font-semibold text-white">
                      #{status.runtimeSubaccount ?? strategy.runtime_subaccount ?? 0}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-3.5">
                    <p className="text-cyan-200 text-[11px] uppercase tracking-[0.16em]">
                      Allocated Capital
                    </p>
                    <p className="mt-1 text-lg font-semibold text-white">
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
                {!compactCards && (
                  <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    <div className="rounded-xl border border-cyan-500/25 bg-cyan-500/10 p-3.5">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200">
                        Trades
                      </p>
                      <p className="mt-1 text-lg font-semibold text-cyan-50">
                        {status.tradesExecuted ?? '—'}
                      </p>
                    </div>
                    <div
                      className={`rounded-xl border p-3.5 ${
                        status.pnl !== undefined
                          ? status.pnl > 0
                            ? 'border-emerald-600/40 bg-emerald-900/15'
                            : status.pnl < 0
                              ? 'border-rose-600/40 bg-rose-900/15'
                              : 'border-slate-700/60 bg-slate-900/45'
                          : 'border-slate-700/60 bg-slate-900/45'
                      }`}
                    >
                      <p
                        className={`text-[11px] uppercase tracking-[0.16em] ${
                          status.pnl !== undefined
                            ? status.pnl > 0
                              ? 'text-emerald-300'
                              : status.pnl < 0
                                ? 'text-rose-300'
                                : 'text-slate-300'
                            : 'text-slate-400'
                        }`}
                      >
                        Live P&amp;L
                      </p>
                      <p
                        className={`mt-1 text-lg font-semibold ${
                          status.pnl !== undefined
                            ? status.pnl > 0
                              ? 'text-emerald-100'
                              : status.pnl < 0
                                ? 'text-rose-100'
                                : 'text-slate-100'
                            : 'text-slate-400'
                        }`}
                      >
                        {status.pnl !== undefined ? `$${status.pnl.toFixed(2)}` : '—'}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-3.5">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">
                        Win Rate
                      </p>
                      <p className="mt-1 font-mono text-sm text-slate-100">
                        {status.winRate !== undefined ? `${status.winRate.toFixed(1)}%` : '—'}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-3.5">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">
                        Open Positions
                      </p>
                      <p className="mt-1 font-mono text-sm text-slate-100">
                        {status.openPositions ?? '—'}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-3.5">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">
                        Runtime Uptime
                      </p>
                      <p className="mt-1 font-mono text-sm text-slate-100">
                        {formatRuntimeDuration(status.uptimeSeconds)}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-3.5">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">
                        Last Runtime Update
                      </p>
                      <p className="mt-1 font-mono text-sm text-slate-100">
                        {formatRuntimeTime(status.runtimeUpdatedAt || status.updatedAt)}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-3.5">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">
                        Started At
                      </p>
                      <p className="mt-1 font-mono text-sm text-slate-100">
                        {status.startedAt ? formatRuntimeTime(status.startedAt) : '—'}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-3.5">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">
                        Status Sync
                      </p>
                      <p className="mt-1 font-mono text-sm text-slate-100">
                        {formatRuntimeTime(status.updatedAt)}
                      </p>
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="sticky bottom-2 z-10 mt-2 rounded-2xl border border-slate-700/60 bg-slate-950/70 p-2 backdrop-blur-sm">
                  <div className="flex flex-wrap items-center gap-2">
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
                            : 'bg-emerald-600 hover:bg-emerald-700 text-white';

                      return (
                        <button
                          type="button"
                          onClick={() => void handleRuntimeToggle(strategy)}
                          disabled={pendingAction !== undefined}
                          aria-label={`${buttonLabel} for ${strategy.name}`}
                          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-80 ${buttonClass}`}
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
                      type="button"
                      onClick={() => handleEditConfig(strategy)}
                      aria-label={`Configure ${strategy.name}`}
                      className="inline-flex items-center gap-2 rounded-xl border border-cyan-500/40 bg-cyan-500/15 px-4 py-2 text-sm font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/25"
                    >
                      <Settings className="w-4 h-4" />
                      Configure
                    </button>

                    {/* Backtest Button */}
                    <button
                      type="button"
                      onClick={() => handleRunBacktest(strategy)}
                      aria-label={`Run backtest for ${strategy.name}`}
                      className="inline-flex items-center gap-2 rounded-xl border border-indigo-500/40 bg-indigo-500/15 px-4 py-2 text-sm font-semibold text-indigo-100 transition-colors hover:bg-indigo-500/25"
                    >
                      <BarChart3 className="w-4 h-4" />
                      Backtest
                    </button>

                    {/* Copy Button */}
                    <button
                      type="button"
                      onClick={() => void handleDuplicateStrategy(strategy)}
                      aria-label={`Duplicate ${strategy.name}`}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-700/70 bg-slate-900/70 px-4 py-2 text-sm font-semibold text-white transition-colors hover:border-cyan-500/35 hover:bg-slate-900"
                    >
                      <Copy className="w-4 h-4" />
                      Duplicate
                    </button>

                    {/* Delete Button */}
                    {deleteConfirmId === strategy.id ? (
                      <>
                        <button
                          type="button"
                          onClick={() => void handleDeleteStrategy(strategy)}
                          aria-label={`Confirm delete ${strategy.name}`}
                          className="inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-500"
                        >
                          <Trash2 className="w-4 h-4" />
                          Confirm Delete
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteConfirmId(null)}
                          aria-label={`Cancel delete ${strategy.name}`}
                          className="inline-flex items-center gap-2 rounded-xl border border-slate-700/70 bg-slate-900/70 px-4 py-2 text-sm font-semibold text-white transition-colors hover:border-cyan-500/35 hover:bg-slate-900"
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setDeleteConfirmId(strategy.id)}
                        aria-label={`Delete ${strategy.name}`}
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-700/70 bg-slate-900/70 px-4 py-2 text-sm font-semibold text-white transition-colors hover:border-red-500/40 hover:bg-red-900/20"
                      >
                        <Trash2 className="w-4 h-4" />
                        Delete
                      </button>
                    )}
                  </div>
                </div>

                <p className="mt-3 text-[11px] text-slate-500">
                  Shortcuts while card is focused: <span className="text-slate-300">S</span>{' '}
                  start/stop, <span className="text-slate-300">C</span> configure,{' '}
                  <span className="text-slate-300">B</span> backtest,{' '}
                  <span className="text-slate-300">D</span> duplicate,{' '}
                  <span className="text-slate-300">Delete</span> remove.
                </p>

                {/* AI Parameter Advisor */}
                <div className="mt-6 border-t border-slate-700/60 pt-5">
                  <AIStrategyAdvisor
                    strategy={strategy}
                    lastError={status.lastError}
                    recentBacktests={strategyBacktests.get(strategy.id) ?? []}
                    onApplyParams={(params) => handleApplySuggestedParams(strategy, params)}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>

      {startDialogStrategy &&
        typeof document !== 'undefined' &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div
              className="w-full max-w-3xl rounded-3xl border border-slate-700 bg-slate-900 shadow-2xl shadow-black/40"
              role="dialog"
              aria-modal="true"
              aria-labelledby="start-runtime-dialog-title"
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  closeStartDialog();
                }
              }}
            >
              <div className="flex items-center justify-between border-b border-slate-800 px-6 py-5">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Live Launch</p>
                  <h2
                    id="start-runtime-dialog-title"
                    className="mt-2 text-2xl font-semibold text-white"
                  >
                    Start {startDialogStrategy.name}
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={() => closeStartDialog()}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-700 text-slate-300 transition hover:border-slate-500 hover:text-white"
                  aria-label="Close launch dialog"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-6 px-6 py-6">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-200">
                      Environment
                    </label>
                    <select
                      ref={startDialogNetworkRef}
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
                    type="button"
                    onClick={() => closeStartDialog()}
                    className="rounded-2xl border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
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
            <div
              className="bg-slate-800 rounded-lg border border-slate-700 max-w-2xl w-full max-h-[90vh] overflow-y-auto"
              role="dialog"
              aria-modal="true"
              aria-labelledby="strategy-config-dialog-title"
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  closeConfigDialog();
                }
              }}
            >
              {/* Modal Header */}
              <div className="sticky top-0 bg-slate-800 border-b border-slate-700 p-6 flex items-center justify-between">
                <h2 id="strategy-config-dialog-title" className="text-2xl font-bold text-white">
                  Configure Strategy
                </h2>
                <button
                  type="button"
                  onClick={closeConfigDialog}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-700 text-gray-400 transition hover:border-slate-500 hover:text-white"
                  aria-label="Close strategy configuration"
                >
                  <X className="h-4 w-4" />
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
                        ref={configNameInputRef}
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
                    type="button"
                    onClick={handleSaveConfig}
                    className="flex-1 px-4 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors"
                  >
                    ✅ Save Configuration
                  </button>
                  <button
                    type="button"
                    onClick={closeConfigDialog}
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
