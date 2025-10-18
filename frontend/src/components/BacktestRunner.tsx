import { Play } from 'lucide-react';
import React, { useState } from 'react';
import api from '../api';

interface BacktestRunRequest {
    start_date: string;
    end_date: string;
    num_pairs?: number;
    zscore_threshold?: number;
    stats_window?: number;
    usd_per_trade?: number;
}

export const BacktestRunner: React.FC<{ onBacktestComplete?: () => void }> = ({ onBacktestComplete }) => {
    const [formData, setFormData] = useState<BacktestRunRequest>({
        start_date: '2024-01-01',
        end_date: '2024-03-31',
        num_pairs: 10,
        zscore_threshold: 1.5,
        stats_window: 21,
        usd_per_trade: 10,
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: name === 'num_pairs' || name === 'stats_window' 
                ? parseInt(value)
                : name === 'zscore_threshold' || name === 'usd_per_trade'
                ? parseFloat(value)
                : value
        }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        setSuccess(false);

        try {
            console.log('📊 BacktestRunner: Starting backtest with:', formData);
            const response = await api.runBacktest(formData);
            console.log('📊 BacktestRunner: Backtest started:', response);
            setSuccess(true);
            setFormData({
                start_date: '2024-01-01',
                end_date: '2024-03-31',
                num_pairs: 10,
                zscore_threshold: 1.5,
                stats_window: 21,
                usd_per_trade: 10,
            });
            
            if (onBacktestComplete) {
                setTimeout(() => onBacktestComplete(), 1000);
            }
        } catch (err: any) {
            console.error('❌ BacktestRunner: Error:', err);
            setError(err.response?.data?.message || err.message || 'Failed to start backtest');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-xl font-bold text-white mb-6">Start New Backtest</h3>
            
            {error && (
                <div className="mb-4 p-4 bg-red-900 border border-red-700 rounded text-red-200">
                    {error}
                </div>
            )}

            {success && (
                <div className="mb-4 p-4 bg-green-900 border border-green-700 rounded text-green-200">
                    ✅ Backtest started successfully! Check the results below.
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                            Start Date
                        </label>
                        <input
                            type="date"
                            name="start_date"
                            value={formData.start_date}
                            onChange={handleChange}
                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                            End Date
                        </label>
                        <input
                            type="date"
                            name="end_date"
                            value={formData.end_date}
                            onChange={handleChange}
                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                            Number of Pairs
                        </label>
                        <input
                            type="number"
                            name="num_pairs"
                            value={formData.num_pairs}
                            onChange={handleChange}
                            min="1"
                            max="50"
                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                            Z-Score Threshold
                        </label>
                        <input
                            type="number"
                            name="zscore_threshold"
                            value={formData.zscore_threshold}
                            onChange={handleChange}
                            step="0.1"
                            min="0.5"
                            max="3"
                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                            Stats Window (days)
                        </label>
                        <input
                            type="number"
                            name="stats_window"
                            value={formData.stats_window}
                            onChange={handleChange}
                            min="5"
                            max="60"
                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                            USD Per Trade
                        </label>
                        <input
                            type="number"
                            name="usd_per_trade"
                            value={formData.usd_per_trade}
                            onChange={handleChange}
                            step="1"
                            min="1"
                            max="1000"
                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                        />
                    </div>
                </div>

                <button
                    type="submit"
                    disabled={loading}
                    className="w-full mt-6 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg font-medium flex items-center justify-center gap-2"
                >
                    <Play className="w-4 h-4" />
                    {loading ? 'Running Backtest...' : 'Start Backtest'}
                </button>
            </form>
        </div>
    );
};
