/**
 * Zustand store for authentication state
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../api';

const getErrorMessage = (error: unknown, fallback: string): string =>
  error instanceof Error ? error.message : fallback;

interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  avatar?: string; // Base64 or URL to avatar image
  full_name?: string;
}

interface AuthStore {
  user: User | null;
  loading: boolean;
  error: string | null;
  twoFARequired: boolean;
  twoFASecret?: string;
  twoFAQRCode?: string;
  backupCodes?: string[];
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
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
      error: null,
      twoFARequired: false,
      twoFASecret: undefined,
      twoFAQRCode: undefined,
      backupCodes: undefined,

      login: async (username: string, password: string) => {
        set({ loading: true, error: null });
        try {
          const loginResult = await api.login({ username, password });

          // Ensure token is set in api client (api.login already does this but be explicit)
          if (loginResult?.access_token) {
            api.setToken(loginResult.access_token, true);
            if (loginResult.refresh_token) {
              try {
                localStorage.setItem('refresh_token', loginResult.refresh_token);
              } catch (e) {
                console.warn('❌ auth.ts: Failed to persist refresh_token', e);
              }
            }
          }

          await get().getCurrentUser();
        } catch (error: unknown) {
          console.error('❌ auth.ts: Login error:', error);
          set({ error: getErrorMessage(error, 'Login failed') });
        } finally {
          set({ loading: false });
        }
      },

      register: async (username: string, email: string, password: string) => {
        set({ loading: true, error: null });
        try {
          await api.register({ username, email, password });

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
        set({ user: null });
      },

      getCurrentUser: async () => {
        try {
          const response = await api.getCurrentUser();
          const userData = response.data;
          set({ user: userData || null });
        } catch (error) {
          console.error('❌ auth.ts: getCurrentUser failed:', error);
          set({ user: null });
        }
      },

      initializeSession: async () => {
        set({ loading: true, error: null });

        try {
          const restored = await api.restoreSession();
          if (!restored) {
            set({ user: null, loading: false });
            return;
          }

          await get().getCurrentUser();
        } catch (error: unknown) {
          console.error('❌ auth.ts: initializeSession failed:', error);
          api.logout();
          set({
            user: null,
            error: error instanceof Error ? error.message : 'Session restore failed',
          });
        } finally {
          set({ loading: false });
        }
      },

      isAuthenticated: () => {
        return get().user !== null;
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
        } finally {
          set({ loading: false });
        }
      },

      verify2FA: async (token: string) => {
        set({ loading: true, error: null });
        try {
          const response = await api.verify2FA(token);
          if (response.success) {
            set({
              twoFARequired: false,
              twoFAQRCode: undefined,
              twoFASecret: undefined,
            });
          }
        } catch (error: Error | unknown) {
          const errorMessage =
            error instanceof Error ? error.message : 'Failed to verify 2FA token';
          console.error('❌ auth.ts: verify2FA failed:', error);
          set({ error: errorMessage });
        } finally {
          set({ loading: false });
        }
      },

      has2FAEnabled: () => {
        return get().user?.is_active ?? false;
      },
    }),
    {
      name: 'auth-store-legacy', // localStorage key (avoid collision with enhancedAuth store)
      partialize: (state) => ({
        user: state.user, // Only persist user, not loading/error
      }),
    }
  )
);
