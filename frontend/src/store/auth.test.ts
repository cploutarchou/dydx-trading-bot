import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const storage = new Map<string, string>();

const apiMock = {
  hasToken: vi.fn(() => true),
  hasSessionHint: vi.fn(() => true),
  login: vi.fn(),
  register: vi.fn(),
  setup2FA: vi.fn(),
  verify2FA: vi.fn(),
  setToken: vi.fn(),
  markSessionEstablishedForCookieAuth: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
  restoreSession: vi.fn(),
  shouldAttemptCookieRefresh: vi.fn(() => true),
  consumePendingMFAChallenge: vi.fn(() => false),
  clearPendingMFAChallenge: vi.fn(),
};

vi.mock('../api', () => ({
  default: apiMock,
}));

const clearUserScopedQueriesMock = vi.fn();

vi.mock('../api/queryClient', () => ({
  clearUserScopedQueries: clearUserScopedQueriesMock,
}));

vi.mock('../utils/perf', () => ({
  perfMark: vi.fn(),
  perfMeasure: vi.fn(),
}));

let useAuthStore: typeof import('./auth').useAuthStore;

beforeAll(async () => {
  Object.defineProperty(globalThis, 'localStorage', {
    value: {
      getItem: (key: string) => (storage.has(key) ? storage.get(key)! : null),
      setItem: (key: string, value: string) => {
        storage.set(key, value);
      },
      removeItem: (key: string) => {
        storage.delete(key);
      },
      clear: () => {
        storage.clear();
      },
    },
    configurable: true,
  });

  ({ useAuthStore } = await import('./auth'));
});

beforeEach(() => {
  storage.clear();
  vi.clearAllMocks();
  apiMock.hasToken.mockReturnValue(true);
  apiMock.hasSessionHint.mockReturnValue(true);
  apiMock.shouldAttemptCookieRefresh.mockReturnValue(true);
  apiMock.consumePendingMFAChallenge.mockReturnValue(false);
  useAuthStore.setState({
    user: null,
    loading: false,
    sessionLoading: false,
    sessionInitialized: false,
    sessionUnavailable: false,
    error: null,
    twoFARequired: false,
    mfaChallengeRequired: false,
    twoFASecret: undefined,
    twoFAQRCode: undefined,
    backupCodes: undefined,
  });
});

describe('auth store session bootstrap', () => {
  it('falls back to a cookie-backed current-user probe when refresh restore returns false', async () => {
    apiMock.hasToken.mockReturnValue(false);
    apiMock.hasSessionHint.mockReturnValue(true);
    apiMock.restoreSession.mockResolvedValue(false);
    apiMock.getCurrentUser.mockResolvedValue({
      success: true,
      message: 'ok',
      data: {
        id: 7,
        username: 'admin',
        email: 'admin@executionlab.io',
        role: 'admin',
        is_active: true,
        is_admin: true,
        password_change_required: false,
        created_at: '2026-06-02T00:00:00Z',
      },
    });

    await useAuthStore.getState().initializeSession();

    expect(apiMock.restoreSession).toHaveBeenCalledWith({ allowCookieRefresh: true });
    expect(apiMock.getCurrentUser).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().user?.username).toBe('admin');
    expect(useAuthStore.getState().isAuthenticated()).toBe(true);
    expect(useAuthStore.getState().sessionInitialized).toBe(true);
    expect(useAuthStore.getState().sessionLoading).toBe(false);
  });

  it('arms the TOTP challenge step instead of probing when a pending MFA session exists', async () => {
    apiMock.hasToken.mockReturnValue(false);
    apiMock.hasSessionHint.mockReturnValue(true);
    apiMock.restoreSession.mockResolvedValue(false);
    apiMock.consumePendingMFAChallenge.mockReturnValue(true);

    await useAuthStore.getState().initializeSession();

    // The /users/me probe would 401 and log out, destroying the pending
    // challenge session — it must not run.
    expect(apiMock.getCurrentUser).not.toHaveBeenCalled();
    expect(useAuthStore.getState().mfaChallengeRequired).toBe(true);
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated()).toBe(false);
    expect(useAuthStore.getState().sessionInitialized).toBe(true);
    expect(useAuthStore.getState().sessionLoading).toBe(false);
  });
});

describe('auth store logout', () => {
  it('clears user-scoped queries so the next user never sees cached data', () => {
    clearUserScopedQueriesMock.mockClear();

    useAuthStore.getState().logout();

    expect(apiMock.logout).toHaveBeenCalled();
    expect(clearUserScopedQueriesMock).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().user).toBeNull();
  });
});

const adminUser = {
  id: 7,
  username: 'admin',
  email: 'admin@executionlab.io',
  role: 'admin',
  is_active: true,
  is_admin: true,
  password_change_required: false,
  created_at: '2026-06-02T00:00:00Z',
};

const networkError = () => new AxiosError('Network Error', 'ERR_NETWORK');

const rejectionError = (status: number) =>
  new AxiosError(
    `Request failed with status code ${status}`,
    'ERR_BAD_REQUEST',
    undefined,
    undefined,
    {
      status,
      statusText: '',
      headers: {},
      data: {},
      config: { headers: new AxiosHeaders() },
    } as AxiosResponse
  );

// Runs the bootstrap under fake timers, advancing far enough to cover every
// retry delay and every per-call timeout in the store.
const runBootstrap = async () => {
  const run = useAuthStore.getState().initializeSession();
  await vi.advanceTimersByTimeAsync(60_000);
  await run;
};

describe('auth store session bootstrap on transient failures', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    apiMock.hasToken.mockReturnValue(false);
    apiMock.hasSessionHint.mockReturnValue(true);
    apiMock.restoreSession.mockResolvedValue(false);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('keeps the session and never logs out when the probe hits a network error', async () => {
    apiMock.getCurrentUser.mockRejectedValue(networkError());

    await runBootstrap();

    // One attempt plus two retries, then give up without touching the server session.
    expect(apiMock.getCurrentUser).toHaveBeenCalledTimes(3);
    expect(apiMock.logout).not.toHaveBeenCalled();
    expect(useAuthStore.getState().sessionUnavailable).toBe(true);
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().sessionInitialized).toBe(true);
    expect(useAuthStore.getState().sessionLoading).toBe(false);
  });

  it('logs out once, without retrying, when the backend answers 401', async () => {
    apiMock.getCurrentUser.mockRejectedValue(rejectionError(401));

    await runBootstrap();

    expect(apiMock.getCurrentUser).toHaveBeenCalledTimes(1);
    expect(apiMock.logout).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().sessionUnavailable).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().sessionInitialized).toBe(true);
  });

  it('recovers when a retry succeeds', async () => {
    apiMock.getCurrentUser
      .mockRejectedValueOnce(networkError())
      .mockResolvedValueOnce({ success: true, message: 'ok', data: adminUser });

    await runBootstrap();

    expect(apiMock.getCurrentUser).toHaveBeenCalledTimes(2);
    expect(apiMock.logout).not.toHaveBeenCalled();
    expect(useAuthStore.getState().user?.username).toBe('admin');
    expect(useAuthStore.getState().sessionUnavailable).toBe(false);
    expect(useAuthStore.getState().isAuthenticated()).toBe(true);
  });

  it('treats a probe that never answers as unavailable, not as a rejection', async () => {
    apiMock.getCurrentUser.mockReturnValue(new Promise(() => {}));

    await runBootstrap();

    expect(apiMock.getCurrentUser).toHaveBeenCalledTimes(3);
    expect(apiMock.logout).not.toHaveBeenCalled();
    expect(useAuthStore.getState().sessionUnavailable).toBe(true);
    expect(useAuthStore.getState().sessionInitialized).toBe(true);
  });

  it('keeps a restored session when the profile load fails with a server error', async () => {
    apiMock.hasToken.mockReturnValue(true);
    apiMock.restoreSession.mockResolvedValue(true);
    apiMock.getCurrentUser.mockRejectedValue(rejectionError(503));
    useAuthStore.setState({ user: adminUser });

    await runBootstrap();

    expect(apiMock.logout).not.toHaveBeenCalled();
    expect(useAuthStore.getState().user?.username).toBe('admin');
    expect(useAuthStore.getState().sessionUnavailable).toBe(true);
    expect(useAuthStore.getState().isAuthenticated()).toBe(true);
  });
});

describe('auth store login', () => {
  it('reports an unconfirmed session instead of failing when the profile load is unavailable', async () => {
    apiMock.login.mockResolvedValue({ access_token: 'token' });
    apiMock.getCurrentUser.mockRejectedValue(networkError());

    await useAuthStore.getState().login('admin', 'secret');

    expect(apiMock.logout).not.toHaveBeenCalled();
    expect(useAuthStore.getState().sessionUnavailable).toBe(true);
    expect(useAuthStore.getState().error).toContain('could not be confirmed');
    expect(useAuthStore.getState().loading).toBe(false);
  });
});
