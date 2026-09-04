/**
 * Trade History Component - Task 19
 *
 * Displays paginated table of all trades in a backtest:
 * - Entry/exit prices and timestamps
 * - Market pairs and trade sides
 * - PnL and duration for each trade
 * - Click to view detailed trade info
 */

import React, { useState } from 'react';
import { useBacktestTrades } from '../api/hooks';

interface Trade {
  id: number;
  trade_id: string;
  market_1: string;
  market_2: string;
  entry_timestamp: string;
  exit_timestamp: string;
  entry_price_1: number;
  entry_price_2: number;
  exit_price_1: number;
  exit_price_2: number;
  side_1: string;
  side_2: string;
  size_1: number;
  size_2: number;
  pnl: number;
  pnl_pct: number;
  duration_hours: number;
}

interface TradeHistoryProps {
  runId: string;
  onTradeSelect?: (trade: Trade) => void;
}

export const TradeHistory: React.FC<TradeHistoryProps> = ({ runId, onTradeSelect }) => {
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const tradesQuery = useBacktestTrades(runId, limit, offset);
  // useBacktestTrades unwraps the envelope to { count, data: trades[] }
  const trades = (tradesQuery.data?.data ?? []) as unknown as Trade[];
  const total = tradesQuery.data?.count || 0;
  const loading = tradesQuery.isLoading && trades.length === 0;
  const error =
    tradesQuery.error instanceof Error
      ? tradesQuery.error.message
      : tradesQuery.isError
        ? 'Failed to load trades'
        : null;

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return (
      date.toLocaleDateString() +
      ' ' +
      date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    );
  };

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  if (loading && trades.length === 0) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-slate-700 rounded w-1/4"></div>
          <div className="h-64 bg-slate-700 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{error}</div>
    );
  }

  if (trades.length === 0) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 text-center">
        <p className="text-gray-400">No trades found in this backtest</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Trade History</h2>
        <p className="text-gray-400">All trades executed during this backtest ({total} total)</p>
      </div>

      {/* Table */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-700 border-b border-slate-600">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-300">#</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-300">Entry Time</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-300">Exit Time</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-300">Markets</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-300">Entry Price</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-300">Exit Price</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-300">P&L</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-300">Duration</th>
                <th className="px-4 py-3 text-center font-semibold text-gray-300">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {trades.map((trade, index) => (
                <tr key={trade.id} className="hover:bg-slate-700 transition-colors">
                  <td className="px-4 py-3 text-gray-300">{offset + index + 1}</td>
                  <td className="px-4 py-3 text-gray-300 text-xs">
                    {formatDate(trade.entry_timestamp)}
                  </td>
                  <td className="px-4 py-3 text-gray-300 text-xs">
                    {formatDate(trade.exit_timestamp)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-mono text-xs">
                      <div className="text-blue-400">{trade.market_1}</div>
                      <div className="text-purple-400">{trade.market_2}</div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-300 text-xs">
                    <div>${trade.entry_price_1.toFixed(2)}</div>
                    <div className="text-gray-500">${trade.entry_price_2.toFixed(2)}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-300 text-xs">
                    <div>${trade.exit_price_1.toFixed(2)}</div>
                    <div className="text-gray-500">${trade.exit_price_2.toFixed(2)}</div>
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">
                    <div className={trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                      ${trade.pnl.toFixed(2)}
                    </div>
                    <div
                      className={`text-xs ${trade.pnl_pct >= 0 ? 'text-green-500' : 'text-red-500'}`}
                    >
                      ({trade.pnl_pct.toFixed(2)}%)
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-400 text-xs">
                    {trade.duration_hours.toFixed(1)}h
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => onTradeSelect?.(trade)}
                      className="text-blue-400 hover:text-blue-300 font-medium text-xs hover:underline"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="flex justify-between items-center text-sm text-gray-400">
        <div>
          Showing {offset + 1}-{Math.min(offset + limit, total)} of {total} trades
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed rounded text-xs font-medium"
          >
            ← Previous
          </button>
          <div className="px-3 py-2 text-gray-400">
            Page {currentPage} of {totalPages}
          </div>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={offset + limit >= total}
            className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed rounded text-xs font-medium"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
};

export default TradeHistory;
