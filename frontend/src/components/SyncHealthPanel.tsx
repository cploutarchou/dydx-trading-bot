import { Activity, AlertTriangle, Loader } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import api from '../api';
import { enhancedApiClient } from '../api/enhancedClient';

interface SyncHealthRun {
  run_id: string;
  status: string;
  trades: number;                    // Primary: delegated artifact-backed trade availability
  backend_mirrored_trades?: number;  // Debug: legacy backend DB mirror count (if available)
  positions: number;
  candles: number;
  sync_lag_seconds?: number;
  run_age_seconds?: number;
  quality_issues?: string[];
}

interface BotDBSyncDiagnostics {
  active: boolean;
  remainingSeconds: number;
  state: string;
}

const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const toNumber = (value: unknown, fallback = 0): number => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

const toStringValue = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;

const toIssues = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];

const normalizeBotDBSyncDiagnostics = (raw: unknown): BotDBSyncDiagnostics | null => {
  const payload = toRecord(raw);
  const diagnostics = toRecord(payload.bot_db_sync);
  if (Object.keys(diagnostics).length === 0) {
    return null;
  }

  return {
    active: Boolean(diagnostics.active),
    remainingSeconds: toNumber(diagnostics.remaining_seconds, 0),
    state: toStringValue(diagnostics.state, 'unknown'),
  };
};

const normalizeRuns = (raw: unknown): SyncHealthRun[] => {
  const payload = toRecord(raw);
  const root = toRecord(payload.data);
  const candidates =
    (Array.isArray(root.runs) && root.runs) ||
    (Array.isArray(root.items) && root.items) ||
    (Array.isArray(payload.runs) && payload.runs) ||
    (Array.isArray(payload.items) && payload.items) ||
    [];

  return candidates
    .map((item) => toRecord(item))
    .filter((item) => toStringValue(item.run_id).length > 0)
    .map((item) => ({
      run_id: toStringValue(item.run_id),
      status: toStringValue(item.status, 'unknown').toUpperCase(),
      trades: toNumber(item.trades),
      backend_mirrored_trades: toNumber(item.backend_mirrored_trades, undefined),
      positions: toNumber(item.positions),
      candles: toNumber(item.candles),
      sync_lag_seconds: toNumber(item.sync_lag_seconds, 0),
      run_age_seconds: toNumber(item.run_age_seconds, 0),
      quality_issues: toIssues(item.quality_issues),
    }));
};

const isRunActive = (status: string): boolean => status === 'RUNNING' || status === 'PENDING';

const formatAge = (seconds?: number): string => {
  const safe = Number(seconds);
  if (!Number.isFinite(safe) || safe <= 0) return '-';
  if (safe < 60) return `${Math.round(safe)}s`;
  if (safe < 3600) return `${Math.round(safe / 60)}m`;
  return `${(safe / 3600).toFixed(1)}h`;
};

export const SyncHealthPanel: React.FC = () => {
  const [runs, setRuns] = useState<SyncHealthRun[]>([]);
  const [botDBSync, setBotDBSync] = useState<BotDBSyncDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    let failureCount = 0;

    const scheduleNext = (delayMs: number) => {
      if (cancelled) return;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      timerRef.current = setTimeout(() => {
        void loadSyncHealth();
      }, delayMs);
    };

    const loadSyncHealth = async () => {
      try {
        const [response, systemStatus] = await Promise.all([
          api.getBacktestSyncHealth(),
          enhancedApiClient.getSystemStatus(),
        ]);
        if (cancelled) return;

        const parsed = normalizeRuns(response);
        const botDBSyncDiagnostics = normalizeBotDBSyncDiagnostics(systemStatus);
        setRuns(parsed);
        setBotDBSync(botDBSyncDiagnostics);
        setError(null);
        failureCount = 0;
        scheduleNext(10000);
      } catch (err: unknown) {
        if (cancelled) return;

        failureCount = Math.min(failureCount + 1, 4);
        const nextDelay = Math.min(10000 * 2 ** failureCount, 60000);
        setError(err instanceof Error ? err.message : 'Failed to load sync health');
        scheduleNext(nextDelay);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadSyncHealth();

    return () => {
      cancelled = true;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  const activeRuns = useMemo(() => runs.filter((run) => isRunActive(run.status)), [runs]);

  const warnCount = useMemo(
    () =>
      runs.filter((run) => {
        const status = run.status;
        const shouldWarn = status === 'COMPLETED' || isRunActive(status);
        if (!shouldWarn) return false;
        return run.trades === 0 || run.positions === 0 || run.candles === 0;
      }).length,
    [runs]
  );

  const hasBotDBSyncCooldown = botDBSync?.active === true;

  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
            <Activity className="h-4 w-4 text-cyan-400" />
            Run Sync Health
          </h3>
          <p className="mt-0.5 text-xs text-slate-400">
            Delegated artifact-backed trades (primary) + legacy DB mirror counts (debug)
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {warnCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full border border-yellow-700 bg-yellow-900/40 px-2 py-1 text-[10px] uppercase tracking-wide text-yellow-300">
              <AlertTriangle className="h-3 w-3" /> {warnCount} warning{warnCount !== 1 ? 's' : ''}
            </span>
          )}
          {hasBotDBSyncCooldown && (
            <span
              className="inline-flex items-center gap-1 rounded-full border border-amber-700 bg-amber-900/40 px-2 py-1 text-[10px] uppercase tracking-wide text-amber-200"
              title={`DB sync cooldown active (${Math.ceil(botDBSync?.remainingSeconds || 0)}s remaining)`}
            >
              <AlertTriangle className="h-3 w-3" />
              DB sync cooldown · {Math.ceil(botDBSync?.remainingSeconds || 0)}s
            </span>
          )}
        </div>
      </div>

      {hasBotDBSyncCooldown && (
        <div className="mb-3 rounded-lg border border-amber-700/70 bg-amber-900/25 px-3 py-2 text-xs text-amber-100">
          Persistence writes are temporarily throttled due to upstream DB pressure. Runtime state
          remains active; sync retry state is{' '}
          <span className="font-semibold">{botDBSync?.state || 'unknown'}</span>.
        </div>
      )}

      {loading ? (
        <div className="flex min-h-24 items-center justify-center gap-2 text-sm text-slate-400">
          <Loader className="h-4 w-4 animate-spin text-blue-400" /> Loading sync health...
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-700 bg-red-900/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      ) : runs.length === 0 ? (
        <p className="py-5 text-sm text-slate-400">No sync-health runs reported yet.</p>
      ) : (
        <div className="space-y-2">
          {runs.slice(0, 6).map((run) => {
            const warn =
              (run.status === 'COMPLETED' || isRunActive(run.status)) &&
              (run.trades === 0 || run.positions === 0 || run.candles === 0);
            return (
              <div
                key={run.run_id}
                className={`rounded-lg border px-3 py-2 ${warn ? 'border-yellow-700 bg-yellow-900/20' : 'border-slate-700 bg-slate-900/50'}`}
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-blue-300">{run.run_id}</span>
                  <span className="text-[11px] text-slate-400">{run.status}</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs text-slate-300">
                  <span>
                    Trades:{' '}
                    <span className={run.trades === 0 ? 'text-yellow-300' : 'text-slate-100'}>
                      {run.trades}
                    </span>
                  </span>
                  <span>
                    Positions:{' '}
                    <span className={run.positions === 0 ? 'text-yellow-300' : 'text-slate-100'}>
                      {run.positions}
                    </span>
                  </span>
                  <span>
                    Candles:{' '}
                    <span className={run.candles === 0 ? 'text-yellow-300' : 'text-slate-100'}>
                      {run.candles}
                    </span>
                  </span>
                </div>
                {run.backend_mirrored_trades !== undefined && run.backend_mirrored_trades !== null && (
                  <div className="mt-1 text-xs text-slate-500">
                    <span className="text-slate-600">DB Mirror:</span> {run.backend_mirrored_trades}
                  </div>
                )}
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
                  <span>Lag: {formatAge(run.sync_lag_seconds)}</span>
                  <span>Age: {formatAge(run.run_age_seconds)}</span>
                  {run.quality_issues && run.quality_issues.length > 0 && (
                    <span className="text-yellow-300">
                      Issues: {run.quality_issues.slice(0, 2).join(', ')}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
          {activeRuns.length > 0 && (
            <p className="pt-1 text-[11px] text-blue-300">
              {activeRuns.length} active run{activeRuns.length !== 1 ? 's' : ''} currently syncing.
            </p>
          )}
        </div>
      )}
    </div>
  );
};
