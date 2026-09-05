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
});
