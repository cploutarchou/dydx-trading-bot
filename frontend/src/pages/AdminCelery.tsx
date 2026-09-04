import {
    Activity,
    AlertTriangle,
    Ban,
    CheckCircle2,
    Clock3,
    Filter,
    RefreshCw,
    RotateCcw,
    Server,
    Timer,
    Zap,
} from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import api, {
    type CeleryHealthResponse,
    type CeleryQueuesResponse,
    type CeleryTask,
    type CeleryTasksResponse,
    type CeleryWorkersResponse,
} from '../api';
import { useAuthStore } from '../store/auth';

const ADMIN_ROLES = new Set(['admin', 'super_admin', 'backoffice_admin']);
const ACTIVE_STATES = new Set(['STARTED', 'PROGRESS', 'PENDING', 'RETRY', 'SCHEDULED']);
const FAILURE_STATES = new Set(['FAILURE', 'REVOKED', 'TIMEOUT', 'TIMED_OUT', 'STALE']);
const SUCCESS_STATES = new Set(['SUCCESS', 'COMPLETED']);
const STALE_TASK_SECONDS = 15 * 60;
const DEFAULT_QUEUE_ANOMALY_THRESHOLD = 25;

const statusTone = (status?: string) => {
  const normalized = String(status || '').toUpperCase();
  if (normalized === 'SUCCESS' || normalized === 'COMPLETED')
    return 'text-emerald-300 bg-emerald-500/10';
  if (normalized === 'FAILURE' || normalized === 'REVOKED') return 'text-rose-300 bg-rose-500/10';
  if (normalized === 'STARTED' || normalized === 'PROGRESS') return 'text-sky-300 bg-sky-500/10';
  if (normalized === 'RETRY') return 'text-amber-300 bg-amber-500/10';
  return 'text-slate-300 bg-slate-700/70';
};

const formatDate = (value?: string | null) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

const progressValue = (task: CeleryTask) => {
  const raw = task.progress_percent;
  if (typeof raw !== 'number' || Number.isNaN(raw)) return 0;
  return Math.max(0, Math.min(100, raw));
};

const toFiniteNumber = (value: unknown): number | null => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const taskStatus = (task: CeleryTask): string => String(task.status || '').toUpperCase();

const taskUpdatedAt = (task: CeleryTask): string | null =>
  task.finished_at || task.started_at || task.created_at || null;

const taskRuntimeSeconds = (task: CeleryTask): number | null => {
  const explicit = toFiniteNumber(task.runtime_seconds);
  if (explicit !== null) {
    return Math.max(0, explicit);
  }

  if (!task.started_at) {
    return null;
  }

  const startTs = new Date(task.started_at).getTime();
  if (!Number.isFinite(startTs)) {
    return null;
  }
  const finishTs = task.finished_at ? new Date(task.finished_at).getTime() : Date.now();
  if (!Number.isFinite(finishTs)) {
    return null;
  }

  return Math.max(0, (finishTs - startTs) / 1000);
};

const isStaleActiveTask = (task: CeleryTask): boolean => {
  if (!ACTIVE_STATES.has(taskStatus(task))) {
    return false;
  }
  const runtime = taskRuntimeSeconds(task);
  return runtime !== null && runtime >= STALE_TASK_SECONDS;
};

const anomalyReasonsForTask = (
  task: CeleryTask,
  overloadedQueues: Set<string>
): Array<'failure' | 'stale-active' | 'queue-pressure'> => {
  const reasons: Array<'failure' | 'stale-active' | 'queue-pressure'> = [];
  const status = taskStatus(task);
  if (FAILURE_STATES.has(status)) {
    reasons.push('failure');
  }
  if (isStaleActiveTask(task)) {
    reasons.push('stale-active');
  }
  const queueName = String(task.queue || '').trim();
  if (queueName && overloadedQueues.has(queueName)) {
    reasons.push('queue-pressure');
  }
  return reasons;
};

const formatDuration = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) {
    return '—';
  }
  if (seconds < 1) return '<1s';
  const rounded = Math.round(seconds);
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const secs = rounded % 60;
  const parts: string[] = [];
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
  return parts.join(' ');
};

const formatRelativeAge = (value?: string | null): string => {
  if (!value) return 'never';
  const parsed = new Date(value).getTime();
  if (!Number.isFinite(parsed)) return 'unknown';
  const delta = Math.max(0, Date.now() - parsed);
  const sec = Math.round(delta / 1000);
  if (sec < 5) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  return `${day}d ago`;
};

type WorkerSummary = {
  hostname: string;
  status: string;
  activeTasks: number;
  registeredTasks: number;
  queueCount: number;
};

const toWorkerSummary = (worker: Record<string, unknown>): WorkerSummary => {
  const load =
    worker.load && typeof worker.load === 'object' ? (worker.load as Record<string, unknown>) : {};
  const activeTasks = toFiniteNumber(load.active_tasks) ?? 0;
  const queueCount = Array.isArray(worker.queues) ? worker.queues.length : 0;
  const registeredTasks = Array.isArray(worker.registered_tasks)
    ? worker.registered_tasks.length
    : 0;

  return {
    hostname: String(worker.hostname || worker.name || 'unknown-worker'),
    status: String(worker.status || 'unknown'),
    activeTasks: Math.max(0, activeTasks),
    queueCount,
    registeredTasks,
  };
};

export const AdminCeleryPage: React.FC = () => {
  const user = useAuthStore((state) => state.user);
  const flowerUrl = String(import.meta.env.VITE_FLOWER_URL || '').trim();
  const [tasks, setTasks] = useState<CeleryTask[]>([]);
  const [health, setHealth] = useState<CeleryHealthResponse | null>(null);
  const [workers, setWorkers] = useState<CeleryWorkersResponse | null>(null);
  const [queues, setQueues] = useState<CeleryQueuesResponse | null>(null);
  const [selectedTask, setSelectedTask] = useState<CeleryTask | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [taskNameFilter, setTaskNameFilter] = useState('');
  const [queueFilter, setQueueFilter] = useState('');
  const [environmentFilter, setEnvironmentFilter] = useState('');
  const [showAnomaliesOnly, setShowAnomaliesOnly] = useState(false);
  const [queueAnomalyThreshold, setQueueAnomalyThreshold] = useState<number>(
    DEFAULT_QUEUE_ANOMALY_THRESHOLD
  );
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastLoadedAt, setLastLoadedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isStrictAdmin = Boolean(user?.is_admin) || ADMIN_ROLES.has(String(user?.role || ''));

  const load = useCallback(async () => {
    if (!isStrictAdmin) return;
    setLoading(true);
    setError(null);
    try {
      const [tasksResponse, healthResponse, workersResponse, queuesResponse] = await Promise.all([
        api.listCeleryTasks({
          ...(statusFilter ? { status: statusFilter } : {}),
          ...(taskNameFilter ? { task_name: taskNameFilter.trim() } : {}),
          ...(queueFilter ? { queue: queueFilter.trim() } : {}),
          ...(environmentFilter ? { environment: environmentFilter.trim() } : {}),
        }),
        api.getCeleryHealth(),
        api.getCeleryWorkers(),
        api.getCeleryQueues(),
      ]);
      const taskData = (tasksResponse.data || {}) as CeleryTasksResponse;
      setTasks(Array.isArray(taskData.tasks) ? taskData.tasks : []);
      setHealth((healthResponse.data || null) as CeleryHealthResponse | null);
      setWorkers((workersResponse.data || null) as CeleryWorkersResponse | null);
      setQueues((queuesResponse.data || null) as CeleryQueuesResponse | null);
      setLastLoadedAt(new Date().toISOString());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load Celery telemetry');
    } finally {
      setLoading(false);
    }
  }, [environmentFilter, isStrictAdmin, queueFilter, statusFilter, taskNameFilter]);

  useEffect(() => {
    void load();
    if (!autoRefresh) {
      return;
    }
    const timer = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, load]);

  const sortedTasks = useMemo(
    () =>
      [...tasks].sort((a, b) =>
        String(taskUpdatedAt(b) || '').localeCompare(String(taskUpdatedAt(a) || ''))
      ),
    [tasks]
  );

  const failedTasks = useMemo(
    () => sortedTasks.filter((task) => FAILURE_STATES.has(taskStatus(task))),
    [sortedTasks]
  );
  const activeTasks = useMemo(
    () => sortedTasks.filter((task) => ACTIVE_STATES.has(taskStatus(task))),
    [sortedTasks]
  );
  const succeededTasks = useMemo(
    () => sortedTasks.filter((task) => SUCCESS_STATES.has(taskStatus(task))),
    [sortedTasks]
  );

  const staleActiveTasks = useMemo(
    () => activeTasks.filter((task) => isStaleActiveTask(task)),
    [activeTasks]
  );

  const statusCounts = useMemo(() => {
    const map = new Map<string, number>();
    sortedTasks.forEach((task) => {
      const status = taskStatus(task) || 'UNKNOWN';
      map.set(status, (map.get(status) || 0) + 1);
    });
    return Array.from(map.entries()).sort((left, right) => right[1] - left[1]);
  }, [sortedTasks]);

  const successRate = useMemo(() => {
    const denominator = succeededTasks.length + failedTasks.length;
    if (denominator <= 0) return null;
    return (succeededTasks.length / denominator) * 100;
  }, [failedTasks.length, succeededTasks.length]);

  const queueInsights = useMemo(() => {
    const rows = Array.isArray(queues?.queues)
      ? queues.queues.map((queue) => ({
          name: queue.name,
          length: toFiniteNumber(queue.length) ?? 0,
        }))
      : [];
    const totalBacklog = rows.reduce((sum, row) => sum + Math.max(0, row.length), 0);
    const hottest = [...rows].sort((left, right) => right.length - left.length)[0] || null;
    return {
      rows: rows.sort((left, right) => right.length - left.length),
      totalBacklog,
      hottest,
    };
  }, [queues?.queues]);

  const anomalousQueueNames = useMemo(() => {
    return new Set(
      queueInsights.rows
        .filter((queue) => queue.length >= queueAnomalyThreshold)
        .map((queue) => queue.name)
    );
  }, [queueAnomalyThreshold, queueInsights.rows]);

  const workerSummaries = useMemo(() => {
    const list = Array.isArray(workers?.workers)
      ? workers.workers.map((worker) => toWorkerSummary(worker))
      : [];
    return list.sort((left, right) => right.activeTasks - left.activeTasks);
  }, [workers?.workers]);

  const failureHotspots = useMemo(() => {
    const counter = new Map<string, number>();
    failedTasks.forEach((task) => {
      const raw =
        String(task.error_code || '').trim() ||
        String(task.error_message || '')
          .split('\n')[0]?.trim() ||
        'unknown';
      const key = raw.length > 80 ? `${raw.slice(0, 77)}...` : raw;
      counter.set(key, (counter.get(key) || 0) + 1);
    });
    return Array.from(counter.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((left, right) => right.count - left.count)
      .slice(0, 5);
  }, [failedTasks]);

  const anomalousTasks = useMemo(() => {
    return sortedTasks.filter((task) => {
      const status = taskStatus(task);
      if (FAILURE_STATES.has(status)) return true;
      if (isStaleActiveTask(task)) return true;
      const queueName = String(task.queue || '').trim();
      if (queueName && anomalousQueueNames.has(queueName)) return true;
      return false;
    });
  }, [anomalousQueueNames, sortedTasks]);

  const visibleTasks = showAnomaliesOnly ? anomalousTasks : sortedTasks;

  const revoke = async (task: CeleryTask) => {
    if (!window.confirm(`Revoke Celery task ${task.task_id}?`)) return;
    await api.revokeCeleryTask(task.task_id, false);
    await load();
  };

  const retry = async (task: CeleryTask) => {
    if (!window.confirm(`Retry failed Celery task ${task.task_id}?`)) return;
    await api.retryCeleryTask(task.task_id);
    await load();
  };

  if (!isStrictAdmin) {
    return (
      <div className="min-h-[60vh] px-6 py-8 text-slate-200">
        <h2 className="text-2xl font-semibold">Forbidden</h2>
        <p className="mt-2 text-sm text-slate-400">Admin access is required.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-5 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <div className="flex flex-col gap-3 border-b border-slate-800 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-normal">Celery Operations</h2>
            <p className="mt-1 text-sm text-slate-400">
              Admin task inspection, worker health, queue pressure, and faster failure triage.
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Last sync {formatRelativeAge(lastLoadedAt)}{' '}
              {lastLoadedAt ? `· ${formatDate(lastLoadedAt)}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {flowerUrl && (
              <a
                href={flowerUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-10 items-center gap-2 rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-100 hover:bg-slate-800"
              >
                <Server className="h-4 w-4" />
                Flower
              </a>
            )}
            <button
              type="button"
              onClick={() => setAutoRefresh((value) => !value)}
              className={`inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm transition ${
                autoRefresh
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                  : 'border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800'
              }`}
            >
              <Zap className="h-4 w-4" />
              {autoRefresh ? 'Auto refresh on' : 'Auto refresh off'}
            </button>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
            >
              <option value="">All states</option>
              <option value="PENDING">Pending</option>
              <option value="STARTED">Started</option>
              <option value="PROGRESS">Progress</option>
              <option value="SUCCESS">Success</option>
              <option value="FAILURE">Failure</option>
              <option value="REVOKED">Revoked</option>
            </select>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex h-10 items-center gap-2 rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-100 hover:bg-slate-800"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        <div className="grid gap-3 rounded-md border border-slate-800 bg-slate-900/60 p-3 md:grid-cols-4">
          <label className="space-y-1 text-xs text-slate-400">
            <span className="inline-flex items-center gap-1">
              <Filter className="h-3.5 w-3.5" /> Task name
            </span>
            <input
              value={taskNameFilter}
              onChange={(event) => setTaskNameFilter(event.target.value)}
              placeholder="backtests.run"
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-2.5 py-2 text-sm text-slate-100"
            />
          </label>
          <label className="space-y-1 text-xs text-slate-400">
            <span>Queue</span>
            <input
              value={queueFilter}
              onChange={(event) => setQueueFilter(event.target.value)}
              placeholder="celery"
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-2.5 py-2 text-sm text-slate-100"
            />
          </label>
          <label className="space-y-1 text-xs text-slate-400">
            <span>Environment</span>
            <input
              value={environmentFilter}
              onChange={(event) => setEnvironmentFilter(event.target.value)}
              placeholder="local / testnet / mainnet"
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-2.5 py-2 text-sm text-slate-100"
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              onClick={() => {
                setStatusFilter('');
                setTaskNameFilter('');
                setQueueFilter('');
                setEnvironmentFilter('');
                setShowAnomaliesOnly(false);
              }}
              className="inline-flex h-10 w-full items-center justify-center rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-200 transition hover:bg-slate-800"
            >
              Clear filters
            </button>
          </div>
        </div>

        <div className="grid gap-3 rounded-md border border-slate-800 bg-slate-900/60 p-3 md:grid-cols-[1fr_auto_auto] md:items-end">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-slate-400">
              Anomaly mode
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Flags failures, stale-active tasks (&gt;15m), and tasks in queues above backlog
              threshold.
            </p>
          </div>
          <label className="space-y-1 text-xs text-slate-400">
            <span>Queue anomaly threshold</span>
            <input
              type="number"
              min={1}
              step={1}
              value={queueAnomalyThreshold}
              onChange={(event) => {
                const next = Number(event.target.value);
                setQueueAnomalyThreshold(Number.isFinite(next) && next > 0 ? Math.floor(next) : 1);
              }}
              className="w-40 rounded-md border border-slate-700 bg-slate-950 px-2.5 py-2 text-sm text-slate-100"
            />
          </label>
          <button
            type="button"
            onClick={() => setShowAnomaliesOnly((value) => !value)}
            className={`inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm transition ${
              showAnomaliesOnly
                ? 'border-amber-400/40 bg-amber-500/10 text-amber-200'
                : 'border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800'
            }`}
            title="Show only failures, stale-active tasks, and tasks in overloaded queues"
          >
            <AlertTriangle className="h-4 w-4" />
            {showAnomaliesOnly
              ? `Only anomalies (${anomalousTasks.length})`
              : `Show only anomalies (${anomalousTasks.length})`}
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-md border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <CheckCircle2 className="h-4 w-4" /> Health
            </div>
            <div className="mt-2 text-xl font-semibold">{health?.status || 'unknown'}</div>
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Clock3 className="h-4 w-4" /> Active
            </div>
            <div className="mt-2 text-xl font-semibold">{activeTasks.length}</div>
            <p className="mt-1 text-xs text-slate-500">Stale over 15m: {staleActiveTasks.length}</p>
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <AlertTriangle className="h-4 w-4" /> Failed
            </div>
            <div className="mt-2 text-xl font-semibold">{failedTasks.length}</div>
            <p className="mt-1 text-xs text-slate-500">
              Success rate: {successRate !== null ? `${successRate.toFixed(1)}%` : 'n/a'}
            </p>
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Server className="h-4 w-4" /> Workers
            </div>
            <div className="mt-2 text-xl font-semibold">{workers?.total ?? 0}</div>
            <p className="mt-1 text-xs text-slate-500">
              Queue backlog: {queueInsights.totalBacklog}
            </p>
          </div>
        </div>

        <div className="rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-100">
          <span className="font-semibold">Anomalies:</span> {anomalousTasks.length} tasks · stale{' '}
          {staleActiveTasks.length} · failed {failedTasks.length} · overloaded queues{' '}
          {anomalousQueueNames.size} (threshold {queueAnomalyThreshold})
        </div>

        <div className="flex flex-wrap gap-2">
          {statusCounts.map(([status, count]) => (
            <span
              key={status}
              className={`inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium ${statusTone(status)}`}
            >
              {status}: {count}
            </span>
          ))}
        </div>

        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
          <div className="overflow-hidden rounded-md border border-slate-800 bg-slate-900">
            <div className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">
              Tasks
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-950 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Task</th>
                    <th className="px-4 py-3">State</th>
                    <th className="px-4 py-3">Queue / Worker</th>
                    <th className="px-4 py-3">Runtime</th>
                    <th className="px-4 py-3">Progress</th>
                    <th className="px-4 py-3">Context</th>
                    <th className="px-4 py-3">Updated</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {visibleTasks.map((task) => {
                    const runtime = taskRuntimeSeconds(task);
                    const stale = isStaleActiveTask(task);
                    const anomalyReasons = anomalyReasonsForTask(task, anomalousQueueNames);
                    const taskQueue = String(task.queue || '').trim();

                    return (
                      <tr
                        key={task.task_id}
                        className={`hover:bg-slate-800/60 ${stale ? 'bg-amber-500/5' : ''}`}
                      >
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            onClick={() => setSelectedTask(task)}
                            className="max-w-70 truncate text-left font-mono text-xs text-sky-300"
                          >
                            {task.task_id}
                          </button>
                          <div className="mt-1 text-xs text-slate-500">
                            {task.task_name || 'unknown task'}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded px-2 py-1 text-xs font-medium ${statusTone(task.status)}`}
                          >
                            {task.status}
                          </span>
                          {anomalyReasons.length > 0 && (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {anomalyReasons.map((reason) => {
                                const toneClass =
                                  reason === 'failure'
                                    ? 'bg-rose-500/15 text-rose-200'
                                    : reason === 'stale-active'
                                      ? 'bg-amber-500/15 text-amber-200'
                                      : 'bg-cyan-500/15 text-cyan-200';

                                const baseClass = `inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide transition hover:brightness-110 ${toneClass}`;

                                if (reason === 'failure') {
                                  return (
                                    <button
                                      key={`${task.task_id}-${reason}`}
                                      type="button"
                                      onClick={() => {
                                        setStatusFilter('FAILURE');
                                        setShowAnomaliesOnly(false);
                                      }}
                                      className={baseClass}
                                      title="Filter task list to failures"
                                    >
                                      {reason}
                                    </button>
                                  );
                                }

                                if (reason === 'stale-active') {
                                  return (
                                    <button
                                      key={`${task.task_id}-${reason}`}
                                      type="button"
                                      onClick={() => {
                                        setShowAnomaliesOnly(true);
                                        setStatusFilter('');
                                      }}
                                      className={baseClass}
                                      title="Focus anomaly view for stale-active triage"
                                    >
                                      {reason}
                                    </button>
                                  );
                                }

                                if (reason === 'queue-pressure' && taskQueue) {
                                  return (
                                    <button
                                      key={`${task.task_id}-${reason}`}
                                      type="button"
                                      onClick={() => setQueueFilter(taskQueue)}
                                      className={baseClass}
                                      title={`Filter tasks by queue: ${taskQueue}`}
                                    >
                                      {reason}
                                    </button>
                                  );
                                }

                                return (
                                  <span
                                    key={`${task.task_id}-${reason}`}
                                    className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${toneClass}`}
                                  >
                                    {reason}
                                  </span>
                                );
                              })}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-300">
                          <div>{task.queue || '—'}</div>
                          <div className="text-slate-500">
                            {task.worker_hostname || 'unassigned'}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-300">
                          <div className="inline-flex items-center gap-1">
                            <Timer className="h-3.5 w-3.5 text-slate-500" />
                            {formatDuration(runtime)}
                          </div>
                          {stale && (
                            <div className="mt-1 text-[11px] text-amber-300">stale-active</div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <div className="h-2 w-28 overflow-hidden rounded bg-slate-800">
                            <div
                              className="h-full bg-sky-400"
                              style={{ width: `${progressValue(task)}%` }}
                            />
                          </div>
                          <div className="mt-1 text-xs text-slate-400">
                            {progressValue(task).toFixed(1)}%
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-300">
                          <div>{task.current_step || '—'}</div>
                          <div className="text-slate-500">
                            {task.backtest_run_id || task.bot_id || task.environment || '—'}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-400">
                          <div>{formatDate(taskUpdatedAt(task))}</div>
                          <div className="text-slate-500">
                            {formatRelativeAge(taskUpdatedAt(task))}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              title="Revoke task"
                              onClick={() => void revoke(task)}
                              className="rounded-md border border-slate-700 p-2 text-slate-300 hover:bg-slate-800"
                            >
                              <Ban className="h-4 w-4" />
                            </button>
                            <button
                              type="button"
                              title="Retry failed task"
                              disabled={String(task.status).toUpperCase() !== 'FAILURE'}
                              onClick={() => void retry(task)}
                              className="rounded-md border border-slate-700 p-2 text-slate-300 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              <RotateCcw className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {visibleTasks.length === 0 && (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                        {showAnomaliesOnly
                          ? 'No anomalous tasks match current filters.'
                          : 'No Celery tasks found.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-5">
            <div className="rounded-md border border-slate-800 bg-slate-900">
              <div className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">
                Queues ({queueInsights.totalBacklog} pending)
              </div>
              <div className="divide-y divide-slate-800">
                {queueInsights.rows.map((queue) => (
                  <div key={queue.name} className="px-4 py-3 text-sm">
                    <div className="flex items-center justify-between">
                      <span>{queue.name}</span>
                      <span className="text-slate-400">{queue.length}</span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded bg-slate-800">
                      <div
                        className="h-full bg-cyan-400"
                        style={{
                          width: `${Math.min(100, queueInsights.totalBacklog > 0 ? (queue.length / queueInsights.totalBacklog) * 100 : 0)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
                {queueInsights.rows.length === 0 && (
                  <div className="px-4 py-3 text-sm text-slate-500">
                    No queue telemetry available.
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-md border border-slate-800 bg-slate-900">
              <div className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">
                Workers
              </div>
              <div className="divide-y divide-slate-800">
                {workerSummaries.map((worker) => (
                  <div key={worker.hostname} className="px-4 py-3 text-xs text-slate-300">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-slate-100">{worker.hostname}</span>
                      <span className="text-slate-500">{worker.status}</span>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-slate-400">
                      <span className="inline-flex items-center gap-1">
                        <Activity className="h-3.5 w-3.5" />
                        {worker.activeTasks} active
                      </span>
                      <span>{worker.queueCount} queues</span>
                      <span>{worker.registeredTasks} registered</span>
                    </div>
                  </div>
                ))}
                {workerSummaries.length === 0 && (
                  <div className="px-4 py-3 text-sm text-slate-500">No workers reported.</div>
                )}
              </div>
            </div>

            <div className="rounded-md border border-slate-800 bg-slate-900">
              <div className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">
                Failure hotspots
              </div>
              <div className="divide-y divide-slate-800">
                {failureHotspots.map((item) => (
                  <div
                    key={item.label}
                    className="flex items-center justify-between gap-3 px-4 py-3 text-xs"
                  >
                    <span className="text-slate-300">{item.label}</span>
                    <span className="rounded bg-rose-500/10 px-2 py-1 text-rose-200">
                      {item.count}
                    </span>
                  </div>
                ))}
                {failureHotspots.length === 0 && (
                  <div className="px-4 py-3 text-sm text-slate-500">
                    No failure clusters detected.
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-md border border-slate-800 bg-slate-900">
              <div className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">
                Selected Task
              </div>
              {selectedTask ? (
                <div className="space-y-3 p-4 text-sm">
                  <div className="font-mono text-xs text-sky-300">{selectedTask.task_id}</div>
                  {selectedTask.error_message && (
                    <div className="text-rose-200">{selectedTask.error_message}</div>
                  )}
                  {selectedTask.traceback && (
                    <details className="rounded-md border border-slate-800 bg-slate-950 p-3">
                      <summary className="cursor-pointer text-slate-300">Traceback</summary>
                      <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap text-xs text-slate-300">
                        {selectedTask.traceback}
                      </pre>
                    </details>
                  )}
                  <div className="grid gap-2 rounded-md border border-slate-800 bg-slate-950 p-3 text-xs text-slate-300 sm:grid-cols-2">
                    <div>
                      Queue: <span className="text-slate-100">{selectedTask.queue || '—'}</span>
                    </div>
                    <div>
                      Worker:{' '}
                      <span className="text-slate-100">{selectedTask.worker_hostname || '—'}</span>
                    </div>
                    <div>
                      Runtime:{' '}
                      <span className="text-slate-100">
                        {formatDuration(taskRuntimeSeconds(selectedTask))}
                      </span>
                    </div>
                    <div>
                      Retries:{' '}
                      <span className="text-slate-100">{selectedTask.retry_count ?? 0}</span>
                    </div>
                  </div>
                  <pre className="max-h-72 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-300">
                    {JSON.stringify(selectedTask, null, 2)}
                  </pre>
                </div>
              ) : (
                <div className="p-4 text-sm text-slate-500">Select a task to inspect metadata.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminCeleryPage;
