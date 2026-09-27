import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiRequestError, getApiErrorCode } from './requestError';

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

describe('strategy chat API', () => {
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

  it('reads the conversation of one strategy', async () => {
    mockGet.mockResolvedValue({
      data: { success: true, data: { session: null, messages: [], runtime_active: false } },
    });

    const response = await api.getStrategyChat(7);

    expect(mockGet).toHaveBeenCalledWith('/api/v1/strategies/7/chat');
    expect(response.data).toEqual({ session: null, messages: [], runtime_active: false });
  });

  it('posts a message with the session and provider', async () => {
    mockPost.mockResolvedValue({ data: { success: true, data: { session: {}, messages: [] } } });

    await api.sendStrategyChatMessage(7, { session_id: 11, content: 'Hi', provider: 'grok' });

    expect(mockPost).toHaveBeenCalledWith('/api/v1/strategies/7/chat/messages', {
      session_id: 11,
      content: 'Hi',
      provider: 'grok',
    });
  });

  it('applies the selected fields with the running acknowledgement', async () => {
    mockPost.mockResolvedValue({
      data: {
        success: true,
        data: {
          strategy: { id: 7, name: 'S', candle_resolution: '4HOURS' },
          message: { id: 22, proposal_status: 'applied' },
        },
      },
    });

    const response = await api.applyStrategyChatProposal(7, 22, {
      fields: ['zscore_threshold'],
      acknowledge_running: true,
    });

    expect(mockPost).toHaveBeenCalledWith('/api/v1/strategies/7/chat/messages/22/apply', {
      fields: ['zscore_threshold'],
      acknowledge_running: true,
    });
    expect(response.data?.strategy.resolution).toBe('4HOURS');
    expect(response.data?.message.proposal_status).toBe('applied');
  });

  it('creates a strategy and dismisses a proposal on their own routes', async () => {
    mockPost.mockResolvedValue({ data: { success: true, data: { message: { id: 22 } } } });

    await api.createStrategyFromChatProposal(7, 22, { name: 'Variant', fields: ['slippage'] });
    await api.dismissStrategyChatProposal(7, 22);
    await api.startStrategyChatSession(7);

    expect(mockPost).toHaveBeenNthCalledWith(
      1,
      '/api/v1/strategies/7/chat/messages/22/create-strategy',
      { name: 'Variant', fields: ['slippage'] }
    );
    expect(mockPost).toHaveBeenNthCalledWith(
      2,
      '/api/v1/strategies/7/chat/messages/22/dismiss',
      {}
    );
    expect(mockPost).toHaveBeenNthCalledWith(3, '/api/v1/strategies/7/chat/sessions', {});
  });

  it('keeps the backend code and status on a failed call', async () => {
    mockPost.mockRejectedValue(
      rejectionWith(409, {
        success: false,
        error: 'The strategy is running; confirm to save anyway',
        code: 'STRATEGY_RUNNING_ACK_REQUIRED',
      })
    );

    const failure = await api
      .applyStrategyChatProposal(7, 22, { fields: ['zscore_threshold'] })
      .catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiRequestError);
    expect(failure).toMatchObject({
      message: 'The strategy is running; confirm to save anyway',
      status: 409,
      code: 'STRATEGY_RUNNING_ACK_REQUIRED',
    });
    expect(getApiErrorCode(failure)).toBe('STRATEGY_RUNNING_ACK_REQUIRED');
  });

  it('reports no code when the request never got a response', async () => {
    mockPost.mockRejectedValue(new MockAxiosError('Network Error'));

    const failure = await api
      .sendStrategyChatMessage(7, { content: 'Hi' })
      .catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiRequestError);
    expect(failure).toMatchObject({ message: 'Network Error', status: null, code: null });
  });
});
