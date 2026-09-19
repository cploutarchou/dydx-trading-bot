/**
 * Zustand store for authentication state
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../api';
import { clearUserScopedQueries } from '../api/queryClient';
import { perfMark, perfMeasure } from '../utils/perf';

const withTimeout = async <T>(
  promise: Promise<T>,
  timeoutMs: number,
  label: string
): Promise<T> => {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  const timeoutPromise = new Promise<T>((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error(`${label} timed out after ${timeoutMs}ms`));
    }, timeoutMs);
  });

  try {
    return await Promise.race([promise, timeoutPromise]);
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
};

const getVerifiedTwoFAMessage = (response: {
  success: boolean;
  message?: string;
}): string | null => {
  if (response.success) {
    return null;
  }

  return response.message || 'Failed to verify 2FA token';
};

// Every transition to the logged-out state (explicit logout, expired or
// rejected session) drops the user-scoped React Query cache, so the next user
// on this browser never sees the previous user's balances, bots or trades.
const buildLoggedOutState = () => {
  clearUserScopedQueries();
  return loggedOutState();
};

const loggedOutState = () => ({
  user: null,
  loading: false,
  sessionLoading: false,
  sessionInitialized: true,
  error: null,
  twoFARequired: false,
  twoFASecret: undefined,
  twoFAQRCode: undefined,
  backupCodes: undefined,
});

const hasActiveSession = (): boolean => api.hasToken() || api.hasSessionHint();
let activeInitializeSession: Promise<void> | null = null;

interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  is_admin: boolean;
  mfa_enabled?: boolean;
  privileged_mfa_required?: boolean;
  password_change_required: boolean;
  created_at: string;
  avatar?: string; // Base64 or URL to avatar image
  full_name?: string;
}

interface AuthStore {
  user: User | null;
  loading: boolean;
  sessionLoading: boolean;
  sessionInitialized: boolean;
  error: string | null;
  twoFARequired: boolean;
  /** True after a password-only login for an MFA-enrolled account. */
  mfaChallengeRequired: boolean;
  twoFASecret?: string;
  twoFAQRCode?: string;
  backupCodes?: string[];
  login: (username: string, password: string, turnstileToken?: string) => Promise<void>;
  completeMfaChallenge: (token: string) => Promise<void>;
  cancelMfaChallenge: () => void;
  /** Arms the login page's TOTP step for an existing pending-MFA session. */
  armMfaChallenge: () => void;
  register: (
    username: string,
    email: string,
    password: string,
    invitationCode?: string,
    turnstileToken?: string
  ) => Promise<void>;
  setup2FA: () => Promise<void>;
  verify2FA: (token: string) => Promise<void>;
  logout: () => void;
  getCurrentUser: () => Promise<void>;
  initializeSession: () => Promise<void>;
  isAuthenticated: () => boolean;
  has2FAEnabled: () => boolean;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
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

      login: async (username: string, password: string, turnstileToken?: string) => {
        set({ loading: true, error: null, mfaChallengeRequired: false });
        try {
          const loginResult = await api.login({
            username,
            password,
            ...(turnstileToken ? { cf_turnstile_response: turnstileToken } : {}),
          });
          if (loginResult?.access_token) {
            api.setToken(loginResult.access_token, true);
          }

          if (loginResult?.mfa_required) {
            // Password accepted; the TOTP step must complete before a session
            // exists. Keep credentials out of store state — the pending
            // HttpOnly session cookie authorizes the challenge call.
            set({ mfaChallengeRequired: true });
            return;
          }

          await get().getCurrentUser();
        } catch (error: unknown) {
          console.error('❌ auth.ts: Login failed');
          set({ error: 'Unable to sign in with those credentials.', user: null });
          return Promise.reject(error);
        } finally {
          set({ loading: false });
        }
      },

      completeMfaChallenge: async (token: string) => {
        set({ loading: true, error: null });
        try {
          await api.completeMfaChallenge(token);
          api.clearPendingMFAChallenge();
          set({ mfaChallengeRequired: false });
          await get().getCurrentUser();
        } catch {
          // Keep the challenge UI up so the user can retry with a fresh code;
          // the page shows a specific invalid-code message.
          set({ error: 'That code was invalid or expired. Try the latest one.' });
          return Promise.reject(new Error('invalid_mfa_code'));
        } finally {
          set({ loading: false });
        }
      },

      cancelMfaChallenge: () => {
        api.clearPendingMFAChallenge();
        set({ mfaChallengeRequired: false, error: null });
      },

      armMfaChallenge: () => {
        // A pending (password-only) session exists but awaits its TOTP
        // challenge: show the login challenge step directly — the pending
        // HttpOnly cookie still authorizes the challenge call, so the user
        // skips the password prompt.
        set({ ...buildLoggedOutState(), mfaChallengeRequired: true });
      },

      register: async (
        username: string,
        email: string,
        password: string,
        invitationCode?: string,
        turnstileToken?: string
      ) => {
        set({ loading: true, error: null });
        try {
          await api.register({
            username,
            email,
            password,
            ...(invitationCode ? { invitation_code: invitationCode } : {}),
            ...(turnstileToken ? { cf_turnstile_response: turnstileToken } : {}),
          });

          // Registration successful, now try to auto-login
          await get().login(username, password);
        } catch (error: Error | unknown) {
          const errorMessage = error instanceof Error ? error.message : 'Registration failed';
          console.error('❌ auth.ts: register() error:', error);
          set({ error: errorMessage, loading: false });
          throw error; // Re-throw so component can handle it
        } finally {
          // Make sure loading is always set to false
          set((state) => ({ loading: state.error ? state.loading : false }));
        }
      },

      logout: () => {
        api.logout();
        set(buildLoggedOutState());
      },

      getCurrentUser: async () => {
        try {
          const response = await api.getCurrentUser();
          const userData = response.data;
          if (!userData) {
            throw new Error('Current user response did not include a user payload');
          }
          set({ user: userData, error: null });
        } catch (error) {
          console.error('❌ auth.ts: getCurrentUser failed:', error);
          api.logout();
          set(buildLoggedOutState());
        }
      },

      initializeSession: async () => {
        if (activeInitializeSession) {
          return activeInitializeSession;
        }

        // Signal that auth bootstrap is in flight so ProtectedRoute can show a skeleton
        // instead of redirecting to /login prematurely.
        activeInitializeSession = (async () => {
          set({ sessionLoading: true, sessionInitialized: false, error: null });
          perfMark('session:init:start');

          try {
            const allowCookieRefresh = api.shouldAttemptCookieRefresh();
            const restored = await withTimeout(
              api.restoreSession({
                allowCookieRefresh,
              }),
              10000,
              'restoreSession'
            );
            if (!restored) {
              if (api.consumePendingMFAChallenge()) {
                // Pending MFA session: arm the login page's TOTP step instead
                // of probing /users/me — the probe would 401 and log out,
                // destroying the pending challenge session.
                set({ ...buildLoggedOutState(), mfaChallengeRequired: true });
                return;
              }
              if (allowCookieRefresh) {
                console.warn(
                  '⚠️ auth.ts: restoreSession did not recover a token, probing current user via cookie session'
                );
                await withTimeout(
                  get().getCurrentUser(),
                  10000,
                  'initializeSession cookie session probe'
                );
                if (get().user) {
                  return;
                }
              }

              set(buildLoggedOutState());
              return;
            }

            await withTimeout(get().getCurrentUser(), 10000, 'initializeSession current user');
          } catch (error: unknown) {
            console.error('❌ auth.ts: initializeSession failed:', error);
            api.logout();
            set({
              ...buildLoggedOutState(),
              error: error instanceof Error ? error.message : 'Session restore failed',
            });
          } finally {
            perfMark('session:init:end');
            perfMeasure('session:init:duration', 'session:init:start', 'session:init:end');
            set({ sessionLoading: false, sessionInitialized: true });
            activeInitializeSession = null;
          }
        })();

        return activeInitializeSession;
      },

      isAuthenticated: () => {
        return get().user !== null && hasActiveSession();
      },

      setup2FA: async () => {
        set({ loading: true, error: null });
        try {
          const response = await api.setup2FA();
          const setupData = (response.data || {}) as {
            qr_code?: string;
            secret?: string;
            backup_codes?: string[];
          };
          set({
            twoFAQRCode: setupData.qr_code,
            twoFASecret: setupData.secret,
            backupCodes: setupData.backup_codes,
          });
        } catch (error: Error | unknown) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to setup 2FA';
          console.error('❌ auth.ts: setup2FA failed:', error);
          set({ error: errorMessage });
          return Promise.reject(error);
        } finally {
          set({ loading: false });
        }
      },

      verify2FA: async (token: string) => {
        set({ loading: true, error: null });
        try {
          const response = await api.verify2FA(token);
          const verifyMessage = getVerifiedTwoFAMessage(response);
          if (verifyMessage) {
            set({ error: verifyMessage });
            return Promise.reject(new Error(verifyMessage));
          }

          set({
            twoFARequired: false,
            twoFAQRCode: undefined,
            twoFASecret: undefined,
          });

          await get().getCurrentUser();
        } catch (error: Error | unknown) {
          const errorMessage =
            error instanceof Error ? error.message : 'Failed to verify 2FA token';
          console.error('❌ auth.ts: verify2FA failed:', error);
          set({ error: errorMessage });
          return Promise.reject(error);
        } finally {
          set({ loading: false });
        }
      },

      has2FAEnabled: () => {
        return get().user?.mfa_enabled ?? false;
      },
    }),
    {
      name: 'auth-store-legacy', // localStorage key (avoid collision with enhancedAuth store)
      partialize: (state) => ({
        user: state.user, // Only persist user, not loading/error
      }),
      onRehydrateStorage: () => (state) => {
        if (!state) {
          return;
        }

        if (!hasActiveSession()) {
          state.user = null;
          state.error = null;
          state.loading = false;
          state.sessionLoading = false;
          state.sessionInitialized = false;
          state.twoFARequired = false;
          state.twoFASecret = undefined;
          state.twoFAQRCode = undefined;
          state.backupCodes = undefined;
        }
      },
    }
  )
);
