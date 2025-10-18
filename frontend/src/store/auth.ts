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
    login: (username: string, password: string) => Promise<void>;
    register: (username: string, email: string, password: string) => Promise<void>;
    logout: () => void;
    getCurrentUser: () => Promise<void>;
    isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthStore>()(
    persist(
        (set, get) => ({
            user: null,
            loading: false,
            error: null,

            login: async (username: string, password: string) => {
                console.log('🔐 auth.ts: login() called with username:', username);
                set({ loading: true, error: null });
                try {
                    console.log('🔐 auth.ts: Calling api.login()');
                    const loginResult = await api.login({ username, password });
                    console.log('🔐 auth.ts: api.login() succeeded:', loginResult);
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
                set({ loading: true, error: null });
                try {
                    await api.register({ username, email, password });
                    await get().login(username, password);
                } catch (error: any) {
                    set({ error: error.message || 'Registration failed' });
                } finally {
                    set({ loading: false });
                }
            },

            logout: () => {
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
        }),
        {
            name: 'auth-store', // localStorage key
            partialize: (state) => ({
                user: state.user, // Only persist user, not loading/error
            }),
        }
    )
);
