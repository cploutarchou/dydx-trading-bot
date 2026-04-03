import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { PageContainer } from './PageContainer';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (isRecord(error) && isRecord(error.response) && isRecord(error.response.data)) {
    const data = error.response.data as Record<string, unknown>;
    if (typeof data.message === 'string' && data.message.length > 0) return data.message;
    if (typeof data.detail === 'string' && data.detail.length > 0) return data.detail;
  }

  if (error instanceof Error) return error.message;
  return fallback;
};

const getErrorStatus = (error: unknown): number | null => {
  if (!isRecord(error) || !isRecord(error.response)) return null;
  const status = error.response.status;
  return typeof status === 'number' ? status : null;
};

const extractRunId = (response: unknown): string | null => {
  if (!isRecord(response)) return null;
  if (typeof response.run_id === 'string') return response.run_id;

  const nested = response.data;
  if (isRecord(nested) && typeof nested.run_id === 'string') return nested.run_id;
  return null;
};

interface Strategy {
  id: number;
  name: string;
  category: string;
  description: string;
  zscore_threshold: number;
  stats_window: number;
  max_half_life: number;
  usd_per_trade: number;
  usd_min_collateral: number;
  close_at_zscore_cross: boolean;
  find_cointegrated_pairs: boolean;
  manage_exits: boolean;
  place_trades: boolean;
  abort_all_positions: boolean;
  max_positions: number;
  max_drawdown_pct: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  trailing_stop_pct: number;
  rebalance_interval_hours: number;
  position_timeout_hours: number;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export default function StrategyLibrary() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(0);
  const [totalStrategies, setTotalStrategies] = useState(0);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [runModalOpen, setRunModalOpen] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null);
  const [backtestStartDate, setBacktestStartDate] = useState('');
  const [backtestEndDate, setBacktestEndDate] = useState('');
  const [runLoading, setRunLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const ITEMS_PER_PAGE = 10;

  // Load strategies on mount and when page changes
  useEffect(() => {
    loadStrategies();
  }, [currentPage]);

  const loadStrategies = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.listStrategies(currentPage * ITEMS_PER_PAGE, ITEMS_PER_PAGE);
      if (response.data) {
        setStrategies((response.data.strategies || []) as Strategy[]);
        setTotalStrategies(response.data.total || 0);
      }
    } catch (err: unknown) {
      console.error('Failed to load strategies:', err);
      setError('Failed to load strategies');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (strategyId: number) => {
    try {
      await api.deleteStrategy(strategyId);
      setStrategies(strategies.filter((s) => s.id !== strategyId));
      setDeleteConfirmId(null);
    } catch (err: unknown) {
      console.error('Failed to delete strategy:', err);
      setError('Failed to delete strategy');
    }
  };

  const handleDuplicate = async (strategy: Strategy) => {
    try {
      const { id: _id, created_at: _created_at, updated_at: _updated_at, ...newStrategy } =
        strategy;
      const duplicatedStrategy = {
        ...newStrategy,
        name: `${strategy.name} (Copy)`,
      };

      const response = await api.createStrategy(duplicatedStrategy);
      if (response.data) {
        setStrategies([...strategies, response.data as Strategy]);
      }
    } catch (err: unknown) {
      console.error('Failed to duplicate strategy:', err);
      setError('Failed to duplicate strategy');
    }
  };

  const handleRunStrategy = (strategy: Strategy) => {
    setSelectedStrategy(strategy);
    setRunModalOpen(true);
    setRunError(null);
    // Set default dates: last 30 days
    const endDate = new Date();
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - 30);
    setBacktestStartDate(startDate.toISOString().split('T')[0]);
    setBacktestEndDate(endDate.toISOString().split('T')[0]);
  };

  const buildRunPayload = () => {
    if (!selectedStrategy || !backtestStartDate || !backtestEndDate) return null;
    return {
      start_date: backtestStartDate,
      end_date: backtestEndDate,
      strategy_id: selectedStrategy.id,
    };
  };

  const handleExecuteBacktest = async () => {
    if (!selectedStrategy || !backtestStartDate || !backtestEndDate) {
      setRunError('Please enter valid start and end dates');
      return;
    }

    try {
      setRunLoading(true);
      setRunError(null);

      // Ensure token is loaded from localStorage before making request
      api.ensureTokenLoaded();

      // Check if token exists
      const token = localStorage.getItem('access_token');

      if (!token) {
        console.error('❌ No auth token found - user needs to login');
        setRunError('Authentication required. Please login again.');
        return;
      }

      const runPayload = buildRunPayload();
      if (!runPayload) {
        setRunError('Unable to build backtest payload. Please check dates and strategy.');
        return;
      }

      // Call API to run backtest using strategy_id
      const response = await api.runBacktest(runPayload);

      // Handle both wrapped (ApiResponse.data.run_id) and direct (response.run_id) formats
      const runId = extractRunId(response);
      if (runId) {
        navigate(`/backtest/${runId}`);
        setRunModalOpen(false);
        setSelectedStrategy(null);
      } else {
        setRunError('Backtest started but no run ID returned');
      }
    } catch (err: unknown) {
      console.error('❌ Failed to run backtest:', {
        status: isRecord(err) && isRecord(err.response) ? err.response.status : undefined,
        statusText: isRecord(err) && isRecord(err.response) ? err.response.statusText : undefined,
        message: getErrorMessage(err, 'Failed to run backtest'),
        data: isRecord(err) && isRecord(err.response) ? err.response.data : undefined,
      });

      // Handle specific error cases
      const status = getErrorStatus(err);
      if (status === 401) {
        setRunError('Your session has expired. Please login again.');
      } else if (status === 403) {
        setRunError('You do not have permission to run this backtest.');
      } else if (status === 404) {
        setRunError('Strategy not found. It may have been deleted.');
      } else {
        setRunError(getErrorMessage(err, 'Failed to run backtest'));
      }
    } finally {
      setRunLoading(false);
    }
  };

  const filteredStrategies = strategies.filter(
    (s) =>
      s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const totalPages = Math.ceil(totalStrategies / ITEMS_PER_PAGE);

  if (loading && strategies.length === 0) {
    return (
      <PageContainer size="wide" className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-white">Loading strategies...</p>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer size="wide">
        {/* Header */}
        <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Trading Strategies</h1>
            <p className="text-gray-400">Manage your custom trading strategies</p>
          </div>
          <div className="flex flex-wrap gap-2 justify-end">
            <button
              onClick={() => navigate('/strategies/manage')}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition"
            >
              ⚙️ Runtime Manager
            </button>
            <button
              onClick={() => navigate('/bots')}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg transition"
            >
              🤖 Bot Manager
            </button>
            <button
              onClick={() => navigate('/strategies/new')}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition flex items-center gap-2"
            >
              ✨ New Strategy
            </button>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500 rounded-lg">
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {/* Search Bar */}
        <div className="mb-6">
          <input
            type="text"
            placeholder="Search strategies by name or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Strategies Grid */}
        {filteredStrategies.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-400 mb-4">
              {strategies.length === 0
                ? 'No strategies yet. Create one to get started!'
                : 'No strategies match your search.'}
            </p>
            {strategies.length === 0 && (
              <button
                onClick={() => navigate('/strategies/new')}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition"
              >
                Create First Strategy
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {filteredStrategies.map((strategy) => (
              <div
                key={strategy.id}
                className="bg-slate-800 border border-slate-700 rounded-lg p-6 hover:border-slate-600 transition"
              >
                <div className="flex justify-between items-start mb-3">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-white mb-1">{strategy.name}</h3>
                    <p className="text-gray-400 text-sm mb-2">{strategy.description}</p>
                    <div className="flex gap-3 flex-wrap">
                      <span className="inline-block px-2 py-1 bg-slate-700 rounded text-xs text-gray-300">
                        Category: {strategy.category}
                      </span>
                      {strategy.is_public && (
                        <span className="inline-block px-2 py-1 bg-blue-500/20 rounded text-xs text-blue-300">
                          🌐 Public
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Parameters */}
                <div className="grid grid-cols-3 gap-4 my-4 py-4 border-t border-slate-700">
                  <div>
                    <p className="text-xs text-gray-500">Z-Score Threshold</p>
                    <p className="text-lg font-semibold text-blue-400">
                      {strategy.zscore_threshold}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Stats Window (h)</p>
                    <p className="text-lg font-semibold text-blue-400">{strategy.stats_window}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Max Half-Life (h)</p>
                    <p className="text-lg font-semibold text-blue-400">{strategy.max_half_life}</p>
                  </div>
                </div>

                {/* Metadata */}
                <div className="text-xs text-gray-500 mb-4">
                  Updated: {new Date(strategy.updated_at).toLocaleDateString()} at{' '}
                  {new Date(strategy.updated_at).toLocaleTimeString()}
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleRunStrategy(strategy)}
                    className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded transition"
                  >
                    ▶️ Run Backtest
                  </button>
                  <button
                    onClick={() => navigate(`/strategies/${strategy.id}/edit`)}
                    className="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium rounded transition"
                  >
                    ✏️ Edit
                  </button>
                  <button
                    onClick={() => handleDuplicate(strategy)}
                    className="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium rounded transition"
                  >
                    📋 Duplicate
                  </button>
                  {deleteConfirmId === strategy.id ? (
                    <>
                      <button
                        onClick={() => handleDelete(strategy.id)}
                        className="flex-1 px-3 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded transition"
                      >
                        Confirm Delete
                      </button>
                      <button
                        onClick={() => setDeleteConfirmId(null)}
                        className="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium rounded transition"
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => setDeleteConfirmId(strategy.id)}
                      className="flex-1 px-3 py-2 bg-slate-700 hover:bg-red-600/30 text-white text-sm font-medium rounded transition"
                    >
                      🗑️ Delete
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-8 flex justify-center gap-2">
            <button
              onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
              disabled={currentPage === 0}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700/50 text-white rounded transition"
            >
              ← Previous
            </button>
            <div className="flex items-center gap-2">
              {Array.from({ length: totalPages }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentPage(i)}
                  className={`px-3 py-2 rounded transition ${
                    currentPage === i
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-700 hover:bg-slate-600 text-gray-300'
                  }`}
                >
                  {i + 1}
                </button>
              ))}
            </div>
            <button
              onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
              disabled={currentPage === totalPages - 1}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700/50 text-white rounded transition"
            >
              Next →
            </button>
          </div>
        )}

        {/* Run Backtest Modal */}
        {runModalOpen && selectedStrategy && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 max-w-md w-full">
              <h2 className="text-xl font-bold text-white mb-4">
                Run Backtest: {selectedStrategy.name}
              </h2>

              {/* Strategy Preview */}
              <div className="bg-slate-700/50 rounded p-4 mb-4">
                <p className="text-sm text-gray-400 mb-2">Strategy Parameters:</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="text-gray-300">
                    Z-Score:{' '}
                    <span className="text-blue-400">{selectedStrategy.zscore_threshold}</span>
                  </div>
                  <div className="text-gray-300">
                    Stats Window:{' '}
                    <span className="text-blue-400">{selectedStrategy.stats_window}h</span>
                  </div>
                  <div className="text-gray-300">
                    Max Positions:{' '}
                    <span className="text-blue-400">{selectedStrategy.max_positions}</span>
                  </div>
                  <div className="text-gray-300">
                    USD/Trade:{' '}
                    <span className="text-blue-400">${selectedStrategy.usd_per_trade}</span>
                  </div>
                  <div className="text-gray-300">
                    Max Drawdown:{' '}
                    <span className="text-blue-400">{selectedStrategy.max_drawdown_pct}%</span>
                  </div>
                  <div className="text-gray-300">
                    Stop Loss:{' '}
                    <span className="text-blue-400">{selectedStrategy.stop_loss_pct}%</span>
                  </div>
                </div>
              </div>

              {/* Error Alert */}
              {runError && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500 rounded text-sm text-red-400">
                  {runError}
                </div>
              )}

              {/* Date Inputs */}
              <div className="space-y-3 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">Start Date</label>
                  <input
                    type="date"
                    value={backtestStartDate}
                    onChange={(e) => setBacktestStartDate(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">End Date</label>
                  <input
                    type="date"
                    value={backtestEndDate}
                    onChange={(e) => setBacktestEndDate(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              {/* Request Preview */}
              <div className="mb-4 p-3 bg-slate-900/70 border border-slate-600 rounded">
                <p className="text-xs text-slate-300 mb-2">Request payload preview</p>
                <pre className="text-[11px] text-slate-400 whitespace-pre-wrap break-all">
                  {JSON.stringify(buildRunPayload(), null, 2)}
                </pre>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={handleExecuteBacktest}
                  disabled={runLoading}
                  className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-600/50 text-white font-medium rounded transition"
                >
                  {runLoading ? 'Running...' : '▶️ Run Backtest'}
                </button>
                <button
                  onClick={() => {
                    setRunModalOpen(false);
                    setSelectedStrategy(null);
                    setRunError(null);
                  }}
                  disabled={runLoading}
                  className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700/50 text-white font-medium rounded transition"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
    </PageContainer>
  );
}
