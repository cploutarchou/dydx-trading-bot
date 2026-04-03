// Custom React Query Hooks for API Endpoints
// Provides optimized data fetching with loading states, error handling, and caching

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { enhancedApiClient as apiClient } from './enhancedClient';
import { cacheUtils, queryConfigs, queryKeys } from './queryClient';
import type {
    BacktestConfig,
    BotInstance,
    CreateBotRequest,
    ListAlertsParams,
    ListBacktestsParams,
    ListBotsParams,
    ListTradesParams,
    StartBotRequest,
    UpdateBotRequest,
    User,
} from './types';

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
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      apiClient.login(username, password),
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
    }: {
      username: string;
      email: string;
      password: string;
    }) => apiClient.register(username, email, password),
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
  const normalizeStatus = (status: unknown): string => String(status || '').trim().toUpperCase();

  const normalizeProgressPercent = (data: unknown): number => {
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

    // Backtest endpoints already report percentage values (including decimals like 0.5%).
    return Math.min(100, Math.max(0, parsed));
  };

  const extractCurrentPair = (data: unknown): string | null => {
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
    const pair = record.current_pair ?? record.current_market ?? record.market;
    return typeof pair === 'string' && pair.trim().length > 0 ? pair : null;
  };

  const extractEtaSeconds = (data: unknown): number | null => {
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
    const rawEta = record.estimated_completion_seconds ?? record.eta_seconds ?? record.remaining_seconds;
    if (typeof rawEta !== 'number' && typeof rawEta !== 'string') {
      return null;
    }
    const parsed = Number(rawEta);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
  };

  const extractProgressSource = (data: unknown): 'details' | 'list_fallback' | 'default' => {
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
    const source = record.progress_source;
    if (source === 'details' || source === 'list_fallback' || source === 'default') {
      return source;
    }
    return 'default';
  };

  const query = useQuery({
    queryKey: queryKeys.backtestStatus(runId),
    queryFn: () => apiClient.getBacktestStatus(runId),
    refetchInterval: (query) => {
      const status = normalizeStatus((query.state.data as { status?: string } | undefined)?.status);
      // Stop polling if backtest is complete or failed
      if (status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED') {
        return false;
      }
      return 2000; // Poll every 2 seconds
    },
    enabled: !!runId,
  });

  return {
    ...query,
    isComplete: normalizeStatus(query.data?.status) === 'COMPLETED',
    isFailed: normalizeStatus(query.data?.status) === 'FAILED',
    isCancelled: normalizeStatus(query.data?.status) === 'CANCELLED',
    isRunning: normalizeStatus(query.data?.status) === 'RUNNING',
    progressPercent: normalizeProgressPercent(query.data),
    currentPair: extractCurrentPair(query.data),
    etaSeconds: extractEtaSeconds(query.data),
    progressSource: extractProgressSource(query.data),
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
