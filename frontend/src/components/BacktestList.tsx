import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';

interface BacktestRun {
    id?: string;
    run_id: string;
    start_date?: string;
    end_date?: string;
    status: string;
    total_trades: number;
    profitable_trades?: number;
    losing_trades?: number;
    total_pnl: number;
    sharpe_ratio?: number;
    win_rate: number;
    profit_factor?: number;
    max_drawdown?: number;
    created_at: string;
}

export const BacktestList: React.FC<{ refreshTrigger?: number }> = ({ refreshTrigger = 0 }) => {
    const navigate = useNavigate();
    const [runs, setRuns] = useState<BacktestRun[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadBacktests();
    }, [refreshTrigger]);

    const loadBacktests = async () => {
        setLoading(true);
        setError(null);
        try {
            console.log('📊 BacktestList: Loading backtests...');
            const response = await api.listBacktests(0, 50);
            console.log('📊 BacktestList: API Response:', JSON.stringify(response, null, 2));
            
            // Handle the response - backend returns data.backtests array
            // The api.ts already extracts response.data, so we need to handle response.data.backtests
            const backtestsArray = response.data?.backtests || [];
            console.log('📊 BacktestList: Found backtests array, length:', backtestsArray.length);
            
            if (!Array.isArray(backtestsArray)) {
                console.error('❌ BacktestList: backtests is not an array!', backtestsArray);
                setError('Invalid response format from server');
                setRuns([]);
            } else {
                console.log('📊 BacktestList: Setting runs with', backtestsArray.length, 'items');
                setRuns(backtestsArray);
            }
        } catch (err: any) {
            console.error('❌ BacktestList: Error loading backtests:', err);
            setError(err.message || 'Failed to load backtests');
            setRuns([]);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
                <h3 className="text-xl font-bold text-white mb-4">Backtest Runs</h3>
                <p className="text-gray-400">Loading...</p>
            </div>
        );
    }

    return (
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h3 className="text-xl font-bold text-white mb-4">Backtest Runs ({runs.length})</h3>

            {error && (
                <div className="mb-4 p-4 bg-red-900 border border-red-700 rounded text-red-200">
                    {error}
                </div>
            )}

            {runs.length === 0 ? (
                <p className="text-gray-400">No backtest runs yet. Start a new analysis above.</p>
            ) : (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-gray-300">
                        <thead className="border-b border-slate-700">
                            <tr>
                                <th className="px-4 py-2 text-left">Run ID</th>
                                <th className="px-4 py-2 text-left">Start Time</th>
                                <th className="px-4 py-2 text-left">Period</th>
                                <th className="px-4 py-2 text-center">Trades</th>
                                <th className="px-4 py-2 text-right">P&L</th>
                                <th className="px-4 py-2 text-right">Win Rate</th>
                                <th className="px-4 py-2 text-right">Sharpe</th>
                                <th className="px-4 py-2 text-right">Max DD</th>
                                <th className="px-4 py-2 text-center">Status</th>
                                <th className="px-4 py-2 text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {Array.isArray(runs) && runs.map(run => (
                                <tr key={run.run_id} className="border-b border-slate-700 hover:bg-slate-700">
                                    <td className="px-4 py-2 font-mono text-xs text-blue-400">
                                        {run.run_id.substring(0, 8)}...
                                    </td>
                                    <td className="px-4 py-2 text-sm">
                                        {new Date(run.created_at).toLocaleString()}
                                    </td>
                                    <td className="px-4 py-2">
                                        {run.start_date && run.end_date ? (
                                            <>
                                                {new Date(run.start_date).toLocaleDateString()} - {new Date(run.end_date).toLocaleDateString()}
                                            </>
                                        ) : (
                                            '-'
                                        )}
                                    </td>
                                    <td className="px-4 py-2 text-center">{run.total_trades}</td>
                                    <td className={`px-4 py-2 text-right font-semibold ${run.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        ${run.total_pnl.toFixed(2)}
                                    </td>
                                    <td className="px-4 py-2 text-right">{run.win_rate !== null && run.win_rate !== undefined ? `${run.win_rate.toFixed(1)}%` : 'N/A'}</td>
                                    <td className="px-4 py-2 text-right">{run.sharpe_ratio ? run.sharpe_ratio.toFixed(2) : 'N/A'}</td>
                                    <td className="px-4 py-2 text-right">{run.max_drawdown ? run.max_drawdown.toFixed(1) : 'N/A'}%</td>
                                    <td className="px-4 py-2 text-center">
                                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                                            run.status === 'completed' ? 'bg-green-900 text-green-300' :
                                            run.status === 'running' ? 'bg-blue-900 text-blue-300' :
                                            'bg-yellow-900 text-yellow-300'
                                        }`}>
                                            {run.status}
                                        </span>
                                    </td>
                                    <td className="px-4 py-2 text-center">
                                        <button
                                            onClick={() => navigate(`/backtest/${run.run_id}`)}
                                            className="text-blue-400 hover:text-blue-300 underline font-semibold"
                                        >
                                            View Details
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};
