// React Query setup and configuration
// Provides advanced caching, background updates, and data synchronization

import type { QueryKey } from '@tanstack/react-query';
import { QueryClient } from '@tanstack/react-query';

type QueryParams = object;

const hasResponseStatus = (error: unknown, status: number): boolean => {
  if (typeof error !== 'object' || error === null) return false;
  const response = (error as { response?: unknown }).response;
  if (typeof response !== 'object' || response === null) return false;
  return (response as { status?: unknown }).status === status;
};

// Query keys for consistent caching
export const queryKeys = {
  // Auth
  currentUser: ['auth', 'currentUser'] as const,

  // Bots
  bots: (params?: QueryParams) => ['bots', params] as const,
  bot: (instanceId: string) => ['bots', instanceId] as const,
  botStats: (instanceId: string) => ['bots', instanceId, 'stats'] as const,
  botTrades: (instanceId: string, params?: QueryParams) =>
    ['bots', instanceId, 'trades', params] as const,
  botPositions: (instanceId: string) => ['bots', instanceId, 'positions'] as const,
  botPosition: (instanceId: string, positionId: string) =>
    ['bots', instanceId, 'positions', positionId] as const,
  botAlerts: (instanceId: string, params?: QueryParams) =>
    ['bots', instanceId, 'alerts', params] as const,
  botRealtimeStats: (instanceId: string) => ['bots', instanceId, 'realtime'] as const,
  botMarketData: (instanceId: string) => ['bots', instanceId, 'market-data'] as const,
  botJobs: (instanceId: string, days?: number) => ['bots', instanceId, 'jobs', days ?? 7] as const,

  // Backtests
  backtests: (params?: QueryParams) => ['backtests', params] as const,
  backtest: (runId: string) => ['backtests', runId] as const,
  backtestStatus: (runId: string) => ['backtests', runId, 'status'] as const,
  backtestTrades: (runId: string, params?: QueryParams) =>
    ['backtests', runId, 'trades', params] as const,
  backtestMetrics: (runId: string) => ['backtests', runId, 'metrics'] as const,
  backtestAnalytics: (runId: string) => ['backtests', runId, 'analytics'] as const,
  backtestSyncHealth: (runId?: string) => ['backtests', 'sync-health', runId ?? 'all'] as const,
  backtestInterrupted: (admin: boolean = false, limit?: number) =>
    ['backtests', admin ? 'admin-interrupted' : 'interrupted', limit ?? 50] as const,

  // System
  systemStatus: ['system', 'status'] as const,
  health: ['system', 'health'] as const,
  readiness: ['system', 'readiness'] as const,
  botCapabilities: ['system', 'bot-capabilities'] as const,
  runtimeDbConfig: ['system', 'runtime-db-config'] as const,
} as const;

// Create QueryClient with optimized defaults
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Cache for 5 minutes by default
      staleTime: 5 * 60 * 1000,
      // Keep cached data for 10 minutes
      gcTime: 10 * 60 * 1000,
      // Retry failed requests 3 times with exponential backoff
      retry: (failureCount, error) => {
        if (hasResponseStatus(error, 401) || hasResponseStatus(error, 403)) {
          return false; // Don't retry auth errors
        }
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      // Refetch on window focus for critical data
      refetchOnWindowFocus: true,
      // Don't refetch on mount if data is fresh
      refetchOnMount: true,
      // Refetch on reconnect
      refetchOnReconnect: true,
    },
    mutations: {
      // Retry mutations once
      retry: 1,
      retryDelay: 1000,
    },
  },
});

// Query Client Provider Component is in QueryProvider.tsx

// Utility functions for cache management
export const cacheUtils = {
  // Invalidate all queries matching a pattern
  invalidateQueries: (queryKey: QueryKey) => {
    return queryClient.invalidateQueries({ queryKey });
  },

  // Remove queries from cache
  removeQueries: (queryKey: QueryKey) => {
    return queryClient.removeQueries({ queryKey });
  },

  // Get cached data
  getQueryData: <T>(queryKey: QueryKey): T | undefined => {
    return queryClient.getQueryData<T>(queryKey);
  },

  // Set cached data
  setQueryData: <T>(queryKey: QueryKey, data: T) => {
    return queryClient.setQueryData<T>(queryKey, data);
  },

  // Prefetch data
  prefetchQuery: (options: {
    queryKey: QueryKey;
    queryFn: () => Promise<unknown>;
    staleTime?: number;
  }) => {
    return queryClient.prefetchQuery(options);
  },

  // Invalidate all bot-related queries
  invalidateBotQueries: (instanceId?: string) => {
    if (instanceId) {
      return queryClient.invalidateQueries({ queryKey: ['bots', instanceId] });
    }
    return queryClient.invalidateQueries({ queryKey: ['bots'] });
  },

  // Invalidate all backtest-related queries
  invalidateBacktestQueries: (runId?: string) => {
    if (runId) {
      return queryClient.invalidateQueries({ queryKey: ['backtests', runId] });
    }
    return queryClient.invalidateQueries({ queryKey: ['backtests'] });
  },

  // Clear all cache
  clearCache: () => {
    return queryClient.clear();
  },

  // Get cache statistics
  getCacheStats: () => {
    const cache = queryClient.getQueryCache();
    return {
      totalQueries: cache.getAll().length,
      freshQueries: cache.getAll().filter((q) => q.isStale() === false).length,
      staleQueries: cache.getAll().filter((q) => q.isStale() === true).length,
      errorQueries: cache.getAll().filter((q) => q.state.status === 'error').length,
    };
  },
};

// Query configuration presets for different data types
export const queryConfigs = {
  // Real-time data - short cache, frequent refetch
  realtime: {
    staleTime: 1000, // 1 second
    gcTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: 5000, // 5 seconds
  },

  // Static reference data - long cache
  static: {
    staleTime: 30 * 60 * 1000, // 30 minutes
    gcTime: 60 * 60 * 1000, // 1 hour
  },

  // User-specific data - medium cache
  user: {
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 15 * 60 * 1000, // 15 minutes
  },

  // Trading data - short cache, background refresh
  trading: {
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
  },

  // Historical data - long cache
  historical: {
    staleTime: 60 * 60 * 1000, // 1 hour
    gcTime: 24 * 60 * 60 * 1000, // 24 hours
  },
};
