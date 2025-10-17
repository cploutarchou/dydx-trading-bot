/**
 * Zustand store for authentication state
 */

import create from 'zustand';
import api from './api';

interface User {
    id: number;
    username: string;
    email: string;
    is_active: boolean;
    is_admin: boolean;
    created_at: string;
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

export const useAuthStore = create<AuthStore>((set, get) => ({
    user: null,
    loading: false,
    error: null,

    login: async (username: string, password: string) => {
        set({ loading: true, error: null });
        try {
            await api.login({ username, password });
            await get().getCurrentUser();
        } catch (error: any) {
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
            set({ user: response.data || response });
        } catch (error) {
            set({ user: null });
        }
    },

    isAuthenticated: () => {
        return get().user !== null;
    },
}));
