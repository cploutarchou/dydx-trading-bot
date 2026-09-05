import { Inbox, SlidersHorizontal } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { classifyApiError } from '../api';
import { enhancedApiClient } from '../api/enhancedClient';
import { useNow } from '../hooks/useNow';
import { getEnvelopeList, getEnvelopeValue, toApiRecord } from '../api/normalizers';

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
  category:
    'data' | 'network' | 'timeout' | 'config' | 'runtime' | 'interruption' | 'capacity' | 'unknown';
  summary: string;
  hint: string;
};

type RetryPressureBadge = {
  score: number;
  label: 'low' | 'moderate' | 'high';
  className: string;
};

function normalizePercent(value: number | undefined | null): number | null {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return null;
  const numeric = Number(value);
  return Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
}

const optionalPercent = (value: number | undefined | null): number | undefined =>
  normalizePercent(value) ?? undefined;

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
const LIVE_SYNC_STALE_AFTER_MS = 30000;

const toRecord = toApiRecord;

const toFiniteNumber = (value: unknown, fallback = 0): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const clampPct = (value: number): number => Math.max(0, Math.min(100, value));

const deriveRetryPressureBadge = (run: BacktestRun): RetryPressureBadge | null => {
  const request = toRecord(run.request);
  const taskContext = toRecord(request._task_context);
  const metadata = toRecord(taskContext.metadata);
  const telemetry = toRecord(metadata.history_fetch_telemetry);

  if (Object.keys(telemetry).length === 0) {
    return null;
  }

  const totalWindows = toFiniteNumber(telemetry.total_windows, 0);
  const totalRetries = toFiniteNumber(telemetry.total_retries, 0);
  const totalFailedWindows = toFiniteNumber(telemetry.total_failed_windows, 0);
  const avgBackoffPerRetrySeconds = toFiniteNumber(telemetry.avg_backoff_per_retry_seconds, 0);

  const retryRatePct = totalWindows > 0 ? (totalRetries / totalWindows) * 100 : 0;
  const failedRatePct = totalWindows > 0 ? (totalFailedWindows / totalWindows) * 100 : 0;
  const score = clampPct(
    retryRatePct * 0.55 + failedRatePct * 0.9 + Math.min(12, avgBackoffPerRetrySeconds * 3)
  );

  if (score < 30) {
    return {
      score,
      label: 'low',
      className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    };
  }

  if (score < 60) {
    return {
      score,
      label: 'moderate',
      className: 'border-amber-500/35 bg-amber-500/10 text-amber-300',
    };
  }

  return {
    score,
    label: 'high',
    className: 'border-rose-500/35 bg-rose-500/10 text-rose-300',
  };
};

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

const formatLiveSyncAge = (value?: string): string | null => {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  const deltaMs = Date.now() - parsed.getTime();
  if (deltaMs < 0) return 'just now';
  const sec = Math.floor(deltaMs / 1000);
  if (sec < 5) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  return `${hr}h ago`;
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

  if (
    /interrupted|reload|restart|orphaned|worker task may have been interrupted/.test(normalized)
  ) {
    return {
      category: 'interruption',
      summary: rawMessage,
      hint: 'This usually means worker/API lifecycle interruption. Verify worker uptime and use retry/restart for the run.',
    };
  }

  if (
    /capacity|saturated|too many active|queue depth|admission|429|rate limit|retry-after/.test(
      normalized
    )
  ) {
    return {
      category: 'capacity',
      summary: rawMessage,
      hint: 'System concurrency limits were reached. Wait for active runs to finish or reduce parallel submissions.',
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
  const [showHighPressureOnly, setShowHighPressureOnly] = useState(false);
  const [pollFailures, setPollFailures] = useState(0);
  const [liveSyncMeta, setLiveSyncMeta] = useState<{
    syncedRuns: number;
    updatedAt: string | null;
  }>({
    syncedRuns: 0,
    updatedAt: null,
  });
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const nowTs = useNow();
  const isLoadingRef = useRef(false);
  const activeRequestIdRef = useRef(0);
  const pollFailureRef = useRef(0);
  const isControlled = Array.isArray(controlledRuns);
  const displayRuns = controlledRuns ?? runs;
  const displayLoading = isControlled ? controlledLoading : loading;
  const displayError = isControlled ? controlledError : error;

  const fetchAllRuns = async (): Promise<BacktestRun[]> => {
    // Keep this fast for dashboard rendering: fetch the newest page only.
    // If needed later, we can add cursor-based pagination without blocking initial paint.
    const response = await api.listBacktests(0, 50);
    const runs = getEnvelopeList<BacktestRun>(response, ['backtests', 'runs']);

    const activeRuns = runs
      .filter((run) => {
        const status = normalizeStatus(run.status, run);
        return status === 'RUNNING' || status === 'PENDING';
      })
      .slice(0, 12);

    if (activeRuns.length === 0) {
      setLiveSyncMeta({ syncedRuns: 0, updatedAt: null });
      return runs;
    }

    const statusSettled = await Promise.allSettled(
      activeRuns.map(async (run) => {
        const statusResponse = await enhancedApiClient.getBacktestStatus(run.run_id);
        const payload = toRecord(statusResponse);

        return {
          run_id: run.run_id,
          status: String(getEnvelopeValue(payload, 'status') ?? run.status),
          progress_pct: optionalPercent(
            Number(
              getEnvelopeValue(payload, 'progress_pct') ??
                getEnvelopeValue(payload, 'progress_percent') ??
                getEnvelopeValue(payload, 'progress')
            )
          ),
          progress_percent: optionalPercent(
            Number(
              getEnvelopeValue(payload, 'progress_percent') ??
                getEnvelopeValue(payload, 'progress_pct') ??
                getEnvelopeValue(payload, 'progress')
            )
          ),
          progress: optionalPercent(
            Number(
              getEnvelopeValue(payload, 'progress') ??
                getEnvelopeValue(payload, 'progress_pct') ??
                getEnvelopeValue(payload, 'progress_percent')
            )
          ),
          current_pair:
            typeof getEnvelopeValue(payload, 'current_pair') === 'string'
              ? String(getEnvelopeValue(payload, 'current_pair'))
              : run.current_pair,
          current_task:
            typeof getEnvelopeValue(payload, 'current_task') === 'string'
              ? String(getEnvelopeValue(payload, 'current_task'))
              : run.current_task,
          updated_at:
            typeof getEnvelopeValue(payload, 'updated_at') === 'string'
              ? String(getEnvelopeValue(payload, 'updated_at'))
              : run.updated_at,
          error:
            typeof getEnvelopeValue(payload, 'error') === 'string'
              ? String(getEnvelopeValue(payload, 'error'))
              : run.error,
          error_message:
            typeof getEnvelopeValue(payload, 'error_message') === 'string'
              ? String(getEnvelopeValue(payload, 'error_message'))
              : run.error_message,
        } satisfies Partial<BacktestRun> & { run_id: string };
      })
    );

    const liveByRunId = new Map<string, Partial<BacktestRun>>();
    statusSettled.forEach((result) => {
      if (result.status !== 'fulfilled') {
        return;
      }
      liveByRunId.set(result.value.run_id, result.value);
    });

    setLiveSyncMeta({
      syncedRuns: liveByRunId.size,
      updatedAt: liveByRunId.size > 0 ? new Date().toISOString() : null,
    });

    return runs.map((run) => ({
      ...run,
      ...(liveByRunId.get(run.run_id) ?? {}),
    }));
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
        <div className="scroll-shadow-x overflow-x-auto">
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

  const highPressureRunCount = displayRuns.filter(
    (run) => deriveRetryPressureBadge(run)?.label === 'high'
  ).length;

  const filteredRuns = displayRuns.filter((run) => {
    const statusMatches =
      statusFilter === 'ALL' || normalizeStatus(run.status, run) === statusFilter;
    if (!statusMatches) return false;
    if (!showHighPressureOnly) return true;
    return deriveRetryPressureBadge(run)?.label === 'high';
  });
  const liveSyncAge = formatLiveSyncAge(liveSyncMeta.updatedAt ?? undefined);
  const liveSyncHealthy = liveSyncMeta.syncedRuns > 0;
  const liveSyncStale = (() => {
    if (!liveSyncMeta.updatedAt || !liveSyncHealthy) return false;
    const ageMs = nowTs - new Date(liveSyncMeta.updatedAt).getTime();
    return Number.isFinite(ageMs) && ageMs > LIVE_SYNC_STALE_AFTER_MS;
  })();

  const formatPct = (value: number | undefined | null) => {
    const normalized = normalizePercent(value);
    if (normalized === null) return 'N/A';
    return `${normalized.toFixed(1)}%`;
  };

  const maxDdValue = (run: BacktestRun) =>
    run.max_drawdown_pct !== undefined && run.max_drawdown_pct !== null
      ? run.max_drawdown_pct
      : run.max_drawdown;

  const handleManualRefresh = () => {
    pollFailureRef.current = 0;
    setPollFailures(0);
    if (isControlled) {
      return;
    }
    void loadBacktests(false);
  };

  const handleArchiveKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }

    const target = event.target as HTMLElement | null;
    const tagName = target?.tagName?.toLowerCase();
    const isEditableTarget =
      tagName === 'input' ||
      tagName === 'textarea' ||
      tagName === 'select' ||
      tagName === 'button' ||
      target?.isContentEditable;

    if (isEditableTarget) {
      return;
    }

    if (event.key.toLowerCase() === 'h') {
      event.preventDefault();
      setShowHighPressureOnly((value) => !value);
    }
  };

  return (
    // Keyboard shortcuts (archive/cancel) on the region are deliberate;
    // the rule reads any listener on a non-interactive role as a smell.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <div
      // Deliberate focusable region: the archive exposes keyboard shortcuts
      // (archive/cancel) on the container itself.
      role="region"
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
      onKeyDown={handleArchiveKeyDown}
      aria-label="Backtest run archive"
      className="overflow-hidden rounded-lg border border-slate-700/80 bg-stone-950/45 focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
    >
      <div className="flex flex-col gap-3 border-b border-slate-700 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase text-cyan-300">Run archive</p>
          <h3 className="mt-1 text-base font-semibold text-white">Backtest runs</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            {displayRuns.length} total run{displayRuns.length !== 1 ? 's' : ''}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            Tip: press H to toggle high pressure filter
          </p>
        </div>
        <div className="inline-flex flex-wrap items-center gap-2 rounded-lg border border-slate-700 bg-stone-950 px-3 py-2 text-xs text-slate-400">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              liveSyncHealthy ? (liveSyncStale ? 'bg-amber-300' : 'bg-emerald-300') : 'bg-cyan-300'
            }`}
          />
          <span>Soft refresh for active jobs</span>
          <span className="text-slate-600">•</span>
          <span
            className={
              liveSyncHealthy
                ? liveSyncStale
                  ? 'text-amber-300'
                  : 'text-emerald-300'
                : 'text-slate-500'
            }
            title={
              liveSyncHealthy
                ? 'Active rows are merged with live list status values.'
                : 'No active rows are currently receiving live status merges.'
            }
          >
            {liveSyncHealthy
              ? `${liveSyncStale ? 'Live sync stale' : 'Live synced'} (${liveSyncMeta.syncedRuns})${liveSyncAge ? ` · ${liveSyncAge}` : ''}`
              : 'Live sync idle'}
          </span>
        </div>
      </div>

      <div className="border-b border-slate-700/60 px-5 py-3">
        <div
          className="flex flex-wrap items-center gap-2"
          role="toolbar"
          aria-label="Backtest status filters"
        >
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
              type="button"
              onClick={() => setStatusFilter(status)}
              aria-pressed={statusFilter === status}
              className={`rounded-lg border px-3 py-1 text-xs font-medium transition ${
                statusFilter === status
                  ? 'border-cyan-500/50 bg-cyan-500/15 text-white'
                  : 'border-slate-700 bg-stone-950/80 text-slate-300 hover:border-slate-600 hover:bg-stone-900'
              }`}
            >
              {label} ({count})
            </button>
          ))}

          <button
            type="button"
            onClick={() => setShowHighPressureOnly((value) => !value)}
            aria-pressed={showHighPressureOnly}
            className={`rounded-lg border px-3 py-1 text-xs font-medium transition ${
              showHighPressureOnly
                ? 'border-rose-500/50 bg-rose-500/15 text-rose-200'
                : 'border-slate-700 bg-stone-950/80 text-slate-300 hover:border-slate-600 hover:bg-stone-900'
            }`}
            title="Filter to runs with high retry-pressure telemetry"
          >
            High pressure only ({highPressureRunCount})
          </button>
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
              type="button"
              onClick={handleManualRefresh}
              className="underline underline-offset-2 hover:text-amber-100 transition-colors"
            >
              Retry sync
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
                {showHighPressureOnly
                  ? `No high-pressure ${statusFilter === 'ALL' ? '' : statusFilter.toLowerCase() + ' '}runs`
                  : `No ${statusFilter.toLowerCase()} runs`}
              </p>
              <p className="text-xs text-slate-500">Try a different filter to see results.</p>
              <button
                onClick={() => {
                  setStatusFilter('ALL');
                  setShowHighPressureOnly(false);
                }}
                className="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-slate-600 bg-slate-800/50 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-slate-500"
              >
                Show all runs
              </button>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="space-y-3 p-4 md:hidden">
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
              const eta = isActive ? calcEta(run.started_at || run.created_at, progressPct) : null;
              const linkedStrategyId = getLinkedStrategyId(run);
              const retryPressureBadge = deriveRetryPressureBadge(run);

              return (
                <article
                  key={run.run_id}
                  className="rounded-xl border border-slate-700/70 bg-slate-950/55 p-4"
                  aria-label={`Backtest ${run.name || run.run_id}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-xs text-cyan-300" title={run.run_id}>
                        {run.run_id}
                      </p>
                      {run.name && (
                        <p className="mt-1 truncate text-sm font-semibold text-white">{run.name}</p>
                      )}
                      <p className="mt-1 text-xs text-slate-500">
                        Started {formatUtcDateTime(run.created_at)}
                      </p>
                    </div>
                    <span
                      className={`inline-flex shrink-0 items-center gap-1 rounded-lg border px-2 py-1 text-xs font-medium ${statusBadgeClass(normalizedStatus)}`}
                    >
                      {normalizedStatus === 'RUNNING' && (
                        <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-cyan-400" />
                      )}
                      {normalizedStatus}
                    </span>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-slate-500">Strategy</p>
                      {linkedStrategyId ? (
                        <button
                          type="button"
                          onClick={() => navigate(`/strategies/${linkedStrategyId}/edit`)}
                          className="mt-1 max-w-full truncate rounded-lg border border-cyan-500/25 bg-cyan-500/10 px-2 py-1 text-xs font-semibold text-cyan-200 transition hover:border-cyan-400/60"
                        >
                          {run.strategy_name || `Strategy #${linkedStrategyId}`}
                        </button>
                      ) : (
                        <p className="mt-1 text-xs text-slate-300">Manual</p>
                      )}
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Period</p>
                      <p className="mt-1 text-xs text-slate-300">
                        {run.start_date && run.end_date
                          ? `${formatUtcDate(run.start_date)} - ${formatUtcDate(run.end_date)}`
                          : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">P&L</p>
                      <p
                        className={`mt-1 font-semibold ${run.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
                      >
                        ${run.total_pnl.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Risk</p>
                      <p className="mt-1 text-slate-200">
                        DD {formatPct(maxDdValue(run))} · WR {formatPct(run.win_rate)}
                      </p>
                    </div>
                  </div>

                  {retryPressureBadge && (
                    <span
                      className={`mt-3 inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${retryPressureBadge.className}`}
                      title={`Retry pressure score ${retryPressureBadge.score.toFixed(1)} / 100`}
                    >
                      pressure: {retryPressureBadge.label}
                    </span>
                  )}

                  {isActive && (
                    <div className="mt-4">
                      <div className="mb-1.5 flex items-center justify-between text-xs text-slate-400">
                        <span>
                          {run.current_pair ? `Scanning ${run.current_pair}` : 'Initialising'}
                        </span>
                        <span>{progressPct > 0 ? `${progressPct.toFixed(1)}%` : '...'}</span>
                      </div>
                      <div
                        className="h-1.5 overflow-hidden rounded-full bg-slate-700"
                        role="progressbar"
                        aria-label={`Backtest ${run.run_id} progress`}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={Math.round(progressPct)}
                      >
                        <div
                          className="h-1.5 rounded-full bg-cyan-500 transition-all duration-700"
                          style={{ width: `${Math.min(progressPct, 100)}%` }}
                        />
                      </div>
                      {eta && <p className="mt-2 text-xs text-slate-500">ETA: {eta}</p>}
                    </div>
                  )}

                  {failureDiagnostic && (
                    <div className="mt-4 rounded-lg border border-rose-700/60 bg-rose-900/25 p-3 text-xs">
                      <p className="font-semibold uppercase text-rose-200">
                        {failureDiagnostic.category}
                      </p>
                      <p className="mt-1 text-rose-100">{failureDiagnostic.summary}</p>
                      <p className="mt-2 text-slate-300">
                        <span className="font-semibold text-slate-200">Next step:</span>{' '}
                        {failureDiagnostic.hint}
                      </p>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => navigate(`/backtest/${run.run_id}`)}
                    className="mt-4 w-full rounded-lg border border-cyan-500/35 bg-cyan-500/10 px-3 py-2 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-500/20"
                  >
                    View Details
                  </button>
                </article>
              );
            })}
          </div>

          <div className="scroll-shadow-x hidden overflow-x-auto md:block">
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
                  const retryPressureBadge = deriveRetryPressureBadge(run);

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
                          <div className="flex flex-col items-center gap-1">
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
                            {retryPressureBadge && (
                              <span
                                className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${retryPressureBadge.className}`}
                                title={`Retry pressure score ${retryPressureBadge.score.toFixed(1)} / 100`}
                              >
                                pressure: {retryPressureBadge.label}
                              </span>
                            )}
                          </div>
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
                              <div
                                className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-700"
                                role="progressbar"
                                aria-label={`Backtest ${run.run_id} progress`}
                                aria-valuemin={0}
                                aria-valuemax={100}
                                aria-valuenow={Math.round(progressPct)}
                              >
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
                                  <span className="font-mono text-slate-200">
                                    {run.current_pair}
                                  </span>
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
        </>
      )}
    </div>
  );
};
