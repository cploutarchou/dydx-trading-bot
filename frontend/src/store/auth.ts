/**
 * Zustand store for authentication state
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../api';

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
                console.log('🔐 auth.ts: login() called with username:', username);
                set({ loading: true, error: null });
                try {
                    console.log('🔐 auth.ts: Calling api.login()');
                    const loginResult = await api.login({ username, password });
                    console.log('🔐 auth.ts: api.login() succeeded:', loginResult);

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

                    console.log('🔐 auth.ts: Calling getCurrentUser()');
                    await get().getCurrentUser();
                    console.log('🔐 auth.ts: getCurrentUser() succeeded');
                } catch (error: any) {
                    console.error('❌ auth.ts: Login error:', error);
                    set({ error: error.message || 'Login failed' });
                } finally {
                    set({ loading: false });
                }
            },

            register: async (username: string, email: string, password: string) => {
                console.log('🔐 auth.ts: register() called with username:', username);
                set({ loading: true, error: null });
                try {
                    console.log('🔐 auth.ts: Calling api.register()');
                    const registerResponse = await api.register({ username, email, password });
                    console.log('🔐 auth.ts: api.register() succeeded:', registerResponse);

                    // Registration successful, now try to auto-login
                    console.log('🔐 auth.ts: Registration successful, attempting auto-login');
                    await get().login(username, password);
                    console.log('🔐 auth.ts: Auto-login after registration succeeded');
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
                console.log('🔐 auth.ts: logout called');
                api.logout();
                set({ user: null });
            },

            getCurrentUser: async () => {
                try {
                    const response = await api.getCurrentUser();
                    // API returns UserResponse directly
                    const userData = response.data || response;
                    console.log('🔐 auth.ts: getCurrentUser response:', userData);
                    set({ user: userData });
                } catch (error) {
                    console.error('❌ auth.ts: getCurrentUser failed:', error);
                    set({ user: null });
                }
            },

            isAuthenticated: () => {
                return get().user !== null;
            },

            setup2FA: async () => {
                console.log('🔐 auth.ts: setup2FA() called');
                set({ loading: true, error: null });
                try {
                    const response = await api.setup2FA();
                    const { qr_code, secret, backup_codes } = response.data || response;
                    set({
                        twoFAQRCode: qr_code,
                        twoFASecret: secret,
                        backupCodes: backup_codes,
                    });
                    console.log('🔐 auth.ts: 2FA setup successful');
                } catch (error: Error | unknown) {
                    const errorMessage = error instanceof Error ? error.message : 'Failed to setup 2FA';
                    console.error('❌ auth.ts: setup2FA failed:', error);
                    set({ error: errorMessage });
                } finally {
                    set({ loading: false });
                }
            },

            verify2FA: async (token: string) => {
                console.log('🔐 auth.ts: verify2FA() called');
                set({ loading: true, error: null });
                try {
                    const response = await api.verify2FA(token);
                    if (response.success) {
                        set({
                            twoFARequired: false,
                            twoFAQRCode: undefined,
                            twoFASecret: undefined,
                        });
                        console.log('🔐 auth.ts: 2FA verification successful');
                    }
                } catch (error: Error | unknown) {
                    const errorMessage = error instanceof Error ? error.message : 'Failed to verify 2FA token';
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
            name: 'auth-store', // localStorage key
            partialize: (state) => ({
                user: state.user, // Only persist user, not loading/error
            }),
        }
    )
);
