/**
 * Main React App Entry Point
 */

import React from 'react';
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import { BacktestDetailsPage } from './pages/BacktestDetails';
import { LoginPage } from './pages/Login';
import { useAuthStore } from './store/auth';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated());

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
};

export const App: React.FC = () => {
    return (
        <Router>
            <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route
                    path="/backtest/:runId"
                    element={
                        <ProtectedRoute>
                            <BacktestDetailsPage />
                        </ProtectedRoute>
                    }
                />
                <Route path="/" element={<Navigate to="/login" replace />} />
            </Routes>
        </Router>
    );
};
