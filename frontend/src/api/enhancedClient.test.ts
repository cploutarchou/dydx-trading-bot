import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

let enhancedApiClient: typeof import('./enhancedClient').enhancedApiClient;
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

  ({ enhancedApiClient } = await import('./enhancedClient'));
  ({ default: baseApiClient } = await import('../api'));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('enhanced API client (consolidated on the axios client)', () => {
  it('uses list progress without calling the unstable status endpoint', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

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

    const status = await enhancedApiClient.getBacktestStatus('run-1');

    expect(status.run_id).toBe('run-1');
    expect(status.status).toBe('RUNNING');
    expect(status.progress_percent).toBe(42);
    expect(status.progress_source).toBe('list_fallback');
    expect(status.current_pair).toBe('BTC-USD/ETH-USD');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('shares an in-flight list fallback across concurrent status lookups', async () => {
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
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    const [firstStatus, secondStatus] = await Promise.all([
      enhancedApiClient.getBacktestStatus('run-1'),
      enhancedApiClient.getBacktestStatus('run-2'),
    ]);

    expect(firstStatus.progress_percent).toBe(77);
    expect(secondStatus.progress_percent).toBe(12);
    expect(firstStatus.progress_source).toBe('list_fallback');
    expect(secondStatus.progress_source).toBe('list_fallback');
    expect(listSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
