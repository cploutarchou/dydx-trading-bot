import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';

type RunStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

interface BacktestRun {
  id?: string;
  run_id: string;
  name?: string;
  start_date?: string;
  end_date?: string;
  status: string;
  progress_pct?: number;
  current_pair?: string;
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
  updated_at?: string;
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

/** Format a millisecond duration as "Xh Ym Zs" (omits leading zeros). */
function formatDuration(ms: number): string {
  if (ms <= 0) return '< 1s';
  const totalSecs = Math.round(ms / 1000);
  const h = Math.floor(totalSecs / 3600);
  const m = Math.floor((totalSecs % 3600) / 60);
  const s = totalSecs % 60;
  const parts: string[] = [];
  if (h > 0) parts.push(`${h}h`);
  if (m > 0) parts.push(`${m}m`);
  if (s > 0 || parts.length === 0) parts.push(`${s}s`);
  return parts.join(' ');
}

/** Estimate remaining time given start timestamp and current progress (0-100). */
function calcEta(createdAt: string, progressPct: number): string | null {
  if (progressPct < 0.3) return null; // not enough data yet
  const elapsedMs = Date.now() - new Date(createdAt).getTime();
  if (elapsedMs <= 0) return null;
  const remainingMs = (elapsedMs / progressPct) * (100 - progressPct);
  return formatDuration(remainingMs);
}

const POLL_INTERVAL_MS = 4000;

const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const getErrorMessage = (error: unknown, fallback: string): string =>
  error instanceof Error ? error.message : fallback;

export const BacktestList: React.FC<{ refreshTrigger?: number }> = ({ refreshTrigger = 0 }) => {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<RunStatus | 'ALL'>('ALL');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // First load blocks with spinner; subsequent refreshes stay non-blocking
    void loadBacktests(!hasLoadedOnce);
  }, [refreshTrigger]);

  // Auto-poll while any run is active
  useEffect(() => {
    const hasActive = runs.some((r) => {
      const s = normalizeStatus(r.status);
      return s === 'RUNNING' || s === 'PENDING';
    });

    if (hasActive) {
      if (!pollRef.current) {
        pollRef.current = setInterval(() => {
          loadBacktestsSilent();
        }, POLL_INTERVAL_MS);
      }
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [runs]);

  const fetchAllRuns = async (): Promise<BacktestRun[]> => {
    // Keep this fast for dashboard rendering: fetch the newest page only.
    // If needed later, we can add cursor-based pagination without blocking initial paint.
    const response = await api.listBacktests(0, 200);
    const raw = toRecord(response);
    const rawData = toRecord(raw.data);

    const pageRuns: BacktestRun[] = Array.isArray(rawData.backtests)
      ? (rawData.backtests as BacktestRun[])
      : Array.isArray(raw?.backtests)
        ? (raw.backtests as BacktestRun[])
        : Array.isArray(rawData.runs)
          ? (rawData.runs as BacktestRun[])
          : Array.isArray(raw?.runs)
            ? (raw.runs as BacktestRun[])
            : [];

    return pageRuns;
  };

  const loadBacktests = async (showBlockingLoader: boolean = true) => {
    if (showBlockingLoader) {
      setLoading(true);
    }
    setError(null);
    try {
      const runsPromise = fetchAllRuns();
      const timeoutPromise = new Promise<BacktestRun[]>((_, reject) => {
        setTimeout(() => reject(new Error('Timed out while loading backtest runs')), 15000);
      });

      const nextRuns = await Promise.race([runsPromise, timeoutPromise]);
      setRuns(nextRuns);
      setHasLoadedOnce(true);
    } catch (err: unknown) {
      console.error('❌ BacktestList: Error loading backtests:', err);
      setError(getErrorMessage(err, 'Failed to load backtests'));
      if (!hasLoadedOnce) {
        setRuns([]);
      }
    } finally {
      if (showBlockingLoader) {
        setLoading(false);
      }
    }
  };

  /** Silent refresh — keeps existing data visible while updating in background. */
  const loadBacktestsSilent = async () => {
    try {
      setRuns(await fetchAllRuns());
    } catch {
      // ignore transient errors during polling
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
              {filteredRuns.map((run) => {
                const normalizedStatus = normalizeStatus(run.status);
                const isActive = normalizedStatus === 'RUNNING' || normalizedStatus === 'PENDING';
                const progressPct = run.progress_pct ?? 0;
                const eta = isActive ? calcEta(run.created_at, progressPct) : null;

                return (
                  <React.Fragment key={run.run_id}>
                    {/* ── Main data row ─────────────────────────────────── */}
                    <tr
                      className={`border-b ${isActive ? 'border-slate-700/50' : 'border-slate-700'} hover:bg-slate-700`}
                    >
                      <td className="px-4 py-2 font-mono text-xs text-blue-400">
                        <span title={run.run_id}>{run.run_id.substring(0, 8)}…</span>
                        {run.name && (
                          <div className="text-slate-400 font-sans truncate max-w-28">
                            {run.name}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-2 text-sm">
                        {new Date(run.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2">
                        {run.start_date && run.end_date ? (
                          <>
                            {new Date(run.start_date).toLocaleDateString()} –{' '}
                            {new Date(run.end_date).toLocaleDateString()}
                          </>
                        ) : (
                          '–'
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
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${statusBadgeClass(normalizedStatus)}`}
                        >
                          {normalizedStatus === 'RUNNING' && (
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse shrink-0" />
                          )}
                          {normalizedStatus}
                          {isActive && progressPct > 0 && (
                            <span className="ml-1 opacity-80">{progressPct.toFixed(1)}%</span>
                          )}
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

                    {/* ── Progress sub-row (RUNNING / PENDING only) ─────── */}
                    {isActive && (
                      <tr className="border-b border-slate-700 bg-slate-900/40">
                        <td colSpan={10} className="px-4 pb-3 pt-1">
                          {/* Progress bar */}
                          <div className="flex items-center gap-2 mb-1.5">
                            <div className="flex-1 bg-slate-700 rounded-full h-1.5 overflow-hidden">
                              <div
                                className="h-1.5 rounded-full bg-blue-500 transition-all duration-700"
                                style={{ width: `${Math.min(progressPct, 100)}%` }}
                              />
                            </div>
                            <span className="text-xs text-blue-400 w-10 text-right shrink-0">
                              {progressPct > 0 ? `${progressPct.toFixed(1)}%` : '…'}
                            </span>
                          </div>

                          {/* Current pair + ETA */}
                          <div className="flex flex-wrap items-center gap-x-4 gap-y-0.5 text-xs text-slate-400">
                            {run.current_pair ? (
                              <span>
                                Scanning:{' '}
                                <span className="font-mono text-slate-200">{run.current_pair}</span>
                              </span>
                            ) : (
                              <span className="italic">Initialising…</span>
                            )}
                            {eta ? (
                              <span className="text-slate-500">
                                ETA: <span className="text-slate-300 font-medium">{eta}</span>
                              </span>
                            ) : progressPct > 0 ? (
                              <span className="text-slate-600 italic">Calculating ETA…</span>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
