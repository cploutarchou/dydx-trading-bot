import { Play } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import api from '../api';
import { useStrategyStore } from '../store/strategies';

interface TradingParameters {
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
  resolution?: string;
}

interface BacktestRunRequest {
  start_date: string;
  end_date: string;
  name?: string;
  description?: string;
  initial_balance?: number;
  max_pairs?: number;
  pairs?: string[];
  strategy_id?: number;
  trading_parameters: TradingParameters;
}

export const BacktestRunner: React.FC<{ onBacktestComplete?: () => void }> = ({
  onBacktestComplete,
}) => {
  const { strategies, fetchStrategies } = useStrategyStore();
  const [useStrategy, setUseStrategy] = useState(false);
  const [selectedStrategyId, setSelectedStrategyId] = useState<number | null>(null);
  const [formData, setFormData] = useState<BacktestRunRequest>({
    start_date: '2024-01-01',
    end_date: '2024-03-31',
    name: 'ui-backtest',
    max_pairs: 10,
    trading_parameters: {
      zscore_threshold: 1.5,
      stats_window: 21,
      usd_per_trade: 10,
    },
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

  const TRADING_PARAM_FIELDS = new Set([
    'zscore_threshold',
    'stats_window',
    'max_half_life',
    'usd_per_trade',
    'usd_min_collateral',
    'close_at_zscore_cross',
    'find_cointegrated_pairs',
    'manage_exits',
    'place_trades',
    'abort_all_positions',
    'max_positions',
    'max_drawdown_pct',
    'stop_loss_pct',
    'take_profit_pct',
    'trailing_stop_pct',
    'rebalance_interval_hours',
    'position_timeout_hours',
    'resolution',
  ]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    if (TRADING_PARAM_FIELDS.has(name)) {
      setFormData((prev) => ({
        ...prev,
        trading_parameters: {
          ...prev.trading_parameters,
          [name]:
            name === 'stats_window' ||
            name === 'max_positions' ||
            name === 'rebalance_interval_hours' ||
            name === 'position_timeout_hours'
              ? parseInt(value)
              : name === 'zscore_threshold' ||
                  name === 'usd_per_trade' ||
                  name === 'max_half_life' ||
                  name === 'usd_min_collateral' ||
                  name === 'max_drawdown_pct' ||
                  name === 'stop_loss_pct' ||
                  name === 'take_profit_pct' ||
                  name === 'trailing_stop_pct'
                ? parseFloat(value)
                : value,
        },
      }));
    } else {
      setFormData((prev) => ({
        ...prev,
        [name]: name === 'max_pairs' ? parseInt(value) : value,
      }));
    }
  };

  const handleStrategyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value ? parseInt(e.target.value) : null;
    setSelectedStrategyId(id);

    if (id && useStrategy) {
      const strategy = strategies.find((s) => s.id === id);
      if (strategy) {
        setFormData((prev) => ({
          ...prev,
          strategy_id: id,
          trading_parameters: {
            ...prev.trading_parameters,
            resolution: strategy.resolution,
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
          },
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
      const tp = formData.trading_parameters;
      const cleanedData = {
        start_date: formData.start_date,
        end_date: formData.end_date,
        name: formData.name || 'ui-backtest',
        max_pairs: Number(formData.max_pairs),
        trading_parameters: {
          ...(tp.zscore_threshold !== undefined && {
            zscore_threshold: Number(tp.zscore_threshold),
          }),
          ...(tp.stats_window !== undefined && { stats_window: Number(tp.stats_window) }),
          ...(tp.max_half_life !== undefined && { max_half_life: Number(tp.max_half_life) }),
          ...(tp.usd_per_trade !== undefined && { usd_per_trade: Number(tp.usd_per_trade) }),
          ...(tp.usd_min_collateral !== undefined && {
            usd_min_collateral: Number(tp.usd_min_collateral),
          }),
          ...(tp.close_at_zscore_cross !== undefined && {
            close_at_zscore_cross: tp.close_at_zscore_cross,
          }),
          ...(tp.find_cointegrated_pairs !== undefined && {
            find_cointegrated_pairs: tp.find_cointegrated_pairs,
          }),
          ...(tp.manage_exits !== undefined && { manage_exits: tp.manage_exits }),
          ...(tp.place_trades !== undefined && { place_trades: tp.place_trades }),
          ...(tp.abort_all_positions !== undefined && {
            abort_all_positions: tp.abort_all_positions,
          }),
          ...(tp.max_positions !== undefined && { max_positions: Number(tp.max_positions) }),
          ...(tp.max_drawdown_pct !== undefined && {
            max_drawdown_pct: Number(tp.max_drawdown_pct),
          }),
          ...(tp.stop_loss_pct !== undefined && { stop_loss_pct: Number(tp.stop_loss_pct) }),
          ...(tp.take_profit_pct !== undefined && { take_profit_pct: Number(tp.take_profit_pct) }),
          ...(tp.trailing_stop_pct !== undefined && {
            trailing_stop_pct: Number(tp.trailing_stop_pct),
          }),
          ...(tp.rebalance_interval_hours !== undefined && {
            rebalance_interval_hours: Number(tp.rebalance_interval_hours),
          }),
          ...(tp.position_timeout_hours !== undefined && {
            position_timeout_hours: Number(tp.position_timeout_hours),
          }),
          ...(tp.resolution !== undefined && { resolution: tp.resolution }),
        },
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
        // All strategy parameters from nested trading_parameters
        zscore_threshold: Number(formData.trading_parameters.zscore_threshold || 1.5),
        stats_window: Number(formData.trading_parameters.stats_window || 21),
        max_half_life: Number(formData.trading_parameters.max_half_life || 24),
        usd_per_trade: Number(formData.trading_parameters.usd_per_trade || 10.0),
        usd_min_collateral: Number(formData.trading_parameters.usd_min_collateral || 100.0),
        close_at_zscore_cross: formData.trading_parameters.close_at_zscore_cross !== false,
        find_cointegrated_pairs: formData.trading_parameters.find_cointegrated_pairs !== false,
        manage_exits: formData.trading_parameters.manage_exits !== false,
        place_trades: formData.trading_parameters.place_trades !== false,
        abort_all_positions: formData.trading_parameters.abort_all_positions || false,
        max_positions: Number(formData.trading_parameters.max_positions || 5),
        max_drawdown_pct: Number(formData.trading_parameters.max_drawdown_pct || 15.0),
        stop_loss_pct: Number(formData.trading_parameters.stop_loss_pct || 2.0),
        take_profit_pct: Number(formData.trading_parameters.take_profit_pct || 5.0),
        trailing_stop_pct: Number(formData.trading_parameters.trailing_stop_pct || 1.0),
        rebalance_interval_hours: Number(
          formData.trading_parameters.rebalance_interval_hours || 24
        ),
        position_timeout_hours: Number(formData.trading_parameters.position_timeout_hours || 72),
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

              {selectedStrategyId && strategies.find((s) => s.id === selectedStrategyId) && (
                <div className="mt-3 p-3 bg-blue-900/30 border border-blue-700 rounded-lg">
                  <h4 className="text-sm font-semibold text-blue-300 mb-2">Strategy Settings:</h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs text-gray-300">
                    {(() => {
                      const s = strategies.find((st) => st.id === selectedStrategyId);
                      if (!s) return null;
                      return (
                        <>
                          <div>
                            Z-Score:{' '}
                            <span className="text-blue-300 font-semibold">
                              {s.zscore_threshold}
                            </span>
                          </div>
                          <div>
                            Stats Window:{' '}
                            <span className="text-blue-300 font-semibold">{s.stats_window}h</span>
                          </div>
                          <div>
                            Half-Life:{' '}
                            <span className="text-blue-300 font-semibold">{s.max_half_life}h</span>
                          </div>
                          <div>
                            USD/Trade:{' '}
                            <span className="text-blue-300 font-semibold">${s.usd_per_trade}</span>
                          </div>
                          <div>
                            Max Positions:{' '}
                            <span className="text-blue-300 font-semibold">{s.max_positions}</span>
                          </div>
                          <div>
                            Max Drawdown:{' '}
                            <span className="text-blue-300 font-semibold">
                              {s.max_drawdown_pct}%
                            </span>
                          </div>
                          <div>
                            Stop Loss:{' '}
                            <span className="text-blue-300 font-semibold">{s.stop_loss_pct}%</span>
                          </div>
                          <div>
                            Take Profit:{' '}
                            <span className="text-blue-300 font-semibold">
                              {s.take_profit_pct}%
                            </span>
                          </div>
                          <div>
                            Trailing Stop:{' '}
                            <span className="text-blue-300 font-semibold">
                              {s.trailing_stop_pct}%
                            </span>
                          </div>
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
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Number of Pairs
                </label>
                <input
                  type="number"
                  name="max_pairs"
                  value={formData.max_pairs}
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
                  value={formData.trading_parameters.zscore_threshold}
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
                  value={formData.trading_parameters.stats_window}
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
                  value={formData.trading_parameters.usd_per_trade}
                  onChange={handleChange}
                  step="1"
                  min="1"
                  max="1000"
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                />
              </div>
            </>
          )}
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

      {showSaveDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-lg p-6 max-w-md w-full mx-4 border border-slate-700">
            <h4 className="text-lg font-bold text-white mb-4">Save Results as Strategy?</h4>
            <input
              type="text"
              placeholder="Strategy name"
              value={strategyName}
              onChange={(e) => setStrategyName(e.target.value)}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white mb-4"
            />
            <div className="flex gap-2">
              <button
                onClick={() => setShowSaveDialog(false)}
                className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded"
              >
                Skip
              </button>
              <button
                onClick={handleSaveAsStrategy}
                className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
