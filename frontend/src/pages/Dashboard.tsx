import React, { useState } from 'react';
import { BacktestList } from '../components/BacktestList';
import { BacktestRunner } from '../components/BacktestRunner';
import { useAuthStore } from '../store/auth';

export const DashboardPage: React.FC = () => {
    const { user } = useAuthStore();
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    const handleBacktestComplete = () => {
        setRefreshTrigger(prev => prev + 1);
    };

    return (
        <div className="min-h-screen bg-linear-to-br from-slate-900 to-slate-800">
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
