import { AlertTriangle, Database } from 'lucide-react';
import React from 'react';
import { useBacktestSyncHealth } from '../api/hooks';

interface SyncHealthPanelProps {
  activeRunIds?: string[];
}

const toStatus = (status: unknown): string => String(status || '').toUpperCase();

export const SyncHealthPanel: React.FC<SyncHealthPanelProps> = ({ activeRunIds = [] }) => {
  const { data, isLoading, error } = useBacktestSyncHealth(undefined, true);

  const runs = Array.isArray(data?.runs) ? data.runs : [];

  const visibleRuns = runs.slice(0, 5);

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-4">
        <p className="text-sm text-slate-400">Loading sync health...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-700/60 bg-red-900/30 p-4 text-sm text-red-200">
        Unable to load sync health panel.
      </div>
    );
  }

  if (visibleRuns.length === 0) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Database className="h-4 w-4 text-cyan-400" />
        <h3 className="text-sm font-semibold text-white">Run Sync Health</h3>
      </div>

      <div className="space-y-2">
        {visibleRuns.map((run) => {
          const status = toStatus(run.status);
          const shouldWarn =
            (status === 'RUNNING' || status === 'COMPLETED' || activeRunIds.includes(run.run_id)) &&
            ((run.trades ?? 0) === 0 || (run.positions ?? 0) === 0 || (run.candles ?? 0) === 0);

          return (
            <div
              key={run.run_id}
              className={`rounded-lg border px-3 py-2 ${
                shouldWarn
                  ? 'border-yellow-700/70 bg-yellow-900/20'
                  : 'border-slate-700/70 bg-slate-900/40'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-mono text-xs text-slate-300">{run.run_id}</span>
                {shouldWarn && <AlertTriangle className="h-3.5 w-3.5 text-yellow-400" />}
              </div>
              <div className="mt-1 grid grid-cols-3 gap-2 text-[11px] text-slate-400">
                <span>trades: {run.trades ?? 0}</span>
                <span>positions: {run.positions ?? 0}</span>
                <span>candles: {run.candles ?? 0}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

