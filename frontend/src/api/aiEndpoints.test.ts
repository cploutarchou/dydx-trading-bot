import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const mockGet = vi.fn();
const mockPost = vi.fn();

const mockAxiosInstance = {
  get: mockGet,
  post: mockPost,
  put: vi.fn(),
  delete: vi.fn(),
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  },
};

// Hoisted so the mocked module and the tests share one error class: the client
// only reads the response envelope from errors that are `instanceof AxiosError`.
const { MockAxiosError } = vi.hoisted(() => {
  class MockAxiosError extends Error {
    response?: { status?: number; data?: unknown; headers?: Record<string, unknown> };
    code?: string;
  }
  return { MockAxiosError };
});

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockAxiosInstance),
    post: vi.fn(),
    isCancel: vi.fn(() => false),
  },
  create: vi.fn(() => mockAxiosInstance),
  isAxiosError: vi.fn(() => false),
  isCancel: vi.fn(() => false),
  AxiosError: MockAxiosError,
}));

const rejectionWith = (status: number, data: unknown) => {
  const rejection = new MockAxiosError(`Request failed with status code ${status}`);
  rejection.response = { status, data };
  return rejection;
};

const evidenceSummary = {
  completed_runs: 2,
  trades_analysed: 40,
  pairs_analysed: 3,
  live_closed_trades: 0,
  live_open_positions: 0,
  live_available: false,
  cointegrated_pairs: 0,
  data_notes: [],
};

describe('AI endpoints', () => {
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
    mockPost.mockReset();
  });

  it('posts the strategy id to suggest-params and returns the structured envelope', async () => {
    mockPost.mockResolvedValue({
      data: {
        success: true,
        data: {
          provider: 'grok',
          model: 'grok-4.7',
          used_ai: true,
          content: "1. zscore_threshold: Current '1.5' -> Suggested '2'. Rationale: fewer entries.",
          summary: 'Fewer, stronger entries.',
          suggestions: [
            {
              parameter: 'zscore_threshold',
              label: 'Z-score entry threshold',
              unit: '',
              current: 1.5,
              suggested: 2,
              rationale: 'Fewer entries.',
              evidence: '40 trades over 2 runs.',
              risk: 'normal',
              backtest_only: false,
            },
          ],
          dropped: [],
          data_gaps: ['No live trades.'],
          evidence_summary: evidenceSummary,
        },
      },
    });

    const response = await api.suggestStrategyParams({
      provider: 'grok',
      strategy_id: 7,
      max_suggestions: 5,
    });

    expect(mockPost).toHaveBeenCalledWith('/api/v1/ai/strategies/suggest-params', {
      provider: 'grok',
      strategy_id: 7,
      max_suggestions: 5,
    });
    expect(response.data?.suggestions[0]?.suggested).toBe(2);
    expect(response.data?.evidence_summary.completed_runs).toBe(2);
    expect(response.data?.data_gaps).toEqual(['No live trades.']);
  });

  it('posts the run id to explain and the strategy id to market selection', async () => {
    mockPost.mockResolvedValue({
      data: {
        success: true,
        data: {
          provider: 'grok',
          model: 'grok-4.7',
          used_ai: true,
          content: 'A short reading.',
          evidence_summary: evidenceSummary,
        },
      },
    });

    const explained = await api.explainBacktest({ provider: 'grok', run_id: 'run-1' });
    await api.selectAIMarkets({ provider: 'grok', mode: 'ai_recommended', strategy_id: 7 });

    expect(mockPost).toHaveBeenNthCalledWith(1, '/api/v1/ai/backtests/explain', {
      provider: 'grok',
      run_id: 'run-1',
    });
    expect(mockPost).toHaveBeenNthCalledWith(2, '/api/v1/ai/market-filters/select', {
      provider: 'grok',
      mode: 'ai_recommended',
      strategy_id: 7,
    });
    expect(explained.data?.evidence_summary.trades_analysed).toBe(40);
  });

  it('surfaces the backend error text instead of the axios status message', async () => {
    mockPost.mockRejectedValueOnce(
      rejectionWith(429, { success: false, error: 'CHAT_RATE_LIMITED: slow down' })
    );
    await expect(api.suggestStrategyParams({ strategy_id: 7 })).rejects.toThrow(
      'CHAT_RATE_LIMITED: slow down'
    );

    mockPost.mockRejectedValueOnce(
      rejectionWith(404, { success: false, error: 'Backtest run not found' })
    );
    await expect(api.explainBacktest({ run_id: 'run-x' })).rejects.toThrow(
      'Backtest run not found'
    );

    mockPost.mockRejectedValueOnce(
      rejectionWith(502, { success: false, error: 'The AI provider is unavailable' })
    );
    await expect(api.selectAIMarkets({ provider: 'grok', mode: 'ai_recommended' })).rejects.toThrow(
      'The AI provider is unavailable'
    );
  });
});
