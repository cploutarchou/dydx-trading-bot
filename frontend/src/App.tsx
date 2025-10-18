/**
 * Main React App Entry Point
 */

import React, { useEffect, useState } from 'react';
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import { BacktestDetailsPage } from './pages/BacktestDetails';
import { DashboardPage } from './pages/Dashboard';
import { LoginPage } from './pages/Login';
import { useAuthStore } from './store/auth';

interface ErrorBoundaryState {
    hasError: boolean;
    error?: Error;
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, ErrorBoundaryState> {
    constructor(props: { children: React.ReactNode }) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        console.error('❌ ErrorBoundary caught:', error);
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('Error details:', errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white p-4">
                    <h1 className="text-2xl font-bold mb-4">⚠️ Application Error</h1>
                    <p className="text-red-400 mb-4">{this.state.error?.message}</p>
                    <p className="text-gray-400 text-sm">Check browser console (F12) for details</p>
                </div>
            );
        }

        return this.props.children;
    }
}

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
    const user = useAuthStore((state) => state.user);

    if (!isAuthenticated && !user) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
};

export const App: React.FC = () => {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        console.log('🔧 App.tsx: Component mounted, setting mounted=true');
        setMounted(true);
    }, []);

    if (!mounted) {
        return <div className="min-h-screen bg-slate-900 flex items-center justify-center"><p className="text-white">Loading...</p></div>;
    }

    console.log('🔧 App.tsx: Rendering router');
    return (
        <ErrorBoundary>
            <Router>
                <Routes>
                    <Route path="/login" element={<LoginPage />} />
                    <Route
                        path="/dashboard"
                        element={
                            <ProtectedRoute>
                                <DashboardPage />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/backtest/:runId"
                        element={
                            <ProtectedRoute>
                                <BacktestDetailsPage />
                            </ProtectedRoute>
                        }
                    />
                    <Route path="/" element={<Navigate to="/login" replace />} />
                    {/* Catch-all: redirect unknown routes to login */}
                    <Route path="*" element={<Navigate to="/login" replace />} />
                </Routes>
            </Router>
        </ErrorBoundary>
    );
};
