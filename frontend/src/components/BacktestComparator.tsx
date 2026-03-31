import { Download, Trash2 } from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import api from '../api';

interface BacktestResult {
  run_id: string;
  total_return_pct: number;
  total_pnl: number;
  sharpe_ratio: number;
  win_rate: number;
  max_drawdown: number;
  num_trades: number;
  avg_trade_duration: number;
  start_date: string;
  end_date: string;
  created_at?: string;
  status?: string;
  is_from_cache?: boolean; // Indicates if result is from cached backtest
  cache_age_days?: number; // Number of days since cached result was created
}

const toNumber = (value: unknown, fallback = 0): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const getErrorMessage = (error: unknown, fallback: string): string =>
  error instanceof Error ? error.message : fallback;

const normalizeRun = (raw: unknown): BacktestResult => {
  const normalized = toRecord(raw);
  const totalPnl = toNumber(normalized.total_pnl, 0);
  const initialBalance = 1000;

  return {
    run_id: String(normalized.run_id || ''),
    total_return_pct:
      normalized.total_return_pct !== undefined
        ? toNumber(normalized.total_return_pct, 0)
        : (totalPnl / initialBalance) * 100,
    total_pnl: totalPnl,
    sharpe_ratio: toNumber(normalized.sharpe_ratio, 0),
    win_rate: toNumber(normalized.win_rate, 0),
    max_drawdown:
      normalized.max_drawdown !== undefined
        ? toNumber(normalized.max_drawdown, 0)
        : toNumber(normalized.max_drawdown_pct, 0),
    num_trades:
      normalized.num_trades !== undefined
        ? toNumber(normalized.num_trades, 0)
        : toNumber(normalized.total_trades, 0),
    avg_trade_duration: toNumber(normalized.avg_trade_duration, 0),
    start_date: String(normalized.start_date || ''),
    end_date: String(normalized.end_date || ''),
    created_at:
      typeof normalized.created_at === 'string' ? normalized.created_at : undefined,
    status: typeof normalized.status === 'string' ? normalized.status : undefined,
    is_from_cache: Boolean(normalized.is_from_cache),
    cache_age_days:
      normalized.cache_age_days !== undefined ? toNumber(normalized.cache_age_days, 0) : undefined,
  };
};

interface SelectedBacktest {
  run_id: string;
  data: BacktestResult;
}

const ITEMS_PER_PAGE = 10;

export const BacktestComparator: React.FC = () => {
  const [backtests, setBacktests] = useState<BacktestResult[]>([]);
  const [selectedBacktests, setSelectedBacktests] = useState<SelectedBacktest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  // Fetch available backtests
  useEffect(() => {
    const fetchBacktests = async () => {
      setLoading(true);
      try {
        const response = await api.listBacktests(0, 500);
        const raw = toRecord(response);
        const rawData = toRecord(raw.data);
        const data = Array.isArray(raw?.backtests)
          ? raw.backtests
          : Array.isArray(rawData.backtests)
            ? rawData.backtests
            : Array.isArray(rawData.runs)
              ? rawData.runs
              : Array.isArray(raw?.runs)
                ? raw.runs
                : [];

        const normalized = data.map((entry) => normalizeRun(entry));
        // Sort by most recent first
        const sorted = [...normalized].sort((a, b) => {
          if (!a.created_at || !b.created_at) return 0;
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });
        setBacktests(sorted);
      } catch (err: unknown) {
        setError(getErrorMessage(err, 'Failed to load backtests'));
        console.error('❌ BacktestComparator: Failed to load backtests:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchBacktests();
  }, []);

  // Pagination logic
  const paginatedBacktests = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return backtests.slice(start, start + ITEMS_PER_PAGE);
  }, [backtests, currentPage]);

  const totalPages = Math.ceil(backtests.length / ITEMS_PER_PAGE);

  // Toggle backtest selection
  const toggleBacktest = (backtest: BacktestResult) => {
    setSelectedBacktests((prev) => {
      const existing = prev.find((b) => b.run_id === backtest.run_id);
      if (existing) {
        return prev.filter((b) => b.run_id !== backtest.run_id);
      } else if (prev.length < 5) {
        return [...prev, { run_id: backtest.run_id, data: backtest }];
      }
      return prev;
    });
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  // Remove selected backtest
  const removeSelected = (run_id: string) => {
    setSelectedBacktests((prev) => prev.filter((b) => b.run_id !== run_id));
  };

  // Calculate delta between first and other backtests
  const getDelta = (metric: keyof BacktestResult, index: number) => {
    if (index === 0 || selectedBacktests.length === 0) return null;
    const baseline = selectedBacktests[0].data[metric] as number;
    const current = selectedBacktests[index].data[metric] as number;
    const delta = current - baseline;
    const deltaPercent = (delta / Math.abs(baseline)) * 100;
    return { delta, deltaPercent };
  };

  // Export to CSV
  const exportToCSV = () => {
    const headers = [
      'Run ID',
      'Total Return %',
      'Total PnL',
      'Sharpe Ratio',
      'Win Rate',
      'Max Drawdown',
      'Num Trades',
      'Avg Trade Duration',
      'Start Date',
      'End Date',
    ];

    const rows = selectedBacktests.map((bt) => [
      bt.run_id || 'N/A',
      (bt.data.total_return_pct ?? 0).toFixed(2),
      (bt.data.total_pnl ?? 0).toFixed(2),
      (bt.data.sharpe_ratio ?? 0).toFixed(2),
      (bt.data.win_rate ?? 0).toFixed(2),
      (bt.data.max_drawdown ?? 0).toFixed(2),
      bt.data.num_trades ?? 0,
      (bt.data.avg_trade_duration ?? 0).toFixed(1),
      bt.data.start_date || 'N/A',
      bt.data.end_date || 'N/A',
    ]);

    const csv = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest-comparison-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  // Get best/worst for highlighting
  const getBest = (metric: keyof BacktestResult) => {
    if (selectedBacktests.length === 0) return null;
    const metricValues = selectedBacktests.map((bt) => ({
      run_id: bt.run_id,
      value: bt.data[metric] as number,
    }));
    // Higher is better for most metrics (return, sharpe, win_rate)
    // Lower is better for drawdown
    if (metric === 'max_drawdown') {
      return metricValues.reduce((min, curr) => (curr.value < min.value ? curr : min)).run_id;
    }
    return metricValues.reduce((max, curr) => (curr.value > max.value ? curr : max)).run_id;
  };

  // Calculate how old a cached result is
  const getCacheAgeText = (createdAt?: string): string | null => {
    if (!createdAt) return null;
    const created = new Date(createdAt);
    const now = new Date();
    const diffMs = now.getTime() - created.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    return 'Today';
  };

  return (
    <div className="space-y-6">
      {/* Backtest Selection - Card View */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-white">Compare Backtests</h2>
            <p className="text-sm text-gray-400 mt-1">
              Select up to 5 backtests to compare side by side
            </p>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-400">
              Showing {(currentPage - 1) * ITEMS_PER_PAGE + 1} -{' '}
              {Math.min(currentPage * ITEMS_PER_PAGE, backtests.length)} of {backtests.length}
            </div>
            <div className="text-sm font-semibold text-blue-400 mt-1">
              Selected: {selectedBacktests.length} / 5
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-900 border border-red-700 rounded text-red-200">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-12">
            <div className="text-gray-400">Loading backtests...</div>
          </div>
        ) : backtests.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-gray-400">No backtests available</div>
          </div>
        ) : (
          <>
            {/* Card Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
              {paginatedBacktests.map((bt) => {
                const isSelected = selectedBacktests.some((s) => s.run_id === bt.run_id);
                const canSelectMore = selectedBacktests.length < 5;
                const isClickable = isSelected || canSelectMore;

                return (
                  <button
                    key={bt.run_id}
                    onClick={() => isClickable && toggleBacktest(bt)}
                    disabled={!isClickable}
                    className={`relative p-4 rounded-lg border-2 transition-all text-left ${
                      isSelected
                        ? 'bg-blue-900 border-blue-500 shadow-lg shadow-blue-500/20'
                        : isClickable
                          ? 'bg-slate-700 border-slate-600 hover:border-slate-500 hover:bg-slate-600'
                          : 'bg-slate-700 border-slate-600 opacity-50 cursor-not-allowed'
                    }`}
                  >
                    {/* Selection Indicator */}
                    {isSelected && (
                      <div className="absolute top-2 right-2 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center">
                        <div className="w-2 h-2 bg-white rounded-full"></div>
                      </div>
                    )}

                    {/* Card Content */}
                    <div>
                      {/* Run ID */}
                      <div className="font-mono text-xs text-blue-300 mb-2">
                        {(bt.run_id || 'N/A').slice(0, 8)}
                      </div>

                      {/* Date Range + Cache Badge */}
                      <div className="mb-3">
                        <div className="text-xs text-gray-400 mb-2 line-clamp-2">
                          {(bt.start_date || 'N/A').split('T')[0]} to{' '}
                          {(bt.end_date || 'N/A').split('T')[0]}
                        </div>
                        {bt.is_from_cache && (
                          <div className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-orange-900 text-orange-200 border border-orange-700">
                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z" />
                            </svg>
                            <span>
                              From cache {bt.created_at && `(${getCacheAgeText(bt.created_at)})`}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Key Metrics */}
                      <div className="space-y-2">
                        {/* Return */}
                        <div className="flex items-end justify-between">
                          <span className="text-xs text-gray-400">Return</span>
                          <span
                            className={`font-semibold text-sm ${
                              (bt.total_return_pct ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                            }`}
                          >
                            {(bt.total_return_pct ?? 0).toFixed(1)}%
                          </span>
                        </div>

                        {/* Sharpe */}
                        <div className="flex items-end justify-between">
                          <span className="text-xs text-gray-400">Sharpe</span>
                          <span
                            className={`font-semibold text-sm ${
                              (bt.sharpe_ratio ?? 0) >= 1 ? 'text-green-400' : 'text-yellow-400'
                            }`}
                          >
                            {(bt.sharpe_ratio ?? 0).toFixed(2)}
                          </span>
                        </div>

                        {/* Win Rate */}
                        <div className="flex items-end justify-between">
                          <span className="text-xs text-gray-400">Win Rate</span>
                          <span
                            className={`font-semibold text-sm ${
                              (bt.win_rate ?? 0) >= 50 ? 'text-green-400' : 'text-orange-400'
                            }`}
                          >
                            {(bt.win_rate ?? 0).toFixed(0)}%
                          </span>
                        </div>

                        {/* PnL */}
                        <div className="flex items-end justify-between">
                          <span className="text-xs text-gray-400">PnL</span>
                          <span
                            className={`font-semibold text-sm ${
                              (bt.total_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                            }`}
                          >
                            ${(bt.total_pnl ?? 0).toFixed(0)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t border-slate-600">
                <button
                  onClick={handlePreviousPage}
                  disabled={currentPage === 1}
                  className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  ← Previous
                </button>

                <div className="flex items-center gap-2">
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={`px-3 py-1 rounded text-sm font-medium ${
                        currentPage === page
                          ? 'bg-blue-600 text-white'
                          : 'text-gray-400 hover:text-white hover:bg-slate-700'
                      }`}
                    >
                      {page}
                    </button>
                  ))}
                </div>

                <button
                  onClick={handleNextPage}
                  disabled={currentPage === totalPages}
                  className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Comparison Table */}
      {selectedBacktests.length > 0 && (
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 overflow-x-auto">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-white">Comparison Results</h3>
            <button
              onClick={exportToCSV}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </button>
          </div>

          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-600">
                <th className="text-left px-4 py-2 text-gray-300 font-medium">Metric</th>
                {selectedBacktests.map((bt) => (
                  <th key={bt.run_id} className="text-left px-4 py-2 text-gray-300 font-medium">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs">{bt.run_id.slice(0, 8)}</span>
                      <button
                        onClick={() => removeSelected(bt.run_id)}
                        className="text-gray-400 hover:text-red-400"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {/* Total Return */}
              <tr className="hover:bg-slate-700">
                <td className="px-4 py-3 text-gray-400 font-medium">Total Return %</td>
                {selectedBacktests.map((bt, idx) => {
                  const isBest = getBest('total_return_pct') === bt.run_id;
                  const delta = getDelta('total_return_pct', idx);
                  return (
                    <td
                      key={bt.run_id}
                      className={`px-4 py-3 font-mono ${
                        isBest ? 'text-green-400' : 'text-gray-300'
                      }`}
                    >
                      <div>{(bt.data.total_return_pct ?? 0).toFixed(2)}%</div>
                      {delta && (
                        <div
                          className={`text-xs ${
                            delta.delta >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}
                        >
                          {delta.delta >= 0 ? '+' : ''}
                          {delta.delta.toFixed(2)}% ({delta.deltaPercent.toFixed(1)}
                          %)
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>

              {/* Total PnL */}
              <tr className="hover:bg-slate-700">
                <td className="px-4 py-3 text-gray-400 font-medium">Total PnL</td>
                {selectedBacktests.map((bt, idx) => {
                  const isBest = getBest('total_pnl') === bt.run_id;
                  const delta = getDelta('total_pnl', idx);
                  return (
                    <td
                      key={bt.run_id}
                      className={`px-4 py-3 font-mono ${
                        isBest ? 'text-green-400' : 'text-gray-300'
                      }`}
                    >
                      <div>${(bt.data.total_pnl ?? 0).toFixed(2)}</div>
                      {delta && (
                        <div
                          className={`text-xs ${
                            delta.delta >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}
                        >
                          {delta.delta >= 0 ? '+' : ''}${delta.delta.toFixed(2)}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>

              {/* Sharpe Ratio */}
              <tr className="hover:bg-slate-700">
                <td className="px-4 py-3 text-gray-400 font-medium">Sharpe Ratio</td>
                {selectedBacktests.map((bt, idx) => {
                  const isBest = getBest('sharpe_ratio') === bt.run_id;
                  const delta = getDelta('sharpe_ratio', idx);
                  return (
                    <td
                      key={bt.run_id}
                      className={`px-4 py-3 font-mono ${
                        isBest ? 'text-green-400' : 'text-gray-300'
                      }`}
                    >
                      <div>{(bt.data.sharpe_ratio ?? 0).toFixed(2)}</div>
                      {delta && (
                        <div
                          className={`text-xs ${
                            delta.delta >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}
                        >
                          {delta.delta >= 0 ? '+' : ''}
                          {delta.delta.toFixed(2)}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>

              {/* Win Rate */}
              <tr className="hover:bg-slate-700">
                <td className="px-4 py-3 text-gray-400 font-medium">Win Rate</td>
                {selectedBacktests.map((bt, idx) => {
                  const isBest = getBest('win_rate') === bt.run_id;
                  const delta = getDelta('win_rate', idx);
                  return (
                    <td
                      key={bt.run_id}
                      className={`px-4 py-3 font-mono ${
                        isBest ? 'text-green-400' : 'text-gray-300'
                      }`}
                    >
                      <div>{(bt.data.win_rate ?? 0).toFixed(1)}%</div>
                      {delta && (
                        <div
                          className={`text-xs ${
                            delta.delta >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}
                        >
                          {delta.delta >= 0 ? '+' : ''}
                          {(delta.delta * 100).toFixed(1)}%
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>

              {/* Max Drawdown */}
              <tr className="hover:bg-slate-700">
                <td className="px-4 py-3 text-gray-400 font-medium">Max Drawdown</td>
                {selectedBacktests.map((bt, idx) => {
                  const isBest = getBest('max_drawdown') === bt.run_id;
                  const delta = getDelta('max_drawdown', idx);
                  return (
                    <td
                      key={bt.run_id}
                      className={`px-4 py-3 font-mono ${
                        isBest ? 'text-green-400' : 'text-gray-300'
                      }`}
                    >
                      <div>{(bt.data.max_drawdown ?? 0).toFixed(1)}%</div>
                      {delta && (
                        <div
                          className={`text-xs ${
                            delta.delta <= 0 ? 'text-green-400' : 'text-red-400'
                          }`}
                        >
                          {delta.delta >= 0 ? '+' : ''}
                          {(delta.delta * 100).toFixed(1)}%
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>

              {/* Num Trades */}
              <tr className="hover:bg-slate-700">
                <td className="px-4 py-3 text-gray-400 font-medium">Number of Trades</td>
                {selectedBacktests.map((bt) => (
                  <td key={bt.run_id} className="px-4 py-3 font-mono text-gray-300">
                    {bt.data.num_trades ?? 0}
                  </td>
                ))}
              </tr>

              {/* Avg Trade Duration */}
              <tr className="hover:bg-slate-700">
                <td className="px-4 py-3 text-gray-400 font-medium">Avg Trade Duration (hours)</td>
                {selectedBacktests.map((bt) => (
                  <td key={bt.run_id} className="px-4 py-3 font-mono text-gray-300">
                    {(bt.data.avg_trade_duration ?? 0).toFixed(1)}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {selectedBacktests.length === 0 && !loading && (
        <div className="text-center py-12 text-gray-400">
          Select at least 2 backtests to compare
        </div>
      )}
    </div>
  );
};
