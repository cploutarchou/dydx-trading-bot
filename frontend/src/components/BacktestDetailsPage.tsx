import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';

interface StrategyConfig {
  zscore_threshold: number;
  stats_window: number;
  max_half_life: number;
  usd_per_trade: number;
  usd_min_collateral: number;
  close_at_zscore_cross: boolean;
  max_positions: number;
  max_drawdown_pct: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  [key: string]: any;
}

interface BacktestData {
  run_id: string;
  status: string;
  total_trades: number;
  profitable_trades: number;
  total_pnl: number;
  total_pnl_usd: number;
  win_rate: number;
  sharpe_ratio: number;
  max_drawdown: number;
  profit_factor: number;
  starting_balance: number;
  ending_balance: number;
  strategy_snapshot?: StrategyConfig;
  strategy_id?: number;
  results: any[];
  all_trades: any[];
}

interface StrategyVersion {
  id: number;
  version_number: number;
  name: string;
  description: string;
  config: StrategyConfig;
  changed_fields: string[];
  change_reason: string;
  created_at: string;
  created_by_user_id: number;
}

export const BacktestDetailsPage: React.FC = () => {
  const { run_id } = useParams<{ run_id: string }>();
  const navigate = useNavigate();
  
  const [backtest, setBacktest] = useState<BacktestData | null>(null);
  const [strategyVersions, setStrategyVersions] = useState<StrategyVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateStrategyModal, setShowCreateStrategyModal] = useState(false);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [newStrategyName, setNewStrategyName] = useState('');
  const [newStrategyDesc, setNewStrategyDesc] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadBacktestDetails();
  }, [run_id]);

  const loadBacktestDetails = async () => {
    setLoading(true);
    setError(null);
    try {
      if (!run_id) {
        setError('No backtest ID provided');
        return;
      }

      const response = await api.getBacktest(run_id);
      console.log('Backtest details API response:', response);
      
      // api.getBacktest returns the ApiResponse wrapper, actual data is in response.data
      const backtestData = response?.data || response;
      console.log('Extracted backtest data:', backtestData);
      console.log('Strategy snapshot:', backtestData?.strategy_snapshot);
      
      if (backtestData) {
        setBacktest(backtestData);
        
        // If backtest has strategy_id, load version history
        if (backtestData.strategy_id) {
          loadStrategyVersions(backtestData.strategy_id);
        }
      } else {
        setError('Failed to load backtest details');
      }
    } catch (err: any) {
      console.error('Error loading backtest:', err);
      setError(err.message || 'Failed to load backtest');
    } finally {
      setLoading(false);
    }
  };

  const loadStrategyVersions = async (strategyId: number) => {
    try {
      const response = await api.getStrategyVersionHistory(strategyId);
      if (response.data?.versions) {
        setStrategyVersions(response.data.versions);
      }
    } catch (err) {
      console.error('Error loading strategy versions:', err);
    }
  };

  const handleCreateStrategy = async () => {
    if (!newStrategyName.trim() || !backtest?.strategy_snapshot) {
      alert('Please enter a strategy name');
      return;
    }

    setCreating(true);
    try {
      const response = await api.createStrategyFromBacktest({
        name: newStrategyName,
        description: newStrategyDesc,
        config: backtest.strategy_snapshot,
        backtest_run_id: backtest.run_id,
      });

      if (response.success) {
        alert('Strategy created successfully!');
        setShowCreateStrategyModal(false);
        setNewStrategyName('');
        setNewStrategyDesc('');
        // Navigate to strategy manager
        navigate('/strategies');
      } else {
        alert('Failed to create strategy');
      }
    } catch (err: any) {
      alert(`Error creating strategy: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-slate-900 min-h-screen p-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-center text-gray-400">Loading backtest details...</div>
        </div>
      </div>
    );
  }

  if (error || !backtest) {
    return (
      <div className="bg-slate-900 min-h-screen p-8">
        <div className="max-w-6xl mx-auto">
          <div className="bg-red-900 border border-red-700 rounded p-4 text-red-200">
            {error || 'Backtest not found'}
          </div>
          <button
            onClick={() => navigate('/backtests')}
            className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded"
          >
            Back to Backtests
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 min-h-screen p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/backtests')}
            className="text-blue-400 hover:text-blue-300 mb-4"
          >
            ← Back to Backtests
          </button>
          <h1 className="text-3xl font-bold text-white mb-2">Backtest Details</h1>
          <p className="text-gray-400">Run ID: {backtest.run_id}</p>
        </div>

        {/* Main Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-slate-800 border border-slate-700 rounded p-4">
            <p className="text-gray-400 text-sm">Total P&L</p>
            <p className={`text-2xl font-bold ${backtest.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${backtest.total_pnl.toFixed(2)}
            </p>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded p-4">
            <p className="text-gray-400 text-sm">Win Rate</p>
            <p className="text-2xl font-bold text-blue-400">
              {backtest.win_rate.toFixed(1)}%
            </p>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded p-4">
            <p className="text-gray-400 text-sm">Sharpe Ratio</p>
            <p className="text-2xl font-bold text-purple-400">
              {backtest.sharpe_ratio ? backtest.sharpe_ratio.toFixed(2) : 'N/A'}
            </p>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded p-4">
            <p className="text-gray-400 text-sm">Total Trades</p>
            <p className="text-2xl font-bold text-yellow-400">{backtest.total_trades}</p>
          </div>
        </div>

        {/* Debug Section */}
        <div className="bg-slate-900 border border-slate-600 rounded p-4 mb-8 text-xs">
          <p className="text-gray-400 mb-2">🔍 DEBUG:</p>
          <p className="text-gray-500">Has strategy_snapshot: {backtest.strategy_snapshot ? '✅ YES' : '❌ NO'}</p>
          <p className="text-gray-500">strategy_id: {backtest.strategy_id || 'null'}</p>
          {backtest.strategy_snapshot && (
            <p className="text-green-400 mt-2">strategy_snapshot keys: {Object.keys(backtest.strategy_snapshot).join(', ')}</p>
          )}
        </div>

        {/* Strategy Config Section */}
        {backtest.strategy_snapshot && (
          <div className="bg-slate-800 border border-slate-700 rounded p-6 mb-8">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-white">Strategy Configuration</h2>
              <div className="space-x-2">
                <button
                  onClick={() => setShowVersionHistory(!showVersionHistory)}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded text-sm"
                >
                  📜 Version History ({strategyVersions.length})
                </button>
                <button
                  onClick={() => setShowCreateStrategyModal(true)}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded text-sm font-semibold"
                >
                  ✨ Create Strategy from This
                </button>
              </div>
            </div>

            {/* Strategy Config Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="bg-slate-700 rounded p-3">
                <p className="text-gray-400 text-xs">Z-Score Threshold</p>
                <p className="text-white font-semibold">{backtest.strategy_snapshot.zscore_threshold}</p>
              </div>
              <div className="bg-slate-700 rounded p-3">
                <p className="text-gray-400 text-xs">Stats Window</p>
                <p className="text-white font-semibold">{backtest.strategy_snapshot.stats_window}</p>
              </div>
              <div className="bg-slate-700 rounded p-3">
                <p className="text-gray-400 text-xs">Max Half-Life</p>
                <p className="text-white font-semibold">{backtest.strategy_snapshot.max_half_life}h</p>
              </div>
              <div className="bg-slate-700 rounded p-3">
                <p className="text-gray-400 text-xs">USD per Trade</p>
                <p className="text-white font-semibold">${backtest.strategy_snapshot.usd_per_trade}</p>
              </div>
              <div className="bg-slate-700 rounded p-3">
                <p className="text-gray-400 text-xs">Min Collateral</p>
                <p className="text-white font-semibold">${backtest.strategy_snapshot.usd_min_collateral}</p>
              </div>
              <div className="bg-slate-700 rounded p-3">
                <p className="text-gray-400 text-xs">Close at Z-Score Cross</p>
                <p className="text-white font-semibold">{backtest.strategy_snapshot.close_at_zscore_cross ? '✓' : '✗'}</p>
              </div>
              <div className="bg-slate-700 rounded p-3">
                <p className="text-gray-400 text-xs">Max Positions</p>
                <p className="text-white font-semibold">{backtest.strategy_snapshot.max_positions || 'N/A'}</p>
              </div>
              <div className="bg-slate-700 rounded p-3">
                <p className="text-gray-400 text-xs">Max Drawdown %</p>
                <p className="text-white font-semibold">{backtest.strategy_snapshot.max_drawdown_pct || 'N/A'}%</p>
              </div>
              <div className="bg-slate-700 rounded p-3">
                <p className="text-gray-400 text-xs">Stop Loss %</p>
                <p className="text-white font-semibold">{backtest.strategy_snapshot.stop_loss_pct || 'N/A'}%</p>
              </div>
            </div>
          </div>
        )}

        {/* Version History Section */}
        {showVersionHistory && strategyVersions.length > 0 && (
          <div className="bg-slate-800 border border-slate-700 rounded p-6 mb-8">
            <h2 className="text-xl font-bold text-white mb-4">Strategy Version History</h2>
            <div className="space-y-3">
              {strategyVersions.map((version) => (
                <div key={version.id} className="bg-slate-700 rounded p-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-white font-semibold">Version {version.version_number}</p>
                      <p className="text-gray-400 text-sm">{version.name}</p>
                      <p className="text-gray-500 text-xs mt-1">{version.description}</p>
                      {version.changed_fields.length > 0 && (
                        <p className="text-yellow-400 text-xs mt-2">
                          Changed: {version.changed_fields.join(', ')}
                        </p>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-gray-400 text-sm">
                        {new Date(version.created_at).toLocaleString()}
                      </p>
                      <button
                        onClick={() => console.log('Revert to version', version.id)}
                        className="mt-2 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs"
                      >
                        Revert
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Create Strategy Modal */}
        {showCreateStrategyModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 max-w-2xl w-full mx-4 my-8">
              <h2 className="text-xl font-bold text-white mb-4">Create Strategy from Backtest</h2>
              
              {/* Strategy Parameters Preview */}
              {backtest?.strategy_snapshot && (
                <div className="mb-6 bg-slate-700 border border-slate-600 rounded p-4">
                  <h3 className="text-sm font-semibold text-gray-300 mb-3">Strategy Configuration</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                    <div>
                      <p className="text-gray-500">Z-Score Threshold</p>
                      <p className="text-white font-semibold">{backtest.strategy_snapshot.zscore_threshold}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Stats Window</p>
                      <p className="text-white font-semibold">{backtest.strategy_snapshot.stats_window}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Max Half Life</p>
                      <p className="text-white font-semibold">{backtest.strategy_snapshot.max_half_life}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">USD Per Trade</p>
                      <p className="text-white font-semibold">${backtest.strategy_snapshot.usd_per_trade}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Max Positions</p>
                      <p className="text-white font-semibold">{backtest.strategy_snapshot.max_positions}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Max Drawdown %</p>
                      <p className="text-white font-semibold">{backtest.strategy_snapshot.max_drawdown_pct}%</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Stop Loss %</p>
                      <p className="text-white font-semibold">{backtest.strategy_snapshot.stop_loss_pct}%</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Take Profit %</p>
                      <p className="text-white font-semibold">{backtest.strategy_snapshot.take_profit_pct}%</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Close at Z-Score Cross</p>
                      <p className="text-white font-semibold">{backtest.strategy_snapshot.close_at_zscore_cross ? 'Yes' : 'No'}</p>
                    </div>
                  </div>
                </div>
              )}
              
              <div className="mb-4">
                <label className="block text-gray-400 text-sm mb-2">Strategy Name *</label>
                <input
                  type="text"
                  value={newStrategyName}
                  onChange={(e) => setNewStrategyName(e.target.value)}
                  placeholder="e.g., High Sharpe BTC-ETH"
                  className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="mb-6">
                <label className="block text-gray-400 text-sm mb-2">Description</label>
                <textarea
                  value={newStrategyDesc}
                  onChange={(e) => setNewStrategyDesc(e.target.value)}
                  placeholder="Describe this strategy..."
                  rows={3}
                  className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex space-x-3">
                <button
                  onClick={() => setShowCreateStrategyModal(false)}
                  disabled={creating}
                  className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateStrategy}
                  disabled={creating}
                  className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded font-semibold disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create Strategy'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Trade Results Section */}
        {backtest.results && backtest.results.length > 0 && (
          <div className="bg-slate-800 border border-slate-700 rounded p-6">
            <h2 className="text-xl font-bold text-white mb-4">Trading Results by Pair</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-gray-300">
                <thead className="border-b border-slate-700">
                  <tr>
                    <th className="px-4 py-2 text-left">Pair</th>
                    <th className="px-4 py-2 text-center">Trades</th>
                    <th className="px-4 py-2 text-right">P&L</th>
                    <th className="px-4 py-2 text-right">Win Rate</th>
                    <th className="px-4 py-2 text-right">Sharpe</th>
                  </tr>
                </thead>
                <tbody>
                  {backtest.results.map((result, idx) => (
                    <tr key={idx} className="border-b border-slate-700">
                      <td className="px-4 py-2">{result.market_1} / {result.market_2}</td>
                      <td className="px-4 py-2 text-center">{result.total_trades}</td>
                      <td className={`px-4 py-2 text-right font-semibold ${result.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        ${result.pnl.toFixed(2)}
                      </td>
                      <td className="px-4 py-2 text-right">{result.win_rate.toFixed(1)}%</td>
                      <td className="px-4 py-2 text-right">{result.sharpe_ratio ? result.sharpe_ratio.toFixed(2) : 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
