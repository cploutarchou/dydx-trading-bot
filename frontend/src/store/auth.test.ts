import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const storage = new Map<string, string>();

const apiMock = {
  hasToken: vi.fn(() => true),
  login: vi.fn(),
  register: vi.fn(),
  setup2FA: vi.fn(),
  verify2FA: vi.fn(),
  setToken: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
  restoreSession: vi.fn(),
  shouldAttemptCookieRefresh: vi.fn(() => true),
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
  apiMock.shouldAttemptCookieRefresh.mockReturnValue(true);
  useAuthStore.setState({
    user: null,
    loading: false,
    sessionLoading: false,
    sessionInitialized: false,
    error: null,
    twoFARequired: false,
    twoFASecret: undefined,
    twoFAQRCode: undefined,
    backupCodes: undefined,
  });
});

describe('auth store session bootstrap', () => {
  it('falls back to a cookie-backed current-user probe when refresh restore returns false', async () => {
    apiMock.restoreSession.mockResolvedValue(false);
    apiMock.getCurrentUser.mockResolvedValue({
      success: true,
      message: 'ok',
      data: {
        id: 7,
        username: 'admin',
        email: 'admin@example.com',
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
    expect(useAuthStore.getState().sessionInitialized).toBe(true);
    expect(useAuthStore.getState().sessionLoading).toBe(false);
  });
});
