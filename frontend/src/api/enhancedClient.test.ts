import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

let parseJsonResponse: typeof import('./enhancedClient').parseJsonResponse;
let resolveEnhancedApiUrl: typeof import('./enhancedClient').resolveEnhancedApiUrl;
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

  ({ parseJsonResponse, resolveEnhancedApiUrl } = await import('./enhancedClient'));
  ({ enhancedApiClient } = await import('./enhancedClient'));
  ({ default: baseApiClient } = await import('../api'));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('enhanced API client helpers', () => {
  it('resolves bot API requests against the configured backend URL', () => {
    expect(resolveEnhancedApiUrl('/api/v1/bots', 'http://localhost:8888')).toBe(
      'http://localhost:8888/api/v1/bots'
    );
  });

  it('throws a readable error when HTML is returned instead of JSON', async () => {
    const response = new Response('<!doctype html><html><body>Not JSON</body></html>', {
      status: 200,
      headers: {
        'Content-Type': 'text/html',
      },
    });

    await expect(parseJsonResponse(response)).rejects.toThrow(/expected json/i);
  });

  it('falls back to list progress when details endpoint is stale', async () => {
    vi.spyOn(baseApiClient, 'getBacktest').mockResolvedValue({
      success: true,
      message: 'ok',
      data: {
        run_id: 'run-1',
        status: 'RUNNING',
        progress_percent: 0,
      },
      timestamp: new Date().toISOString(),
    });

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
    });

    const status = await enhancedApiClient.getBacktestStatus('run-1');

    expect(status.run_id).toBe('run-1');
    expect(status.status).toBe('RUNNING');
    expect(status.progress_percent).toBe(42);
    expect(status.progress_source).toBe('list_fallback');
    expect(status.current_pair).toBe('BTC-USD/ETH-USD');
  });

  it('keeps details progress when available and avoids fallback override', async () => {
    const listSpy = vi.spyOn(baseApiClient, 'listBacktests').mockResolvedValue({
      success: true,
      message: 'ok',
      data: {
        total: 1,
        backtests: [
          {
            run_id: 'run-1',
            status: 'RUNNING',
            created_at: '2026-04-11T00:00:00Z',
            progress_pct: 77,
          },
        ],
      },
      timestamp: new Date().toISOString(),
    });

    vi.spyOn(baseApiClient, 'getBacktest').mockResolvedValue({
      success: true,
      message: 'ok',
      data: {
        run_id: 'run-1',
        status: 'RUNNING',
        progress_percent: 35,
      },
      timestamp: new Date().toISOString(),
    });

    const status = await enhancedApiClient.getBacktestStatus('run-1');

    expect(status.progress_percent).toBe(35);
    expect(status.progress_source).toBe('details');
    expect(listSpy).not.toHaveBeenCalled();
  });
});
