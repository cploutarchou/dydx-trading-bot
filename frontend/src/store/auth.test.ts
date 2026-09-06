import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

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
