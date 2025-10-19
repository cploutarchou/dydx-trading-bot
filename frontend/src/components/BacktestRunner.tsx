import { Play } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import api from '../api';
import { useStrategyStore } from '../store/strategies';

interface BacktestRunRequest {
    start_date: string;
    end_date: string;
    num_pairs?: number;
    zscore_threshold?: number;
    stats_window?: number;
    max_half_life?: number;
    usd_per_trade?: number;
    usd_min_collateral?: number;
    close_at_zscore_cross?: boolean;
    find_cointegrated_pairs?: boolean;
    manage_exits?: boolean;
    place_trades?: boolean;
    abort_all_positions?: boolean;
    max_positions?: number;
    max_drawdown_pct?: number;
    stop_loss_pct?: number;
    take_profit_pct?: number;
    trailing_stop_pct?: number;
    rebalance_interval_hours?: number;
    position_timeout_hours?: number;
    strategy_id?: number;
}

export const BacktestRunner: React.FC<{ onBacktestComplete?: () => void }> = ({ onBacktestComplete }) => {
    const { strategies, fetchStrategies } = useStrategyStore();
    const [useStrategy, setUseStrategy] = useState(false);
    const [selectedStrategyId, setSelectedStrategyId] = useState<number | null>(null);
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
    const [showSaveDialog, setShowSaveDialog] = useState(false);
    const [strategyName, setStrategyName] = useState('');

    // Fetch strategies on mount
    useEffect(() => {
        fetchStrategies();
    }, [fetchStrategies]);

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

    const handleStrategyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const id = e.target.value ? parseInt(e.target.value) : null;
        setSelectedStrategyId(id);
        
        if (id && useStrategy) {
            const strategy = strategies.find(s => s.id === id);
            if (strategy) {
                setFormData(prev => ({
                    ...prev,
                    // All 21 strategy parameters
                    zscore_threshold: strategy.zscore_threshold,
                    stats_window: strategy.stats_window,
                    max_half_life: strategy.max_half_life,
                    usd_per_trade: strategy.usd_per_trade,
                    usd_min_collateral: strategy.usd_min_collateral,
                    close_at_zscore_cross: strategy.close_at_zscore_cross,
                    find_cointegrated_pairs: strategy.find_cointegrated_pairs,
                    manage_exits: strategy.manage_exits,
                    place_trades: strategy.place_trades,
                    abort_all_positions: strategy.abort_all_positions,
                    max_positions: strategy.max_positions,
                    max_drawdown_pct: strategy.max_drawdown_pct,
                    stop_loss_pct: strategy.stop_loss_pct,
                    take_profit_pct: strategy.take_profit_pct,
                    trailing_stop_pct: strategy.trailing_stop_pct,
                    rebalance_interval_hours: strategy.rebalance_interval_hours,
                    position_timeout_hours: strategy.position_timeout_hours,
                    strategy_id: id,
                }));
            }
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        setSuccess(false);

        try {
            // Convert all numeric fields to proper types
            const cleanedData = {
                start_date: formData.start_date,
                end_date: formData.end_date,
                num_pairs: Number(formData.num_pairs),
                zscore_threshold: Number(formData.zscore_threshold),
                stats_window: Number(formData.stats_window),
                max_half_life: Number(formData.max_half_life),
                usd_per_trade: Number(formData.usd_per_trade),
                usd_min_collateral: Number(formData.usd_min_collateral),
                close_at_zscore_cross: formData.close_at_zscore_cross,
                find_cointegrated_pairs: formData.find_cointegrated_pairs,
                manage_exits: formData.manage_exits,
                place_trades: formData.place_trades,
                abort_all_positions: formData.abort_all_positions,
                max_positions: Number(formData.max_positions),
                max_drawdown_pct: Number(formData.max_drawdown_pct),
                stop_loss_pct: Number(formData.stop_loss_pct),
                take_profit_pct: Number(formData.take_profit_pct),
                trailing_stop_pct: Number(formData.trailing_stop_pct),
                rebalance_interval_hours: Number(formData.rebalance_interval_hours),
                position_timeout_hours: Number(formData.position_timeout_hours),
                ...(useStrategy && selectedStrategyId && { strategy_id: selectedStrategyId }),
            };
            console.log('📊 BacktestRunner: Starting backtest with:', cleanedData);
            const response = await api.runBacktest(cleanedData);
            console.log('📊 BacktestRunner: Backtest started:', response);
            setSuccess(true);
            setShowSaveDialog(true);
            
            if (onBacktestComplete) {
                setTimeout(() => onBacktestComplete(), 1000);
            }
        } catch (err: any) {
            console.error('❌ BacktestRunner: Error:', err);
            console.log('📊 BacktestRunner: Payload:', formData);
            console.log('📊 BacktestRunner: Response error:', err.response?.data);
            setError(err.response?.data?.message || err.message || 'Failed to start backtest');
        } finally {
            setLoading(false);
        }
    };

    const handleSaveAsStrategy = async () => {
        if (!strategyName.trim()) {
            setError('Strategy name is required');
            return;
        }

        try {
            await useStrategyStore.getState().createStrategy({
                name: strategyName,
                category: 'pairs_trading',
                description: `Backtest results from ${formData.start_date} to ${formData.end_date}`,
                is_public: false,
                // All 21 strategy parameters - with explicit numeric conversion
                zscore_threshold: Number(formData.zscore_threshold || 1.5),
                stats_window: Number(formData.stats_window || 21),
                max_half_life: Number(formData.max_half_life || 24),
                usd_per_trade: Number(formData.usd_per_trade || 10.0),
                usd_min_collateral: Number(formData.usd_min_collateral || 100.0),
                close_at_zscore_cross: formData.close_at_zscore_cross !== false,
                find_cointegrated_pairs: formData.find_cointegrated_pairs !== false,
                manage_exits: formData.manage_exits !== false,
                place_trades: formData.place_trades !== false,
                abort_all_positions: formData.abort_all_positions || false,
                max_positions: Number(formData.max_positions || 5),
                max_drawdown_pct: Number(formData.max_drawdown_pct || 15.0),
                stop_loss_pct: Number(formData.stop_loss_pct || 2.0),
                take_profit_pct: Number(formData.take_profit_pct || 5.0),
                trailing_stop_pct: Number(formData.trailing_stop_pct || 1.0),
                rebalance_interval_hours: Number(formData.rebalance_interval_hours || 24),
                position_timeout_hours: Number(formData.position_timeout_hours || 72),
            });
            setShowSaveDialog(false);
            setStrategyName('');
            await fetchStrategies();
        } catch (err: any) {
            setError('Failed to save strategy');
            console.error(err);
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
                <div className="border-b border-slate-700 pb-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={useStrategy}
                            onChange={(e) => {
                                setUseStrategy(e.target.checked);
                                if (!e.target.checked) {
                                    setSelectedStrategyId(null);
                                }
                            }}
                            className="w-4 h-4"
                        />
                        <span className="text-sm font-medium text-gray-300">Use Saved Strategy</span>
                    </label>
                    
                    {useStrategy && (
                        <>
                            <select
                                value={selectedStrategyId || ''}
                                onChange={handleStrategyChange}
                                className="w-full mt-2 px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                            >
                                <option value="">Select a strategy...</option>
                                {strategies.map((strategy) => (
                                    <option key={strategy.id} value={strategy.id}>
                                        {strategy.name} (Z-score: {strategy.zscore_threshold})
                                    </option>
                                ))}
                            </select>

                            {selectedStrategyId && strategies.find(s => s.id === selectedStrategyId) && (
                                <div className="mt-3 p-3 bg-blue-900/30 border border-blue-700 rounded-lg">
                                    <h4 className="text-sm font-semibold text-blue-300 mb-2">Strategy Settings:</h4>
                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs text-gray-300">
                                        {(() => {
                                            const s = strategies.find(st => st.id === selectedStrategyId);
                                            if (!s) return null;
                                            return (
                                                <>
                                                    <div>Z-Score: <span className="text-blue-300 font-semibold">{s.zscore_threshold}</span></div>
                                                    <div>Stats Window: <span className="text-blue-300 font-semibold">{s.stats_window}h</span></div>
                                                    <div>Half-Life: <span className="text-blue-300 font-semibold">{s.max_half_life}h</span></div>
                                                    <div>USD/Trade: <span className="text-blue-300 font-semibold">${s.usd_per_trade}</span></div>
                                                    <div>Max Positions: <span className="text-blue-300 font-semibold">{s.max_positions}</span></div>
                                                    <div>Max Drawdown: <span className="text-blue-300 font-semibold">{s.max_drawdown_pct}%</span></div>
                                                    <div>Stop Loss: <span className="text-blue-300 font-semibold">{s.stop_loss_pct}%</span></div>
                                                    <div>Take Profit: <span className="text-blue-300 font-semibold">{s.take_profit_pct}%</span></div>
                                                    <div>Trailing Stop: <span className="text-blue-300 font-semibold">{s.trailing_stop_pct}%</span></div>
                                                </>
                                            );
                                        })()}
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">Start Date</label>
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
                        <label className="block text-sm font-medium text-gray-300 mb-2">End Date</label>
                        <input
                            type="date"
                            name="end_date"
                            value={formData.end_date}
                            onChange={handleChange}
                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                            required
                        />
                    </div>

                    {!useStrategy && (
                        <>
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">Number of Pairs</label>
                                <input type="number" name="num_pairs" value={formData.num_pairs} onChange={handleChange} min="1" max="50" className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">Z-Score Threshold</label>
                                <input type="number" name="zscore_threshold" value={formData.zscore_threshold} onChange={handleChange} step="0.1" min="0.5" max="3" className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">Stats Window (days)</label>
                                <input type="number" name="stats_window" value={formData.stats_window} onChange={handleChange} min="5" max="60" className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">USD Per Trade</label>
                                <input type="number" name="usd_per_trade" value={formData.usd_per_trade} onChange={handleChange} step="1" min="1" max="1000" className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white" />
                            </div>
                        </>
                    )}
                </div>

                <button type="submit" disabled={loading} className="w-full mt-6 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg font-medium flex items-center justify-center gap-2">
                    <Play className="w-4 h-4" />
                    {loading ? 'Running Backtest...' : 'Start Backtest'}
                </button>
            </form>

            {showSaveDialog && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-slate-800 rounded-lg p-6 max-w-md w-full mx-4 border border-slate-700">
                        <h4 className="text-lg font-bold text-white mb-4">Save Results as Strategy?</h4>
                        <input type="text" placeholder="Strategy name" value={strategyName} onChange={(e) => setStrategyName(e.target.value)} className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white mb-4" />
                        <div className="flex gap-2">
                            <button onClick={() => setShowSaveDialog(false)} className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded">Skip</button>
                            <button onClick={handleSaveAsStrategy} className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded">Save</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
