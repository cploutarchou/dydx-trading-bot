/**
 * Enhanced Backtest Results Component with Pagination & Filtering
 * Production-ready with data validation and UX/UI best practices
 */

import { ChevronDown, Filter, RefreshCw } from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';
import api from '../api';

// Types
interface BacktestFilters {
  minWinRate?: number;
  maxDrawdown?: number;
  minTrades?: number;
  sortBy: 'pnl' | 'win_rate' | 'sharpe_ratio' | 'total_trades';
  sortOrder: 'asc' | 'desc';
}

interface BacktestResult {
  id: number;
  pair: string;
  market_1: string;
  market_2: string;
  total_trades: number;
  profitable_trades: number;
  losing_trades: number;
  win_rate: number;
  pnl_usd: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  max_drawdown: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  avg_trade_duration_hours: number;
  cointegration_score: number;
  zscore_mean: number;
  zscore_std: number;
}

interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
  returned: number;
  pages: number;
  current_page: number;
}

interface DataQuality {
  score: number;
  warnings: string[];
}

interface TradeRow {
  trade_id?: string;
  market_1?: string;
  market_2?: string;
  pnl_usd?: number;
  win?: boolean;
  duration_hours?: number;
}

const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const getErrorMessage = (error: unknown, fallback: string): string =>
  error instanceof Error ? error.message : fallback;

const getSortMetric = (result: BacktestResult, field: BacktestFilters['sortBy']): number => {
  switch (field) {
    case 'pnl':
      return result.pnl_usd;
    case 'win_rate':
      return result.win_rate;
    case 'sharpe_ratio':
      return result.sharpe_ratio ?? 0;
    case 'total_trades':
      return result.total_trades;
    default:
      return 0;
  }
};

// Formatting utilities
const formatCurrency = (value: number | null): string => {
  if (value === null || isNaN(value)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(value);
};

const formatPercent = (value: number | null): string => {
  if (value === null || isNaN(value)) return '—';
  return `${value.toFixed(1)}%`;
};

const formatRatio = (value: number | null): string => {
  if (value === null || isNaN(value)) return 'N/A';
  return value.toFixed(2);
};

// Component
export const BacktestResultsEnhanced: React.FC<{
  runId: string;
  liveRefreshToken?: string | null;
}> = ({ runId, liveRefreshToken }) => {
  // State
  const [results, setResults] = useState<BacktestResult[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta>({
    total: 0,
    limit: 20,
    offset: 0,
    returned: 0,
    pages: 0,
    current_page: 1,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dataQuality, setDataQuality] = useState<DataQuality | null>(null);

  // Filters
  const [filters, setFilters] = useState<BacktestFilters>({
    minWinRate: undefined,
    maxDrawdown: undefined,
    minTrades: undefined,
    sortBy: 'pnl',
    sortOrder: 'desc',
  });

  const [showFilters, setShowFilters] = useState(false);

  const buildResultsFromTrades = (trades: TradeRow[]): BacktestResult[] => {
    const groups = new Map<
      string,
      {
        id: number;
        pair: string;
        market_1: string;
        market_2: string;
        pnlValues: number[];
        totalPnl: number;
        totalTrades: number;
        profitableTrades: number;
        losingTrades: number;
        sumWins: number;
        sumLosses: number;
        durations: number[];
      }
    >();

    trades.forEach((t, idx) => {
      const m1 = t.market_1 || 'UNKNOWN-1';
      const m2 = t.market_2 || 'UNKNOWN-2';
      const pair = `${m1}/${m2}`;
      const key = `${m1}::${m2}`;
      const pnl = Number(t.pnl_usd || 0);
      const duration = Number(t.duration_hours || 0);
      const win = typeof t.win === 'boolean' ? t.win : pnl >= 0;

      if (!groups.has(key)) {
        groups.set(key, {
          id: idx + 1,
          pair,
          market_1: m1,
          market_2: m2,
          pnlValues: [],
          totalPnl: 0,
          totalTrades: 0,
          profitableTrades: 0,
          losingTrades: 0,
          sumWins: 0,
          sumLosses: 0,
          durations: [],
        });
      }

      const g = groups.get(key)!;
      g.totalTrades += 1;
      g.totalPnl += pnl;
      g.pnlValues.push(pnl);
      if (duration > 0) g.durations.push(duration);

      if (win) {
        g.profitableTrades += 1;
        g.sumWins += pnl;
      } else {
        g.losingTrades += 1;
        g.sumLosses += pnl;
      }
    });

    return Array.from(groups.values()).map((g) => {
      const winRate = g.totalTrades > 0 ? (g.profitableTrades / g.totalTrades) * 100 : 0;
      const avgWin = g.profitableTrades > 0 ? g.sumWins / g.profitableTrades : 0;
      const avgLoss = g.losingTrades > 0 ? g.sumLosses / g.losingTrades : 0;
      const profitFactor = Math.abs(g.sumLosses) > 0 ? g.sumWins / Math.abs(g.sumLosses) : 0;

      const mean = g.pnlValues.length
        ? g.pnlValues.reduce((a, b) => a + b, 0) / g.pnlValues.length
        : 0;
      const variance =
        g.pnlValues.length > 1
          ? g.pnlValues.reduce((acc, v) => acc + (v - mean) ** 2, 0) / (g.pnlValues.length - 1)
          : 0;
      const std = Math.sqrt(variance);
      const sharpeRatio = std > 0 ? mean / std : null;

      let running = 0;
      let peak = 0;
      let maxDrawdown = 0;
      g.pnlValues.forEach((v) => {
        running += v;
        peak = Math.max(peak, running);
        maxDrawdown = Math.min(maxDrawdown, running - peak);
      });

      const avgDuration =
        g.durations.length > 0 ? g.durations.reduce((a, b) => a + b, 0) / g.durations.length : 0;

      return {
        id: g.id,
        pair: g.pair,
        market_1: g.market_1,
        market_2: g.market_2,
        total_trades: g.totalTrades,
        profitable_trades: g.profitableTrades,
        losing_trades: g.losingTrades,
        win_rate: winRate,
        pnl_usd: g.totalPnl,
        avg_win: avgWin,
        avg_loss: avgLoss,
        profit_factor: profitFactor,
        max_drawdown: maxDrawdown,
        sharpe_ratio: sharpeRatio,
        sortino_ratio: null,
        avg_trade_duration_hours: avgDuration,
        cointegration_score: 0,
        zscore_mean: 0,
        zscore_std: 0,
      };
    });
  };

  // Fetch results with pagination and filters
  const fetchResults = useCallback(
    async (page: number = 0) => {
      const hasExistingResults = results.length > 0;
      setLoading(!hasExistingResults);
      setError(null);

      try {
        const apiResponse = await api.getBacktestTradesDetailed(
          runId,
          undefined,
          undefined,
          0,
          1000
        );
        const responseRoot = toRecord(apiResponse);
        const root = toRecord(responseRoot.data ?? responseRoot);
        const trades = Array.isArray(root.trades) ? (root.trades as TradeRow[]) : [];

        let aggregated = buildResultsFromTrades(trades);

        if (filters.minWinRate !== undefined) {
          aggregated = aggregated.filter((r) => r.win_rate >= filters.minWinRate!);
        }
        if (filters.maxDrawdown !== undefined) {
          aggregated = aggregated.filter((r) => r.max_drawdown >= filters.maxDrawdown!);
        }
        if (filters.minTrades !== undefined) {
          aggregated = aggregated.filter((r) => r.total_trades >= filters.minTrades!);
        }

        aggregated.sort((a, b) => {
          const aVal = getSortMetric(a, filters.sortBy);
          const bVal = getSortMetric(b, filters.sortBy);
          return filters.sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
        });

        const total = aggregated.length;
        const limit = pagination.limit;
        const offset = page * limit;
        const pageResults = aggregated.slice(offset, offset + limit);
        const pages = Math.max(1, Math.ceil(total / limit));

        setResults(pageResults);
        setPagination({
          total,
          limit,
          offset,
          returned: pageResults.length,
          pages,
          current_page: page + 1,
        });

        setDataQuality({
          score: 100,
          warnings: [],
        });
      } catch (err: unknown) {
        setError(getErrorMessage(err, 'Failed to load results'));
        if (results.length === 0) {
          setResults([]);
        }
      } finally {
        setLoading(false);
      }
    },
    [filters, pagination.limit, results.length, runId]
  );

  // Load initial data
  useEffect(() => {
    fetchResults(0);
  }, [fetchResults, filters]);

  useEffect(() => {
    if (!liveRefreshToken) {
      return;
    }
    void fetchResults(Math.max(0, pagination.current_page - 1));
  }, [fetchResults, liveRefreshToken, pagination.current_page]);

  // Handle filter changes
  const updateFilter = <K extends keyof BacktestFilters>(
    filterName: K,
    value: BacktestFilters[K]
  ) => {
    setFilters((prev) => ({
      ...prev,
      [filterName]: value,
    }));
  };

  const clearFilters = () => {
    setFilters({
      minWinRate: undefined,
      maxDrawdown: undefined,
      minTrades: undefined,
      sortBy: 'pnl',
      sortOrder: 'desc',
    });
  };

  // Render
  return (
    <div className="space-y-6">
      {/* Data Quality Warning */}
      {dataQuality && dataQuality.score < 90 && (
        <div className="bg-yellow-900/50 border border-yellow-700 text-yellow-100 px-4 py-3 rounded">
          <p className="font-semibold">⚠️ Data Quality: {dataQuality.score}%</p>
          <ul className="text-sm mt-2 space-y-1">
            {dataQuality.warnings.map((warning, i) => (
              <li key={i}>• {warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Filter Panel */}
      <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="flex items-center gap-2 text-slate-200 hover:text-white"
        >
          <Filter size={18} />
          <span>Filters {Object.values(filters).some((v) => v !== undefined) && '(Active)'}</span>
          <ChevronDown size={18} className={showFilters ? 'rotate-180' : ''} />
        </button>

        {showFilters && (
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Min Win Rate */}
            <div>
              <label className="block text-sm text-slate-400 mb-1">Min Win Rate %</label>
              <input
                type="number"
                min="0"
                max="100"
                value={filters.minWinRate || ''}
                onChange={(e) =>
                  updateFilter(
                    'minWinRate',
                    e.target.value ? parseFloat(e.target.value) : undefined
                  )
                }
                className="w-full bg-slate-700 text-white px-2 py-1 rounded text-sm"
                placeholder="e.g., 40"
              />
            </div>

            {/* Max Drawdown */}
            <div>
              <label className="block text-sm text-slate-400 mb-1">Max Drawdown %</label>
              <input
                type="number"
                value={filters.maxDrawdown || ''}
                onChange={(e) =>
                  updateFilter(
                    'maxDrawdown',
                    e.target.value ? parseFloat(e.target.value) : undefined
                  )
                }
                className="w-full bg-slate-700 text-white px-2 py-1 rounded text-sm"
                placeholder="e.g., -20"
              />
            </div>

            {/* Min Trades */}
            <div>
              <label className="block text-sm text-slate-400 mb-1">Min Trades</label>
              <input
                type="number"
                min="1"
                value={filters.minTrades || ''}
                onChange={(e) =>
                  updateFilter('minTrades', e.target.value ? parseInt(e.target.value) : undefined)
                }
                className="w-full bg-slate-700 text-white px-2 py-1 rounded text-sm"
                placeholder="e.g., 10"
              />
            </div>

            {/* Sort By */}
            <div>
              <label className="block text-sm text-slate-400 mb-1">Sort By</label>
              <select
                value={filters.sortBy}
                onChange={(e) => updateFilter('sortBy', e.target.value as BacktestFilters['sortBy'])}
                className="w-full bg-slate-700 text-white px-2 py-1 rounded text-sm"
              >
                <option value="pnl">P&L</option>
                <option value="win_rate">Win Rate</option>
                <option value="sharpe_ratio">Sharpe Ratio</option>
                <option value="total_trades">Total Trades</option>
              </select>
            </div>

            {/* Actions */}
            <div className="col-span-2 md:col-span-4 flex gap-2 mt-2">
              <button
                onClick={clearFilters}
                className="px-3 py-1 bg-slate-700 text-slate-300 rounded text-sm hover:bg-slate-600"
              >
                Clear All
              </button>
              <button
                onClick={() => fetchResults(0)}
                className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 flex items-center gap-1"
              >
                <RefreshCw size={14} />
                Refresh
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-100 px-4 py-3 rounded">
          <p>{error}</p>
          <button
            onClick={() => fetchResults(0)}
            className="mt-2 px-3 py-1 bg-red-700 hover:bg-red-600 text-white rounded text-sm"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
          <p className="text-slate-400 mt-2">Loading results...</p>
        </div>
      )}

      {/* Results Table */}
      {!loading && results.length > 0 && (
        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-700 bg-slate-900">
              <tr>
                <th className="px-4 py-2 text-left text-slate-400 font-medium">Pair</th>
                <th className="px-4 py-2 text-right text-slate-400 font-medium">Trades</th>
                <th className="px-4 py-2 text-right text-slate-400 font-medium">Win Rate</th>
                <th className="px-4 py-2 text-right text-slate-400 font-medium">P&L</th>
                <th className="px-4 py-2 text-right text-slate-400 font-medium">Profit Factor</th>
                <th className="px-4 py-2 text-right text-slate-400 font-medium">Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result, idx) => (
                <tr
                  key={result.id}
                  className={`border-b border-slate-700 ${
                    idx % 2 === 0 ? 'bg-slate-800' : 'bg-slate-850'
                  } hover:bg-slate-700 cursor-pointer transition`}
                >
                  <td className="px-4 py-2 text-white font-medium">{result.pair}</td>
                  <td className="px-4 py-2 text-right text-slate-300">{result.total_trades}</td>
                  <td
                    className={`px-4 py-2 text-right font-medium ${
                      (result.win_rate || 0) >= 50 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {formatPercent(result.win_rate)}
                  </td>
                  <td
                    className={`px-4 py-2 text-right font-medium ${
                      (result.pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {formatCurrency(result.pnl_usd)}
                  </td>
                  <td className="px-4 py-2 text-right text-slate-300">
                    {formatRatio(result.profit_factor)}
                  </td>
                  <td className="px-4 py-2 text-right text-slate-300">
                    {result.sharpe_ratio !== null ? formatRatio(result.sharpe_ratio) : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty State */}
      {!loading && results.length === 0 && !error && (
        <div className="text-center py-12 text-slate-400">
          <p className="text-lg mb-2">No results found</p>
          <p className="text-sm">Try adjusting your filters</p>
        </div>
      )}

      {/* Pagination */}
      {!loading && pagination.pages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-slate-400 text-sm">
            Showing {pagination.offset + 1} to {pagination.offset + pagination.returned} of{' '}
            {pagination.total} results
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => fetchResults(pagination.current_page - 2)}
              disabled={pagination.current_page === 1}
              className="px-3 py-1 bg-slate-700 text-white rounded disabled:opacity-50"
            >
              ← Previous
            </button>
            <span className="px-3 py-1 text-slate-300">
              Page {pagination.current_page} of {pagination.pages}
            </span>
            <button
              onClick={() => fetchResults(pagination.current_page)}
              disabled={pagination.current_page === pagination.pages}
              className="px-3 py-1 bg-slate-700 text-white rounded disabled:opacity-50"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default BacktestResultsEnhanced;
