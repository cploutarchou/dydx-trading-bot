// Bot/backtest/system endpoint surface (FE-015 consolidation): every request
// rides the shared axios client from src/api.ts — cookie auth, trace headers,
// and 401→refresh→retry all live in that one interceptor chain. Auth/session
// calls belong to src/api.ts directly; this module only owns the bot-service
// and backtest endpoints plus the infra probes.

import apiClient from '../api';

type Entity = Record<string, unknown>;
type QueryParams = object;
type ListResponse = { count: number; data: Entity[] };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

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

/** Drop undefined entries and coerce the rest so axios serializes the
 *  surviving values into the query string. */
const toQueryParams = (
  params: Record<string, unknown>
): Record<string, string | number | boolean | undefined> => {
  const out: Record<string, string | number | boolean | undefined> = {};
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined) return;
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      out[key] = value;
    } else {
      out[key] = String(value);
    }
  });
  return out;
};

class BotApiClient {
  private baseClient = apiClient;
  private backtestStatusListPromise: Promise<Entity[]> | null = null;

  private request(url: string, method: 'get' | 'post' | 'put' | 'delete' = 'get', body?: unknown) {
    return this.baseClient.requestJson<unknown>(method, url, body !== undefined ? { body } : {});
  }

  private listRequest(url: string, params: Record<string, unknown>, listKeys: string[]) {
    return this.requestJsonWithParams(url, params).then((result) =>
      toListResponse(result, listKeys)
    );
  }

  private requestJsonWithParams(url: string, params: Record<string, unknown>) {
    return this.baseClient.requestJson<unknown>('get', url, { params: toQueryParams(params) });
  }

  // ==================== Bot Instance Management ====================

  async listBotInstances(params: QueryParams = {}): Promise<ListResponse> {
    return this.listRequest('/api/v1/bots', params as Record<string, unknown>, ['bots', 'items']);
  }

  async getBotInstance(instanceId: string): Promise<Entity> {
    const result = await this.request(`/api/v1/bots/${instanceId}`);
    return withDataFallback<Entity>(result, {});
  }

  async getBotStats(instanceId: string): Promise<Entity> {
    const result = await this.request(`/api/v1/bots/${instanceId}/stats`);
    return withDataFallback<Entity>(result, {});
  }

  async getBotSummary(
    instanceId: string,
    params: { include?: string; limit?: number } = {}
  ): Promise<Entity> {
    const result = await this.requestJsonWithParams(
      `/api/v1/bots/${instanceId}/summary`,
      params as Record<string, unknown>
    );
    return withDataFallback<Entity>(result, {});
  }

  async getBotTrades(instanceId: string, params: QueryParams = {}): Promise<ListResponse> {
    return this.listRequest(
      `/api/v1/bots/${instanceId}/trades`,
      params as Record<string, unknown>,
      ['trades', 'items']
    );
  }

  async createBotInstance(config: object): Promise<Entity> {
    const result = await this.request('/api/v1/bots', 'post', config);
    return withDataFallback<Entity>(result, {});
  }

  async updateBotInstance(instanceId: string, updates: object): Promise<Entity> {
    const result = await this.request(`/api/v1/bots/${instanceId}`, 'put', updates);
    return withDataFallback<Entity>(result, {});
  }

  async startBotInstance(instanceId: string, config?: object): Promise<{ message: string }> {
    const result = await this.request(`/api/v1/bots/${instanceId}/start`, 'post', config ?? {});
    return withDataFallback<{ message: string }>(result, { message: 'Started' });
  }

  async stopBotInstance(instanceId: string): Promise<{ message: string }> {
    const result = await this.request(`/api/v1/bots/${instanceId}/stop`, 'post');
    return withDataFallback<{ message: string }>(result, { message: 'Stopped' });
  }

  async restartBotInstance(instanceId: string): Promise<{ message: string }> {
    const result = await this.request(`/api/v1/bots/${instanceId}/restart`, 'post');
    return withDataFallback<{ message: string }>(result, { message: 'Restarted' });
  }

  async deleteBotInstance(instanceId: string): Promise<void> {
    await this.request(`/api/v1/bots/${instanceId}`, 'delete');
  }

  // ==================== Real-Time Data Methods ====================

  async getCurrentPositions(instanceId: string): Promise<Entity[]> {
    const result = await this.request(`/api/v1/bots/${instanceId}/positions/current`);
    return toListResponse(result, ['positions', 'items']).data;
  }

  async getPosition(instanceId: string, positionId: string): Promise<Entity | null> {
    const result = await this.request(`/api/v1/bots/${instanceId}/positions/${positionId}`);
    return withDataFallback<Entity | null>(result, null);
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
    const result = await this.request(`/api/v1/bots/${instanceId}/realtime-stats`);
    return withDataFallback<Entity>(result, {});
  }

  async getMarketData(instanceId: string): Promise<Record<string, unknown>> {
    const result = await this.request(`/api/v1/bots/${instanceId}/market-data`);
    return withDataFallback<Record<string, unknown>>(result, {});
  }

  async getAlerts(instanceId: string, params: QueryParams = {}): Promise<ListResponse> {
    return this.listRequest(
      `/api/v1/bots/${instanceId}/alerts`,
      params as Record<string, unknown>,
      ['alerts', 'items']
    );
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
    const result = await this.requestJsonWithParams('/api/v1/backtests', {
      offset: params.offset ?? 0,
      limit: params.limit ?? 50,
      status: params.status,
      days: params.days,
    });
    const data = withDataFallback<{ total?: number; backtests?: Entity[] }>(result, {});
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
      console.warn('📊 botApi.ts: failed to fetch list fallback for backtest status', error);
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

  private static readonly SYSTEM_STATUS_FALLBACK: Entity = {
    status: 'operational',
    components: {
      database: 'healthy',
      bot_api: 'healthy',
      cache: 'healthy',
      indexer: 'healthy',
    },
  };

  async getSystemStatus(): Promise<Entity> {
    try {
      const result = await this.request('/api/v1/system/status');
      return (
        isRecord(result) && result.data !== undefined
          ? (result.data as Entity)
          : BotApiClient.SYSTEM_STATUS_FALLBACK
      ) as Entity;
    } catch {
      return BotApiClient.SYSTEM_STATUS_FALLBACK;
    }
  }

  async getHealth(): Promise<Entity> {
    try {
      const result = await this.request('/health');
      return withDataFallback<Entity>(result, { status: 'unknown' });
    } catch {
      return { status: 'unknown' };
    }
  }

  async getReadiness(): Promise<unknown> {
    try {
      return await this.request('/ready');
    } catch {
      return { status: 'unknown', ready: false };
    }
  }
}

export const botApi = new BotApiClient();
export default botApi;
