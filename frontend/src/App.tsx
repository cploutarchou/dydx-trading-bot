/**
 * Main React App Entry Point
 * Enhanced with React Query, Error Boundaries, and Toast Notifications
 */

import { useQuery } from '@tanstack/react-query';
import React, { Suspense, lazy, useEffect, useRef } from 'react';
import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
  useLocation,
} from 'react-router-dom';
import api from './api';
import { QueryProvider } from './api/QueryProvider';
import { getCurrentPortalType } from './app/portal';
import { getPortalRouteManifest } from './app/routeManifest';
import {
  BACKOFFICE_ROLES,
  getUserWorkspaceRole,
  roleMatches,
  type WorkspaceRole,
} from './auth/roles';
import {
  ErrorBoundary as EnhancedErrorBoundary,
  ToastContainer,
  useToastStore,
} from './components/ErrorBoundary';
import { MainLayout } from './components/MainLayout';
import { RegistrationDisabledLoginGate } from './components/RegistrationDisabledLoginGate';
import { ThemeProvider } from './components/ThemeProvider';
import { LandingPage } from './pages/Landing';
import { LoginPage } from './pages/Login';
import { PricingPage } from './pages/Pricing';
import { PublicServicePage } from './pages/PublicServicePage';
import { RegisterPage } from './pages/Register';
import { useAuthStore } from './store/auth';
import { useUIPreferencesStore } from './store/uiPreferences';

// Legacy error boundary removed - using enhanced version from components/ErrorBoundary

const AUTH_BOOTSTRAP_TIMEOUT_MS = 12000;

const withTimeout = async <T,>(
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

const AuthSkeleton: React.FC = () => (
  <div className="min-h-screen bg-slate-900 flex items-center justify-center">
    <div className="w-8 h-8 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
  </div>
);

const ForcePasswordChangePage = lazy(() =>
  import('./pages/ForcePasswordChange').then((module) => ({
    default: module.ForcePasswordChangePage,
  }))
);
const TwoFactorAuthPage = lazy(() =>
  import('./pages/TwoFactorAuth').then((module) => ({ default: module.TwoFactorAuthPage }))
);
const UnauthorizedPage = lazy(() =>
  import('./pages/Unauthorized').then((module) => ({ default: module.UnauthorizedPage }))
);
const ComingSoonPage = lazy(() =>
  import('./pages/ComingSoon').then((module) => ({ default: module.ComingSoonPage }))
);

const COMING_SOON_AUTH_BYPASS_PATHS = new Set([
  '/login',
  '/2fa-setup',
  '/force-password',
  '/unauthorized',
]);

const ProtectedRoute: React.FC<{ children: React.ReactNode; allowedRoles?: WorkspaceRole[] }> = ({
  children,
  allowedRoles,
}) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const sessionLoading = useAuthStore((state) => state.sessionLoading);
  const sessionInitialized = useAuthStore((state) => state.sessionInitialized);
  const user = useAuthStore((state) => state.user);

  // Wait until bootstrap resolves before deciding to redirect.
  if (!sessionInitialized || (!isAuthenticated && sessionLoading)) {
    return <AuthSkeleton />;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (user.password_change_required) {
    return <Navigate to="/force-password" replace />;
  }

  const requiresPrivilegedMFA =
    Boolean(allowedRoles && allowedRoles.length > 0) &&
    (allowedRoles?.some((role) => BACKOFFICE_ROLES.includes(role)) ?? false);

  if (requiresPrivilegedMFA && user.privileged_mfa_required && !user.mfa_enabled) {
    return <Navigate to="/2fa-setup" replace />;
  }

  if (!roleMatches(getUserWorkspaceRole(user), allowedRoles)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <MainLayout>{children}</MainLayout>;
};

const PasswordRotationRoute: React.FC = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const sessionLoading = useAuthStore((state) => state.sessionLoading);
  const sessionInitialized = useAuthStore((state) => state.sessionInitialized);
  const user = useAuthStore((state) => state.user);

  if (!sessionInitialized || (!isAuthenticated && sessionLoading)) {
    return <AuthSkeleton />;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (!user.password_change_required) {
    return <Navigate to="/dashboard" replace />;
  }

  return <ForcePasswordChangePage />;
};

const ComingSoonGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const portal = getCurrentPortalType();
  const location = useLocation();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const appConfigQuery = useQuery({
    queryKey: ['public', 'app-config'],
    queryFn: async () => {
      const response = await api.getPublicAppConfig();
      return response.data;
    },
    staleTime: 30_000,
    retry: 1,
    enabled: portal === 'client',
  });

  if (portal !== 'client') {
    return <>{children}</>;
  }

  if (appConfigQuery.isLoading) {
    return <AuthSkeleton />;
  }

  if (appConfigQuery.isError || !appConfigQuery.data?.coming_soon_enabled) {
    return <>{children}</>;
  }

  const isAuthBypassPath = COMING_SOON_AUTH_BYPASS_PATHS.has(location.pathname);
  if (isAuthenticated || isAuthBypassPath) {
    return <>{children}</>;
  }

  return <ComingSoonPage />;
};

export const App: React.FC = () => {
  const portal = getCurrentPortalType();
  const portalRoutes = getPortalRouteManifest(portal);
  const logout = useAuthStore((state) => state.logout);
  const initializeSession = useAuthStore((state) => state.initializeSession);
  const toastWarning = useToastStore((state) => state.warning);
  const language = useUIPreferencesStore((state) => state.language);
  const refreshWarningLastShownRef = useRef(0);

  useEffect(() => {
    document.documentElement.setAttribute('lang', language === 'el' ? 'el' : 'en');
  }, [language]);

  useEffect(() => {
    // Auth bootstrap runs in the background — the UI renders immediately and
    // protected routes redirect to /login if the session cannot be restored.
    const bootstrapAuth = async () => {
      try {
        await withTimeout(initializeSession(), AUTH_BOOTSTRAP_TIMEOUT_MS, 'Auth bootstrap');
      } catch (error) {
        console.warn('⚠️ App.tsx: auth bootstrap failed', error);
        if (error instanceof Error && error.message.includes('timed out')) {
          toastWarning(
            'Session restore timed out',
            'Continuing to login. You can sign in again if needed.',
            { duration: 5000 }
          );
        }
      }
    };

    void bootstrapAuth();
  }, [initializeSession, toastWarning]);

  useEffect(() => {
    const handleSessionExpired = () => {
      console.warn('🔒 Session expired event received, logging out');
      logout();
    };

    const handleRefreshWarning = (event: Event) => {
      const now = Date.now();
      if (now - refreshWarningLastShownRef.current < 8000) {
        return;
      }
      refreshWarningLastShownRef.current = now;

      const detail =
        event instanceof CustomEvent
          ? (event.detail as { reason?: string; status?: number | null } | undefined)
          : undefined;

      toastWarning(
        'Session refresh unavailable',
        detail?.status
          ? `Could not refresh session (status ${detail.status}). Retry in a moment.`
          : 'Could not refresh session right now. Please retry shortly.',
        { duration: 5000 }
      );
    };

    window.addEventListener('auth:session-expired', handleSessionExpired);
    window.addEventListener('auth:refresh-warning', handleRefreshWarning);
    return () => {
      window.removeEventListener('auth:session-expired', handleSessionExpired);
      window.removeEventListener('auth:refresh-warning', handleRefreshWarning);
    };
  }, [logout, toastWarning]);

  return (
    <ThemeProvider>
      <QueryProvider>
        <EnhancedErrorBoundary>
          <Router>
            <ToastContainer />
            <RegistrationDisabledLoginGate />
            <Suspense fallback={<AuthSkeleton />}>
              <ComingSoonGate>
                <Routes>
                  <Route
                    path="/"
                    element={
                      portal === 'client' ? <LandingPage /> : <Navigate to="/dashboard" replace />
                    }
                  />
                  <Route path="/services/:slug" element={<PublicServicePage />} />
                  <Route path="/pricing" element={<PricingPage />} />
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/register" element={<RegisterPage />} />
                  <Route path="/2fa-setup" element={<TwoFactorAuthPage />} />
                  <Route path="/force-password" element={<PasswordRotationRoute />} />
                  <Route
                    path="/unauthorized"
                    element={
                      <ProtectedRoute>
                        <UnauthorizedPage />
                      </ProtectedRoute>
                    }
                  />

                  {portalRoutes.map((route) => (
                    <Route
                      key={`${portal}:${route.path}`}
                      path={route.path}
                      element={
                        <ProtectedRoute allowedRoles={route.allowedRoles}>
                          {route.element}
                        </ProtectedRoute>
                      }
                    />
                  ))}

                  <Route path="*" element={<Navigate to="/unauthorized" replace />} />
                </Routes>
              </ComingSoonGate>
            </Suspense>
          </Router>
        </EnhancedErrorBoundary>
      </QueryProvider>
    </ThemeProvider>
  );
};
