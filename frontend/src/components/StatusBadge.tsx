import React from 'react';
import type { JobStatus } from '../api/types';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

const STATUS_STYLES: Record<JobStatus, string> = {
  pending: 'bg-amber-900/60 text-amber-300 border border-amber-700',
  running: 'bg-blue-900/60 text-blue-300 border border-blue-700',
  completed: 'bg-emerald-900/60 text-emerald-300 border border-emerald-700',
  failed: 'bg-rose-900/60 text-rose-300 border border-rose-700',
  cancelled: 'bg-slate-700 text-slate-300 border border-slate-600',
};

const FALLBACK_STYLE = 'bg-slate-700 text-slate-300 border border-slate-600';

function normalizeStatus(raw: string): JobStatus | null {
  const lower = raw.toLowerCase().trim();
  // Map legacy values to canonical
  const legacyMap: Record<string, JobStatus> = {
    queued: 'pending',
    created: 'pending',
    retry: 'running',
    retrying: 'running',
    success: 'completed',
    done: 'completed',
    error: 'failed',
    stopped: 'cancelled',
    canceled: 'cancelled',
  };
  if (lower in STATUS_STYLES) return lower as JobStatus;
  if (lower in legacyMap) return legacyMap[lower];
  return null;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'sm' }) => {
  const canonical = normalizeStatus(status);
  const styles = canonical ? STATUS_STYLES[canonical] : FALLBACK_STYLE;
  const displayLabel = canonical ?? status.toLowerCase();
  const isRunning = canonical === 'running';

  const sizeClass = size === 'md' ? 'px-2.5 py-1 text-xs' : 'px-2 py-0.5 text-[10px]';

  return (
    <span
      className={`inline-flex items-center gap-1 rounded font-semibold uppercase whitespace-nowrap ${sizeClass} ${styles}`}
    >
      {isRunning && (
        <span className="relative flex h-1.5 w-1.5 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-blue-400" />
        </span>
      )}
      {displayLabel}
    </span>
  );
};
