// Enhanced Auth Store with comprehensive TypeScript support
// Includes authentication state, preferences, and session management

import { create } from 'zustand';
import { persist, subscribeWithSelector } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import { enhancedApiClient } from '../api/enhancedClient';
import { cacheUtils } from '../api/queryClient';
import type { User } from '../api/types';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const getErrorMessage = (error: unknown, fallback: string): string =>
  error instanceof Error ? error.message : fallback;

const normalizeUser = (user: Partial<User> | null | undefined): User | null => {
  if (!user || typeof user.id !== 'number' || !user.username || !user.email || !user.created_at) {
    return null;
  }

  return {
    id: user.id,
    username: user.username,
    email: user.email,
    full_name: user.full_name,
    avatar: user.avatar,
    is_active: user.is_active ?? true,
    is_admin: user.is_admin ?? false,
    created_at: user.created_at,
    updated_at: user.updated_at,
    profile: user.profile,
  };
};

// Auth state interface
interface AuthState {
  // User data
  user: User | null;
  isAuthenticated: boolean;

  // Loading states
  isLoading: boolean;
  isLoggingIn: boolean;
  isLoggingOut: boolean;
  isRefreshing: boolean;

  // Error states
  error: string | null;
  lastLoginAttempt: number | null;

  // Session data
  sessionStarted: number | null;
  lastActivity: number;
  rememberMe: boolean;

  // Preferences
  preferences: UserPreferences;
}

interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  currency: 'USD' | 'EUR' | 'BTC';
  timezone: string;
  notifications: {
    trades: boolean;
    alerts: boolean;
    system: boolean;
    email: boolean;
    push: boolean;
  };
  dashboard: {
    defaultView: 'overview' | 'bots' | 'backtests';
    autoRefresh: boolean;
    refreshInterval: number;
    showAdvancedMetrics: boolean;
  };
}

// Auth actions interface
interface AuthActions {
  // Authentication
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  refreshToken: () => Promise<void>;

  // User management
  updateUser: (updates: Partial<User>) => void;
  updatePreferences: (preferences: Partial<UserPreferences>) => void;

  // Session management
  updateActivity: () => void;
  checkSession: () => boolean;

  // Error handling
  clearError: () => void;
  setError: (error: string) => void;

  // State management
  reset: () => void;
  initialize: () => Promise<void>;
}

type AuthStore = AuthState & AuthActions;

// Default preferences
const defaultPreferences: UserPreferences = {
  theme: 'dark',
  currency: 'USD',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  notifications: {
    trades: true,
    alerts: true,
    system: true,
    email: true,
    push: false,
  },
  dashboard: {
    defaultView: 'overview',
    autoRefresh: true,
    refreshInterval: 30000, // 30 seconds
    showAdvancedMetrics: false,
  },
};

// Create enhanced auth store
export const useAuthStore = create<AuthStore>()(
  subscribeWithSelector(
    persist(
      immer((set, get) => ({
        // Initial state
        user: null,
        isAuthenticated: false,
        isLoading: false,
        isLoggingIn: false,
        isLoggingOut: false,
        isRefreshing: false,
        error: null,
        lastLoginAttempt: null,
        sessionStarted: null,
        lastActivity: Date.now(),
        rememberMe: false,
        preferences: defaultPreferences,

        // Authentication actions
        login: async (username: string, password: string) => {
          set((state) => {
            state.isLoggingIn = true;
            state.error = null;
            state.lastLoginAttempt = Date.now();
          });

          try {
            await enhancedApiClient.login(username, password);
            const userResponse = await enhancedApiClient.getCurrentUser();
            const currentUser = normalizeUser((userResponse.data || null) as Partial<User> | null);

            set((state) => {
              state.user = currentUser;
              state.isAuthenticated = true;
              state.sessionStarted = Date.now();
              state.lastActivity = Date.now();
              state.rememberMe = true;
              state.isLoggingIn = false;
              state.error = null;
            });
          } catch (error: unknown) {
            set((state) => {
              state.error = getErrorMessage(error, 'Login failed');
              state.isLoggingIn = false;
              state.isAuthenticated = false;
              state.user = null;
            });
            throw error;
          }
        },

        logout: async () => {
          set((state) => {
            state.isLoggingOut = true;
          });

          try {
            // Clear API client
            enhancedApiClient.logout();

            // Clear all cached data
            cacheUtils.clearCache();

            set((state) => {
              state.user = null;
              state.isAuthenticated = false;
              state.sessionStarted = null;
              state.isLoggingOut = false;
              state.error = null;
              // Keep preferences
            });
          } catch (error: unknown) {
            console.error('Logout error:', error);
            // Force logout even on error
            set((state) => {
              state.user = null;
              state.isAuthenticated = false;
              state.sessionStarted = null;
              state.isLoggingOut = false;
            });
          }
        },

        register: async (username: string, email: string, password: string) => {
          set((state) => {
            state.isLoading = true;
            state.error = null;
          });

          try {
            await enhancedApiClient.register(username, email, password);

            // Auto-login after registration
            await get().login(username, password);
          } catch (error: unknown) {
            set((state) => {
              state.error = getErrorMessage(error, 'Registration failed');
              state.isLoading = false;
            });
            throw error;
          }
        },

        refreshToken: async () => {
          if (get().isRefreshing) return;

          set((state) => {
            state.isRefreshing = true;
          });

          try {
            await enhancedApiClient.refreshAccessToken();

            set((state) => {
              state.isRefreshing = false;
              state.lastActivity = Date.now();
            });
          } catch (error) {
            console.error('Token refresh failed:', error);

            set((state) => {
              state.isRefreshing = false;
              state.error = 'Session expired';
            });

            // Force logout on refresh failure
            await get().logout();
            throw error;
          }
        },

        // User management
        updateUser: (updates: Partial<User>) => {
          set((state) => {
            if (state.user) {
              state.user = { ...state.user, ...updates };
            }
          });
        },

        updatePreferences: (preferences: Partial<UserPreferences>) => {
          set((state) => {
            state.preferences = { ...state.preferences, ...preferences };
          });
        },

        // Session management
        updateActivity: () => {
          set((state) => {
            state.lastActivity = Date.now();
          });
        },

        checkSession: () => {
          const { sessionStarted, lastActivity, rememberMe } = get();

          if (!sessionStarted) return false;

          const now = Date.now();
          const sessionAge = now - sessionStarted;
          const inactiveTime = now - lastActivity;

          // Session limits
          const maxSessionAge = rememberMe ? 7 * 24 * 60 * 60 * 1000 : 24 * 60 * 60 * 1000; // 7 days or 1 day
          const maxInactiveTime = 4 * 60 * 60 * 1000; // 4 hours

          if (sessionAge > maxSessionAge || inactiveTime > maxInactiveTime) {
            get().logout();
            return false;
          }

          return true;
        },

        // Error handling
        clearError: () => {
          set((state) => {
            state.error = null;
          });
        },

        setError: (error: string) => {
          set((state) => {
            state.error = error;
          });
        },

        // State management
        reset: () => {
          set((state) => {
            state.user = null;
            state.isAuthenticated = false;
            state.isLoading = false;
            state.isLoggingIn = false;
            state.isLoggingOut = false;
            state.isRefreshing = false;
            state.error = null;
            state.lastLoginAttempt = null;
            state.sessionStarted = null;
            state.lastActivity = Date.now();
            state.rememberMe = false;
            state.preferences = defaultPreferences;
          });
        },

        initialize: async () => {
          set((state) => {
            state.isLoading = true;
          });

          try {
            // Check if we have stored auth data
            if (enhancedApiClient.isAuthenticated()) {
              const userResponse = await enhancedApiClient.getCurrentUser();
              const currentUser = normalizeUser(
                (userResponse.data || null) as Partial<User> | null
              );

              set((state) => {
                state.user = currentUser;
                state.isAuthenticated = true;
                state.lastActivity = Date.now();
                state.isLoading = false;
              });
            } else {
              set((state) => {
                state.isLoading = false;
              });
            }
          } catch (error: unknown) {
            console.error('Auth initialization failed:', error);
            set((state) => {
              state.isLoading = false;
              state.error = 'Failed to initialize session';
            });

            // Clear invalid auth data
            enhancedApiClient.logout();
          }
        },
      })),
      {
        name: 'auth-store',
        partialize: (state) => ({
          user: state.user,
          isAuthenticated: state.isAuthenticated,
          sessionStarted: state.sessionStarted,
          rememberMe: state.rememberMe,
          preferences: state.preferences,
        }),
        version: 2, // Increment when changing store structure
        migrate: (persistedState: unknown, version: number) => {
          // Handle store migrations
          const state = isRecord(persistedState) ? persistedState : {};
          if (version < 2) {
            const statePreferences = isRecord(state.preferences) ? state.preferences : {};
            return {
              ...state,
              preferences: { ...defaultPreferences, ...statePreferences },
            };
          }
          return state;
        },
      }
    )
  )
);

// Subscribe to auth state changes
useAuthStore.subscribe(
  (state) => state.isAuthenticated,
  (isAuthenticated, previousIsAuthenticated) => {
    // Handle authentication state changes
    if (!isAuthenticated && previousIsAuthenticated) {
      // Clear sensitive data
      cacheUtils.clearCache();
    }
  }
);

// Auto-check session validity
setInterval(() => {
  const store = useAuthStore.getState();
  if (store.isAuthenticated) {
    store.checkSession();
  }
}, 60000); // Check every minute

// Auto-update activity on user interaction
const updateActivity = () => {
  const store = useAuthStore.getState();
  if (store.isAuthenticated) {
    store.updateActivity();
  }
};

// Listen for user activity
['click', 'keydown', 'scroll', 'touchstart'].forEach((event) => {
  document.addEventListener(event, updateActivity, { passive: true });
});

export default useAuthStore;
