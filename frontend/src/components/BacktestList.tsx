import { Inbox, SlidersHorizontal } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { classifyApiError } from '../api';

type RunStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'STALE' | 'TIMEOUT';

interface BacktestRun {
  id?: string;
  run_id: string;
  name?: string;
  start_date?: string;
  end_date?: string;
  status: string;
  progress_pct?: number;
  progress_percent?: number;
  progress?: number;
  current_pair?: string;
  current_task?: string;
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
  started_at?: string;
  completed_at?: string;
  finished_at?: string;
  deadline_at?: string;
  updated_at?: string;
  error?: string;
  error_message?: string;
  strategy_id?: number;
  strategy_name?: string;
  request?: Record<string, unknown>;
}

type FailureDiagnostic = {
  category: 'data' | 'network' | 'timeout' | 'config' | 'runtime' | 'unknown';
  summary: string;
  hint: string;
};

function normalizePercent(value: number | undefined | null): number | null {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return null;
  const numeric = Number(value);
  return Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
}

const normalizeStatus = (status?: string, run?: Partial<BacktestRun>): RunStatus => {
  const normalized = String(status || '')
    .trim()
    .toUpperCase();
  const progressPct =
    normalizePercent(run?.progress_pct ?? run?.progress_percent ?? run?.progress) ?? 0;
  const currentPair = String(run?.current_pair || '')
    .trim()
    .toLowerCase();
  const currentTask = String(run?.current_task || '')
    .trim()
    .toLowerCase();
  const hasMetrics =
    Number(run?.total_trades || 0) > 0 ||
    Number(run?.total_pnl || 0) !== 0 ||
    Number(run?.win_rate || 0) !== 0 ||
    Number(run?.sharpe_ratio || 0) !== 0;
  const hasWorkEvidence =
    progressPct > 0 ||
    hasMetrics ||
    (!!currentPair && !['pending', 'queued', 'complete'].includes(currentPair)) ||
    (!!currentTask && !['pending', 'queued', 'complete', 'created'].includes(currentTask));

  if (['CREATED', 'QUEUED', 'SCHEDULED', 'PENDING'].includes(normalized)) {
    if (String(run?.error_message || run?.error || '').trim()) return 'FAILED';
    if (progressPct >= 100 || currentPair === 'complete' || currentTask === 'complete') {
      return 'COMPLETED';
    }
    return hasWorkEvidence ? 'RUNNING' : 'PENDING';
  }
  if (['RUNNING', 'IN_PROGRESS', 'PROCESSING', 'ACTIVE'].includes(normalized)) return 'RUNNING';
  if (normalized === 'COMPLETED') return 'COMPLETED';
  if (normalized === 'FAILED') return 'FAILED';
  if (normalized === 'CANCELLED' || normalized === 'CANCELED') return 'CANCELLED';
  if (normalized === 'STALE' || normalized === 'STALLED') return 'STALE';
  if (normalized === 'TIMEOUT' || normalized === 'TIMED_OUT') return 'TIMEOUT';
  return 'PENDING';
};

const statusBadgeClass = (status: RunStatus): string => {
  switch (status) {
    case 'COMPLETED':
      return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
    case 'RUNNING':
      return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300';
    case 'FAILED':
    case 'TIMEOUT':
      return 'border-rose-500/30 bg-rose-500/10 text-rose-300';
    case 'CANCELLED':
      return 'border-slate-600/50 bg-slate-700/30 text-slate-300';
    case 'STALE':
      return 'border-orange-500/30 bg-orange-500/10 text-orange-300';
    default:
      return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
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
function calcEta(startedAt: string | undefined, progressPct: number): string | null {
  if (!startedAt || progressPct < 2) return null; // not enough stable data yet
  const elapsedMs = Date.now() - new Date(startedAt).getTime();
  if (elapsedMs <= 0) return null;
  const remainingMs = (elapsedMs / progressPct) * (100 - progressPct);
  if (!Number.isFinite(remainingMs) || remainingMs > 24 * 60 * 60 * 1000) return null;
  return formatDuration(remainingMs);
}

const POLL_INTERVAL_MS = 4000;
const MAX_POLL_INTERVAL_MS = 30000;

const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const getErrorMessage = (error: unknown, fallback: string): string =>
  error instanceof Error ? error.message : fallback;

const toUserFacingApiError = (error: unknown, fallback: string): string => {
  const classification = classifyApiError(error);
  if (classification.kind === 'transport') {
    return 'Unable to reach backend services. Check API availability or dev proxy configuration.';
  }
  if (classification.statusCode === 401) {
    return 'Session expired or unauthorized. Please sign in again.';
  }
  return getErrorMessage(error, fallback);
};

const formatUtcDateTime = (value?: string): string => {
  if (!value) return 'N/A';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'N/A';
  return parsed.toISOString().replace('T', ' ').replace('Z', ' UTC');
};

const formatUtcDate = (value?: string): string => {
  if (!value) return 'N/A';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'N/A';
  return parsed.toISOString().substring(0, 10);
};

const getLinkedStrategyId = (run: BacktestRun): number | null => {
  const direct = Number(run.strategy_id);
  if (Number.isInteger(direct) && direct > 0) return direct;
  const requestId = Number(run.request?.strategy_id);
  return Number.isInteger(requestId) && requestId > 0 ? requestId : null;
};

const classifyFailureDiagnostic = (run: BacktestRun): FailureDiagnostic => {
  const rawMessage = String(run.error_message || run.error || '').trim();
  const normalized = rawMessage.toLowerCase();

  if (!rawMessage) {
    return {
      category: 'unknown',
      summary: 'No explicit failure reason was returned by the backend.',
      hint: 'Open details and verify worker logs + API logs for the same run ID.',
    };
  }

  if (/timeout|timed out|deadline/.test(normalized)) {
    return {
      category: 'timeout',
      summary: rawMessage,
      hint: 'Try a shorter period or fewer pairs, then re-run and monitor progress cadence.',
    };
  }

  if (/network|connection|unreachable|refused|socket|dns/.test(normalized)) {
    return {
      category: 'network',
      summary: rawMessage,
      hint: 'Check API/worker connectivity and verify infrastructure services are healthy.',
    };
  }

  if (/insufficient|balance|margin|equity|collateral/.test(normalized)) {
    return {
      category: 'data',
      summary: rawMessage,
      hint: 'Review account state and ensure required balances/inputs are available.',
    };
  }

  if (/config|invalid|missing|required|parameter|env/.test(normalized)) {
    return {
      category: 'config',
      summary: rawMessage,
      hint: 'Validate bot configuration and required runtime variables before retrying.',
    };
  }

  if (/panic|exception|traceback|internal/.test(normalized)) {
    return {
      category: 'runtime',
      summary: rawMessage,
      hint: 'Inspect backend stack traces for this run and retry after applying the fix.',
    };
  }

  return {
    category: 'unknown',
    summary: rawMessage,
    hint: 'Open run details for deeper logs and execution context.',
  };
};

export const BacktestList: React.FC<{
  refreshTrigger?: number;
  runs?: BacktestRun[];
  loading?: boolean;
  error?: string | null;
}> = ({
  refreshTrigger = 0,
  runs: controlledRuns,
  loading: controlledLoading = false,
  error: controlledError = null,
}) => {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<RunStatus | 'ALL'>('ALL');
  const [pollFailures, setPollFailures] = useState(0);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isLoadingRef = useRef(false);
  const activeRequestIdRef = useRef(0);
  const pollFailureRef = useRef(0);
  const isControlled = Array.isArray(controlledRuns);
  const displayRuns = controlledRuns ?? runs;
  const displayLoading = isControlled ? controlledLoading : loading;
  const displayError = isControlled ? controlledError : error;

  useEffect(() => {
    if (isControlled) {
      return;
    }
    // First load blocks with spinner; subsequent refreshes stay non-blocking
    void loadBacktests(!hasLoadedOnce);
  }, [hasLoadedOnce, isControlled, refreshTrigger]);

  // Auto-poll while any run is active
  useEffect(() => {
    if (isControlled) {
      return;
    }

    const hasActive = runs.some((r) => {
      const s = normalizeStatus(r.status, r);
      return s === 'RUNNING' || s === 'PENDING';
    });

    const scheduleNextPoll = (delayMs: number) => {
      if (pollRef.current) {
        clearTimeout(pollRef.current);
      }
      pollRef.current = setTimeout(async () => {
        const ok = await loadBacktestsSilent();
        pollFailureRef.current = ok ? 0 : Math.min(pollFailureRef.current + 1, 4);
        setPollFailures(pollFailureRef.current);
        const nextDelay = ok
          ? POLL_INTERVAL_MS
          : Math.min(POLL_INTERVAL_MS * 2 ** pollFailureRef.current, MAX_POLL_INTERVAL_MS);
        scheduleNextPoll(nextDelay);
      }, delayMs);
    };

    if (hasActive) {
      if (!pollRef.current) {
        scheduleNextPoll(POLL_INTERVAL_MS);
      }
    } else {
      pollFailureRef.current = 0;
      setPollFailures(0);
      if (pollRef.current) {
        clearTimeout(pollRef.current);
        pollRef.current = null;
      }
    }

    return () => {
      if (pollRef.current) {
        clearTimeout(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [isControlled, runs]);

  const fetchAllRuns = async (): Promise<BacktestRun[]> => {
    // Keep this fast for dashboard rendering: fetch the newest page only.
    // If needed later, we can add cursor-based pagination without blocking initial paint.
    const response = await api.listBacktests(0, 50);
    const raw = toRecord(response);
    const rawData = toRecord(raw.data);

    return Array.isArray(rawData.backtests)
      ? (rawData.backtests as BacktestRun[])
      : Array.isArray(raw?.backtests)
        ? (raw.backtests as BacktestRun[])
        : Array.isArray(rawData.runs)
          ? (rawData.runs as BacktestRun[])
          : Array.isArray(raw?.runs)
            ? (raw.runs as BacktestRun[])
            : [];
  };

  const loadBacktests = async (showBlockingLoader: boolean = true) => {
    if (isLoadingRef.current) {
      return;
    }

    isLoadingRef.current = true;
    const requestId = activeRequestIdRef.current + 1;
    activeRequestIdRef.current = requestId;

    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    if (showBlockingLoader) {
      setLoading(true);
    }
    setError(null);
    try {
      const runsPromise = fetchAllRuns();
      const timeoutPromise = new Promise<BacktestRun[]>((_, reject) => {
        timeoutId = setTimeout(
          () => reject(new Error('Timed out while loading backtest runs')),
          25000
        );
      });

      const nextRuns = await Promise.race([runsPromise, timeoutPromise]);
      if (activeRequestIdRef.current !== requestId) {
        return;
      }
      setRuns(nextRuns);
      setHasLoadedOnce(true);
    } catch (err: unknown) {
      if (activeRequestIdRef.current !== requestId) {
        return;
      }
      console.error('❌ BacktestList: Error loading backtests:', err);
      setError(toUserFacingApiError(err, 'Failed to load backtests'));
      if (!hasLoadedOnce) {
        setRuns([]);
      }
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      if (activeRequestIdRef.current === requestId) {
        isLoadingRef.current = false;
      }
      if (showBlockingLoader) {
        setLoading(false);
      }
    }
  };

  /** Silent refresh — keeps existing data visible while updating in background. */
  const loadBacktestsSilent = async (): Promise<boolean> => {
    if (isLoadingRef.current) return true;
    try {
      setRuns(await fetchAllRuns());
      return true;
    } catch {
      // ignore transient errors during polling
      return false;
    }
  };

  if (displayLoading) {
    return (
      <div className="overflow-hidden rounded-lg border border-slate-700/80 bg-stone-950/45">
        <div className="flex items-center justify-between border-b border-slate-700 px-5 py-4">
          <div className="space-y-2">
            <div className="skeleton h-2.5 w-14 rounded" />
            <div className="skeleton h-4 w-32 rounded" />
          </div>
        </div>
        <div className="border-b border-slate-700/60 px-5 py-3">
          <div className="flex gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="skeleton h-6 w-16 rounded-lg" />
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-700 bg-stone-950/95">
              <tr>
                {[
                  'Run ID',
                  'Strategy',
                  'Started',
                  'Period',
                  'Trades',
                  'P&L',
                  'Win Rate',
                  'Sharpe',
                  'Max DD',
                  'Status',
                  '',
                ].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="border-b border-slate-700/40">
                  <td className="px-4 py-3">
                    <div className="skeleton h-3 w-20 rounded" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="skeleton h-3 w-32 rounded" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="skeleton h-3 w-28 rounded" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="skeleton mx-auto h-3 w-10 rounded" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="skeleton ml-auto h-3 w-16 rounded" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="skeleton ml-auto h-3 w-12 rounded" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="skeleton ml-auto h-3 w-10 rounded" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="skeleton ml-auto h-3 w-10 rounded" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="skeleton mx-auto h-5 w-20 rounded-full" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="skeleton mx-auto h-4 w-16 rounded" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  const statusCounts: Record<RunStatus, number> = {
    PENDING: 0,
    RUNNING: 0,
    COMPLETED: 0,
    FAILED: 0,
    CANCELLED: 0,
    STALE: 0,
    TIMEOUT: 0,
  };

  for (const run of displayRuns) {
    statusCounts[normalizeStatus(run.status, run)] += 1;
  }

  const filteredRuns = displayRuns.filter((run) => {
    if (statusFilter === 'ALL') return true;
    return normalizeStatus(run.status, run) === statusFilter;
  });

  const formatPct = (value: number | undefined | null) => {
    const normalized = normalizePercent(value);
    if (normalized === null) return 'N/A';
    return `${normalized.toFixed(1)}%`;
  };

  const maxDdValue = (run: BacktestRun) =>
    run.max_drawdown_pct !== undefined && run.max_drawdown_pct !== null
      ? run.max_drawdown_pct
      : run.max_drawdown;

  return (
    <div className="overflow-hidden rounded-lg border border-slate-700/80 bg-stone-950/45">
      <div className="flex flex-col gap-3 border-b border-slate-700 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase text-cyan-300">Run archive</p>
          <h3 className="mt-1 text-base font-semibold text-white">Backtest runs</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            {displayRuns.length} total run{displayRuns.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-stone-950 px-3 py-2 text-xs text-slate-400">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
          Soft refresh for active jobs
        </div>
      </div>

      <div className="border-b border-slate-700/60 px-5 py-3">
        <div className="flex flex-wrap gap-2">
          {(
            [
              ['ALL', displayRuns.length, 'All runs'],
              ['PENDING', statusCounts.PENDING, 'Pending'],
              ['RUNNING', statusCounts.RUNNING, 'Running'],
              ['COMPLETED', statusCounts.COMPLETED, 'Completed'],
              ['FAILED', statusCounts.FAILED, 'Failed'],
              ['CANCELLED', statusCounts.CANCELLED, 'Cancelled'],
              ['STALE', statusCounts.STALE, 'Stale'],
              ['TIMEOUT', statusCounts.TIMEOUT, 'Timeout'],
            ] as const
          ).map(([status, count, label]) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`rounded-lg border px-3 py-1 text-xs font-medium transition ${
                statusFilter === status
                  ? 'border-cyan-500/50 bg-cyan-500/15 text-white'
                  : 'border-slate-700 bg-stone-950/80 text-slate-300 hover:border-slate-600 hover:bg-stone-900'
              }`}
            >
              {label} ({count})
            </button>
          ))}
        </div>
      </div>

      {displayError && (
        <div className="mx-6 my-4 rounded-lg border border-red-700/60 bg-red-900/30 p-3 text-sm text-red-200">
          <span className="font-semibold">Failed to load runs.</span> {displayError} — check your
          connection or try refreshing the page.
        </div>
      )}

      {pollFailures > 0 && !displayError && (
        <div className="mx-6 my-4 flex items-center gap-2 rounded-lg border border-amber-600/60 bg-amber-900/25 p-3 text-xs text-amber-200">
          <span className="text-base">⚠️</span>
          <span>
            <span className="font-semibold">Live updates paused.</span> Data shown may be slightly
            behind.{' '}
            <button
              onClick={() => window.location.reload()}
              className="underline underline-offset-2 hover:text-amber-100 transition-colors"
            >
              Refresh
            </button>{' '}
            to restore live polling.
          </span>
        </div>
      )}

      {filteredRuns.length === 0 ? (
        <div className="px-6 py-16 text-center">
          {displayRuns.length === 0 ? (
            <div className="flex flex-col items-center gap-3">
              <div className="rounded-xl border border-slate-700/60 bg-slate-800/30 p-4">
                <Inbox className="h-8 w-8 text-slate-500" />
              </div>
              <p className="text-sm font-medium text-slate-300">No runs recorded yet</p>
              <p className="text-xs text-slate-500">
                Kick off a new backtest ticket to populate this list.
              </p>
              <a
                href="/backtests/new"
                className="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-300 transition-colors hover:bg-cyan-500/20"
              >
                New Backtest →
              </a>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <div className="rounded-xl border border-slate-700/60 bg-slate-800/30 p-4">
                <SlidersHorizontal className="h-8 w-8 text-slate-500" />
              </div>
              <p className="text-sm font-medium text-slate-300">
                No {statusFilter.toLowerCase()} runs
              </p>
              <p className="text-xs text-slate-500">Try a different filter to see results.</p>
              <button
                onClick={() => setStatusFilter('ALL')}
                className="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-slate-600 bg-slate-800/50 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-slate-500"
              >
                Show all runs
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-gray-300">
            <thead className="sticky top-0 z-10 border-b border-slate-700 bg-stone-950/95">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">
                  Run ID
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">
                  Strategy
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">
                  Started
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">
                  Period
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-slate-400 uppercase">
                  Trades
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-slate-400 uppercase">
                  P&L
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-slate-400 uppercase">
                  Win Rate
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-slate-400 uppercase">
                  Sharpe
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-slate-400 uppercase">
                  Max DD
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-slate-400 uppercase">
                  Status
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-slate-400 uppercase">
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map((run) => {
                const normalizedStatus = normalizeStatus(run.status, run);
                const isActive = normalizedStatus === 'RUNNING' || normalizedStatus === 'PENDING';
                const isFailed =
                  normalizedStatus === 'FAILED' ||
                  normalizedStatus === 'CANCELLED' ||
                  normalizedStatus === 'STALE' ||
                  normalizedStatus === 'TIMEOUT';
                const failureDiagnostic = isFailed ? classifyFailureDiagnostic(run) : null;
                const progressPct =
                  normalizePercent(run.progress_pct ?? run.progress_percent ?? run.progress) ?? 0;
                const eta = isActive
                  ? calcEta(run.started_at || run.created_at, progressPct)
                  : null;
                const linkedStrategyId = getLinkedStrategyId(run);

                return (
                  <React.Fragment key={run.run_id}>
                    {/* ── Main data row ─────────────────────────────────── */}
                    <tr
                      className={`border-b ${isActive ? 'border-slate-700/50' : 'border-slate-700'} hover:bg-stone-900/80`}
                    >
                      <td className="px-4 py-2 font-mono text-xs text-cyan-300">
                        <span title={run.run_id}>{run.run_id.substring(0, 8)}…</span>
                        {run.name && (
                          <div className="text-slate-400 font-sans truncate max-w-28">
                            {run.name}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        {linkedStrategyId ? (
                          <button
                            type="button"
                            onClick={() => navigate(`/strategies/${linkedStrategyId}/edit`)}
                            className="rounded-lg border border-cyan-500/25 bg-cyan-500/10 px-2 py-1 text-xs font-semibold text-cyan-200 transition hover:border-cyan-400/60"
                          >
                            {run.strategy_name || `Strategy #${linkedStrategyId}`}
                          </button>
                        ) : (
                          <span className="text-xs text-slate-500">Manual</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-sm">{formatUtcDateTime(run.created_at)}</td>
                      <td className="px-4 py-2">
                        {run.start_date && run.end_date ? (
                          <>
                            {formatUtcDate(run.start_date)} - {formatUtcDate(run.end_date)}
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
                          className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs font-medium ${statusBadgeClass(normalizedStatus)}`}
                        >
                          {normalizedStatus === 'RUNNING' && (
                            <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-cyan-400" />
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
                          className="font-semibold text-cyan-300 underline hover:text-cyan-200"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>

                    {/* ── Progress sub-row (RUNNING / PENDING only) ─────── */}
                    {isActive && (
                      <tr className="border-b border-slate-700 bg-stone-950/55">
                        <td colSpan={11} className="px-4 pb-3 pt-1">
                          {/* Progress bar */}
                          <div className="flex items-center gap-2 mb-1.5">
                            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-700">
                              <div
                                className="h-1.5 rounded-full bg-cyan-500 transition-all duration-700"
                                style={{ width: `${Math.min(progressPct, 100)}%` }}
                              />
                            </div>
                            <span className="w-10 shrink-0 text-right text-xs text-cyan-300">
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

                    {isFailed && failureDiagnostic && (
                      <tr className="border-b border-slate-700 bg-rose-950/20">
                        <td colSpan={11} className="px-4 pb-3 pt-2">
                          <div className="flex flex-wrap items-center gap-3 text-xs">
                            <span className="rounded-lg border border-rose-700/60 bg-rose-900/40 px-2 py-0.5 uppercase text-rose-200">
                              {failureDiagnostic.category}
                            </span>
                            <span className="text-rose-100">{failureDiagnostic.summary}</span>
                          </div>
                          <p className="mt-2 text-xs text-slate-300">
                            <span className="font-semibold text-slate-200">Next step:</span>{' '}
                            {failureDiagnostic.hint}
                          </p>
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
