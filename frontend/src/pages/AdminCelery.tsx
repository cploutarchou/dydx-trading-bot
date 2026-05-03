import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock3,
  RefreshCw,
  RotateCcw,
  Server,
} from 'lucide-react';
import api, {
  type CeleryHealthResponse,
  type CeleryQueuesResponse,
  type CeleryTask,
  type CeleryTasksResponse,
  type CeleryWorkersResponse,
} from '../api';
import { useAuthStore } from '../store/auth';

const ADMIN_ROLES = new Set(['admin', 'super_admin', 'backoffice_admin']);

const statusTone = (status?: string) => {
  const normalized = String(status || '').toUpperCase();
  if (normalized === 'SUCCESS' || normalized === 'COMPLETED') return 'text-emerald-300 bg-emerald-500/10';
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

export const AdminCeleryPage: React.FC = () => {
  const user = useAuthStore((state) => state.user);
  const flowerUrl = String(import.meta.env.VITE_FLOWER_URL || '').trim();
  const [tasks, setTasks] = useState<CeleryTask[]>([]);
  const [health, setHealth] = useState<CeleryHealthResponse | null>(null);
  const [workers, setWorkers] = useState<CeleryWorkersResponse | null>(null);
  const [queues, setQueues] = useState<CeleryQueuesResponse | null>(null);
  const [selectedTask, setSelectedTask] = useState<CeleryTask | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isStrictAdmin = Boolean(user?.is_admin) || ADMIN_ROLES.has(String(user?.role || ''));

  const load = useCallback(async () => {
    if (!isStrictAdmin) return;
    setLoading(true);
    setError(null);
    try {
      const [tasksResponse, healthResponse, workersResponse, queuesResponse] = await Promise.all([
        api.listCeleryTasks(statusFilter ? { status: statusFilter } : undefined),
        api.getCeleryHealth(),
        api.getCeleryWorkers(),
        api.getCeleryQueues(),
      ]);
      const taskData = (tasksResponse.data || {}) as CeleryTasksResponse;
      setTasks(Array.isArray(taskData.tasks) ? taskData.tasks : []);
      setHealth((healthResponse.data || null) as CeleryHealthResponse | null);
      setWorkers((workersResponse.data || null) as CeleryWorkersResponse | null);
      setQueues((queuesResponse.data || null) as CeleryQueuesResponse | null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load Celery telemetry');
    } finally {
      setLoading(false);
    }
  }, [isStrictAdmin, statusFilter]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  const failedTasks = useMemo(
    () => tasks.filter((task) => ['FAILURE', 'REVOKED'].includes(String(task.status).toUpperCase())),
    [tasks]
  );
  const activeTasks = useMemo(
    () => tasks.filter((task) => ['STARTED', 'PROGRESS', 'PENDING', 'RETRY'].includes(String(task.status).toUpperCase())),
    [tasks]
  );

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
        <h1 className="text-2xl font-semibold">Forbidden</h1>
        <p className="mt-2 text-sm text-slate-400">Admin access is required.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-5 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <div className="flex flex-col gap-3 border-b border-slate-800 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-normal">Celery Operations</h1>
            <p className="mt-1 text-sm text-slate-400">Admin task inspection, worker health, and controlled task actions.</p>
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

        {error && (
          <div className="flex items-center gap-2 rounded-md border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400"><CheckCircle2 className="h-4 w-4" /> Health</div>
            <div className="mt-2 text-xl font-semibold">{health?.status || 'unknown'}</div>
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400"><Clock3 className="h-4 w-4" /> Active</div>
            <div className="mt-2 text-xl font-semibold">{activeTasks.length}</div>
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400"><AlertTriangle className="h-4 w-4" /> Failed</div>
            <div className="mt-2 text-xl font-semibold">{failedTasks.length}</div>
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400"><Server className="h-4 w-4" /> Workers</div>
            <div className="mt-2 text-xl font-semibold">{workers?.total ?? 0}</div>
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
          <div className="overflow-hidden rounded-md border border-slate-800 bg-slate-900">
            <div className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">Tasks</div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-950 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Task</th>
                    <th className="px-4 py-3">State</th>
                    <th className="px-4 py-3">Progress</th>
                    <th className="px-4 py-3">Context</th>
                    <th className="px-4 py-3">Updated</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {tasks.map((task) => (
                    <tr key={task.task_id} className="hover:bg-slate-800/60">
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => setSelectedTask(task)}
                          className="max-w-[280px] truncate text-left font-mono text-xs text-sky-300"
                        >
                          {task.task_id}
                        </button>
                        <div className="mt-1 text-xs text-slate-500">{task.task_name || 'unknown task'}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`rounded px-2 py-1 text-xs font-medium ${statusTone(task.status)}`}>
                          {task.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-2 w-28 overflow-hidden rounded bg-slate-800">
                          <div className="h-full bg-sky-400" style={{ width: `${progressValue(task)}%` }} />
                        </div>
                        <div className="mt-1 text-xs text-slate-400">{progressValue(task).toFixed(1)}%</div>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-300">
                        <div>{task.current_step || '—'}</div>
                        <div className="text-slate-500">{task.backtest_run_id || task.bot_id || task.environment || '—'}</div>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">{formatDate(task.finished_at || task.started_at || task.created_at)}</td>
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
                  ))}
                  {tasks.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-500">No Celery tasks found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-5">
            <div className="rounded-md border border-slate-800 bg-slate-900">
              <div className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">Queues</div>
              <div className="divide-y divide-slate-800">
                {(queues?.queues || []).map((queue) => (
                  <div key={queue.name} className="flex items-center justify-between px-4 py-3 text-sm">
                    <span>{queue.name}</span>
                    <span className="text-slate-400">{queue.length ?? 'unknown'}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-slate-800 bg-slate-900">
              <div className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">Selected Task</div>
              {selectedTask ? (
                <div className="space-y-3 p-4 text-sm">
                  <div className="font-mono text-xs text-sky-300">{selectedTask.task_id}</div>
                  {selectedTask.error_message && <div className="text-rose-200">{selectedTask.error_message}</div>}
                  {selectedTask.traceback && (
                    <details className="rounded-md border border-slate-800 bg-slate-950 p-3">
                      <summary className="cursor-pointer text-slate-300">Traceback</summary>
                      <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap text-xs text-slate-300">{selectedTask.traceback}</pre>
                    </details>
                  )}
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
