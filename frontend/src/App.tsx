/**
 * Main React App Entry Point
 * Enhanced with React Query, Error Boundaries, and Toast Notifications
 */

import React, { Suspense, lazy, useEffect, useRef } from 'react';
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import { QueryProvider } from './api/QueryProvider';
import { getCurrentPortalType } from './app/portal';
import {
    BACKOFFICE_ROLES,
    CLIENT_ROLES,
    IB_ROLES,
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

const BacktestComparator = lazy(() =>
  import('./components/BacktestComparator').then((module) => ({
    default: module.BacktestComparator,
  }))
);
const BotManager = lazy(() => import('./components/BotManager'));
const StrategyBuilder = lazy(() => import('./components/StrategyBuilder'));
const StrategyLibrary = lazy(() => import('./components/StrategyLibrary'));
const StrategyManager = lazy(() => import('./components/StrategyManager'));
const AdminHubPage = lazy(() =>
  import('./pages/AdminHub').then((module) => ({ default: module.AdminHubPage }))
);
const BacktestDetailsV2 = lazy(() => import('./pages/BacktestDetailsV2'));
const BacktestsPage = lazy(() =>
  import('./pages/Backtests').then((module) => ({ default: module.BacktestsPage }))
);
const ClientAreaPage = lazy(() =>
  import('./pages/ClientArea').then((module) => ({ default: module.ClientAreaPage }))
);
const CodexPage = lazy(() =>
  import('./pages/Codex').then((module) => ({ default: module.CodexPage }))
);
const CRMRouter = lazy(() =>
  import('./pages/crm/index').then((module) => ({ default: module.CRMRouter }))
);
const DashboardPage = lazy(() =>
  import('./pages/Dashboard').then((module) => ({ default: module.DashboardPage }))
);
const ClientProfilePage = lazy(() =>
  import('./pages/client/ClientAccountPages').then((module) => ({
    default: module.ClientProfilePage,
  }))
);
const ClientSecurityPage = lazy(() =>
  import('./pages/client/ClientAccountPages').then((module) => ({
    default: module.ClientSecurityPage,
  }))
);
const ForcePasswordChangePage = lazy(() =>
  import('./pages/ForcePasswordChange').then((module) => ({
    default: module.ForcePasswordChangePage,
  }))
);
const IBRouter = lazy(() => import('./pages/ib').then((module) => ({ default: module.IBRouter })));
const NewsPage = lazy(() =>
  import('./pages/News').then((module) => ({ default: module.NewsPage }))
);
const SettingsPage = lazy(() => import('./pages/Settings'));
const TwoFactorAuthPage = lazy(() =>
  import('./pages/TwoFactorAuth').then((module) => ({ default: module.TwoFactorAuthPage }))
);
const UnauthorizedPage = lazy(() =>
  import('./pages/Unauthorized').then((module) => ({ default: module.UnauthorizedPage }))
);

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

export const App: React.FC = () => {
  const portal = getCurrentPortalType();
  const logout = useAuthStore((state) => state.logout);
  const initializeSession = useAuthStore((state) => state.initializeSession);
  const toastWarning = useToastStore((state) => state.warning);
  const language = useUIPreferencesStore((state) => state.language);
  const refreshWarningLastShownRef = useRef(0);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
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
    <QueryProvider>
      <EnhancedErrorBoundary>
        <Router>
          <ToastContainer />
          <RegistrationDisabledLoginGate />
          <Suspense fallback={<AuthSkeleton />}>
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

              {portal === 'client' && (
                <>
                  <Route
                    path="/dashboard"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <DashboardPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/client-area"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <ClientAreaPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/codex"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <CodexPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/news"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <NewsPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/backtests"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <BacktestsPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/backtest/:runId"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <BacktestDetailsV2 />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/backtests/compare"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <BacktestComparator />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/strategies"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <StrategyLibrary />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/strategies/new"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <StrategyBuilder />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/strategies/manage"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <StrategyManager />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/strategies/:id/edit"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <StrategyBuilder />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/bots"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <BotManager />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/profile"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <Navigate to="/settings?section=profile" replace />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/security"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <Navigate to="/settings?section=security" replace />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/wallet"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <Navigate to="/settings?section=dydx_keys" replace />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/settings"
                    element={
                      <ProtectedRoute allowedRoles={CLIENT_ROLES}>
                        <SettingsPage />
                      </ProtectedRoute>
                    }
                  />
                </>
              )}

              {portal === 'backoffice' && (
                <>
                  <Route
                    path="/dashboard"
                    element={
                      <ProtectedRoute allowedRoles={BACKOFFICE_ROLES}>
                        <AdminHubPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/admin"
                    element={
                      <ProtectedRoute allowedRoles={BACKOFFICE_ROLES}>
                        <AdminHubPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/crm/*"
                    element={
                      <ProtectedRoute allowedRoles={BACKOFFICE_ROLES}>
                        <CRMRouter />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/ib-portal/*"
                    element={
                      <ProtectedRoute allowedRoles={BACKOFFICE_ROLES}>
                        <IBRouter />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/settings"
                    element={
                      <ProtectedRoute allowedRoles={BACKOFFICE_ROLES}>
                        <SettingsPage />
                      </ProtectedRoute>
                    }
                  />
                </>
              )}

              {portal === 'ib' && (
                <>
                  <Route
                    path="/profile"
                    element={
                      <ProtectedRoute allowedRoles={[...IB_ROLES, ...BACKOFFICE_ROLES]}>
                        <ClientProfilePage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/security"
                    element={
                      <ProtectedRoute allowedRoles={[...IB_ROLES, ...BACKOFFICE_ROLES]}>
                        <ClientSecurityPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/*"
                    element={
                      <ProtectedRoute allowedRoles={[...IB_ROLES, ...BACKOFFICE_ROLES]}>
                        <IBRouter />
                      </ProtectedRoute>
                    }
                  />
                </>
              )}

              <Route path="*" element={<Navigate to="/unauthorized" replace />} />
            </Routes>
          </Suspense>
        </Router>
      </EnhancedErrorBoundary>
    </QueryProvider>
  );
};
