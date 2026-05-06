// Enhanced API Client - extends existing client with new methods
// Adds all missing bot and backtest management endpoints

import apiClient from '../api';
import { getBackendHttpBase, resolveBackendUrl } from './origin';
import { attachTraceHeader } from './trace';
import type { User } from './types';

type Entity = Record<string, unknown>;
type QueryParams = object;
type ListResponse = { count: number; data: Entity[] };

export const resolveEnhancedApiUrl = (
  input: string,
  baseUrl: string = getBackendHttpBase()
): string => resolveBackendUrl(input, baseUrl);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

export const parseJsonResponse = async (response: Response): Promise<unknown> => {
  const rawText = await response.text();
  if (!rawText) {
    return {};
  }

  try {
    return JSON.parse(rawText);
  } catch {
    const contentType = response.headers.get('content-type') || 'unknown content type';
    const preview = rawText.replace(/\s+/g, ' ').slice(0, 120);
    throw new Error(
      `Expected JSON from API but received ${contentType}${response.url ? ` at ${response.url}` : ''}: ${preview}`
    );
  }
};

const withDataFallback = <T>(result: unknown, fallback: T): T => {
  if (isRecord(result) && 'data' in result && result.data !== undefined) {
    return result.data as T;
  }

  if (result !== undefined && result !== null) {
    return result as T;
  }

  return fallback;
};

const toListResponse = (result: unknown, listKeys: string[] = []): ListResponse => {
  const payload = withDataFallback<unknown>(result, {});
  if (Array.isArray(payload)) {
    return { count: payload.length, data: payload as Entity[] };
  }

  if (!isRecord(payload)) {
    return { count: 0, data: [] };
  }

  for (const key of listKeys) {
    const candidate = payload[key];
    if (Array.isArray(candidate)) {
      return {
        count:
          typeof payload.count === 'number'
            ? payload.count
            : typeof payload.total === 'number'
              ? payload.total
              : candidate.length,
        data: candidate as Entity[],
      };
    }
  }

  if (Array.isArray(payload.data)) {
    return {
      count:
        typeof payload.count === 'number'
          ? payload.count
          : typeof payload.total === 'number'
            ? payload.total
            : payload.data.length,
      data: payload.data as Entity[],
    };
  }

  return { count: 0, data: [] };
};

// Enhanced API client with additional methods
class EnhancedAPIClient {
  private baseClient = apiClient;
  private backtestStatusListPromise: Promise<Entity[]> | null = null;

  private getAccessToken(): string | null {
    return this.baseClient.getAccessToken();
  }

  private buildAuthHeaders(existingHeaders?: unknown): Headers {
    const headers = new Headers((existingHeaders ?? {}) as Record<string, string>);
    headers.set('Content-Type', 'application/json');
    attachTraceHeader(headers);

    const token = this.getAccessToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    } else {
      headers.delete('Authorization');
    }

    return headers;
  }

  private async fetchWithAuth(
    input: string,
    init: Record<string, unknown> = {},
    retryOnUnauthorized: boolean = true
  ): Promise<Response> {
    const headers = this.buildAuthHeaders((init as { headers?: unknown }).headers);
    const requestUrl = resolveEnhancedApiUrl(input);
    const response = await fetch(requestUrl, {
      ...(init as object),
      credentials: 'include',
      headers,
    });

    response.json = async () => parseJsonResponse(response);

    if (response.status === 401 && retryOnUnauthorized) {
      if (!this.baseClient.shouldAttemptCookieRefresh()) {
        return response;
      }

      try {
        await this.baseClient.refreshAccessToken();
        return this.fetchWithAuth(input, init, false);
      } catch (error) {
        console.warn('🔐 enhancedClient.ts: token refresh failed for fetch request', error);
      }
    }

    return response;
  }

  // Delegate existing methods
  logout = this.baseClient.logout.bind(this.baseClient);
  getCurrentUser = this.baseClient.getCurrentUser.bind(this.baseClient);
  getStats = this.baseClient.getStats.bind(this.baseClient);
  hasToken = this.baseClient.hasToken.bind(this.baseClient);
  setToken = this.baseClient.setToken.bind(this.baseClient);
  refreshAccessToken = this.baseClient.refreshAccessToken.bind(this.baseClient);

  async login(username: string, password: string, turnstileToken?: string) {
    return this.baseClient.login({
      username,
      password,
      ...(turnstileToken ? { cf_turnstile_response: turnstileToken } : {}),
    });
  }

  async register(
    username: string,
    email: string,
    password: string,
    invitationCode?: string,
    turnstileToken?: string
  ) {
    return this.baseClient.register({
      username,
      email,
      password,
      ...(invitationCode ? { invitation_code: invitationCode } : {}),
      ...(turnstileToken ? { cf_turnstile_response: turnstileToken } : {}),
    });
  }

  async updateProfile(profile: Partial<User>) {
    return this.baseClient.updateProfile(profile as Record<string, unknown>);
  }

  // Check if authenticated
  isAuthenticated(): boolean {
    return this.baseClient.hasToken();
  }

  // ==================== Bot Instance Management (New Methods) ====================

  async listBotInstances(params: QueryParams = {}): Promise<ListResponse> {
    // Map to existing backend endpoints through proxy
    const queryString = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryString.append(key, String(value));
      }
    });

    try {
      const response = await this.fetchWithAuth(
        `/api/v1/bots${queryString.toString() ? `?${queryString}` : ''}`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return toListResponse(result, ['bots', 'items']);
    } catch (error) {
      console.error('listBotInstances error:', error);
      throw error;
    }
  }

  async getBotInstance(instanceId: string): Promise<Entity> {
    try {
      const response = await this.fetchWithAuth(`/api/v1/bots/${instanceId}`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return withDataFallback<Entity>(result, {});
    } catch (error) {
      console.error('getBotInstance error:', error);
      throw error;
    }
  }

  async getBotStats(instanceId: string): Promise<Entity> {
    try {
      const response = await this.fetchWithAuth(`/api/v1/bots/${instanceId}/stats`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return withDataFallback<Entity>(result, {});
    } catch (error) {
      console.error('getBotStats error:', error);
      throw error;
    }
  }

  async getBotSummary(
    instanceId: string,
    params: { include?: string; limit?: number } = {}
  ): Promise<Entity> {
    try {
      const queryString = new URLSearchParams();
      if (params.include) queryString.append('include', params.include);
      if (params.limit !== undefined) queryString.append('limit', String(params.limit));

      const url = `/api/v1/bots/${instanceId}/summary${queryString.toString() ? `?${queryString}` : ''}`;
      const response = await this.fetchWithAuth(url, {
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return withDataFallback<Entity>(result, {});
    } catch (error) {
      console.error('getBotSummary error:', error);
      throw error;
    }
  }

  async getBotTrades(instanceId: string, params: QueryParams = {}): Promise<ListResponse> {
    try {
      const queryString = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          queryString.append(key, String(value));
        }
      });

      const response = await this.fetchWithAuth(
        `/api/v1/bots/${instanceId}/trades${queryString.toString() ? `?${queryString}` : ''}`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return toListResponse(result, ['trades', 'items']);
    } catch (error) {
      console.error('getBotTrades error:', error);
      throw error;
    }
  }

  async createBotInstance(config: object): Promise<Entity> {
    try {
      const response = await this.fetchWithAuth('/api/v1/bots', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return withDataFallback<Entity>(result, {});
    } catch (error) {
      console.error('createBotInstance error:', error);
      throw error;
    }
  }

  async updateBotInstance(instanceId: string, updates: object): Promise<Entity> {
    try {
      const response = await this.fetchWithAuth(`/api/v1/bots/${instanceId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return withDataFallback<Entity>(result, {});
    } catch (error) {
      console.error('updateBotInstance error:', error);
      throw error;
    }
  }

  async startBotInstance(instanceId: string, config?: object): Promise<{ message: string }> {
    try {
      const response = await this.fetchWithAuth(`/api/v1/bots/${instanceId}/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config || {}),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return withDataFallback<{ message: string }>(result, { message: 'Started' });
    } catch (error) {
      console.error('startBotInstance error:', error);
      throw error;
    }
  }

  async stopBotInstance(instanceId: string): Promise<{ message: string }> {
    try {
      const response = await this.fetchWithAuth(`/api/v1/bots/${instanceId}/stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return withDataFallback<{ message: string }>(result, { message: 'Stopped' });
    } catch (error) {
      console.error('stopBotInstance error:', error);
      throw error;
    }
  }

  async restartBotInstance(instanceId: string): Promise<{ message: string }> {
    try {
      const response = await this.fetchWithAuth(`/api/v1/bots/${instanceId}/restart`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      return withDataFallback<{ message: string }>(result, { message: 'Restarted' });
    } catch (error) {
      console.error('restartBotInstance error:', error);
      throw error;
    }
  }

  async deleteBotInstance(instanceId: string): Promise<void> {
    try {
      const response = await this.fetchWithAuth(`/api/v1/bots/${instanceId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (error) {
      console.error('deleteBotInstance error:', error);
      throw error;
    }
  }

  // ==================== Real-Time Data Methods ====================

  async getCurrentPositions(instanceId: string): Promise<Entity[]> {
    try {
      const response = await this.fetchWithAuth(`/api/v1/bots/${instanceId}/positions/current`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const result = await response.json();
      return toListResponse(result, ['positions', 'items']).data;
    } catch (error) {
      console.error('getCurrentPositions error:', error);
      throw error;
    }
  }

  async getPosition(instanceId: string, positionId: string): Promise<Entity | null> {
    try {
      const response = await this.fetchWithAuth(
        `/api/v1/bots/${instanceId}/positions/${positionId}`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      const result = await response.json();
      return withDataFallback<Entity | null>(result, null);
    } catch (error) {
      console.error('getPosition error:', error);
      throw error;
    }
  }

  async getPositionHistory(
    instanceId: string,
    positionId: string,
    hours: number = 24
  ): Promise<ListResponse> {
    const result = await this.baseClient.getBotPositionHistory(instanceId, positionId, hours);
    return toListResponse(result, ['history', 'points', 'snapshots']);
  }

  async getRealtimeStats(instanceId: string): Promise<Entity> {
    try {
      const response = await this.fetchWithAuth(`/api/v1/bots/${instanceId}/realtime-stats`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const result = await response.json();
      return withDataFallback<Entity>(result, {});
    } catch (error) {
      console.error('getRealtimeStats error:', error);
      throw error;
    }
  }

  async getMarketData(instanceId: string): Promise<Record<string, unknown>> {
    try {
      const response = await this.fetchWithAuth(`/api/v1/bots/${instanceId}/market-data`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const result = await response.json();
      return withDataFallback<Record<string, unknown>>(result, {});
    } catch (error) {
      console.error('getMarketData error:', error);
      throw error;
    }
  }

  async getAlerts(instanceId: string, params: QueryParams = {}): Promise<ListResponse> {
    try {
      const queryString = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          queryString.append(key, String(value));
        }
      });

      const response = await this.fetchWithAuth(
        `/api/v1/bots/${instanceId}/alerts${queryString.toString() ? `?${queryString}` : ''}`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      const result = await response.json();
      return toListResponse(result, ['alerts', 'items']);
    } catch (error) {
      console.error('getAlerts error:', error);
      throw error;
    }
  }

  async getBotHistory(instanceId: string, days: number = 7): Promise<Entity> {
    const result = await this.baseClient.getBotHistory(instanceId, days);
    return withDataFallback<Entity>(result, {});
  }

  async getBotJobs(instanceId: string, days: number = 7): Promise<Entity> {
    const result = await this.baseClient.getBotJobs(instanceId, days);
    return withDataFallback<Entity>(result, {});
  }

  async quickDeployBot(
    instanceName: string,
    autoStart: boolean,
    config: Record<string, unknown>
  ): Promise<Entity> {
    const result = await this.baseClient.quickDeployBot(instanceName, autoStart, config);
    return withDataFallback<Entity>(result, {});
  }

  // ==================== Backtest Methods (delegate to existing) ====================

  async listBacktests(
    params: { offset?: number; limit?: number; status?: string; days?: number } = {}
  ): Promise<ListResponse> {
    const query = new URLSearchParams();
    query.set('offset', String(params.offset ?? 0));
    query.set('limit', String(params.limit ?? 50));
    if (params.status) {
      query.set('status', params.status);
    }
    if (params.days !== undefined) {
      query.set('days', String(params.days));
    }

    const response = await this.fetchWithAuth(`/api/v1/backtests?${query.toString()}`, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    const result = await response.json();
    const data = (result.data ?? {}) as { total?: number; backtests?: Entity[] };
    return {
      count: data.total || 0,
      data: Array.isArray(data.backtests) ? data.backtests : [],
    };
  }

  async getBacktest(runId: string): Promise<Entity> {
    const result = await this.baseClient.getBacktest(runId);
    return (result.data as Entity | undefined) ?? {};
  }

  private async getBacktestStatusList(): Promise<Entity[]> {
    if (this.backtestStatusListPromise) {
      return this.backtestStatusListPromise;
    }

    this.backtestStatusListPromise = this.baseClient
      .listBacktests(0, 50)
      .then((listResult) => {
        const listData = (listResult.data ?? {}) as { backtests?: unknown[] };
        const runs = Array.isArray(listData.backtests) ? listData.backtests.filter(isRecord) : [];
        return runs;
      })
      .finally(() => {
        this.backtestStatusListPromise = null;
      });

    return this.backtestStatusListPromise;
  }

  async getBacktestStatus(runId: string): Promise<{
    run_id: string;
    status: string;
    progress_percent: number;
    current_pair?: string;
    estimated_completion_seconds?: number;
    updated_at?: string;
    checked_at?: string;
    progress_source?: 'status' | 'list_fallback' | 'default';
  }> {
    const parseProgress = (value: unknown): number | null => {
      if (typeof value !== 'number' && typeof value !== 'string') {
        return null;
      }
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) {
        return null;
      }
      return Math.min(100, Math.max(0, parsed));
    };

    const extractFromRunRecord = (
      run: Record<string, unknown>
    ): {
      status?: string;
      progress?: number;
      currentPair?: string;
      etaSeconds?: number;
      updatedAt?: string;
    } => {
      const status = typeof run.status === 'string' ? run.status.toUpperCase() : undefined;
      const progress =
        parseProgress(run.progress_percent) ??
        parseProgress(run.progress_pct) ??
        parseProgress(run.progress) ??
        parseProgress(run.percent_complete);

      const currentPairRaw = run.current_pair ?? run.current_market ?? run.market;
      const currentPair =
        typeof currentPairRaw === 'string' && currentPairRaw.trim().length > 0
          ? currentPairRaw
          : undefined;

      const etaRaw = run.estimated_completion_seconds ?? run.eta_seconds ?? run.remaining_seconds;
      const etaParsed =
        typeof etaRaw === 'number' || typeof etaRaw === 'string' ? Number(etaRaw) : Number.NaN;
      const etaSeconds = Number.isFinite(etaParsed) && etaParsed >= 0 ? etaParsed : undefined;
      const updatedAt =
        typeof run.updated_at === 'string' && run.updated_at.trim().length > 0
          ? run.updated_at
          : typeof run.last_heartbeat_at === 'string' && run.last_heartbeat_at.trim().length > 0
            ? run.last_heartbeat_at
            : undefined;

      return {
        status,
        progress: progress ?? undefined,
        currentPair,
        etaSeconds,
        updatedAt,
      };
    };

    const checkedAt = new Date().toISOString();
    let status = 'PENDING';
    let progress: number | undefined;
    let currentPair: string | undefined;
    let etaSeconds: number | undefined;
    let updatedAt: string | undefined;
    let progressSource: 'status' | 'list_fallback' | 'default' = 'default';

    // The dedicated status endpoint currently times out for some active runs.
    // The list response carries the same live fields without producing browser-level fetch errors.
    try {
      const listRuns = await this.getBacktestStatusList();
      const matchedRun = listRuns.find((item) => item.run_id === runId);

      if (isRecord(matchedRun)) {
        const fallbackStatusProgress = extractFromRunRecord(matchedRun);
        status = fallbackStatusProgress.status ?? status;
        if (fallbackStatusProgress.progress !== undefined) {
          progress = fallbackStatusProgress.progress;
          progressSource = 'list_fallback';
        }
        currentPair = fallbackStatusProgress.currentPair ?? currentPair;
        etaSeconds = fallbackStatusProgress.etaSeconds ?? etaSeconds;
        updatedAt = fallbackStatusProgress.updatedAt ?? updatedAt;
      }
    } catch (error) {
      console.warn(
        '📊 enhancedClient.ts: failed to fetch list fallback for backtest status',
        error
      );
    }

    const computedProgress = progress !== undefined ? progress : status === 'COMPLETED' ? 100 : 0;

    return {
      run_id: runId,
      status,
      progress_percent: computedProgress,
      current_pair: currentPair,
      estimated_completion_seconds: etaSeconds,
      updated_at: updatedAt,
      checked_at: checkedAt,
      progress_source: progressSource,
    };
  }

  async getBacktestTrades(
    runId: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<ListResponse> {
    const result = await this.baseClient.getBacktestTrades(runId, limit, offset);
    const data = (result.data ?? {}) as { total?: number; trades?: Entity[] };
    return {
      count: data.total || 0,
      data: Array.isArray(data.trades) ? data.trades : [],
    };
  }

  async getBacktestMetrics(runId: string): Promise<Entity> {
    const result = await this.baseClient.getBacktestPerformance(runId);
    return (result.data as Entity | undefined) ?? {};
  }

  async createBacktest(config: { start_date: string; end_date: string }): Promise<Entity> {
    const result = await this.baseClient.runBacktest(
      config as { start_date: string; end_date: string } & Record<string, unknown>
    );
    return (result.data as Entity | undefined) ?? {};
  }

  async deleteBacktest(runId: string): Promise<void> {
    await this.baseClient.deleteBacktest(runId);
  }

  async cancelBacktest(runId: string): Promise<{ message: string }> {
    const result = await this.baseClient.cancelBacktest(runId);
    const data = (result.data ?? {}) as { message?: string };
    return { message: data.message || result.message || `Backtest ${runId} cancelled` };
  }

  async compareBacktests(runIds: string[], metrics: string[]): Promise<Entity> {
    const result = await this.baseClient.compareBacktests(runIds, metrics);
    return withDataFallback<Entity>(result, {});
  }

  async getInterruptedBacktests(limit: number = 50, admin: boolean = false): Promise<Entity> {
    const result = await this.baseClient.getInterruptedBacktests(limit, admin);
    return withDataFallback<Entity>(result, {});
  }

  async reconcileInterruptedBacktests(
    dryRun: boolean = true,
    admin: boolean = false
  ): Promise<Entity> {
    const result = await this.baseClient.reconcileInterruptedBacktests(dryRun, admin);
    return withDataFallback<Entity>(result, {});
  }

  async getCapabilities(): Promise<Entity> {
    const result = await this.baseClient.getBotServiceCapabilities();
    return withDataFallback<Entity>(result, {});
  }

  async getRuntimeDBConfig(): Promise<Entity> {
    const result = await this.baseClient.getBotRuntimeDBConfig();
    return withDataFallback<Entity>(result, {});
  }

  // ==================== System Methods ====================

  async getSystemStatus(): Promise<Entity> {
    try {
      const response = await this.fetchWithAuth('/api/v1/system/status', {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const result = await response.json();
      return (
        result.data || {
          status: 'operational',
          components: {
            database: 'healthy',
            bot_api: 'healthy',
            cache: 'healthy',
            indexer: 'healthy',
          },
        }
      );
    } catch (error) {
      console.error('getSystemStatus error:', error);
      return {
        status: 'operational',
        components: {
          database: 'healthy',
          bot_api: 'healthy',
          cache: 'healthy',
          indexer: 'healthy',
        },
      };
    }
  }

  async getHealth(): Promise<Entity> {
    try {
      const response = await fetch(resolveEnhancedApiUrl('/health'));
      const result = await parseJsonResponse(response);
      return withDataFallback<Entity>(result, { status: 'unknown' });
    } catch (error) {
      console.error('getHealth error:', error);
      return { status: 'unknown' };
    }
  }

  async getReadiness(): Promise<unknown> {
    try {
      const response = await fetch(resolveEnhancedApiUrl('/ready'));
      const result = await parseJsonResponse(response);
      return result;
    } catch (error) {
      console.error('getReadiness error:', error);
      return { status: 'unknown', ready: false };
    }
  }
}

// Export enhanced client instance
export const enhancedApiClient = new EnhancedAPIClient();
export default enhancedApiClient;
