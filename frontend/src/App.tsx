/**
 * Main React App Entry Point
 * Enhanced with React Query, Error Boundaries, and Toast Notifications
 */

import React, { useEffect, useState } from 'react';
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import { QueryProvider } from './api/QueryProvider';
import { BacktestComparator } from './components/BacktestComparator';
import BotManager from './components/BotManager';
import { ErrorBoundary as EnhancedErrorBoundary, ToastContainer } from './components/ErrorBoundary';
import { useToastStore } from './components/ErrorBoundary';
import { MainLayout } from './components/MainLayout';
import StrategyBuilder from './components/StrategyBuilder';
import StrategyLibrary from './components/StrategyLibrary';
import StrategyManager from './components/StrategyManager';
import BacktestDetailsV2 from './pages/BacktestDetailsV2';
import { BacktestsPage } from './pages/Backtests';
import { DashboardPage } from './pages/Dashboard';
import { LoginPage } from './pages/Login';
import { RegisterPage } from './pages/Register';
import SettingsPage from './pages/Settings';
import { TwoFactorAuthPage } from './pages/TwoFactorAuth';
import { useAuthStore } from './store/auth';

// Legacy error boundary removed - using enhanced version from components/ErrorBoundary

const AUTH_BOOTSTRAP_TIMEOUT_MS = 12000;

const withTimeout = async <T,>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> => {
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

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const user = useAuthStore((state) => state.user);

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  return <MainLayout>{children}</MainLayout>;
};

export const App: React.FC = () => {
  const [mounted, setMounted] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const [authBootstrapTimedOut, setAuthBootstrapTimedOut] = useState(false);
  const logout = useAuthStore((state) => state.logout);
  const initializeSession = useAuthStore((state) => state.initializeSession);
  const toastWarning = useToastStore((state) => state.warning);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const bootstrapAuth = async () => {
      try {
        setAuthBootstrapTimedOut(false);
        await withTimeout(initializeSession(), AUTH_BOOTSTRAP_TIMEOUT_MS, 'Auth bootstrap');
      } catch (error) {
        console.warn('⚠️ App.tsx: auth bootstrap failed', error);
        if (error instanceof Error && error.message.includes('timed out')) {
          setAuthBootstrapTimedOut(true);
          toastWarning(
            'Session restore timed out',
            'Continuing to login. You can sign in again if needed.',
            { duration: 5000 }
          );
        }
      } finally {
        if (!cancelled) {
          setAuthReady(true);
        }
      }
    };

    void bootstrapAuth();

    return () => { cancelled = true; };
  }, [initializeSession]);

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

  if (!mounted || !authReady) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center space-y-3 px-4">
          <p className="text-white">Restoring session...</p>
          {authBootstrapTimedOut && (
            <button
              type="button"
              onClick={() => {
                logout();
                setAuthReady(true);
              }}
              className="px-4 py-2 rounded-md bg-slate-700 hover:bg-slate-600 text-slate-100 text-sm"
            >
              Continue to Login
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <QueryProvider>
      <EnhancedErrorBoundary>
        <Router>
          <ToastContainer />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/2fa-setup" element={<TwoFactorAuthPage />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
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
              path="/settings"
              element={
                <ProtectedRoute>
                  <SettingsPage />
                </ProtectedRoute>
              }
            />
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
            <Route path="/" element={<Navigate to="/login" replace />} />
            {/* Catch-all: redirect unknown routes to login */}
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </Router>
      </EnhancedErrorBoundary>
    </QueryProvider>
  );
};
