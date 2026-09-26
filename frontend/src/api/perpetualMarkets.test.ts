import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const mockGet = vi.fn();
const mockAxiosPost = vi.fn();

const mockAxiosInstance = {
  get: mockGet,
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  },
};

vi.mock('axios', () => {
  class MockAxiosError extends Error {
    response?: { status?: number; data?: unknown; headers?: Record<string, unknown> };
    code?: string;
  }

  return {
    default: {
      create: vi.fn(() => mockAxiosInstance),
      post: mockAxiosPost,
      isCancel: vi.fn(() => false),
    },
    create: vi.fn(() => mockAxiosInstance),
    isAxiosError: vi.fn(() => false),
    isCancel: vi.fn(() => false),
    AxiosError: MockAxiosError,
  };
});

describe('api.getPerpetualMarkets', () => {
  let api: typeof import('../api').default;

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

    ({ default: api } = await import('../api'));
  });

  beforeEach(() => {
    mockGet.mockReset();
    mockAxiosPost.mockReset();
  });

  it('normalizes missing markets/count/source to safe defaults', async () => {
    mockGet.mockResolvedValue({
      data: {
        success: true,
        message: 'ok',
        data: {},
        timestamp: '2026-05-16T00:00:00.000Z',
      },
      headers: {
        'x-cache-hit': 'true',
        'x-cache-stale': 'false',
        'x-markets-fallback': '1',
      },
    });

    const response = await api.getPerpetualMarkets();

    expect(mockGet).toHaveBeenCalledWith('/api/v1/markets/perpetuals');
    expect(response.data?.markets).toEqual([]);
    expect(response.data?.count).toBe(0);
    expect(response.data?.source).toBe('unknown');
    expect(response.data?.cache_hit).toBe(true);
    expect(response.data?.cache_stale).toBe(false);
    expect(response.data?.static_fallback).toBe(true);
  });

  it('marks cache_stale from source when header is absent', async () => {
    mockGet.mockResolvedValue({
      data: {
        success: true,
        message: 'ok',
        data: {
          markets: ['BTC-USD'],
          count: 1,
          source: 'cache_stale',
        },
        timestamp: '2026-05-16T00:00:00.000Z',
      },
      headers: {},
    });

    const response = await api.getPerpetualMarkets();

    expect(response.data?.markets).toEqual(['BTC-USD']);
    expect(response.data?.count).toBe(1);
    expect(response.data?.source).toBe('cache_stale');
    expect(response.data?.cache_stale).toBe(true);
    expect(response.data?.static_fallback).toBe(false);
  });

  it('passes the market universe fields through untouched', async () => {
    const detail = {
      ticker: 'BTC-USD',
      status: 'ACTIVE',
      volume_24h: 2377823.0794,
      open_interest: 191.639,
      open_interest_usd: 16125208.1,
      next_funding_rate: -0.00000027,
      oracle_price: 84143.7,
      trades_24h: 1346,
    };
    mockGet.mockResolvedValue({
      data: {
        success: true,
        message: 'ok',
        data: {
          markets: ['BTC-USD'],
          market_details: [detail],
          count: 1,
          source: 'dydx',
          include_settled: false,
          active_total: 78,
          inactive_total: 218,
        },
        timestamp: '2026-09-26T00:00:00.000Z',
      },
      headers: {},
    });

    const response = await api.getPerpetualMarkets();

    expect(response.data?.market_details).toEqual([detail]);
    expect(response.data?.include_settled).toBe(false);
    expect(response.data?.active_total).toBe(78);
    expect(response.data?.inactive_total).toBe(218);
  });

  it('forwards the limit and the include_settled flag as query parameters', async () => {
    mockGet.mockResolvedValue({
      data: { success: true, message: 'ok', data: { markets: [], count: 0, source: 'dydx' } },
      headers: {},
    });

    await api.getPerpetualMarkets(25);
    expect(mockGet).toHaveBeenLastCalledWith('/api/v1/markets/perpetuals?limit=25');

    await api.getPerpetualMarkets(0, { includeSettled: true });
    expect(mockGet).toHaveBeenLastCalledWith('/api/v1/markets/perpetuals?include_settled=true');

    await api.getPerpetualMarkets(3, { includeSettled: true });
    expect(mockGet).toHaveBeenLastCalledWith(
      '/api/v1/markets/perpetuals?limit=3&include_settled=true'
    );
  });

  it('asks for the backtest market list when the caller runs backtests', async () => {
    mockGet.mockResolvedValue({
      data: { success: true, message: 'ok', data: { markets: [], count: 0, source: 'dydx' } },
      headers: {},
    });

    await api.getPerpetualMarkets(0, { forBacktest: true });
    expect(mockGet).toHaveBeenLastCalledWith('/api/v1/markets/perpetuals?purpose=backtest');
  });
});
