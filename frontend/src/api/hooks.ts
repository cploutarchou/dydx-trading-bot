// Custom React Query Hooks for API Endpoints
// Provides optimized data fetching with loading states, error handling, and caching

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../api';
import { enhancedApiClient as apiClient } from './enhancedClient';
import { cacheUtils, queryConfigs, queryKeys } from './queryClient';
import type {
    BacktestConfig,
    BotInstance,
    BotJob,
    CreateBotRequest,
    ListAlertsParams,
    ListBacktestsParams,
    ListBotsParams,
    ListTradesParams,
    QuickDeployBotRequest,
    StartBotRequest,
    UpdateBotRequest,
    User,
} from './types';

interface ManagedWebSocketOptions {
  enabled: boolean;
  connectSocket: () => WebSocket;
  onMessage: (_parsed: unknown) => void;
  onOpen?: (_socket: WebSocket) => (() => void) | void;
  staleAfterMs?: number;
  onStale?: () => Promise<void> | void;
}

const useManagedWebSocket = ({
  enabled,
  connectSocket,
  onMessage,
  onOpen,
  staleAfterMs = 15000,
  onStale,
}: ManagedWebSocketOptions) => {
  const [isConnected, setIsConnected] = useState(false);
  const [socketError, setSocketError] = useState<Error | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const staleTimerRef = useRef<number | null>(null);
  const staleInFlightRef = useRef(false);

  useEffect(() => {
    if (!enabled) {
      setIsConnected(false);
      setSocketError(null);
      return;
    }

    let closedByEffect = false;
    let pausedForPageLifecycle = false;
    let shouldResumeAfterPageShow = false;
    let socket: WebSocket | null = null;
    let openCleanup: (() => void) | null = null;

    const clearStaleTimer = () => {
      if (staleTimerRef.current !== null) {
        window.clearTimeout(staleTimerRef.current);
        staleTimerRef.current = null;
      }
    };

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const clearOpenCleanup = () => {
      if (openCleanup) {
        openCleanup();
        openCleanup = null;
      }
    };

    const scheduleStaleCheck = () => {
      clearStaleTimer();
      if (!staleAfterMs || staleAfterMs <= 0) {
        return;
      }

      staleTimerRef.current = window.setTimeout(() => {
        staleTimerRef.current = null;

        if (closedByEffect || !socket || socket.readyState !== WebSocket.OPEN) {
          return;
        }

        if (!staleInFlightRef.current) {
          staleInFlightRef.current = true;
          Promise.resolve(onStale?.())
            .catch((error) => {
              console.warn('Failed websocket stale resync', error);
            })
            .finally(() => {
              staleInFlightRef.current = false;
            });
        }

        try {
          socket.close();
        } catch (error) {
          console.warn('Failed to close stale websocket', error);
        }
      }, staleAfterMs);
    };

    const scheduleReconnect = () => {
      if (closedByEffect || reconnectTimerRef.current !== null) {
        return;
      }
      const attempts = Math.min(reconnectAttemptRef.current, 4);
      const delayMs = Math.min(1000 * 2 ** attempts, 15000);
      reconnectAttemptRef.current += 1;
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        connect();
      }, delayMs);
    };

    const connect = () => {
      clearReconnectTimer();
      clearOpenCleanup();

      try {
        socket = connectSocket();
      } catch (error) {
        setSocketError(error instanceof Error ? error : new Error('Failed to open websocket'));
        setIsConnected(false);
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        reconnectAttemptRef.current = 0;
        setIsConnected(true);
        setSocketError(null);
        const activeSocket = socket;
        if (!activeSocket) {
          return;
        }
        openCleanup = onOpen?.(activeSocket) ?? null;
        scheduleStaleCheck();
      };

      socket.onmessage = (event) => {
        scheduleStaleCheck();
        try {
          onMessage(JSON.parse(event.data) as unknown);
        } catch (error) {
          console.warn('Failed to parse websocket payload', error);
        }
      };

      socket.onerror = () => {
        setSocketError(new Error('Live websocket connection error'));
      };

      socket.onclose = () => {
        setIsConnected(false);
        clearStaleTimer();
        clearOpenCleanup();
        if (!closedByEffect && !pausedForPageLifecycle) {
          scheduleReconnect();
        }
      };
    };

    const handleOnline = () => {
      if (closedByEffect || !socket || socket.readyState === WebSocket.OPEN) {
        return;
      }
      clearReconnectTimer();
      connect();
    };

    const handlePageHide = () => {
      if (closedByEffect) {
        return;
      }

      shouldResumeAfterPageShow =
        socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING;
      pausedForPageLifecycle = shouldResumeAfterPageShow;

      clearReconnectTimer();
      clearStaleTimer();
      clearOpenCleanup();

      if (socket && socket.readyState !== WebSocket.CLOSED) {
        try {
          socket.close(1000, 'pagehide');
        } catch (error) {
          console.warn('Failed to close websocket on pagehide', error);
        }
      }
    };

    const handlePageShow = () => {
      if (closedByEffect || !pausedForPageLifecycle) {
        return;
      }

      pausedForPageLifecycle = false;
      if (!shouldResumeAfterPageShow) {
        return;
      }

      shouldResumeAfterPageShow = false;
      reconnectAttemptRef.current = 0;
      clearReconnectTimer();
      connect();
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('pagehide', handlePageHide);
    window.addEventListener('pageshow', handlePageShow);
    connect();

    return () => {
      closedByEffect = true;
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('pagehide', handlePageHide);
      window.removeEventListener('pageshow', handlePageShow);
      clearReconnectTimer();
      clearStaleTimer();
      clearOpenCleanup();
      staleInFlightRef.current = false;
      reconnectAttemptRef.current = 0;
      setIsConnected(false);
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [connectSocket, enabled, onMessage, onOpen, onStale, staleAfterMs]);

  return { isConnected, socketError };
};

// ==================== Authentication Hooks ====================

export function useCurrentUser() {
  return useQuery({
    queryKey: queryKeys.currentUser,
    queryFn: () => apiClient.getCurrentUser(),
    ...queryConfigs.user,
    enabled: apiClient.isAuthenticated(),
  });
}

export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      username,
      password,
      turnstileToken,
    }: {
      username: string;
      password: string;
      turnstileToken?: string;
    }) => apiClient.login(username, password, turnstileToken),
    onSuccess: () => {
      // Invalidate user queries after successful login
      queryClient.invalidateQueries({ queryKey: ['auth'] });
      queryClient.invalidateQueries({ queryKey: ['bots'] });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => {
      apiClient.logout();
      return Promise.resolve();
    },
    onSuccess: () => {
      // Clear all cached data on logout
      queryClient.clear();
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: ({
      username,
      email,
      password,
      invitationCode,
      turnstileToken,
    }: {
      username: string;
      email: string;
      password: string;
      invitationCode?: string;
      turnstileToken?: string;
    }) => apiClient.register(username, email, password, invitationCode, turnstileToken),
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (profile: Partial<User>) => apiClient.updateProfile(profile),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.currentUser });
    },
  });
}

// ==================== Bot Instance Hooks ====================

export function useBotInstances(params: ListBotsParams = {}) {
  return useQuery({
    queryKey: queryKeys.bots(params),
    queryFn: () => apiClient.listBotInstances(params),
    ...queryConfigs.trading,
  });
}

export function useBotInstance(instanceId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.bot(instanceId),
    queryFn: () => apiClient.getBotInstance(instanceId),
    ...queryConfigs.trading,
    enabled: enabled && !!instanceId,
  });
}

export function useBotStats(instanceId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.botStats(instanceId),
    queryFn: () => apiClient.getBotStats(instanceId),
    ...queryConfigs.trading,
    enabled: enabled && !!instanceId,
  });
}

export function useBotTrades(instanceId: string, params: ListTradesParams = {}) {
  return useQuery({
    queryKey: queryKeys.botTrades(instanceId, params),
    queryFn: () => apiClient.getBotTrades(instanceId, params),
    ...queryConfigs.trading,
    enabled: !!instanceId,
  });
}

export function useBotTradesInfinite(
  instanceId: string,
  params: Omit<ListTradesParams, 'offset'> = {}
) {
  return useInfiniteQuery({
    queryKey: queryKeys.botTrades(instanceId, params),
    queryFn: ({ pageParam = 0 }) =>
      apiClient.getBotTrades(instanceId, { ...params, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const hasMore = lastPage.data.length === (params.limit || 50);
      return hasMore ? allPages.length * (params.limit || 50) : undefined;
    },
    ...queryConfigs.trading,
    enabled: !!instanceId,
  });
}

export function useCreateBotInstance() {
  return useMutation({
    mutationFn: (config: CreateBotRequest) => apiClient.createBotInstance(config),
    onSuccess: () => {
      cacheUtils.invalidateBotQueries();
    },
  });
}

export function useUpdateBotInstance(instanceId: string) {
  return useMutation({
    mutationFn: (updates: UpdateBotRequest) => apiClient.updateBotInstance(instanceId, updates),
    onSuccess: () => {
      cacheUtils.invalidateBotQueries(instanceId);
    },
  });
}

export function useStartBotInstance() {
  return useMutation({
    mutationFn: ({ instanceId, config }: { instanceId: string; config?: StartBotRequest }) =>
      apiClient.startBotInstance(instanceId, config),
    onSuccess: (_, { instanceId }) => {
      cacheUtils.invalidateBotQueries(instanceId);
    },
  });
}

export function useStopBotInstance() {
  return useMutation({
    mutationFn: (instanceId: string) => apiClient.stopBotInstance(instanceId),
    onSuccess: (_, instanceId) => {
      cacheUtils.invalidateBotQueries(instanceId);
    },
  });
}

export function useRestartBotInstance() {
  return useMutation({
    mutationFn: (instanceId: string) => apiClient.restartBotInstance(instanceId),
    onSuccess: (_, instanceId) => {
      cacheUtils.invalidateBotQueries(instanceId);
    },
  });
}

export function useDeleteBotInstance() {
  return useMutation({
    mutationFn: (instanceId: string) => apiClient.deleteBotInstance(instanceId),
    onSuccess: () => {
      cacheUtils.invalidateBotQueries();
    },
  });
}

export function useQuickDeployBot() {
  return useMutation({
    mutationFn: ({
      instanceName,
      autoStart,
      config,
    }: {
      instanceName: string;
      autoStart: boolean;
      config: QuickDeployBotRequest;
    }) => apiClient.quickDeployBot(instanceName, autoStart, config as Record<string, unknown>),
    onSuccess: () => {
      cacheUtils.invalidateBotQueries();
    },
  });
}

// ==================== Real-Time Data Hooks ====================

export function useBotPositions(instanceId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.botPositions(instanceId),
    queryFn: () => apiClient.getCurrentPositions(instanceId),
    ...queryConfigs.realtime,
    enabled: enabled && !!instanceId,
  });
}

export function useBotPosition(instanceId: string, positionId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.botPosition(instanceId, positionId),
    queryFn: () => apiClient.getPosition(instanceId, positionId),
    ...queryConfigs.realtime,
    enabled: enabled && !!instanceId && !!positionId,
  });
}

export function useBotRealtimeStats(instanceId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.botRealtimeStats(instanceId),
    queryFn: () => apiClient.getRealtimeStats(instanceId),
    ...queryConfigs.realtime,
    enabled: enabled && !!instanceId,
  });
}

export function useBotRuntimeStatsStream(instanceId: string, enabled: boolean = true) {
  const [data, setData] = useState<Record<string, unknown> | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const [bootstrapError, setBootstrapError] = useState<Error | null>(null);

  const extractStatsPayload = useCallback((payload: unknown): Record<string, unknown> | null => {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      return null;
    }

    const record = payload as Record<string, unknown>;
    if (record.type === 'initial_state') {
      const dataRecord =
        record.data && typeof record.data === 'object' && !Array.isArray(record.data)
          ? (record.data as Record<string, unknown>)
          : null;
      const statsRecord =
        dataRecord?.stats &&
        typeof dataRecord.stats === 'object' &&
        !Array.isArray(dataRecord.stats)
          ? (dataRecord.stats as Record<string, unknown>)
          : null;
      return statsRecord;
    }

    if (record.type === 'stats' || record.type === 'stats_updated') {
      const dataRecord =
        record.data && typeof record.data === 'object' && !Array.isArray(record.data)
          ? (record.data as Record<string, unknown>)
          : null;
      return dataRecord;
    }

    return null;
  }, []);

  useEffect(() => {
    if (!instanceId || !enabled) {
      setData(undefined);
      setIsLoading(false);
      setBootstrapError(null);
      return;
    }

    let cancelled = false;

    const bootstrap = async () => {
      setIsLoading(true);
      try {
        const result = await apiClient.getBotStats(instanceId);
        if (!cancelled && result && typeof result === 'object') {
          setData(result as Record<string, unknown>);
          setBootstrapError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setBootstrapError(
            error instanceof Error ? error : new Error('Failed to fetch bot runtime stats')
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, [enabled, instanceId]);

  const { isConnected, socketError } = useManagedWebSocket({
    enabled: enabled && !!instanceId,
    connectSocket: useCallback(() => api.connectBotRuntimeSocket(instanceId), [instanceId]),
    onMessage: useCallback(
      (parsed: unknown) => {
        const statsPayload = extractStatsPayload(parsed);
        if (statsPayload) {
          setData(statsPayload);
          setBootstrapError(null);
        }
      },
      [extractStatsPayload]
    ),
    onOpen: useCallback((socket: WebSocket) => {
      const requestStats = () => {
        if (socket.readyState !== WebSocket.OPEN) {
          return;
        }
        try {
          socket.send(JSON.stringify({ type: 'request_stats' }));
        } catch (error) {
          console.warn('Failed to request bot runtime stats over websocket', error);
        }
      };

      requestStats();
      const timerId = window.setInterval(requestStats, 5000);
      return () => {
        window.clearInterval(timerId);
      };
    }, []),
    onStale: useCallback(async () => {
      if (!instanceId || !enabled) {
        return;
      }
      try {
        const result = await apiClient.getBotStats(instanceId);
        if (result && typeof result === 'object') {
          setData(result as Record<string, unknown>);
          setBootstrapError(null);
        }
      } catch (error) {
        setBootstrapError(
          error instanceof Error ? error : new Error('Failed to refresh bot runtime stats')
        );
      }
    }, [enabled, instanceId]),
  });

  const combinedError = socketError ?? bootstrapError;
  return {
    data,
    error: combinedError,
    isError: combinedError !== null,
    isLoading,
    isSuccess: !!data,
    isConnected,
  };
}

export function useBotMarketData(instanceId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.botMarketData(instanceId),
    queryFn: () => apiClient.getMarketData(instanceId),
    ...queryConfigs.realtime,
    enabled: enabled && !!instanceId,
  });
}

export function useBotAlerts(instanceId: string, params: ListAlertsParams = {}) {
  return useQuery({
    queryKey: queryKeys.botAlerts(instanceId, params),
    queryFn: () => apiClient.getAlerts(instanceId, params),
    ...queryConfigs.trading,
    enabled: !!instanceId,
  });
}

export function useBotJobs(instanceId: string, days: number = 7, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.botJobs(instanceId, days),
    queryFn: async (): Promise<BotJob[]> => {
      const result = await apiClient.getBotJobs(instanceId, days);
      const raw = result as { jobs?: unknown; data?: { jobs?: unknown } };
      const jobs: unknown[] = Array.isArray(raw.jobs)
        ? (raw.jobs as unknown[])
        : Array.isArray((raw.data as { jobs?: unknown } | undefined)?.jobs)
          ? ((raw.data as { jobs: unknown[] }).jobs as unknown[])
          : [];
      return jobs.map((j): BotJob => {
        const job = (j && typeof j === 'object' ? j : {}) as Record<string, unknown>;
        const rawPct =
          (job.progress_pct as number | undefined) ??
          (job.progress_percent as number | undefined) ??
          (job.progress as number | undefined) ??
          0;
        const pct = Math.min(
          100,
          Math.max(0, Number.isFinite(Number(rawPct)) ? Number(rawPct) : 0)
        );
        return {
          job_id: String(job.job_id ?? ''),
          job_type: String(job.job_type ?? ''),
          status: String(job.status ?? 'pending').toLowerCase() as BotJob['status'],
          progress_pct: pct,
          progress_percent: job.progress_percent as number | undefined,
          progress: job.progress as number | undefined,
          created_at: String(job.created_at ?? new Date().toISOString()),
          updated_at: String(job.updated_at ?? new Date().toISOString()),
          started_at: job.started_at ? String(job.started_at) : undefined,
          completed_at: job.completed_at ? String(job.completed_at) : undefined,
          execution_time_ms:
            job.execution_time_ms !== undefined ? Number(job.execution_time_ms) : undefined,
          process_id: job.process_id !== undefined ? Number(job.process_id) : undefined,
          error_message: job.error_message ? String(job.error_message) : undefined,
          error_traceback: job.error_traceback ? String(job.error_traceback) : undefined,
          cancellation_reason: job.cancellation_reason
            ? String(job.cancellation_reason)
            : undefined,
          metadata: job.metadata as Record<string, unknown> | undefined,
          result: job.result as Record<string, unknown> | undefined,
          config: job.config as Record<string, unknown> | undefined,
          retry_count: job.retry_count !== undefined ? Number(job.retry_count) : undefined,
          max_retries: job.max_retries !== undefined ? Number(job.max_retries) : undefined,
        };
      });
    },
    ...queryConfigs.trading,
    enabled: enabled && !!instanceId,
  });
}

// ==================== Backtest Hooks ====================

export function useBacktests(params: ListBacktestsParams = {}) {
  return useQuery({
    queryKey: queryKeys.backtests(params),
    queryFn: () => apiClient.listBacktests(params),
    ...queryConfigs.historical,
  });
}

export function useBacktest(runId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.backtest(runId),
    queryFn: () => apiClient.getBacktest(runId),
    ...queryConfigs.historical,
    enabled: enabled && !!runId,
  });
}

export function useBacktestStatus(runId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.backtestStatus(runId),
    queryFn: () => apiClient.getBacktestStatus(runId),
    ...queryConfigs.realtime,
    enabled: enabled && !!runId,
  });
}

export function useBacktestTrades(runId: string, limit: number = 50, offset: number = 0) {
  return useQuery({
    queryKey: queryKeys.backtestTrades(runId, { limit, offset }),
    queryFn: () => apiClient.getBacktestTrades(runId, limit, offset),
    ...queryConfigs.historical,
    enabled: !!runId,
  });
}

export function useBacktestMetrics(runId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.backtestMetrics(runId),
    queryFn: () => apiClient.getBacktestMetrics(runId),
    ...queryConfigs.historical,
    enabled: enabled && !!runId,
  });
}

export function useCreateBacktest() {
  return useMutation({
    mutationFn: (config: BacktestConfig) => apiClient.createBacktest(config),
    onSuccess: () => {
      cacheUtils.invalidateBacktestQueries();
    },
  });
}

export function useDeleteBacktest() {
  return useMutation({
    mutationFn: (runId: string) => apiClient.deleteBacktest(runId),
    onSuccess: () => {
      cacheUtils.invalidateBacktestQueries();
    },
  });
}

export function useCancelBacktest() {
  return useMutation({
    mutationFn: (runId: string) => apiClient.cancelBacktest(runId),
    onSuccess: (_, runId) => {
      cacheUtils.invalidateBacktestQueries(runId);
    },
  });
}

export function useCompareBacktests() {
  return useMutation({
    mutationFn: ({ runIds, metrics }: { runIds: string[]; metrics: string[] }) =>
      apiClient.compareBacktests(runIds, metrics),
  });
}

// ==================== System Hooks ====================

export function useSystemStatus() {
  return useQuery({
    queryKey: queryKeys.systemStatus,
    queryFn: () => apiClient.getSystemStatus(),
    ...queryConfigs.realtime,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => apiClient.getHealth(),
    ...queryConfigs.realtime,
    retry: 1, // Health checks should fail fast
  });
}

export function useReadiness() {
  return useQuery({
    queryKey: queryKeys.readiness,
    queryFn: () => apiClient.getReadiness(),
    ...queryConfigs.realtime,
    retry: 1,
  });
}

export function useBotCapabilities() {
  return useQuery({
    queryKey: queryKeys.botCapabilities,
    queryFn: () => apiClient.getCapabilities(),
    ...queryConfigs.static,
  });
}

export function useRuntimeDBConfig(enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.runtimeDbConfig,
    queryFn: () => apiClient.getRuntimeDBConfig(),
    ...queryConfigs.static,
    enabled,
  });
}

export function useInterruptedBacktests(
  limit: number = 50,
  admin: boolean = false,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: queryKeys.backtestInterrupted(admin, limit),
    queryFn: () => apiClient.getInterruptedBacktests(limit, admin),
    ...queryConfigs.trading,
    enabled,
  });
}

export function useReconcileInterruptedBacktests() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ dryRun = true, admin = false }: { dryRun?: boolean; admin?: boolean }) =>
      apiClient.reconcileInterruptedBacktests(dryRun, admin),
    onSuccess: (_, { admin }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.backtestInterrupted(admin) });
    },
  });
}

// ==================== Advanced Composite Hooks ====================

/**
 * Combined hook for bot overview data
 * Fetches bot instance, stats, and current positions in parallel
 */
export function useBotOverview(instanceId: string) {
  const botQuery = useBotInstance(instanceId);
  const statsQuery = useBotStats(instanceId, botQuery.isSuccess);
  const positionsQuery = useBotPositions(instanceId, botQuery.isSuccess);
  const realtimeQuery = useBotRealtimeStats(instanceId, botQuery.isSuccess);

  return {
    bot: botQuery,
    stats: statsQuery,
    positions: positionsQuery,
    realtime: realtimeQuery,
    isLoading:
      botQuery.isLoading ||
      statsQuery.isLoading ||
      positionsQuery.isLoading ||
      realtimeQuery.isLoading,
    isError:
      botQuery.isError || statsQuery.isError || positionsQuery.isError || realtimeQuery.isError,
    error: botQuery.error || statsQuery.error || positionsQuery.error || realtimeQuery.error,
    refetchAll: () => {
      botQuery.refetch();
      statsQuery.refetch();
      positionsQuery.refetch();
      realtimeQuery.refetch();
    },
  };
}

/**
 * Combined hook for backtest analysis
 * Fetches backtest details, metrics, and trades
 */
export function useBacktestAnalysis(runId: string) {
  const backtestQuery = useBacktest(runId);
  const metricsQuery = useBacktestMetrics(runId, backtestQuery.isSuccess);
  const tradesQuery = useBacktestTrades(runId, 100, 0);

  return {
    backtest: backtestQuery,
    metrics: metricsQuery,
    trades: tradesQuery,
    isLoading: backtestQuery.isLoading || metricsQuery.isLoading || tradesQuery.isLoading,
    isError: backtestQuery.isError || metricsQuery.isError || tradesQuery.isError,
    error: backtestQuery.error || metricsQuery.error || tradesQuery.error,
    refetchAll: () => {
      backtestQuery.refetch();
      metricsQuery.refetch();
      tradesQuery.refetch();
    },
  };
}

/**
 * Hook for polling backtest progress
 * Automatically stops polling when backtest is complete
 */
export function useBacktestProgress(runId: string) {
  const normalizeStatus = (status: unknown): string =>
    String(status || '')
      .trim()
      .toUpperCase();
  const [data, setData] = useState<Record<string, unknown> | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const [bootstrapError, setBootstrapError] = useState<Error | null>(null);
  const [lastSocketEvent, setLastSocketEvent] = useState<Record<string, unknown> | null>(null);
  const isTerminalStatus = useCallback((status: unknown): boolean => {
    return ['COMPLETED', 'FAILED', 'TIMED_OUT', 'CANCELLED', 'STALLED'].includes(
      normalizeStatus(status)
    );
  }, []);

  const normalizeProgressPercent = useCallback((data: unknown): number => {
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
    const rawProgress =
      record.progress_percent ?? record.progress_pct ?? record.progress ?? record.percent_complete;

    if (typeof rawProgress !== 'number' && typeof rawProgress !== 'string') {
      return 0;
    }

    const parsed = Number(rawProgress);
    if (!Number.isFinite(parsed)) {
      return 0;
    }

    const normalized = Math.abs(parsed) <= 1 ? parsed * 100 : parsed;
    return Math.min(100, Math.max(0, normalized));
  }, []);

  const extractCurrentPair = useCallback((data: unknown): string | null => {
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
    const pair = record.current_pair ?? record.current_market ?? record.market;
    return typeof pair === 'string' && pair.trim().length > 0 ? pair : null;
  }, []);

  const extractEtaSeconds = useCallback((data: unknown): number | null => {
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
    const rawEta =
      record.estimated_completion_seconds ?? record.eta_seconds ?? record.remaining_seconds;
    if (typeof rawEta !== 'number' && typeof rawEta !== 'string') {
      return null;
    }
    const parsed = Number(rawEta);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
  }, []);

  const mergeProgressData = useCallback(
    (
      current: Record<string, unknown> | undefined,
      patch: Record<string, unknown>
    ): Record<string, unknown> => {
      const next = { ...(current || {}) };

      for (const [key, value] of Object.entries(patch)) {
        if (value !== undefined) {
          next[key] = value;
        }
      }

      return next;
    },
    []
  );

  const parseSocketPayload = useCallback(
    (payload: unknown): Record<string, unknown> | null => {
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
        return null;
      }

      const record = payload as Record<string, unknown>;
      const progress =
        record.progress_percent ??
        record.progress_pct ??
        record.progress ??
        record.percent_complete;
      const message =
        typeof record.message === 'string'
          ? record.message
          : typeof record.type === 'string'
            ? record.type
            : undefined;

      return {
        run_id: typeof record.run_id === 'string' ? record.run_id : runId,
        status: typeof record.status === 'string' ? normalizeStatus(record.status) : undefined,
        progress_percent:
          typeof progress === 'number' || typeof progress === 'string'
            ? normalizeProgressPercent({ progress_percent: progress })
            : undefined,
        current_pair:
          typeof record.current_pair === 'string'
            ? record.current_pair
            : typeof record.current_market === 'string'
              ? record.current_market
              : typeof record.market === 'string'
                ? record.market
                : undefined,
        estimated_completion_seconds:
          typeof record.estimated_completion_seconds === 'number' ||
          typeof record.estimated_completion_seconds === 'string'
            ? Number(record.estimated_completion_seconds)
            : typeof record.eta_seconds === 'number' || typeof record.eta_seconds === 'string'
              ? Number(record.eta_seconds)
              : typeof record.remaining_seconds === 'number' ||
                  typeof record.remaining_seconds === 'string'
                ? Number(record.remaining_seconds)
                : undefined,
        message,
        details:
          record.details && typeof record.details === 'object' && !Array.isArray(record.details)
            ? record.details
            : undefined,
        total_pnl:
          typeof record.total_pnl === 'number' || typeof record.total_pnl === 'string'
            ? Number(record.total_pnl)
            : undefined,
        total_trades:
          typeof record.total_trades === 'number' || typeof record.total_trades === 'string'
            ? Number(record.total_trades)
            : undefined,
        win_rate:
          typeof record.win_rate === 'number' || typeof record.win_rate === 'string'
            ? Number(record.win_rate)
            : undefined,
        sharpe_ratio:
          typeof record.sharpe_ratio === 'number' || typeof record.sharpe_ratio === 'string'
            ? Number(record.sharpe_ratio)
            : undefined,
        max_drawdown_pct:
          typeof record.max_drawdown_pct === 'number' || typeof record.max_drawdown_pct === 'string'
            ? Number(record.max_drawdown_pct)
            : undefined,
        profit_factor:
          typeof record.profit_factor === 'number' || typeof record.profit_factor === 'string'
            ? Number(record.profit_factor)
            : undefined,
        error: typeof record.error === 'string' ? record.error : undefined,
        error_message: typeof record.error_message === 'string' ? record.error_message : undefined,
        progress_source: 'websocket',
        updated_at:
          typeof record.timestamp === 'string' ? record.timestamp : new Date().toISOString(),
      };
    },
    [normalizeProgressPercent, runId]
  );

  useEffect(() => {
    if (!runId) {
      setData(undefined);
      setIsLoading(false);
      setBootstrapError(null);
      return;
    }

    let cancelled = false;

    const bootstrap = async () => {
      setIsLoading(true);
      try {
        const result = await apiClient.getBacktestStatus(runId);
        if (!cancelled) {
          setData(result as unknown as Record<string, unknown>);
          setBootstrapError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setBootstrapError(
            error instanceof Error ? error : new Error('Failed to fetch backtest progress')
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, [runId]);

  const { isConnected, socketError } = useManagedWebSocket({
    enabled: !!runId,
    connectSocket: useCallback(() => api.connectBacktestSocket(runId), [runId]),
    onMessage: useCallback(
      (parsed: unknown) => {
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          setLastSocketEvent(parsed as Record<string, unknown>);
        }
        const patch = parseSocketPayload(parsed);
        if (!patch) {
          return;
        }

        setData((current) => mergeProgressData(current, patch));
        setBootstrapError(null);
      },
      [mergeProgressData, parseSocketPayload]
    ),
    onOpen: useCallback((socket: WebSocket) => {
      const requestStatus = () => {
        if (socket.readyState !== WebSocket.OPEN) {
          return;
        }

        try {
          socket.send(JSON.stringify({ type: 'request_status' }));
        } catch (error) {
          console.warn('Failed to request backtest status over websocket', error);
        }
      };

      requestStatus();
      const timerId = window.setInterval(requestStatus, 5000);
      return () => {
        window.clearInterval(timerId);
      };
    }, []),
    onStale: useCallback(async () => {
      if (!runId) {
        return;
      }
      try {
        const result = await apiClient.getBacktestStatus(runId);
        if (result && typeof result === 'object') {
          setData((current) =>
            mergeProgressData(current, {
              ...(result as Record<string, unknown>),
              progress_source: 'stale_resync',
            })
          );
          setBootstrapError(null);
        }
      } catch (error) {
        setBootstrapError(
          error instanceof Error ? error : new Error('Failed to refresh backtest progress')
        );
      }
    }, [mergeProgressData, runId]),
  });

  useEffect(() => {
    if (!runId || isConnected || isTerminalStatus(data?.status)) {
      return;
    }

    let cancelled = false;

    const pollStatus = async () => {
      try {
        const result = await apiClient.getBacktestStatus(runId);
        if (cancelled || !result || typeof result !== 'object') {
          return;
        }

        setData((current) =>
          mergeProgressData(current, {
            ...(result as Record<string, unknown>),
            progress_source: isConnected ? 'polling' : 'polling_recovery',
            checked_at:
              typeof result.checked_at === 'string' && result.checked_at.length > 0
                ? result.checked_at
                : new Date().toISOString(),
            updated_at:
              typeof result.updated_at === 'string' && result.updated_at.length > 0
                ? result.updated_at
                : new Date().toISOString(),
          })
        );
        setBootstrapError(null);
      } catch (error) {
        if (!cancelled) {
          setBootstrapError(
            error instanceof Error ? error : new Error('Failed to refresh backtest progress')
          );
        }
      }
    };

    void pollStatus();
    const timerId = window.setInterval(pollStatus, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timerId);
    };
  }, [data?.status, isConnected, isTerminalStatus, mergeProgressData, runId]);

  const resolvedData = data;
  const combinedError = socketError ?? bootstrapError;

  return {
    data: resolvedData,
    error: combinedError,
    isError: combinedError !== null,
    isLoading,
    isSuccess: !!resolvedData,
    isConnected,
    lastSocketEvent,
    isComplete: normalizeStatus(resolvedData?.status) === 'COMPLETED',
    isFailed: normalizeStatus(resolvedData?.status) === 'FAILED',
    isTimedOut: normalizeStatus(resolvedData?.status) === 'TIMED_OUT',
    isStalled: normalizeStatus(resolvedData?.status) === 'STALLED',
    isCancelled: normalizeStatus(resolvedData?.status) === 'CANCELLED',
    isRunning: normalizeStatus(resolvedData?.status) === 'RUNNING',
    progressPercent: normalizeProgressPercent(resolvedData),
    currentPair: extractCurrentPair(resolvedData),
    etaSeconds: extractEtaSeconds(resolvedData),
    progressSource:
      typeof resolvedData?.progress_source === 'string' ? resolvedData.progress_source : 'default',
  };
}

// ==================== Utility Hooks ====================

/**
 * Hook to prefetch related data for better UX
 */
export function usePrefetchBotData() {
  const queryClient = useQueryClient();

  return {
    prefetchBot: (instanceId: string) => {
      queryClient.prefetchQuery({
        queryKey: queryKeys.bot(instanceId),
        queryFn: () => apiClient.getBotInstance(instanceId),
        staleTime: queryConfigs.trading.staleTime,
      });
    },
    prefetchBotStats: (instanceId: string) => {
      queryClient.prefetchQuery({
        queryKey: queryKeys.botStats(instanceId),
        queryFn: () => apiClient.getBotStats(instanceId),
        staleTime: queryConfigs.trading.staleTime,
      });
    },
  };
}

/**
 * Hook for optimistic UI updates
 */
export function useOptimisticBotUpdate(instanceId: string) {
  const queryClient = useQueryClient();

  return {
    updateBotOptimistically: (updates: Partial<BotInstance>) => {
      queryClient.setQueryData(queryKeys.bot(instanceId), (old: BotInstance | undefined) =>
        old ? { ...old, ...updates } : undefined
      );
    },
    revertBotUpdate: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bot(instanceId) });
    },
  };
}
