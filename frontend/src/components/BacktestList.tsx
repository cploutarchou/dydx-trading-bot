import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';

type RunStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

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
  max_drawdown_pct?: number;
  created_at: string;
}

const normalizeStatus = (status?: string): RunStatus => {
  const normalized = String(status || '')
    .trim()
    .toUpperCase();
  if (normalized === 'CREATED') return 'PENDING';
  if (normalized === 'RUNNING') return 'RUNNING';
  if (normalized === 'COMPLETED') return 'COMPLETED';
  if (normalized === 'FAILED') return 'FAILED';
  if (normalized === 'CANCELLED') return 'CANCELLED';
  return 'PENDING';
};

const statusBadgeClass = (status: RunStatus): string => {
  switch (status) {
    case 'COMPLETED':
      return 'bg-green-900 text-green-300';
    case 'RUNNING':
      return 'bg-blue-900 text-blue-300';
    case 'FAILED':
      return 'bg-red-900 text-red-300';
    case 'CANCELLED':
      return 'bg-slate-700 text-slate-300';
    default:
      return 'bg-yellow-900 text-yellow-300';
  }
};

export const BacktestList: React.FC<{ refreshTrigger?: number }> = ({ refreshTrigger = 0 }) => {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<RunStatus | 'ALL'>('ALL');

  useEffect(() => {
    loadBacktests();
  }, [refreshTrigger]);

  const loadBacktests = async () => {
    setLoading(true);
    setError(null);
    try {
      const pageSize = 200;
      let skip = 0;
      let total: number | null = null;
      let pageGuard = 0;
      const allRuns: BacktestRun[] = [];

      while (pageGuard < 20) {
        pageGuard += 1;
        const response = await api.listBacktests(skip, pageSize);
        const raw = response as any;

        const pageRuns: BacktestRun[] = Array.isArray(raw?.backtests)
          ? raw.backtests
          : Array.isArray(raw?.data?.backtests)
            ? raw.data.backtests
            : Array.isArray(raw?.data?.runs)
              ? raw.data.runs
              : Array.isArray(raw?.runs)
                ? raw.runs
                : [];

        const pageTotal =
          typeof raw?.total === 'number'
            ? raw.total
            : typeof raw?.data?.total === 'number'
              ? raw.data.total
              : null;

        if (pageTotal !== null) {
          total = pageTotal;
        }

        if (!Array.isArray(pageRuns)) {
          console.error('❌ BacktestList: backtests is not an array!', pageRuns);
          setError('Invalid response format from server');
          setRuns([]);
          return;
        }

        allRuns.push(...pageRuns);

        if (pageRuns.length < pageSize) {
          break;
        }

        skip += pageSize;

        if (total !== null && allRuns.length >= total) {
          break;
        }
      }

      setRuns(allRuns);
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

  const statusCounts: Record<RunStatus, number> = {
    PENDING: 0,
    RUNNING: 0,
    COMPLETED: 0,
    FAILED: 0,
    CANCELLED: 0,
  };

  for (const run of runs) {
    statusCounts[normalizeStatus(run.status)] += 1;
  }

  const filteredRuns = runs.filter((run) => {
    if (statusFilter === 'ALL') return true;
    return normalizeStatus(run.status) === statusFilter;
  });

  const formatPct = (value: number | undefined | null) => {
    if (value === undefined || value === null || Number.isNaN(Number(value))) return 'N/A';
    return `${Number(value).toFixed(1)}%`;
  };

  const maxDdValue = (run: BacktestRun) =>
    run.max_drawdown_pct !== undefined && run.max_drawdown_pct !== null
      ? run.max_drawdown_pct
      : run.max_drawdown;

  return (
    <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
      <h3 className="text-xl font-bold text-white mb-4">Backtest Runs ({runs.length})</h3>

      <div className="mb-4 flex flex-wrap gap-2">
        {(
          [
            ['ALL', runs.length],
            ['PENDING', statusCounts.PENDING],
            ['RUNNING', statusCounts.RUNNING],
            ['COMPLETED', statusCounts.COMPLETED],
            ['FAILED', statusCounts.FAILED],
            ['CANCELLED', statusCounts.CANCELLED],
          ] as const
        ).map(([status, count]) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
              statusFilter === status
                ? 'bg-blue-600 text-white border-blue-500'
                : 'bg-slate-700 text-slate-200 border-slate-600 hover:bg-slate-600'
            }`}
          >
            {status} ({count})
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-900 border border-red-700 rounded text-red-200">
          {error}
        </div>
      )}

      {filteredRuns.length === 0 ? (
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
              {Array.isArray(filteredRuns) &&
                filteredRuns.map((run) => {
                  const normalizedStatus = normalizeStatus(run.status);

                  return (
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
                            {new Date(run.start_date).toLocaleDateString()} -{' '}
                            {new Date(run.end_date).toLocaleDateString()}
                          </>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td className="px-4 py-2 text-center">{run.total_trades}</td>
                      <td
                        className={`px-4 py-2 text-right font-semibold ${run.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
                      >
                        ${run.total_pnl.toFixed(2)}
                      </td>
                      <td className="px-4 py-2 text-right">{formatPct(run.win_rate)}</td>
                      <td className="px-4 py-2 text-right">
                        {run.sharpe_ratio ? run.sharpe_ratio.toFixed(2) : 'N/A'}
                      </td>
                      <td className="px-4 py-2 text-right">{formatPct(maxDdValue(run))}</td>
                      <td className="px-4 py-2 text-center">
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${statusBadgeClass(normalizedStatus)}`}
                        >
                          {normalizedStatus}
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
                  );
                })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
