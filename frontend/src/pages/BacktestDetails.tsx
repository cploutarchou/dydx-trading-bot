import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Loader } from 'lucide-react';

interface BacktestData {
  id: number;
  run_id: string;
  status: string;
  created_at: string;
  start_date: string;
  end_date: string;
  num_pairs: number;
  total_markets: number;
  duration_seconds: number;
  total_trades: number;
  profitable_trades: number;
  win_rate: number;
  total_pnl: number;
  total_pnl_usd: number;
  sharpe_ratio: number;
  max_drawdown: number;
  profit_factor: number;
}

export const BacktestDetailsPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const [backtest, setBacktest] = useState<BacktestData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchBacktest = async () => {
      try {
        if (runId) {
          const response = await api.getBacktest(runId);
          if (response.success && response.data) {
            setBacktest(response.data);
          }
        }
      } catch (err: any) {
        setError(err.message || 'Failed to fetch backtest');
      } finally {
        setLoading(false);
      }
    };

    fetchBacktest();
  }, [runId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !backtest) {
    return (
      <div className="p-8 text-center text-red-600">
        {error || 'Backtest not found'}
      </div>
    );
  }

  const metrics = [
    { label: 'Total Trades', value: backtest.total_trades },
    { label: 'Win Rate', value: `${(backtest.win_rate * 100).toFixed(1)}%` },
    { label: 'Total PnL', value: `$${backtest.total_pnl_usd?.toFixed(2) || '0'}` },
    { label: 'Sharpe Ratio', value: backtest.sharpe_ratio?.toFixed(2) || 'N/A' },
    { label: 'Max Drawdown', value: `${(backtest.max_drawdown * 100).toFixed(1)}%` },
    { label: 'Profit Factor', value: backtest.profit_factor?.toFixed(2) || 'N/A' },
  ];

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Backtest Details</h1>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {metrics.map((metric) => (
            <div key={metric.label} className="bg-white p-6 rounded-lg shadow">
              <p className="text-sm text-slate-600 mb-2">{metric.label}</p>
              <p className="text-2xl font-bold text-slate-900">{metric.value}</p>
            </div>
          ))}
        </div>

        <div className="bg-white p-6 rounded-lg shadow mb-8">
          <h2 className="text-xl font-bold mb-4">Backtest Info</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-slate-600">Run ID</p>
              <p className="font-mono text-sm text-slate-900">{backtest.run_id}</p>
            </div>
            <div>
              <p className="text-sm text-slate-600">Status</p>
              <span className={`px-2 py-1 rounded text-white text-sm font-medium ${
                backtest.status === 'completed' ? 'bg-green-500' : 'bg-yellow-500'
              }`}>
                {backtest.status}
              </span>
            </div>
            <div>
              <p className="text-sm text-slate-600">Period</p>
              <p className="text-slate-900">{backtest.start_date} to {backtest.end_date}</p>
            </div>
            <div>
              <p className="text-sm text-slate-600">Duration</p>
              <p className="text-slate-900">{backtest.duration_seconds?.toFixed(1) || 'N/A'} seconds</p>
            </div>
            <div>
              <p className="text-sm text-slate-600">Markets Tested</p>
              <p className="text-slate-900">{backtest.total_markets}</p>
            </div>
            <div>
              <p className="text-sm text-slate-600">Pairs Analyzed</p>
              <p className="text-slate-900">{backtest.num_pairs}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
