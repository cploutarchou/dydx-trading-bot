/**
 * Main React App Entry Point
 * Enhanced with React Query, Error Boundaries, and Toast Notifications
 */

import React, { Suspense, lazy, useEffect } from 'react';
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import { QueryProvider } from './api/QueryProvider';
import { getUserWorkspaceRole, roleMatches, type WorkspaceRole } from './auth/roles';
import {
    ErrorBoundary as EnhancedErrorBoundary,
    ToastContainer,
    useToastStore,
} from './components/ErrorBoundary';
import { MainLayout } from './components/MainLayout';
import { RegistrationDisabledLoginGate } from './components/RegistrationDisabledLoginGate';
import { isCRMHost } from './pages/crm/paths';
import { isIBPortalHost } from './pages/ib/paths';
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
  import('./components/BacktestComparator').then((module) => ({ default: module.BacktestComparator }))
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
const CRMRouter = lazy(() => import('./pages/crm').then((module) => ({ default: module.CRMRouter })));
const CRMClientDetail = lazy(() =>
  import('./pages/crm/CRMClientDetail').then((module) => ({ default: module.CRMClientDetail }))
);
const CRMClients = lazy(() =>
  import('./pages/crm/CRMClients').then((module) => ({ default: module.CRMClients }))
);
const CRMCommissions = lazy(() =>
  import('./pages/crm/CRMCommissions').then((module) => ({ default: module.CRMCommissions }))
);
const CRMDashboard = lazy(() =>
  import('./pages/crm/CRMDashboard').then((module) => ({ default: module.CRMDashboard }))
);
const CRMHierarchy = lazy(() =>
  import('./pages/crm/CRMHierarchy').then((module) => ({ default: module.CRMHierarchy }))
);
const CRMLayout = lazy(() =>
  import('./pages/crm/CRMLayout').then((module) => ({ default: module.CRMLayout }))
);
const CRMPipeline = lazy(() =>
  import('./pages/crm/CRMPipeline').then((module) => ({ default: module.CRMPipeline }))
);
const CRMSecurity = lazy(() =>
  import('./pages/crm/CRMSecurity').then((module) => ({ default: module.CRMSecurity }))
);
const DashboardPage = lazy(() =>
  import('./pages/Dashboard').then((module) => ({ default: module.DashboardPage }))
);
const ForcePasswordChangePage = lazy(() =>
  import('./pages/ForcePasswordChange').then((module) => ({ default: module.ForcePasswordChangePage }))
);
const IBRouter = lazy(() => import('./pages/ib').then((module) => ({ default: module.IBRouter })));
const LandingPage = lazy(() =>
  import('./pages/Landing').then((module) => ({ default: module.LandingPage }))
);
const LoginPage = lazy(() =>
  import('./pages/Login').then((module) => ({ default: module.LoginPage }))
);
const NewsPage = lazy(() =>
  import('./pages/News').then((module) => ({ default: module.NewsPage }))
);
const PricingPage = lazy(() =>
  import('./pages/Pricing').then((module) => ({ default: module.PricingPage }))
);
const PublicServicePage = lazy(() =>
  import('./pages/PublicServicePage').then((module) => ({ default: module.PublicServicePage }))
);
const RegisterPage = lazy(() =>
  import('./pages/Register').then((module) => ({ default: module.RegisterPage }))
);
const SettingsPage = lazy(() => import('./pages/Settings'));
const TwoFactorAuthPage = lazy(() =>
  import('./pages/TwoFactorAuth').then((module) => ({ default: module.TwoFactorAuthPage }))
);

const ProtectedRoute: React.FC<{ children: React.ReactNode; allowedRoles?: WorkspaceRole[] }> = ({
  children,
  allowedRoles,
}) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const loading = useAuthStore((state) => state.loading);
  const user = useAuthStore((state) => state.user);

  // Auth bootstrap in flight — show skeleton rather than redirect prematurely
  if (!isAuthenticated && loading) {
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
    (allowedRoles?.some((role) => role === 'admin' || role === 'backoffice') ?? false);

  if (requiresPrivilegedMFA && user.privileged_mfa_required && !user.mfa_enabled) {
    return <Navigate to="/2fa-setup" replace />;
  }

  if (!roleMatches(getUserWorkspaceRole(user), allowedRoles)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <MainLayout>{children}</MainLayout>;
};

const PasswordRotationRoute: React.FC = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const loading = useAuthStore((state) => state.loading);
  const user = useAuthStore((state) => state.user);

  if (!isAuthenticated && loading) {
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
  const ibPortalHost = isIBPortalHost();
  const crmHost = isCRMHost();
  const logout = useAuthStore((state) => state.logout);
  const initializeSession = useAuthStore((state) => state.initializeSession);
  const toastWarning = useToastStore((state) => state.warning);
  const language = useUIPreferencesStore((state) => state.language);

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

    window.addEventListener('auth:session-expired', handleSessionExpired);
    return () => {
      window.removeEventListener('auth:session-expired', handleSessionExpired);
    };
  }, [logout]);

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
                  ibPortalHost || crmHost ? <Navigate to="/dashboard" replace /> : <LandingPage />
                }
              />
              <Route path="/services/:slug" element={<PublicServicePage />} />
              <Route path="/pricing" element={<PricingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/2fa-setup" element={<TwoFactorAuthPage />} />
              <Route path="/force-password" element={<PasswordRotationRoute />} />
              <Route
                path="/dashboard"
                element={
                  crmHost ? (
                    <ProtectedRoute allowedRoles={['admin', 'backoffice']}>
                      <CRMLayout>
                        <CRMDashboard />
                      </CRMLayout>
                    </ProtectedRoute>
                  ) : (
                    <ProtectedRoute>
                      <DashboardPage />
                    </ProtectedRoute>
                  )
                }
              />
              <Route
                path="/client-area"
                element={
                  <ProtectedRoute>
                    <ClientAreaPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/codex"
                element={
                  <ProtectedRoute>
                    <CodexPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/news"
                element={
                  <ProtectedRoute>
                    <NewsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/backtests"
                element={
                  <ProtectedRoute>
                    <BacktestsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/backtest/:runId"
                element={
                  <ProtectedRoute>
                    <BacktestDetailsV2 />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/crm/*"
                element={
                  <ProtectedRoute allowedRoles={['admin', 'backoffice']}>
                    <CRMRouter />
                  </ProtectedRoute>
                }
              />
              {crmHost && (
                <>
                  <Route
                    path="/clients"
                    element={
                      <ProtectedRoute allowedRoles={['admin', 'backoffice']}>
                        <CRMLayout>
                          <CRMClients />
                        </CRMLayout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/clients/:id"
                    element={
                      <ProtectedRoute allowedRoles={['admin', 'backoffice']}>
                        <CRMLayout>
                          <CRMClientDetail />
                        </CRMLayout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/pipeline"
                    element={
                      <ProtectedRoute allowedRoles={['admin', 'backoffice']}>
                        <CRMLayout>
                          <CRMPipeline />
                        </CRMLayout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/hierarchy"
                    element={
                      <ProtectedRoute allowedRoles={['admin', 'backoffice']}>
                        <CRMLayout>
                          <CRMHierarchy />
                        </CRMLayout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/commissions"
                    element={
                      <ProtectedRoute allowedRoles={['admin', 'backoffice']}>
                        <CRMLayout>
                          <CRMCommissions />
                        </CRMLayout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/security"
                    element={
                      <ProtectedRoute allowedRoles={['admin', 'backoffice']}>
                        <CRMLayout>
                          <CRMSecurity />
                        </CRMLayout>
                      </ProtectedRoute>
                    }
                  />
                </>
              )}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminHubPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <SettingsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/ib-portal/*"
                element={
                  <ProtectedRoute allowedRoles={['admin', 'backoffice', 'ib', 'sub_ib']}>
                    <IBRouter />
                  </ProtectedRoute>
                }
              />
              {ibPortalHost && (
                <Route
                  path="/*"
                  element={
                    <ProtectedRoute allowedRoles={['admin', 'backoffice', 'ib', 'sub_ib']}>
                      <IBRouter />
                    </ProtectedRoute>
                  }
                />
              )}
              <Route
                path="/strategies"
                element={
                  <ProtectedRoute>
                    <StrategyLibrary />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/strategies/new"
                element={
                  <ProtectedRoute>
                    <StrategyBuilder />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/strategies/manage"
                element={
                  <ProtectedRoute>
                    <StrategyManager />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/strategies/:id/edit"
                element={
                  <ProtectedRoute>
                    <StrategyBuilder />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/bots"
                element={
                  <ProtectedRoute>
                    <BotManager />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/backtests/compare"
                element={
                  <ProtectedRoute>
                    <BacktestComparator />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </Router>
      </EnhancedErrorBoundary>
    </QueryProvider>
  );
};
