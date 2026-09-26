import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

let botApi: typeof import('./botApi').botApi;
let baseApiClient: typeof import('../api').default;

beforeAll(async () => {
  Object.defineProperty(globalThis, 'localStorage', {
    value: {
      getItem: () => null,
      setItem: () => undefined,
      removeItem: () => undefined,
      clear: () => undefined,
    },
    configurable: true,
  });
  Object.defineProperty(globalThis, 'document', {
    value: { cookie: '' },
    configurable: true,
  });

  ({ botApi } = await import('./botApi'));
  ({ default: baseApiClient } = await import('../api'));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('bot API surface (consolidated on the axios client)', () => {
  it('reads status and progress from the status route when it answers', async () => {
    vi.spyOn(baseApiClient, 'getBacktestStatus').mockResolvedValue({
      success: true,
      message: 'ok',
      data: {
        run_id: 'run-1',
        status: 'running',
        progress_pct: 37.5,
        current_pair: 'BTC-USD/SOL-USD',
        updated_at: '2026-09-26T11:25:00+00:00',
        request_available: true,
        restartable: false,
        request: { initial_balance: 100 },
      },
      timestamp: new Date().toISOString(),
    } as Awaited<ReturnType<typeof baseApiClient.getBacktestStatus>>);
    const listSpy = vi.spyOn(baseApiClient, 'listBacktests');

    const status = await botApi.getBacktestStatus('run-1');

    expect(status.status).toBe('RUNNING');
    expect(status.progress_percent).toBe(37.5);
    expect(status.progress_source).toBe('status');
    expect(status.current_pair).toBe('BTC-USD/SOL-USD');
    expect(status.updated_at).toBe('2026-09-26T11:25:00+00:00');
    expect(status.request_available).toBe(true);
    expect(status.restartable).toBe(false);
    expect(status.request).toEqual({ initial_balance: 100 });
    expect(listSpy).not.toHaveBeenCalled();
  });

  it('falls back to list progress when the status route fails', async () => {
    vi.spyOn(baseApiClient, 'getBacktestStatus').mockRejectedValue(new Error('timeout'));

    vi.spyOn(baseApiClient, 'listBacktests').mockResolvedValue({
      success: true,
      message: 'ok',
      data: {
        total: 1,
        backtests: [
          {
            run_id: 'run-1',
            status: 'RUNNING',
            created_at: '2026-04-11T00:00:00Z',
            progress_pct: 42,
            current_pair: 'BTC-USD/ETH-USD',
            estimated_completion_seconds: 120,
          },
        ],
      },
      timestamp: new Date().toISOString(),
    } as Awaited<ReturnType<typeof baseApiClient.listBacktests>>);

    const status = await botApi.getBacktestStatus('run-1');

    expect(status.run_id).toBe('run-1');
    expect(status.status).toBe('RUNNING');
    expect(status.progress_percent).toBe(42);
    expect(status.progress_source).toBe('list_fallback');
    expect(status.current_pair).toBe('BTC-USD/ETH-USD');
  });

  it('never reports the Go zero time as an update time', async () => {
    vi.spyOn(baseApiClient, 'getBacktestStatus').mockRejectedValue(new Error('timeout'));
    vi.spyOn(baseApiClient, 'listBacktests').mockResolvedValue({
      success: true,
      message: 'ok',
      data: {
        total: 1,
        backtests: [
          {
            run_id: 'run-1',
            status: 'PENDING',
            created_at: '2026-09-26T11:22:16Z',
            updated_at: '0001-01-01T00:00:00Z',
          },
        ],
      },
      timestamp: new Date().toISOString(),
    } as Awaited<ReturnType<typeof baseApiClient.listBacktests>>);

    const status = await botApi.getBacktestStatus('run-1');

    expect(status.updated_at).toBeUndefined();
  });

  it('shares an in-flight list fallback across concurrent status lookups', async () => {
    vi.spyOn(baseApiClient, 'getBacktestStatus').mockRejectedValue(new Error('timeout'));
    const listSpy = vi.spyOn(baseApiClient, 'listBacktests').mockResolvedValue({
      success: true,
      message: 'ok',
      data: {
        total: 2,
        backtests: [
          {
            run_id: 'run-1',
            status: 'RUNNING',
            created_at: '2026-04-11T00:00:00Z',
            progress_pct: 77,
          },
          {
            run_id: 'run-2',
            status: 'PENDING',
            created_at: '2026-04-11T00:00:01Z',
            progress_pct: 12,
          },
        ],
      },
      timestamp: new Date().toISOString(),
    } as Awaited<ReturnType<typeof baseApiClient.listBacktests>>);

    const [firstStatus, secondStatus] = await Promise.all([
      botApi.getBacktestStatus('run-1'),
      botApi.getBacktestStatus('run-2'),
    ]);

    expect(firstStatus.progress_percent).toBe(77);
    expect(secondStatus.progress_percent).toBe(12);
    expect(firstStatus.progress_source).toBe('list_fallback');
    expect(secondStatus.progress_source).toBe('list_fallback');
    expect(listSpy).toHaveBeenCalledTimes(1);
  });
});
