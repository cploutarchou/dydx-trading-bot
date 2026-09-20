import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const mockPost = vi.fn();
const mockPut = vi.fn();

const mockAxiosInstance = {
  get: vi.fn(),
  post: mockPost,
  put: mockPut,
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

describe('strategy risk controls API', () => {
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
    mockPost.mockReset();
    mockPut.mockReset();
  });

  it('posts the fields with the acknowledgement flag and the selected network', async () => {
    mockPost.mockResolvedValue({
      data: {
        success: true,
        data: {
          id: 12,
          name: 'Live candidate',
          candle_resolution: '1HOUR',
          max_drawdown_pct: 0,
          trailing_stop_pct: 0,
          disabled_risk_controls: [
            { field: 'max_drawdown_pct', previous_value: 15 },
            { field: 'trailing_stop_pct', previous_value: 1 },
          ],
        },
        timestamp: '2026-09-21T00:00:00.000Z',
      },
    });

    const response = await api.disableUnenforcedRiskControls(
      12,
      ['max_drawdown_pct', 'trailing_stop_pct'],
      'mainnet'
    );

    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost).toHaveBeenCalledWith(
      '/api/v1/strategies/12/unenforced-risk-controls/disable',
      {
        fields: ['max_drawdown_pct', 'trailing_stop_pct'],
        acknowledged: true,
        network: 'mainnet',
      }
    );
    expect(response.data?.max_drawdown_pct).toBe(0);
    expect(response.data?.resolution).toBe('1HOUR');
    expect(response.data?.disabled_risk_controls).toEqual([
      { field: 'max_drawdown_pct', previous_value: 15 },
      { field: 'trailing_stop_pct', previous_value: 1 },
    ]);
  });

  it('omits the network when none is given', async () => {
    mockPost.mockResolvedValue({ data: { success: true, data: { id: 3, name: 'S' } } });

    await api.disableUnenforcedRiskControls(3, ['trailing_stop_pct']);

    expect(mockPost).toHaveBeenCalledWith('/api/v1/strategies/3/unenforced-risk-controls/disable', {
      fields: ['trailing_stop_pct'],
      acknowledged: true,
    });
  });

  it('surfaces the error string from the response envelope', async () => {
    const rejection = new MockAxiosError('Request failed with status code 400');
    rejection.response = {
      status: 400,
      data: { success: false, error: 'field "stop_loss_pct" cannot be disabled' },
    };
    mockPost.mockRejectedValue(rejection);

    await expect(
      api.disableUnenforcedRiskControls(12, ['stop_loss_pct'], 'testnet')
    ).rejects.toThrow('field "stop_loss_pct" cannot be disabled');
  });

  it('sends an explicit 0 for both limits when a strategy is updated', async () => {
    mockPut.mockResolvedValue({ data: { success: true, data: { id: 12, name: 'S' } } });

    await api.updateStrategy(12, {
      name: 'S',
      max_drawdown_pct: 0,
      trailing_stop_pct: 0,
    });

    expect(mockPut).toHaveBeenCalledTimes(1);
    const [url, payload] = mockPut.mock.calls[0] as [string, Record<string, unknown>];
    expect(url).toBe('/api/v1/strategies/12');
    expect(payload.max_drawdown_pct).toBe(0);
    expect(payload.trailing_stop_pct).toBe(0);
    expect(JSON.parse(JSON.stringify(payload))).toMatchObject({
      max_drawdown_pct: 0,
      trailing_stop_pct: 0,
    });
  });
});
