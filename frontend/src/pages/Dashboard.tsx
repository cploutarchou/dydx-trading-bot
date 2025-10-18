import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BacktestList } from '../components/BacktestList';
import { BacktestRunner } from '../components/BacktestRunner';
import { useAuthStore } from '../store/auth';

export const DashboardPage: React.FC = () => {
    const navigate = useNavigate();
    const { user, logout } = useAuthStore();
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const handleBacktestComplete = () => {
        setRefreshTrigger(prev => prev + 1);
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
            {/* Header */}
            <div className="bg-slate-800 border-b border-slate-700">
                <div className="max-w-7xl mx-auto px-4 py-6 flex justify-between items-center">
                    <h1 className="text-3xl font-bold text-white">dYdX Backtest Dashboard</h1>
                    <button
                        onClick={handleLogout}
                        className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg font-medium"
                    >
                        Logout
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <div className="max-w-7xl mx-auto px-4 py-8">
                <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
                    <h2 className="text-2xl font-bold text-white mb-4">Welcome!</h2>
                    <p className="text-gray-300 mb-4">
                        Logged in as: <span className="font-semibold text-blue-400">{user?.username}</span>
                    </p>
                    <p className="text-gray-400">
                        Email: <span className="font-semibold">{user?.email}</span>
                    </p>
                </div>

            {/* Placeholder for backtest results */}
            <div className="mt-8 grid grid-cols-1 gap-6">
                <BacktestRunner onBacktestComplete={handleBacktestComplete} />
                <BacktestList refreshTrigger={refreshTrigger} />
            </div>
            </div>
        </div>
    );
};
