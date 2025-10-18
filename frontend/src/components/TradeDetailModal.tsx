/**
 * Trade Detail Modal Component - Task 19
 * 
 * Modal showing detailed information about a specific trade:
 * - Entry/exit details with prices and Z-scores
 * - Market pair and position sizing
 * - PnL calculation breakdown
 * - Fees and slippage
 */

import React, { useEffect, useState } from 'react';
import apiClient from '../api';

interface TradeDetail {
  id: number;
  trade_id: string;
  run_id: string;
  market_1: string;
  market_2: string;
  entry_timestamp: string;
  exit_timestamp: string;
  entry_price_1: number;
  entry_price_2: number;
  exit_price_1: number;
  exit_price_2: number;
  entry_z_score: number;
  exit_z_score: number;
  side_1: string;
  side_2: string;
  size_1: number;
  size_2: number;
  hedge_ratio: number;
  pnl: number;
  pnl_pct: number;
  duration_hours: number;
  transaction_fee: number;
  slippage: number;
}

interface TradeDetailModalProps {
  runId: string;
  tradeId: number;
  isOpen: boolean;
  onClose: () => void;
}

export const TradeDetailModal: React.FC<TradeDetailModalProps> = ({ runId, tradeId, isOpen, onClose }) => {
  const [trade, setTrade] = useState<TradeDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && runId && tradeId) {
      fetchTradeDetail();
    }
  }, [isOpen, runId, tradeId]);

  const fetchTradeDetail = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getBacktestTrade(runId, tradeId.toString());
      if (response.success) {
        setTrade(response.data as TradeDetail);
      } else {
        setError(response.message || 'Failed to load trade details');
      }
    } catch (err: any) {
      setError(err.message || 'Error loading trade details');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-lg border border-slate-700 max-w-2xl w-full max-h-96 overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-slate-700 sticky top-0 bg-slate-800">
          <div>
            <h2 className="text-2xl font-bold text-white">Trade Details</h2>
            <p className="text-gray-400 text-sm mt-1">Trade ID: {trade?.trade_id}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl font-bold"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {loading && (
            <div className="flex justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {trade && !loading && !error && (
            <>
              {/* Market Pair */}
              <div>
                <h3 className="text-lg font-bold text-white mb-3">Market Pair</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-slate-700 rounded-lg border border-slate-600">
                    <p className="text-gray-400 text-sm">Base Market</p>
                    <p className="text-xl font-bold text-blue-400 mt-1">{trade.market_1}</p>
                  </div>
                  <div className="p-3 bg-slate-700 rounded-lg border border-slate-600">
                    <p className="text-gray-400 text-sm">Quote Market</p>
                    <p className="text-xl font-bold text-purple-400 mt-1">{trade.market_2}</p>
                  </div>
                </div>
                <p className="text-gray-400 text-sm mt-2">
                  Hedge Ratio: <span className="text-white font-semibold">{trade.hedge_ratio.toFixed(4)}</span>
                </p>
              </div>

              {/* Entry Details */}
              <div>
                <h3 className="text-lg font-bold text-white mb-3">Entry</h3>
                <div className="space-y-2 text-sm">
                  <p className="text-gray-400">
                    Time: <span className="text-white font-mono">{formatDateTime(trade.entry_timestamp)}</span>
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-gray-400">Price ({trade.market_1})</p>
                      <p className="text-white font-semibold">${trade.entry_price_1.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-gray-400">Price ({trade.market_2})</p>
                      <p className="text-white font-semibold">${trade.entry_price_2.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-gray-400">Side ({trade.market_1})</p>
                      <p className={`font-semibold ${trade.side_1 === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                        {trade.side_1}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-400">Side ({trade.market_2})</p>
                      <p className={`font-semibold ${trade.side_2 === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                        {trade.side_2}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 p-3 bg-slate-700 rounded-lg border border-slate-600">
                    <p className="text-gray-400 text-xs">Entry Z-Score</p>
                    <p className={`text-lg font-bold ${Math.abs(trade.entry_z_score) >= 1.5 ? 'text-blue-400' : 'text-yellow-400'}`}>
                      {trade.entry_z_score.toFixed(3)}
                    </p>
                  </div>
                </div>
              </div>

              {/* Position Sizing */}
              <div>
                <h3 className="text-lg font-bold text-white mb-3">Position Sizing</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="p-3 bg-slate-700 rounded-lg border border-slate-600">
                    <p className="text-gray-400">Size ({trade.market_1})</p>
                    <p className="text-white font-semibold mt-1">{trade.size_1.toFixed(6)}</p>
                  </div>
                  <div className="p-3 bg-slate-700 rounded-lg border border-slate-600">
                    <p className="text-gray-400">Size ({trade.market_2})</p>
                    <p className="text-white font-semibold mt-1">{trade.size_2.toFixed(6)}</p>
                  </div>
                </div>
              </div>

              {/* Exit Details */}
              <div>
                <h3 className="text-lg font-bold text-white mb-3">Exit</h3>
                <div className="space-y-2 text-sm">
                  <p className="text-gray-400">
                    Time: <span className="text-white font-mono">{formatDateTime(trade.exit_timestamp)}</span>
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-gray-400">Price ({trade.market_1})</p>
                      <p className="text-white font-semibold">${trade.exit_price_1.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-gray-400">Price ({trade.market_2})</p>
                      <p className="text-white font-semibold">${trade.exit_price_2.toFixed(2)}</p>
                    </div>
                  </div>
                  <div className="mt-3 p-3 bg-slate-700 rounded-lg border border-slate-600">
                    <p className="text-gray-400 text-xs">Exit Z-Score</p>
                    <p className="text-lg font-bold text-yellow-400">
                      {trade.exit_z_score.toFixed(3)}
                    </p>
                  </div>
                </div>
              </div>

              {/* PnL Breakdown */}
              <div>
                <h3 className="text-lg font-bold text-white mb-3">Profit & Loss</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between p-3 bg-slate-700 rounded-lg border border-slate-600">
                    <span className="text-gray-400">Total P&L</span>
                    <span className={`font-semibold ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      ${trade.pnl.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between p-3 bg-slate-700 rounded-lg border border-slate-600">
                    <span className="text-gray-400">Return %</span>
                    <span className={`font-semibold ${trade.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {trade.pnl_pct.toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between p-3 bg-slate-700 rounded-lg border border-slate-600">
                    <span className="text-gray-400">Transaction Fee</span>
                    <span className="text-white font-semibold">-${trade.transaction_fee.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between p-3 bg-slate-700 rounded-lg border border-slate-600">
                    <span className="text-gray-400">Slippage</span>
                    <span className="text-white font-semibold">-${trade.slippage.toFixed(2)}</span>
                  </div>
                </div>
              </div>

              {/* Trade Duration */}
              <div className="p-4 bg-blue-900 bg-opacity-50 border border-blue-700 rounded-lg">
                <p className="text-blue-300 text-sm">Duration</p>
                <p className="text-2xl font-bold text-blue-400 mt-1">
                  {trade.duration_hours.toFixed(1)} hours
                </p>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-700 p-4 bg-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default TradeDetailModal;
